"""P2 测试：受效关系 Σ=1（本体域）、Parquet 载体回读、M4 班报叙述化机判回流。"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from fieldforge import evaluate as gate
from fieldforge import narrate
from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent
RECIPE_CONTRACT = ROOT / "recipes" / "tpa_s1_demo.yaml"
RECIPE_CORE = ROOT / "recipes" / "one_well_365d.yaml"


def _rows(out: Path, name: str) -> list[dict]:
    with (out / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class P2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(tempfile.mkdtemp(prefix="ff-p2-"))
        assert main(["generate", "--recipe", str(RECIPE_CONTRACT), "--out", str(cls.out)]) == 0

    def test_injection_connection_sigma_one(self):
        conns = _rows(self.out, "injection_connection.csv")
        self.assertGreater(len(conns), 0)
        sums: dict[str, float] = {}
        pairs = set()
        for r in conns:
            pairs.add((r["injector_well_id"], r["producer_well_id"]))
            sums[r["injector_well_id"]] = sums.get(r["injector_well_id"], 0.0) + float(r["split_coefficient"])
        self.assertEqual(len(pairs), len(conns))                       # 主键唯一
        for k, v in sums.items():
            self.assertAlmostEqual(v, 1.0, places=6, msg=f"{k} 劈分系数合计 ≠ 1")
        # 受效油井与注水井同区块
        block = {w["well_id"]: w["block_name"] for w in _rows(self.out, "well_info.csv")}
        for r in conns:
            self.assertEqual(block[r["injector_well_id"]], block[r["producer_well_id"]])

    def test_gate_r_eff_passes(self):
        report = gate.evaluate(self.out)
        r_eff = next(m for m in report["metrics"] if m["id"] == "r_eff")
        self.assertEqual(r_eff["status"], "pass")

    def test_narrate_corpus_and_validation(self):
        wells = _rows(self.out, "well_info.csv")
        wid = next(w["well_id"] for w in wells if w["well_type"] == "EW")
        corpus_dir = self.out / "narration" / wid
        rc = main(["narrate", "--data", str(self.out), "--well", wid, "--days", "7",
                   "--out", str(corpus_dir)])
        self.assertEqual(rc, 0)
        m = json.loads((corpus_dir / "narration_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(m["reports"], 7)
        self.assertEqual(m["validation_failures"], 0)                  # 数值一致性全过
        first = sorted(e["prod_date"] for e in m["reports"])[0] if isinstance(m["reports"], list) else None
        # m["reports"] 是篇数；逐文件断言首篇内容含结构化要素
        sample = next(corpus_dir.glob("*.txt"))
        body = sample.read_text(encoding="utf-8")
        self.assertIn("生产班报", body)
        self.assertIn("日产油", body)
        self.assertIn("完成率", body)

    def test_narrate_validation_catches_tampering(self):
        row = {"prod_date": "2025-09-01", "oil_output": "30.0", "liquid_output": "40.0",
               "water_cut": "21.3", "oil_pressure": "4.2", "plan_output": "32.0",
               "open_days": "24.0", "report_shift": "A"}
        well = {"well_name": "渤南01", "field_name": "渤南油田", "platform": "CEP-A"}
        text = narrate.daily_report(row, well)
        self.assertEqual(narrate.validate(text, row), [])              # 模板自产自检零违例
        tampered = text.replace("30.00", "35.00")
        self.assertTrue(narrate.validate(tampered, row))               # 篡改必被机判逮住

    def test_narrate_unknown_well_rejected(self):
        rc = main(["narrate", "--data", str(self.out), "--well", "NO-SUCH", "--out",
                   str(self.out / "narration-bad")])
        self.assertEqual(rc, 2)                                        # 查无此井=合法数据态的拒答


class P2Parquet(unittest.TestCase):
    def test_core_parquet_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            rc = main(["generate", "--recipe", str(RECIPE_CORE), "--out", d, "--format", "parquet"])
            self.assertEqual(rc, 0)
            m = json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(m["output_format"], "parquet")
            import pyarrow.parquet as pq
            t = pq.read_table(Path(d) / "production_daily.parquet")
            self.assertEqual(t.num_rows, 365)
            self.assertIn("oil_rate", t.column_names)


if __name__ == "__main__":
    unittest.main()
