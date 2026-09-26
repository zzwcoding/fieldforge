"""输出层：CSV / Parquet（可插拔后端）+ manifest（含单位表与合成数据声明）。"""
from __future__ import annotations

import csv
import json
import platform
from datetime import date, datetime, timezone
from pathlib import Path

from . import __version__

SYNTHETIC_DECLARATION = (
    "本数据集由 fieldforge 生成的合成数据：仅可用于算法研发、测试、演示与教学；"
    "禁止用于储量申报、生产决策等任何真实业务场景。"
)


def _cell(v):
    if isinstance(v, date):
        return v.isoformat()
    return v


def write_table(path: Path, rows: list[dict], fields: list[str], fmt: str) -> None:
    if fmt == "csv":
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for row in rows:
                w.writerow({k: _cell(row.get(k)) for k in fields})
        return
    if fmt == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:
            raise SystemExit(
                "Parquet 后端需要 pyarrow（M1 未内置依赖）：pip install pyarrow 后重试 --format parquet"
            ) from e
        cols = {f: [_cell(r.get(f)) for r in rows] for f in fields}
        pq.write_table(pa.Table.from_pydict(cols), path)
        return
    raise ValueError(f"未知输出格式 {fmt!r}")


def write_manifest(
    path: Path,
    *,
    schema,
    recipe,
    seed: int,
    fmt: str,
    tables: dict[str, list[dict]],
    conformance_cells: int,
) -> dict:
    manifest = {
        "tool": "fieldforge",
        "version": __version__,
        "python": platform.python_version(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schema": {"name": schema.name, "version": schema.version, "file": schema.path},
        "recipe": {
            "name": recipe.name,
            "file": recipe.path,
            "seed": seed,
            "period": {"start": recipe.start.isoformat(), "days": recipe.days},
            "counts": recipe.counts,
        },
        "seed": seed,
        "output_format": fmt,
        "synthetic_data_declaration": SYNTHETIC_DECLARATION,
        "entities": [
            {"entity": name, "file": f"{name}.{fmt}", "rows": len(tables[name])}
            for name in schema.entities
        ],
        "units": {
            name: {fs.name: fs.unit for fs in ent.fields.values() if fs.unit}
            for name, ent in schema.entities.items()
        },
        "conformance": {"status": "pass", "checked_cells": conformance_cells},
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
