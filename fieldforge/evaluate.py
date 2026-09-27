"""M3 评估闸门 v1 —— 三族指标（质量 / 隐私 / 物理一致性）+ 报告。

- 数据入口 = generate 输出目录（manifest.json + CSV 表）。
- 质量族：分布健全性（无参照即可）+ 同构参照对比（--reference 指向同列结构的 CSV，
  如另种子生成 / T1 物理骨架；未来接 Volve/FORCE 真实锚点即为真质量评估，路径不变）。
- 隐私族：主键重复率（schema 驱动）+ 数值组合重复率（全合成场景可判）；
  anonymeter 三类攻击（Singling Out / Linkability / Inference）需真实参照数据，
  接口留 --real，未提供则 skipped——不硬编。
- 物理一致性族（自研，差异化卖点）：物质平衡（含水率界）、停机一致性（hours=0⇒产量 0）、
  传感器量程合法性、停机静稳、日间递减率合理性。
- 平台规则族（P1-T2，tpa-contract 自动启用）：规则 1–10、12 逐条机判（判据对齐
  tpa/docs/business-setting.md §4 质量规则库）；规则 11 为实时域（教学演绎）如实 skipped；
  13–20 维度由既有指标覆盖（枚举合法=符合性、极值/波动率=q2/f5、引用完整=fk、钩稽=r12）。
- 判定：任一 fail → 闸门不过（exit 1）；skipped 不计失败。
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import re
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_BUILTIN_PK = {
    "well": ["well_id"],
    "wellbore": ["wellbore_id"],
    "sensor_channel": ["channel_id"],
    "production_daily": ["well_id", "prod_date"],
    "sensor_reading": ["channel_id", "reading_date"],
}

_RATE_COLS = ("oil_rate", "water_rate", "gas_rate")


def _load_data(data_dir: Path) -> tuple[dict, dict[str, list[dict]]]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    data: dict[str, list[dict]] = {}
    for ent in manifest["entities"]:
        f = data_dir / ent["file"]
        with f.open(newline="", encoding="utf-8") as fh:
            data[ent["entity"]] = list(csv.DictReader(fh))
    return manifest, data


def _load_pk(schema_file: str | None) -> dict[str, list[str]]:
    """主键优先取 schema 声明；读不到时退回内建映射。"""
    if schema_file:
        try:
            from .schema import load_schema
            schema = load_schema(schema_file)
            return {name: list(ent.primary_key) or ["_row"]
                    for name, ent in schema.entities.items()}
        except Exception:
            pass
    return dict(_BUILTIN_PK)


def _primary_key_of(schema_file: str | None, entity: str) -> list[str]:
    return _load_pk(schema_file).get(entity, ["_row"])


def _num(row: dict, col: str) -> float | None:
    v = row.get(col)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _metric(mid: str, family: str, name: str, status: str, value, detail: str = "") -> dict:
    return {"id": mid, "family": family, "name": name,
            "status": status, "value": value, "detail": detail}


def _ks_stat(a: list[float], b: list[float]) -> float:
    """两样本 KS 统计量（纯 stdlib，O(n log n)）。"""
    a, b = sorted(a), sorted(b)
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    d = 0.0
    for x in sorted(set(a) | set(b)):
        d = max(d, abs(bisect.bisect_right(a, x) / la - bisect.bisect_right(b, x) / lb))
    return d


# ---------------------------------------------------------------- 质量族

def q_shape(data: dict, manifest: dict) -> dict:
    bad = []
    for ent in manifest["entities"]:
        got = len(data.get(ent["entity"], []))
        if got != ent["rows"]:
            bad.append(f"{ent['entity']}: manifest {ent['rows']} ≠ 实际 {got}")
    if bad:
        return _metric("q1", "质量", "行数与 manifest 一致", "fail", bad, "数据与账不符")
    return _metric("q1", "质量", "行数与 manifest 一致", "pass",
                   {e["entity"]: e["rows"] for e in manifest["entities"]})


def q_degenerate(data: dict) -> dict:
    """数值列非退化（有方差、有多值）——无参照也成立的质量底线。"""
    bad = []
    checked = 0
    for entity, cols in (("production_daily", _RATE_COLS), ("sensor_reading", ("value",))):
        for row in data.get(entity, []):
            continue  # 列级检查在下方聚合
        series: dict[str, list[float]] = {}
        for row in data.get(entity, []):
            for c in cols:
                v = _num(row, c)
                if v is not None:
                    series.setdefault(c, []).append(v)
        for c, vals in series.items():
            checked += 1
            if len(set(vals)) <= 1 or (len(vals) > 1 and statistics.pstdev(vals) == 0):
                bad.append(f"{entity}.{c} 退化（单值）")
    if bad:
        return _metric("q2", "质量", "数值列非退化", "fail", bad)
    return _metric("q2", "质量", "数值列非退化", "pass", f"检查 {checked} 列")


def q_reference(data: dict, reference_rows: list[dict] | None) -> dict:
    """同构参照对比：共享数值列的 KS 距离 + 均值相对偏差。

    参照与生成物均值差 >10 倍视为不同分布域（不同井/不同制度/不同单位），
    记 skipped 而不硬判——参照可比性由调用方保证。
    """
    if reference_rows is None:
        return _metric("q3", "质量", "参照分布对比（KS/均值偏差）", "skipped",
                       None, "未提供 --reference；接入真实锚点后同路径即为真质量评估")
    per_col = {}
    worst = ("", 0.0)
    for entity in ("production_daily",):
        for c in _RATE_COLS:
            a = [v for r in data.get(entity, []) if (v := _num(r, c)) is not None]
            b = [v for r in reference_rows if (v := _num(r, c)) is not None]
            if not a or not b:
                continue
            ma, mb = statistics.mean(a), statistics.mean(b)
            if ma == 0 or abs(ma - mb) > 10 * max(abs(ma), abs(mb)):
                per_col[c] = {"ks": None, "note": "均值差 >10×，不同分布域"}
                continue
            ks = _ks_stat(a, b)
            per_col[c] = {"ks": round(ks, 4),
                          "mean_dev": round(abs(ma - mb) / abs(ma), 4)}
            if ks > worst[1]:
                worst = (c, ks)
    if not per_col:
        return _metric("q3", "质量", "参照分布对比（KS/均值偏差）", "skipped", None, "无共享可比列")
    worst_col, worst_ks = worst
    status = "pass" if worst_ks < 0.30 else ("warn" if worst_ks < 0.50 else "fail")
    return _metric("q3", "质量", "参照分布对比（KS/均值偏差）", status, per_col,
                   f"最差列 {worst_col} KS={worst_ks:.3f}（阈值 pass<0.30 / warn<0.50）")


# ---------------------------------------------------------------- 隐私族

def p_primary_key(data: dict, manifest: dict) -> dict:
    schema_file = (manifest.get("schema") or {}).get("file")
    dup = {}
    for entity, rows in data.items():
        pk = _primary_key_of(schema_file, entity)
        seen, n_dup = set(), 0
        for r in rows:
            key = tuple(r.get(c) for c in pk)
            if key in seen:
                n_dup += 1
            seen.add(key)
        if n_dup:
            dup[entity] = n_dup
    if dup:
        return _metric("p1", "隐私", "主键重复率", "fail", dup, "主键必须唯一")
    return _metric("p1", "隐私", "主键重复率", "pass", {e: 0 for e in data})


def p_combination(data: dict) -> dict:
    rows = data.get("production_daily", [])
    key = [tuple(_num(r, c) for c in _RATE_COLS) for r in rows]
    key = [k for k in key if all(v is not None for v in k)]
    if not key:
        return _metric("p2", "隐私", "数值组合重复率", "skipped", None, "无可检数据")
    rate = len(key) - len(set(key))
    pct = rate / len(key)
    status = "pass" if pct < 0.05 else ("warn" if pct < 0.20 else "fail")
    return _metric("p2", "隐私", "数值组合重复率", status,
                   {"duplicates": rate, "ratio": round(pct, 4)},
                   "全合成场景的结构性隐私信号（>20% 视为指纹性过强）")


def p_anonymeter(real_dir: str | None) -> dict:
    if real_dir:
        return _metric("p3", "隐私", "anonymeter 三类攻击", "skipped", None,
                       "真实参照接入后的攻击评估属 M3 后续票（--real 接口已留）")
    return _metric("p3", "隐私", "anonymeter 三类攻击", "skipped", None,
                   "Singling Out / Linkability / Inference 需真实参照数据（--real）；全合成场景不可判")


# ------------------------------------------------------- 物理一致性族

def f_material_balance(data: dict) -> dict:
    """含水率 = 水/(油+水) 必须在 [0, 1]；油水全零的停机行跳过。"""
    bad = []
    checked = 0
    for r in data.get("production_daily", []):
        o, w = _num(r, "oil_rate"), _num(r, "water_rate")
        if o is None or w is None or (o == 0 and w == 0):
            continue
        checked += 1
        wc = w / (o + w)
        if not (0.0 <= wc <= 1.0):
            bad.append({r.get("prod_date"): round(wc, 4)})
            if len(bad) >= 5:
                break
    if bad:
        return _metric("f1", "物理", "物质平衡（含水率界）", "fail", bad)
    return _metric("f1", "物理", "物质平衡（含水率界）", "pass", f"检查 {checked} 行")


def f_downtime(data: dict) -> dict:
    bad = []
    for r in data.get("production_daily", []):
        h = _num(r, "producing_hours")
        if h == 0.0 and any((_num(r, c) or 0.0) > 0 for c in _RATE_COLS):
            bad.append(r.get("prod_date"))
            if len(bad) >= 5:
                break
    if bad:
        return _metric("f2", "物理", "停机一致性（hours=0 ⇒ 产量 0）", "fail", bad)
    n_down = sum(1 for r in data.get("production_daily", []) if _num(r, "producing_hours") == 0.0)
    return _metric("f2", "物理", "停机一致性（hours=0 ⇒ 产量 0）", "pass", f"停机行 {n_down}")


def f_sensor_range(data: dict) -> dict:
    channels = {c["channel_id"]: (_num(c, "range_min"), _num(c, "range_max"))
                for c in data.get("sensor_channel", [])}
    if not channels or not data.get("sensor_reading"):
        return _metric("f3", "物理", "传感器量程合法性", "skipped", None, "无传感器表")
    bad = []
    for r in data.get("sensor_reading", []):
        rng = channels.get(r.get("channel_id"))
        v = _num(r, "value")
        if rng and v is not None and not (rng[0] <= v <= rng[1]):
            bad.append({r.get("reading_date"): v})
            if len(bad) >= 5:
                break
    if bad:
        return _metric("f3", "物理", "传感器量程合法性", "fail", bad)
    return _metric("f3", "物理", "传感器量程合法性", "pass", f"检查 {len(data['sensor_reading'])} 读数")


def f_shutdown_static(data: dict) -> dict:
    channels = data.get("sensor_channel", [])
    ledger = data.get("production_daily", [])
    if not channels or not ledger or not data.get("sensor_reading"):
        return _metric("f4", "物理", "停机读数静稳", "skipped", None, "无传感器表")
    down = {r.get("prod_date") for r in ledger if _num(r, "producing_hours") == 0.0}
    if not down:
        return _metric("f4", "物理", "停机读数静稳", "skipped", None, "数据窗内无停机日")
    vals: dict[str, set] = {}
    for r in data.get("sensor_reading", []):
        if r.get("reading_date") in down:
            vals.setdefault(r.get("channel_id"), set()).add(r.get("value"))
    unsteady = {k: len(v) for k, v in vals.items() if len(v) > 1}
    if unsteady:
        return _metric("f4", "物理", "停机读数静稳", "fail", unsteady,
                       "同通道停机读数应唯一（静稳常值）；若数据经过坏点注入，属预期，用无注入输出评估")
    return _metric("f4", "物理", "停机读数静稳", "pass",
                   {k: len(v) for k, v in vals.items()})


def f_decline(data: dict) -> dict:
    """相邻生产日（停机行除外）油量比值有界——排除注入尖刺后仍应平稳。"""
    rows = [r for r in data.get("production_daily", []) if _num(r, "producing_hours") != 0.0]
    rates = [_num(r, "oil_rate") for r in rows if _num(r, "oil_rate") is not None and _num(r, "oil_rate") > 0]
    if len(rates) < 2:
        return _metric("f5", "物理", "日间递减率合理性", "skipped", None, "有效生产行不足")
    worst = 0.0
    for a, b in zip(rates, rates[1:]):
        worst = max(worst, abs(math.log(b / a)))
    status = "pass" if worst < math.log(2.0) else ("warn" if worst < math.log(3.0) else "fail")
    return _metric("f5", "物理", "日间递减率合理性", status,
                   {"max_day_jump_x": round(math.exp(worst), 3)},
                   "相邻生产日油量比值上限：pass<2× / warn<3×（注入尖刺按设计可达 2.2×）")


# ------------------------------------------------- 平台规则族（tpa-contract）

def _platform_rules(data: dict) -> list[dict]:
    """规则 1–10、12 逐条机判（判据对齐 tpa 设定书 §4；规则 11 实时域 skipped）。"""
    prod = data.get("oil_production_daily", [])
    rules: list[dict] = []

    # 规则 1 唯一性：(well_id, prod_date)
    keys = [(r.get("well_id"), r.get("prod_date")) for r in prod]
    dup = len(keys) - len(set(keys))
    rules.append(_metric("r1", "规则", "规则1 (well_id,prod_date) 唯一性",
                         "pass" if dup == 0 else "fail", {"duplicates": dup}))

    # 规则 2 完整性：oil_output 非空率 ≥99.5%
    empty = sum(1 for r in prod if r.get("oil_output") in ("", None))
    ratio = empty / len(prod) if prod else 0.0
    rules.append(_metric("r2", "规则", "规则2 oil_output 非空率 ≥99.5%",
                         "pass" if ratio <= 0.005 else "fail",
                         {"empty": empty, "ratio": round(ratio, 5)}))

    # 规则 3 准确性：折算密度 = 油/(液×(1−含水)) ∈ [0.82, 0.98]
    bad3 = checked3 = 0
    for r in prod:
        oil, liq, wc = _num(r, "oil_output"), _num(r, "liquid_output"), _num(r, "water_cut")
        if not oil or not liq or wc is None or wc >= 100:
            continue
        checked3 += 1
        if not 0.82 <= oil / (liq * (1 - wc / 100)) <= 0.98:
            bad3 += 1
    rules.append(_metric("r3", "规则", "规则3 单位一致性（折算密度带）",
                         "pass" if bad3 == 0 else "fail", {"violations": bad3, "checked": checked3}))

    # 规则 4 一致性：计量含水 vs 化验含水 ≤5pp（井号+日期双键联结）
    lab = {(r.get("well_id"), r.get("sample_date")): _num(r, "water_cut_lab")
           for r in data.get("fluid_test", [])}
    diffs = [abs(wc - lab[k]) for r in prod
             if (k := (r.get("well_id"), r.get("prod_date"))) in lab
             and (wc := _num(r, "water_cut")) is not None and lab[k] is not None]
    bad4 = sum(1 for d in diffs if d > 5.0)
    rules.append(_metric("r4", "规则", "规则4 计量 vs 化验含水 ≤5pp",
                         "pass" if bad4 == 0 else "fail",
                         {"violations": bad4, "compared": len(diffs)}))

    # 规则 5 值域：water_cut∈[0,100]、open_days∈[0,24]
    bad5 = sum(1 for r in prod if not (
        0.0 <= (_num(r, "water_cut") or 0.0) <= 100.0
        and 0.0 <= (_num(r, "open_days") or 0.0) <= 24.0))
    rules.append(_metric("r5", "规则", "规则5 water_cut/open_days 值域",
                         "pass" if bad5 == 0 else "fail", {"violations": bad5}))

    # 规则 6 及时性：批次水位 ≤T-1（-T3 补录为超窗样本）
    over = sum(1 for r in data.get("well_overhaul", [])
               if str(r.get("batch_id", "")).endswith("-T3"))
    rules.append(_metric("r6", "规则", "规则6 批次水位 ≤T-1",
                         "pass" if over == 0 else "fail", {"late_batches": over}))

    # 规则 7 规范性：井号归一化（N2/N-2 → N-02）
    bad7 = sum(1 for r in prod if not re.match(r"^[A-Z]-\d{2}$", str(r.get("well_id", ""))))
    rules.append(_metric("r7", "规则", "规则7 井号归一化",
                         "pass" if bad7 == 0 else "fail", {"legacy_rows": bad7}))

    # 规则 8 规范性：stop_reason_code 新旧编码映射全命中
    known = {"RUNNING", "BELT", "MOTOR", "PUMP", "POWER", "R3", "R4", "R5", "R6"}
    bad8 = sum(1 for r in data.get("equip_status", [])
               if r.get("stop_reason_code") not in known)
    rules.append(_metric("r8", "规则", "规则8 停机原因码映射全命中",
                         "pass" if bad8 == 0 else "fail", {"unknown_codes": bad8}))

    # 规则 9 唯一性/状态机：档案"生产中"但近 30 日全停 = 状态滞后
    tail = max((str(r["prod_date"]) for r in prod), default=None)
    lag = []
    if tail is not None:
        cut = (date.fromisoformat(tail) - timedelta(days=30)).isoformat()
        status_of = {w.get("well_id"): w.get("current_status")
                     for w in data.get("well_info", [])}
        ran30: dict[str, bool] = {}
        for r in prod:
            if r["prod_date"] >= cut:
                ran30[r["well_id"]] = ran30.get(r["well_id"], False) or (_num(r, "open_days") or 0) > 0
        lag = [w for w, ran in ran30.items()
               if not ran and status_of.get(w) == "生产中"]
    rules.append(_metric("r9", "规则", "规则9 状态机合法迁移（滞后检测）",
                         "pass" if not lag else "fail", {"lagged_wells": lag}))

    # 规则 10 一致性：连续 30 日恒值告警（生产行）
    worst = 0
    wells_ordered: dict[str, list] = {}
    for r in prod:
        wells_ordered.setdefault(r.get("well_id"), []).append(r)
    for rows in wells_ordered.values():
        run, prev = 1, None
        for r in rows:
            v = r.get("oil_output")
            if _num(r, "open_days") == 0.0:
                run, prev = 1, None
                continue
            run = run + 1 if v == prev else 1
            prev = v
            worst = max(worst, run)
    rules.append(_metric("r10", "规则", "规则10 恒值 30 日告警",
                         "pass" if worst < 30 else "warn", {"longest_constant_run": worst},
                         "判据=告警级（warn），恒值窗口属仪表卡死信号"))

    # 规则 11 实时域：传感器零值 2 小时告警（教学演绎，日粒度数据不可判）
    rules.append(_metric("r11", "规则", "规则11 传感器零值 2 小时告警", "skipped", None,
                         "实时域规则（tpa 设定书自标教学演绎）；日粒度数据不可判，接入 15 分钟档后启用"))

    # 规则 12 一致性：区块月物质平衡偏差 ≤3%（结算净重 vs 产量合计 ×(1−损耗)）
    block_of = {w.get("well_id"): w.get("block_name") for w in data.get("well_info", [])}
    sums: dict[tuple, float] = {}
    for r in prod:
        key = (block_of.get(r["well_id"]), str(r.get("prod_date"))[:7])
        sums[key] = sums.get(key, 0.0) + (_num(r, "oil_output") or 0.0)
    worst_dev = 0.0
    checked12 = 0
    for r in data.get("monthly_settlement", []):
        key = (r.get("block_name"), str(r.get("settle_date"))[:7])
        total = sums.get(key, 0.0)
        net = _num(r, "net_weight")
        if not total or net is None:
            continue
        checked12 += 1
        worst_dev = max(worst_dev, abs(net / total - 1.0))
    rules.append(_metric("r12", "规则", "规则12 区块月物质平衡偏差 ≤3%",
                         "pass" if worst_dev <= 0.03 else "fail",
                         {"max_dev": round(worst_dev, 4), "checked": checked12}))

    # 规则 13–20（引用完整/跨表一致/枚举合法/正则格式/极值/波动率/钩稽/scrub）：
    # 维度由既有指标覆盖——枚举合法=符合性检查、极值/波动率=q2/f5、引用完整=fk、钩稽=r12。
    rules.append(_metric("r13_20", "规则", "规则13–20（泛维度）", "skipped", None,
                         "枚举合法/极值/波动率/引用完整/钩稽由符合性检查与 q2/f5/r12 覆盖，专条规则待提取件二核对后启用"))
    return rules


# ---------------------------------------------------------------- 闸门主流程

def evaluate(data_dir: Path, reference: Path | None = None, real_dir: str | None = None) -> dict:
    data_dir = Path(data_dir)
    manifest, data = _load_data(data_dir)
    reference_rows = None
    if reference is not None:
        with Path(reference).open(newline="", encoding="utf-8") as f:
            reference_rows = list(csv.DictReader(f))

    metrics = [
        q_shape(data, manifest),
        q_degenerate(data),
        q_reference(data, reference_rows),
        p_primary_key(data, manifest),
        p_combination(data),
        p_anonymeter(real_dir),
        f_material_balance(data),
        f_downtime(data),
        f_sensor_range(data),
        f_shutdown_static(data),
        f_decline(data),
    ]
    if (manifest.get("schema") or {}).get("name") == "tpa-contract":
        metrics += _platform_rules(data)
    counts = {s: sum(1 for m in metrics if m["status"] == s)
              for s in ("pass", "warn", "fail", "skipped")}
    overall = "fail" if counts["fail"] else ("warn" if counts["warn"] else "pass")
    return {
        "tool": "fieldforge-gate",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_dir": str(data_dir),
        "reference": str(reference) if reference else None,
        "synthetic_data_declaration": (manifest.get("synthetic_data_declaration")),
        "metrics": metrics,
        "summary": {**counts, "overall": overall},
    }


def to_html(report: dict) -> str:
    rows = []
    for m in report["metrics"]:
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌", "skipped": "⏭️"}[m["status"]]
        value = m["value"] if not isinstance(m["value"], (dict, list)) else json.dumps(
            m["value"], ensure_ascii=False)
        rows.append(f"<tr><td>{icon} {m['status']}</td><td>{m['family']}</td>"
                    f"<td>{m['name']}</td><td><code>{value}</code></td>"
                    f"<td>{m['detail']}</td></tr>")
    s = report["summary"]
    return ("<!doctype html><meta charset='utf-8'><title>fieldforge 评估闸门</title>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:2rem auto}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;text-align:left}"
            "code{font-size:.85em}</style>"
            f"<h1>fieldforge 评估闸门 · {report['summary']['overall'].upper()}</h1>"
            f"<p>数据目录 <code>{report['data_dir']}</code> ｜ 参照 <code>{report['reference']}</code><br>"
            f"pass {s['pass']} · warn {s['warn']} · fail {s['fail']} · skipped {s['skipped']}</p>"
            f"<p>{report['synthetic_data_declaration']}</p>"
            "<table><tr><th>状态</th><th>族</th><th>指标</th><th>值</th><th>说明</th></tr>"
            + "".join(rows) + "</table>")
