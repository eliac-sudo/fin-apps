import math, unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np

from bzd import option_lab as L
from bzd import option_models as M

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


class TestBlack76(unittest.TestCase):
    def test_known_value(self):
        # at the money: call = F * (2N(s/2) - 1); F=100, vol 20%, one year
        self.assertAlmostEqual(float(M.black76(100, 100, 1, .2, True)), 7.9656, places=3)

    def test_put_call_parity(self):
        for k in (80, 100, 130):
            c, p = float(M.black76(100, k, .5, .3, True, .98)), float(M.black76(100, k, .5, .3, False, .98))
            self.assertAlmostEqual(c - p, .98 * (100 - k), places=8)

    def test_arrays_mix_calls_and_puts(self):
        v = M.black76(100, np.array([90.0, 110.0]), .5, .3, np.array([False, True]))
        self.assertAlmostEqual(v[0], float(M.black76(100, 90, .5, .3, False)))
        self.assertAlmostEqual(v[1], float(M.black76(100, 110, .5, .3, True)))

    def test_implied_vol_recovers_the_input(self):
        for vol, k, call in ((.15, 95, False), (.8, 120, True), (.3, 100, True)):
            price = float(M.black76(100, k, .25, vol, call, .99))
            self.assertAlmostEqual(M.implied_vol(price, 100, k, .25, call, .99), vol, places=4)

    def test_impossible_price_has_no_vol(self):
        self.assertIsNone(M.implied_vol(1.0, 100, 50, .25, True))
        self.assertIsNone(M.implied_vol(0.0, 100, 100, .25, True))

    def test_forward_resists_one_bad_quote(self):
        k = [98, 99, 100, 101, 102]
        c = [3.0, 2.5, 2.0, 1.5, 1.0]
        p = [1.0, 1.5, 2.0, 2.5, 3.0]
        self.assertAlmostEqual(M.forward_from_parity(k, c, p, 1.0, 100), 100.0)
        c[4] = 50.0
        self.assertAlmostEqual(M.forward_from_parity(k, c, p, 1.0, 100), 100.0)


class TestSVI(unittest.TestCase):
    def test_fit_recovers_a_known_smile(self):
        p = [.01, .1, -.5, .02, .15]
        k = np.linspace(-.3, .3, 25)
        vols = M.svi_vol(k, p, .25)
        fit = M.fit_svi(k, vols, .25)
        self.assertLess(np.abs(M.svi_vol(k, fit, .25) - vols).max(), .002)

    def test_too_few_points(self):
        self.assertIsNone(M.fit_svi([0, .1], [.2, .2], .25))


class TestHar(unittest.TestCase):
    def sim(self, vols, seed=1):
        return np.random.default_rng(seed).standard_normal(len(vols)) * np.asarray(vols)

    def test_steady_market_gets_its_own_volatility(self):
        daily = .01
        f = M.har_forecast(self.sim(np.full(2000, daily)), 21, 252)
        self.assertAlmostEqual(f, daily * math.sqrt(252), delta=.02)

    def test_recent_calm_lowers_the_forecast(self):
        vols = np.r_[np.tile(np.r_[np.full(100, .02), np.full(100, .005)], 10)]
        calm = M.har_forecast(self.sim(vols), 21, 252)
        busy = M.har_forecast(self.sim(np.r_[vols, np.full(100, .02)]), 21, 252)
        self.assertLess(calm, busy)

    def test_too_little_data(self):
        self.assertIsNone(M.har_forecast(np.zeros(50), 21, 252))

    def test_future_returns_cannot_enter_the_fit(self):
        r = self.sim(np.full(1000, .01))
        changed = r.copy()
        changed[-1] = .2  # the newest return moves the inputs, so the forecast rises, but only through today's inputs
        self.assertGreater(M.har_forecast(changed, 21, 252), M.har_forecast(r, 21, 252))


class TestGex(unittest.TestCase):
    def test_flip_sits_between_put_and_call_gamma(self):
        k, call = np.array([90.0, 110.0]), np.array([False, True])
        oi, iv, y = np.array([100.0, 100.0]), np.array([.2, .2]), np.array([.1, .1])
        self.assertAlmostEqual(M.gamma_flip(k, call, oi, iv, y, 100, 100), 100, delta=2)

    def test_no_flip_when_only_calls(self):
        k, call = np.array([110.0]), np.array([True])
        self.assertIsNone(M.gamma_flip(k, call, np.array([10.0]), np.array([.2]), np.array([.1]), 100, 100))

    def test_max_pain(self):
        self.assertEqual(M.max_pain([90, 100, 110], np.array([False, False, True]), [10, 10, 10]), 100)


class TestLab(unittest.TestCase):
    """A synthetic chain priced at 30% vol: the model must call it dear when it forecasts 15% and cheap when it forecasts 60%."""

    def chain(self, vol=.3, spread=.02):
        rows, exp = [], NOW + timedelta(days=30)
        for k in range(70, 131, 2):
            for call in (True, False):
                v = float(M.black76(100, k, 30 / 365, vol, call))
                rows.append({"code": f"X{k}{'C' if call else 'P'}", "expiry": exp, "is_call": call, "strike": float(k), "bid": v * (1 - spread), "ask": v * (1 + spread), "oi": 500.0, "volume": 10.0})
        return rows

    MARKET = {"key": "X", "name": "X", "ticker": "X", "kind": "cboe", "group": "g", "job": "x", "under": ("tradfi", "X")}

    def run_lab(self, vol, spread=.02):
        with mock.patch.object(L, "forecast_at", return_value=vol):
            return L.analyze_chain(self.MARKET, self.chain(spread=spread), 100.0, 100, NOW, [0.0], .2, 252, 0.0)

    def test_forecast_below_implied_means_dear(self):
        r = self.run_lab(.15)
        self.assertEqual(r["label"], "care")
        self.assertGreater(r["n_dear"], 0)
        self.assertEqual(r["n_cheap"], 0)
        self.assertGreater(r["dear"][0]["bid"], r["dear"][0]["fair"])

    def test_forecast_above_implied_means_cheap(self):
        r = self.run_lab(.6)
        self.assertEqual(r["label"], "economiche")
        self.assertGreater(r["n_cheap"], 0)
        self.assertLess(r["cheap"][0]["ask"], r["cheap"][0]["fair"])

    def test_implied_recovered_at_the_money(self):
        self.assertAlmostEqual(self.run_lab(.3)["near"]["atm"], .3, delta=.01)

    def test_a_gap_inside_the_spread_is_neutral(self):
        r = self.run_lab(.3, spread=.2)
        self.assertEqual(r["n_cheap"] + r["n_dear"], 0)

    def test_ranked_by_volatility_points_not_by_cheap_lottery_tickets(self):
        r = self.run_lab(.15)
        self.assertTrue(all(abs(c["delta"]) >= L.DELTA_RANGE[0] for c in r["dear"]))
        gaps = [c["gap_vol"] for c in r["dear"]]
        self.assertEqual(gaps, sorted(gaps, reverse=True))

    def test_no_forecast_means_no_verdict(self):
        with mock.patch.object(L, "forecast_at", return_value=None):
            r = L.analyze_chain(self.MARKET, self.chain(), 100.0, 100, NOW, [0.0], .2, 252, 0.0)
        self.assertIsNone(r["label"])
        self.assertEqual(r["n_tradable"], 0)

    def test_gex_has_levels(self):
        g = self.run_lab(.3)["gex"]
        self.assertIn(g["regime"], ("positiva", "negativa"))
        self.assertEqual(g["put_call_oi"], 1)
        self.assertTrue(g["by_strike"])


class TestParsers(unittest.TestCase):
    def test_cboe(self):
        rows, spot, mult, _ = L.parse_cboe_chain({"data": {"symbol": "SPY", "current_price": 700.0, "options": [{"option": "SPY261204P00650000", "bid": 1, "ask": 2, "open_interest": 3, "volume": 4}, {"option": "B1SPY261204P00650000", "bid": 1, "ask": 2}]}})
        self.assertEqual((len(rows), rows[0]["strike"], rows[0]["is_call"], spot, mult), (1, 650, False, 700, 100))

    def test_deribit_converts_coins_to_dollars(self):
        rows, spot, mult, _ = L.parse_deribit_chain({"result": [{"instrument_name": "BTC-27NOV26-70000-P", "bid_price": .01, "ask_price": .02, "open_interest": 5, "volume": 1, "underlying_price": 80000.0, "estimated_delivery_price": 79900.0}]})
        self.assertEqual((rows[0]["bid"], rows[0]["ask"], rows[0]["forward"], spot, mult), (800, 1600, 80000, 79900, 1))
