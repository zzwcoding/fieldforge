"""M5-T1 测井曲线测试：FORCE 记忆码对齐、深度单调、图版值域、分区结构、可复现。"""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE = ROOT / "recipes" / "tpa_s1_demo.yaml"
N_WELLS, N_SAMPLES = 120, 2401  # (2600-1400)/0.5 + 1


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class M5WellLogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="ff-m5-"))
        rc = main(["generate", "--recipe", str(RECIPE), "--out", str(cls.out)])
        assert rc == 0, "含闸门的合同生成失败"

    def test_shape_and_pk(self):
        rows = _rows(self.out, "well_log_curve.csv")
        self.assertEqual(len(rows), N_WELLS * N_SAMPLES)
        keys = {(r["well_id"], r["depth_md"]) for r in rows}
        self.assertEqual(len(keys), len(rows))

    def test_depth_monotonic_per_well(self):
        by_well: dict[str, list[float]] = {}
        for r in _rows(self.out, "well_log_curve.csv"):
            by_well.setdefault(r["well_id"], []).append(float(r["depth_md"]))
        self.assertEqual(len(by_well), N_WELLS)
        for wid, depths in by_well.items():
            self.assertEqual(depths, sorted(depths), f"{wid} 深度非单调")
            self.assertEqual(len(depths), N_SAMPLES)

    def test_curves_in_physical_ranges(self):
        bands = {"gr": (0, 300), "rhob": (1.0, 3.2), "nphi": (-0.05, 0.7),
                 "rdep": (0.1, 100000), "dtc": (40, 150), "cali": (6, 26), "pef": (0.5, 9)}
        for r in _rows(self.out, "well_log_curve.csv"):
            for col, (lo, hi) in bands.items():
                v = float(r[col])
                self.assertGreaterEqual(v, lo, f"{col}={v}")
                self.assertLessEqual(v, hi, f"{col}={v}")

    def test_lithology_zoned_not_noise(self):
        """分区结构：岩性按厚度成段（存在 ≥10m 的连续段），而非逐采样点随机。"""
        from collections import Counter
        by_well: dict[str, list[str]] = {}
        for r in _rows(self.out, "well_log_curve.csv"):
            by_well.setdefault(r["well_id"], []).append(r["lithology"])
        longest = 0
        for seq in by_well.values():
            run, prev = 0, None
            for v in seq:
                run = run + 1 if v == prev else 1
                prev = v
                longest = max(longest, run)
        self.assertGreaterEqual(longest, 20)  # ≥10m 连续段（0.5m 采样 ×20）
        counts = Counter(v for seq in by_well.values() for v in seq)
        self.assertLessEqual(len(counts), 12)  # FORCE 12 类以内

    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            main(["generate", "--recipe", str(RECIPE), "--out", d])
            self.assertEqual((self.out / "well_log_curve.csv").read_bytes(),
                             (Path(d) / "well_log_curve.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
