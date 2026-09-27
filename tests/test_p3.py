"""P3 测试：亚日传感器（分层采样+规则 11 启用）、Parquet 交付态过闸、闸门 enforce 语义。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE_DEMO = ROOT / "recipes" / "tpa_s1_demo.yaml"
RECIPE_DIRTY = ROOT / "recipes" / "tpa_s1_dirty.yaml"


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class P3SubdailyAndGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="ff-p3-"))
        rc = main(["generate", "--recipe", str(RECIPE_DEMO), "--out", str(cls.out)])
        assert rc == 0, "含闸门的合同生成失败"

    def test_subdaily_shape_and_spacing(self):
        rows = _rows(self.out, "sensor_reading_subdaily.csv")
        self.assertEqual(len(rows), 2 * 3 * 96 * 365)              # 2 井 × 3 通道 × 96 × 365
        ts = sorted(r["ts"] for r in rows if r["well_id"] == "N-01"
                    and r["channel_id"].endswith("-WHP")
                    and r["ts"].startswith("2025-09-01"))
        self.assertEqual(len(ts), 96)                              # 单通道单日 96 读数
        gaps = {(datetime.fromisoformat(b) - datetime.fromisoformat(a)).seconds
                for a, b in zip(ts, ts[1:])}
        self.assertEqual(gaps, {900})                              # 15 分钟步长

    def test_subdaily_downtime_static(self):
        ledger = _rows(self.out, "oil_production_daily.csv")
        down = {r["prod_date"] for r in ledger
                if r["well_id"] == "N-01" and float(r["open_days"]) == 0.0}
        if not down:
            self.skipTest("该种子下 N-01 无停机日")
        readings = _rows(self.out, "sensor_reading_subdaily.csv")
        vals = {r["value"] for r in readings
                if r["well_id"] == "N-01" and r["channel_id"].endswith("-WHP")
                and r["ts"][:10] in down}
        self.assertEqual(len(vals), 1)                             # 停机时段整段静稳

    def test_gate_embedded_and_enforced(self):
        m = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["gate"]["overall"], "pass")             # 干净基线过闸
        self.assertTrue(m["gate"]["enforce"])
        self.assertTrue((self.out / "evaluation.json").is_file())
        rep = json.loads((self.out / "evaluation.json").read_text(encoding="utf-8"))
        r11 = next(x for x in rep["metrics"] if x["id"] == "r11")
        self.assertEqual(r11["status"], "pass")                    # 规则 11 在亚日数据上启用

    def test_enforce_fail_returns_one(self):
        with tempfile.TemporaryDirectory() as d:
            recipe_text = RECIPE_DIRTY.read_text(encoding="utf-8").replace(
                "enforce: false", "enforce: true")
            p = Path(d) / "dirty_enforce.yaml"
            p.write_text(recipe_text, encoding="utf-8")
            rc = main(["generate", "--recipe", str(p), "--out", str(Path(d) / "out")])
            self.assertEqual(rc, 1)                                # 未过闸不出库语义

    def test_parquet_delivery_passes_gate(self):
        with tempfile.TemporaryDirectory() as d:
            rc = main(["generate", "--recipe", str(RECIPE_DEMO), "--out", d,
                       "--format", "parquet"])
            self.assertEqual(rc, 0)                                # Parquet 交付态过闸（含亚日）
            m = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(m["output_format"], "parquet")
            self.assertEqual(m["gate"]["overall"], "pass")
            import pyarrow.parquet as pq
            sub = pq.read_table(Path(d) / "sensor_reading_subdaily.parquet")
            self.assertEqual(sub.num_rows, 2 * 3 * 96 * 365)


if __name__ == "__main__":
    unittest.main()
