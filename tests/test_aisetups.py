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
                {"market": "GC=F", "label": "Oro", "plan_key": "oro", "class": "commodities", "price": 3651.4, "returns": {}},
                {"market": "ETH", "label": "ETH", "plan_key": "ETH", "class": "crypto", "price": 2000.0, "returns": {}},
                {"market": "ES=F", "label": "S&P 500", "plan_key": "ES", "class": "equities", "price": 6000.0, "returns": {}},
                {"market": "NQ=F", "label": "Nasdaq 100", "plan_key": "NQ", "class": "equities", "price": 21000.0, "returns": {}}],
    "technical": [{"market": "BTC", "trend": {"1d": "ribasso"}, "rsi": {"1d": 24.9}, "reset": {}, "support": {"price": 58779.3}, "resistance": {"price": 64986.11}}],
    "flows": [], "options": [], "lab": [], "alerts": {"setups": [], "moves": []}, "sentiment": {"fear_greed": {"value": 11}},
    "verdicts": {"O2": {"outcome": "supportata", "line": "Economiche meglio."}, "O1": {"outcome": "non supportata", "line": "No."}},
    "tests": [{"setup": "panic", "class": "crypto", "outcome": "supportata", "setup_name": "PANICO", "class_name": "cripto", "reading": ["Ha retto."]}],
}


def prop(h="breve", m="BTC", d="long", inv=58779.3, tgt=64986.11, test="nessuno", tesi="RSI a 25 e prezzo molto economico, 38% sotto il massimo.", titolo="Rimbalzo da ipervenduto", conv=3):
    return {"orizzonte": h, "mercato": m, "direzione": d, "titolo": titolo, "tesi": tesi, "fatti": ["Paura a 11"], "test": test, "convinzione": conv,
            "invalidazione": inv, "obiettivo": tgt, "rischi": "Il trend è in ribasso."}


GOOD = {"quadro": "Mercati deboli.", "attivi": [], "candidati": [prop(), prop(m="Oro", inv=3550, tgt=3800, tesi="Oro sotto la norma."),
        prop("medio", m="ETH", inv=1900, tgt=2300, tesi="ETH debole."), prop("medio", m="S&P 500", d="short", inv=6100, tgt=5700, tesi="Azioni deboli."),
        prop("lungo", m="Nasdaq 100", inv=20000, tgt=23000, tesi="Nasdaq.", test="B3-panic-crypto")]}


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

    def test_too_few_valid_candidates_fail_the_round(self):
        bad = {**GOOD, "candidati": GOOD["candidati"][:4] + [prop("breve")]}
        self.assertIn("lungo: 0 validi", A.check(bad, self.data, self.tests)[0])

    def test_a_bad_candidate_is_dropped_not_the_round(self):
        out = {**GOOD, "candidati": GOOD["candidati"] + [prop(m="Pippo"), prop(inv=61000), prop("medio", tgt=50000), prop(test="O1"), prop(tgt=59900)]}
        self.assertEqual(A.check(out, self.data, self.tests), [])
        cands, _ = A.screen(out, self.data, self.tests)
        problems = " ".join(" ".join(c["problemi"]) for c in cands)
        for x in ("Pippo", "invalidazione 61000", "obiettivo 50000", "O1", "più vicino"):
            self.assertIn(x, problems)

    def test_score(self):
        p = prop()  # reward/risk (64986.11 - 59694.2) / (59694.2 - 58779.3) is about 5.8, capped at 3
        self.assertEqual(A.score(p, 59694.2, self.tests), 6.0)
        self.assertEqual(A.score({**p, "test": "B3-panic-crypto", "convinzione": 5}, 59694.2, self.tests), 10.0)

    def test_invented_numbers_are_caught_and_italian_decimals_read(self):
        self.assertEqual(A.numbers_ok("RSI a 24,9 e prezzo 59.694,2", A.allowed_numbers(self.data, self.tests)), [])
        self.assertEqual(A.numbers_ok("supporto a 52000", A.allowed_numbers(self.data, self.tests)), ["52000"])


NOW = datetime(2026, 11, 25, 13, 30, tzinfo=timezone.utc)


class TestBoard(Base):
    def entry(self, key, h="breve", m="BTC", d="long", punteggio=6.0, ts="2026-11-25T06:30:00+00:00"):
        return {**prop(h, m, d), "key": key, "ts": ts, "prezzo": 59694.2, "punteggio": punteggio}

    def cands(self, *ps):
        return A.screen({"candidati": list(ps)}, self.data, self.tests)[0]

    def test_a_good_setup_stays_when_nothing_is_clearly_better(self):
        board = [self.entry("a")]
        cands = self.cands(prop(m="Oro", inv=3550, tgt=3800, tesi="Oro sotto la norma."))  # 3 + 1 = 4 points
        kept, entering, leaving, changes, _ = A.pick(board, cands, {}, {"btc": 59694.2, "oro": 3651.4}, NOW)
        self.assertEqual([e["key"] for e in kept], ["a"])
        self.assertEqual([c["mercato"] for c in entering], ["Oro"])  # the second short-term slot was free
        self.assertEqual(leaving, [])

    def test_overtaken_setup_is_replaced(self):
        board = [self.entry("a"), self.entry("b", m="Oro", d="short", punteggio=4.0)]
        board[1].update(invalidazione=3750, obiettivo=3500, prezzo=3651.4)
        cands = self.cands(prop(m="BTC", d="long"))
        verdicts = {"b": {"id": "b", "giudizio": "superata", "motivo": "l'oro ha girato"}}
        kept, entering, leaving, changes, fate = A.pick(board, cands, verdicts, {"btc": 59694.2, "oro": 3651.4}, NOW)
        self.assertEqual([e["key"] for e in kept], ["a", "b"])  # BTC long confirms "a"; with nothing to put in its place, "b" stays
        self.assertEqual(entering, [])
        self.assertEqual(list(fate.values()), ["conferma un'idea già in bacheca"])
        kept, entering, leaving, changes, fate = A.pick(board[1:], cands, verdicts, {"btc": 59694.2, "oro": 3651.4}, NOW)
        self.assertEqual(kept, [])
        self.assertEqual(leaving[0][1]["stato"], "sostituita")
        self.assertEqual([c["mercato"] for c in entering], ["BTC"])
        self.assertIn("l'oro ha girato", changes[0])

    def test_clearly_better_candidate_replaces_and_closed_ones_leave(self):
        board = [self.entry("a", punteggio=3.0), self.entry("c", h="medio", m="Oro", punteggio=5.0)]
        board[1].update(invalidazione=3550, obiettivo=3800, prezzo=3651.4)
        cands = self.cands(prop(m="Oro", inv=3550, tgt=3800, tesi="Oro sotto la norma.", conv=5))  # 5 + 1 = 6 points, not >= 3 + 2? it is 6 >= 5
        kept, entering, leaving, changes, _ = A.pick(board, cands, {}, {"btc": 59694.2, "oro": 3400.0}, NOW)
        self.assertEqual(leaving[0][1]["stato"], "invalidata")  # Oro under its invalidation: closed
        self.assertEqual(leaving[1][0]["key"], "a")
        self.assertEqual(leaving[1][1]["stato"], "sostituita")
        self.assertEqual([c["mercato"] for c in entering], ["Oro"])
        self.assertTrue(any(c.startswith("Sostituita BTC") for c in changes))


class TestRun(Base):
    def test_one_retry_with_the_problems_then_saved(self):
        bad = {**GOOD, "candidati": [prop(m="Pippo"), *GOOD["candidati"][1:]]}
        client, create = client_with(bad, GOOD)
        rec = A.run(client, get=lambda p, **k: SNAP, now=NOW)
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(create.call_count, 2)
        self.assertIn("Pippo", create.call_args.kwargs["messages"][0]["content"])
        self.assertEqual(len(rec["attivi"]), 5)
        self.assertEqual({p["plan_key"] for p in rec["proposte"]}, {"BTC", "oro", "ETH", "ES", "NQ"})
        self.assertEqual(len(A.runs()), 1)

    def test_second_round_keeps_the_board_and_sends_nothing(self):
        client, _ = client_with(GOOD, {**GOOD, "attivi": []})
        first = A.run(client, get=lambda p, **k: SNAP, now=NOW)
        second = A.run(client, get=lambda p, **k: SNAP, now=datetime(2026, 11, 26, 6, 30, tzinfo=timezone.utc))
        self.assertEqual(second["proposte"], [])
        self.assertEqual([e["key"] for e in second["attivi"]], [e["key"] for e in first["attivi"]])
        with mock.patch("bzd.alerts.sending_enabled", return_value=True), mock.patch("bzd.alerts.send_text") as st:
            self.assertFalse(A.send(second))
            self.assertTrue(A.send(first))
            self.assertTrue(st.called)

    def test_two_failures_save_an_error_and_no_proposals(self):
        bad = {**GOOD, "candidati": GOOD["candidati"][:3]}
        client, _ = client_with(bad, bad)
        rec = A.run(client, get=lambda p, **k: SNAP, now=NOW)
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
        A.run(client, get=lambda p, **k: SNAP, now=NOW)
        low = {**SNAP, "markets": [{**SNAP["markets"][0], "price": 58000.0}, SNAP["markets"][1]]}
        v = A.view(get=lambda p, **k: low)
        btc = [h for h in v["history"] if h["mercato"] == "BTC" and h["direzione"] == "long"]
        self.assertTrue(all(h["stato"] == "invalidata" for h in btc))
        v = A.view(get=lambda p, **k: SNAP)  # price back up: the closed ones don't reopen
        btc = [h for h in v["history"] if h["mercato"] == "BTC" and h["direzione"] == "long"]
        self.assertTrue(all(h["stato"] == "invalidata" for h in btc))
        self.assertEqual(v["latest"]["quadro"], "Mercati deboli.")
        self.assertEqual(len(v["board"]), 5)


if __name__ == "__main__":
    unittest.main()
