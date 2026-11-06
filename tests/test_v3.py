import unittest
from unittest import mock

import numpy as np
import pandas as pd

from bzd import v3 as V
from bzd.option_models import har_forecast


def prices(n=900, seed=1):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, .01, n)))
    idx = pd.date_range("2015-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * .99, "close": c}, index=idx)


class TestV3(unittest.TestCase):
    def test_spacing_keeps_holding_periods_apart(self):
        self.assertEqual(V.spaced([1, 1, 0, 1, 1, 1, 0, 1], 3), [0, 3, 7])

    def test_har_path_matches_the_app_forecast_on_each_day(self):
        c = prices(1200).close
        path = V.har_path(c, 21, 252)
        for day in (600, 900, 1199):
            r = np.log(c.iloc[:day + 1]).diff().dropna().values
            self.assertAlmostEqual(path.loc[c.index[day]], har_forecast(r, 21, 252), places=8)

    def test_straddle_seller_keeps_the_premium_when_price_stands_still(self):
        df = pd.DataFrame({"close": [100.0] * 40, "iv": [.2] * 40})
        self.assertAlmostEqual(V.straddle_pnl(df, {"days": 21})[0], 1.0)
        df.loc[21, "close"] = 130.0
        self.assertLess(V.straddle_pnl(df, {"days": 21})[0], -1)

    def test_holm_stops_at_the_first_failure(self):
        cfg = {"test": {"family_alpha": .05, "power_min": .5}}
        r = {k: {"p": p, "power": .9} for k, p in {"a": .001, "b": .03, "c": .02, "d": .5}.items()}
        out = V.holm(r, cfg)
        self.assertEqual(out["a"]["outcome"], "supportata")      # .001 < .05/4
        self.assertEqual(out["c"]["outcome"], "non supportata")  # .02 > .05/3: Holm stops, so b is not reached
        self.assertEqual(out["b"]["outcome"], "non supportata")

    def test_reset_fires_once_until_rsi_is_back_at_fifty(self):
        d = prices(400)
        with mock.patch.object(V.K.I, "rsi", return_value=pd.Series([50.0] * 100 + [35, 29, 31, 29, 28] + [55.0] * 10 + [35, 29] + [40.0] * 283, index=d.index)), \
             mock.patch.object(V.K, "long_trend", return_value=pd.Series(["rialzo"] * 400, index=d.index)):
            up = V.reset_flags(d)["R1"]
        self.assertEqual(list(np.flatnonzero(up)), [101, 116])

    def test_excess_is_signed_and_uses_the_next_bar(self):
        idx = pd.date_range("2020-01-01", periods=300, freq="D", tz="UTC")
        ret = np.zeros(300)
        ret[51] = .05  # the bar after the signal
        flags = np.zeros(300, bool)
        flags[50] = True
        cfg = {"test": {"min_pool": 20, "baseline_draws": 200}}
        out = V.pick_excess(idx, ret, flags, 5, -1, cfg, np.random.default_rng(0), idx[0], idx[-1] + pd.Timedelta(days=1))
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0][2], -.05)

    def test_counting_computes_no_return(self):
        cfg = V.load_config()
        cfg = {**cfg, "options_markets": {}}
        boom = mock.Mock(side_effect=AssertionError("a return was computed"))
        with mock.patch.object(V, "all_markets", return_value=["ES=F"]), mock.patch.object(V, "horizon_returns", boom), mock.patch.object(V, "straddle_pnl", boom), \
             mock.patch.object(V, "level_flags", lambda d, cfg: {"L1": np.zeros(len(d), bool), "L2": np.zeros(len(d), bool)}):
            rows, _ = V.collect(cfg, count_only=True)
        self.assertTrue(rows["Z1"])
        self.assertTrue(all(r[3] is None and r[4] is None for k in rows for r in rows[k]))


if __name__ == "__main__":
    unittest.main()
