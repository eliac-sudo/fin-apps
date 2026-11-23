import os, tempfile, unittest
from datetime import datetime, timedelta, timezone

from bzd import vol_bot as B

NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)
EXP = datetime(2026, 12, 25, 8, tzinfo=timezone.utc)
INST = {"tick_size": 5.0, "tick_size_steps": [{"tick_size": 20.0, "above_price": 3000.0}]}


def put(strike, bid, ask, delta):
    return {"name": f"BTC_USDC-25DEC26-{strike}-P", "strike": strike, "bid": bid, "ask": ask, "delta": delta}


CHAIN = [put(60000, 2740, 2770, -.40), put(56000, 1515, 1535, -.21), put(54000, 1125, 1145, -.15), put(50000, 640, 655, -.07), put(45000, 300, 320, -.03)]


class FakeClient:
    """Fills every limit order in full at its price, unless the instrument is listed in `refuse`."""
    base = B.URLS["test"]

    def __init__(self, equity=10000.0, refuse=()):
        self.equity, self.refuse, self.pos, self.orders, self.calls = equity, set(refuse), {}, {}, []
        self.quotes = {p["name"]: p for p in CHAIN}

    def call(self, method, **p):
        self.calls.append((method, p))
        if method == "public/get_instruments":
            return [{"instrument_name": q["name"], "base_currency": "BTC", "option_type": "put", "strike": q["strike"],
                     "expiration_timestamp": int(EXP.timestamp() * 1000), **INST} for q in CHAIN]
        if method == "public/get_book_summary_by_currency":
            return [{"instrument_name": q["name"], "bid_price": q["bid"], "ask_price": q["ask"], "mark_iv": 55, "underlying_price": 61500}
                    for q in self.quotes.values()]
        if method == "public/get_instrument":
            return INST
        if method == "public/ticker":
            q = self.quotes[p["instrument_name"]]
            return {"best_bid_price": q["bid"], "best_ask_price": q["ask"], "greeks": {"delta": q["delta"]}, "underlying_price": 61500}
        if method == "private/get_account_summary":
            return {"equity": self.equity}
        if method == "private/get_positions":
            return [{"instrument_name": k, "size": v} for k, v in self.pos.items() if v]
        if method in ("private/buy", "private/sell"):
            oid = str(len(self.orders))
            name, amt = p["instrument_name"], p["amount"]
            filled = 0 if name in self.refuse else amt
            self.pos[name] = round(self.pos.get(name, 0) + (filled if method == "private/buy" else -filled), 8)
            o = {"order_id": oid, "order_state": "filled" if filled else "open", "filled_amount": filled, "average_price": p["price"]}
            self.orders[oid] = o
            return {"order": o}
        if method == "private/edit":
            return {"order": self.orders[p["order_id"]]}
        if method == "private/get_order_state":
            return self.orders[p["order_id"]]
        if method == "private/cancel":
            self.orders[p["order_id"]]["order_state"] = "cancelled"
            return self.orders[p["order_id"]]
        raise AssertionError(method)


class TestRules(unittest.TestCase):
    def setUp(self):
        self.cfg = B.load_config()

    def test_testnet_unless_live_is_asked_for_twice(self):
        old = dict(os.environ)
        try:
            os.environ.pop("DERIBIT_NETWORK", None)
            self.assertEqual(B.network(), "test")
            os.environ["DERIBIT_NETWORK"] = "live"
            os.environ.pop("BZD_BOT_LIVE", None)
            with self.assertRaises(SystemExit):
                B.network()
            os.environ["BZD_BOT_LIVE"] = B.LIVE_SWITCH
            self.assertEqual(B.network(), "live")
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_names_and_ticks(self):
        self.assertEqual(B.parse_name("BTC_USDC-25DEC26-55000-P")[1:], (55000.0, True))
        self.assertEqual(B.parse_name("AVAX_USDC-24NOV26-7d5-C")[1], 7.5)
        self.assertEqual(B.tick_for(INST, 1500), 5.0)
        self.assertEqual(B.tick_for(INST, 3500), 20.0)

    def test_prices_walk_from_mid_to_far_side_on_tick(self):
        self.assertEqual(B.limit_price("sell", 1515, 1535, 0, 5, INST), 1525)
        self.assertEqual(B.limit_price("sell", 1515, 1535, 5, 5, INST), 1515)
        self.assertEqual(B.limit_price("buy", 640, 655, 0, 5, INST), 650)
        self.assertEqual(B.limit_price("buy", 640, 655, 5, 5, INST), 655)

    def test_expiry_nearest_thirty_days_in_range(self):
        ms = lambda d: int((NOW + timedelta(days=d)).timestamp() * 1000)
        insts = [{"expiration_timestamp": ms(d)} for d in (4, 11, 32, 123)]
        self.assertEqual(B.choose_expiry(insts, NOW, self.cfg), ms(32))
        self.assertIsNone(B.choose_expiry(insts[:2], NOW, self.cfg))

    def test_legs_short_near_twenty_delta_wing_below(self):
        legs = B.choose_legs(CHAIN, self.cfg)
        self.assertEqual((legs["short"]["strike"], legs["long"]["strike"]), (56000, 50000))
        self.assertEqual(legs["credit"], 1515 - 655)

    def test_wide_quotes_or_thin_credit_are_skipped(self):
        wide = [dict(p, bid=p["bid"] / 3) for p in CHAIN]
        self.assertIsNone(B.choose_legs(wide, self.cfg))
        thin = [put(56000, 680, 690, -.21), put(50000, 640, 655, -.07)]
        self.assertIsNone(B.choose_legs(thin, self.cfg))

    def test_size_respects_trade_and_total_caps(self):
        # width 6000, credit 860: 5140 per BTC. 3% of 10000 = 300 -> 0.05 BTC
        self.assertEqual(B.size(10000, 0, 6000, 860, self.cfg), 0.05)
        self.assertEqual(B.size(10000, 1100, 6000, 860, self.cfg), 0.01)  # 100 of the 12% left
        self.assertEqual(B.size(10000, 1200, 6000, 860, self.cfg), 0.0)
        self.assertEqual(B.size(1000, 0, 6000, 860, self.cfg), 0.0)  # too small an account for one lot

    def test_exit_at_half_profit_or_near_expiry(self):
        pos = {"expiry": "2026-12-25", "credit": 800.0}
        self.assertIsNone(B.exit_reason(pos, 900, 300, NOW, self.cfg))
        self.assertEqual(B.exit_reason(pos, 500, 120, NOW, self.cfg), "profitto preso")
        self.assertEqual(B.exit_reason(pos, 900, 300, EXP - timedelta(days=6), self.cfg), "scadenza vicina")

    def test_a_sold_put_needs_a_lower_wing(self):
        n = "BTC_USDC-25DEC26-%d-P"
        self.assertEqual(B.uncovered([{"instrument_name": n % 56000, "size": -.05}, {"instrument_name": n % 50000, "size": .05}]), {})
        self.assertEqual(B.uncovered([{"instrument_name": n % 56000, "size": -.05}, {"instrument_name": n % 50000, "size": .03}]), {n % 56000: .02})
        self.assertEqual(B.uncovered([{"instrument_name": n % 56000, "size": -.05}, {"instrument_name": n % 60000, "size": .05}]), {n % 56000: .05})
        self.assertEqual(B.uncovered([{"instrument_name": n % 56000, "size": -.05}, {"instrument_name": n % 56000 + "x", "size": 0}]), {n % 56000: .05})
        other = "BTC_USDC-26MAR27-50000-P"
        self.assertEqual(B.uncovered([{"instrument_name": n % 56000, "size": -.05}, {"instrument_name": other, "size": .05}]), {n % 56000: .05})
        self.assertEqual(B.uncovered([{"instrument_name": "BTC_USDC-25DEC26-70000-C", "size": -.01}]), {"BTC_USDC-25DEC26-70000-C": .01})


class TestBot(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.sent = []

    def tearDown(self):
        self.dir.cleanup()

    def bot(self, client, now=NOW):
        return B.Bot(client, root=self.dir.name, notify=self.sent.append, sleep=lambda s: None, now=lambda: now, log=lambda *a: None)

    def order_methods(self, c):
        return [(m.split("/")[1], p["instrument_name"]) for m, p in c.calls if m in ("private/buy", "private/sell")]

    def test_entry_buys_the_wing_before_selling_the_put(self):
        c = FakeClient()
        b = self.bot(c)
        b.cycle()
        # mark vol 55 on every strike: 54000 is the put nearest 20 delta, 50000 the wing nearest 7
        self.assertEqual(self.order_methods(c), [("buy", CHAIN[3]["name"]), ("sell", CHAIN[2]["name"])])
        pos = b.st["book"][0]
        self.assertEqual((pos["short_amount"], pos["long_amount"]), (0.08, 0.08))
        self.assertLessEqual(B.max_loss(pos), 10000 * .03)
        self.assertEqual(B.uncovered(b.positions()), {})
        self.assertIsNone(b.st["blocked"])
        self.assertIn("Aperto", self.sent[-1])

    def test_one_entry_per_period(self):
        c = FakeClient()
        b = self.bot(c)
        b.cycle()
        b.cycle()
        self.assertEqual(len(b.st["book"]), 1)

    def test_put_not_sold_leaves_no_wing_behind(self):
        c = FakeClient(refuse={CHAIN[2]["name"]})
        b = self.bot(c)
        b.cycle()
        self.assertEqual(b.st["book"], [])
        self.assertEqual(c.pos[CHAIN[3]["name"]], 0)
        self.assertEqual(b.st["closed"][0]["reason"], "entrata a metà")

    def test_close_buys_back_the_put_first(self):
        c = FakeClient()
        b = self.bot(c)
        b.cycle()
        c.calls.clear()
        c.quotes[CHAIN[2]["name"]] = dict(CHAIN[2], bid=300, ask=310)
        c.quotes[CHAIN[3]["name"]] = dict(CHAIN[3], bid=100, ask=110)
        b.cycle()
        self.assertEqual(self.order_methods(c)[:2], [("buy", CHAIN[2]["name"]), ("sell", CHAIN[3]["name"])])
        self.assertEqual(b.st["book"], [])
        self.assertGreater(b.st["closed"][0]["pnl"], 0)
        self.assertTrue(all(v == 0 for v in c.pos.values()))

    def test_naked_put_on_the_account_is_bought_back(self):
        c = FakeClient()
        b = self.bot(c)
        b.st["paused"] = True
        c.pos[CHAIN[1]["name"]] = -0.02  # e.g. placed by hand
        B.write_control({"paused": True}, self.dir.name)
        b.cycle()
        self.assertEqual(c.pos[CHAIN[1]["name"]], 0)
        self.assertEqual(b.st["book"], [])

    def test_mismatch_blocks_new_entries(self):
        c = FakeClient()
        c.pos[CHAIN[3]["name"]] = 0.02  # a bought put the bot doesn't know
        b = self.bot(c)
        b.cycle()
        self.assertIsNotNone(b.st["blocked"])
        self.assertEqual(b.st["book"], [])

    def test_kill_switch_stops_entries_until_resumed(self):
        c = FakeClient()
        b = self.bot(c)
        b.st["peak"] = 12000
        c.equity = 10000
        b.st["last_entry"] = None
        b.cycle()
        self.assertTrue(b.st["halted"])
        self.assertEqual(b.st["book"], [])
        B.write_control({"paused": False, "resume": "x"}, self.dir.name)
        b.cycle()
        self.assertIsNone(b.st["halted"])
        self.assertEqual(len(b.st["book"]), 1)

    def test_expired_spreads_are_settled(self):
        c = FakeClient()
        b = self.bot(c)
        b.cycle()
        c.pos = {}
        later = self.bot(c, now=EXP + timedelta(hours=2))
        B.write_control({"paused": True}, self.dir.name)
        later.cycle()
        self.assertEqual(later.st["book"], [])
        self.assertEqual(later.st["closed"][0]["reason"], "scaduta")


if __name__ == "__main__":
    unittest.main()
