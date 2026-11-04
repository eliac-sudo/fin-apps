import json
import unittest

import numpy as np
import pandas as pd

from bzd import events as E
from bzd import history as H


def days(n, start="2020-01-01"):
    return pd.date_range(start, periods=n, freq="D", tz="UTC")


class TestNoLookahead(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.s = pd.Series(100 * np.exp(rng.normal(0, .01, 400).cumsum()), index=days(400))

    def test_features_ignore_future_values(self):
        for fn in (lambda x: E.ret_z(x, 60), lambda x: E.log_z(x, 60), lambda x: E.past_quantile(x, .9, 52)):
            base = fn(self.s)
            changed = self.s.copy()
            changed.iloc[300:] *= 5
            pd.testing.assert_series_equal(base.iloc[:300], fn(changed).iloc[:300])

    def test_quantile_excludes_current_value(self):
        s = pd.Series([1.0] * 60 + [100.0], index=days(61))
        self.assertEqual(E.past_quantile(s, .9).iloc[-1], 1.0)

    def test_cot_is_invisible_until_available(self):
        rep = pd.Series(pd.to_datetime(["2024-01-02"]))
        self.assertEqual(H.cot_available(rep)[0], pd.Timestamp("2024-01-08"))
        cot = pd.DataFrame({"available": ["2024-01-08"], "spec_net_pct_oi": [0.5]})
        got = E.align_cot(cot, days(10, "2024-01-05"))
        self.assertTrue(np.isnan(got.spec_net_pct_oi[pd.Timestamp("2024-01-07", tz="UTC")]))
        self.assertEqual(got.spec_net_pct_oi[pd.Timestamp("2024-01-08", tz="UTC")], 0.5)


class TestEvents(unittest.TestCase):
    def test_cool_off_keeps_first_trigger(self):
        m = pd.Series(False, index=days(20))
        m.iloc[[1, 2, 3, 10]] = True
        got = E.first_of_runs(m, 3)
        self.assertEqual(list(got), [m.index[1], m.index[10]])

    def test_cool_off_handles_missing_values(self):
        m = pd.Series([True, None, True], index=days(3), dtype=object)
        self.assertEqual(len(E.first_of_runs(m.astype("boolean"), 1)), 2)

    def test_clusters_merge_close_events_across_assets(self):
        i = days(30)
        self.assertEqual(E.n_clusters([i[0], i[1], i[2], i[20]], 1), 2)
        self.assertEqual(E.n_clusters([], 1), 0)

    def test_roll_gap_is_flagged_but_session_move_is_not(self):
        idx = days(3)
        d = pd.DataFrame({"open": [100., 90.2, 100.], "close": [100., 90., 92.]}, index=idx)
        bad = E.roll_artefact(d, None)
        self.assertTrue(bad.iloc[1])  # all gap: open already near the new price
        self.assertFalse(bad.iloc[2])  # opened far from the close, so the move happened in session
        d2 = pd.DataFrame({"open": [100., 99.8], "close": [100., 90.]}, index=idx[:2])
        self.assertFalse(E.roll_artefact(d2, None).iloc[1])

    def test_calm_etf_flags_a_futures_move(self):
        idx = days(2)
        d = pd.DataFrame({"open": [100., 99.8], "close": [100., 90.]}, index=idx)
        self.assertTrue(E.roll_artefact(d, None, pd.Series([0., .2], index=idx)).iloc[1])
        self.assertFalse(E.roll_artefact(d, None, pd.Series([0., -4.], index=idx)).iloc[1])

    def test_moving_etf_confirms_an_overnight_crash(self):
        idx = days(2)
        d = pd.DataFrame({"open": [100., 90.2], "close": [100., 90.]}, index=idx)
        self.assertFalse(E.roll_artefact(d, None, pd.Series([0., -5.], index=idx)).iloc[1])

    def test_gap_rule_applies_on_days_the_etf_has_no_value(self):
        idx = days(2)
        d = pd.DataFrame({"open": [100., 90.2], "close": [100., 90.]}, index=idx)
        self.assertTrue(E.roll_artefact(d, None, pd.Series([0., np.nan], index=idx)).iloc[1])


class TestYahoo(unittest.TestCase):
    def yahoo(self, ts, tz="America/New_York", close=1.5):
        return json.dumps({"chart": {"result": [{"meta": {"gmtoffset": -18000, "exchangeTimezoneName": tz}, "timestamp": [ts],
                "indicators": {"quote": [{"open": [1], "high": [2], "low": [1], "close": [close], "volume": [5]}]}}]}}).encode()

    def test_daylight_saving_bar_keeps_its_session_date(self):
        # 04:00 UTC is midnight in New York in April. Today's -5h winter offset would give the previous day.
        ts = int(pd.Timestamp("2025-04-03 04:00", tz="UTC").timestamp())
        self.assertEqual(H.parse_yahoo(self.yahoo(ts)).date.iloc[0], "2025-04-03")

    def test_winter_bar_keeps_its_session_date(self):
        ts = int(pd.Timestamp("2025-01-15 05:00", tz="UTC").timestamp())
        self.assertEqual(H.parse_yahoo(self.yahoo(ts)).date.iloc[0], "2025-01-15")

    def test_bars_without_a_close_are_dropped(self):
        self.assertEqual(len(H.parse_yahoo(self.yahoo(1700000000, close=None))), 0)


if __name__ == "__main__":
    unittest.main()
