"""M3 评估闸门测试：三族指标的 pass/fail 语义（合成最小数据集，不依赖完整 generate）。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fieldforge import evaluate as gate
from fieldforge.cli import main

ROOT = Path(__file__).resolve().parent.parent

DECL = "测试用合成数据声明：禁止用于储量申报、生产决策。"


def _write_dataset(d: Path, *, rows: list[dict] | None = None, readings: list[dict] | None = None,
                   channels: list[dict] | None = None) -> Path:
    """构造最小合法数据集：1 井 1 通道 3 生产日（默认全合法）。"""
    d.mkdir(parents=True, exist_ok=True)
    (d / "well.csv").write_text(
        "field_name,well_id,well_type,spud_date,longitude,latitude\n长风,SYN-1,生产井,2015-01-01,121.0,38.0\n",
        encoding="utf-8")
    (d / "wellbore.csv").write_text(
        "well_id,wellbore_id,measured_depth,completion_type,completion_date\nSYN-1,SYN-1-B1,3000.0,射孔完井,2015-06-01\n",
        encoding="utf-8")
    (d / "sensor_channel.csv").write_text(
        "well_id,channel_id,channel_code,channel_name,unit,range_min,range_max,sample_interval_min\n"
        "SYN-1,SYN-1-WHP,WHP,井口油压,MPa,0.0,35.0,5\n", encoding="utf-8")
    prod = rows or [
        {"well_id": "SYN-1", "prod_date": "2025-01-01", "producing_hours": "24.0",
         "oil_rate": "30.0", "water_rate": "3.0", "gas_rate": "0.4"},
        {"well_id": "SYN-1", "prod_date": "2025-01-02", "producing_hours": "24.0",
         "oil_rate": "29.5", "water_rate": "3.1", "gas_rate": "0.4"},
        {"well_id": "SYN-1", "prod_date": "2025-01-03", "producing_hours": "0.0",
         "oil_rate": "0.0", "water_rate": "0.0", "gas_rate": "0.0"},
    ]
    with (d / "production_daily.csv").open("w", newline="", encoding="utf-8") as f:
        w = __import__("csv").DictWriter(f, fieldnames=list(prod[0]))
        w.writeheader()
        w.writerows(prod)
    chan = channels or [{"channel_id": "SYN-1-WHP", "range_min": "0.0", "range_max": "35.0"}]
    rd = readings or [
        {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-01", "value": "12.0"},
        {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-02", "value": "12.1"},
        {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-03", "value": "20.0"},  # 停机静稳
    ]
    with (d / "sensor_reading.csv").open("w", newline="", encoding="utf-8") as f:
        w = __import__("csv").DictWriter(f, fieldnames=list(rd[0]))
        w.writeheader()
        w.writerows(rd)
    entities = [{"entity": e, "file": f"{e}.csv",
                 "rows": sum(1 for _ in open(d / f"{e}.csv", encoding="utf-8")) - 1}
                for e in ("well", "wellbore", "sensor_channel", "production_daily", "sensor_reading")]
    (d / "manifest.json").write_text(json.dumps({
        "schema": {"file": "schemas/core-v0.yaml"},
        "synthetic_data_declaration": DECL,
        "entities": entities,
    }, ensure_ascii=False), encoding="utf-8")
    return d


class M3Gate(unittest.TestCase):
    def test_good_dataset_passes(self):
        with tempfile.TemporaryDirectory() as d:
            report = gate.evaluate(_write_dataset(Path(d)))
            self.assertEqual(report["summary"]["overall"], "pass")
            self.assertEqual(report["summary"]["fail"], 0)
            ids = {m["id"] for m in report["metrics"]}
            self.assertTrue({"q1", "q2", "p1", "p2", "p3", "f1", "f2", "f3", "f4", "f5"} <= ids)

    def test_sensor_out_of_range_fails(self):
        with tempfile.TemporaryDirectory() as d:
            readings = [
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-01", "value": "12.0"},
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-02", "value": "99.0"},  # 越量程
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-03", "value": "20.0"},
            ]
            report = gate.evaluate(_write_dataset(Path(d), readings=readings))
            f3 = next(m for m in report["metrics"] if m["id"] == "f3")
            self.assertEqual(f3["status"], "fail")
            self.assertEqual(report["summary"]["overall"], "fail")

    def test_downtime_with_production_fails(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [
                {"well_id": "SYN-1", "prod_date": "2025-01-01", "producing_hours": "24.0",
                 "oil_rate": "30.0", "water_rate": "3.0", "gas_rate": "0.4"},
                {"well_id": "SYN-1", "prod_date": "2025-01-02", "producing_hours": "0.0",
                 "oil_rate": "15.0", "water_rate": "0.0", "gas_rate": "0.0"},  # 停机日出油
                {"well_id": "SYN-1", "prod_date": "2025-01-03", "producing_hours": "24.0",
                 "oil_rate": "29.0", "water_rate": "3.1", "gas_rate": "0.4"},
            ]
            report = gate.evaluate(_write_dataset(Path(d), rows=rows))
            f2 = next(m for m in report["metrics"] if m["id"] == "f2")
            self.assertEqual(f2["status"], "fail")

    def test_primary_key_duplicate_fails(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [
                {"well_id": "SYN-1", "prod_date": "2025-01-01", "producing_hours": "24.0",
                 "oil_rate": "30.0", "water_rate": "3.0", "gas_rate": "0.4"},
                {"well_id": "SYN-1", "prod_date": "2025-01-01", "producing_hours": "24.0",
                 "oil_rate": "30.0", "water_rate": "3.0", "gas_rate": "0.4"},  # 主键重复
            ]
            report = gate.evaluate(_write_dataset(Path(d), rows=rows))
            p1 = next(m for m in report["metrics"] if m["id"] == "p1")
            self.assertEqual(p1["status"], "fail")

    def test_reference_identical_gives_ks_zero(self):
        with tempfile.TemporaryDirectory() as d:
            _write_dataset(Path(d))
            ref = Path(d) / "production_daily.csv"
            report = gate.evaluate(Path(d), reference=ref)
            q3 = next(m for m in report["metrics"] if m["id"] == "q3")
            self.assertEqual(q3["status"], "pass")
            self.assertTrue(all(v["ks"] == 0.0 for v in q3["value"].values()))

    def test_anonymeter_skipped_without_real(self):
        with tempfile.TemporaryDirectory() as d:
            report = gate.evaluate(_write_dataset(Path(d)))
            p3 = next(m for m in report["metrics"] if m["id"] == "p3")
            self.assertEqual(p3["status"], "skipped")

    def test_cli_exit_code_semantics(self):
        with tempfile.TemporaryDirectory() as d_good, tempfile.TemporaryDirectory() as d_bad:
            _write_dataset(Path(d_good))
            self.assertEqual(main(["evaluate", "--data", d_good]), 0)
            readings = [
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-01", "value": "12.0"},
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-02", "value": "99.0"},
                {"well_id": "SYN-1", "channel_id": "SYN-1-WHP", "reading_date": "2025-01-03", "value": "20.0"},
            ]
            _write_dataset(Path(d_bad), readings=readings)
            self.assertEqual(main(["evaluate", "--data", d_bad]), 1)


if __name__ == "__main__":
    unittest.main()
