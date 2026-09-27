"""M2-T2 注入器测试：可复现性、manifest 记账、注入效果与符合性。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE_PLAIN = ROOT / "recipes" / "one_well_365d.yaml"
RECIPE_INJ = ROOT / "recipes" / "one_well_365d_injected.yaml"


def _run(recipe: Path, out: Path) -> int:
    return main(["generate", "--recipe", str(recipe), "--out", str(out)])


def _rows(out: Path) -> list[dict]:
    with (out / "production_daily.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class M2T2Injection(unittest.TestCase):
    def test_injected_reproducible(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            self.assertEqual(_run(RECIPE_INJ, Path(d1)), 0)
            self.assertEqual(_run(RECIPE_INJ, Path(d2)), 0)
            self.assertEqual(
                (Path(d1) / "production_daily.csv").read_bytes(),
                (Path(d2) / "production_daily.csv").read_bytes(),
            )

    def test_injection_manifest_and_effects(self):
        with tempfile.TemporaryDirectory() as dp, tempfile.TemporaryDirectory() as di:
            self.assertEqual(_run(RECIPE_PLAIN, Path(dp)), 0)
            self.assertEqual(_run(RECIPE_INJ, Path(di)), 0)

            manifest = json.loads((Path(di) / "manifest.json").read_text(encoding="utf-8"))
            inj = manifest["injection"]
            self.assertTrue(inj["enabled"])
            self.assertEqual(inj["version"], "2.0.0")
            counts = inj["counts"]
            self.assertGreater(counts["spike"]["points"], 0)      # 确定性种子下必有坏点
            self.assertGreater(counts["maintenance_window"]["days"], 0)

            plain, inj_rows = _rows(Path(dp)), _rows(Path(di))
            removed = counts["gap"]["removed_rows"]
            self.assertEqual(len(plain), 365)
            self.assertEqual(len(inj_rows), 365 - removed)        # 缺测=丢行
            self.assertTrue({r["prod_date"] for r in inj_rows} <= {r["prod_date"] for r in plain})

            zero_plain = sum(1 for r in plain if float(r["producing_hours"]) == 0.0)
            zero_inj = sum(1 for r in inj_rows if float(r["producing_hours"]) == 0.0)
            # 停机窗口只增不减零行；缺测至多删 removed 行零行
            self.assertGreaterEqual(
                zero_inj,
                zero_plain + counts["maintenance_window"]["days"] - removed,
            )
            # 注入后仍过符合性（rc==0 即通过），conformance 记账在案
            self.assertEqual(manifest["conformance"]["status"], "pass")

    def test_plain_recipe_records_no_injection(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(_run(RECIPE_PLAIN, Path(d)), 0)
            manifest = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["injection"], {"enabled": False})


if __name__ == "__main__":
    unittest.main()
