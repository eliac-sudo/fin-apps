import unittest

import numpy as np
import pandas as pd

from bzd import v7


class V7(unittest.TestCase):
    def test_rule_count_matches_the_preregistration(self):
        cfg = v7.load_config()
        self.assertEqual(len(v7.conditions(list(cfg["features"]))) * 2, 484)

    def test_events_end_inside_their_period(self):
        idx = pd.date_range("2018-12-01", "2019-01-31", freq="B", tz="UTC")
        n = len(idx)
        flags = np.zeros(n, bool)
        flags[idx.searchsorted(pd.Timestamp("2018-12-20", tz="UTC"))] = True  # exit would fall in January
        flags[idx.searchsorted(pd.Timestamp("2018-12-03", tz="UTC"))] = True  # exit inside December
        data = {"X": {"index": idx, "ret": np.full(n, 0.01), "year": idx.year.values, "f": {"a": (flags, flags)}}}
        ev = v7.events(data, (("a", "lo"),), ("2018-01-01", "2019-01-01"), 10)
        self.assertEqual([e[1][:10] for e in ev], ["2018-12-03"])

    def test_year_means_ignore_returns_that_leave_the_period(self):
        idx = pd.date_range("2018-12-03", "2019-01-31", freq="B", tz="UTC")
        ret = np.where(idx <= pd.Timestamp("2018-12-18", tz="UTC"), 0.01, 0.5)  # Dec 18 + 9 sessions = Dec 31, the last one inside
        data = {"X": {"index": idx, "ret": ret, "year": idx.year.values}}
        self.assertAlmostEqual(v7.year_means(data, ("2018-01-01", "2019-01-01"), 10)["X"][2018], 0.01)

    def test_past_percentile_uses_only_earlier_values(self):
        s = pd.Series([1.0, 2, 3, 4, 5, 6, 0])
        p = v7.rolling_past_pct(s, 4)
        self.assertEqual(p.iloc[4], 100.0)
        self.assertEqual(p.iloc[6], 0.0)


if __name__ == "__main__":
    unittest.main()
