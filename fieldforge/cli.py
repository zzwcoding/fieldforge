"""fieldforge CLI（M1 仅 generate 子命令）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import check, emit, engine, inject
from .schema import SchemaError, load_recipe, load_schema


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="fieldforge", description="油气领域专用合成数据生成工作台")
    sub = parser.add_subparsers(dest="command", required=True)
    g = sub.add_parser("generate", help="按配方生成合成数据")
    g.add_argument("--recipe", required=True, help="配方 YAML 路径")
    g.add_argument("--seed", type=int, default=None, help="随机种子（覆盖配方内 seed）")
    g.add_argument("--out", default="out", help="输出目录（默认 ./out）")
    g.add_argument("--format", choices=["csv", "parquet"], default=None, help="输出格式（默认取配方声明）")
    s = sub.add_parser("sweep", help="物理扫参（OPM Flow 容器，GPL 组件独立进程）")
    s.add_argument("--sweep", required=True, help="扫参配方 YAML 路径")
    s.add_argument("--out", default=None, help="输出目录（默认 out/sweep-<name>）")
    args = parser.parse_args(argv)
    if args.command == "sweep":
        return _cmd_sweep(args)
    return _cmd_generate(args)


def _cmd_generate(args) -> int:

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
    injection_info = None
    if recipe.injection:
        tables, injection_info = inject.apply_injections(schema, tables, recipe.injection, seed)
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
        injection_info=injection_info,
    )
    print(f"已生成 {len(schema.entities)} 张表 → {out_dir}/（seed={seed}，格式 {fmt}）")
    for item in manifest["entities"]:
        print(f"  {item['file']:<26}{item['rows']:>6} 行")
    print(f"  {'manifest.json':<26}含合成数据声明 / 单位表 / 符合性结论")
    return 0


def _cmd_sweep(args) -> int:
    from .physics.flow_adapter import SweepError, load_sweep, run_sweep

    try:
        spec = load_sweep(args.sweep)
    except SweepError as e:
        print(f"配置错误：{e}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else Path("out") / f"sweep-{spec.name}"
    manifest = run_sweep(spec, out)
    ok = sum(1 for s in manifest["solutions"] if s["rc"] == 0)
    total = len(manifest["solutions"])
    print(f"扫参 {spec.name}：{ok}/{total} 方案成功 → {out}/")
    for s in manifest["solutions"]:
        mark = "✓" if s["rc"] == 0 else "✗"
        print(f"  {mark} {s['solution']} {s['params']} rc={s['rc']} {s['wall_s']}s rows={s.get('rows', '-')}")
    return 0 if ok == total else 1
