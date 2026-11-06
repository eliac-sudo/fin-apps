import os, tempfile, unittest
from datetime import datetime, timezone
from unittest import mock

from bzd import wallets as W


def lb_row(address, capital, pnl_all, pnl_month, vlm_month):
    w = lambda pnl, vlm: {"pnl": str(pnl), "roi": "0", "vlm": str(vlm)}
    return {"ethAddress": address, "accountValue": str(capital), "displayName": None,
            "windowPerformances": [["day", w(0, 0)], ["week", w(0, 0)], ["month", w(pnl_month, vlm_month)], ["allTime", w(pnl_all, vlm_month * 10)]]}


def state(*positions, value=1000.0):
    return {"marginSummary": {"accountValue": str(value)},
            "assetPositions": [{"position": {"coin": c, "szi": str(s), "entryPx": "1", "positionValue": str(v), "leverage": {"value": 3}, "unrealizedPnl": "0", "liquidationPx": None}} for c, s, v in positions]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"BZD_DATA": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class TestChoose(Base):
    def test_small_accounts_are_dropped_when_saving(self):
        rows = W.slim({"leaderboardRows": [lb_row("a", 5_000, 1, 1, 1), lb_row("b", 50_000, 1, 1, 1)]})
        self.assertEqual([r[0] for r in rows], ["b"])

    def test_market_makers_and_idle_accounts_are_not_followed(self):
        rows = W.slim({"leaderboardRows": [lb_row("trader", 1e6, 5e6, 1e5, 5e6), lb_row("maker", 1e6, 9e6, 1e5, 5e8), lb_row("vault", 1e6, 8e6, 1e5, 0),
                                           lb_row("loser", 1e6, -3e6, -1e5, 2e6), lb_row("small", 50_000, 7e6, 1e5, 1e5)]})
        c = W.choose(rows)
        self.assertEqual(c.get("trader"), "vincenti storici")
        self.assertEqual(c.get("loser"), "perdenti storici")
        for gone in ("maker", "vault", "small"):
            self.assertNotIn(gone, c)

    def test_a_winner_list_never_holds_a_loss(self):
        rows = W.slim({"leaderboardRows": [lb_row("x", 1e6, -1e6, -1e4, 2e6)]})
        self.assertNotIn("vincenti", W.choose(rows).get("x", ""))


class TestPositions(Base):
    def test_flows_count_sides_and_net_dollars(self):
        snap = {"at": "2026-11-06T13:00:00+00:00", "wallets": {
            "a": {"cohort": "vincenti storici", "positions": [["", "BTC", -2.0, 1, 500.0, 3, 0, None]]},
            "b": {"cohort": "vincenti storici", "positions": [["", "BTC", 1.0, 1, 200.0, 3, 0, None]]},
            "c": {"cohort": "perdenti storici", "positions": [["xyz", "xyz:GOLD", 3.0, 1, 300.0, 3, 0, None]]}}}
        f = W.flows(snap)
        self.assertEqual(f["BTC"]["vincenti storici"], {"long": 1, "short": 1, "net": -300.0})
        self.assertEqual(f["xyz:GOLD"]["perdenti storici"]["net"], 300.0)
        self.assertIn("BTC", W.flows_text(snap))

    def test_a_round_reads_both_dexes_and_survives_a_failure(self):
        def http(url, body=None, timeout=0):
            if body["user"] == "bad":
                raise OSError("down")
            return state(("BTC", -1, 100)) if body["dex"] == "" else state(("xyz:GOLD", 2, 50))
        with mock.patch.object(W, "http", http):
            snap = W.take_positions({"good": "vincenti storici", "bad": "perdenti storici"}, datetime(2026, 11, 6, 13, tzinfo=timezone.utc), sleep=lambda s: None, log=lambda m: None)
        self.assertEqual([p[1] for p in snap["good"]["positions"]], ["BTC", "xyz:GOLD"])
        self.assertEqual(snap["good"]["capital"], 2000)
        self.assertEqual(W.latest_positions()["failed"], 1)

    def test_leaderboard_once_a_day_and_positions_once_an_hour(self):
        calls = []
        with mock.patch.object(W, "take_leaderboard", side_effect=lambda now: calls.append("lb") or ([], {"a": "vincenti storici"})), \
             mock.patch.object(W, "take_positions", side_effect=lambda c, now, log=None: calls.append("pos")):
            st = {}
            t = datetime(2026, 11, 6, 13, 5, tzinfo=timezone.utc)
            W.cycle(st, t, log=lambda m: None)
            W.cycle(st, t.replace(minute=40), log=lambda m: None)
            W.cycle(st, t.replace(hour=14, minute=1), log=lambda m: None)
        self.assertEqual(calls, ["lb", "pos", "pos"])
