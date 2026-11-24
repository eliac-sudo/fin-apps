import os, tempfile, unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from bzd import flows as F, history as H


def days(n, start="2024-01-01"):
    return pd.date_range(start, periods=n, tz="UTC")


class TestBeyond(unittest.TestCase):
    def setUp(self):
        r = np.random.default_rng(3)
        self.move = pd.Series(r.normal(size=600), index=days(600))
        self.noise = pd.Series(r.normal(size=600) * .1, index=days(600))

    def test_a_pure_reflex_is_not_beyond_the_move(self):
        flow = -self.move + self.noise
        flow.iloc[-1], self.move.iloc[-1] = 3.0, -3.0  # a big purchase, entirely what a big fall predicts
        self.assertLess(abs(F.beyond_move(flow, self.move).iloc[-1]), 90)
        self.assertGreater(F.pressure_of(flow).iloc[-1], 95)

    def test_buying_a_rise_against_the_reflex_is_beyond(self):
        flow = -self.move + self.noise
        flow.iloc[-1], self.move.iloc[-1] = 1.0, 1.0
        self.assertGreater(F.beyond_move(flow, self.move).iloc[-1], 95)

    def test_later_data_cannot_change_the_past(self):
        flow = -self.move + self.noise
        a, b = F.beyond_move(flow.iloc[:500], self.move.iloc[:500]).dropna(), F.beyond_move(flow, self.move).iloc[:500].dropna()
        self.assertTrue(np.allclose(a.values, b.values))


class TestPressure(unittest.TestCase):
    def test_later_data_cannot_change_the_past(self):
        s = pd.Series(np.random.default_rng(1).normal(size=400), index=days(400))
        self.assertTrue(F.pressure_of(s.iloc[:300]).dropna().equals(F.pressure_of(s).iloc[:300].dropna()))

    def test_a_record_change_is_the_most_intense(self):
        s = pd.Series(np.random.default_rng(2).normal(size=200), index=days(200))
        s.iloc[-1], s.iloc[-2] = 50, -50
        p = F.pressure_of(s)
        self.assertEqual(p.iloc[-1], 100)
        self.assertLess(p.iloc[-2], -99)


def table(states, retail, big):
    n = len(states)
    return pd.DataFrame({"state": states, "retail": retail, "big": big, "close": np.arange(100.0, 100.0 + n)}, index=days(n))


class TestTables(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        env = mock.patch.dict(os.environ, {"BZD_DATA": self.dir.name})
        env.start()
        self.addCleanup(env.stop)

    def write(self, group, name, df):
        p = Path(self.dir.name) / "hist" / group
        p.mkdir(parents=True, exist_ok=True)
        df.to_csv(p / f"{name}.csv.gz", index=False, compression="gzip")

    def cot(self, name):
        rep = pd.date_range("2024-01-02", periods=3, freq="7D").strftime("%Y-%m-%d")
        self.write("positions", name, pd.DataFrame({"report_date": rep, "available": rep, "oi": 100, "small_long": [10, 20, 20], "small_short": 10, "big_long": [10, 10, 40], "big_short": [10, 10, 5]}))

    def frames(self):
        d = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=days(30))
        return mock.patch.object(F.K, "frames", return_value={"1d": d})

    def test_cot_flows_are_changes_as_a_share_of_open_interest(self):
        self.cot("ESF")
        with self.frames():
            x = F.cot_table("ES=F")
        self.assertEqual([round(v, 2) for v in x.retail_flow], [.1, 0])
        self.assertEqual([round(v, 2) for v in x.big_flow], [0, .35])
        self.assertEqual((round(x.big_long_change.iloc[-1], 2), round(x.big_short_change.iloc[-1], 2)), (.3, -.05))

    def test_a_report_says_what_the_price_did_since(self):
        self.cot("ESF")
        with self.frames():
            self.assertEqual(F.cot_table("ES=F").attrs["latest"]["close"], 1.0)

    def test_rows_before_the_funds_report_are_left_out(self):
        rep = pd.date_range("2024-01-02", periods=3, freq="7D").strftime("%Y-%m-%d")
        self.write("positions", "ESF", pd.DataFrame({"report_date": rep, "available": rep, "oi": 100, "small_long": [10, 20, 30], "small_short": 10, "big_long": [np.nan, 10, 20], "big_short": [np.nan, 5, 5]}))
        with self.frames():
            self.assertEqual(len(F.cot_table("ES=F")), 1)

    def test_pairs_quoted_the_other_way_flip_the_sign(self):
        self.cot("USDJPYX")
        with self.frames():
            x = F.cot_table("USDJPY=X")
        self.assertEqual([round(v, 2) for v in x.retail_flow], [-.1, 0])

    def test_cot_levels_are_net_shares_signed_for_the_pair(self):
        self.cot("ESF")
        self.cot("USDJPYX")
        with self.frames():
            es, jpy = F.cot_levels("ES=F"), F.cot_levels("USDJPY=X")
        self.assertEqual([round(v, 2) for v in es.retail], [0, .1, .1])
        self.assertEqual([round(v, 2) for v in es.big], [0, 0, .35])
        self.assertEqual([round(v, 2) for v in jpy.retail], [0, -.1, -.1])

    def test_a_market_without_data_is_none(self):
        with self.frames():
            self.assertIsNone(F.cot_table("ES=F"))
        self.assertIsNone(F.crypto_table("BTC", "9h"))


class TestLevels(unittest.TestCase):
    def test_percentile_uses_only_the_window_up_to_each_bar(self):
        s = pd.Series([1.0, 2, 3, 4, 0])
        p = F.rolling_pct(s, 5, 2)
        self.assertEqual(p.iloc[3], 100.0)
        self.assertEqual(p.iloc[4], 0.0)
        self.assertEqual(F.rolling_pct(s.iloc[:4], 5, 2).iloc[3], p.iloc[3])  # later data never moves an earlier value

    def test_words_and_sides(self):
        self.assertEqual([F.level_word(x) for x in (95, 75, 50, 20, 5)], ["molto long", "più long del solito", "nella norma", "più short del solito", "molto short"])
        self.assertEqual((F.side_of(80), F.side_of(50), F.side_of(20)), (1, 0, -1))


class TestDownload(unittest.TestCase):
    def test_the_refresh_never_starts_a_history_of_its_own(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"BZD_DATA": tmp}), mock.patch.object(H, "vision_day") as day, mock.patch.object(H, "get") as get:
            H.refresh_positions()
        day.assert_not_called()
        get.assert_not_called()

    def test_bars_keep_the_last_reading_as_a_long_share(self):
        t = pd.Series(["2026-11-01 03:55:00", "2026-11-01 00:00:00", "2026-11-01 04:00:00"])
        d = H.position_bars(t, pd.Series([3.0, 1.0, 1.0]), pd.Series([1.0, 1.0, 4.0]), pd.Series([10.0, 9.0, 0.0]))
        self.assertEqual(len(d), 2)
        self.assertEqual((d.retail_long[0], d.big_long[0], d.oi[0]), (.75, .5, 10.0))
        self.assertEqual(d.big_long[1], .8)
        self.assertTrue(np.isnan(d.oi[1]))

    def test_gaps_are_days_without_all_six_bars(self):
        whole = pd.date_range("2026-11-01", periods=6, freq="4h", tz="UTC").astype(str)
        old = pd.DataFrame({"t": list(whole) + ["2026-11-02 00:00:00+00:00"]})
        self.assertEqual(H.position_gaps(old, "2026-11-01", "2026-11-03"), ["2026-11-02", "2026-11-03"])
        self.assertEqual(H.position_gaps(None, "2026-11-01", "2026-11-02"), ["2026-11-01", "2026-11-02"])


if __name__ == "__main__":
    unittest.main()
