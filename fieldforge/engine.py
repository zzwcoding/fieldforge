"""L1 规则打底生成引擎。

- 全部随机性经 random.Random(seed)：同种子同输出；跨 Python 小版本的随机序列
  不保证一致，manifest 记录生成时的 Python 版本。
- production_daily 目前是"规则骨架"（Arps 递减 + 含水率爬升 + 停机事件 +
  乘性对数正态噪声），M2 由 OPM Flow 独立进程扫参替换骨架，模型接口不变。
"""
from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from importlib import resources

from .schema import EntitySpec, Recipe, Schema

# schema 字段名 → 传感器目录键
_SENSOR_FIELD_MAP = {
    "channel_code": "code",
    "channel_name": "name",
    "unit": "unit",
    "range_min": "range_min",
    "range_max": "range_max",
    "sample_interval_min": "sample_interval_min",
}


def load_seeds() -> dict:
    raw = resources.files("fieldforge.seeds").joinpath("dicts.json").read_text(encoding="utf-8")
    return json.loads(raw)


def _clip(v: float, rng_decl: list) -> float:
    lo, hi = rng_decl
    return min(max(v, lo), hi)


class Engine:
    def __init__(self, schema: Schema, recipe: Recipe, seed: int):
        self.schema = schema
        self.recipe = recipe
        self.rng = random.Random(seed)
        self.seeds = load_seeds()
        self.tables: dict[str, list[dict]] = {}

    def generate(self) -> dict[str, list[dict]]:
        """按 schema 声明顺序生成全部实体。"""
        for name, ent in self.schema.entities.items():
            self.tables[name] = self._gen_static(name, ent) if ent.model is None else self._gen_model(name, ent)
        return self.tables

    # ---- 静态实体：逐行独立，字段按声明顺序由生成器填充 --------------------

    def _gen_static(self, name: str, ent: EntitySpec) -> list[dict]:
        fk_field = next((fs for fs in ent.fields.values() if fs.type == "fk"), None)
        rows: list[dict] = []
        if fk_field is None:
            for _ in range(int(self.recipe.counts.get(name, 1))):
                row: dict = {}
                ctx: dict = {}
                for fname, fs in ent.fields.items():
                    row[fname] = self._gen_value(fs, row, ctx, None)
                rows.append(row)
            return rows

        parent_entity = fk_field.raw["fk"]["entity"]
        parent_field = fk_field.raw["fk"]["field"]
        for parent_row in self.tables[parent_entity]:
            row: dict = {}
            ctx: dict = {}
            for fname, fs in ent.fields.items():
                if fs.type == "fk":
                    row[fname] = parent_row[parent_field]
                else:
                    row[fname] = self._gen_value(fs, row, ctx, parent_row)
            rows.append(row)
        return rows

    def _gen_value(self, fs, row: dict, ctx: dict, parent_row: dict | None):
        gen = fs.raw.get("generator")
        if gen == "oil_field_name":
            entry = self.rng.choice(self.seeds["oil_fields"])
            ctx["oil_field"] = entry
            return entry["name"]
        if gen == "well_id":
            return f"{ctx['oil_field']['code']}-{self.rng.randint(1, 9)}-{self.rng.randint(1, 99)}"
        if gen == "wellbore_id":
            return f"{parent_row['well_id']}-B1"
        if gen == "channel_id":
            return f"{parent_row['well_id']}-{row['channel_code']}"
        if gen == "date_range":
            d0 = fs.raw["params"]["start"]
            d1 = fs.raw["params"]["end"]
            return d0 + timedelta(days=self.rng.randint(0, (d1 - d0).days))
        if gen == "date_after_parent":
            p = fs.raw["params"]
            return parent_row[p["parent_field"]] + timedelta(days=self.rng.randint(int(p["min_days"]), int(p["max_days"])))
        if gen == "float_range":
            return round(self.rng.uniform(*fs.raw["range"]), 6)
        if gen == "integer_range":
            return self.rng.randint(*fs.raw["range"])
        if fs.type == "enum":
            weights = fs.raw.get("weights")
            if weights:
                return self.rng.choices(fs.raw["values"], weights=weights, k=1)[0]
            return self.rng.choice(fs.raw["values"])
        raise NotImplementedError(f"字段 {fs.name} 缺少可用生成器（generator）声明")

    # ---- 模型实体：整段序列/整组行一次成型 ---------------------------------

    def _gen_model(self, name: str, ent: EntitySpec) -> list[dict]:
        if ent.model == "standard_sensor_set":
            return self._model_sensor_set(ent)
        if ent.model == "arps_production":
            return self._model_arps(ent)
        raise NotImplementedError(f"未知模型：{ent.model}")

    def _model_sensor_set(self, ent: EntitySpec) -> list[dict]:
        rows = []
        for w in self.tables["well"]:
            for entry in self.seeds["sensor_catalog"]:
                row: dict = {"well_id": w["well_id"]}
                for fname in ent.fields:
                    if fname == "well_id":
                        continue
                    if fname == "channel_id":
                        row[fname] = f"{w['well_id']}-{entry['code']}"
                    else:
                        row[fname] = entry[_SENSOR_FIELD_MAP[fname]]
                rows.append(row)
        return rows

    def _model_arps(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        days = self.recipe.days
        start = self.recipe.start
        denom = max(days - 1, 1)
        sigma = float(p["noise_sigma"])
        p_down = float(p["downtime_prob_per_day"])
        rows = []
        for w in self.tables["well"]:
            qi = self.rng.uniform(*p["initial_oil_rate_t_per_d"])
            b = self.rng.uniform(*p["arps_b"])
            di = self.rng.uniform(*p["arps_di_per_day"])
            gor = self.rng.uniform(*p["gor_m3_per_m3"])
            wc0 = self.rng.uniform(*p["water_cut_start"])
            wc1 = self.rng.uniform(*p["water_cut_end"])
            for t in range(days):
                row: dict = {"well_id": w["well_id"], "prod_date": start + timedelta(days=t)}
                if self.rng.random() < p_down:
                    row.update(producing_hours=0.0, oil_rate=0.0, water_rate=0.0, gas_rate=0.0)
                else:
                    hours = min(24.0, max(0.0, self.rng.gauss(23.8, 0.5)))
                    q = qi / (1.0 + b * di * t) ** (1.0 / b)
                    oil = q * (hours / 24.0) * math.exp(self.rng.gauss(0.0, sigma))
                    wc = min(0.95, wc0 + (wc1 - wc0) * (t / denom))
                    water = oil * wc / (1.0 - wc) * math.exp(self.rng.gauss(0.0, sigma))
                    gas = oil * gor / 1e4 * math.exp(self.rng.gauss(0.0, sigma))
                    row["producing_hours"] = round(hours, 1)
                    row["oil_rate"] = round(self._clip_field(oil, ent, "oil_rate"), 4)
                    row["water_rate"] = round(self._clip_field(water, ent, "water_rate"), 4)
                    row["gas_rate"] = round(self._clip_field(gas, ent, "gas_rate"), 4)
                rows.append(row)
        return rows

    def _clip_field(self, v: float, ent: EntitySpec, field: str) -> float:
        rng_decl = ent.fields[field].raw.get("range")
        return _clip(v, rng_decl) if rng_decl else v
