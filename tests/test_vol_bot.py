import os, tempfile, unittest
from datetime import datetime, timedelta, timezone

from bzd import vol_bot as B
from bzd.option_models import delta_gamma

MON = datetime(2026, 11, 23, 11, tzinfo=timezone.utc)  # a Monday inside the entry window
EXP = datetime(2026, 12, 25, 8, tzinfo=timezone.utc)
F = 61500.0
INST = {"tick_size": 5.0, "tick_size_steps": [{"tick_size": 20.0, "above_price": 3000.0}], "min_trade_amount": 0.01}
PERP = {"tick_size": 0.1, "min_trade_amount": 0.0001}
STRIKES = [50000, 54000, 56000, 58000, 60000, 64000, 66000, 68000, 72000]


def name(k, typ):
    return f"BTC_USDC-25DEC26-{k}-{typ}"


def bs_delta(k, typ, now=MON):
    years = (EXP - now).total_seconds() / (365 * 86400)
    return float(delta_gamma(F, k, years, .55, typ == "C")[0])


class FakeClient:
    """Options at vol 55 on every strike, quotes 20 wide around a fixed mid. Post-only sells fill in full if maker_fill,
    else they rest. Takers fill in full at the far side."""
    base = B.URLS["test"]

    def __init__(self, equity=100000.0, maker_fill=True):
        self.equity, self.maint, self.maker_fill = equity, 0.0, maker_fill
        self.pos, self.orders, self.calls, self.deliv = {}, {}, [], []
        self.q = {}
        for k in STRIKES:
            for typ in ("P", "C"):
                self.q[name(k, typ)] = {"bid": 1500.0, "ask": 1520.0, "delta": bs_delta(k, typ)}
        self.q["BTC_USDC-PERPETUAL"] = {"bid": F - 1, "ask": F + 1, "delta": 1.0}

    def call(self, method, **p):
        self.calls.append((method, p))
        n = p.get("instrument_name")
        if method == "public/get_instruments":
            return [{"instrument_name": x, "expiration_timestamp": int(EXP.timestamp() * 1000), **INST} for x in self.q if x != "BTC_USDC-PERPETUAL"]
        if method == "public/get_instrument":
            return PERP if n == "BTC_USDC-PERPETUAL" else INST
        if method == "public/get_book_summary_by_currency":
            return [{"instrument_name": x, "mark_iv": 55, "underlying_price": F} for x in self.q if x != "BTC_USDC-PERPETUAL"]
        if method == "public/get_order_book":
            q = self.q[n]
            return {"best_bid_price": q["bid"], "best_ask_price": q["ask"], "underlying_price": F}
        if method == "public/get_delivery_prices":
            return {"data": self.deliv}
        if method == "private/get_account_summary":
            return {"equity": self.equity, "maintenance_margin": self.maint}
        if method == "private/get_positions":
            if p["kind"] == "future":
                btc = self.pos.get("BTC_USDC-PERPETUAL", 0)
                return [{"instrument_name": "BTC_USDC-PERPETUAL", "size": btc * F, "size_currency": btc}]  # Deribit gives dollars in size
            return [{"instrument_name": x, "size": s, "delta": s * self.q[x]["delta"]} for x, s in self.pos.items() if s and x != "BTC_USDC-PERPETUAL"]
        if method in ("private/buy", "private/sell"):
            oid = str(len(self.orders))
            sign = 1 if method == "private/buy" else -1
            filled = p["amount"] if (not p.get("post_only") or self.maker_fill) else 0.0
            self.pos[n] = round(self.pos.get(n, 0) + sign * filled, 8)
            o = {"order_id": oid, "instrument_name": n, "amount": p["amount"], "price": p["price"], "filled_amount": filled,
                 "average_price": p["price"] if filled else 0.0,
                 "order_state": "filled" if filled else ("cancelled" if p.get("time_in_force") == "immediate_or_cancel" else "open")}
            self.orders[oid] = o
            return {"order": dict(o)}
        if method == "private/edit":
            o = self.orders[p["order_id"]]
            o.update(price=p["price"], amount=p["amount"])
            return {"order": dict(o)}
        if method == "private/get_order_state":
            return dict(self.orders[p["order_id"]])
        if method == "private/cancel":
            self.orders[p["order_id"]]["order_state"] = "cancelled"
            return dict(self.orders[p["order_id"]])
        raise AssertionError(method)

    def fill(self, oid):
        """A resting maker order gets hit."""
        o = self.orders[oid]
        self.pos[o["instrument_name"]] = round(self.pos.get(o["instrument_name"], 0) - (o["amount"] - o["filled_amount"]), 8)
        o.update(filled_amount=o["amount"], average_price=o["price"], order_state="filled")


class TestRules(unittest.TestCase):
    cfg = B.load_config()

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

    def test_maker_price_is_the_mid_on_tick_never_on_the_bid(self):
        self.assertEqual(B.maker_price(1515, 1535, INST), 1525)
        self.assertEqual(B.maker_price(1515, 1520, INST), 1520)
        self.assertEqual(B.maker_price(3000, 3020, INST), 3020)  # above 3000 the tick is 20
        self.assertEqual(B.maker_price(100, 105, INST), 105)

    def test_strangle_takes_the_out_of_the_money_legs_nearest_25_delta(self):
        legs = B.choose_strangle([{"instrument_name": x, "mark_iv": 55, "underlying_price": F} for k in STRIKES for x in (name(k, "P"), name(k, "C"))],
                                 int(EXP.timestamp() * 1000), MON, self.cfg)
        put_k, call_k = B.parse_name(legs["put"])[1], B.parse_name(legs["call"])[1]
        self.assertLess(put_k, F)
        self.assertGreater(call_k, F)
        for k, typ in ((put_k, "P"), (call_k, "C")):
            others = [abs(abs(bs_delta(s, typ)) - .25) for s in STRIKES if (s < F) == (typ == "P")]
            self.assertAlmostEqual(abs(abs(bs_delta(k, typ)) - .25), min(others))

    def test_size_is_a_quarter_of_equity_and_one_times_in_all(self):
        self.assertEqual(B.entry_amount(100000, F, 0, self.cfg, .01), 0.40)
        self.assertEqual(B.entry_amount(100000, F, 1.5, self.cfg, .01), 0.12)
        self.assertEqual(B.entry_amount(100000, F, 1.7, self.cfg, .01), 0.0)
        self.assertEqual(B.entry_amount(2000, F, 0, self.cfg, .01), 0.0)  # too small for one lot

    def test_hedge_flattens_delta_above_the_minimum(self):
        self.assertEqual(B.hedge_trade(-.05, 0, .001), .05)
        self.assertEqual(B.hedge_trade(.03, -.01, .001), -.02)
        self.assertEqual(B.hedge_trade(.0004, 0, .001), 0.0)

    def test_a_hedge_bigger_than_the_options_is_refused(self):
        self.assertTrue(B.hedge_sane(-.1, .8, 0))
        self.assertTrue(B.hedge_sane(.5, 0, -.5))  # flattening the old hedge is fine
        self.assertFalse(B.hedge_sane(152.99, .01, -.0025))  # the dollars-for-BTC mix-up seen on the testnet

    def test_windows(self):
        self.assertTrue(B.in_entry_window(MON, self.cfg))
        self.assertFalse(B.in_entry_window(MON.replace(hour=16), self.cfg))
        self.assertFalse(B.in_entry_window(MON + timedelta(days=1), self.cfg))
        self.assertTrue(B.hedge_due(MON.replace(hour=8), None, self.cfg))
        self.assertFalse(B.hedge_due(MON.replace(hour=7), None, self.cfg))
        self.assertFalse(B.hedge_due(MON.replace(hour=9), MON.date().isoformat(), self.cfg))


class TestBot(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.sent = []

    def tearDown(self):
        self.dir.cleanup()

    def bot(self, c, now):
        return B.Bot(c, root=self.dir.name, notify=self.sent.append, now=lambda: now, log=lambda *a: None)

    def net_delta(self, c):
        return sum(s * c.q[x]["delta"] for x, s in c.pos.items() if x != "BTC_USDC-PERPETUAL") + c.pos.get("BTC_USDC-PERPETUAL", 0)

    def sells(self, c):
        return [p for m, p in c.calls if m == "private/sell" and p.get("post_only")]

    def perp_trades(self, c):
        return [p for m, p in c.calls if p.get("instrument_name") == "BTC_USDC-PERPETUAL" and m in ("private/buy", "private/sell")]

    def test_monday_entry_sells_both_legs_as_maker_and_hedges(self):
        c = FakeClient()
        b = self.bot(c, MON)
        b.cycle()
        s = self.sells(c)
        self.assertEqual(len(s), 2)
        self.assertTrue(all(p["price"] == 1510 and p["amount"] == 0.40 for p in s))  # mid of 1500/1520
        self.assertEqual(len(b.st["book"]), 1)
        self.assertEqual((b.st["book"][0]["put_amount"], b.st["book"][0]["call_amount"]), (0.40, 0.40))
        self.assertLess(abs(self.net_delta(c)), .001)
        b2 = self.bot(c, MON.replace(hour=16))
        b2.cycle()
        self.assertIsNone(b2.st["working"])
        self.assertIn("Venduto lo strangle", self.sent[-1])

    def test_one_entry_a_week(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        self.bot(c, MON.replace(hour=12)).cycle()
        self.assertEqual(len(self.sells(c)), 2)

    def test_no_entry_off_monday(self):
        c = FakeClient()
        self.bot(c, MON + timedelta(days=1, hours=1)).cycle()
        self.assertEqual(self.sells(c), [])

    def test_resting_orders_follow_the_book_and_are_cancelled_at_16(self):
        c = FakeClient(maker_fill=False)
        self.bot(c, MON).cycle()
        for x in c.q:
            c.q[x] = dict(c.q[x], bid=1400.0, ask=1420.0)
        self.bot(c, MON.replace(hour=12)).cycle()
        edits = [p for m, p in c.calls if m == "private/edit"]
        self.assertEqual({p["price"] for p in edits}, {1410})
        b = self.bot(c, MON.replace(hour=16))
        b.cycle()
        self.assertEqual(sum(1 for m, _ in c.calls if m == "private/cancel"), 2)
        self.assertEqual(b.st["book"], [])
        self.assertTrue(all(not v for v in c.pos.values()))

    def test_a_fill_between_cycles_is_recorded_and_hedged(self):
        c = FakeClient(maker_fill=False)
        self.bot(c, MON).cycle()
        put_order = next(o for o in c.orders.values() if o["instrument_name"].endswith("-P"))
        c.fill(put_order["order_id"])
        b = self.bot(c, MON.replace(hour=12))
        b.cycle()
        self.assertEqual(b.st["book"][0]["put_amount"], 0.40)
        self.assertEqual(b.st["book"][0]["call_amount"], 0.0)
        self.assertLess(abs(self.net_delta(c)), .001)

    def test_daily_hedge_at_eight_then_not_again_that_day(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        for x in c.q:
            if x.endswith("-P"):
                c.q[x] = dict(c.q[x], delta=c.q[x]["delta"] * 1.5)  # the price fell: puts carry more delta
        tue = (MON + timedelta(days=1)).replace(hour=8, minute=30)
        before = c.pos["BTC_USDC-PERPETUAL"]
        self.bot(c, tue).cycle()
        self.assertNotEqual(before, c.pos["BTC_USDC-PERPETUAL"])
        self.assertLess(abs(self.net_delta(c)), .001)
        n = len(self.perp_trades(c))
        self.bot(c, tue.replace(hour=14)).cycle()
        self.assertEqual(n, len(self.perp_trades(c)))

    def test_emergency_hedge_when_delta_drifts_far(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        put = next(x for x in c.pos if x.endswith("-P"))
        c.q[put] = dict(c.q[put], delta=-.9)  # a crash: the sold put is now deep in the money
        b = self.bot(c, (MON + timedelta(days=1)).replace(hour=3))  # before 08:00
        b.cycle()
        self.assertLess(abs(self.net_delta(c)), .001)
        self.assertTrue(any("fuori orario" in m for m in self.sent))

    def test_margin_above_eighty_percent_closes_everything(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        c.maint = 0.85 * c.equity
        b = self.bot(c, MON.replace(hour=20))
        b.cycle()
        self.assertEqual(b.st["book"], [])
        self.assertTrue(all(abs(v) < 1e-9 for v in c.pos.values()))
        self.assertEqual(b.st["closed"][-1]["reason"], "margine")

    def test_margin_above_half_blocks_entries(self):
        c = FakeClient()
        c.maint = 0.6 * c.equity
        self.bot(c, MON).cycle()
        self.assertEqual(self.sells(c), [])

    def test_kill_switch_stops_entries_until_resumed(self):
        c = FakeClient(equity=80000)
        b = self.bot(c, MON)
        b.st["peak"] = 100000
        b.cycle()
        self.assertTrue(b.st["halted"])
        self.assertEqual(self.sells(c), [])
        B.write_control({"paused": False, "resume": "x"}, self.dir.name)
        b.st["last_week"] = None
        b.cycle()
        self.assertIsNone(b.st["halted"])
        self.assertEqual(len(self.sells(c)), 2)

    def test_unknown_position_blocks_entries(self):
        c = FakeClient()
        c.pos[name(60000, "C")] = -0.05
        b = self.bot(c, MON)
        b.cycle()
        self.assertIsNotNone(b.st["blocked"])
        self.assertEqual(self.sells(c), [])

    def test_insane_hedge_blocks_instead_of_trading(self):
        c = FakeClient()
        c.pos["BTC_USDC-PERPETUAL"] = 0.0
        b = self.bot(c, MON + timedelta(days=1, hours=9))
        c.pos[name(56000, "P")] = -0.01
        b.st["book"] = [{"id": "x", "put": name(56000, "P"), "call": name(68000, "C"), "put_amount": 0.01, "call_amount": 0.0, "cash_in": 15}]
        c.q[name(56000, "P")] = dict(c.q[name(56000, "P")], delta=-500.0)  # a broken reading
        b.cycle()
        self.assertEqual(self.perp_trades(c), [])
        self.assertIn("copertura assurda", b.st["blocked"])

    def test_expiry_records_the_options_result(self):
        c = FakeClient()
        self.bot(c, MON).cycle()
        self.bot(c, MON.replace(hour=16)).cycle()
        p = self.bot(c, MON.replace(hour=17)).st["book"][0]
        kp = B.parse_name(p["put"])[1]
        for x in list(c.pos):
            if x != "BTC_USDC-PERPETUAL":
                c.pos[x] = 0
        c.deliv = [{"date": "2026-12-25", "delivery_price": kp - 1000}]
        b = self.bot(c, EXP + timedelta(hours=1))
        b.cycle()
        self.assertEqual(b.st["book"], [])
        self.assertAlmostEqual(b.st["closed"][0]["pnl_options"], p["cash_in"] - 0.40 * 1000, places=2)
        self.assertLess(abs(c.pos["BTC_USDC-PERPETUAL"]), .001)  # no options left, so the hedge is gone too


if __name__ == "__main__":
    unittest.main()
