"""噪声/工况注入器 + 平台脏特征注入器家族（F4 / P1-T1）。

两类注入共用一个框架（统一签名 tables/entity/section/rng/schema）：
- 通用工况扰动（M2-T2）：maintenance_window / spike / gap；
- tpa 平台脏特征（P1-T1，交付物而非缺陷——每条都被平台质量规则或 W-DP 断言消费）：
  shift_duplicate（A/B 班重复行→规则 1）、plan_dual_value（配产版本切换日双值→规则 1）、
  unit_misentry（"12.40 方"式单位误录→规则 3）、well_id_legacy（N2/N-2 旧写法→规则 7）、
  stale_constant（恒值 30 日→规则 10）、late_batch（T-3 补录批次→规则 6）、
  status_lag（状态滞后→规则 9）、legacy_stop_code（新旧编码并存/未知码→规则 8）、
  measure_missing（措施缺效期缺失→完整性）、lab_conflict（化验 vs 计量打架→规则 4）。

纪律：
- 注入随机流独立于骨架生成流（base_seed + injection.seed），同 seed 可复现；
- 注入点不落标记列，计数入 manifest——供平台规则族以同 seed 重建 ground truth；
- dirty_mode: true 时符合性检查跳过 fk/enum（脏值按设计存在），日期/量程/缺失仍校验。
"""
from __future__ import annotations

import random
from datetime import timedelta

INJECTOR_VERSION = "2.0.0"

# 旧停机原因码映射（规则 8"新旧编码映射表"的 fieldforge 侧声明；R3=皮带断取形自 tpa 设定书）
LEGACY_CODE_MAP = {"BELT": "R3", "MOTOR": "R4", "PUMP": "R5", "POWER": "R6"}


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
        "dirty_mode": bool(cfg.get("dirty_mode")),
        "params": cfg,
        "counts": {},
    }

    # 固定按声明键排序应用，保证可复现
    for name in sorted(k for k in cfg if k not in ("seed", "dirty_mode")):
        fn = _INJECTORS.get(name)
        if fn is None:
            continue
        section = cfg[name] or {}
        entity = section.get("entity", _DEFAULT_ENTITY.get(name))
        rows = tables.get(entity)
        if rows is None:
            info["counts"][name] = {"error": f"实体 {entity} 不存在，跳过"}
            continue
        info["counts"][name] = fn(tables, entity, section, rng, schema)
    return tables, info


# ---- 通用工况扰动（M2-T2） ----------------------------------------------

def _inj_maintenance_window(tables, entity, section, rng, schema):
    rows = tables[entity]
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
    return {"windows": windows, "days": days}


def _inj_spike(tables, entity, section, rng, schema):
    """坏点（尖刺）：字段值 ×随机因子；量程取自 schema 声明（无声明则不截断）；停机行不打点。"""
    rows = tables[entity]
    fname = section["field"]
    prob = float(section.get("prob_per_day", 0.01))
    lo, hi = section.get("factor", [1.5, 2.0])
    skip_zero = section.get("skip_zero_field", "producing_hours")
    rng_decl = None
    if schema is not None and entity in schema.entities and fname in schema.entities[entity].fields:
        rng_decl = schema.entities[entity].fields[fname].raw.get("range")
    hits = 0
    for row in rows:
        v = row.get(fname)
        if v is None:
            continue
        if skip_zero and float(row.get(skip_zero, 24.0) or 0.0) == 0.0:
            continue
        if rng.random() < prob:
            spiked = float(v) * rng.uniform(lo, hi)
            if rng_decl:
                spiked = min(max(spiked, rng_decl[0]), rng_decl[1])
            row[fname] = round(spiked, 4)
            hits += 1
    return {"points": hits}


def _inj_gap(tables, entity, section, rng, schema):
    rows = tables[entity]
    count = int(section.get("count", 0))
    lo, hi = section.get("length_days", [1, 2])
    removed = 0
    for _ in range(count):
        length = rng.randint(int(lo), int(hi))
        start = rng.randint(0, max(len(rows) - length, 0))
        del rows[start : start + length]
        removed += length
    return {"removed_rows": removed}


# ---- tpa 平台脏特征（P1-T1） --------------------------------------------

def _inj_shift_duplicate(tables, entity, section, rng, schema):
    """A/B 班重复上报：随机抽行原样复制插到原行之后（主键重复，规则 1 挂样本）。"""
    rows = tables[entity]
    count = min(int(section.get("count", 0)), len(rows))
    idx = set(rng.sample(range(len(rows)), count) if count else [])
    out, dup = [], 0
    for i, row in enumerate(rows):
        out.append(row)
        if i in idx:
            out.append(dict(row))
            dup += 1
    tables[entity] = out
    return {"duplicated_rows": dup}


def _inj_plan_dual_value(tables, entity, section, rng, schema):
    """配产版本切换日双值：季度首日行复制一份并改 plan_output（规则 1 + 口径双值样本）。"""
    rows = tables[entity]
    factor = float(section.get("factor", 1.1))
    out, dup = [], 0
    for row in rows:
        out.append(row)
        d = row.get("prod_date")
        if d is not None and d.day == 1 and d.month in (1, 4, 7, 10):
            dual = dict(row)
            dual["plan_output"] = round(float(row["plan_output"]) * factor, 2)
            out.append(dual)
            dup += 1
    tables[entity] = out
    return {"dual_rows": dup}


def _inj_unit_misentry(tables, entity, section, rng, schema):
    """单位误录：液量漏折算密度（折算密度=1.0 越规则 3 上界）或方/桶混淆（×6.29）。"""
    rows = tables[entity]
    count = int(section.get("count", 0))
    flowing = [r for r in rows if float(r.get("oil_output", 0) or 0) > 0
               and 0 < float(r.get("water_cut", 0) or 0) < 100]
    idx = set(rng.sample(range(len(flowing)), min(count, len(flowing))) if count else [])
    hits = 0
    for j, r in enumerate(flowing):
        if j not in idx:
            continue
        oil, wc = float(r["oil_output"]), float(r["water_cut"]) / 100.0
        if hits % 2 == 0:  # 漏折算密度（吨→方未除密度）
            r["liquid_output"] = round(oil / (1.0 - wc), 2)
        else:  # 方/桶混淆（×6.29 桶/m³）
            r["liquid_output"] = round(float(r["liquid_output"]) * 6.29, 2)
        hits += 1
    return {"misentered_rows": hits}


def _inj_well_id_legacy(tables, entity, section, rng, schema):
    """井号旧写法：部分行 well_id 改为 N2 / N-2 式（归一化前的形态，规则 7 挂样本）。"""
    rows = tables[entity]
    count = int(section.get("count", 0))
    idx = set(rng.sample(range(len(rows)), min(count, len(rows))) if count else [])
    hits = 0
    for i, r in enumerate(rows):
        if i not in idx:
            continue
        wid = r["well_id"]
        if "-" not in wid:
            continue
        letter, seq = wid.split("-", 1)
        r["well_id"] = f"{letter}{seq}" if i % 2 == 0 else f"{letter}-{int(seq)}"
        hits += 1
    return {"legacy_rows": hits}


def _inj_stale_constant(tables, entity, section, rng, schema):
    """恒值 30 日：选井取连续 30 个生产日，油量冻结为窗口首日值（规则 10 告警样本）。"""
    rows = tables[entity]
    wells = int(section.get("wells", 1))
    window = int(section.get("window", 30))
    by_well: dict[str, list[dict]] = {}
    for r in rows:
        by_well.setdefault(r["well_id"], []).append(r)
    ew_wells = [k for k, v in by_well.items() if len(v) >= window]
    if not ew_wells:
        return {"frozen_windows": 0}
    chosen = rng.sample(ew_wells, min(wells, len(ew_wells)))
    frozen = 0
    for wid in chosen:
        seq = by_well[wid]
        start = rng.randint(0, len(seq) - window)
        anchor = float(seq[start]["oil_output"])
        for r in seq[start : start + window]:
            r["oil_output"] = anchor
            r["open_days"] = 24.0
            wc = float(r["water_cut"]) / 100.0
            density = 0.86  # 冻结窗口内保持量纲自洽，避免误触规则 3
            r["liquid_output"] = round(anchor / ((1.0 - wc) * density), 2) if wc < 1 else 0.0
        frozen += 1
    return {"frozen_windows": frozen, "window_days": window}


def _inj_late_batch(tables, entity, section, rng, schema):
    """T-3 补录批次：部分 batch_id 由 -T1 改 -T3（规则 6 超窗挂样本）。"""
    rows = tables[entity]
    ratio = float(section.get("ratio", 0.2))
    hits = 0
    for r in rows:
        bid = r.get("batch_id", "")
        if bid.endswith("-T1") and rng.random() < ratio:
            r["batch_id"] = bid[:-3] + "-T3"
            hits += 1
    return {"late_batches": hits}


def _inj_status_lag(tables, entity, section, rng, schema):
    """状态滞后：制造"近 30 日全停、档案仍标生产中"的井（规则 9 挂样本）。

    选尾窗 30 行齐全的井，强制其近 30 日全停（open_days=0、产量归零），
    档案 current_status 保持/置为"生产中"——滞后未更新。
    """
    wells = tables[entity]
    prod = tables.get("oil_production_daily", [])
    count = int(section.get("count", 3))
    tail = max((r["prod_date"] for r in prod), default=None)
    if tail is None:
        return {"lagged_wells": 0}
    cut = tail - timedelta(days=30)  # 与规则 9 的 31 行尾窗对齐（tail−30 … tail）
    by_well: dict[str, list[dict]] = {}
    for r in prod:
        if r["prod_date"] >= cut:
            by_well.setdefault(r["well_id"], []).append(r)
    candidates = [wid for wid, rows in by_well.items() if len(rows) >= 31]
    chosen = rng.sample(candidates, min(count, len(candidates))) if candidates else []
    hits = 0
    for wid in chosen:
        for r in by_well[wid]:
            r.update(oil_output=0.0, liquid_output=0.0, water_cut=0.0,
                     open_days=0.0, oil_pressure=0.0)
        for w in wells:
            if w["well_id"] == wid and w["current_status"] != "生产中":
                w["current_status"] = "生产中"  # 滞后未更新
                break
        hits += 1
    return {"lagged_wells": hits}


def _inj_legacy_stop_code(tables, entity, section, rng, schema):
    """新旧编码并存：部分非 RUNNING 行改旧码（映射全命中=规则 8 通过态）；未知码另计（挂样本）。"""
    rows = tables[entity]
    ratio = float(section.get("ratio", 0.15))
    unknown = int(section.get("unknown_count", 0))
    legacy = unknown_hits = 0
    for r in rows:
        code = r.get("stop_reason_code")
        if code in LEGACY_CODE_MAP and rng.random() < ratio:
            r["stop_reason_code"] = LEGACY_CODE_MAP[code]
            legacy += 1
    for r in rows:
        if unknown_hits >= unknown:
            break
        if r.get("stop_reason_code") != "RUNNING":
            r["stop_reason_code"] = "LEGACY-OLD"
            unknown_hits += 1
    return {"legacy_rows": legacy, "unknown_rows": unknown_hits}


def _inj_measure_missing(tables, entity, section, rng, schema):
    """措施缺效期缺失：约 ratio 比例行清空 effective_from/to（完整性脏特征）。"""
    rows = tables[entity]
    ratio = float(section.get("ratio", 0.3))
    hits = 0
    for r in rows:
        if rng.random() < ratio:
            r["effective_from"] = ""
            r["effective_to"] = ""
            hits += 1
    return {"missing_rows": hits}


def _inj_lab_conflict(tables, entity, section, rng, schema):
    """化验 vs 计量打架：化验含水偏移 6–15 个百分点（规则 4 挂样本，容差 5pp）。"""
    rows = tables[entity]
    count = int(section.get("count", 0))
    idx = set(rng.sample(range(len(rows)), min(count, len(rows))) if count else [])
    hits = 0
    for j, r in enumerate(rows):
        if j not in idx:
            continue
        wc = float(r.get("water_cut_lab", 0.0))
        delta = rng.uniform(6.0, 15.0) * (1 if j % 2 == 0 else -1)
        r["water_cut_lab"] = round(min(max(wc + delta, 0.0), 100.0), 2)
        hits += 1
    return {"conflict_rows": hits}


_INJECTORS = {
    "maintenance_window": _inj_maintenance_window,
    "spike": _inj_spike,
    "gap": _inj_gap,
    "shift_duplicate": _inj_shift_duplicate,
    "plan_dual_value": _inj_plan_dual_value,
    "unit_misentry": _inj_unit_misentry,
    "well_id_legacy": _inj_well_id_legacy,
    "stale_constant": _inj_stale_constant,
    "late_batch": _inj_late_batch,
    "status_lag": _inj_status_lag,
    "legacy_stop_code": _inj_legacy_stop_code,
    "measure_missing": _inj_measure_missing,
    "lab_conflict": _inj_lab_conflict,
}

_DEFAULT_ENTITY = {
    "shift_duplicate": "oil_production_daily",
    "plan_dual_value": "oil_production_daily",
    "unit_misentry": "oil_production_daily",
    "well_id_legacy": "oil_production_daily",
    "stale_constant": "oil_production_daily",
    "late_batch": "well_overhaul",
    "status_lag": "well_info",
    "legacy_stop_code": "equip_status",
    "measure_missing": "well_measures",
    "lab_conflict": "fluid_test",
    "maintenance_window": "production_daily",
    "gap": "production_daily",
}
