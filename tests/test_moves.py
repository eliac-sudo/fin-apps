import gzip, json, os, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from bzd import alerts as A
from bzd import moves as M

NOW = datetime(2026, 11, 4, 12, 0, 30, tzinfo=timezone.utc)


def snap(root, job, when, marks):
    d = Path(root) / "raw" / job / when.strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    body = [{"universe": [{"name": n} for n in marks]}, [{"markPx": str(m), "prevDayPx": str(p)} for m, p in marks.values()]]
    with gzip.open(d / f"{when:%H%M%S}Z.json.gz", "wt") as f:
        json.dump(body, f)


class TestAssess(unittest.TestCase):
    def test_small_move_is_ignored(self):
        self.assertIsNone(M.assess("BTC", 99, 100, 100, .02))

    def test_fast_drop_trips_the_4h_window(self):
        m = M.assess("BTC", 96, 97, 100, .02)  # limit is 3.5 * 2% * sqrt(1/6) = 2.9%
        self.assertEqual((m["window"], m["down"]), ("4h", True))
        self.assertAlmostEqual(m["pct"], -4)

    def test_slow_rise_trips_the_24h_window(self):
        m = M.assess("BTC", 107, 100, 106, .02)
        self.assertEqual((m["window"], m["down"]), ("24h", False))

    def test_no_volatility_means_no_alert(self):
        self.assertIsNone(M.assess("BTC", 50, 100, 100, None))

    def test_missing_4h_snapshot_still_checks_24h(self):
        self.assertEqual(M.assess("BTC", 90, 100, None, .02)["window"], "24h")


class TestFind(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name})
        self.env.start()
        snap(self.tmp.name, "hl_ctx_main", NOW - timedelta(hours=4), {"BTC": (100, 100), "ETH": (10, 10), "OTHER": (1, 1)})
        snap(self.tmp.name, "hl_ctx_main", NOW - timedelta(seconds=30), {"BTC": (95, 98), "ETH": (10, 10), "OTHER": (.5, 1)})

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def find(self, st, now=NOW):
        return M.find_moves({"BTC": "BTC", "ETH": "ETH"}, st, now, self.tmp.name, lambda m: .02)

    def test_only_followed_markets_that_moved(self):
        self.assertEqual([m["name"] for m in self.find({})], ["BTC"])

    def test_each_snapshot_is_checked_once(self):
        st = {}
        self.assertEqual(len(self.find(st)), 1)
        self.assertEqual(self.find(st), [])

    def test_stale_data_sends_nothing(self):
        self.assertEqual(self.find({}, NOW + timedelta(hours=2)), [])

    def test_cooldown_is_per_direction(self):
        st, down = {}, {"name": "BTC", "down": True}
        self.assertEqual(len(M.apply_cooldown([down], st, NOW)), 1)
        self.assertEqual(M.apply_cooldown([down], st, NOW + timedelta(hours=1)), [])
        self.assertEqual(len(M.apply_cooldown([{"name": "BTC", "down": False}], st, NOW + timedelta(hours=1))), 1)
        self.assertEqual(len(M.apply_cooldown([down], st, NOW + timedelta(hours=13))), 1)

    def test_market_wide_move_is_one_message_and_logged(self):
        st = {"pending": []}
        snap(self.tmp.name, "hl_ctx_main", NOW - timedelta(seconds=30), {"BTC": (95, 98), "ETH": (9, 10)})
        with mock.patch.object(A, "safe_options", return_value="OPZ-QUI"):
            moved = A.check_moves(st, True, NOW, self.tmp.name, lambda m: .02)
        self.assertEqual(len(moved), 2)
        self.assertEqual(len(st["pending"]), 1)
        for word in ("BTC", "ETH", "OPZ-QUI", "Non è consulenza", "Testato 2008"):
            self.assertIn(word, st["pending"][0])
        self.assertEqual(len((Path(self.tmp.name) / "alerts" / "moves.jsonl").read_text().splitlines()), 2)

    def test_nothing_is_queued_without_the_bot(self):
        st = {"pending": []}
        A.check_moves(st, False, NOW, self.tmp.name, lambda m: .02)
        self.assertEqual(st["pending"], [])
        self.assertTrue((Path(self.tmp.name) / "alerts" / "moves.jsonl").exists())


class TestSigma(unittest.TestCase):
    def test_too_little_history_gives_nothing(self):
        import pandas as pd
        self.assertIsNone(M.daily_sigma(pd.Series([1.0, 1.1, 1.2])))
        self.assertGreater(M.daily_sigma(pd.Series([100 + (i % 2) for i in range(100)], dtype=float)), 0)
