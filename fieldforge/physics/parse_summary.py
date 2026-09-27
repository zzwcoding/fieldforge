"""flow 汇总文件解析（宿主侧，依赖可选包 resdata）。

flow 在容器内产出 ECLIPSE 二进制汇总（SMSPEC/UNSMRY）；本模块用 resdata 读取并
按扫参配方声明的单位换算（FIELD: stb/d、Mscf/d、psia）归一为 production_daily
同构骨架行。resdata 缺失时报明确安装提示。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

_COLUMN_BY_KEYWORD = {
    "WOPR": ("oil_rate", "oil"),
    "WWPR": ("water_rate", "water"),
    "WGPR": ("gas_rate", "gas"),
    "WBHP": ("bhp_mpa", "pressure"),
}
_CORE_KEYWORDS = ("WOPR", "WWPR", "WGPR")


def _load_summary(case_dir: Path, deck_base: str):
    try:
        from resdata.summary import Summary
    except ImportError as e:
        raise RuntimeError(
            "宿主缺少 resdata：pip install 'resdata>=6.3'（fieldforge[physics] 可选依赖）"
        ) from e
    return Summary(str(case_dir / deck_base))


def parse_case(
    case_dir: Path,
    deck_well: str,
    well_id: str,
    keywords: tuple[str, ...],
    units: dict,
) -> list[dict]:
    """读取一个方案的汇总，返回 production_daily 同构行（附 bhp_mpa 信息列）。"""
    case_dir = Path(case_dir)
    deck_base = next((p.stem for p in case_dir.glob("*.DATA")), None)
    if deck_base is None:
        raise RuntimeError(f"{case_dir}: 找不到 deck 文件")
    summ = _load_summary(case_dir, deck_base)
    dates = [d if isinstance(d, datetime) else datetime(*d[:3]) for d in summ.dates]

    factors = {}
    for kw in keywords:
        col, unit_key = _COLUMN_BY_KEYWORD.get(kw, (None, None))
        if col is None:
            continue
        u = units.get(unit_key) or {}
        factor = float(u.get("factor", 1.0))
        try:
            factors[kw] = (col, summ.numpy_vector(f"{kw}:{deck_well}"), factor)
        except KeyError:
            if kw in _CORE_KEYWORDS:
                raise RuntimeError(f"汇总缺少核心关键字 {kw}:{deck_well}（deck SUMMARY 段未声明？）")
            factors[kw] = (col, None, factor)

    rows = []
    for i, d in enumerate(dates):
        row = {"well_id": well_id, "prod_date": d.date().isoformat(), "producing_hours": 24.0}
        for kw, (col, vec, factor) in factors.items():
            if vec is None:
                continue
            v = float(vec[i]) * factor
            if col in ("oil_rate", "water_rate", "gas_rate"):
                v = max(0.0, v)  # 数值噪声可能出现 -ε，速率物理非负
            row[col] = round(v, 4)
        rows.append(row)
    return rows
