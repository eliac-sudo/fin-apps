import unittest
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from bzd import indicators as I, thermo as Th

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def series(v):
    return pd.Series(np.array(v, float), index=pd.date_range("2020-01-01", periods=len(v), freq="D", tz="UTC"))


class TestIndicators(unittest.TestCase):
    def test_rsi_extremes_and_known_value(self):
        self.assertEqual(I.rsi(series(range(1, 40))).iloc[-1], 100)
        self.assertLess(I.rsi(series(range(40, 1, -1))).iloc[-1], 1)
        self.assertAlmostEqual(I.rsi(series([1, 2] * 30)).iloc[-1], 50, delta=5)

    def test_rolling_indicators_ignore_later_data(self):
        s = series(np.random.default_rng(1).normal(100, 1, 300))
        d = pd.DataFrame({"high": s + 1, "low": s - 1, "close": s, "volume": 10.0})
        for fn in (I.rsi, lambda x: I.sma_distance(x, 50), lambda x: I.past_percentile(x, 20)):
            a = fn(s)
            b = fn(s.iloc[:200])
            pd.testing.assert_series_equal(a.iloc[:200], b, check_freq=False)
        pd.testing.assert_series_equal(I.vwap_distance(d, 20).iloc[:200], I.vwap_distance(d.iloc[:200], 20), check_freq=False)

    def test_percentile_uses_only_earlier_values(self):
        p = I.past_percentile(series(list(range(100)) + [1000, -5]), 100)
        self.assertEqual(p.iloc[100], 100)
        self.assertEqual(p.iloc[101], 0)
        self.assertTrue(np.isnan(p.iloc[50]))

    def test_black_scholes_known_values(self):
        d, g = I.bs_greeks(100, 100, 1, .2, True)
        self.assertAlmostEqual(d, .5398, places=3)
        self.assertAlmostEqual(g, .01985, places=4)
        p, g2 = I.bs_greeks(100, 100, 1, .2, False)
        self.assertAlmostEqual(d - p, 1, places=9)  # put-call parity on delta
        self.assertEqual(g, g2)
        self.assertIsNone(I.bs_greeks(100, 100, -1, .2, True))
        self.assertIsNone(I.bs_greeks(100, 100, 1, 0, True))

    def chain(self):
        e30 = datetime(2026, 12, 4, tzinfo=timezone.utc)
        rows = []
        for k in range(70, 131, 5):
            rows.append({"strike": k, "expiry": e30, "is_call": True, "iv": .2, "oi": 10, "volume": 1})
            rows.append({"strike": k, "expiry": e30, "is_call": False, "iv": .3, "oi": 20, "volume": 1})
        return rows

    def test_metrics_on_a_chain_with_known_skew(self):
        m = I.option_metrics(self.chain(), 100, NOW, 100)
        self.assertAlmostEqual(m["skew_25d"], .10)
        self.assertEqual(m["put_call_oi"], 2)
        self.assertLess(m["gex_call_long"], 0)  # more put gamma than call gamma
        self.assertLess(m["gex_all_short"], m["gex_call_long"])

    def test_inverted_term_structure_is_flagged(self):
        rows = self.chain()
        e7 = datetime(2026, 11, 11, tzinfo=timezone.utc)
        rows.append({"strike": 100, "expiry": e7, "is_call": True, "iv": .6, "oi": 1, "volume": 1})
        self.assertTrue(I.option_metrics(rows, 100, NOW, 100)["term_inverted"])

    def test_small_short_term_gap_is_not_an_inversion(self):
        rows = self.chain()
        rows.append({"strike": 100, "expiry": datetime(2026, 11, 11, tzinfo=timezone.utc), "is_call": True, "iv": .205, "oi": 1, "volume": 1})
        self.assertFalse(I.option_metrics(rows, 100, NOW, 100)["term_inverted"])

    def test_nonstandard_roots_are_excluded(self):
        c = {"data": {"symbol": "SPY", "current_price": 700, "options": [{"option": "B1SPY261106C00740000", "iv": .18, "open_interest": 5, "volume": 1}, {"option": "SPY261120P00700000", "iv": .2, "open_interest": 7, "volume": 1}]}}
        self.assertEqual(len(I.parse_cboe(c)[0]), 1)
        i = {"data": {"symbol": "_SPX", "current_price": 7000, "options": [{"option": "SPX261120C00400000", "iv": .2, "open_interest": 1, "volume": 0}]}}
        self.assertEqual(len(I.parse_cboe(i)[0]), 1)

    def test_contract_still_open_at_snapshot_time_counts(self):
        expiry_today = {"strike": 100, "expiry": datetime(2026, 11, 4, 20, tzinfo=timezone.utc), "is_call": True, "iv": .2, "oi": 10, "volume": 1}
        self.assertIsNotNone(I.option_metrics([expiry_today], 100, datetime(2026, 11, 4, 17, tzinfo=timezone.utc), 100))
        self.assertIsNone(I.option_metrics([expiry_today], 100, datetime(2026, 11, 4, 21, tzinfo=timezone.utc), 100))

    def test_parsers_read_real_symbol_shapes(self):
        c = {"data": {"current_price": 700, "options": [{"option": "B1SPY261106C00740000", "iv": .18, "open_interest": 5, "volume": 1}, {"option": "SPY261120P00700000", "iv": .2, "open_interest": 7, "volume": 1}]}}
        rows, spot, mult = I.parse_cboe(c)
        self.assertEqual((rows[0]["strike"], rows[0]["is_call"], rows[1]["strike"], rows[1]["is_call"], spot, mult), (740, True, 700, False, 700, 100))
        d = {"result": [{"instrument_name": "BTC-13NOV26-83000-P", "mark_iv": 40, "open_interest": 3, "volume": 1, "underlying_price": 80000}]}
        rows, spot, mult = I.parse_deribit(d)
        self.assertEqual((rows[0]["strike"], rows[0]["is_call"], rows[0]["iv"], spot, mult), (83000, False, .4, 80000, 1))
        self.assertEqual(rows[0]["expiry"].month, 11)


class TestThermo(unittest.TestCase):
    def test_heat_averages_available_parts_only(self):
        self.assertEqual(Th.heat_from({"a": 80, "b": 40, "c": None, "d": float("nan")})[0], 60)
        self.assertEqual(Th.heat_from({"a": None}), (None, {}))

    def test_bands(self):
        self.assertIn("molto caldo", Th.band(95))
        self.assertIn("neutro", Th.band(50))
        self.assertIn("molto freddo", Th.band(3))

    def test_mood_counts_only_topic_and_period(self):
        items = [{"time": "2026-11-03T20:00:00+00:00", "text": "bitcoin crash panic"}, {"time": "2026-11-03T21:00:00+00:00", "text": "bitcoin to the moon"},
                 {"time": "2026-11-03T22:00:00+00:00", "text": "cake recipe"}, {"time": "2026-10-01T00:00:00+00:00", "text": "bitcoin crash"}]
        self.assertEqual(Th.mood(items, "crypto", NOW), {"texts": 2, "fear": 1, "greed": 1})

    def test_money_format(self):
        self.assertEqual(Th.fmt_money(2.5e9), "+2.5 mld $")
        self.assertEqual(Th.fmt_money(-3e6), "−3 mln $")


if __name__ == "__main__":
    unittest.main()
