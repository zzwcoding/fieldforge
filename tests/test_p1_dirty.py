"""P1 脏特征注入 + 平台规则族测试：挂样本齐备、干净基线零误报、可复现、freshness 记账。"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from fieldforge import evaluate as gate
from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE_CLEAN = ROOT / "recipes" / "tpa_s1_demo.yaml"
RECIPE_DIRTY = ROOT / "recipes" / "tpa_s1_dirty.yaml"


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


import csv  # noqa: E402


class P1DirtyAndRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean = Path(tempfile.mkdtemp(prefix="ff-p1-clean-"))
        cls.dirty = Path(tempfile.mkdtemp(prefix="ff-p1-dirty-"))
        assert main(["generate", "--recipe", str(RECIPE_CLEAN), "--out", str(cls.clean)]) == 0
        assert main(["generate", "--recipe", str(RECIPE_DIRTY), "--out", str(cls.dirty)]) == 0
        cls.clean_report = gate.evaluate(cls.clean)
        cls.dirty_report = gate.evaluate(cls.dirty)

    def _rule(self, report, rid: str) -> dict:
        return next(m for m in report["metrics"] if m["id"] == rid)

    def test_dirty_recipe_injection_accounting(self):
        m = json.loads((self.dirty / "manifest.json").read_text(encoding="utf-8"))
        inj = m["injection"]
        self.assertTrue(inj["enabled"] and inj["dirty_mode"])
        c = inj["counts"]
        self.assertEqual(c["shift_duplicate"]["duplicated_rows"], 40)
        self.assertGreater(c["unit_misentry"]["misentered_rows"], 0)
        self.assertGreater(c["well_id_legacy"]["legacy_rows"], 0)
        self.assertEqual(c["stale_constant"]["frozen_windows"], 3)
        self.assertGreater(c["late_batch"]["late_batches"], 0)
        self.assertGreater(c["legacy_stop_code"]["legacy_rows"], 0)
        self.assertEqual(c["legacy_stop_code"]["unknown_rows"], 1)
        self.assertGreater(c["measure_missing"]["missing_rows"], 0)
        self.assertEqual(c["lab_conflict"]["conflict_rows"], 15)

    def test_nullable_measures_survive(self):
        rows = _rows(self.dirty, "well_measures.csv")
        missing = sum(1 for r in rows if r["effective_from"] == "")
        self.assertGreater(missing, 0)
        self.assertLess(missing, len(rows))  # 约 30% 缺失，非全缺

    def test_freshness_metadata(self):
        for out in (self.clean, self.dirty):
            m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(m["freshness"]["tier"], "offline")
            self.assertEqual(m["freshness"]["watermark"], "T-1")
            self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}$", m["freshness"]["as_of"]))

    def test_clean_dataset_all_rules_pass(self):
        self.assertEqual(self.clean_report["summary"]["overall"], "pass")
        for rid in ("r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r12"):
            self.assertEqual(self._rule(self.clean_report, rid)["status"], "pass", rid)
        self.assertEqual(self._rule(self.clean_report, "r11")["status"], "skipped")

    def test_dirty_dataset_hits_target_rules(self):
        """每条注入的脏特征都被对应规则逮住——挂样本齐备实证。"""
        expect_fail = {"r1", "r3", "r4", "r6", "r7", "r8", "r9", "r12"}
        for rid in expect_fail:
            self.assertEqual(self._rule(self.dirty_report, rid)["status"], "fail", rid)
        self.assertEqual(self._rule(self.dirty_report, "r10")["status"], "warn")
        # 未被产量改写类注入器波及的规则保持通过
        for rid in ("r2", "r5"):
            self.assertEqual(self._rule(self.dirty_report, rid)["status"], "pass", rid)
        # r12 联动失败属预期：产量改写（恒值冻结/强制停井）必然破坏月勾稽——
        # tpa 设定书 §3.1"指标不是独立数字"的物质平衡联动约束的活教材。

    def test_dirty_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            main(["generate", "--recipe", str(RECIPE_DIRTY), "--out", d])
            a = (self.dirty / "oil_production_daily.csv").read_bytes()
            b = (Path(d) / "oil_production_daily.csv").read_bytes()
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
