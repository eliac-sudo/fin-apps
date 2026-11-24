import inspect, unittest

import numpy as np
import pandas as pd

from bzd import setups as S

CFG = S.load_config()


def market(n=900, seed=3, freq="D"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n, freq=freq, tz="UTC")
    close = 100 * np.exp(rng.normal(0, .01, n).cumsum())
    d = pd.DataFrame({"open": close * (1 + rng.normal(0, .001, n)), "close": close, "volume": rng.lognormal(10, .3, n)}, index=idx)
    d["high"], d["low"] = d[["open", "close"]].max(axis=1) * 1.002, d[["open", "close"]].min(axis=1) * .998
    return d


def cot_for(idx, seed=4):
    rng = np.random.default_rng(seed)
    rep = idx[::7]
    return pd.DataFrame({"available": (rep + pd.Timedelta(days=6)).strftime("%Y-%m-%d"), "spec_net_pct_oi": rng.normal(0, .1, len(rep))})


def crypto_inputs(n=1500):
    d = market(n, freq="4h").rename(columns={"volume": "volume_usd"})
    rng = np.random.default_rng(5)
    fidx = pd.date_range(d.index[0], d.index[-1], freq="8h")
    return d, pd.Series(rng.normal(0, 1e-4, len(fidx)), index=fidx), pd.Series(1e6 * np.exp(rng.normal(0, .01, n).cumsum()), index=d.index)


class TestNoLookahead(unittest.TestCase):
    """The strongest check: results up to a date can't change when later data is removed."""

    def assert_prefix_equal(self, full, cut, trimmed, margin=1):
        stop = trimmed[next(iter(trimmed))][0].index[-1 - margin]
        for setup, (price, conds) in full.items():
            pd.testing.assert_series_equal(price[:stop], trimmed[setup][0][:stop], check_freq=False, obj=setup)
            for name in conds:
                pd.testing.assert_series_equal(conds[name][:stop], trimmed[setup][1][name][:stop], check_freq=False, obj=name)

    def test_daily_truncation(self):
        d = market()
        vi = pd.Series(20 + np.random.default_rng(6).normal(0, 2, len(d)), index=d.index)
        cot = cot_for(d.index)
        cut = 700
        full = S.daily_setups(CFG["classes"]["equities"], d, cot=cot, vol_index=vi)
        available = pd.to_datetime(cot.available, utc=True)
        cot_cut = cot[available <= d.index[cut - 1]]
        trimmed = S.daily_setups(CFG["classes"]["equities"], d.iloc[:cut], cot=cot_cut, vol_index=vi.iloc[:cut])
        self.assert_prefix_equal(full, cut, trimmed)

    def test_crypto_truncation(self):
        d, f, o = crypto_inputs()
        cut = 1200
        full = S.crypto_setups(CFG["classes"]["crypto"], d, f, o)
        trimmed = S.crypto_setups(CFG["classes"]["crypto"], d.iloc[:cut], f[f.index <= d.index[cut - 1]], o.iloc[:cut])
        self.assert_prefix_equal(full, cut, trimmed)

    def test_volume_confirmation_is_unknown_on_the_last_bar(self):
        idx = pd.date_range("2020-01-01", periods=3, tz="UTC")
        got = S.volume_fading(pd.Series([1., 9., 2.], index=idx), pd.Series([0., 5., 5.], index=idx), 2)
        self.assertEqual(got.iloc[1], 1)
        self.assertTrue(np.isnan(got.iloc[2]))

    def test_panic_entry_waits_for_the_confirmation_bar(self):
        d = market(400)
        d.iloc[300, d.columns.get_loc("close")] *= .8
        d.iloc[300, d.columns.get_loc("open")] = d.close.iloc[299]
        setups = S.daily_setups(CFG["classes"]["equities"], d)
        config = {**CFG, "scored": {}}
        rows = [r for r in S.event_rows("equities", "X", setups, d.index, config) if r["setup"] == "panic" and r["trigger"] == d.index[300]]
        self.assertEqual(rows[0]["entry"], d.index[302])

    def test_detector_never_reads_future_prices(self):
        src = inspect.getsource(S)
        self.assertEqual(src.count(".shift(-"), 1)  # only next-bar volume in volume_fading
        self.assertIn("nxt = volume.shift(-1)", src)


class TestKnownEffect(unittest.TestCase):
    def test_injected_crash_triggers_panic_and_quiet_data_does_not(self):
        d = market(400)
        cfg = CFG["classes"]["equities"]
        quiet = S.daily_setups(cfg, d)["panic"][0]
        self.assertLess(int(quiet.sum()), 8)
        d.iloc[350:, d.columns.get_loc("close")] *= .85
        d.iloc[350, d.columns.get_loc("open")] = d.close.iloc[349]
        self.assertTrue(S.daily_setups(cfg, d)["panic"][0].iloc[350])

    def test_roll_gap_with_calm_etf_is_not_a_panic(self):
        d = market(400)
        d.iloc[350:, d.columns.get_loc("close")] *= .85
        etf = pd.Series(0.0, index=d.index)
        self.assertFalse(S.daily_setups(CFG["classes"]["equities"], d, etf_z=etf)["panic"][0].iloc[350])

    def test_missing_data_is_nan_not_a_failed_condition(self):
        conds = S.daily_setups(CFG["classes"]["equities"], market(400))["panic"][1]
        self.assertTrue(conds["spec_low"].isna().all())
        self.assertTrue(conds["vol_index_high"].isna().all())


class TestRuleAndScore(unittest.TestCase):
    def test_selectivity_rule_keeps_only_the_band(self):
        t = pd.DataFrame([{"class": "c", "setup": "s", "condition": n, "share": v} for n, v in [("a", .04), ("b", .05), ("c", .6), ("d", .61), ("e", None)]])
        self.assertEqual(S.apply_rule(t, {"min_share": .05, "max_share": .6}), {"c": {"s": ["b", "c"]}})

    def test_score_counts_only_scored_conditions(self):
        idx = pd.date_range("2020-01-01", periods=5, tz="UTC")
        price = pd.Series([False, True, False, False, False], index=idx)
        one = pd.Series(1.0, index=idx)
        setups = {"panic": (price, {"a": one, "b": one, "c": one * np.nan})}
        config = {"classes": {"x": {"cooldown_days": 1}}, "scored": {"x": {"panic": ["a", "c"]}}, "confirm_bars": {"panic": 1}}
        r = S.event_rows("x", "M", setups, idx, config)[0]
        self.assertEqual((r["score"], r["max_score"]), (1, 2))
        self.assertEqual(r["entry"], idx[3])


class TestFrozen(unittest.TestCase):
    def test_preregistration_names_the_current_config(self):
        self.assertIn(S.config_hash(), (S.BASE / "docs" / "PREREGISTRAZIONE_v1.md").read_text())

    def test_every_class_has_scored_conditions(self):
        for cls, v in CFG["scored"].items():
            for setup in ("panic", "squeeze", "overheating"):
                self.assertTrue(v[setup], (cls, setup))


if __name__ == "__main__":
    unittest.main()
