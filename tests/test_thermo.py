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

    def test_options_without_a_bid_do_not_count_for_skew(self):
        rows = [{**r, "bid": 0.0 if not r["is_call"] else 1.0} for r in self.chain()]
        self.assertIsNone(I.option_metrics(rows, 100, NOW, 100)["skew_25d"])
        rows = [{**r, "bid": 1.0} for r in self.chain()]
        self.assertAlmostEqual(I.option_metrics(rows, 100, NOW, 100)["skew_25d"], .10)

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
        self.assertIn("molto tirato in alto", Th.band(95))
        self.assertIn("in equilibrio", Th.band(50))
        self.assertIn("molto tirato in basso", Th.band(3))

    def rows(self):
        return [{"market": "BTC", "class": "crypto", "heat": 90.0, "heat_change_7d": 12.0, "parts": {"funding": 95, "slancio": 85, "oi": 30}},
                {"market": "ETH", "class": "crypto", "heat": 70.0, "heat_change_7d": 8.0, "parts": {"funding": 75, "slancio": 65, "oi": 20}},
                {"market": "ES=F", "class": "equities", "heat": 30.0, "heat_change_7d": None, "parts": {"calma": 10}}]

    def test_digest_says_what_is_going_on_in_words(self):
        from unittest import mock
        with mock.patch.object(Th, "all_readings", return_value=self.rows()), mock.patch.object(Th, "fear_greed", return_value={"value": 34, "date": "x"}), \
                mock.patch.object(Th, "market_position", return_value=None):
            t, _ = Th.build_digest(NOW)
        self.assertNotIn("GEX", t)
        self.assertIn("0 tirato in basso", t)
        self.assertIn("Tirati in alto: Cripto. Tirati in basso: Azioni.", t)
        self.assertIn("Cripto (+10)", t)
        self.assertIn("+10 in 7 giorni", t)
        self.assertIn("Più in alto BTC 90 · più in basso ETH 70", t)
        self.assertIn("Spinge: funding, slancio. Frena: leva (OI).", t)
        self.assertIn("Frena: volatilità alta.", t)
        self.assertIn("S&amp;P 500 30", t)

    def test_quiet_markets_say_so(self):
        s = {"crypto": {"band": Th.band(50), "change_7d": 1.0}}
        self.assertEqual(Th.overview(s), "Nessun gruppo tirato in alto. Nessun gruppo tirato in basso.")

    def test_reading_compares_with_a_week_ago(self):
        import pandas as pd
        up, c = pd.Series([40.0] * 6 + [60.0]), pd.Series([1.0] * 7)
        r = Th.reading("X", "fx", c, up, {"slancio": up}, pd.Timestamp("2026-11-04"), 5, {})
        self.assertEqual(r["heat_change_7d"], 20)


class TestOptionsReport(unittest.TestCase):
    def test_levels(self):
        from bzd import options_report as O
        self.assertEqual((O.level(5), O.level(50), O.level(95)), ("molto bassa", "media", "molto alta"))

    def test_report_has_no_gex_and_says_what_it_is(self):
        from unittest import mock
        from bzd import options_report as O
        block = {"label": "VIX", "value": 20.8, "pct": 71.0, "date": NOW}
        chain = {"skew_25d": .048, "iv_7d": .13, "iv_30d": .14, "term_inverted": False, "gex_call_long": 1e9}
        with mock.patch.object(O, "level_line", return_value=block), mock.patch.object(O, "iv_line", return_value=None), mock.patch.object(O.I, "latest_options", return_value=chain), mock.patch.object(O, "index_series", return_value=None):
            t = O.build_report(NOW)
        self.assertIn("<b>alta</b>", t)
        self.assertIn("put più care", t)
        self.assertIn("Più tesa", t)
        self.assertNotIn("GEX", t)
        self.assertIn("Testato 2008", t)

    def test_term_flags_near_term_fear(self):
        from unittest import mock
        from bzd import options_report as O
        a, b = series([25.0]), series([20.0])
        with mock.patch.object(O, "index_series", side_effect=[a, b]):
            self.assertIn("paura immediata", O.term_line({"short": "VIX9D", "long": "VIX3M"}, None))


if __name__ == "__main__":
    unittest.main()


class TestCheapOrDear(unittest.TestCase):
    def test_price_position(self):
        import pandas as pd
        from bzd import thermo as Z
        up = pd.Series([float(x) for x in range(1, 101)])
        p = Z.price_position(up, 100)
        self.assertEqual(p["label"], "molto caro")
        self.assertEqual(p["from_high"], 0)
        down = pd.Series([float(x) for x in range(100, 0, -1)])
        self.assertEqual(Z.price_position(down, 100)["label"], "molto economico")
        self.assertIsNone(Z.price_position(up.head(10), 100))
        self.assertIn("rispetto all'ultimo anno", Z.position_text(p))

    def test_options_cost_compares_implied_with_forecast(self):
        import numpy as np, pandas as pd
        from unittest import mock
        from bzd import options_report as R
        s = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, .01, 60))))
        b = {"underlying": ("tradfi", "X", 252)}
        with mock.patch.object(R, "index_series", return_value=s), mock.patch.object(R, "forecast_vol", return_value=.2):
            self.assertEqual(R.price_of_options(b, {"iv_30d": .4})["label"], "care")
            self.assertEqual(R.price_of_options(b, {"iv_30d": .1})["label"], "economiche")
            self.assertEqual(R.price_of_options(b, {"iv_30d": .2})["label"], "nella norma")
        self.assertIsNone(R.price_of_options({}, {"iv_30d": .2}))
        self.assertIsNone(R.price_of_options(b, None))


class TestCryptoDaily(unittest.TestCase):
    def test_keeps_the_last_bar_of_each_day(self):
        import pandas as pd
        from unittest import mock
        from bzd import events as E
        bars = pd.DataFrame({"t": ["2026-11-03 00:00:00+00:00", "2026-11-03 20:00:00+00:00", "2026-11-04 00:00:00+00:00", "2026-11-04 16:00:00+00:00"], "close": [1.0, 2.0, 3.0, 4.0]})
        with mock.patch.object(E, "read", return_value=bars):
            self.assertEqual(E.crypto_daily("BTC").close.tolist(), [2, 4])
