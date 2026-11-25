import json, os, tempfile, unittest
from unittest import mock

import pandas as pd

from bzd import v8


class V8(unittest.TestCase):
    def test_forward_results_live_in_data_not_in_config(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                d = v8.forward_dir()
            finally:
                os.environ.pop("BZD_DATA")
        self.assertEqual(d.name, "v8")
        self.assertTrue(str(d).startswith(t))

    def test_size_ignores_direction(self):
        b = pd.DataFrame({"open": [100.0, 100, 100, 100], "close": [110.0, 90, 100, 100]})
        r = v8.returns_for(b, 1, "ampiezza")
        self.assertAlmostEqual(r[0], 0.1)
        self.assertAlmostEqual(r[1], 0.1)

    def test_config_matches_the_preregistration(self):
        self.assertIn(v8.config_hash(), v8.DOC.read_text())

    def test_amendment_matches_the_preregistration(self):
        self.assertIn(v8.seq_hash(), v8.DOC.read_text())
        L = v8.load_looks()
        self.assertEqual(sorted(L["open"] + list(L["closed"])), sorted(v8.load_config()["forward"]["hypotheses"]))

    def test_looks(self):
        L, early, late = v8.load_looks(), pd.Timestamp("2027-06-01", tz="UTC"), pd.Timestamp("2028-11-25", tz="UTC")
        self.assertIsNone(v8.look_reached(L, 19, early))
        self.assertEqual(v8.look_reached(L, 20, early), 0)
        self.assertEqual(v8.look_reached(L, 45, early), 1)
        self.assertEqual(v8.look_reached(L, 5, late), 2)

    def judge(self, t, n, p, mean, now):
        rows = [("x", "m", f"2027-01-{i % 28 + 1:02d}", 0.01, 0.01) for i in range(n)]
        with mock.patch.object(v8, "collect", lambda cfg, hyps, *a, **k: {k2: rows for k2 in hyps}), \
             mock.patch.object(v8, "clusters", lambda r, cfg: n), \
             mock.patch.object(v8.V3, "summarise", lambda *a: {"p": p, "mean": mean, "clusters": n}):
            return v8.judge_forward(v8.load_config(), now=pd.Timestamp(now, tz="UTC"))

    def test_judging(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                s = self.judge(t, 10, 0.00001, 0.01, "2027-03-01")
                self.assertFalse(s["P1"]["judged"])  # no look before 20 clusters
                self.assertEqual(s["D1"]["result"]["outcome"], "chiusa senza guardare")
                s = self.judge(t, 20, 0.001, 0.01, "2027-06-01")
                self.assertFalse(s["P1"]["judged"])  # 0.001 is not under 0.0001
                self.assertEqual(s["P1"]["looks_done"], 1)
                s = self.judge(t, 21, 0.00001, 0.01, "2027-06-02")
                self.assertFalse(s["P1"]["judged"])  # the first look is never taken twice
                s = self.judge(t, 40, 0.005, 0.01, "2027-12-01")
                self.assertEqual(s["P1"]["result"]["outcome"], "supportata")
                self.assertEqual(s["P1"]["result"]["look"], 2)
                self.assertEqual(s["A1"]["result"]["threshold"], 0.01614)  # rechecked at 5% once P1 passed
            finally:
                os.environ.pop("BZD_DATA")


if __name__ == "__main__":
    unittest.main()
