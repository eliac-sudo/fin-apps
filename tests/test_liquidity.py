import os, tempfile, unittest

import numpy as np
import pandas as pd

from bzd import liquidity as L


class Liquidity(unittest.TestCase):
    def test_book_spread_and_depth_within_half_a_percent(self):
        snap = {"time": 1795551916039, "levels": [[{"px": "100.0", "sz": "2"}, {"px": "99.6", "sz": "1"}, {"px": "99.0", "sz": "50"}],
                                                 [{"px": "100.2", "sz": "3"}, {"px": "100.5", "sz": "1"}, {"px": "101.0", "sz": "50"}]]}
        r = L.book_row(snap)
        self.assertAlmostEqual(r["spread_bps"], 0.2 / 100.1 * 1e4)
        self.assertAlmostEqual(r["depth_usd"], 200 + 99.6 + 300.6 + 100.5)  # 99.0 and 101.0 are outside ±0.5%

    def test_empty_side_gives_no_row(self):
        self.assertIsNone(L.book_row({"time": 0, "levels": [[], [{"px": "1", "sz": "1"}]]}))

    def test_thin_trading_scores_low(self):
        idx = pd.date_range("2023-01-01", periods=900, freq="D", tz="UTC")
        rng = np.random.default_rng(1)
        close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, .01, 900))), idx)
        vol = pd.Series(1e6, idx)
        vol.iloc[-20:] = 1e5  # volume dries up and the same moves now cost more per dollar
        v = L.volume_liquidity(close, close * vol, vol)
        self.assertLess(v["volume_pct"], 5)
        self.assertGreater(v["impact_pct"], 90)
        self.assertEqual(v["band"], "scarsa")

    def test_net_liquidity_units(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                from bzd import history as H
                d = ["2026-11-11", "2026-11-18"]
                H.save("macro", "WALCL", pd.DataFrame({"date": d, "value": [6_600_000, 6_610_000]}), quiet=True)  # millions
                H.save("macro", "WTREGEN", pd.DataFrame({"date": d, "value": [800_000, 780_000]}), quiet=True)  # millions
                H.save("macro", "RRPONTSYD", pd.DataFrame({"date": ["2026-11-17", "2026-11-18"], "value": [5.0, 4.0]}), quiet=True)  # billions
                net = L.net_liquidity()
            finally:
                os.environ.pop("BZD_DATA")
        self.assertEqual(net.round(1).tolist(), [6600 - 800 - 0, 6610 - 780 - 4])

    def test_crypto_days_keep_only_complete_days(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                from bzd import history as H
                ts = pd.date_range("2026-11-22", periods=10, freq="4h", tz="UTC")
                H.save("crypto", "BTC_candles_4h", pd.DataFrame({"t": ts.astype(str), "open": 1, "high": 1, "low": 1, "close": range(10), "volume_usd": 10.0}), quiet=True)
                d = L.crypto_days("BTC")
            finally:
                os.environ.pop("BZD_DATA")
        self.assertEqual(len(d), 1)
        self.assertEqual((d.close.iloc[0], d.volume_usd.iloc[0]), (5, 60.0))


if __name__ == "__main__":
    unittest.main()
