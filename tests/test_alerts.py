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
    def test_message_gives_insight_and_no_trade_instructions(self):
        pos = {"pct": 8, "label": "molto economico", "from_high": -40.0, "from_low": 3.0}
        for setup in ("panic", "squeeze", "overheating"):
            with mock.patch.object(A, "market_position", return_value=pos):
                t = A.format_group([alert(setup=setup)])
            self.assertIn("molto economico", t)
            self.assertIn("Test", t)
            self.assertIn("Non è consulenza", t)
            self.assertIn("Non ancora noto", t)
            for word in ("95.0000", "115.0000", "stop", "Ingresso", "/piano", "3R", "valuta di ridurla"):
                self.assertNotIn(word, t.lower() if word == "stop" else t)

    def test_alert_says_which_way_it_leans_and_how_far_the_test_backs_it(self):
        self.assertIn("Potenziale long", A.format_group([alert()]))
        self.assertIn("presa di profitto", A.format_group([alert(setup="overheating")]))
        self.assertIn("non lo confermano", A.bias_line("commodities", "panic"))
        self.assertIn("supporto debole", A.bias_line("crypto", "panic"))
        self.assertIn("in salita il 46%", A.history_line("commodities", "panic"))
        self.assertIn("5 sedute", A.history_line("commodities", "panic"))
        self.assertIn("24 ore", A.history_line("crypto", "panic"))

    def test_context_failure_never_loses_an_alert(self):
        with mock.patch.object(A.K, "analyze", side_effect=ValueError):
            self.assertIn("PANICO", A.format_group([alert()]))

    def test_position_failure_never_loses_an_alert(self):
        with mock.patch.object(A, "market_position", side_effect=ValueError):
            self.assertIn("PANICO", A.format_group([alert()]))

    def test_plan_is_still_logged_for_paper_tracking(self):
        self.assertIn("plan", alert())

    def test_split_respects_the_limit_and_loses_nothing(self):
        text = "\n".join(f"riga {i} " + "x" * 50 for i in range(300))
        parts = A.split_message(text, 500)
        self.assertTrue(all(len(p) <= 500 for p in parts))
        self.assertEqual("\n".join(parts), text)
        self.assertTrue(all(len(p) <= 100 for p in A.split_message("y" * 250, 100)))


class TestFreshness2(unittest.TestCase):
    def frame(self, closes):
        idx = pd.date_range("2026-11-01", periods=len(closes), freq="D", tz="UTC")
        return pd.DataFrame({"close": closes}, index=idx)

    def test_price_below_stop_breaks_the_plan(self):
        d = self.frame([100., 96., 88.])
        plan = {"price": 96., "stop": 92., "target_3r": 110., "risk_pct": .04}
        with mock.patch.object(A, "hl_mark", return_value=None):
            f = A.freshness(d, d.index[1], plan, "CL=F", NOW)
        self.assertTrue(f["plan_broken"])
        self.assertEqual(f["bars_since_trigger"], 1)
        self.assertAlmostEqual(f["move_since_trigger_pct"], -8.33)

    def test_crypto_uses_the_hyperliquid_mark(self):
        d = self.frame([100., 96.])
        plan = {"price": 96., "stop": 92., "target_3r": 110., "risk_pct": .04}
        with mock.patch.object(A, "hl_mark", return_value=90.):
            self.assertTrue(A.freshness(d, d.index[1], plan, "BTC", NOW)["plan_broken"])

    def test_other_markets_show_the_mark_but_do_not_compare_across_basis(self):
        d = self.frame([100., 96.])
        plan = {"price": 96., "stop": 92., "target_3r": 110., "risk_pct": .04}
        with mock.patch.object(A, "hl_mark", return_value=90.):
            f = A.freshness(d, d.index[1], plan, "CL=F", NOW)
        self.assertFalse(f["plan_broken"])
        self.assertAlmostEqual(f["hl_gap_from_plan_pct"], -6.25)

    def test_digest_is_once_a_day_from_the_set_hour(self):
        early, later = pd.Timestamp("2026-11-05 03:00", tz="UTC"), pd.Timestamp("2026-11-05 09:00", tz="UTC")
        self.assertFalse(A.digest_due({}, early))
        self.assertTrue(A.digest_due({}, later))
        self.assertFalse(A.digest_due({"last_digest": "2026-11-05"}, later))

    def test_rejected_markup_falls_back_to_plain_text(self):
        calls = []

        def fake(method, params):
            calls.append(params)
            if params.get("parse_mode"):
                raise RuntimeError("telegram http 400")

        with mock.patch.object(A, "telegram_call", fake), mock.patch.dict(os.environ, {"TELEGRAM_CHAT_ID": "1"}):
            A.send_text('<b>x</b> &amp; <a href="u">y</a>')
        self.assertEqual(calls[1]["text"], "x & y")
        self.assertNotIn("parse_mode", calls[1])


class TestVerdict(unittest.TestCase):
    def test_each_outcome_reads_differently(self):
        crypto = A.test_verdict("crypto", "panic")
        self.assertIn("falso positivo", crypto)
        self.assertIn("NON superato", A.test_verdict("crypto", "squeeze"))
        self.assertIn("non informativo", A.test_verdict("bonds", "panic"))
        self.assertIn("NON VALIDATO", A.test_verdict("crypto", "other"))


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

    def test_every_alert_is_logged_and_sent_even_with_score_zero(self):
        st = self.empty()
        with mock.patch.object(A, "safe_options", return_value=""):
            A.enqueue([alert(), alert(key="k2", market="ETH", score=0, unknown=[])], st, True)
        rows = [json.loads(x) for x in (Path(self.tmp.name) / "alerts" / "log.jsonl").read_text().splitlines()]
        self.assertEqual([r["queued_for_telegram"] for r in rows], [True, True])
        self.assertIn("ETH", st["pending"][0])
        self.assertEqual(st["seen"], ["BTC|panic|t", "k2"])

    def test_options_failure_never_loses_an_alert(self):
        with mock.patch("bzd.options_report.options_note", side_effect=ValueError):
            self.assertIn("PANICO", A.format_group([alert()]))

    def test_alert_carries_options_context(self):
        with mock.patch("bzd.options_report.options_note", return_value="OPZ-QUI"):
            self.assertIn("OPZ-QUI", A.format_group([alert()]))

    def test_same_move_on_many_coins_is_one_message(self):
        st = self.empty()
        with mock.patch.object(A, "safe_options", return_value=""):
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
