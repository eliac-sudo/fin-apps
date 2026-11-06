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


def fill(t, coin, side, sz, start, d, pnl=0.0, px=10.0, maker=True, tid=None):
    return [t, coin, px, sz, side, start, d, pnl, .01, maker, False, tid if tid is not None else t]


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

    def test_only_profitable_active_traders_are_followed(self):
        rows = W.slim({"leaderboardRows": [lb_row("trader", 1e6, 5e6, 1e5, 5e6), lb_row("maker", 1e6, 9e6, 1e5, 5e8), lb_row("idle", 1e6, 8e6, 1e5, 0),
                                           lb_row("loser", 1e6, -3e6, -1e5, 2e6), lb_row("small", 50_000, 7e6, 1e5, 1e5)]})
        c = W.choose(rows)
        self.assertEqual(c, {"trader": "vincenti storici"})

    def test_vaults_need_money_age_and_profit_and_skip_the_exchange_own(self):
        now = datetime(2026, 11, 6, tzinfo=timezone.utc)
        old = (now.timestamp() - 200 * 86400) * 1000
        v = lambda name, tvl, pnl, created=old, closed=False: {"apr": .1, "pnls": [["allTime", ["0", str(pnl)]]], "summary": {"name": name, "vaultAddress": name, "leader": "x", "tvl": str(tvl), "isClosed": closed, "createTimeMillis": created}}
        raw = [v("good", 5e5, 1e5), v("small", 5e4, 1e5), v("young", 5e5, 1e5, created=now.timestamp() * 1000), v("losing", 5e5, -1), v("closed", 5e5, 1e5, closed=True), v("HLP Strategy A", 5e6, 1e6)]
        self.assertEqual(list(W.choose_vaults(raw, now)), ["good"])


class TestPositions(Base):
    def test_flows_count_sides_and_net_dollars(self):
        snap = {"at": "2026-11-06T13:00:00+00:00", "wallets": {
            "a": {"cohort": "vincenti storici", "positions": [["", "BTC", -2.0, 1, 500.0, 3, 0, None]]},
            "b": {"cohort": "vincenti del mese", "positions": [["", "BTC", 1.0, 1, 200.0, 3, 0, None]]},
            "c": {"cohort": "vault", "positions": [["xyz", "xyz:GOLD", 3.0, 1, 300.0, 3, 0, None]]}}}
        f = W.flows(snap, W.kind_of)
        self.assertEqual(f["BTC"]["trader"], {"long": 1, "short": 1, "net": -300.0})
        self.assertEqual(f["xyz:GOLD"]["vault"]["net"], 300.0)
        self.assertIn("BTC", W.flows_text(snap))

    def test_a_round_reads_both_dexes_and_survives_a_failure(self):
        def http(url, body=None, timeout=0):
            if body["user"] == "bad":
                raise OSError("down")
            return state(("BTC", -1, 100)) if body["dex"] == "" else state(("xyz:GOLD", 2, 50))
        with mock.patch.object(W, "http", http):
            snap = W.take_positions({"good": "vincenti storici", "bad": "vault"}, datetime(2026, 11, 6, 13, tzinfo=timezone.utc), sleep=lambda s: None, log=lambda m: None)
        self.assertEqual([p[1] for p in snap["good"]["positions"]], ["BTC", "xyz:GOLD"])
        self.assertEqual(snap["good"]["capital"], 2000)
        self.assertEqual(W.latest_positions()["failed"], 1)

    def test_leaderboard_and_fills_once_a_day_positions_once_an_hour(self):
        calls = []
        with mock.patch.object(W, "take_leaderboard", side_effect=lambda now: calls.append("lb") or ([], {"a": "vincenti storici"})), \
             mock.patch.object(W, "take_positions", side_effect=lambda c, now, log=None: calls.append("pos")), \
             mock.patch.object(W, "update_fills", side_effect=lambda c, now, log=None: calls.append("fills")):
            st = {}
            t = datetime(2026, 11, 6, 13, 5, tzinfo=timezone.utc)
            W.cycle(st, t, log=lambda m: None)
            W.cycle(st, t.replace(minute=40), log=lambda m: None)
            W.cycle(st, t.replace(hour=14, minute=1), log=lambda m: None)
        self.assertEqual(calls, ["lb", "pos", "fills", "pos"])


class TestStrategy(unittest.TestCase):
    def test_round_trips_go_flat_to_flat_and_handle_a_flip(self):
        h = 3_600_000
        fills = [fill(0, "BTC", "B", 1, 0, "Open Long"), fill(2 * h, "BTC", "A", 1, 1, "Close Long", pnl=5),
                 fill(3 * h, "ETH", "A", 2, 0, "Open Short"), fill(5 * h, "ETH", "B", 3, -2, "Long > Short", pnl=-1), fill(9 * h, "ETH", "A", 1, 1, "Close Long", pnl=2)]
        trips = W.round_trips(fills)
        self.assertEqual([(t["coin"], t["side"], (t["close"] - t["open"]) // h) for t in trips], [("BTC", 1, 2), ("ETH", -1, 2), ("ETH", 1, 4)])
        self.assertAlmostEqual(trips[0]["pnl"], 5 - .02)

    def test_a_position_open_before_the_history_is_left_out(self):
        self.assertEqual(W.round_trips([fill(0, "BTC", "A", 1, 3, "Close Long", pnl=1)]), [])

    def test_profile_reads_style_direction_and_execution(self):
        d = 86_400_000
        fills = []
        for k in range(6):
            fills += [fill(k * 3 * d, "BTC", "B", 1, 0, "Open Long", tid=2 * k), fill(k * 3 * d + 2 * d, "BTC", "A", 1, 1, "Close Long", pnl=1 if k % 3 else -1, tid=2 * k + 1)]
        p = W.profile(fills)
        self.assertAlmostEqual(p["hold_days"], 2)
        self.assertEqual(p["long_share"], 1)
        self.assertEqual(p["maker_share"], 1)
        self.assertIn("Swing trader", p["sentence"])
        self.assertIn("soprattutto long", p["sentence"])
        self.assertIn("concentrato su BTC", p["sentence"])
        self.assertIn("ordini limite", p["sentence"])

    def test_without_closed_positions_the_hold_comes_from_turnover(self):
        d = 86_400_000
        fills = [fill(0, "ETH", "B", 10, 100, "Open Long", px=100), fill(10 * d, "ETH", "A", 10, 110, "Close Long", px=100, pnl=3)]
        p = W.profile(fills, gross=50_000)  # $2,000 traded over 10 days: $100 out and $100 in a day
        self.assertIsNone(p["hold_days"])
        self.assertAlmostEqual(p["hold_estimate"], 500)
        self.assertIn("circa", p["sentence"])

    def test_structure_names_a_hedged_bet_and_a_long_short_book(self):
        r = lambda c, side, v: {"coin": c, "side": side, "value": v}
        hedged = W.structure([r("HYPE", "long", 100), r("W", "short", 15), r("ZRO", "short", 15)], 100)
        self.assertIn("coperto da short su 2 mercati", hedged)
        book = W.structure([r("BTC", "long", 40), r("ETH", "short", 35), r("SOL", "long", 10), r("DOGE", "short", 15)], 100)
        self.assertIn("long-short", book)
        self.assertIn("non ha posizioni", W.structure([], 100))

    def test_merging_keeps_each_fill_once(self):
        a = [fill(1, "BTC", "B", 1, 0, "Open Long", tid=7)]
        self.assertEqual(len(W.merge_fills(a, a, [fill(2, "BTC", "A", 1, 1, "Close Long", tid=8)])), 2)


if __name__ == "__main__":
    unittest.main()
