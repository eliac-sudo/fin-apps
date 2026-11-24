import json, os, tempfile, unittest
from unittest import mock

from bzd import labels as LB


def item(i, text):
    return {"id": f"t{i}", "text": text, "source": "soc_x", "time": "2026-11-01T00:00:00+00:00", "url": "", "raw_file": "f", "raw_sha256": "s"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def write_set(self, texts):
        (LB.root() / "label_set.json").write_text(json.dumps({"texts": texts}))


class TestSet(Base):
    def test_strata_and_market_filter(self):
        items = [item(i, f"Bitcoin crash panic across the market, number {i} today") for i in range(40)] + [item(100 + i, f"Bitcoin rally to the moon for everyone, number {i}") for i in range(40)] \
            + [item(200 + i, f"Bitcoin price update number {i} for traders") for i in range(80)] + [item(300 + i, f"My cat had a lovely day number {i}") for i in range(50)] \
            + [item(400 + i, f"Bitcoin crash then rally number {i} today") for i in range(20)]
        chosen = LB.prepare(items)
        kinds = [LB.word_label(t["text"]) for t in chosen]
        self.assertEqual((kinds.count("paura"), kinds.count("euforia"), kinds.count("neutro")), (25, 25, 50))
        self.assertFalse(any("cat" in t["text"] for t in chosen))
        self.assertEqual([t["id"] for t in chosen], [t["id"] for t in LB.prepare(items)])

    def test_only_known_texts_and_labels_are_saved(self):
        self.write_set([item(1, "Bitcoin crash")])
        LB.save_label("t1", "paura")
        self.assertEqual(LB.labels(), {"t1": "paura"})
        for bad in (("t9", "paura"), ("t1", "felice")):
            with self.assertRaises(ValueError):
                LB.save_label(*bad)
        LB.save_label("t1", "neutro")
        self.assertEqual(LB.next_text()["done"], 1)
        self.assertEqual(LB.labels()["t1"], "neutro")


class TestAgreement(Base):
    def test_kappa_known_values(self):
        self.assertAlmostEqual(LB.kappa(["a", "b"] * 5, ["a", "b"] * 5), 1.0)
        self.assertAlmostEqual(LB.kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]), 0.0)

    def test_compare_leaves_out_irrelevant_texts(self):
        self.write_set([item(1, "Bitcoin crash panic"), item(2, "Bitcoin to the moon"), item(3, "Bitcoin update"), item(4, "Cats")])
        for i, l in ((1, "paura"), (2, "neutro"), (3, "neutro"), (4, "non pertinente")):
            LB.save_label(f"t{i}", l)
        r = LB.compare()
        self.assertEqual((r["n"], r["not_relevant"]), (3, 1))
        self.assertEqual(r["table"]["neutro→euforia"], 1)
