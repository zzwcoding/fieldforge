"""fieldforge-api：FastAPI 薄壳——把 generate / evaluate / narrate 包成 HTTP。

设计纪律：
- 只做"CLI 的 HTTP 化"，不复制业务逻辑；
- 生成任务互斥限流（同一时刻一个，2C4G 小机防内存峰值，其余请求 429）；
- 每个响应带 X-Synthetic-Data 头——合成数据红线跟到 HTTP 层；
- 产物落 /data/runs/<run_id>/，下载走白名单文件名（防路径穿越）。
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from fieldforge import evaluate as gate
from fieldforge import narrate

REPO = Path(os.environ.get("FF_REPO", "/app"))
DATA = Path(os.environ.get("FF_DATA", "/data"))
RUNS = DATA / "runs"

_LOCK = threading.Lock()
app = FastAPI(title="fieldforge-api", version="0.1.0",
              description="油气领域专用合成数据生成服务。所有产出均为合成数据，禁止用于储量申报、生产决策等真实业务。")


@app.middleware("http")
async def _synthetic_header(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Synthetic-Data"] = ("all outputs are synthetic; "
                                        "not for reserve filing or real business decisions")
    return resp


def _run_dir(run_id: str) -> Path:
    if not re_fullmatch(run_id):
        raise HTTPException(400, "非法 run_id")
    d = RUNS / run_id
    if not (d / "manifest.json").is_file():
        raise HTTPException(404, f"run 不存在：{run_id}")
    return d


def re_fullmatch(s: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9._-]{1,80}", s))


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "fieldforge-api"}


@app.get("/api/recipes")
def list_recipes():
    out = []
    for p in sorted((REPO / "recipes").glob("*.yaml")):
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        out.append({"name": raw.get("recipe", p.stem), "file": p.name,
                    "description": raw.get("description", ""),
                    "schema": raw.get("schema")})
    return {"recipes": out}


@app.post("/api/generate")
def generate(body: dict):
    recipe = body.get("recipe")
    if not recipe or not re_fullmatch(recipe):
        raise HTTPException(400, "body 需要 {recipe: <配置名（不含 .yaml）>}")
    recipe_path = REPO / "recipes" / f"{recipe}.yaml"
    if not recipe_path.is_file():
        raise HTTPException(404, f"配方不存在：{recipe}")
    if not _LOCK.acquire(blocking=False):
        raise HTTPException(429, "已有生成任务在跑（限流：同一时刻一个）")
    try:
        from fieldforge.cli import main as cli_main
        run_id = f"{recipe}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
        out = RUNS / run_id
        argv = ["generate", "--recipe", str(recipe_path), "--out", str(out)]
        if body.get("seed") is not None:
            argv += ["--seed", str(int(body["seed"]))]
        if body.get("format") in ("csv", "parquet"):
            argv += ["--format", body["format"]]
        rc = cli_main(argv)
        manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        if rc != 0:  # enforce 闸门拦截等
            return JSONResponse(status_code=409, content={
                "run_id": run_id, "rc": rc,
                "gate": manifest.get("gate"),
                "synthetic_data_declaration": manifest.get("synthetic_data_declaration")})
        return {"run_id": run_id, "manifest": manifest}
    finally:
        _LOCK.release()


@app.get("/api/runs")
def list_runs():
    runs = []
    for d in sorted(RUNS.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = json.loads(d.read_text(encoding="utf-8"))
        runs.append({"run_id": d.parent.name,
                     "recipe": m.get("recipe", {}).get("name"),
                     "schema": m.get("schema", {}).get("name"),
                     "seed": m.get("seed"),
                     "entities": {e["entity"]: e["rows"] for e in m.get("entities", [])},
                     "gate": (m.get("gate") or {}).get("overall", "not-run")})
    return {"runs": runs}


@app.get("/api/runs/{run_id}/manifest")
def run_manifest(run_id: str):
    return json.loads(_run_dir(run_id).joinpath("manifest.json").read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/download/{filename}")
def download(run_id: str, filename: str):
    d = _run_dir(run_id)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    allowed = {e["file"] for e in manifest.get("entities", [])} | {"manifest.json", "evaluation.json"}
    if filename not in allowed:
        raise HTTPException(403, f"文件不在白名单：{filename}（可下载：{sorted(allowed)}）")
    f = d / filename
    if not f.is_file():
        raise HTTPException(404, "文件未生成（Parquet 交付态请下载 .parquet）")
    return FileResponse(f, filename=filename,
                        headers={"X-Synthetic-Data": "synthetic data; not for real business decisions"})


@app.post("/api/evaluate/{run_id}")
def evaluate_run(run_id: str):
    d = _run_dir(run_id)
    report = gate.evaluate(d)
    (d / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


@app.post("/api/narrate/{run_id}")
def narrate_run(run_id: str, body: dict):
    d = _run_dir(run_id)
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema") or {}).get("name") != "tpa-contract":
        raise HTTPException(400, "班报叙述化仅支持 tpa-contract 数据（合同 8 表列名）")
    well = body.get("well")
    if not well:
        raise HTTPException(400, "body 需要 {well: 井号}")
    _, tables = gate._load_data(d)
    try:
        corpus = narrate.build_corpus(tables, well, body.get("days"))
    except KeyError as e:
        raise HTTPException(404, str(e).strip("'")) from e  # 查无此井=合法数据态
    return {"well": well, "reports": [{"prod_date": dt, "text": t,
                                       "validation": v} for dt, t, v in corpus]}
