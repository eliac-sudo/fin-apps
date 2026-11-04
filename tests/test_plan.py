import os, tempfile, unittest
from pathlib import Path
from unittest import mock

from bzd import alerts as A
from bzd import plan as P

INFO = {"mark": 100.0, "funding": .00001, "max_leverage": 40, "decimals": 3}


def build(capital=10000, risk=1, entry=100.0, stop=95.0, target=3, info=INFO, costs=0, **k):
    return P.build_plan(capital, risk, entry, stop, target, info, costs, **k)


class TestSize(unittest.TestCase):
    def test_loss_at_stop_is_the_risk_chosen(self):
        p = build()
        self.assertEqual(p["size"], 20)
        self.assertAlmostEqual(p["loss_at_stop"], 100)
        self.assertAlmostEqual(p["gain_at_target"], 300)
        self.assertEqual(p["target"], 115)

    def test_costs_make_the_position_smaller_and_stay_inside_the_budget(self):
        p = build(costs=.001)
        self.assertLess(p["size"], 20)
        self.assertLessEqual(p["loss_at_stop"], 100.0001)
        self.assertLess(p["gain_at_target"], 300)

    def test_size_rounds_down_to_what_the_market_accepts(self):
        p = build(stop=93.0, info={**INFO, "decimals": 0})
        self.assertEqual(p["size"], 14)
        self.assertLessEqual(p["loss_at_stop"], 100)

    def test_wider_stop_means_smaller_position_same_loss(self):
        a, b = build(stop=98), build(stop=80)
        self.assertGreater(a["size"], b["size"])
        self.assertAlmostEqual(a["loss_at_stop"], b["loss_at_stop"])
        self.assertTrue(any("largo" in w for w in b["warnings"]))

    def test_stop_above_price_is_a_short(self):
        p = build(stop=105)
        self.assertEqual(p["side"], "short")
        self.assertEqual(p["target"], 85)
        self.assertLess(p["funding_per_day"], 1e9)
        self.assertGreater(p["funding_per_day"], 0)  # positive funding: shorts receive it

    def test_short_target_below_zero_is_refused(self):
        with self.assertRaises(P.PlanError):
            build(stop=150)

    def test_stop_equal_to_price_is_refused(self):
        with self.assertRaises(P.PlanError):
            build(stop=100)

    def test_tiny_account_on_a_coarse_market_is_refused(self):
        with self.assertRaises(P.PlanError):
            build(capital=10, stop=50, info={**INFO, "decimals": 0})


class TestLeverage(unittest.TestCase):
    def test_lowest_leverage_that_fits(self):
        self.assertEqual(build(capital=100000)["leverage"], 1)  # 20,000 on 100,000
        self.assertEqual(build(capital=10000, stop=99.5, risk=1)["leverage"], 2)

    def test_position_capped_by_max_leverage_says_risk_is_lower(self):
        p = build(stop=99.99, info={**INFO, "max_leverage": 3})
        self.assertLessEqual(p["notional"], 30000.001)
        self.assertLess(p["loss_at_stop"], 100)
        self.assertTrue(any("ridotta" in w for w in p["warnings"]))

    def test_liquidation_matches_the_formula(self):
        # long at 100, 10x, max 40x: l = 1/80. 100 - 100 * (0.1 - 0.0125) / (1 - 0.0125)
        self.assertAlmostEqual(P.liquidation(100, 10, 40, True), 91.139, places=3)
        self.assertAlmostEqual(P.liquidation(100, 10, 40, False), 108.642, places=3)
        self.assertEqual(P.liquidation(100, 1, 40, True), 0)

    def test_leverage_that_liquidates_before_the_stop_is_flagged(self):
        p = build(stop=80, leverage=10)
        msg = [w for w in p["warnings"] if w.startswith("❌")]
        self.assertTrue(msg)
        safe = int(msg[0].split("sotto ")[1].split("x")[0])
        self.assertLess(P.liquidation(100, safe, 40, True), 80)
        self.assertFalse(any(w.startswith("❌") for w in build(stop=80, leverage=safe)["warnings"]))

    def test_leverage_above_the_market_limit_is_flagged(self):
        self.assertTrue(any("non disponibile" in w for w in build(leverage=100)["warnings"]))


class TestWarnings(unittest.TestCase):
    def test_high_risk_shows_what_ten_stops_cost(self):
        self.assertTrue(any("10 stop" in w for w in build(risk=5)["warnings"]))
        self.assertFalse(any("10 stop" in w for w in build(risk=1)["warnings"]))

    def test_stop_inside_normal_noise(self):
        self.assertTrue(any("stretto" in w for w in build(stop=99, atr_share=.05)["warnings"]))

    def test_small_order(self):
        self.assertTrue(any("minimo" in w for w in build(capital=50, stop=50)["warnings"]))


class TestParse(unittest.TestCase):
    def test_full_request(self):
        r = P.parse_request("oro 5000 0,5 stop 3900 target 2 leva 3".split())
        self.assertEqual((r["market"], r["capital"], r["risk_pct"], r["stop"], r["target_r"], r["leverage"]), ("oro", 5000, .5, 3900, 2, 3))

    def test_defaults(self):
        r = P.parse_request(["BTC", "5000"])
        self.assertEqual((r["risk_pct"], r["target_r"]), (1, 3))

    def test_capital_from_env_or_usage(self):
        with mock.patch.dict(os.environ, {"BZD_CAPITAL": "700"}):
            self.assertEqual(P.parse_request(["BTC"])["capital"], 700)
        with mock.patch.dict(os.environ), self.assertRaises(P.PlanError):
            os.environ.pop("BZD_CAPITAL", None)
            P.parse_request(["BTC"])

    def test_bad_input_gets_words_not_a_crash(self):
        for words in (["BTC", "abc"], ["BTC", "-5"], ["BTC", "nan"], ["BTC", "100", "stop"], ["BTC", "100", "boh", "3"], []):
            with self.assertRaises(P.PlanError):
                P.parse_request(words)

    def test_names(self):
        self.assertEqual(P.resolve("btc"), "BTC")
        self.assertEqual(P.resolve("Oro"), "xyz:GOLD")
        self.assertEqual(P.resolve("xyz:CL"), "xyz:CL")
        with self.assertRaises(P.PlanError):
            P.resolve("PIPPO")


class TestMake(unittest.TestCase):
    def setUp(self):
        self.levels = {"close": 100.0, "stop": 94.0, "stop_share": .06, "atr_share": .02}

    def make(self, words, name_info=INFO):
        with mock.patch.object(P, "market_info", return_value=name_info), mock.patch.object(P, "history_levels", return_value=self.levels):
            return P.make_plan(words)

    def test_text_has_every_decision(self):
        t = self.make(["BTC", "10000"])[0]
        for w in ("LONG", "Quanto", "Leva", "Stop", "Obiettivo 3R", "Tempo", "14 giorni", "Funding", "consulenza"):
            self.assertIn(w, t)

    def test_crypto_rule_stop_comes_from_the_recent_lows(self):
        self.assertAlmostEqual(self.make(["BTC", "10000"])[1]["stop"], 94)

    def test_other_markets_use_the_share_and_warn_about_third_party(self):
        t, rec = self.make(["oro", "10000"], {**INFO, "mark": 200.0})
        self.assertAlmostEqual(rec["stop"], 188)
        self.assertIn("terzi", t)
        self.assertIn("20 sedute", t)

    def test_no_price_means_no_plan(self):
        with self.assertRaises(P.PlanError):
            self.make(["BTC", "10000"], None)
        with self.assertRaises(P.PlanError):
            self.make(["BTC", "10000", "entrata", "100"], None)

    def test_no_history_needs_a_stop(self):
        self.levels = None
        with self.assertRaises(P.PlanError):
            self.make(["BTC", "10000"])
        self.assertEqual(self.make(["BTC", "10000", "stop", "90"])[1]["stop"], 90)


class TestTelegram(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name, "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "42"})
        self.env.start()
        (Path(self.tmp.name) / "alerts").mkdir()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_poll(self, text, chat=42, date=1000, now=1000):
        st, sent, asked = {"seen": [], "pending": []}, [], []
        ups = {"result": [{"update_id": 7, "message": {"text": text, "date": date, "chat": {"id": chat}}}]}
        with mock.patch.object(A, "telegram_call", return_value=ups), mock.patch.object(A, "send_text", side_effect=sent.append), \
                mock.patch("bzd.plan.answer", side_effect=lambda w: asked.append(w) or "RISPOSTA"):
            A.poll_commands(st, now=now)
        return st, sent, asked

    def test_own_chat_gets_an_answer(self):
        st, sent, asked = self.run_poll("/piano BTC 5000")
        self.assertEqual((sent, asked, st["tg_offset"]), (["RISPOSTA"], [["BTC", "5000"]], 8))

    def test_other_chats_are_ignored_but_consumed(self):
        st, sent, _ = self.run_poll("/piano BTC 5000", chat=99)
        self.assertEqual((sent, st["tg_offset"]), ([], 8))

    def test_old_requests_are_ignored(self):
        self.assertEqual(self.run_poll("/piano BTC 5000", date=1000, now=5000)[1], [])

    def test_other_text_is_ignored(self):
        self.assertEqual(self.run_poll("ciao")[1], [])

    def test_answer_turns_errors_into_words_and_logs_plans(self):
        self.assertIn("non seguito", P.answer(["PIPPO", "100"]))
        with mock.patch.object(P, "make_plan", return_value=("ok", {"market": "BTC"})):
            self.assertEqual(P.answer(["BTC", "100"]), "ok")
        self.assertIn("BTC", (Path(self.tmp.name) / "alerts" / "plans.jsonl").read_text())
