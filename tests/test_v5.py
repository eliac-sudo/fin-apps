import unittest
from unittest import mock

import numpy as np
import pandas as pd

from bzd import v5 as V


class TestV5(unittest.TestCase):
    def test_names_read_as_they_say(self):
        self.assertEqual(V.SIGN, {"E1": 1, "E2": -1, "E3": 1, "E4": -1})

    def test_the_running_month_is_dropped(self):
        idx = pd.date_range("2026-08-01", "2026-11-05", freq="D", tz="UTC")
        d = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
        m = V.monthly_bars(d, pd.Timestamp("2026-11-06", tz="UTC"))
        self.assertEqual(m.index[-1].strftime("%Y-%m"), "2026-10")

    def test_monthly_pool_spans_the_whole_period(self):
        idx = pd.date_range("2010-01-01", periods=120, freq="MS", tz="UTC")
        ret = np.zeros(120)
        ret[61] = .1
        flags = np.zeros(120, bool)
        flags[60] = True
        cfg = {"test": {"min_pool": 20, "baseline_draws": 200}}
        out = V.pick_excess(idx, ret, flags, 3, 1, cfg, np.random.default_rng(0), idx[0], idx[-1], np.zeros(120, int))
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0][2], .1)

    def test_no_stock_is_a_market_of_the_program(self):
        from bzd.history import CRYPTO, ETF_CHECK, MARKETS
        from bzd.option_lab import BY_KEY
        from bzd import v4
        used = {*CRYPTO, *MARKETS, *ETF_CHECK.values(), *BY_KEY, *(m for _, m in v4.markets(v4.load_config()))}
        self.assertFalse(used & set(V.load_config()["markets"]))

    def test_counting_computes_no_return(self):
        boom = mock.Mock(side_effect=AssertionError("a return was computed"))
        with mock.patch.object(V, "horizon_returns", boom), mock.patch.object(V, "pick_excess", boom):
            rows, _ = V.collect(V.load_config(), count_only=True)
        self.assertTrue(all(r[3] is None for k in rows for r in rows[k]))


if __name__ == "__main__":
    unittest.main()
