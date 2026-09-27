"""M2-T3 传感器日度读数测试：可复现、量程、停机静稳、外键、注入联动。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE_PLAIN = ROOT / "recipes" / "one_well_365d.yaml"
RECIPE_SENSORS = ROOT / "recipes" / "one_well_365d_sensors.yaml"


def _run(recipe: Path, out: Path) -> int:
    return main(["generate", "--recipe", str(recipe), "--out", str(out)])


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class M2T3SensorReadings(unittest.TestCase):
    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            self.assertEqual(_run(RECIPE_SENSORS, Path(d1)), 0)
            self.assertEqual(_run(RECIPE_SENSORS, Path(d2)), 0)
            self.assertEqual(
                (Path(d1) / "sensor_reading.csv").read_bytes(),
                (Path(d2) / "sensor_reading.csv").read_bytes(),
            )

    def test_shape_ranges_fk_and_shutdown_static(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_run(RECIPE_PLAIN, Path(d)), 0)  # 无注入配方：满行数
            channels = _rows(Path(d), "sensor_channel.csv")
            ledger = _rows(Path(d), "production_daily.csv")
            readings = _rows(Path(d), "sensor_reading.csv")

            # 形状：每井 3 通道 × 365 生产日
            self.assertEqual(len(channels), 3)
            self.assertEqual(len(ledger), 365)
            self.assertEqual(len(readings), 3 * 365)

            # 外键：channel_id ⊆ 通道注册表
            chan_ids = {c["channel_id"] for c in channels}
            self.assertTrue({r["channel_id"] for r in readings} <= chan_ids)

            # 读数日期与生产台账同源；量程按通道校验
            ranges = {c["channel_id"]: (float(c["range_min"]), float(c["range_max"]))
                      for c in channels}
            for r in readings:
                self.assertIn(r["reading_date"], {x["prod_date"] for x in ledger})
                lo, hi = ranges[r["channel_id"]]
                self.assertGreaterEqual(float(r["value"]), lo)
                self.assertLessEqual(float(r["value"]), hi)

            # 停机日静稳：同一通道所有停机读数完全相等（静稳常值，无噪声）
            down_dates = {x["prod_date"] for x in ledger if float(x["producing_hours"]) == 0.0}
            self.assertTrue(down_dates)
            for cid in chan_ids:
                vals = {r["value"] for r in readings
                        if r["channel_id"] == cid and r["reading_date"] in down_dates}
                self.assertEqual(len(vals), 1, f"{cid} 停机读数不静稳: {vals}")

            # manifest：单位表与新实体记账
            manifest = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            self.assertIn("sensor_reading", manifest["units"])

    def test_injection_on_sensor_readings(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_run(RECIPE_SENSORS, Path(d)), 0)
            manifest = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            inj = manifest["injection"]
            self.assertTrue(inj["enabled"])
            self.assertGreater(inj["counts"]["spike"]["points"], 0)  # 确定性种子下必有坏点
            removed = inj["counts"]["gap"]["removed_rows"]
            readings = _rows(Path(d), "sensor_reading.csv")
            self.assertEqual(len(readings), 3 * 365 - removed)      # 缺测按行删除


if __name__ == "__main__":
    unittest.main()
