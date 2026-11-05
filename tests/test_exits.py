import unittest

import numpy as np
import pandas as pd

from bzd import exits as X

CFG = {"calibration_end": "2020-12-31", "merge_days": 1}
INF_ATR = None


def bars(rows):
    """rows: (open, high, low, close)."""
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def run(rows, rule, stop0=90.0, risk=10.0, e=0, last=None, atr=None, flags=None):
    o, h, l, c = bars(rows)
    atr = np.full(len(rows), 1.0) if atr is None else np.array(atr, float)
    return X.simulate(o, h, l, c, atr, e, stop0, risk, rule, len(rows) - 1 if last is None else last, flags)


class TestSimulate(unittest.TestCase):
    def test_stop_wins_when_a_bar_touches_stop_and_target(self):
        f, _ = run([(100, 125, 85, 110)], {"stop": True, "targets": [[2, 1.0]]})
        self.assertEqual(f, [(1.0, 90.0, 0, "stop")])

    def test_gap_below_stop_fills_at_the_open_not_the_stop(self):
        f, _ = run([(100, 101, 99, 100), (80, 82, 78, 81)], {"stop": True})
        self.assertEqual(f[0][1:], (80, 1, "stop_gap"))

    def test_gap_above_target_fills_at_the_open(self):
        f, _ = run([(100, 101, 99, 100), (130, 131, 129, 130)], {"stop": True, "targets": [[2, 1.0]]})
        self.assertEqual(f[0][1:], (130, 1, "target"))

    def test_hold_ignores_stops_and_exits_at_last_close(self):
        f, _ = run([(100, 101, 50, 60), (60, 70, 55, 65)], {"stop": False})
        self.assertEqual(f, [(1.0, 65, 1, "time")])

    def test_scale_out_fractions_sum_to_one(self):
        rule = {"stop": True, "targets": [[1, .3333333333], [2, .3333333333]], "trail_atr": 100}
        f, _ = run([(100, 111, 99, 110), (110, 121, 109, 120), (120, 125, 119, 124)], rule)
        self.assertAlmostEqual(sum(x[0] for x in f), 1.0)
        self.assertEqual([x[3] for x in f], ["target", "target", "time"])

    def test_breakeven_starts_on_the_next_bar(self):
        rule = {"stop": True, "targets": [[1, .5]], "breakeven_after_first": True}
        # Reaches the target and dips below entry in the same bar: not stopped at entry yet
        f, _ = run([(100, 111, 95, 105), (105, 106, 99, 100)], rule)
        self.assertEqual([x[3] for x in f], ["target", "stop"])
        self.assertEqual(f[1][1], 100)

    def test_trailing_stop_uses_only_earlier_closes(self):
        rows = [(100, 101, 99, 100), (100, 121, 99, 120), (120, 121, 110, 112)]
        f, _ = run(rows, {"stop": True, "trail_atr": 5})
        self.assertEqual(f[0][1:], (115, 2, "stop"))  # 120 close from bar 1, minus 5
        # In bar 1 itself the new high can't raise the stop
        f2, _ = run([(100, 121, 91, 120)], {"stop": True, "trail_atr": 5})
        self.assertEqual(f2[0][3], "time")

    def test_signal_exit_is_at_the_open_of_the_flagged_bar(self):
        rows = [(100, 101, 99, 100), (102, 103, 101, 102), (104, 105, 103, 104)]
        f, _ = run(rows, {"stop": True}, flags=np.array([False, True, False]))
        self.assertEqual(f, [(1.0, 102, 1, "signal")])

    def test_time_exit_at_last_bar(self):
        rows = [(100, 101, 99, 100)] * 5
        f, _ = run(rows, {"stop": True}, last=2)
        self.assertEqual(f[0][2:], (2, "time"))


class TestCosts(unittest.TestCase):
    def test_net_return_and_r_with_costs(self):
        net, r, gross = X.net_result([(1.0, 110.0, 3, "time")], 100.0, 10.0, 0, .001)
        self.assertAlmostEqual(gross, .10)
        self.assertAlmostEqual(net, .098)
        self.assertAlmostEqual(r, .98)

    def test_long_pays_positive_funding_only_while_open(self):
        funding = np.array([9., .01, .01, 9.])
        net, _, _ = X.net_result([(1.0, 100.0, 2, "time")], 100.0, 10.0, 0, 0, funding)
        self.assertAlmostEqual(net, -.02)

    def test_partial_exit_reduces_funding(self):
        funding = np.array([0., .01, .01])
        net, _, _ = X.net_result([(.5, 100.0, 1, "target"), (.5, 100.0, 2, "time")], 100.0, 10.0, 0, 0, funding)
        self.assertAlmostEqual(net, -(.01 + .005))


class TestStop(unittest.TestCase):
    def test_uses_lows_before_entry_and_ignores_the_entry_bar(self):
        low = np.array([95., 90., 92., 1.])
        atr = np.array([2., 2., 2., 99.])
        p = {"low_lookback_bars": 3, "atr_below_low": .5, "min_atr_distance": .5}
        stop, risk = X.initial_stop(low, atr, 3, 100., p)
        self.assertEqual(stop, 89.0)
        self.assertEqual(risk, 11.0)

    def test_minimum_distance_when_price_is_below_the_low(self):
        low = np.array([95., 95., 95., 90.])
        p = {"low_lookback_bars": 3, "atr_below_low": .5, "min_atr_distance": .5}
        stop, risk = X.initial_stop(low, np.full(4, 2.), 3, 90., p)
        self.assertEqual(risk, 1.0)
        self.assertEqual(stop, 89.0)


class TestTestPeriodIsSealed(unittest.TestCase):
    def frame(self, end):
        idx = pd.date_range("2020-01-01", end, freq="D", tz="UTC")
        return pd.DataFrame({"open": 100., "high": 101., "low": 99., "close": 100.}, index=idx)

    def test_cut_removes_everything_after_calibration(self):
        got = X.cut_to_calibration(self.frame("2021-06-30"), CFG)
        self.assertEqual(got.index.max(), pd.Timestamp("2020-12-31", tz="UTC"))

    def test_run_market_refuses_test_period_bars(self):
        ev = pd.DataFrame(columns=["setup", "entry", "market", "trigger", "score"])
        config = {"atr_bars": 14, "entries": ["panic"], "rules": {}, "initial_stop": {}}
        with self.assertRaises(ValueError):
            X.run_market(self.frame("2021-01-02"), ev, {"fee_per_side": 0, "slippage_per_side": 0}, config, CFG)

    def test_later_prices_cannot_change_a_result(self):
        rng = np.random.default_rng(1)
        n = 120
        idx = pd.date_range("2020-06-01", periods=n, freq="D", tz="UTC")
        c = 100 * np.exp(rng.normal(0, .01, n).cumsum())
        d = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * .99, "close": c}, index=idx)
        ev = pd.DataFrame([{"setup": "panic", "entry": str(idx[40]), "market": "X", "trigger": str(idx[38]), "score": 1}])
        config = {"atr_bars": 14, "entries": ["panic"], "initial_stop": {"low_lookback_bars": 3, "atr_below_low": .5, "min_atr_distance": .5},
                  "rules": {"hold": {"stop": False, "exit_at": "horizon"}, "t": {"stop": True, "targets": [[2, 1.]], "exit_at": "max"}}}
        ce = {"fee_per_side": 0, "slippage_per_side": 0, "horizon_bars": 10, "max_hold_bars": 20}
        cfg = {"calibration_end": "2021-12-31", "merge_days": 1}
        a, _ = X.run_market(d, ev, ce, config, cfg)
        d2 = d.copy()
        d2.iloc[70:] *= 3  # after the trade's longest possible path
        b, _ = X.run_market(d2, ev, ce, config, cfg)
        self.assertEqual(a, b)


class TestKnownEffectAndStats(unittest.TestCase):
    def sim_table(self, drift, n=800, seed=2):
        """Random walk trades on synthetic paths, through the real summary code."""
        rng = np.random.default_rng(seed)
        rows = []
        rules = {"hold": {"stop": False}, "stop": {"stop": True}}
        for k in range(n):
            r = rng.normal(drift, .01, 21)
            c = 100 * np.exp(r.cumsum())
            o = np.r_[100., c[:-1]]
            h, l = np.maximum(o, c) * 1.002, np.minimum(o, c) * .998
            for name, rule in rules.items():
                f, hi = X.simulate(o, h, l, c, np.full(21, 1.), 0, 96., 4., rule, 20)
                net, rr, g = X.net_result(f, 100., 4., 0, 0)
                rows.append({"setup": "s", "market": "M", "trigger": str(pd.Timestamp("2010-01-01", tz="UTC") + pd.Timedelta(days=10 * k)),
                             "rule": name, "r": rr, "net": net, "giveback_r": (hi / 100 - 1 - g) / .04, "bars": f[-1][2] + 1})
        return X.summarize(pd.DataFrame(rows), {"merge_days": 1}, {"reps": 500, "seed": 1})

    def test_no_edge_gives_mean_near_zero_and_no_selection(self):
        t = self.sim_table(0.0)
        hold = t[t.rule == "hold"].iloc[0]
        self.assertLess(abs(hold.mean_R), .2)
        self.assertEqual(X.select_rule(t), "hold")

    def test_positive_drift_is_recovered(self):
        drift = .002
        t = self.sim_table(drift)
        hold = t[t.rule == "hold"].iloc[0]
        expected = (np.exp(drift * 21 + .5 * 1e-4 * 21) - 1) / .04
        self.assertAlmostEqual(hold.mean_R, expected, delta=.2)

    def test_selection_needs_interval_above_zero(self):
        t = pd.DataFrame({"rule": ["hold", "a", "b"], "mean_R": [.1, .5, .3], "diff_lo90": [0, -.1, .2]})
        self.assertEqual(X.select_rule(t), "hold")
        t.loc[t.rule == "a", "diff_lo90"] = .01
        self.assertEqual(X.select_rule(t), "a")

    def test_clusters_merge_close_triggers(self):
        got = X.assign_clusters(["2020-01-01", "2020-01-01 12:00", "2020-02-01"], 1)
        self.assertEqual(got[0], got[1])
        self.assertNotEqual(got[0], got[2])

    def test_bad_bars_are_rejected(self):
        o, h, l, c = bars([(100, 101, 99, 100), (100, 99, 98, 100.5)])
        self.assertFalse(X.path_ok(o, h, l, c, 0, 1))
        o, h, l, c = bars([(100, 101, 99, 100), (100, 101, 99, 100)])
        self.assertTrue(X.path_ok(o, h, l, c, 0, 1))


if __name__ == "__main__":
    unittest.main()
