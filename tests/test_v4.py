import unittest
from unittest import mock

import numpy as np

from bzd import v4 as V


class TestV4(unittest.TestCase):
    def test_streak_fires_once_on_the_nth_bar_of_each_run(self):
        f = np.array([1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1], bool)
        self.assertEqual(list(np.flatnonzero(V.streak_start(f, 3))), [2, 10])

    def test_byz_is_short_and_szt_is_long(self):
        self.assertTrue(all(V.SIGN[k] == -1 for k in ("N1", "N3", "N5")))
        self.assertTrue(all(V.SIGN[k] == 1 for k in ("N2", "N4", "N6")))

    def test_no_market_of_the_program_is_in_the_test(self):
        from bzd.history import CRYPTO, ETF_CHECK, MARKETS
        from bzd.option_lab import BY_KEY
        used = {*CRYPTO, *MARKETS, *ETF_CHECK.values(), *BY_KEY}
        self.assertFalse(used & {m for _, m in V.markets(V.load_config())})

    def test_counting_computes_no_return(self):
        boom = mock.Mock(side_effect=AssertionError("a return was computed"))
        with mock.patch.object(V, "horizon_returns", boom), mock.patch.object(V.V3, "pick_excess", boom):
            rows, used = V.collect(V.load_config(), count_only=True)
        self.assertTrue(all(r[3] is None for k in rows for r in rows[k]))


if __name__ == "__main__":
    unittest.main()
