"""M2-T2 噪声/工况注入器 v1。

- 作用于"骨架表"（M1 规则骨架 / M2-T1 物理骨架同接口），与骨架生成解耦：
  现挂 M1 规则骨架先行，T1 到位后无缝替换。
- 注入随机流独立于骨架生成流（base_seed + injection.seed）：调骨架参数不扰动注入结果。
- 注入点不落标记列（保持数据真实感）；精确位置由 seed 复现重建，计数入 manifest，
  供 F7 评估闸门（M3）以同 seed 重建 ground truth 对账。
- 纪律：注入后数据仍须过符合性检查——坏点截在量程内；量程违例型坏点的"检测"属评估闸门，不在此处。
"""
from __future__ import annotations

import random

INJECTOR_VERSION = "1.0.0"


def apply_injections(schema, tables: dict[str, list[dict]], cfg: dict, base_seed: int):
    """按配方 injection 声明注入。返回 (注入后的 tables, manifest 记录)。"""
    if not cfg:
        return tables, {"enabled": False}

    eff_seed = base_seed + int(cfg.get("seed", 1000))
    rng = random.Random(eff_seed)
    info: dict = {
        "enabled": True,
        "version": INJECTOR_VERSION,
        "seed": eff_seed,
        "params": cfg,
        "counts": {},
    }

    # 固定应用顺序保证可复现：连续停机 → 坏点 → 缺测（丢行放最后，避免行号漂移）
    for name in ("maintenance_window", "spike", "gap"):
        section = cfg.get(name)
        if not section:
            continue
        entity = section.get("entity", "production_daily")
        rows = tables.get(entity)
        if rows is None:
            info["counts"][name] = {"error": f"实体 {entity} 不存在，跳过"}
            continue
        ent_spec = schema.entities[entity]
        if name == "maintenance_window":
            windows, days = _maintenance_window(rows, section, rng)
            info["counts"][name] = {"windows": windows, "days": days}
        elif name == "spike":
            info["counts"][name] = {"points": _spike(rows, ent_spec, section, rng)}
        elif name == "gap":
            info["counts"][name] = {"removed_rows": _gap(rows, section, rng)}
    return tables, info


def _maintenance_window(rows: list[dict], section: dict, rng: random.Random):
    """计划性修井/停机窗口：连续多日 producing_hours=0 且产量归零。"""
    hours_field = section.get("hours_field", "producing_hours")
    zero_fields = section.get("zero_fields", ["oil_rate", "water_rate", "gas_rate"])
    count = int(section.get("count", 0))
    lo, hi = section.get("length_days", [3, 8])
    windows = days = 0
    for _ in range(count):
        length = rng.randint(int(lo), int(hi))
        start = rng.randint(0, max(len(rows) - length - 1, 0))
        for row in rows[start : start + length]:
            if float(row.get(hours_field, 24.0)) > 0:
                row[hours_field] = 0.0
                for f in zero_fields:
                    if f in row:
                        row[f] = 0.0
                days += 1
        windows += 1
    return windows, days


def _spike(rows: list[dict], ent_spec, section: dict, rng: random.Random) -> int:
    """坏点（尖刺）：字段值乘随机因子后截在 schema 量程内；停机行不打点。"""
    fname = section["field"]
    prob = float(section.get("prob_per_day", 0.01))
    lo, hi = section.get("factor", [1.5, 2.0])
    skip_zero = section.get("skip_zero_field", "producing_hours")
    rng_decl = ent_spec.fields[fname].raw.get("range") if fname in ent_spec.fields else None
    hits = 0
    for row in rows:
        v = row.get(fname)
        if v is None:
            continue
        if skip_zero and float(row.get(skip_zero, 24.0)) == 0.0:
            continue
        if rng.random() < prob:
            spiked = float(v) * rng.uniform(lo, hi)
            if rng_decl:
                spiked = min(max(spiked, rng_decl[0]), rng_decl[1])
            row[fname] = round(spiked, 4)
            hits += 1
    return hits


def _gap(rows: list[dict], section: dict, rng: random.Random) -> int:
    """缺测：整段删除行，日期出现空洞。"""
    count = int(section.get("count", 0))
    lo, hi = section.get("length_days", [1, 2])
    removed = 0
    for _ in range(count):
        length = rng.randint(int(lo), int(hi))
        start = rng.randint(0, max(len(rows) - length, 0))
        del rows[start : start + length]
        removed += length
    return removed
