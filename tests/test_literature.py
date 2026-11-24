import json, tempfile, unittest
from unittest import mock

from bzd import literature as L

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/1</id><published>2021-03-01T00:00:00Z</published><title>A  Paper
 on Dips</title><author><name>Ann</name></author></entry></feed>"""


def rec(title, source="OpenAlex", cited=5, topic="T", open_url=None):
    return {"title": title, "year": 2020, "authors": ["A"], "venue": "J", "cited": cited, "url": "u", "open_url": open_url, "source": source, "topics": [topic]}


class TestRecords(unittest.TestCase):
    def test_a_work_without_title_is_dropped(self):
        self.assertIsNone(L.openalex_record({"title": None}, "T"))

    def test_openalex_fields_survive_gaps(self):
        r = L.openalex_record({"title": "<i>Dips</i>  now", "authorships": [{"author": {"display_name": "Ann"}}, {"author": None}], "primary_location": None}, "T")
        self.assertEqual((r["title"], r["authors"], r["venue"], r["cited"]), ("Dips now", ["Ann"], None, 0))

    def test_arxiv_is_parsed(self):
        r = L.parse_arxiv(ATOM, "T")[0]
        self.assertEqual((r["title"], r["year"], r["authors"], r["source"]), ("A Paper on Dips", 2021, ["Ann"], "arXiv"))


class TestMerge(unittest.TestCase):
    def test_the_published_version_replaces_the_preprint(self):
        out = L.merge([rec("A Paper!", "arXiv", 0, "X", "free")], [rec("a paper", "OpenAlex", 9, "Y")])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]["source"], out[0]["cited"], out[0]["open_url"], out[0]["topics"]), ("OpenAlex", 9, "free", ["X", "Y"]))


class TestFetch(unittest.TestCase):
    def test_a_busy_answer_is_retried_and_a_missing_page_is_not(self):
        busy = L.urllib.error.HTTPError("u", 429, "busy", {}, None)
        with mock.patch.object(L.urllib.request, "urlopen", side_effect=[busy, busy, mock.MagicMock(**{"__enter__.return_value.read.return_value": b"ok"})]):
            self.assertEqual(L.fetch("http://u", sleep=lambda _: None), b"ok")
        with mock.patch.object(L.urllib.request, "urlopen", side_effect=L.urllib.error.HTTPError("u", 404, "no", {}, None)) as call:
            with self.assertRaises(L.urllib.error.HTTPError):
                L.fetch("http://u", sleep=lambda _: None)
        self.assertEqual(call.call_count, 1)


class TestRun(unittest.TestCase):
    def test_one_source_failing_keeps_the_other(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(L, "TOPICS", {"T": "q"}), mock.patch.object(L, "search_openalex", return_value=[rec("Kept")]), mock.patch.object(L, "search_arxiv", side_effect=OSError):
            rows, failed = L.run(tmp, sleep=lambda _: None)
            self.assertEqual(json.loads(L.path(tmp).read_text())[0]["title"], "Kept")
        self.assertEqual((len(rows), failed), (1, ["arXiv/T: OSError"]))


class TestUse(unittest.TestCase):
    def test_an_invented_title_is_a_poor_match(self):
        rows = [rec("Retail traders and dips"), rec("Gamma exposure")]
        self.assertEqual(L.check("Retail traders and dips", rows)[0][0], 1.0)
        self.assertLess(L.check("Quantum tulip pricing in Mars", rows)[0][0], .6)

    def test_the_page_groups_by_topic_and_warns(self):
        with mock.patch.object(L, "TOPICS", {"T": "q"}):
            md = L.markdown([rec("Dips | more")], "01/01/2026")
        self.assertIn("Nessuno è stato letto", md)
        self.assertIn("Dips / more", md)


if __name__ == "__main__":
    unittest.main()
