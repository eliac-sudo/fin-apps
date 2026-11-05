import unittest

import numpy as np
import pandas as pd

from bzd import b3 as B


class TestReturns(unittest.TestCase):
    def test_open_to_close_with_costs_and_funding(self):
        o = np.array([100., 110., 120., 130.])
        c = np.array([105., 115., 121., 140.])
        r = B.horizon_returns(o, c, 2, .001, np.array([9., .01, .01, 9.]))
        self.assertAlmostEqual(r[0], 115 / 100 - 1 - .001 - .01)
        self.assertTrue(np.isnan(r[3]))

    def test_first_bar_funding_is_not_paid(self):
        r = B.horizon_returns(np.array([100., 100.]), np.array([100., 100.]), 1, 0, np.array([.5, .5]))
        self.assertEqual(r[0], 0)

    def test_negative_prices_are_excluded(self):
        self.assertTrue(np.isnan(B.horizon_returns(np.array([10., 10.]), np.array([-37., 10.]), 1, 0)[0]))


class TestBaseline(unittest.TestCase):
    def test_pool_avoids_events_other_years_and_calibration(self):
        n = 100
        ret, years = np.zeros(n), np.r_[np.full(50, 2024), np.full(50, 2025)]
        in_test = np.arange(n) >= 10
        pool = B.baseline_pool(ret, years, np.array([30]), 5, 2024, in_test)
        self.assertTrue(((pool >= 10) & (pool < 50)).all())
        self.assertFalse(set(range(26, 35)) & set(pool.tolist()))
        self.assertIn(25, pool)
        self.assertIn(35, pool)

    def test_excess_removes_market_drift(self):
        rng = np.random.default_rng(0)
        ret = rng.normal(.05, .01, 1000)  # strong drift, no timing edge
        got = B.event_excess(ret, np.full(1000, 2024), np.arange(50, 950, 30), 5, rng, np.ones(1000, bool))
        ex = np.array([x[2] for x in got])
        self.assertAlmostEqual(ex.mean(), 0, delta=.005)
        self.assertGreater(np.array([x[1] for x in got]).mean(), .04)


class TestOutcome(unittest.TestCase):
    def test_three_outcome_rule(self):
        self.assertEqual(B.outcome(.001, .2), "supportata")
        self.assertEqual(B.outcome(.3, .6), "non supportata")
        self.assertEqual(B.outcome(.3, .4), "non informativa")
        self.assertEqual(B.outcome(None, .4), "non informativa")

    def test_power_matches_preregistered_table(self):
        self.assertAlmostEqual(B.power_at(131, .3, B.ALPHA_FAMILY), .90, delta=.01)
        self.assertAlmostEqual(B.power_at(45, .3, B.ALPHA_FAMILY), .43, delta=.01)

    def test_zero_effect_is_not_significant_often(self):
        rng = np.random.default_rng(1)
        hits = sum(B.cluster_test(rng.normal(0, 1, 100), "greater", reps=200)["outcome"] == "supportata" for _ in range(400))
        self.assertLess(hits / 400, .04)  # near the 1.67% it should be

    def test_known_effect_is_found_about_as_often_as_power_says(self):
        rng = np.random.default_rng(2)
        hits = sum(B.cluster_test(rng.normal(.3, 1, 100), "greater", reps=200)["outcome"] == "supportata" for _ in range(400))
        self.assertAlmostEqual(hits / 400, B.power_at(100, .3, B.ALPHA_FAMILY), delta=.08)

    def test_direction_matters_for_overheating(self):
        rng = np.random.default_rng(3)
        v = rng.normal(-.5, 1, 100)
        self.assertEqual(B.cluster_test(v, "less", reps=200)["outcome"], "supportata")
        self.assertNotEqual(B.cluster_test(v, "greater", reps=200)["outcome"], "supportata")

    def test_too_few_clusters_is_not_informative(self):
        self.assertEqual(B.cluster_test([.1, .2], "greater")["outcome"], "non informativa")


class TestPipeline(unittest.TestCase):
    def synthetic(self, edge):
        """Random walk where events are followed by a known move. The pipeline must recover it."""
        rng = np.random.default_rng(5)
        n = 3000
        r = rng.normal(0, .01, n)
        pos = np.arange(100, 2900, 25)
        for e in pos:
            r[e:e + 5] += edge / 5
        c = 100 * np.exp(r.cumsum())
        o = np.r_[100., c[:-1]]
        return o, c, pos

    def test_end_to_end_recovers_a_known_edge_and_finds_none_when_absent(self):
        for edge, expect in ((.02, "supportata"), (0.0, "non supportata")):
            o, c, pos = self.synthetic(edge)
            ret = B.horizon_returns(o, c, 5, 0)
            got = B.event_excess(ret, np.full(len(o), 2024), pos, 5, np.random.default_rng(1), np.ones(len(o), bool))
            t = B.cluster_test([x[2] for x in got], "greater", reps=500)
            self.assertEqual(t["outcome"], expect, edge)
            if edge:
                self.assertAlmostEqual(t["mean"], edge, delta=.006)

    def test_summary_counts_one_episode_once(self):
        df = pd.DataFrame({"trigger": ["2024-01-01", "2024-01-01", "2024-02-01", "2024-03-01"], "excess": [.1, .3, .1, .1], "net": 0., "score": 1, "market": "m"})
        res, g = B.summarize(df, {"merge_days": 1}, "panic")
        self.assertEqual(res["clusters"], 3)
        self.assertAlmostEqual(g.excess.iloc[0], .2)

    def test_second_run_is_refused(self):
        from unittest import mock
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "v.json"
            p.write_text("{}")
            with mock.patch.object(B, "RESULTS", p), mock.patch.object(B, "run_all") as run:
                self.assertEqual(B.main(["run", "--confirm"]), 1)
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
