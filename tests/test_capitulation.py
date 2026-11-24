import unittest

import numpy as np
import pandas as pd

from bzd import capitulation as CP


def bars(close):
    c = pd.Series(close, index=pd.date_range("2015-01-01", periods=len(close), freq="D"))
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * .999, "close": c})


def path(rise=1200, fall=120, flat=80, fall_to=.4, noise_up=.02, noise_flat=.003, seed=1):
    """Years of noisy rise to a high, a noisy crash to fall_to of the high, then a quiet sideways range."""
    r = np.random.default_rng(seed)
    up = 100 * np.exp(np.cumsum(r.normal(.004, noise_up, rise)))
    down = up[-1] * np.exp(np.linspace(0, np.log(fall_to), fall) + r.normal(0, .04, fall))
    side = down.min() * 1.05 * np.exp(r.normal(0, noise_flat, flat))
    return np.concatenate([up, down, side])


class TestCapitulation(unittest.TestCase):
    def test_fires_after_crash_then_quiet_sideways(self):
        out = CP.check(bars(path()))
        self.assertTrue(all(c["ok"] for c in out["conditions"]), out["conditions"])
        self.assertTrue(out["fired"])
        self.assertEqual(out["met"], 4)

    def test_not_while_still_falling(self):
        p = path(flat=0)
        out = CP.check(bars(p))
        self.assertFalse(out["fired"])
        self.assertFalse(next(c for c in out["conditions"] if c["key"] == "tempo")["ok"])

    def test_not_after_a_small_dip(self):
        out = CP.check(bars(path(fall_to=.9)))
        self.assertFalse(out["fired"])
        self.assertFalse(next(c for c in out["conditions"] if c["key"] == "prezzo")["ok"])

    def test_short_history_says_nothing(self):
        self.assertIsNone(CP.check(bars(np.linspace(100, 50, 300))))

    def test_only_strong_markets(self):
        self.assertIsNone(CP.of("EURUSD=X"))
        self.assertIn("BTC", CP.STRONG)


if __name__ == "__main__":
    unittest.main()
