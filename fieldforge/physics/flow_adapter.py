"""M2-T1 FlowAdapter：OPM Flow 独立进程（容器）扫参适配器。

- GPL-3.0 红线（charter §5）：flow 只在独立容器内运行，宿主仅经命令行与文件交换，
  不链接其源码、不二次分发其代码。
- deck 模板参数化 = 声明式正则替换（v1；deck 结构化解析器属后续增强，须显式声明）。
- 汇总解析在宿主侧（parse_summary.py，依赖可选包 resdata）；容器只负责跑 flow。
- 产出为 production_daily 同构骨架表（行粒度 = deck DATES 步长，日度细化属后续票）。
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from .parse_summary import parse_case


class SweepError(ValueError):
    pass


@dataclass(frozen=True)
class Param:
    name: str
    regex: str
    values: tuple


@dataclass(frozen=True)
class SweepSpec:
    name: str
    template: Path
    deck_name: str
    params: tuple[Param, ...]
    well_id: str
    deck_well: str
    keywords: tuple[str, ...]
    units: dict
    image: str
    timeout_s: int


def load_sweep(path: str | Path) -> SweepSpec:
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SweepError(f"{path}: YAML 解析失败：{e}") from e
    if not isinstance(raw, dict) or not raw.get("sweep"):
        raise SweepError(f"{path}: 缺少顶层键 sweep")

    template = Path(raw.get("template") or "")
    if not template.is_file():
        # 相对配方目录与 CWD 依次解析
        for base in (path.parent, path.parent.parent, Path.cwd()):
            cand = base / template
            if cand.is_file():
                template = cand
                break
        else:
            raise SweepError(f"{path}: 模板不存在 {template}")

    params = []
    for p in raw.get("params") or []:
        try:
            re.compile(p["regex"])
        except (KeyError, re.error) as e:
            raise SweepError(f"{path}: 参数 {p.get('name')} 正则非法：{e}") from e
        if not p.get("values"):
            raise SweepError(f"{path}: 参数 {p.get('name')} 缺 values")
        params.append(Param(p["name"], p["regex"], tuple(p["values"])))
    if not params:
        raise SweepError(f"{path}: 至少声明一个扫参参数")

    container = raw.get("container") or {}
    return SweepSpec(
        name=str(raw["sweep"]),
        template=template,
        deck_name=template.name,
        params=tuple(params),
        well_id=raw.get("well_id", "SYN-PROD"),
        deck_well=raw.get("deck_well", "PROD"),
        keywords=tuple(raw.get("summary_keywords") or ["WOPR", "WWPR", "WGPR", "WBHP"]),
        units=raw.get("units") or {},
        image=container.get("image", "fieldforge/flow:2026.04"),
        timeout_s=int(container.get("timeout_s", 600)),
    )


def render_deck(spec: SweepSpec, combo: dict) -> str:
    """按参数组合对模板做正则替换；每个参数必须恰好命中一次。"""
    text = spec.template.read_text(encoding="utf-8")
    for p in spec.params:
        v = combo[p.name]
        text, n = re.subn(p.regex, lambda m: m.group(1) + str(v), text)
        if n != 1:
            raise SweepError(f"参数 {p.name} 在模板中命中 {n} 次（应为 1）：{p.regex}")
    return text


def _sh(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def run_sweep(spec: SweepSpec, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template_sha = hashlib.sha256(spec.template.read_bytes()).hexdigest()

    combos = [dict(zip([p.name for p in spec.params], values))
              for values in itertools.product(*[p.values for p in spec.params])]

    manifest = {
        "tool": "fieldforge-sweep",
        "sweep": spec.name,
        "template": {"file": str(spec.template), "sha256": template_sha},
        "image": spec.image,
        "deck_well": spec.deck_well,
        "well_id": spec.well_id,
        "units": spec.units,
        "note": "骨架行粒度 = deck DATES 步长；producing_hours 恒 24（停机扰动由注入器 T2 负责）",
        "solutions": [],
    }

    flow_version = None
    for i, combo in enumerate(combos):
        sol = f"sol_{i:03d}"
        sol_dir = out_dir / sol
        sol_dir.mkdir(exist_ok=True)
        (sol_dir / spec.deck_name).write_text(render_deck(spec, combo), encoding="utf-8")

        cname = f"ff-{spec.name}-{i:03d}"
        _sh("docker", "rm", "-f", cname)
        cmd = ["docker", "run", "--rm", "--name", cname,
               "-v", f"{sol_dir.resolve()}:/runs", "-w", "/runs",
               spec.image, "bash", "-c",
               f"flow --version | head -1; flow {spec.deck_name} > flow.log 2>&1; echo RC=$?"]
        t0 = time.monotonic()
        try:
            proc = _sh(*cmd, timeout=spec.timeout_s)
            rc_match = re.search(r"RC=(\d+)", proc.stdout)
            rc = int(rc_match.group(1)) if rc_match else -1
            flow_version = flow_version or next(
                (ln for ln in proc.stdout.splitlines() if ln.startswith("flow ")), None)
            error = proc.stderr.strip()[-300:] if rc != 0 else None
        except subprocess.TimeoutExpired:
            _sh("docker", "rm", "-f", cname)
            rc, error = -2, f"timeout {spec.timeout_s}s"
        wall = round(time.monotonic() - t0, 2)

        entry = {"solution": sol, "params": combo, "rc": rc, "wall_s": wall}
        if error:
            entry["error"] = error
        if rc == 0:
            try:
                rows = parse_case(sol_dir, spec.deck_well, spec.well_id, spec.keywords, spec.units)
                _write_csv(sol_dir / "production_daily_skeleton.csv", rows)
                entry["rows"] = len(rows)
            except Exception as e:  # 解析失败不吞：记入 manifest 并标失败
                entry["rc"], entry["error"] = -3, f"summary 解析失败：{e}"
        manifest["solutions"].append(entry)

    _write_csv(out_dir / "sweep_results.csv", _combine(out_dir, manifest))
    manifest["flow_version"] = flow_version
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _combine(out_dir: Path, manifest: dict) -> list[dict]:
    rows = []
    for entry in manifest["solutions"]:
        if entry.get("rc") != 0:
            continue
        f = out_dir / entry["solution"] / "production_daily_skeleton.csv"
        for line in f.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split(",")
            rows.append({"solution_id": entry["solution"], **dict(
                zip(["well_id", "prod_date", "producing_hours", "oil_rate", "water_rate", "gas_rate", "bhp_mpa"], parts))})
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
