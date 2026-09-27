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
from datetime import date, datetime, time, timedelta
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
    out = json.loads(
        resources.files("fieldforge.seeds").joinpath("dicts.json").read_text(encoding="utf-8"))
    out["tpa"] = json.loads(
        resources.files("fieldforge.seeds").joinpath("tpa_s1.json").read_text(encoding="utf-8"))
    return out


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
        dispatch = {
            "standard_sensor_set": self._model_sensor_set,
            "arps_production": self._model_arps,
            "daily_sensor_readings": self._model_sensor_readings,
            "master_wells": self._model_master_wells,
            "tpa_daily_production": self._model_tpa_daily_production,
            "tpa_water_injection": self._model_tpa_water_injection,
            "tpa_overhaul": self._model_tpa_overhaul,
            "tpa_measures": self._model_tpa_measures,
            "tpa_fluid_test": self._model_tpa_fluid_test,
            "tpa_equip_status": self._model_tpa_equip_status,
            "tpa_monthly_settlement": self._model_tpa_monthly_settlement,
            "tpa_injection_connection": self._model_tpa_injection_connection,
            "subdaily_sensor_readings": self._model_subdaily_sensor_readings,
            "well_log_curves": self._model_well_log_curves,
        }
        if ent.model not in dispatch:
            raise NotImplementedError(f"未知模型：{ent.model}")
        return dispatch[ent.model](ent)

    def _model_sensor_set(self, ent: EntitySpec) -> list[dict]:
        catalog_key = (ent.model_params or {}).get("catalog", "sensor_catalog")
        catalog = self.seeds["tpa"]["sensor_catalog"] if catalog_key == "tpa" else self.seeds[catalog_key]
        rows = []
        for w in self._well_rows():
            for entry in catalog:
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

    # ---- 合同 schema（tpa 生产域 8 表字典，P0） ----------------------------

    def _tpa_wells(self, wtype: str | None = None) -> list[dict]:
        wells = self.tables.get("well_info", [])
        return [w for w in wells if wtype is None or w["well_type"] == wtype]

    def _well_rows(self) -> list[dict]:
        """井主表：合同 schema 为 well_info，core 为 well。"""
        return self.tables.get("well_info") or self.tables.get("well", [])

    def _model_master_wells(self, ent: EntitySpec) -> list[dict]:
        """主数据 profile：120 井 = 86 EW + 34 IW，3 区块 × 5 平台，N-02 式井号。"""
        p = ent.model_params
        tpa = self.seeds["tpa"]
        blocks, platforms = tpa["blocks"], tpa["platforms"]
        wells, seq = [], {b["letter"]: 0 for b in blocks}
        for wtype in ["EW"] * int(p["count_ew"]) + ["IW"] * int(p["count_iw"]):
            blk = self.rng.choice(blocks)
            seq[blk["letter"]] += 1
            wells.append({
                "well_id": f"{blk['letter']}-{seq[blk['letter']]:02d}",
                "well_name": f"{blk['name']}{seq[blk['letter']]:02d}",
                "well_type": wtype,
                "first_prod_date": date(2019, 1, 1) + timedelta(days=self.rng.randint(0, 730)),
                "platform": self.rng.choice(platforms),
                "block_name": blk["name"],
                "field_name": f"{blk['name']}油田",
                "current_status": self.rng.choices(p["status_values"], weights=p["status_weights"], k=1)[0],
                "remarks": "",
            })
        return wells

    def _model_tpa_daily_production(self, ent: EntitySpec) -> list[dict]:
        """oil_production_daily：EW 井 × 日，产量骨架与 core 同族（Arps + 含水爬升 + 停机）。"""
        p = ent.model_params
        days = self.recipe.days
        start = self.recipe.start
        denom = max(days - 1, 1)
        sigma = float(p["noise_sigma"])
        p_down = float(p["downtime_prob_per_day"])
        blocks = {b["name"]: b["density"] for b in self.seeds["tpa"]["blocks"]}
        rows = []
        for w in self._tpa_wells("EW"):
            density = blocks[w["block_name"]]
            qi = self.rng.uniform(*p["initial_oil_rate_t_per_d"])
            b = self.rng.uniform(*p["arps_b"])
            di = self.rng.uniform(*p["arps_di_per_day"])
            wc0 = self.rng.uniform(*p["water_cut_start"])
            wc1 = self.rng.uniform(*p["water_cut_end"])
            plan = round(qi * self.rng.uniform(*p["plan_factor"]), 2)
            p0 = self.rng.uniform(*p["initial_pressure_mpa"])
            for t in range(days):
                row = {"well_id": w["well_id"], "prod_date": start + timedelta(days=t)}
                shift = self.rng.choices(["A", "B", "C"], weights=[0.4, 0.35, 0.25], k=1)[0]
                if self.rng.random() < p_down:
                    row.update(oil_output=0.0, liquid_output=0.0, water_cut=0.0,
                               plan_output=plan, open_days=0.0, oil_pressure=0.0,
                               report_shift=shift)
                else:
                    q = qi / (1.0 + b * di * t) ** (1.0 / b)
                    oil = max(0.0, q * math.exp(self.rng.gauss(0.0, sigma)))
                    wc = min(0.95, wc0 + (wc1 - wc0) * (t / denom))
                    liquid = oil / ((1.0 - wc) * density)
                    press = min(max(p0 * (q / qi) ** 0.5 + self.rng.gauss(0.0, 0.15), 0.0), 40.0)
                    row.update(oil_output=round(oil, 2), liquid_output=round(liquid, 2),
                               water_cut=round(wc * 100.0, 2), plan_output=plan,
                               open_days=24.0, oil_pressure=round(press, 2),
                               report_shift=shift)
                rows.append(row)
        return rows

    def _model_tpa_water_injection(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        days = self.recipe.days
        start = self.recipe.start
        rows = []
        for w in self._tpa_wells("IW"):
            target = self.rng.uniform(*p["target_inj_volume_m3_per_d"])
            pp0 = self.rng.uniform(*p["pump_pressure_mpa"])
            picks = self.rng.sample(["P1", "P2", "P3"], self.rng.randint(2, 3))
            raw = [self.rng.uniform(20.0, 80.0) for _ in picks]
            total = sum(raw)
            split = ":".join(f"{k}:{round(v / total * 100)}" for k, v in zip(picks, raw))
            for t in range(days):
                row = {"well_id": w["well_id"], "prod_date": start + timedelta(days=t),
                       "layer_split": split}
                if self.rng.random() < p["downtime_prob_per_day"]:
                    row.update(inj_volume=0.0, pump_pressure=0.0)
                else:
                    row.update(inj_volume=round(max(0.0, target * math.exp(self.rng.gauss(0.0, 0.04))), 2),
                               pump_pressure=round(min(max(pp0 + self.rng.gauss(0.0, 0.3), 0.0), 25.0), 2))
                rows.append(row)
        return rows

    def _model_tpa_overhaul(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        tpa = self.seeds["tpa"]
        days = self.recipe.days
        start = self.recipe.start
        oil_sum: dict[str, float] = {}
        for r in self.tables["oil_production_daily"]:
            oil_sum[r["well_id"]] = oil_sum.get(r["well_id"], 0.0) + r["oil_output"]
        mean_oil = {k: v / max(days, 1) for k, v in oil_sum.items()}
        rows = []
        for w in self.tables["well_info"]:
            if self.rng.random() >= p["event_prob_per_well"]:
                continue
            dur = self.rng.randint(int(p["duration_days"][0]), int(p["duration_days"][1]))
            s = start + timedelta(days=self.rng.randint(0, max(days - dur - 1, 0)))
            affected = round(mean_oil.get(w["well_id"], 0.0) * dur * 0.8, 2) if w["well_type"] == "EW" else 0.0
            rows.append({"well_id": w["well_id"], "overhaul_start": s,
                         "overhaul_end": s + timedelta(days=dur - 1),
                         "overhaul_type": self.rng.choice(tpa["overhaul_types"]),
                         "affected_output": affected,
                         "batch_id": f"{s:%Y%m%d}-T1"})
        return rows

    def _model_tpa_measures(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        tpa = self.seeds["tpa"]
        days = self.recipe.days
        start = self.recipe.start
        rows = []
        for w in self._tpa_wells("EW"):
            if self.rng.random() >= p["event_prob_per_well"]:
                continue
            used: set[date] = set()
            for _ in range(self.rng.randint(1, 2)):
                job = start + timedelta(days=self.rng.randint(10, max(days - 100, 11)))
                while job in used:  # 主键 (well_id, job_date) 防碰撞
                    job = job + timedelta(days=self.rng.randint(30, 60))
                used.add(job)
                eff = self.rng.randint(int(p["effective_days"][0]), int(p["effective_days"][1]))
                rows.append({"well_id": w["well_id"],
                             "measure_type": self.rng.choice(tpa["measure_types"]),
                             "job_date": job, "effective_from": job,
                             "effective_to": job + timedelta(days=eff),
                             "incr_oil_annual": round(self.rng.uniform(*p["incr_oil_annual_t"]), 2)})
        return rows

    def _model_tpa_fluid_test(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        blocks = {b["name"]: b["density"] for b in self.seeds["tpa"]["blocks"]}
        wc_by_well_date = {(r["well_id"], r["prod_date"]): r["water_cut"]
                           for r in self.tables["oil_production_daily"]}
        days = self.recipe.days
        start = self.recipe.start
        rows = []
        for w in self._tpa_wells("EW"):
            d = self.rng.randint(0, 20)
            while d < days:
                prod_date = start + timedelta(days=d)
                wc = wc_by_well_date.get((w["well_id"], prod_date), 0.0)
                density = min(max(blocks[w["block_name"]] + self.rng.gauss(0.0, 0.005),
                                  p["density_range"][0]), p["density_range"][1])
                rows.append({"well_id": w["well_id"], "sample_date": prod_date,
                             "water_cut_lab": round(min(max(wc + self.rng.gauss(0.0, 1.5), 0.0), 100.0), 2),
                             "density": round(density, 3),
                             "api_gravity": round(141.5 / density - 131.5, 1)})
                d += self.rng.randint(int(p["interval_days"][0]), int(p["interval_days"][1]))
        return rows

    def _model_tpa_equip_status(self, ent: EntitySpec) -> list[dict]:
        p = ent.model_params
        tpa = self.seeds["tpa"]
        rows = []
        for w in self._tpa_wells("EW"):
            rows.append({"equip_id": f"EQ-{w['well_id']}",
                         "equip_type": self.rng.choices(tpa["equip_types"],
                                                        weights=p["equip_type_weights"], k=1)[0],
                         "load": round(self.rng.uniform(*p["load_range"]), 1),
                         "current": round(self.rng.uniform(*p["current_range"]), 1),
                         "stop_reason_code": self.rng.choices(tpa["stop_reason_codes"],
                                                              weights=p["stop_reason_weights"], k=1)[0]})
        return rows

    def _model_tpa_injection_connection(self, ent: EntitySpec) -> list[dict]:
        """受效关系：每口注水井连 1–3 口同区块受效油井，劈分系数（整数百分比分摊）合计恰为 1。"""
        p = ent.model_params
        producers_by_block: dict[str, list[str]] = {}
        for w in self._tpa_wells("EW"):
            producers_by_block.setdefault(w["block_name"], []).append(w["well_id"])
        rows = []
        for w in self._tpa_wells("IW"):
            pool = [wid for wid in producers_by_block.get(w["block_name"], []) if wid != w["well_id"]]
            if not pool:
                continue
            n = min(self.rng.randint(int(p["min_producers"]), int(p["max_producers"])), len(pool))
            picked = self.rng.sample(pool, n)
            pct = [self.rng.randint(10, 80) for _ in range(n)]
            total = sum(pct)
            pcts = [round(v / total * 100) for v in pct]
            pcts[-1] = max(0, 100 - sum(pcts[:-1]))
            if sum(pcts) != 100:  # 取整损耗补到最大份，保证合计恰为 100
                pcts[pcts.index(max(pcts))] += 100 - sum(pcts)
            resp = self.recipe.start + timedelta(days=self.rng.randint(0, int(p["response_start_max_days"])))
            for wid, share in zip(picked, pcts):
                rows.append({"injector_well_id": w["well_id"], "producer_well_id": wid,
                             "split_coefficient": round(share / 100.0, 2),
                             "response_start_date": resp})
        return rows

    def _model_subdaily_sensor_readings(self, ent: EntitySpec) -> list[dict]:
        """P2-T3 亚日读数（拍板：分层采样）：前 wells_limit 口 EW 重点井 × 15 分钟档全期。

        日内曲线 = 日度骨架状态 × 96 读数 + 高频微噪声；停机日整段静稳常值。
        交付建议 Parquet（~21 万行/2 井/年）；规则 11（零值 2 小时告警）在本表启用。
        """
        p = ent.model_params
        limit = int(p.get("wells_limit", 2))
        step = int(p.get("interval_minutes", 15))
        per_day = 24 * 60 // step
        rows = []
        ledgers: dict[str, list[dict]] = {}
        for r in self.tables["oil_production_daily"]:
            ledgers.setdefault(r["well_id"], []).append(r)
        for w in self._tpa_wells("EW")[:limit]:
            wid = w["well_id"]
            ledger = ledgers.get(wid, [])
            oil_max = max((r["oil_output"] for r in ledger), default=0.0) or 1.0
            for ch in self.tables["sensor_channel"]:
                if ch["well_id"] != wid:
                    continue
                span = ch["range_max"] - ch["range_min"]
                if ch["channel_code"] == "WHT":
                    flow_frac, static_frac = self.rng.uniform(0.50, 0.70), self.rng.uniform(0.18, 0.25)
                elif ch["channel_code"] == "CGP":
                    flow_frac, static_frac = self.rng.uniform(0.60, 0.80), self.rng.uniform(0.60, 0.70)
                else:
                    flow_frac, static_frac = self.rng.uniform(0.55, 0.75), self.rng.uniform(0.60, 0.70)
                sigma = span * 0.005
                for r in ledger:
                    down = r["open_days"] == 0.0
                    base = ch["range_min"] + (static_frac if down
                                              else flow_frac * (r["oil_output"] / oil_max)) * span
                    day0 = datetime.combine(r["prod_date"], time.min)
                    for k in range(per_day):
                        if down:
                            value = base  # 停机时段整段静稳
                        else:
                            value = min(max(base + self.rng.gauss(0.0, sigma),
                                            ch["range_min"]), ch["range_max"])
                        rows.append({"well_id": wid, "channel_id": ch["channel_id"],
                                     "ts": day0 + timedelta(minutes=k * step),
                                     "value": round(value, 3)})
        return rows

    def _model_well_log_curves(self, ent: EntitySpec) -> list[dict]:
        """M5-T1（收窄版）：测井曲线合成——FORCE 2020 记忆码 + 12 类岩性标签。

        产状 = 岩性分段（按厚度随机分区）+ 图版典型值 + 噪声；无真实数据（Owner 决策），
        全部取自 seeds 图版表（典型测井响应值，教学/合成用途）。
        交付建议 Parquet（120 井 × 2401 采样点 ≈ 28.8 万行）。
        """
        p = ent.model_params
        tpa = self.seeds["tpa"]
        chart = tpa["lithology_chart"]
        codes = list(chart)
        weights = [tpa["lithology_weights"][c] for c in codes]
        d0, d1 = float(p["depth_start_m"]), float(p["depth_end_m"])
        step = float(p["step_m"])
        thick_lo, thick_hi = p["zone_thickness_m"]
        rows = []
        for w in self._tpa_wells():
            wid = w["well_id"]
            depth = d0
            zone = None
            zone_left = 0.0
            while depth <= d1 + 1e-9:
                if zone_left <= 0.0:
                    code = self.rng.choices(codes, weights=weights, k=1)[0]
                    zone = chart[code]
                    zone_left = self.rng.uniform(*p["zone_thickness_m"])
                def _c(col: str, v: float) -> float:
                    rng_decl = ent.fields[col].raw.get("range")
                    return min(max(v, rng_decl[0]), rng_decl[1]) if rng_decl else v

                props = {
                    "gr": _c("gr", zone["gr"] * math.exp(self.rng.gauss(0.0, 0.20))),
                    "rhob": _c("rhob", zone["rhob"] + self.rng.gauss(0.0, 0.05)),
                    "nphi": _c("nphi", zone["nphi"] + self.rng.gauss(0.0, 0.04)),
                    "rdep": _c("rdep", zone["rdep"] * math.exp(self.rng.gauss(0.0, 0.40))),
                    "dtc": _c("dtc", zone["dtc"] + self.rng.gauss(0.0, 5.0)),
                    "cali": _c("cali", zone["cali"] + self.rng.gauss(0.0, 0.3)),
                    "pef": _c("pef", zone["pef"] + self.rng.gauss(0.0, 0.4)),
                }
                rows.append({
                    "well_id": wid, "depth_md": round(depth, 1),
                    "gr": round(max(0.0, props["gr"]), 2),
                    "rhob": round(props["rhob"], 3),
                    "nphi": round(props["nphi"], 4),
                    "rdep": round(max(0.1, props["rdep"]), 3),
                    "dtc": round(props["dtc"], 2),
                    "cali": round(props["cali"], 2),
                    "pef": round(max(0.1, props["pef"]), 2),
                    "lithology": code,
                })
                depth += step
                zone_left -= step
        return rows

    def _model_tpa_monthly_settlement(self, ent: EntitySpec) -> list[dict]:
        """区块 × 结算月净重量 = 该区块当月油量合计 × (1−损耗率)；损耗 ≤ 规则 12 的 3%。"""
        p = ent.model_params
        block_of = {w["well_id"]: w["block_name"] for w in self.tables["well_info"]}
        sums: dict[tuple, float] = {}
        for r in self.tables["oil_production_daily"]:
            key = (block_of[r["well_id"]], r["prod_date"].replace(day=1))
            sums[key] = sums.get(key, 0.0) + r["oil_output"]
        loss = float(p["loss_ratio"])
        rows = [{"block_name": block, "settle_date": month,
                 "net_weight": round(total * (1.0 - loss), 2)}
                for (block, month), total in sorted(sums.items())]
        return rows

    def _model_sensor_readings(self, ent: EntitySpec) -> list[dict]:
        """M2-T3：日度读数 = 生产骨架驱动（流量联动）+ 停机静稳 + 微噪声。

        每井每通道一次性抽取工况参数，读数值按通道量程截断；
        停机日取静稳常值（无噪声，便于机判静稳）。
        兼容 core（production_daily/oil_rate/producing_hours）与合同 schema
        （oil_production_daily/oil_output/open_days）两套生产表列名。
        """
        prod_table = "oil_production_daily" if self.tables.get("oil_production_daily") else "production_daily"
        prod_rows = self.tables[prod_table]
        hours_col = "open_days" if (prod_rows and "open_days" in prod_rows[0]) else "producing_hours"
        rate_col = "oil_output" if (prod_rows and "oil_output" in prod_rows[0]) else "oil_rate"
        ledgers: dict[str, list[dict]] = {}
        for src in (prod_rows, self.tables.get("water_injection_daily", [])):
            for r in src:  # 采油井挂产油台账，注水井挂注水台账
                ledgers.setdefault(r["well_id"], []).append(r)
        rows = []
        for w in self._well_rows():
            wid = w["well_id"]
            ledger = ledgers.get(wid, [])
            drivers = [(r, next((r[c] for c in (rate_col, "inj_volume") if c in r), 0.0))
                       for r in ledger]
            oil_max = max((d for _, d in drivers), default=0.0) or 1.0
            for ch in self.tables["sensor_channel"]:
                if ch["well_id"] != wid:
                    continue
                span = ch["range_max"] - ch["range_min"]
                if ch["channel_code"] == "WHT":
                    flow_frac = self.rng.uniform(0.50, 0.70)   # 满产温度位
                    static_frac = self.rng.uniform(0.18, 0.25)  # 环境温度档
                elif ch["channel_code"] == "CGP":
                    flow_frac = self.rng.uniform(0.60, 0.80)   # 套压略高于油压
                    static_frac = self.rng.uniform(0.60, 0.70)
                else:  # WHP 油压/泵压
                    flow_frac = self.rng.uniform(0.55, 0.75)
                    static_frac = self.rng.uniform(0.60, 0.70)  # 关井后井口压力回升
                sigma = span * 0.01
                for r, driver in drivers:
                    if r.get(hours_col, 24.0) == 0.0 or driver == 0.0:
                        value = ch["range_min"] + static_frac * span  # 静稳常值
                    else:
                        value = ch["range_min"] + flow_frac * (driver / oil_max) * span
                        value = min(max(value + self.rng.gauss(0.0, sigma),
                                        ch["range_min"]), ch["range_max"])
                    rows.append({
                        "well_id": wid,
                        "channel_id": ch["channel_id"],
                        "reading_date": r["prod_date"],
                        "value": round(value, 3),
                    })
        return rows
