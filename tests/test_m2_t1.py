"""M2-T1 扫参适配器单测：deck 渲染与配方校验（纯本机，不碰 docker）。"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path

from fieldforge.physics.flow_adapter import Param, SweepError, load_sweep, render_deck

ROOT = Path(__file__).resolve().parent.parent
SWEEP = ROOT / "sweeps" / "spe1_orat.yaml"


class M2T1Render(unittest.TestCase):
    def test_render_substitutes_exactly_once(self):
        spec = load_sweep(SWEEP)
        texts = set()
        for v in spec.params[0].values:
            text = render_deck(spec, {"orat": v})
            self.assertRegex(text, rf"'PROD'\s+'OPEN'\s+'ORAT'\s+{v}\b")
            texts.add(text)
        self.assertEqual(len(texts), len(spec.params[0].values))  # 三档互不相同
        self.assertNotRegex(texts.pop(), "'PROD'\\s+'OPEN'\\s+'ORAT'\\s+20000\\b")  # 原值已不在

    def test_render_zero_match_raises(self):
        spec = load_sweep(SWEEP)
        bad = dataclasses.replace(
            spec, params=(Param("orat", "(NOSUCHKEYWORD\\s+)([0-9]+)", (1,)),))
        with self.assertRaises(SweepError):
            render_deck(bad, {"orat": 1})

    def test_load_sweep_missing_template_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.yaml"
            p.write_text("sweep: bad\ntemplate: no/such/file.DATA\nparams:\n"
                         "  - name: x\n    regex: '(A\\s+)([0-9]+)'\n    values: [1]\n",
                         encoding="utf-8")
            with self.assertRaises(SweepError):
                load_sweep(p)

    def test_load_sweep_missing_values_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.yaml"
            p.write_text("sweep: bad\nparams:\n  - name: x\n    regex: '(A\\s+)([0-9]+)'\n",
                         encoding="utf-8")
            with self.assertRaises(SweepError):
                load_sweep(p)


if __name__ == "__main__":
    unittest.main()
