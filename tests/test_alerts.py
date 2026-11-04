import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from bzd import alerts as A, history as H, setups as S

NOW = pd.Timestamp("2026-11-04 12:00", tz="UTC")


def alert(**kw):
    base = {"key": "BTC|panic|t", "class": "crypto", "market": "BTC", "setup": "panic", "bar": "4h", "trigger": "2026-11-04T08:00:00+00:00",
            "z": -3.4, "score": 2, "max_score": 3, "met": ["funding_nonpositive", "oi_flush"], "not_met": [], "unknown": ["volume_spike_fading"],
            "entry_after_bars": 2, "plan": {"price": 100.0, "stop": 95.0, "target_3r": 115.0, "risk_pct": .05}}
    return {**base, **kw}


class TestFreshness(unittest.TestCase):
    def test_only_fresh_triggers_after_cool_off(self):
        idx = pd.date_range("2026-11-01", periods=21, freq="4h", tz="UTC")
        m = pd.Series(False, index=idx)
        m.iloc[[0, 18, 19]] = True  # 19 falls inside the cool-off of 18
        got = A.recent_triggers(m, 1, "4h", idx[19] + pd.Timedelta(hours=2))
        self.assertEqual(got, [idx[18]])

    def test_old_trigger_after_a_pause_is_not_alerted(self):
        idx = pd.date_range("2026-10-01", periods=5, freq="D", tz="UTC")
        m = pd.Series([True, False, False, False, False], index=idx)
        self.assertEqual(A.recent_triggers(m, 3, "1d", NOW), [])

    def test_crypto_refresh_runs_once_per_closed_bar(self):
        bar = 4 * 3600
        close = 1000 * bar
        self.assertFalse(A.crypto_due({"last_crypto": close}, close + 60))  # bar just closed, still waiting
        self.assertFalse(A.crypto_due({"last_crypto": close - bar + 200}, close + 60))
        self.assertTrue(A.crypto_due({"last_crypto": close - bar + 200}, close + 200))
        self.assertFalse(A.crypto_due({"last_crypto": close + 200}, close + 300))


class TestLive(unittest.TestCase):
    def test_open_binance_bar_is_dropped(self):
        rows = [[0, 1, 1, 1, 1, 0, 999, 0], [1000, 1, 1, 1, 1, 0, 1999, 0]]
        self.assertEqual(len(H.closed_klines(rows, 1500)), 1)

    def test_merge_keeps_newest_row_and_order(self):
        old = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "close": [1., 2.]})
        new = pd.DataFrame({"date": ["2026-01-02", "2026-01-03"], "close": [9., 3.]})
        got = H.merge_tail(old, new, "date")
        self.assertEqual(got.close.tolist(), [1., 9., 3.])

    def test_merge_handles_mixed_timestamp_formats(self):
        old = pd.DataFrame({"t": ["2026-11-04 08:00:00+00:00", "2026-11-04 16:00:00.001+00:00"], "x": [1, 2]})
        new = pd.DataFrame({"t": H.to_utc(pd.Series([1793808000000, 1793836800001])).astype(str), "x": [3, 4]})
        got = H.merge_tail(old, new, "t")
        self.assertTrue(got.t.is_monotonic_increasing)
        self.assertEqual(got.t.nunique(), len(got))

    def test_stored_merge_can_be_read_back(self):
        old = pd.DataFrame({"t": ["2026-11-04 08:00:00+00:00"], "x": [1]})
        new = pd.DataFrame({"t": ["2026-11-04 16:00:00.001+00:00"], "x": [2]})
        with tempfile.TemporaryDirectory() as r:
            p = Path(r) / "x.csv"
            H.merge_tail(old, new, "t").to_csv(p, index=False)
            self.assertEqual(len(pd.to_datetime(pd.read_csv(p).t, utc=True, format="ISO8601")), 2)


class TestMessages(unittest.TestCase):
    def test_message_is_labelled_and_shows_levels(self):
        with mock.patch.object(A, "calibration_note", return_value=None):
            t = A.format_group([alert()])
        self.assertIn("NON VALIDATO", t)
        self.assertIn("PANICO", t)
        self.assertIn("stop 95.0000", t)
        self.assertIn("dato non ancora noto", t)

    def test_wide_stop_gets_a_warning(self):
        a = alert(plan={"price": 100., "stop": 80., "target_3r": 160., "risk_pct": .2})
        self.assertIn("liquidazione", A.format_item(a))

    def test_overheating_says_reduce_not_short_and_gives_no_entry_levels(self):
        with mock.patch.object(A, "calibration_note", return_value=None):
            t = A.format_group([alert(setup="overheating", entry_after_bars=1)])
        self.assertIn("Non è un segnale di short", t)
        self.assertNotIn("obiettivo 3R", t)

    def test_market_not_on_hyperliquid_is_marked(self):
        self.assertIn("solo contesto", A.format_item(alert(market="ZC=F", **{"class": "commodities"})))
        self.assertIn("xyz:GOLD", A.format_item(alert(market="GC=F", **{"class": "commodities"})))

    def test_split_respects_the_limit_and_loses_nothing(self):
        text = "\n".join(f"riga {i} " + "x" * 50 for i in range(300))
        parts = A.split_message(text, 500)
        self.assertTrue(all(len(p) <= 500 for p in parts))
        self.assertEqual("\n".join(parts), text)
        self.assertTrue(all(len(p) <= 100 for p in A.split_message("y" * 250, 100)))


class TestDelivery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def empty(self):
        return {"seen": [], "pending": [], "last_crypto": 0, "last_daily": 0, "last_cot": 0}

    def test_every_alert_is_logged_but_low_scores_are_not_sent(self):
        st = self.empty()
        with mock.patch.object(A, "calibration_note", return_value=None):
            A.enqueue([alert(), alert(key="k2", market="ETH", score=0, unknown=[])], st, True)
        rows = [json.loads(x) for x in (Path(self.tmp.name) / "alerts" / "log.jsonl").read_text().splitlines()]
        self.assertEqual([r["queued_for_telegram"] for r in rows], [True, False])
        self.assertEqual(len(st["pending"]), 1)
        self.assertNotIn("ETH", st["pending"][0])
        self.assertEqual(st["seen"], ["BTC|panic|t", "k2"])

    def test_unknown_condition_can_keep_an_alert_alive(self):
        self.assertTrue(A.worth_sending(alert(score=0)))
        self.assertFalse(A.worth_sending(alert(score=0, unknown=[])))

    def test_same_move_on_many_coins_is_one_message(self):
        st = self.empty()
        with mock.patch.object(A, "calibration_note", return_value=None):
            A.enqueue([alert(), alert(key="k2", market="ETH"), alert(key="k3", market="SOL")], st, True)
        self.assertEqual(len(st["pending"]), 1)

    def test_nothing_piles_up_without_a_bot(self):
        st = self.empty()
        A.enqueue([alert()], st, False)
        self.assertEqual(st["pending"], [])
        self.assertEqual(st["seen"], ["BTC|panic|t"])

    def test_sending_needs_the_explicit_switch(self):
        creds = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1"}
        with mock.patch.dict(os.environ, creds):
            os.environ.pop("BZD_ALERTS_TELEGRAM", None)
            self.assertFalse(A.sending_enabled())
            os.environ["BZD_ALERTS_TELEGRAM"] = "on"
            self.assertTrue(A.sending_enabled())
            del os.environ["BZD_ALERTS_TELEGRAM"]

    def test_failed_send_keeps_message_and_order(self):
        st = {**self.empty(), "pending": ["a", "b", "c"]}
        sent = []

        def send(t):
            if t == "b":
                raise RuntimeError("down")
            sent.append(t)

        self.assertFalse(A.flush(st, send, log=lambda m: None))
        self.assertEqual(sent, ["a"])
        self.assertEqual(st["pending"], ["b", "c"])

    def test_token_never_appears_in_errors(self):
        secret = "123:SECRET"
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": secret}):
            with mock.patch("urllib.request.urlopen", side_effect=A.urllib.error.HTTPError(f"https://x/bot{secret}/m", 401, "no", {}, None)):
                with self.assertRaises(RuntimeError) as c:
                    A.telegram_call("sendMessage", {})
        self.assertNotIn(secret, str(c.exception))

    def test_module_never_touches_the_exchange_endpoint(self):
        src = Path(A.__file__).read_text()
        self.assertNotIn("/exchange", src)
        self.assertNotIn("hyperliquid.xyz", src)


class TestPlan(unittest.TestCase):
    def test_levels_use_only_data_up_to_the_trigger(self):
        idx = pd.date_range("2026-01-01", periods=30, freq="D", tz="UTC")
        d = pd.DataFrame({"open": 100., "high": 101., "low": 99., "close": 100.}, index=idx)
        rules = {"low_lookback_bars": 3, "atr_below_low": .5, "min_atr_distance": .5}
        a = A.level_plan(d.iloc[:20], rules)
        d2 = d.copy()
        d2.iloc[20:] *= 5
        self.assertEqual(a, A.level_plan(d2.iloc[:20], rules))
        self.assertAlmostEqual(a["stop"], 98.0)
        self.assertAlmostEqual(a["target_3r"], 106.0)


if __name__ == "__main__":
    unittest.main()
