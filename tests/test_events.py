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

    def test_module_does_not_compute_forward_returns(self):
        import inspect
        src = inspect.getsource(E)
        self.assertNotIn(".shift(-2", src)
        self.assertEqual(src.count(".shift(-"), 2)  # only the next-bar volume confirmation, in each setup builder


class TestYahoo(unittest.TestCase):
    def test_dates_use_exchange_time_and_drop_empty_bars(self):
        raw = b'{"chart":{"result":[{"meta":{"gmtoffset":-14400},"timestamp":[1700000000,1700086400,1700172800],"indicators":{"quote":[{"open":[1,1,1],"high":[2,2,2],"low":[1,1,1],"close":[1.5,null,1.6],"volume":[5,5,5]}]}}]}}'
        d = H.parse_yahoo(raw)
        self.assertEqual(len(d), 2)
        self.assertEqual(d.date.iloc[0], "2023-11-14")


if __name__ == "__main__":
    unittest.main()
