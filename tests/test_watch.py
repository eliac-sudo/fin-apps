import unittest

import pandas as pd

from bzd import history as H
from bzd import technicals as K
from bzd import thermo as Z


class Watch(unittest.TestCase):
    def test_watched_markets_never_reach_the_bot_or_the_frozen_lists(self):
        for m in H.WATCH:
            self.assertNotIn(m, H.MARKETS)
            self.assertNotIn(m, K.all_markets())
            self.assertIn(m, K.app_markets())
        self.assertFalse(set(H.WATCH.values()) & set(Z.CLASS_IT))  # the Telegram thermometer keeps to its classes

    def test_every_watched_market_has_a_label_and_a_class_name(self):
        for m, c in H.WATCH.items():
            self.assertIn(m, Z.LABELS)
            self.assertIn(c, H.WATCH_CLASS_IT)

    def test_bundesbank_csv(self):
        raw = '﻿"",X,X_FLAGS\nunit,Prozent,\n1997-08-01,.,No value available\n2026-11-23,3.37,\n2026-11-24,3.33,\n'.encode("utf-8")
        d = H.bund_rows(raw)
        self.assertEqual(d.date.tolist(), ["2026-11-23", "2026-11-24"])
        self.assertEqual(d.value.tolist(), [3.37, 3.33])

    def test_ecb_csv(self):
        raw = b"KEY,TIME_PERIOD,OBS_VALUE\nIRS.M.IT,2026-09,4.362\nIRS.M.IT,2026-10,4.68\n"
        d = H.ecb_10y_rows(raw)
        self.assertEqual(d.date.tolist(), ["2026-09-01", "2026-10-01"])
        self.assertAlmostEqual(d.value.iloc[-1], 4.68)


if __name__ == "__main__":
    unittest.main()
