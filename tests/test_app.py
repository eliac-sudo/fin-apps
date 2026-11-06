import gzip, json, tempfile, unittest
from pathlib import Path
from unittest import mock

from bzd import app as App
from bzd import plan as P
from bzd import snapshot as S


class TestApp(unittest.TestCase):
    def test_json_has_no_nan(self):
        self.assertEqual(json.loads(json.dumps(S.clean({"a": float("nan"), "b": [1.5, float("inf")]}))), {"a": None, "b": [1.5, None]})

    def test_one_broken_part_is_named_and_the_rest_survives(self):
        errors = {}
        self.assertEqual(S.part(lambda: 1 / 0, errors, "options", []), [])
        self.assertEqual(errors, {"options": "ZeroDivisionError"})

    def test_explanations_follow_the_numbers(self):
        dear = {"iv": .5, "rv": .3, "ratio": 1.6, "label": "care"}
        t = " ".join(S.explain("X", {"pct": 95.0}, dear, {"inverted": True}, .05))
        self.assertIn("molto alta", t)
        self.assertIn("±14,4%", t)
        self.assertIn("prossimi giorni", t)
        self.assertIn("Proteggersi", t)
        self.assertEqual(S.explain("X", None, None, None, None), [])

    def test_old_alert_says_when_its_plan_is_gone(self):
        plan = {"price": 100.0, "stop": 95.0, "target_3r": 115.0}
        self.assertTrue(S.since_trigger(plan, 90.0)["broken"])
        self.assertTrue(S.since_trigger(plan, 120.0)["target_hit"])
        self.assertAlmostEqual(S.since_trigger(plan, 110.0)["since_pct"], 10)
        self.assertEqual(S.since_trigger(None, 90.0), {})

    def test_plan_form_uses_the_same_words_as_the_bot(self):
        with mock.patch.object(P, "make_plan", return_value=("t", {"size": 1})) as m:
            code, reply = App.plan_reply({"market": ["BTC"], "capital": ["5000"], "risk": ["1"], "stop": ["70000"]})
        m.assert_called_once_with(["BTC", "5000", "1", "stop", "70000"])
        self.assertEqual((code, reply), (200, {"plan": {"size": 1}}))

    def test_plan_errors_come_back_as_words(self):
        self.assertEqual(App.plan_reply({"market": [""], "capital": [""]})[0], 400)
        code, reply = App.plan_reply({"market": ["PIPPO"], "capital": ["100"]})
        self.assertEqual(code, 400)
        self.assertIn("non seguito", reply["error"])

    def test_page_builds_links_safely(self):
        page = App.PAGE.read_text()
        self.assertIn("/^https?:", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("http://", page.replace("http://www.w3.org/2000/svg", ""))

    def test_unknown_market_is_refused(self):
        self.assertFalse(S.known_market("../../etc/passwd"))
        self.assertTrue(S.known_market("BTC"))


class TestTrends(unittest.TestCase):
    FEED = b"""<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><title>Daily Search Trends</title>
    <item><title>cavaliers vs thunder</title><ht:approx_traffic>1000+</ht:approx_traffic></item>
    <item><title>bitcoin price</title><ht:approx_traffic>500+</ht:approx_traffic></item></channel></rss>"""

    def test_feed_is_parsed_and_market_queries_are_found(self):
        rows = S.parse_trending(self.FEED)
        self.assertEqual(rows[0], {"query": "cavaliers vs thunder", "traffic": "1000+"})
        self.assertEqual([r["query"] for r in rows if S.TOPIC_ALL.search(r["query"])], ["bitcoin price"])

    def test_no_files_means_nothing_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(S.trends_part(tmp), [])

    def test_latest_file_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "raw" / "trends_google_us" / "2026-11-05"
            d.mkdir(parents=True)
            with gzip.open(d / "120000Z.json.gz", "wb") as f:
                f.write(self.FEED)
            r = S.trends_part(tmp)[0]
            self.assertEqual((r["geo"], r["total"], r["market"][0]["query"]), ("USA", 2, "bitcoin price"))

    def test_recorder_accepts_the_feed(self):
        from bzd.jobs import all_jobs
        from bzd.recorder import validate
        jobs = [j for j in all_jobs() if j.name in S.TRENDS_JOBS]
        self.assertEqual(len(jobs), 2)
        for j in jobs:
            self.assertIsNone(validate(j.kind, self.FEED))


class TestToday(unittest.TestCase):
    MARKETS = [{"label": "Oro", "returns": {"7g": -5.2}}, {"label": "BTC", "returns": {"7g": 3.1}}]
    CLASSES = {"crypto": {"name": "Cripto", "change_7d": 12.0, "why": "Spinge: leva."}}
    TECH = [{"label": "Mais", "rsi": {"1d": 23.0}, "reset": {"1d": None}}, {"label": "Oro", "rsi": {"1d": 40.0}, "reset": {"1w": "ipervenduto"}}]

    def test_briefing_says_what_matters_in_words(self):
        t = " ".join(x["text"] for x in S.briefing(self.MARKETS, self.CLASSES, [{"name": "Petrolio", "ratio": 1.4}, {"name": "Bitcoin", "ratio": .9}], self.TECH, {}))
        for word in ("BTC (+3,1%)", "Oro (-5,2%)", "Cripto: si è spostato verso l'alto di 12 punti", "ipervenduto su Mais", "Reset in corso su Oro", "Petrolio (1,4 volte"):
            self.assertIn(word, t)

    def test_empty_day_says_nothing_rather_than_breaking(self):
        self.assertEqual(S.briefing([], {}, [], [], {}), [])

    def test_class_history_averages_markets_by_day(self):
        h = S.class_history([{"market": "A", "history": {"2026-11-01": 40.0, "2026-11-02": 50.0}}, {"market": "B", "history": {"2026-11-01": 60.0, "2026-11-02": 70.0}}])
        self.assertEqual((h["dates"], h["values"]), (["2026-11-01", "2026-11-02"], [50.0, 60.0]))


class TestSentimentGroups(unittest.TestCase):
    def find(self, text):
        return [n for _, n, p in S.SENTIMENT_GROUPS if __import__("re").search(p, text, __import__("re").I)]

    def test_each_topic_lands_in_its_group(self):
        self.assertIn("Energia", self.find("Brent crude falls"))
        self.assertIn("Metalli preziosi", self.find("gold price jumps"))
        self.assertIn("Metalli rari e industriali", self.find("lithium and rare earth rally"))
        self.assertIn("Giappone", self.find("JGB yields at a high after BOJ"))
        self.assertIn("Europa", self.find("bund yields rise"))
        self.assertIn("Cina", self.find("PBOC cuts, China bond yields fall"))
        self.assertIn("Yen", self.find("the yen slides"))
        self.assertEqual(self.find("cake recipe"), [])


class TestTestPage(unittest.TestCase):
    def test_every_setup_has_a_full_detail(self):
        rows = S.tests_part()
        self.assertEqual(len(rows), 15)
        for r in rows:
            self.assertTrue(r["reading"] and r["rule"] and r["markets"] and r["conditions"] and r["horizons"])
            self.assertTrue(any(h["bars"] == r["horizon_bars"] for h in r["horizons"]))

    def test_reading_follows_the_outcome(self):
        base = {"mean": .01, "ci90": [-.01, .03], "power_d30": .9, "score_link": {"spearman": .01, "p": .9}}
        self.assertIn("falso positivo", " ".join(S.test_reading({**base, "outcome": "supportata", "passes_global": False}, "panic")))
        self.assertIn("non basta", " ".join(S.test_reading({**base, "outcome": "non supportata"}, "panic")))
        self.assertIn("troppo pochi", " ".join(S.test_reading({**base, "outcome": "non informativa"}, "panic")))
        self.assertIn("comprende lo zero", " ".join(S.test_reading({**base, "outcome": "non supportata"}, "panic")))


class TestCache(unittest.TestCase):
    def test_stale_data_comes_back_at_once_and_refreshes_behind(self):
        import threading
        release, done = threading.Event(), threading.Event()

        def slow_build():
            release.wait(5)
            done.set()
            return {"new": 1}

        with mock.patch.object(App, "_cache", {"at": 0, "data": b"old"}), mock.patch.object(App.S, "build", side_effect=slow_build):
            self.assertEqual(App.snapshot(), b"old")  # returned while the rebuild is still waiting
            release.set()
            self.assertTrue(done.wait(5))

    def test_failed_refresh_keeps_the_old_data(self):
        with mock.patch.object(App, "_cache", {"at": 0, "data": b"old"}), mock.patch.object(App.S, "build", side_effect=ValueError):
            App.refresh()
            self.assertEqual(App._cache["data"], b"old")
            self.assertFalse(App._cache["busy"])


class TestBriefingZones(unittest.TestCase):
    def test_briefing_names_the_tags(self):
        rows = [{"label": "Oro", "zones": {"1d": {"tag": "GIU"}}}, {"label": "BTC", "zones": {"1d": {"tag": "SU"}}}, {"label": "ETH", "zones": {"1d": {"tag": "NTR"}}}]
        t = S.briefing(rows, {}, [], [], {})[0]["text"]
        self.assertEqual(t, "Momentum sul giornaliero: in calo su Oro; in salita su BTC.")
