"""M1 冒烟测试（stdlib unittest）：可复现性 + schema 符合性 + 物理常识。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE = ROOT / "recipes" / "one_well_365d.yaml"


def _run(out: Path, seed: int) -> int:
    return main(["generate", "--recipe", str(RECIPE), "--out", str(out), "--seed", str(seed)])


class M1Acceptance(unittest.TestCase):
    def test_same_seed_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            self.assertEqual(_run(Path(d1), 42), 0)
            self.assertEqual(_run(Path(d2), 42), 0)
            for name in ("well.csv", "wellbore.csv", "sensor_channel.csv", "production_daily.csv"):
                self.assertEqual(
                    (Path(d1) / name).read_bytes(),
                    (Path(d2) / name).read_bytes(),
                    f"{name} 同种子两次生成不一致",
                )

    def test_different_seed_changes_output(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            self.assertEqual(_run(Path(d1), 42), 0)
            self.assertEqual(_run(Path(d2), 43), 0)
            self.assertNotEqual(
                (Path(d1) / "production_daily.csv").read_bytes(),
                (Path(d2) / "production_daily.csv").read_bytes(),
            )

    def test_ledger_shape_and_domain_sanity(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_run(Path(d), 7), 0)
            manifest = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))

            with (Path(d) / "production_daily.csv").open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 365)

            ds = [date.fromisoformat(r["prod_date"]) for r in rows]
            self.assertEqual(ds[0], date(2025, 1, 1))
            self.assertEqual([(ds[i + 1] - ds[i]).days for i in range(364)], [1] * 364)

            well_ids = {r["well_id"] for r in rows}
            self.assertEqual(len(well_ids), 1)  # 配方 counts.well=1

            for r in rows:
                hours = float(r["producing_hours"])
                oil = float(r["oil_rate"])
                water = float(r["water_rate"])
                gas = float(r["gas_rate"])
                self.assertTrue(0.0 <= hours <= 24.0)
                self.assertGreaterEqual(oil, 0.0)
                self.assertGreaterEqual(water, 0.0)
                self.assertGreaterEqual(gas, 0.0)
                if hours == 0.0:  # 停机日产量为 0
                    self.assertEqual((oil, water, gas), (0.0, 0.0, 0.0))
                if oil + water > 0.0:  # 含水率不越界
                    wc = water / (oil + water)
                    self.assertLessEqual(wc, 0.95)
                    self.assertGreaterEqual(wc, 0.0)

            # manifest：单位表覆盖全部物理量字段；声明红线在；符合性通过
            units = manifest["units"]["production_daily"]
            for f in ("producing_hours", "oil_rate", "water_rate", "gas_rate"):
                self.assertIn(f, units)
            self.assertIn("禁止用于储量申报", manifest["synthetic_data_declaration"])
            self.assertEqual(manifest["conformance"]["status"], "pass")

            # 传感器通道：每井标准 3 通道，单位来自目录
            with (Path(d) / "sensor_channel.csv").open(newline="", encoding="utf-8") as f:
                channels = list(csv.DictReader(f))
            self.assertEqual(len(channels), 3)
            self.assertEqual({c["unit"] for c in channels}, {"MPa", "MPa", "°C"})


if __name__ == "__main__":
    unittest.main()
