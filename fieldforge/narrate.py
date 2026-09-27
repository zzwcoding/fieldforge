"""M4 文档层 v1 —— 班报模板叙述化（结构化事实 → 文本语料）+ 数值一致性机判回流。

- v1 为模板叙述化：从 oil_production_daily 单行事实生成班报文本，确定性、可复现；
  LLM 叙述化（多样化措辞/摘要素材）待模型选型（charter Q7），接口（per-row 事实 dict → 文本）不变。
- 校验回流（F6 验收：文中数值与结构化源一致，抽查可机判）：逐字段正则提取比对，
  任何一处对不上即 violations 非空——不合格语料不得入 RAG/评测集。
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _f(row: dict, col: str) -> float:
    return float(row.get(col) or 0.0)


def daily_report(row: dict, well: dict) -> str:
    """一行生产事实 → 一篇班报（tpa-contract 列名）。"""
    oil, plan = _f(row, "oil_output"), _f(row, "plan_output")
    wc, hours = _f(row, "water_cut"), _f(row, "open_days")
    liquid, press = _f(row, "liquid_output"), _f(row, "oil_pressure")
    rate = oil / plan * 100 if plan else 0.0
    if hours == 0.0:
        return (f"{well['well_name']}井（{well['field_name']}，{well['platform']} 平台）"
                f"{row['prod_date']} 生产班报：本日全井停产检修，开井 0 小时，"
                f"日产油 0.00 吨，日产液 0.00 方，含水率 0.0%，油压 0.00 MPa；"
                f"配产 {plan:.2f} 吨，完成率 0.0%。当日报表班次 {row['report_shift']} 班。")
    return (f"{well['well_name']}井（{well['field_name']}，{well['platform']} 平台）"
            f"{row['prod_date']} 生产班报：本日开井 {hours:.1f} 小时，日产油 {oil:.2f} 吨，"
            f"日产液 {liquid:.2f} 方，含水率 {wc:.1f}%，油压 {press:.2f} MPa；"
            f"配产 {plan:.2f} 吨，完成率 {rate:.1f}%。当日报表班次 {row['report_shift']} 班。")


_FIELDS = [  # (标签正则, 源列, 容差=文本舍入位的一半) —— 顺序即班报语序
    (r"开井 ([\d.]+) 小时", "open_days", 0.05),
    (r"日产油 ([\d.]+) 吨", "oil_output", 0.005),
    (r"日产液 ([\d.]+) 方", "liquid_output", 0.005),
    (r"含水率 ([\d.]+)%", "water_cut", 0.05),
    (r"油压 ([\d.]+) MPa", "oil_pressure", 0.005),
    (r"配产 ([\d.]+) 吨", "plan_output", 0.005),
]


def validate(text: str, row: dict) -> list[str]:
    """数值一致性机判：班报文本中的标注数值必须与结构化源一致（按文本舍入位给容差）。"""
    bad = []
    for pattern, col, tol in _FIELDS:
        m = re.search(pattern, text)
        if m is None:
            bad.append(f"缺少字段句：{col}（{pattern}）")
            continue
        if abs(float(m.group(1)) - _f(row, col)) > tol:
            bad.append(f"{col} 文中 {m.group(1)} ≠ 源 {row.get(col)}")
    return bad


def build_corpus(tables: dict[str, list[dict]], well_id: str, max_days: int | None = None):
    """某井全期班报语料：[(prod_date, text, violations)]，日期升序。"""
    wells = {w["well_id"]: w for w in tables.get("well_info", [])}
    if well_id not in wells:
        raise KeyError(f"查无此井：{well_id}（合法数据态，但语料生成需真实井号）")
    well = wells[well_id]
    rows = sorted((r for r in tables.get("oil_production_daily", [])
                   if r["well_id"] == well_id), key=lambda r: r["prod_date"])
    if max_days:
        rows = rows[:max_days]
    return [(r["prod_date"], daily_report(r, well), validate(daily_report(r, well), r))
            for r in rows]


def write_corpus(out_dir: Path, corpus: list) -> dict:
    """落盘语料（每日一篇 .txt）+ 叙述化 manifest（含逐篇校验结论）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for d, text, bad in corpus:
        f = out_dir / f"{d}.txt"
        f.write_text(text + "\n", encoding="utf-8")
        entries.append({"prod_date": d, "file": f.name,
                        "validation": "pass" if not bad else bad})
    manifest = {"tool": "fieldforge-narrate", "version": "0.1.0",
                "mode": "template（LLM 叙述化待选型，charter Q7）",
                "reports": len(entries),
                "validation_failures": sum(1 for e in entries if e["validation"] != "pass"),
                "synthetic_data_declaration": (
                    "本语料由 fieldforge 依合成数据模板叙述化生成：仅用于算法研发、测试、演示与教学；"
                    "禁止用于储量申报、生产决策等任何真实业务场景。")}
    (out_dir / "narration_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
