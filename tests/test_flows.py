import os, tempfile, unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from bzd import flows as F, history as H


def days(n, start="2024-01-01"):
    return pd.date_range(start, periods=n, tz="UTC")


class TestWords(unittest.TestCase):
    def test_a_group_acts_only_from_the_threshold(self):
        self.assertEqual([F.action(x) for x in (49.9, 50, -49.9, -50, float("nan"))], ["fermo", "compra", "fermo", "vende", None])

    def test_intensity_words(self):
        self.assertEqual([F.word(x) for x in (10, 50, 80, 95)], ["debole", "moderata", "forte", "estrema"])

    def test_the_sentence_names_who_acts(self):
        self.assertEqual(F.verdict("dip", "compra", "vende", "i grossi"), "Sul dip compra il retail, vendono i grossi.")
        self.assertEqual(F.verdict("top", "vende", "vende", "i fondi"), "Sul top vendono il retail e i fondi.")
        self.assertEqual(F.verdict("top", "fermo", "compra", "i grossi"), "Sul top comprano i grossi.")
        self.assertEqual(F.verdict("dip", "fermo", "fermo", "i grossi"), "Sul dip nessuno si muove più del solito.")
        self.assertIsNone(F.verdict(None, "compra", "vende", "i grossi"))


class TestHow(unittest.TestCase):
    def test_the_report_tells_opening_from_closing(self):
        self.assertEqual(F.how_of("compra", .03, -.01), "apre long")
        self.assertEqual(F.how_of("compra", .01, -.03), "chiude short")
        self.assertEqual(F.how_of("vende", .01, .03), "apre short")
        self.assertEqual(F.how_of("vende", -.03, .01), "chiude long")
        self.assertIsNone(F.how_of("fermo", .03, 0))

    def test_open_interest_gives_a_guess_only_when_clear(self):
        self.assertEqual(F.how_from_oi("compra", 2), "apre long")
        self.assertEqual(F.how_from_oi("compra", -2), "chiude short")
        self.assertEqual(F.how_from_oi("vende", 2), "apre short")
        self.assertEqual(F.how_from_oi("vende", -2), "chiude long")
        self.assertIsNone(F.how_from_oi("compra", .2))
        self.assertIsNone(F.how_from_oi("compra", None))


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


class TestEpisodes(unittest.TestCase):
    def test_a_short_pause_keeps_one_run_with_its_strongest_pressure(self):
        x = table(["dip", None, "dip", None, None, None, None, "top"], [60, 0, 90, 0, 0, 0, 0, -70], [-80, 0, -60, 0, 0, 0, 0, 10])
        e = F.episodes(x, "1d", "i grossi")
        self.assertEqual([(a["kind"], a["bars"]) for a in e], [("dip", 2), ("top", 1)])
        self.assertEqual((e[0]["retail"], e[0]["big"]), (90, -60))
        self.assertEqual(e[0]["verdict"], "Sul dip compra il retail, vendono i grossi.")
        self.assertEqual(e[1]["verdict"], "Sul top vende il retail.")

    def test_habit_counts_the_usual_action_at_extremes(self):
        h = F.habit(table(["dip", "dip", "top", None], [80, 10, -60, 90], [10, 70, 10, 0]))
        self.assertEqual(h["dip"], {"bars": 2, "retail": 50.0, "big": 50.0})
        self.assertEqual(h["top"], {"bars": 1, "retail": 100.0, "big": 0.0})

    def test_a_bar_without_extreme_has_no_verdict(self):
        x = table([None, None], [10, 60], [0, -60]).assign(retail_flow=[.01, .02], big_flow=[.0, -.02], score=[0.0, 10.0], oi_change=[1.0, np.nan], retail_beyond=[0.0, 70.0], big_beyond=[0.0, 0.0])
        now = F.frame_view(x, "1d", "i grossi")["now"]
        self.assertIsNone(now["state"])
        self.assertIsNone(now["verdict"])
        self.assertEqual(now["retail"]["action"], "compra")
        self.assertTrue(now["retail"]["beyond"])
        self.assertFalse(now["big"]["beyond"])
        self.assertIsNone(now["oi_change"])


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

    def test_a_market_without_data_is_none(self):
        with self.frames():
            self.assertIsNone(F.cot_table("ES=F"))
        self.assertIsNone(F.crypto_table("BTC", "9h"))


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
