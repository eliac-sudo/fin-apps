import json, unittest
from datetime import datetime, timezone

from bzd import option_paper as P
from bzd import verdicts as V


def leg(code, is_call, strike, bid, ask, delta=None):
    return {"code": code, "is_call": is_call, "strike": strike, "bid": bid, "ask": ask, "delta": delta}


class TestOptionPaper(unittest.TestCase):
    def test_config_is_frozen_before_the_first_entry(self):
        cfg = P.load_config()
        self.assertGreater(cfg["entry"]["first_day"], cfg["frozen"])
        self.assertGreater(cfg["readout"]["not_before"], cfg["entry"]["first_day"])

    def test_sold_legs_fill_at_the_bid_and_bought_legs_at_the_ask(self):
        chain = [leg("P100", False, 100, 4, 5), leg("C100", True, 100, 3, 4)]
        sold = P.choose_leg("put", "atm", -1, chain, [], 100)
        bought = P.choose_leg("call", "atm", 1, chain, [], 100)
        self.assertEqual((sold["price"], bought["price"]), (4, 4))

    def test_a_wide_quote_is_not_filled(self):
        chain = [leg("P100", False, 100, 1, 5), leg("C100", True, 100, 3, 4)]
        self.assertIsNone(P.choose_leg("put", "atm", -1, chain, [], 100, max_spread=.5))

    def test_iron_condor_loses_at_most_its_width_less_the_credit(self):
        legs = [{"is_call": False, "strike": 80, "qty": 1, "price": 1}, {"is_call": False, "strike": 90, "qty": -1, "price": 3},
                {"is_call": True, "strike": 110, "qty": -1, "price": 3}, {"is_call": True, "strike": 120, "qty": 1, "price": 1}]
        cash = 4.0
        self.assertEqual(P.max_loss(legs, cash), 6.0)
        self.assertEqual(cash + P.payoff(legs, 50), -6.0)
        self.assertEqual(cash + P.payoff(legs, 100), 4.0)

    def test_wings_must_sit_beyond_the_sold_legs(self):
        spec = {"legs": [["put", .05, 1], ["put", .16, -1]]}
        deltas = [leg("P90", False, 90, 2, 2.1, -.16), leg("P80", False, 80, 1, 1.1, -.05)]
        self.assertIsNotNone(P.build_legs(spec, [], deltas, 100))
        same = [leg("P90", False, 90, 2, 2.1, -.10)]  # one quote closest to both targets: no wing, so no condor
        self.assertIsNone(P.build_legs(spec, [], same, 100))

    def test_entry_window_takes_one_chain_a_day(self):
        cfg = P.load_config()
        t = lambda d, h: (datetime(2026, 11, d, h, 0, tzinfo=timezone.utc), f"{d}-{h}")
        snaps = [t(9, 10), t(9, 13), t(9, 15), t(9, 22), t(10, 16)]
        picked = P.entry_snapshots({"kind": "cboe"}, snaps, cfg)
        self.assertEqual([f for _, f in picked], ["9-15", "10-16"])
        picked = P.entry_snapshots({"kind": "deribit"}, snaps, cfg)
        self.assertEqual([f for _, f in picked], ["9-13", "10-16"])

    def test_condition_labels(self):
        cfg = P.load_config()
        self.assertEqual([P.label_of(x, cfg) for x in (.8, 1.0, 1.3, None)], ["economiche", "nella norma", "care", None])


class TestVerdicts(unittest.TestCase):
    def test_every_reading_has_a_sentence_from_the_results_file(self):
        res = json.loads(V.RESULTS.read_text())["results"]
        for rid in V.TEXT:
            self.assertTrue(V.line(rid).startswith("Testato"))
            self.assertEqual(V.short(rid) == "test superato", res[rid]["outcome"] == "supportata")

    def test_byz_says_it_went_the_other_way(self):
        self.assertIn("continuato a scendere", V.line("Z1"))


if __name__ == "__main__":
    unittest.main()
