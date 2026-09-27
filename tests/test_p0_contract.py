"""P0 数据合同测试：tpa 生产域 8 表字典对齐（主数据配比/行数锚点/勾稽/复现）。"""
from __future__ import annotations

import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

from fieldforge.cli import main
from fieldforge.engine import load_seeds

ROOT = Path(__file__).resolve().parent.parent
RECIPE = ROOT / "recipes" / "tpa_s1_demo.yaml"
DAYS = 365
N_EW, N_IW = 86, 34


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class P0Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="ff-p0-"))
        rc = main(["generate", "--recipe", str(RECIPE), "--out", str(cls.out)])
        assert rc == 0, "合同 schema 生成未过符合性检查"

    def test_master_data_profile(self):
        wells = _rows(self.out, "well_info.csv")
        self.assertEqual(len(wells), N_EW + N_IW)                       # 120 井
        self.assertEqual(sum(1 for w in wells if w["well_type"] == "EW"), N_EW)
        self.assertEqual(sum(1 for w in wells if w["well_type"] == "IW"), N_IW)
        ids = [w["well_id"] for w in wells]
        self.assertEqual(len(set(ids)), len(ids))                        # 井号唯一
        for wid in ids:
            self.assertRegex(wid, r"^[A-Z]-\d{2}$")                      # N-02 式
        tpa = load_seeds()["tpa"]
        self.assertTrue({w["block_name"] for w in wells} <= {b["name"] for b in tpa["blocks"]})
        self.assertTrue({w["platform"] for w in wells} <= set(tpa["platforms"]))
        self.assertTrue(all(re.match(r"^2019-\d{2}-\d{2}|^2020-\d{2}-\d{2}", w["first_prod_date"])
                            for w in wells))
        self.assertTrue(all(w["current_status"] in ("生产中", "停产", "检修", "待弃置") for w in wells))

    def test_row_count_anchors(self):
        self.assertEqual(len(_rows(self.out, "oil_production_daily.csv")), N_EW * DAYS)   # 31,390
        self.assertEqual(len(_rows(self.out, "water_injection_daily.csv")), N_IW * DAYS)  # 12,410
        self.assertEqual(len(_rows(self.out, "sensor_reading.csv")), (N_EW + N_IW) * 3 * DAYS)

    def test_daily_production_bounds(self):
        for r in _rows(self.out, "oil_production_daily.csv"):
            self.assertTrue(0.0 <= float(r["open_days"]) <= 24.0)            # 规则 5
            self.assertTrue(0.0 <= float(r["water_cut"]) <= 100.0)
            self.assertTrue(0.0 <= float(r["oil_pressure"]) <= 40.0)
            if float(r["open_days"]) == 0.0:                                  # 停机一致
                self.assertEqual(float(r["oil_output"]), 0.0)
            self.assertIn(r["report_shift"], ("A", "B", "C"))
            self.assertGreaterEqual(float(r["oil_output"]) + float(r["water_cut"]), 0.0)

    def test_monthly_settlement_reconciles(self):
        """规则 12：净重 = 区块月油量合计 × 0.98（损耗 2% ≤ 3% 界）。"""
        block_of = {w["well_id"]: w["block_name"] for w in _rows(self.out, "well_info.csv")}
        sums: dict[tuple, float] = {}
        for r in _rows(self.out, "oil_production_daily.csv"):
            key = (block_of[r["well_id"]], r["prod_date"][:7])
            sums[key] = sums.get(key, 0.0) + float(r["oil_output"])
        for r in _rows(self.out, "monthly_settlement.csv"):
            key = (r["block_name"], r["settle_date"][:7])
            expect = sums[key] * 0.98
            self.assertAlmostEqual(float(r["net_weight"]), expect, delta=0.05)
            dev = 1.0 - float(r["net_weight"]) / sums[key]
            self.assertLessEqual(dev, 0.03)

    def test_fluid_test_density_in_rule3_band(self):
        """规则 3：密度 ∈ [0.82, 0.98]（区块密度 ± 噪声）。"""
        for r in _rows(self.out, "fluid_test.csv"):
            self.assertTrue(0.82 <= float(r["density"]) <= 0.98)

    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d2:
            main(["generate", "--recipe", str(RECIPE), "--out", d2])
            for name in ("well_info.csv", "oil_production_daily.csv"):
                self.assertEqual((self.out / name).read_bytes(),
                                 (Path(d2) / name).read_bytes(), f"{name} 复现失败")

    def test_manifest_and_code_map(self):
        m = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["schema"]["name"], "tpa-contract")
        self.assertEqual(m["schema"]["version"], "0.1.0")
        code_map = load_seeds()["tpa"]["industry_code_map"]
        self.assertEqual(code_map["X_WELL_MASTER"], "well_info")
        self.assertEqual(code_map["X_OP_PROD_DAILY"], "oil_production_daily")
        self.assertIn("禁止用于储量申报", m["synthetic_data_declaration"])


if __name__ == "__main__":
    unittest.main()
