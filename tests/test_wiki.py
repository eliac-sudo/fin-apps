import tempfile, unittest
from pathlib import Path
from unittest import mock

from bzd import wiki as W


class TestWiki(unittest.TestCase):
    def test_every_citation_and_link_in_the_real_wiki_resolves(self):
        hard = [p for p in W.lint() if p["kind"] != "fermo"]
        self.assertEqual(hard, [])

    def test_front_matter_lists_and_body(self):
        meta, body = W.parse("---\ntitle: X\ncode: bzd/a.py#f, bzd/b.py\n---\n## Ciao\ntesto")
        self.assertEqual(meta["title"], "X")
        self.assertEqual(meta["code"], ["bzd/a.py#f", "bzd/b.py"])
        self.assertEqual(meta["data"], [])
        self.assertTrue(body.startswith("## Ciao"))

    def test_a_citation_points_at_the_definition(self):
        line = W.find_line("bzd/wiki.py", "find_line")
        self.assertTrue(Path(W.ROOT / "bzd/wiki.py").read_text().splitlines()[line - 1].startswith("def find_line"))
        self.assertEqual(W.find_line("bzd/wiki.py", "no_such_name_here_xyz"), 0)
        self.assertEqual(W.find_line("bzd/nope.py", ""), 0)

    def test_broken_pages_are_reported(self):
        page = {"slug": "a", "title": "A", "kind": "calcolo", "status": "", "brief": "", "fresh": "", "tab": "",
                "body": "vedi [[manca]] e `bzd/wiki.py#nessuna_funzione_xyz`", "code": ["bzd/manca.py"], "data": ["data/manca"], "docs": [], "feeds": []}
        kinds = {p["kind"] for p in W.lint({"a": page})}
        self.assertTrue({"citazione", "link", "dati", "copertura"} <= kinds)

    def test_secrets_and_paths_outside_stay_hidden(self):
        for bad in (".env", "bzd/../.env", "/etc/passwd", "data/.env", "docs/../.env"):
            self.assertIsNone(W.source(bad), bad)
        for bad in ("data/../.env", "data/alerts/state.json", "bzd", "/data", "data/../bzd"):
            self.assertIsNone(W.data_view(bad), bad)
        self.assertIsNotNone(W.source("bzd/wiki.py"))

    def test_a_data_file_shows_only_its_first_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data" / "x").mkdir(parents=True)
            (root / "data" / "x" / "f.csv").write_text("\n".join(str(i) for i in range(100)))
            with mock.patch.object(W, "ROOT", root):
                v = W.data_view("data/x/f.csv")
                self.assertEqual(len(v["head"]), 25)
                self.assertEqual(W.data_view("data/x")["items"][0]["name"], "f.csv")

    def test_module_graph_reads_imports(self):
        self.assertIn(("app", "wiki"), W.module_graph())
        self.assertIn(("snapshot", "flows"), W.module_graph())


if __name__ == "__main__":
    unittest.main()
