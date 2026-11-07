import tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from bzd import v2


def series(close, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(close), freq="B", tz="UTC")
    c = pd.Series(close, idx, dtype=float)
    return pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]), "high": c, "low": c, "close": c})


def small_cfg(**kw):
    cfg = v2.load_config()
    cfg = {**cfg, "signal": {**cfg["signal"], "length": 5}, "cooldown_bars": 3, "horizon_bars": 3, "first_trigger": "2026-01-01", **kw}
    return cfg


class TestFrozen(unittest.TestCase):
    def test_config_matches_the_preregistration(self):
        self.assertIn(v2.config_hash(), v2.DOC.read_text())

    def test_primary_markets_exist_in_the_store(self):
        from bzd.history import MARKETS
        cfg = v2.load_config()
        for markets in cfg["markets"].values():
            for m in markets:
                self.assertIn(m, MARKETS)


class TestEvents(unittest.TestCase):
    def test_cross_above_the_average_after_being_below(self):
        d = series([10, 10, 10, 10, 10, 9, 9, 12, 13, 14, 9, 8, 8, 13])
        self.assertEqual(v2.trigger_positions(d.close, small_cfg()), [7, 13])

    def test_cooldown_skips_a_quick_second_cross(self):
        d = series([10, 10, 10, 10, 10, 9, 12, 9, 12, 9, 9, 13])
        self.assertEqual(v2.trigger_positions(d.close, small_cfg()), [6, 11])

    def test_an_event_does_not_depend_on_later_bars(self):
        base = [10, 10, 10, 10, 10, 9, 9, 12, 13, 14]
        a = v2.trigger_positions(series(base + [1, 1, 1]).close, small_cfg())
        b = v2.trigger_positions(series(base + [50, 60, 70]).close, small_cfg())
        self.assertEqual([p for p in a if p < len(base)], [p for p in b if p < len(base)])

    def test_events_before_the_first_trigger_date_are_ignored(self):
        d = series([10, 10, 10, 10, 10, 9, 9, 12, 13, 14, 9, 8, 8, 13])
        cfg = small_cfg(first_trigger=d.index[10].strftime("%Y-%m-%d"), markets={"fx": ["X"]})
        ev = v2.events(cfg, prices={"X": d})
        self.assertEqual(len(ev), 1)
        self.assertFalse(ev.complete.iloc[0])


class TestTiming(unittest.TestCase):
    def test_due_only_with_enough_clusters_or_after_the_deadline(self):
        cfg = v2.load_config()
        ev = pd.DataFrame({"class": ["fx"] * 3, "market": ["X"] * 3, "trigger": ["2027-01-01", "2027-03-01", "2027-06-01"], "primary": [True] * 3, "complete": [True] * 3})
        self.assertFalse(v2.due(ev, cfg, datetime(2028, 1, 1, tzinfo=timezone.utc))[0])
        self.assertTrue(v2.due(ev, cfg, datetime(2030, 12, 1, tzinfo=timezone.utc))[0])
        self.assertTrue(v2.due(ev, dict(cfg, evaluate={**cfg["evaluate"], "min_clusters": 3}), datetime(2028, 1, 1, tzinfo=timezone.utc))[0])

    def test_the_test_refuses_to_run_early_or_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            res = Path(tmp) / "validation_v2.json"
            empty = pd.DataFrame(columns=["class", "market", "trigger", "primary", "complete"])
            with mock.patch.object(v2, "RESULTS", res), mock.patch.object(v2, "events", return_value=empty), mock.patch.object(v2, "run_test") as run:
                self.assertEqual(v2.main(["test", "--confirm"]), 1)
                res.write_text("{}")
                self.assertEqual(v2.main(["test", "--confirm"]), 1)
                run.assert_not_called()


class TestRun(unittest.TestCase):
    def test_excess_is_measured_against_random_entries_on_fresh_data(self):
        rng = np.random.default_rng(1)
        close = 100 * np.exp(np.cumsum(rng.normal(0, .01, 400)))
        prices = {"X": series(close)}
        cfg = small_cfg(markets={"fx": ["X"]}, primary_classes=["fx"], first_trigger="2026-03-01")
        with mock.patch.object(v2, "config_hash", return_value="h"):
            r = v2.run_test(cfg, prices)
        p = r["primary"]
        self.assertGreater(p["events"], 5)
        self.assertIn(p["outcome"], ("supportata", "non supportata", "non informativa"))
        self.assertLess(abs(p["mean"]), .05)
        self.assertIn("Ipotesi T1", v2.report(r, cfg))
