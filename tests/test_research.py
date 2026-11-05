import json, os, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

from bzd import agents as G, literature as L, research as R

ABSTRACT = "We find that retail investors buy after price declines. Returns over the next 20 days are 1.5% higher for stocks they buy. The sample covers 2010 to 2020."
PAPER = {"key": "p1", "title": "Retail Dip Buying", "year": 2021, "venue": "J", "authors_found": ["Ann"], "url": "u", "id": "W1", "source": "catalogo", "claims": []}


def note(**kw):
    return {"tesi": "Il retail compra dopo i cali.", "metodo": "Regressioni.", "dati": "Azioni dal 2010 al 2020.", "risultati": [{"punto": "Rendimenti più alti a 20 giorni", "quote": "Returns over the next 20 days are 1.5% higher"}],
            "affermazioni": [], "pertinenza": "alta", "moduli": ["chi compra"], "perche": "Misura lo stesso comportamento.", "idea": "", "limiti": [], **kw}


def client_with(*replies, stop="end_turn"):
    """A fake API client, so no test spends money."""
    def resp(r):
        return NS(stop_reason=stop, model="claude-opus-5-5", usage=NS(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0, cache_creation_input_tokens=0), content=[NS(type="text", text=json.dumps(r))])
    create = mock.Mock(side_effect=[resp(r) for r in replies])
    return NS(beta=NS(messages=NS(create=create)), messages=NS(create=create)), create


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name, "BZD_LLM_BUDGET_USD": "5"})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("BZD_MODEL", None)


class TestReport(unittest.TestCase):
    def test_every_claim_is_copied_word_for_word_from_the_report(self):
        text = R.norm(R.report_text())
        self.assertTrue(text)
        self.assertEqual([r["key"] for r in R.GEMINI_REFS for c in r["claims"] if R.norm(c) not in text], [])
        self.assertEqual([c for c in R.UNSOURCED if R.norm(c) not in text], [])


class TestVerify(unittest.TestCase):
    def work(self, title="Investor Sentiment and the Cross-Section of Stock Returns", year=2006, venue="The Journal of Finance", author="Malcolm Baker"):
        return {"id": "W1", "doi": "d", "title": title, "publication_year": year, "cited_by_count": 9, "authorships": [{"author": {"display_name": author}}], "primary_location": {"source": {"display_name": venue}}}

    REF = {"key": "bw", "authors": "Baker, Wurgler", "year": 2006, "venue": "Journal of Finance", "title": "Investor Sentiment and the Cross-Section of Stock Returns", "claims": []}

    def test_a_full_match_is_confirmed(self):
        self.assertEqual(R.verify(self.REF, lambda q: [self.work()])["esito"], "confermato")

    def test_another_year_is_flagged_not_rejected(self):
        self.assertEqual(R.verify(self.REF, lambda q: [self.work(year=2004)])["esito"], "esiste, dettagli diversi")

    def test_same_title_by_someone_else_is_not_the_paper(self):
        self.assertEqual(R.verify(self.REF, lambda q: [self.work(author="Jane Doe")])["esito"], "non trovato")

    def test_the_best_of_several_results_wins(self):
        r = R.verify(self.REF, lambda q: [self.work(title="Something else"), self.work()])
        self.assertEqual((r["esito"], r["match"]["title"]), ("confermato", self.REF["title"]))

    def test_abstracts_are_rebuilt_in_order(self):
        self.assertEqual(R.from_inverted({"world": [1], "hello": [0], "again": [2]}), "hello world again")
        self.assertEqual(R.from_inverted(None), "")


class TestNoteChecks(unittest.TestCase):
    def test_a_clean_note_passes(self):
        self.assertEqual(R.check_note(note(), PAPER, ABSTRACT, []), [])

    def test_an_invented_quote_sinks_the_note(self):
        bad = note(risultati=[{"punto": "x", "quote": "returns double"}])
        self.assertIn("citazione non presente", R.check_note(bad, PAPER, ABSTRACT, [])[0])

    def test_a_number_from_nowhere_sinks_the_note(self):
        self.assertIn("numeri senza fonte", R.check_note(note(tesi="Il retail guadagna il 7%."), PAPER, ABSTRACT, [])[0])

    def test_every_claim_is_judged_once_and_a_verdict_needs_a_quote(self):
        claims = ["Il retail compra i cali", "Rende il 9% in più"]
        one = [{"n": 1, "esito": "confermata", "quote": "retail investors buy after price declines", "nota": ""}]
        self.assertTrue(any("giudicate" in p for p in R.check_note(note(affermazioni=one), PAPER, ABSTRACT, claims)))
        two = one + [{"n": 2, "esito": "contraddetta", "quote": "", "nota": ""}]
        self.assertTrue(any("senza citazione" in p for p in R.check_note(note(affermazioni=two), PAPER, ABSTRACT, claims)))
        ok = one + [{"n": 2, "esito": "non verificabile dall'abstract", "quote": "", "nota": "Il 9% non compare."}]
        self.assertEqual(R.check_note(note(affermazioni=ok), PAPER, ABSTRACT, claims), [])


class TestReading(Base):
    def test_a_bad_note_gets_one_retry_then_is_kept(self):
        client, create = client_with(note(tesi="Il 7% in più."), note())
        rec = R.read_paper(client, PAPER, ABSTRACT, [])
        self.assertEqual((rec["status"], create.call_count), ("ok", 2))
        self.assertIn("numeri senza fonte", create.call_args.kwargs["messages"][0]["content"])
        self.assertEqual(len(G.usage_rows()), 2)

    def test_two_bad_notes_are_rejected(self):
        client, create = client_with(note(tesi="7%"), note(tesi="8%"))
        self.assertEqual(R.read_paper(client, PAPER, ABSTRACT, [])["status"], "rejected")

    def test_a_refusal_is_an_error_not_a_note(self):
        client, _ = client_with(note(), stop="refusal")
        self.assertEqual(R.read_paper(client, PAPER, ABSTRACT, [])["status"], "error")

    def test_the_call_uses_structured_output_and_fallbacks(self):
        client, create = client_with(note())
        R.read_paper(client, PAPER, ABSTRACT, [])
        kw = create.call_args.kwargs
        self.assertEqual(kw["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(kw["fallbacks"], "default")
        self.assertNotIn("thinking", kw)


def stored(key="p1", **kw):
    return {"key": key, "title": "Retail Dip Buying", "year": 2021, "status": "ok", "note": note(**kw)}


def idea(**kw):
    return {"nome": "Retail sui dip", "ipotesi": "Quando il retail compra forte un dip, rende meno.", "note": ["p1"], "mercati": ["crypto"],
            "regola": [{"variabile": "pressione_retail", "condizione": ">=", "soglia": 80}, {"variabile": "punteggio_byz", "condizione": "<=", "soglia": -50}],
            "orizzonte": "5 sedute", "confronto": "Ingressi casuali sullo stesso mercato.", "falsificazione": "Rendimento non sotto il caso a 5 sedute.", "dati_mancanti": [], "rischi": [], **kw}


class TestIdeas(Base):
    def test_a_good_idea_passes(self):
        self.assertEqual(R.check_ideas({"idee": [idea()], "nessuna_idea_perche": ""}, [stored()]), [])

    def test_a_variable_missing_on_a_market_is_refused(self):
        p = R.check_ideas({"idee": [idea(mercati=["fx"], regola=[{"variabile": "funding", "condizione": ">=", "soglia": 80}])], "nessuna_idea_perche": ""}, [stored()])
        self.assertIn("funding non esiste", p[0])

    def test_an_unknown_note_and_a_free_number_are_refused(self):
        p = R.check_ideas({"idee": [idea(note=["nope"], ipotesi="Rende il 12% in meno.")], "nessuna_idea_perche": ""}, [stored()])
        self.assertTrue(any("note inesistenti" in x for x in p))
        self.assertTrue(any("numeri senza fonte" in x for x in p))

    def test_numbers_from_the_rule_and_the_notes_are_allowed(self):
        ok = idea(ipotesi="Con pressione 80 e 20 giorni come nel lavoro.", falsificazione="Sotto +0,75% come il panico B3.")
        self.assertEqual(R.check_ideas({"idee": [ok], "nessuna_idea_perche": ""}, [stored(risultati=[{"punto": "x", "quote": "Returns over the next 20 days"}])]), [])

    def test_no_idea_is_a_valid_answer(self):
        client, _ = client_with({"idee": [], "nessuna_idea_perche": "Le note non reggono un setup."})
        rec = R.draft_ideas(client, [stored()])
        self.assertEqual(rec["status"], "ok")
        self.assertIn("Nessuna idea", R.ideas_page(rec))


class TestCommands(Base):
    def test_paid_commands_need_the_flag(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
            self.assertIn("--paga", R.paid_ok(["leggi"]))
            self.assertIsNone(R.paid_ok(["leggi", "--paga"]))

    def test_the_cap_stops_paid_commands(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "BZD_LLM_BUDGET_USD": "0"}):
            self.assertIn("tetto", R.paid_ok(["leggi", "--paga"]))

    def test_without_flag_nothing_is_called(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch("anthropic.Anthropic") as make:
            self.assertEqual(R.main(["leggi"]), 1)
        make.assert_not_called()

    def test_a_paper_without_abstract_costs_nothing(self):
        refs = [{"key": "k", "esito": "confermato", "claims": [], "match": {"title": "T", "year": 2000, "venue": "V", "authors": ["A"], "doi": "d", "id": "W1"}}]
        (Path(self.tmp.name) / "literature").mkdir()
        (Path(self.tmp.name) / "literature" / "gemini_refs.json").write_text(json.dumps(refs))
        client, create = client_with()
        with mock.patch.object(R, "abstract_of", return_value=""), mock.patch.object(R, "DOCS", Path(self.tmp.name)):
            self.assertEqual(R.main(["leggi"], client=client, sleep=lambda _: None), 0)
        create.assert_not_called()
        self.assertEqual(R.notes()[0]["status"], "no_abstract")

    def test_catalogue_papers_rotate_across_topics(self):
        rows = [{"title": t, "year": 2020, "venue": "V", "authors": ["A"], "url": "u" + t, "source": "OpenAlex", "cited": c, "topics": [topic]}
                for t, c, topic in (("A1", 9, "Retail e flussi"), ("A2", 8, "Retail e flussi"), ("B1", 1, "Posizioni COT"))]
        with mock.patch.object(L, "path", return_value=Path(self.tmp.name) / "cat.json"):
            (Path(self.tmp.name) / "cat.json").write_text(json.dumps(rows))
            self.assertEqual([p["title"] for p in R.to_read(2)], ["A1", "B1"])


if __name__ == "__main__":
    unittest.main()
