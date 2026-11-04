"""Count setup events per market class. Computes NO forward returns, so test data stays unseen.

    python -m bzd.events

These are first-pass definitions to size the samples. Final thresholds get frozen in phase B1c.
"""
import os, sys

import numpy as np
import pandas as pd

from .history import CRYPTO, ETF_CHECK, MARKETS, root, safe

CUTS = {"crypto": pd.Timestamp("2024-01-01", tz="UTC"), "daily": pd.Timestamp("2015-01-01", tz="UTC")}
VOL_INDEX = {"ES=F": "VIX", "NQ=F": "VIX", "RTY=F": "VIX", "ZT=F": "MOVE", "ZF=F": "MOVE", "ZN=F": "MOVE", "ZB=F": "MOVE",
             "CL=F": "OVX", "GC=F": "GVZ", "SI=F": "GVZ", "EURUSD=X": "EVZCLS", "USDJPY=X": "EVZCLS", "GBPUSD=X": "EVZCLS",
             "AUDUSD=X": "EVZCLS", "USDCHF=X": "EVZCLS", "USDCAD=X": "EVZCLS"}


def ret_z(close, win):
    """Log return in units of past volatility. The window excludes the current bar."""
    r = np.log(close.where(close > 0)).diff()
    return r / r.rolling(win).std().shift(1)


def past_quantile(s, q, min_periods=52):
    """Expanding quantile of strictly earlier values."""
    return s.expanding(min_periods).quantile(q).shift(1)


def log_z(v, win):
    x = np.log(v.where(v > 0))
    return (x - x.rolling(win).mean().shift(1)) / x.rolling(win).std().shift(1)


def align_cot(cot, index):
    """Spec positioning and its past quantiles, usable only from each report's `available` date."""
    c = cot.copy()
    s = c.spec_net_pct_oi
    c["p10"], c["p25"], c["p90"] = past_quantile(s, .1), past_quantile(s, .25), past_quantile(s, .9)
    c = c.assign(available=pd.to_datetime(c.available, utc=True)).drop_duplicates("available", keep="last").set_index("available").sort_index()
    return c[["spec_net_pct_oi", "p10", "p25", "p90"]].reindex(index, method="ffill", tolerance=pd.Timedelta(days=21))


def roll_artefact(d, z, etf_z=None):
    """Flag big futures moves that look like contract rolls, not trading.

    The ETF decides where it has a value: it holds no expiring contract, so a calm ETF means no real move, and a moving
    ETF confirms one even if it all happened overnight. Without an ETF, a move that is nearly all gap is suspect,
    since futures trade nearly all day.
    """
    move = d.close - d.close.shift(1)
    gap_only = (d.close - d.open).abs() < 0.25 * move.abs()
    if etf_z is None:
        return gap_only
    e = etf_z.reindex(d.index)
    return (e.abs() < 1).where(e.notna(), gap_only).astype(bool)


def first_of_runs(mask, days):
    """Keep the first trigger, then ignore more until the cool-off has passed."""
    out, last = [], None
    gap = pd.Timedelta(days=days)
    for t in mask[mask.fillna(False)].index:
        if last is None or t - last >= gap:
            out.append(t)
            last = t
    return pd.DatetimeIndex(out, tz="UTC") if out else pd.DatetimeIndex([], tz="UTC")


def n_clusters(idx, days):
    gap, n, last = pd.Timedelta(days=days), 0, None
    for t in sorted(idx):
        if last is None or t - last > gap:
            n += 1
        last = t
    return n


def read(group, name):
    p = root() / group / f"{name}.csv.gz"
    return pd.read_csv(p) if p.exists() else None


def daily(df):
    d = df.assign(date=pd.to_datetime(df.date, utc=True)).set_index("date").sort_index()
    return d[~d.index.duplicated()]


def vol_series(name, index):
    x = read("vol", name)
    if x is None:
        x = read("tradfi", name)
    if x is not None:
        v = daily(x).close
    else:
        y = read("macro", name)
        if y is None:
            return None
        v = daily(y).value
    return v.reindex(index, method="ffill", tolerance=pd.Timedelta(days=5))


def tradfi_setups(sym, panic_z=-3):
    d = daily(read("tradfi", safe(sym)))
    is_future = sym.endswith("=F")
    z = ret_z(d.close, 60)
    etf = ETF_CHECK.get(sym)
    etf_df = read("tradfi", etf) if etf else None
    etf_z = ret_z(daily(etf_df).close, 60).reindex(d.index) if etf_df is not None else None
    bad = roll_artefact(d, z, etf_z) if is_future else pd.Series(False, index=d.index)

    vz = log_z(d.volume, 60)
    has_volume = (d.volume.fillna(0) > 0).mean() > .5
    cot_df = read("cot", safe(sym))
    c = align_cot(cot_df, d.index) if cot_df is not None else pd.DataFrame(index=d.index, columns=["spec_net_pct_oi", "p10", "p25", "p90"], dtype=float)
    vi = vol_series(VOL_INDEX[sym], d.index) if sym in VOL_INDEX else None
    vi = vi if vi is not None else pd.Series(np.nan, index=d.index)
    vp90, vp25 = past_quantile(vi, .9, 250), past_quantile(vi, .25, 250)

    rng = (d.high.rolling(20).max() - d.low.rolling(20).min()) / d.close
    tight = rng.shift(1) < rng.expanding(250).median().shift(2)
    r20 = np.log(d.close.where(d.close > 0)).diff(20)
    z20 = r20 / (np.log(d.close.where(d.close > 0)).diff().rolling(250).std().shift(1) * np.sqrt(20))
    high60 = d.close >= d.close.rolling(60).max()

    panic = (z <= panic_z) & ~bad
    squeeze = (z >= 2) & tight & ~bad
    hot = high60 & (z20 >= 2)
    vfall = d.volume.shift(-1) < d.volume  # usable only at the next bar's close
    conds = {
        "panic": (panic, [c.spec_net_pct_oi <= c.p25, vi >= vp90, (vz >= 2) & vfall]),
        "squeeze": (squeeze, [c.spec_net_pct_oi <= c.p10, vi.diff() < 0, vz > 1]),
        "overheating": (hot, [c.spec_net_pct_oi >= c.p90, vi <= vp25, vz > 1]),
    }
    return conds, {"removed_as_roll": int(((z <= panic_z) & bad).sum() + ((z >= 2) & tight & bad).sum()), "has_volume": has_volume,
                   "has_cot": cot_df is not None, "has_vol_index": sym in VOL_INDEX, "has_etf_check": etf_df is not None}


def crypto_setups(a):
    d = read("crypto", f"{a}_candles_4h")
    d = d.assign(t=pd.to_datetime(d.t, utc=True)).set_index("t").sort_index()
    d = d[~d.index.duplicated()]
    f = read("crypto", f"{a}_funding")
    f = f.assign(t=pd.to_datetime(f.t, utc=True).dt.floor("s")).drop_duplicates("t").set_index("t").funding.sort_index()
    o = read("crypto", f"{a}_oi_4h")
    o = o.assign(t=pd.to_datetime(o.t, utc=True)).set_index("t").oi.sort_index()

    z, vz = ret_z(d.close, 180), log_z(d.volume_usd, 180)
    fn = f.reindex(d.index, method="ffill")
    f7 = f.rolling(21).mean().reindex(d.index, method="ffill")
    neg3 = ((f < 0).rolling(9).sum() == 9).reindex(d.index, method="ffill").fillna(False).astype(bool)
    fp90 = past_quantile(fn, .9, 180)
    oi = o.reindex(d.index, method="ffill", limit=2)
    doi = oi.pct_change(6, fill_method=None)
    p10 = past_quantile(doi, .1, 180)
    oi7 = oi.pct_change(42, fill_method=None) > 0
    w = (d.high.rolling(42).max() - d.low.rolling(42).min()) / d.close
    tight = w.shift(1) < w.expanding(180).median().shift(2)
    r = np.log(d.close).diff()
    z7 = np.log(d.close).diff(42) / (r.rolling(540).std().shift(1) * np.sqrt(42))
    high = d.close >= d.close.rolling(180).max()
    vfall = d.volume_usd.shift(-1) < d.volume_usd
    return {
        "panic": (z <= -3, [doi <= p10, fn <= 0, (vz >= 3) & vfall]),
        "squeeze": ((z >= 2) & tight, [(f7 < 0) & oi7, neg3, vz > 1]),
        "overheating": (high & (z7 >= 2), [fn >= fp90, oi7, vz > 1]),
    }


def score_table(market_class, setups, cool_days, merge_days, cut):
    """setups: list of dicts setup -> (price mask, [conditions])."""
    rows = []
    for setup in ("panic", "squeeze", "overheating"):
        for n in range(4):
            per_asset = []
            for s in setups:
                price, conds = s[setup]
                score = sum(pd.Series(c, index=price.index).fillna(False).astype(int) for c in conds)
                per_asset.append(first_of_runs(price & (score >= n), cool_days))
            all_ev = pd.DatetimeIndex(np.concatenate([x.values for x in per_asset]) if per_asset else [], tz="UTC")
            rows.append({"class": market_class, "setup": setup, "min_conditions": n, "asset_events": len(all_ev),
                         "clusters": n_clusters(all_ev, merge_days),
                         "calibration": n_clusters(all_ev[all_ev < cut], merge_days),
                         "test": n_clusters(all_ev[all_ev >= cut], merge_days)})
    return rows


def main():
    rows, notes = [], []
    crypto = [crypto_setups(a) for a in CRYPTO if read("crypto", f"{a}_candles_4h") is not None]
    rows += score_table("crypto (4h, split 2024)", crypto, 1, 1, CUTS["crypto"])
    for cls in ("equities", "bonds", "commodities", "fx"):
        built, loose = [], []
        for sym, (c, _) in MARKETS.items():
            if c != cls or read("tradfi", safe(sym)) is None:
                continue
            conds, meta = tradfi_setups(sym)
            built.append(conds)
            loose.append(tradfi_setups(sym, panic_z=-2.5)[0])
            notes.append({"market": sym, "class": cls, **meta})
        rows += score_table(f"{cls} (daily, split 2015)", built, 3, 3, CUTS["daily"])
        rows += [{**r, "setup": "panic z<=-2.5"} for r in score_table(f"{cls} (daily, split 2015)", loose, 3, 3, CUTS["daily"]) if r["setup"] == "panic"]
    t = pd.DataFrame(rows)
    t.to_csv(root() / "event_counts.csv", index=False)
    pd.DataFrame(notes).to_csv(root() / "event_notes.csv", index=False)
    pd.set_option("display.width", 200, "display.max_rows", 500)
    print(t.to_string(index=False))
    print()
    print(pd.DataFrame(notes).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
