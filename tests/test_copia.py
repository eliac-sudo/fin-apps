import json, os, tempfile, unittest
from datetime import datetime, timezone

import numpy as np

from bzd import copia as CP
from bzd import v9

CFG = CP.load_config()


def row(a, cap=200_000, vlm=1_000_000, month=1000, all_=1000):
    return {"address": a, "capital": cap, "vlm_month": vlm, "pnl_month": month, "pnl_all": all_}


class Copia(unittest.TestCase):
    def test_pool_leaves_out_small_idle_and_market_makers(self):
        rows = [row("ok"), row("small", cap=50_000), row("idle", vlm=10_000), row("mm", vlm=1e9)]
        self.assertEqual([r["address"] for r in CP.pool(rows, CFG["historical"]["pool"])], ["ok"])

    def test_best_needs_profit_this_month_and_ever(self):
        p = [row("a", month=500), row("b", month=900, all_=-1), row("c", month=100), row("d", month=-5)]
        self.assertEqual(CP.best(p, 3), ["a", "c"])

    def test_random_draw_is_the_same_for_the_same_week(self):
        p = [row(f"x{i}") for i in range(100)]
        a, b = CP.drawn(p, "2026-11-30", 1), CP.drawn(list(reversed(p)), "2026-11-30", 1)
        self.assertEqual(a, b)
        self.assertNotEqual(a, CP.drawn(p, "2026-12-07", 1))

    def test_monday(self):
        self.assertEqual(CP.monday(datetime(2026, 11, 26, tzinfo=timezone.utc)), "2026-11-23")

    def test_weights_cap_leverage_and_average(self):
        # one account 10x long BTC on $100: capped to 3x; one account flat: cash. Average 1.5x
        w = CP.weights([(100.0, {"BTC": 1000.0}), (100.0, {})], 3)
        self.assertAlmostEqual(w["BTC"], 1.5)
        w = CP.weights([(100.0, {"BTC": 100.0, "ETH": -50.0})], 3)
        self.assertEqual(w, {"BTC": 1.0, "ETH": -0.5})

    def test_rebalance_pays_costs_and_respects_deadband(self):
        b = CP.new_book(10_000)
        CP.rebalance(b, {"BTC": 1.0}, {"BTC": 100.0}, CFG["forward"])
        cost = CFG["forward"]["copy"]["fee_per_side"] + CFG["forward"]["copy"]["slippage_per_side"]
        self.assertAlmostEqual(b["units"]["BTC"], 100.0)
        self.assertAlmostEqual(CP.equity(b, {"BTC": 100.0}), 10_000 * (1 - cost))
        trades = b["trades"]
        CP.rebalance(b, {"BTC": 1.005}, {"BTC": 100.0}, CFG["forward"])
        self.assertEqual(b["trades"], trades)  # within 1%: no trade
        CP.rebalance(b, {}, {"BTC": 110.0}, CFG["forward"])  # the accounts left: close
        self.assertNotIn("BTC", b["units"])
        self.assertAlmostEqual(b["cash"], 10_000 * (1 - cost) + 1000 - 11_000 * cost)

    def test_short_gains_when_price_falls(self):
        b = CP.new_book(1000)
        CP.rebalance(b, {"ETH": -1.0}, {"ETH": 10.0}, CFG["forward"])
        self.assertGreater(CP.equity(b, {"ETH": 9.0}), 1090)

    def test_funding_long_pays_positive_rate(self):
        b = CP.new_book(1000)
        b["units"] = {"BTC": 1.0}
        b["cash"] = 900.0
        CP.pay_funding(b, {"BTC": 0.0001}, {"BTC": 100.0}, 2)
        self.assertAlmostEqual(b["funding"], 0.02)
        self.assertAlmostEqual(b["cash"], 899.98)

    def test_step_waits_for_start_and_never_trades_for_real(self):
        self.assertFalse(CP.step({}, CFG, now=datetime(2026, 11, 1, tzinfo=timezone.utc)))
        src = open(CP.__file__).read()
        for word in ("/exchange", "private_key", "eth_account", "secret"):
            self.assertNotIn(word, src)


class V9(unittest.TestCase):
    def test_config_matches_the_preregistration(self):
        self.assertIn(v9.config_hash(), v9.DOC.read_text())

    def test_holm(self):
        r = v9.holm({"a": {"p": 0.01}, "b": {"p": 0.02}, "c": {"p": 0.2}}, 0.05)
        self.assertEqual([r[k]["outcome"] for k in "abc"], ["supportata", "supportata", "non supportata"])

    def test_block_bootstrap(self):
        rng = np.random.default_rng(0)
        self.assertLess(v9.block_p(rng.normal(0.01, 0.01, 200), 2000, 5, 1), 0.01)
        self.assertGreater(v9.block_p(rng.normal(0, 0.01, 200), 2000, 5, 1), 0.01)

    def test_forward_waits_for_the_judging_date(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                d = CP.root()
                lines = ["date,C,R,BTC"] + [f"2026-12-{i:02d},{10000 + i},{10000 - i},{100 + i}" for i in range(1, 11)]
                (d / "giorni.csv").write_text("\n".join(lines) + "\n")
                s = v9.forward_state(CFG, now=datetime(2027, 1, 1, tzinfo=timezone.utc))
                self.assertEqual(s["days"], 9)
                self.assertFalse((d / "giudicate.json").exists())
                s = v9.forward_state(CFG, now=datetime(2027, 6, 1, tzinfo=timezone.utc))
                self.assertEqual(s["hypotheses"]["H2"]["result"]["outcome"], "non informativa")  # 9 days < 120
                self.assertTrue(json.loads((d / "giudicate.json").read_text()))
            finally:
                os.environ.pop("BZD_DATA")

    def write_days(self, d, n, up):
        lines = ["date,C,R,BTC"]
        c = r = 10000.0
        rng = np.random.default_rng(3)
        for i in range(n + 1):
            lines.append(f"d{i:04d},{c:.4f},{r:.4f},100")
            c *= 1 + (0.02 if up else 0) + rng.normal(0, 0.005)
            r *= 1 + rng.normal(0, 0.005)
        (d / "giorni.csv").write_text("\n".join(lines) + "\n")

    def test_strong_copy_passes_at_the_first_look(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                d = CP.root()
                self.write_days(d, 59, True)
                s = v9.forward_state(CFG, now=datetime(2027, 1, 20, tzinfo=timezone.utc))
                self.assertEqual(s["looks_done"], 0)
                self.write_days(d, 60, True)
                s = v9.forward_state(CFG, now=datetime(2027, 1, 25, tzinfo=timezone.utc))
                self.assertEqual(s["looks_done"], 1)
                self.assertEqual(s["hypotheses"]["H2"]["result"]["outcome"], "supportata")
                self.assertEqual(s["hypotheses"]["H2"]["result"]["look"], 1)
                s = v9.forward_state(CFG, now=datetime(2027, 1, 26, tzinfo=timezone.utc))
                self.assertEqual(s["looks_done"], 1)  # the same look is never taken twice
            finally:
                os.environ.pop("BZD_DATA")

    def test_flat_copy_stays_open_until_the_last_look(self):
        with tempfile.TemporaryDirectory() as t:
            os.environ["BZD_DATA"] = t
            try:
                d = CP.root()
                self.write_days(d, 60, False)
                s = v9.forward_state(CFG, now=datetime(2027, 1, 25, tzinfo=timezone.utc))
                self.assertEqual(s["looks_done"], 1)
                self.assertFalse(s["hypotheses"]["H1"]["judged"])
                self.assertFalse(s["hypotheses"]["H2"]["judged"])
                self.assertEqual(s["next_look"]["days"], 120)
                self.write_days(d, 150, False)
                s = v9.forward_state(CFG, now=datetime(2027, 5, 26, tzinfo=timezone.utc))
                self.assertEqual(s["hypotheses"]["H2"]["result"]["outcome"], "non supportata")
                self.assertEqual(s["hypotheses"]["H2"]["result"]["look"], 3)
            finally:
                os.environ.pop("BZD_DATA")

    def test_thresholds_follow_holm(self):
        L = v9.load_looks()
        self.assertEqual(v9.sequential({"H1": 0.00005, "H2": 0.0005}, 0, L), {"H1": 0.0001, "H2": 0.00069})
        self.assertEqual(v9.sequential({"H1": 0.0005, "H2": 0.5}, 0, L), {})
        self.assertIn(v9.seq_hash(), v9.DOC.read_text())


if __name__ == "__main__":
    unittest.main()
