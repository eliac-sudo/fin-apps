import json, os, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from bzd import alerts as A
from bzd import technicals as K


def bars(close):
    i = pd.date_range("2020-01-01", periods=len(close), freq="D", tz="UTC")
    c = pd.Series(close, index=i, dtype=float)
    return pd.DataFrame({"open": c.shift().fillna(c), "high": c * 1.01, "low": c * .99, "close": c})


class TestLevels(unittest.TestCase):
    def test_repeated_swings_make_one_level_and_single_swings_none(self):
        wave = [100, 104, 108, 112, 108, 104, 100, 96, 92, 96, 100, 104, 108, 112.2, 108, 104, 100, 96, 92.1, 96, 100, 104, 108]
        lv = K.find_levels(bars(wave), 3, 1.5)
        self.assertEqual(len(lv), 2)
        self.assertEqual([x["touches"] for x in lv], [2, 2])
        self.assertEqual(K.find_levels(bars(list(range(100, 130))), 3, 1), [])

    def test_a_swing_needs_bars_on_both_sides(self):
        self.assertEqual(K.swings(bars([100, 101, 102, 103, 104]), 3), [])

    def test_later_bars_cannot_change_old_levels_without_new_swings(self):
        wave = [100, 104, 108, 112, 108, 104, 100, 96, 92, 96, 100, 104, 108, 112.2, 108, 104, 100, 96, 92.1, 96, 100, 104]
        self.assertEqual(K.find_levels(bars(wave), 3, 1.5)[0]["price"], K.find_levels(bars(wave + [108]), 3, 1.5)[0]["price"])


class TestReset(unittest.TestCase):
    def rising_then_dip(self, dip=12):
        up = list(np.linspace(100, 220, 100))
        return bars(up + [up[-1] * (.97 ** k) for k in range(1, dip)])

    def run_until_fired(self, d, tf, fired):
        out = []
        for n in range(90, len(d) + 1):
            r = K.find_reset("BTC", tf, d.close.iloc[:n], fired)
            if r:
                out.append(r)
        return out

    def test_oversold_in_a_rise_fires_once(self):
        found = self.run_until_fired(self.rising_then_dip(), "1d", {})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["trend"], "rialzo")
        self.assertIn("ipervenduto", found[0]["kind"])
        self.assertLess(found[0]["rsi"], 30)

    def test_overbought_in_a_fall_fires_too(self):
        down = list(np.linspace(220, 100, 100))
        d = bars(down + [down[-1] * (1.03 ** k) for k in range(1, 12)])
        found = self.run_until_fired(d, "1d", {})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["trend"], "ribasso")

    def test_oversold_without_a_rising_trend_is_silent(self):
        flat = [100 + (i % 2) for i in range(100)]
        d = bars(flat + [100 * (.97 ** k) for k in range(1, 12)])
        self.assertEqual(self.run_until_fired(d, "1d", {}), [])

    def test_rearms_only_after_rsi_is_back_at_50(self):
        fired, d = {"BTC|1d|up": 1.0}, self.rising_then_dip()
        below_50 = [n for n in range(90, len(d) + 1) if K.I.rsi(d.close.iloc[:n]).iloc[-1] < 50]
        self.assertEqual([r for n in below_50 if (r := K.find_reset("BTC", "1d", d.close.iloc[:n], fired))], [])
        K.find_reset("BTC", "1d", bars(list(np.linspace(100, 220, 100))).close, fired)
        self.assertNotIn("BTC|1d|up", fired)

    def test_4h_never_goes_to_the_bot(self):
        self.assertNotIn("4h", K.RESET_RSI)
        self.assertIsNone(K.find_reset("BTC", "4h", self.rising_then_dip().close, {}))

    def test_message_has_no_trade_instructions(self):
        t = K.format_resets([{"market": "BTC", "tf": "1w", "rsi": 38.0, "threshold": 40, "trend": "rialzo", "kind": "ipervenduto in un trend al rialzo", "price": 80000.0, "bar": "x"}], datetime(2026, 11, 5, tzinfo=timezone.utc))
        self.assertIn("RESET", t)
        self.assertIn("settimanale", t)
        self.assertIn("non è testato", t)
        for word in ("entra", "stop", "compra", "obiettivo"):
            self.assertNotIn(word, t.lower())


class TestContext(unittest.TestCase):
    def test_context_has_trend_and_levels(self):
        frame = {"price": 100.0, "trend": "rialzo", "rsi": 40.0, "supports": [{"price": 90.0}], "resistances": [{"price": 110.0}]}
        with mock.patch.object(K, "analyze", return_value={"1d": frame, "1w": frame}):
            t = K.context_line("BTC")
        for word in ("settimanale in rialzo", "RSI giornaliero 40", "supporto 90.0000 (-10.0%)", "resistenza 110.00 (+10.0%)"):
            self.assertIn(word, t)

    def test_no_data_means_no_context(self):
        with mock.patch.object(K, "analyze", return_value={}):
            self.assertEqual(K.context_line("X"), "")
        with mock.patch.object(K, "analyze", side_effect=ValueError):
            self.assertEqual(K.context_line("X"), "")

    def test_reset_message_says_which_way_it_leans(self):
        with mock.patch.object(K, "context_line", return_value=""):
            t = K.format_resets([{"market": "BTC", "tf": "1w", "rsi": 38.0, "threshold": 40, "trend": "rialzo", "kind": "x", "price": 1.0, "bar": "x"}, {"market": "ETH", "tf": "1d", "rsi": 72.0, "threshold": 70, "trend": "ribasso", "kind": "x", "price": 1.0, "bar": "x"}], datetime(2026, 11, 5, tzinfo=timezone.utc))
        self.assertIn("potenziale long", t)
        self.assertIn("potenziale short", t)


class TestFrames(unittest.TestCase):
    def test_metrics_report_each_indicator(self):
        f = K.read_frame(bars(list(np.linspace(100, 300, 300))), "1d")
        self.assertAlmostEqual(f["metrics"]["rsi"], f["rsi"])
        self.assertGreater(f["metrics"]["dist50"], 0)

    def test_read_frame_on_known_trend(self):
        f = K.read_frame(bars(list(np.linspace(100, 300, 300))), "1d")
        self.assertEqual((f["trend"], f["slow_trend"]), ("rialzo", "rialzo"))
        self.assertGreater(f["rsi"], 70)
        self.assertEqual(len(f["chart"]["c"]), K.CHART_BARS)
        self.assertTrue(all(x["price"] < f["price"] for x in f["supports"]))

    def test_weekly_bars_cover_the_week(self):
        d = bars([float(x) for x in range(1, 29)])
        w = K.resample(d, "W-SUN")
        self.assertEqual(w.high.max(), d.high.max())
        self.assertEqual(w.close.iloc[-1], d.close.iloc[-1])
        self.assertLessEqual(len(w), 6)


class TestDelivery(unittest.TestCase):
    def test_logged_and_queued_as_one_message(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"BZD_DATA": tmp}):
            r = {"market": "BTC", "tf": "1w", "rsi": 38.0, "threshold": 40, "trend": "rialzo", "kind": "ipervenduto in un trend al rialzo", "price": 8e4, "bar": "x"}
            st = {"pending": []}
            with mock.patch.object(A.K, "check_resets", return_value=[r, {**r, "market": "ETH"}]):
                A.check_resets(st, True)
            self.assertEqual(len(st["pending"]), 1)
            self.assertEqual(len((Path(tmp) / "alerts" / "resets.jsonl").read_text().splitlines()), 2)
