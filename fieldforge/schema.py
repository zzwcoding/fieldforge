"""L0 schema 层：加载与结构校验（schema 与配方均为 YAML）。

本模块只做"形状"校验：必填键、字段类型白名单、enum/fk 声明完整性、
fk 目标实体必须先于引用者声明（保证引擎可按声明顺序生成）。
数据级校验（枚举实存、量程、外键实存）在 check.py 于发射前执行。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

FIELD_TYPES = {"string", "enum", "date", "float", "integer", "fk"}


class SchemaError(ValueError):
    """schema/配方结构不合法。"""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    unit: str | None
    description: str
    raw: dict


@dataclass(frozen=True)
class EntitySpec:
    name: str
    description: str
    primary_key: tuple[str, ...]
    fields: dict[str, FieldSpec]
    model: str | None
    model_params: dict


@dataclass(frozen=True)
class Schema:
    name: str
    version: str
    description: str
    entities: dict[str, EntitySpec]  # 保持声明顺序 = 生成依赖顺序
    path: str


@dataclass(frozen=True)
class Recipe:
    name: str
    description: str
    schema_path: Path
    seed: int | None
    start: date
    days: int
    counts: dict
    injection: dict
    freshness: dict
    fmt: str
    path: str


def load_schema(path: str | Path) -> Schema:
    path = Path(path)
    raw = _read_yaml(path, "schema")
    if not raw.get("schema"):
        raise SchemaError(f"{path}: 缺少顶层键 schema")
    if not raw.get("version"):
        raise SchemaError(f"{path}: 缺少顶层键 version")
    entities_raw = raw.get("entities") or {}
    if not entities_raw:
        raise SchemaError(f"{path}: 缺少 entities 声明")

    entities: dict[str, EntitySpec] = {}
    for ent_name, eraw in entities_raw.items():
        fields_raw = eraw.get("fields") or {}
        if not fields_raw:
            raise SchemaError(f"{path}: 实体 {ent_name} 无字段声明")
        fields: dict[str, FieldSpec] = {}
        for fname, fraw in fields_raw.items():
            ftype = fraw.get("type")
            if ftype not in FIELD_TYPES:
                raise SchemaError(f"{path}: {ent_name}.{fname} 非法类型 {ftype!r}（白名单 {sorted(FIELD_TYPES)}）")
            if ftype == "enum":
                values = fraw.get("values")
                if not values:
                    raise SchemaError(f"{path}: {ent_name}.{fname} 为 enum 但缺 values")
                weights = fraw.get("weights")
                if weights and len(weights) != len(values):
                    raise SchemaError(f"{path}: {ent_name}.{fname} weights 与 values 长度不一致")
            if ftype == "fk":
                fk = fraw.get("fk") or {}
                if "entity" not in fk or "field" not in fk:
                    raise SchemaError(f"{path}: {ent_name}.{fname} fk 声明需含 entity 与 field")
                if fk["entity"] not in entities:
                    raise SchemaError(f"{path}: {ent_name}.{fname} 的 fk 目标实体 {fk['entity']} 必须先于 {ent_name} 声明")
            fields[fname] = FieldSpec(fname, ftype, fraw.get("unit"), fraw.get("description", ""), fraw)

        pk = eraw.get("primary_key")
        pk = (pk,) if isinstance(pk, str) else tuple(pk or [])
        entities[ent_name] = EntitySpec(
            ent_name,
            eraw.get("description", ""),
            pk,
            fields,
            eraw.get("model"),
            eraw.get("model_params") or {},
        )

    return Schema(str(raw["schema"]), str(raw["version"]), raw.get("description", ""), entities, str(path))


def load_recipe(path: str | Path) -> Recipe:
    path = Path(path)
    raw = _read_yaml(path, "配方")
    if not raw.get("recipe"):
        raise SchemaError(f"{path}: 缺少顶层键 recipe")
    schema_ref = raw.get("schema")
    if not schema_ref:
        raise SchemaError(f"{path}: 配方缺少 schema 指向")

    period = raw.get("period") or {}
    start = period.get("start")
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if not isinstance(start, date):
        raise SchemaError(f"{path}: period.start 缺失或不是日期")
    days = int(period.get("days") or 0)
    if days <= 0:
        raise SchemaError(f"{path}: period.days 必须为正整数")

    fmt = (raw.get("outputs") or {}).get("format", "csv")
    if fmt not in {"csv", "parquet"}:
        raise SchemaError(f"{path}: outputs.format 只支持 csv/parquet，得到 {fmt!r}")

    seed = raw.get("seed")
    seed = int(seed) if seed is not None else None

    return Recipe(
        str(raw["recipe"]),
        raw.get("description", ""),
        _resolve_schema_path(schema_ref, path),
        seed,
        start,
        days,
        raw.get("counts") or {},
        raw.get("injection") or {},
        raw.get("freshness") or {},
        fmt,
        str(path),
    )


def _read_yaml(path: Path, what: str) -> dict:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SchemaError(f"{path}: {what} YAML 解析失败：{e}") from e
    if not isinstance(raw, dict):
        raise SchemaError(f"{path}: {what} 内容为空或不是映射")
    return raw


def _resolve_schema_path(ref: str, recipe_path: Path) -> Path:
    p = Path(ref)
    if p.is_absolute():
        if p.exists():
            return p
        raise SchemaError(f"schema 文件不存在：{ref}")
    for base in (Path.cwd(), recipe_path.parent, recipe_path.parent.parent):
        cand = base / p
        if cand.exists():
            return cand
    raise SchemaError(f"找不到 schema 文件 {ref}（相对 CWD / 配方目录 / 配方上级目录均未命中）")
