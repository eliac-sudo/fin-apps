import json, os, tempfile, unittest
from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest import mock

from bzd import aisetups as A

SNAP = {
    "at": "2026-11-24T17:00:00+00:00", "overview": "Sotto la norma.", "briefing": [{"text": "RSI giornaliero agli estremi: ipervenduto su BTC."}],
    "classes": {"crypto": {"name": "Cripto", "heat": 31.1, "band": "sotto la norma", "change_7d": 7.4, "why": "Frena: funding."}},
    "markets": [{"market": "BTC", "label": "BTC", "plan_key": "BTC", "class": "crypto", "price": 59694.2, "heat": 23.6, "band": "sotto la norma", "returns": {"7g": -8.05},
                 "position": {"label": "molto economico", "from_high": -38.4, "from_low": 1.86}, "zones": {"1d": {"tag": "GIU"}}},
                {"market": "GC=F", "label": "Oro", "plan_key": "oro", "class": "commodities", "price": 3651.4, "returns": {}}],
    "technical": [{"market": "BTC", "trend": {"1d": "ribasso"}, "rsi": {"1d": 24.9}, "reset": {}, "support": {"price": 58779.3}, "resistance": {"price": 64986.11}}],
    "flows": [], "options": [], "lab": [], "alerts": {"setups": [], "moves": []}, "sentiment": {"fear_greed": {"value": 11}},
    "verdicts": {"O2": {"outcome": "supportata", "line": "Economiche meglio."}, "O1": {"outcome": "non supportata", "line": "No."}},
    "tests": [{"setup": "panic", "class": "crypto", "outcome": "supportata", "setup_name": "PANICO", "class_name": "cripto", "reading": ["Ha retto."]}],
}


def prop(h="breve", m="BTC", d="long", inv=58779.3, tgt=64986.11, test="nessuno", tesi="RSI a 25 e prezzo molto economico, 38% sotto il massimo."):
    return {"orizzonte": h, "mercato": m, "direzione": d, "tesi": tesi, "fatti": ["Paura a 11"], "test": test, "invalidazione": inv, "obiettivo": tgt, "rischi": "Il trend è in ribasso."}


GOOD = {"quadro": "Mercati deboli.", "proposte": [prop(), prop(m="Oro", inv=3500, tgt=3800, tesi="Oro sotto la norma."), prop("medio"), prop("medio", m="Oro", d="short", inv=3800, tgt=3500, tesi="Oro debole."), prop("lungo", test="B3-panic-crypto")]}


def client_with(*replies):
    def resp(r):
        return NS(stop_reason="end_turn", model="claude-haiku-5-5", usage=NS(input_tokens=9000, output_tokens=2000, cache_read_input_tokens=0, cache_creation_input_tokens=0), content=[NS(type="text", text=json.dumps(r))])
    create = mock.Mock(side_effect=[resp(r) for r in replies])
    return NS(beta=NS(messages=NS(create=create)), messages=NS(create=create)), create


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name, "BZD_LLM_BUDGET_USD": "5"})
        env.start()
        self.addCleanup(env.stop)
        self.data, self.tests = A.context(SNAP)


class TestChecks(Base):
    def test_a_good_answer_passes(self):
        self.assertEqual(A.check(GOOD, self.data, self.tests), [])

    def test_wrong_mix_of_horizons_is_caught(self):
        bad = {**GOOD, "proposte": GOOD["proposte"][:4] + [prop("breve")]}
        self.assertIn("2 breve", A.check(bad, self.data, self.tests)[0])

    def test_unknown_market_and_wrong_sides_are_caught(self):
        out = {**GOOD, "proposte": [prop(m="Pippo"), prop(inv=61000), prop("medio", tgt=50000), *GOOD["proposte"][3:]]}
        problems = " ".join(A.check(out, self.data, self.tests))
        self.assertIn("Pippo", problems)
        self.assertIn("invalidazione 61000", problems)
        self.assertIn("obiettivo 50000", problems)

    def test_a_test_that_did_not_hold_cannot_be_cited(self):
        out = {**GOOD, "proposte": [prop(test="O1"), *GOOD["proposte"][1:]]}
        self.assertIn("O1", " ".join(A.check(out, self.data, self.tests)))

    def test_invented_numbers_are_caught_and_italian_decimals_read(self):
        self.assertEqual(A.numbers_ok("RSI a 24,9 e prezzo 59.694,2", A.allowed_numbers(self.data, self.tests)), [])
        self.assertEqual(A.numbers_ok("supporto a 52000", A.allowed_numbers(self.data, self.tests)), ["52000"])


class TestRun(Base):
    def test_one_retry_with_the_problems_then_saved(self):
        bad = {**GOOD, "proposte": [prop(m="Pippo"), *GOOD["proposte"][1:]]}
        client, create = client_with(bad, GOOD)
        rec = A.run(client, get=lambda p, **k: SNAP)
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(create.call_count, 2)
        self.assertIn("Pippo", create.call_args.kwargs["messages"][0]["content"])
        self.assertEqual(rec["proposte"][1]["plan_key"], "oro")
        self.assertEqual(rec["proposte"][0]["prezzo"], 59694.2)
        self.assertEqual(len(A.runs()), 1)

    def test_two_failures_save_an_error_and_no_proposals(self):
        bad = {**GOOD, "proposte": GOOD["proposte"][:3]}
        client, _ = client_with(bad, bad)
        rec = A.run(client, get=lambda p, **k: SNAP)
        self.assertEqual(rec["status"], "error")
        self.assertNotIn("proposte", rec)


class TestFollow(unittest.TestCase):
    P = {**prop(), "prezzo": 100.0, "invalidazione": 95.0, "obiettivo": 110.0}

    def test_states(self):
        now = datetime(2026, 11, 25, tzinfo=timezone.utc)
        ts = "2026-11-24T00:00:00+00:00"
        self.assertEqual(A.follow(self.P, ts, 103, now), {"stato": "aperta", "rend_pct": 3.0})
        self.assertEqual(A.follow(self.P, ts, 94, now)["stato"], "invalidata")
        self.assertEqual(A.follow(self.P, ts, 94, now)["rend_pct"], -5.0)
        self.assertEqual(A.follow(self.P, ts, 111, now)["rend_pct"], 10.0)
        self.assertEqual(A.follow(self.P, ts, 101, datetime(2026, 12, 10, tzinfo=timezone.utc))["stato"], "scaduta")
        short = {**self.P, "direzione": "short", "invalidazione": 105.0, "obiettivo": 90.0}
        self.assertEqual(A.follow(short, ts, 97, now)["rend_pct"], 3.0)


class TestView(Base):
    def test_closed_outcomes_stay_frozen(self):
        client, _ = client_with(GOOD)
        A.run(client, get=lambda p, **k: SNAP)
        low = {**SNAP, "markets": [{**SNAP["markets"][0], "price": 58000.0}, SNAP["markets"][1]]}
        v = A.view(get=lambda p, **k: low)
        btc = [h for h in v["history"] if h["mercato"] == "BTC" and h["direzione"] == "long"]
        self.assertTrue(all(h["stato"] == "invalidata" for h in btc))
        v = A.view(get=lambda p, **k: SNAP)  # price back up: the closed ones don't reopen
        btc = [h for h in v["history"] if h["mercato"] == "BTC" and h["direzione"] == "long"]
        self.assertTrue(all(h["stato"] == "invalidata" for h in btc))
        self.assertEqual(v["latest"]["quadro"], "Mercati deboli.")


if __name__ == "__main__":
    unittest.main()
