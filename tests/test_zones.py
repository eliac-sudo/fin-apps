import unittest
from unittest import mock

import numpy as np
import pandas as pd

from bzd import zones as Z


def bars(close):
    i = pd.date_range("2018-01-01", periods=len(close), freq="D", tz="UTC")
    c = pd.Series(close, index=i, dtype=float)
    return pd.DataFrame({"open": c.shift().fillna(c), "high": c * 1.01, "low": c * .99, "close": c})


class TestScore(unittest.TestCase):
    def test_every_part_stays_in_range(self):
        d = bars(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, .02, 600))))
        for s in Z.indicator_parts(d, "1d").values():
            self.assertLessEqual(s.max(), 1)
            self.assertGreaterEqual(s.min(), -1)

    def test_a_long_rise_is_stretched_up_and_a_fall_down(self):
        self.assertGreater(Z.indicator_score(bars(np.linspace(100, 300, 400)), "1d")[0].iloc[-1], Z.SZT_ABOVE)
        self.assertLess(Z.indicator_score(bars(np.linspace(300, 100, 400)), "1d")[0].iloc[-1], Z.BYZ_BELOW)

    def test_future_bars_cannot_change_a_past_score(self):
        d = bars(100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, .02, 500))))
        full = Z.indicator_score(d, "1d")[0]
        cut = Z.indicator_score(d.iloc[:400], "1d")[0]
        self.assertAlmostEqual(full.iloc[399], cut.iloc[-1], places=9)

    def test_tags(self):
        self.assertEqual((Z.tag_of(-50), Z.tag_of(-49), Z.tag_of(49), Z.tag_of(50)), ("BYZ", "NTR", "NTR", "SZT"))

    def test_weights_are_70_30_and_missing_mood_leaves_indicators_alone(self):
        self.assertAlmostEqual(Z.blend(-60, 100), -12)
        self.assertEqual(Z.blend(-60, None), -60)


class TestSentiment(unittest.TestCase):
    MOODS = {"Metalli preziosi": {"fear": 30, "greed": 10}, "Yen": {"fear": 30, "greed": 10}, "Agricoli": {"fear": 1, "greed": 1}, "Cripto": {"fear": 10, "greed": 30}}

    def test_fear_is_negative(self):
        self.assertEqual(Z.sentiment_score("GC=F", self.MOODS), -50)

    def test_mood_on_the_quoted_currency_flips_the_sign(self):
        self.assertEqual(Z.sentiment_score("USDJPY=X", self.MOODS), 50)

    def test_too_few_signals_mean_no_sentiment(self):
        self.assertIsNone(Z.sentiment_score("ZC=F", self.MOODS))
        self.assertIsNone(Z.sentiment_score("CL=F", self.MOODS))

    def test_crypto_also_uses_fear_and_greed(self):
        self.assertEqual(Z.sentiment_score("BTC", self.MOODS, 25), 0)  # (+50 and -50)
        self.assertEqual(Z.sentiment_score("BTC", {}, 25), -50)

    def test_every_market_has_a_theme(self):
        from bzd import technicals as K
        for m in K.all_markets():
            self.assertIn(m, Z.SENTIMENT_OF)


class TestMarket(unittest.TestCase):
    def test_all_frames_and_the_trend_flag(self):
        d = bars(np.r_[np.linspace(100, 3000, 2500), np.linspace(3000, 2800, 4)])  # a dip too short to turn the 50-bar average
        month = d.resample("MS").agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        with mock.patch.object(Z.K, "frames", return_value={"1d": d, "1M": month}):
            r = Z.market_zones("GC=F", {"Metalli preziosi": {"fear": 90, "greed": 10}})
        self.assertEqual(set(r), {"1d", "1M", "12M"})
        self.assertEqual(r["1d"]["tag"], "BYZ")
        self.assertEqual(r["1d"]["slow"], "rialzo")
        self.assertTrue(r["1d"]["with_trend"])
        self.assertEqual(r["1d"]["sentiment"], -80)
        self.assertAlmostEqual(r["1d"]["score"], .7 * r["1d"]["indicators"] + .3 * -80)
