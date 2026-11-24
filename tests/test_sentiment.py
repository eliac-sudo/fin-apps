import gzip, json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from scipy.stats import norm

from bzd import option_lab as L, option_models as M, sentiment as SM, technicals as K, thermo as Th


def series(values, start="2026-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), tz="UTC"), dtype=float)


class TestEpisodes(unittest.TestCase):
    def test_a_short_pause_keeps_one_episode(self):
        e = SM.episodes(series([50, 10, 12, 50, 8, 50, 50, 50, 50, 50, 9]), 15, 85)
        self.assertEqual([(x["from"], x["to"], x["days"], x["peak"]) for x in e], [("2026-01-02", "2026-01-05", 3, 8.0), ("2026-01-11", "2026-01-11", 1, 9.0)])

    def test_fear_and_euphoria_are_kept_apart(self):
        e = SM.episodes(series([10, 90, 95]), 15, 85)
        self.assertEqual([(x["kind"], x["peak"]) for x in e], [("paura", 10.0), ("euforia", 95.0)])

    def test_later_data_cannot_change_an_old_episode(self):
        base = [50, 10, 50, 50, 50, 50, 50, 50, 90]
        self.assertEqual(SM.episodes(series(base[:6]), 15, 85)[0], SM.episodes(series(base), 15, 85)[0])


class TestWords(unittest.TestCase):
    DAY = {"2026-11-04": {"Cripto": {"texts": 30, "fear": 18, "greed": 2}, "Yen": {"texts": 20, "fear": 1, "greed": 11}}, "2026-11-05": {"Cripto": {"texts": 4, "fear": 3, "greed": 0}, "Yen": {"texts": 30, "fear": 6, "greed": 6}}}

    def test_an_extreme_needs_enough_signals_and_a_clear_side(self):
        theme, marks = SM.word_marks("BTC", self.DAY)
        self.assertEqual(theme, "Cripto")
        self.assertEqual([(m["date"], m["kind"]) for m in marks], [("2026-11-04", "paura")])

    def test_a_pair_quoted_the_other_way_flips_the_mood(self):
        self.assertEqual(SM.word_marks("USDJPY=X", self.DAY)[1][0]["kind"], "paura")

    def test_final_days_are_stored_and_survive_their_raw_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "raw" / "news_x" / "2026-11-01"
            d.mkdir(parents=True)
            with gzip.open(d / "000000Z.json.gz", "wb") as f:
                f.write(b"x")
            rows = [(datetime(2026, 11, 1, 9, tzinfo=timezone.utc), "u1", "bitcoin crash panic"), (datetime(2026, 11, 1, 10, tzinfo=timezone.utc), "u2", "bitcoin to the moon"), (datetime(2026, 11, 1, 10, tzinfo=timezone.utc), "u2", "bitcoin to the moon")]
            now = datetime(2026, 11, 10, tzinfo=timezone.utc)
            with mock.patch.object(SM.T, "parse_job", return_value=rows):
                first = SM.read_days(tmp, now)
            self.assertEqual(first["2026-11-01"]["Cripto"], {"texts": 2, "fear": 1, "greed": 1})
            d.joinpath("000000Z.json.gz").unlink()
            d.rmdir()
            self.assertEqual(SM.read_days(tmp, now)["2026-11-01"]["Cripto"]["texts"], 2)
            self.assertEqual(json.loads((Path(tmp) / "sentiment" / "days.json").read_text())["2026-11-01"]["Cripto"]["fear"], 1)

    def test_recent_days_are_not_stored_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "raw" / "news_x" / "2026-11-09"
            d.mkdir(parents=True)
            with gzip.open(d / "000000Z.json.gz", "wb") as f:
                f.write(b"x")
            now = datetime(2026, 11, 10, tzinfo=timezone.utc)
            with mock.patch.object(SM.T, "parse_job", return_value=[(datetime(2026, 11, 9, 9, tzinfo=timezone.utc), "u1", "bitcoin crash")]):
                self.assertEqual(SM.read_days(tmp, now)["2026-11-09"]["Cripto"]["fear"], 1)
            self.assertFalse((Path(tmp) / "sentiment" / "days.json").exists())


class TestGauge(unittest.TestCase):
    def test_the_cot_sign_flips_on_pairs_quoted_the_other_way(self):
        self.assertEqual(Th.COT_AGAINST_PAIR, {"USDJPY=X", "USDCHF=X", "USDCAD=X"})

    def test_crypto_uses_the_published_limits(self):
        with mock.patch.object(SM, "read", return_value=pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "value": [20, 80]})):
            g = SM.gauge("BTC")
        self.assertEqual((g["low"], g["high"], g["series"].iloc[-1]), (25, 75, 80.0))


def ohlc(highs, lows, start="2020-01-06", freq="D"):
    idx = pd.date_range(start, periods=len(highs), freq=freq, tz="UTC")
    h, l = np.array(highs, float), np.array(lows, float)
    return pd.DataFrame({"open": (h + l) / 2, "high": h, "low": l, "close": (h + l) / 2}, index=idx)


class TestSharedLevels(unittest.TestCase):
    POOL = {"1M": {"width": 5.0, "swings": [(100.0, "2024-01-01"), (120.0, "2024-06-01")]}, "1w": {"width": 2.0, "swings": [(100.8, "2025-01-01"), (110.0, "2025-02-01"), (110.5, "2025-04-01")]},
            "1d": {"width": 1.0, "swings": [(103.0, "2026-01-01"), (103.2, "2026-02-01"), (108.0, "2026-03-01")]}}

    def test_a_slow_level_keeps_its_price_on_every_faster_timeframe(self):
        prices = {tf: {x["price"] for x in K.shared_levels(self.POOL, tf)} for tf in ("1M", "1w", "1d")}
        self.assertIn(100.0, prices["1M"] & prices["1w"] & prices["1d"])
        self.assertIn(120.0, prices["1M"] & prices["1w"] & prices["1d"])

    def test_a_faster_swing_near_a_slow_level_adds_a_touch_not_a_new_level(self):
        rows = K.shared_levels(self.POOL, "1w")
        self.assertEqual([x["price"] for x in rows if 99 < x["price"] < 102], [100.0])

    def test_faster_levels_stay_off_slower_charts(self):
        self.assertNotIn(103.1, {round(x["price"], 1) for x in K.shared_levels(self.POOL, "1w")})
        self.assertIn(103.1, {round(x["price"], 1) for x in K.shared_levels(self.POOL, "1d")})

    def test_a_lone_swing_counts_only_from_a_slower_timeframe(self):
        levels = K.shared_levels(self.POOL, "1d")
        below, above = K.pick_levels(levels, 105.0, "1d")
        self.assertNotIn(108.0, [x["price"] for x in above])  # its own timeframe, one touch
        self.assertIn(103.1, [round(x["price"], 1) for x in below])
        self.assertIn(120.0, [x["price"] for x in above])

    def test_an_empty_side_falls_back_on_the_nearest_swing(self):
        below, above = K.pick_levels([{"price": 90.0, "touches": 1, "last": "2026-01-01", "frame": "1M"}], 100.0, "1M")
        self.assertEqual([x["price"] for x in below], [90.0])
        self.assertEqual(above, [])

    def test_one_violent_bar_does_not_change_the_typical_range(self):
        calm = ohlc([101] * 60, [99] * 60)
        wild = calm.copy()
        wild.iloc[-1, wild.columns.get_loc("high")] = 160
        self.assertAlmostEqual(K.typical_atr(calm, "1d"), K.typical_atr(wild, "1d"))

    def test_a_small_swing_is_noise(self):
        d = ohlc([100, 101, 102, 103, 102, 101, 100], [99, 100, 101, 102, 101, 100, 99])
        self.assertEqual(len(K.swings(d, 3, 1)), 3 - 2)
        self.assertEqual(K.swings(d, 3, 50), [])


class TestModelWorkings(unittest.TestCase):
    def setUp(self):
        self.returns = np.random.default_rng(3).normal(0, .02, 900)

    def test_the_detail_is_the_forecast(self):
        d = M.har_detail(self.returns, 30, 365)
        self.assertEqual(d["forecast"], M.har_forecast(self.returns, 30, 365))
        self.assertAlmostEqual(np.exp(d["intercept"] + d["b_week"] * np.log(d["vol_week"]) + d["b_month"] * np.log(d["vol_month"]) + d["b_quarter"] * np.log(d["vol_quarter"])), d["forecast"])

    def test_the_worked_example_reproduces_the_table(self):
        contract = {"expiry": "2026-12-25", "strike": 110.0, "type": "call", "is_call": True, "delta": .3, "fair_iv": .5, "curve_iv": .45, "fair": float(M.black76(100.0, 110.0, 50 / 365, .5, True, 1.0))}
        exp = {"expiry": "2026-12-25", "days": 50.0, "forward": 100.0, "atm": .4, "forecast": .44, "discount": 1.0, "svi": [.01, .1, -.3, 0.0, .1]}
        e = L.worked_example([contract], [], [contract], [exp], self.returns, 365, .04)["example"]
        rebuilt = float(M.black76(e["forward"], e["strike"], e["years"], e["fair_iv"], True, e["discount"]))
        self.assertAlmostEqual(rebuilt, e["fair"])
        self.assertAlmostEqual(e["forward"] * norm.cdf(e["d1"]) - e["strike"] * norm.cdf(e["d2"]), e["fair"])
        self.assertAlmostEqual(e["scale"], 1.1)

    def test_no_usable_contract_means_no_example(self):
        self.assertIsNone(L.worked_example([], [], [], [{"expiry": "2026-12-25", "days": 50.0}], None, 365, .04)["example"])


if __name__ == "__main__":
    unittest.main()
