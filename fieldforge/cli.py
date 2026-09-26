"""fieldforge CLI（M1 仅 generate 子命令）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import check, emit, engine
from .schema import SchemaError, load_recipe, load_schema


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fieldforge", description="油气领域专用合成数据生成工作台")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="按配方生成合成数据")
    g.add_argument("--recipe", required=True, help="配方 YAML 路径")
    g.add_argument("--seed", type=int, default=None, help="随机种子（覆盖配方内 seed）")
    g.add_argument("--out", default="out", help="输出目录（默认 ./out）")
    g.add_argument("--format", choices=["csv", "parquet"], default=None, help="输出格式（默认取配方声明）")
    args = parser.parse_args(argv)

    try:
        recipe = load_recipe(args.recipe)
        schema = load_schema(recipe.schema_path)
    except SchemaError as e:
        print(f"配置错误：{e}", file=sys.stderr)
        return 2

    seed = args.seed if args.seed is not None else recipe.seed
    if seed is None:
        print("未指定种子：--seed 或配方内 seed 至少给一个", file=sys.stderr)
        return 2
    fmt = args.format or recipe.fmt

    tables = engine.Engine(schema, recipe, seed).generate()
    violations = check.check_conformance(schema, tables)
    if violations:
        print(f"符合性检查未通过（{len(violations)} 条），未写出任何文件：", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cells = 0
    for name, ent in schema.entities.items():
        emit.write_table(out_dir / f"{name}.{fmt}", tables[name], list(ent.fields), fmt)
        cells += len(ent.fields) * len(tables[name])
    manifest = emit.write_manifest(
        out_dir / "manifest.json",
        schema=schema,
        recipe=recipe,
        seed=seed,
        fmt=fmt,
        tables=tables,
        conformance_cells=cells,
    )
    print(f"已生成 {len(schema.entities)} 张表 → {out_dir}/（seed={seed}，格式 {fmt}）")
    for item in manifest["entities"]:
        print(f"  {item['file']:<26}{item['rows']:>6} 行")
    print(f"  {'manifest.json':<26}含合成数据声明 / 单位表 / 符合性结论")
    return 0
