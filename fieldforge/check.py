"""发射前 schema 符合性检查——F7 评估闸门的 M1 内嵌最小版。

只查"数据是否忠于 schema 声明"：枚举实存、量程、日期可解析、外键实存、
字段齐全。分布与物理一致性指标（物质平衡、递减率等）按 charter 属于 M3。
"""
from __future__ import annotations

from datetime import date

_MAX_REPORT = 50


def check_conformance(schema, tables: dict[str, list[dict]], dirty_ok: bool = False) -> list[str]:
    """返回违例清单；空清单 = 通过。

    dirty_ok=True（配方声明了平台脏特征注入）时跳过 fk/enum 检查——
    旧井号写法、旧编码等脏特征按设计违反形状约束，属交付物而非缺陷；
    日期/量程/缺失检查保留（nullable 字段允许空值）。
    """
    violations: list[str] = []

    def add(msg: str) -> bool:  # True = 达到报告上限
        violations.append(msg)
        return len(violations) >= _MAX_REPORT

    fk_targets: dict[tuple[str, str], set] = {}
    if not dirty_ok:
        for ent in schema.entities.values():
            for fs in ent.fields.values():
                if fs.type == "fk":
                    key = (fs.raw["fk"]["entity"], fs.raw["fk"]["field"])
                    fk_targets[key] = {r.get(key[1]) for r in tables.get(key[0], [])}

    for ent_name, ent in schema.entities.items():
        rows = tables.get(ent_name)
        if rows is None:
            if add(f"实体 {ent_name} 缺失"):
                return _truncated(violations)
            continue
        for i, row in enumerate(rows):
            for fname, fs in ent.fields.items():
                if fname not in row:
                    bad = f"{ent_name}[{i}].{fname} 缺字段"
                else:
                    bad = _check_value(ent_name, i, fname, fs, row[fname], fk_targets, dirty_ok)
                if bad and add(bad):
                    return _truncated(violations)
    return violations


def _check_value(ent_name: str, i: int, fname: str, fs, val, fk_targets, dirty_ok: bool = False) -> str | None:
    if val in ("", None) and fs.raw.get("nullable"):
        return None  # 缺失即脏特征（如措施缺效期 30%），完整性由规则族统计
    t = fs.type
    if t == "enum":
        if dirty_ok:
            return None  # 新旧编码并存等脏值由平台规则族（规则 8）判定
        if val not in fs.raw["values"]:
            return f"{ent_name}[{i}].{fname}={val!r} 不在枚举 {fs.raw['values']}"
        return None
    if t == "date":
        try:
            date.fromisoformat(str(val))
        except ValueError:
            return f"{ent_name}[{i}].{fname}={val!r} 不是 ISO 日期"
        return None
    if t == "float":
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"{ent_name}[{i}].{fname}={val!r} 非数值"
        return _range_bad(ent_name, i, fname, val, fs)
    if t == "integer":
        if isinstance(val, bool) or not isinstance(val, int):
            return f"{ent_name}[{i}].{fname}={val!r} 非整数"
        return _range_bad(ent_name, i, fname, val, fs)
    if t == "fk":
        if dirty_ok:
            return None  # 旧井号写法（N2/N-2）按设计存在，归一化由规则 7 判定
        key = (fs.raw["fk"]["entity"], fs.raw["fk"]["field"])
        if val not in fk_targets.get(key, set()):
            return f"{ent_name}[{i}].{fname}={val!r} 在 {key[0]}.{key[1]} 中无对应值"
    return None


def _range_bad(ent_name: str, i: int, fname: str, val, fs) -> str | None:
    rng_decl = fs.raw.get("range")
    if rng_decl and not (rng_decl[0] <= val <= rng_decl[1]):
        return f"{ent_name}[{i}].{fname}={val!r} 超出量程 {rng_decl}"
    return None


def _truncated(violations: list[str]) -> list[str]:
    violations.append(f"（已达 {_MAX_REPORT} 条报告上限，截断）")
    return violations
