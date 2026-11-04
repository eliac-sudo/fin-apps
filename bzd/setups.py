"""Setup detector, driven by config/setups_v1.json. It computes NO forward returns, so test data stays unseen.

    python -m bzd.setups rates     share of triggers meeting each condition, calibration period only
    python -m bzd.setups freeze    apply the selectivity rule, write `scored`, print the config hash
    python -m bzd.setups events    write hist/events_v1.csv and hist/event_counts.csv

A condition is 1, 0, or NaN where its data doesn't exist yet. The score counts scored conditions, equally weighted.
"""
import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

from .events import align_cot, daily, first_of_runs, log_z, n_clusters, past_quantile, read, ret_z, roll_artefact
from .history import CRYPTO, ETF_CHECK, MARKETS, root, safe
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v1.json"
SETUPS = ("panic", "squeeze", "overheating")
VOL_INDEX = {"ES=F": "VIX", "NQ=F": "VIX", "RTY=F": "VIX", "ZT=F": "MOVE", "ZF=F": "MOVE", "ZN=F": "MOVE", "ZB=F": "MOVE",
             "CL=F": "OVX", "GC=F": "GVZ", "SI=F": "GVZ", "EURUSD=X": "EVZCLS", "USDJPY=X": "EVZCLS", "GBPUSD=X": "EVZCLS",
             "AUDUSD=X": "EVZCLS", "USDCHF=X": "EVZCLS", "USDCAD=X": "EVZCLS"}


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flag(cond, *inputs):
    """1 or 0, and NaN wherever an input is missing, so absent data never counts as 'not met'."""
    out = cond.astype(float)
    for x in inputs:
        out = out.where(x.notna())
    return out


def volume_fading(volume, vz, threshold):
    """Spike in this bar, lower volume in the next. Only knowable at the next close, hence `confirm_bars`."""
    nxt = volume.shift(-1)
    return flag((vz >= threshold) & (nxt < volume), vz, nxt)


def crypto_setups(cfg, d, funding, oi):
    """d: 4h candles. funding and oi are timestamped series. Returns setup -> (price trigger, {condition: series})."""
    win = cfg["z_window"]
    z, vz = ret_z(d.close, win), log_z(d.volume_usd, win)
    fn = funding.reindex(d.index, method="ffill")
    f7 = funding.rolling(21).mean().reindex(d.index, method="ffill")
    negs = (funding < 0).rolling(9).sum().where(funding.rolling(9).count() == 9).reindex(d.index, method="ffill")
    o = oi.reindex(d.index, method="ffill", limit=2)
    doi = o.pct_change(6, fill_method=None)
    o7 = o.pct_change(42, fill_method=None)
    width = (d.high.rolling(42).max() - d.low.rolling(42).min()) / d.close
    tight = width.shift(1) < width.expanding(win).median().shift(2)
    r = np.log(d.close).diff()
    z7 = np.log(d.close).diff(42) / (r.rolling(540).std().shift(1) * np.sqrt(42))
    high = d.close >= d.close.rolling(win).max()
    P, S, H = cfg["panic"]["conds"], cfg["squeeze"]["conds"], cfg["overheating"]["conds"]
    p10 = past_quantile(doi, P["oi_flush"]["q"], win)
    fhi = past_quantile(fn, H["funding_high"]["q"], win)
    return {
        "panic": (z <= cfg["panic"]["z"], {
            "oi_flush": flag(doi <= p10, doi, p10), "funding_nonpositive": flag(fn <= 0, fn),
            "volume_spike_fading": volume_fading(d.volume_usd, vz, P["volume_spike_fading"]["z"])}),
        "squeeze": ((z >= cfg["squeeze"]["z"]) & tight, {
            "shorts_building": flag((f7 < 0) & (o7 > 0), f7, o7),
            "funding_mostly_negative": flag(negs >= S["funding_mostly_negative"]["min_negative_of_9"], negs),
            "volume_high": flag(vz > S["volume_high"]["z"], vz)}),
        "overheating": (high & (z7 >= cfg["overheating"]["z_long"]), {
            "funding_high": flag(fn >= fhi, fn, fhi), "oi_rising": flag(o7 > 0, o7),
            "volume_high": flag(vz > H["volume_high"]["z"], vz)}),
    }


def daily_setups(cfg, d, etf_z=None, cot=None, vol_index=None, is_future=True):
    """d: daily bars for one market. Returns setup -> (price trigger, {condition: series})."""
    win = cfg["z_window"]
    z, vz = ret_z(d.close, win), log_z(d.volume, win)
    bad = roll_artefact(d, z, etf_z) if is_future else pd.Series(False, index=d.index)
    c = align_cot(cot, d.index) if cot is not None else pd.DataFrame(np.nan, index=d.index, columns=["spec_net_pct_oi", "p10", "p25", "p75", "p90"])
    vi = vol_index if vol_index is not None else pd.Series(np.nan, index=d.index)
    lc = np.log(d.close.where(d.close > 0))
    z20 = lc.diff(20) / (lc.diff().rolling(250).std().shift(1) * np.sqrt(20))
    high = d.close >= d.close.rolling(60).max()
    width = (d.high.rolling(20).max() - d.low.rolling(20).min()) / d.close
    tight = width.shift(1) < width.expanding(250).median().shift(2)

    def spec(kind, q):
        ref = c[f"p{round(q * 100)}"]
        return flag(c.spec_net_pct_oi <= ref if kind == "low" else c.spec_net_pct_oi >= ref, c.spec_net_pct_oi, ref)

    def build(setup):
        out = {}
        for name, p in cfg[setup]["conds"].items():
            if name == "spec_low":
                out[name] = spec("low", p["q"])
            elif name == "spec_high":
                out[name] = spec("high", p["q"])
            elif name == "vol_index_high":
                ref = past_quantile(vi, p["q"], 250)
                out[name] = flag(vi >= ref, vi, ref)
            elif name == "vol_index_low":
                ref = past_quantile(vi, p["q"], 250)
                out[name] = flag(vi <= ref, vi, ref)
            elif name == "vol_index_drop":
                ch = vi.pct_change(fill_method=None)
                out[name] = flag(ch <= p["pct"], ch)
            elif name == "volume_spike_fading":
                out[name] = volume_fading(d.volume, vz, p["z"])
            elif name == "volume_high":
                out[name] = flag(vz > p["z"], vz)
            else:
                raise KeyError(name)
        return out

    return {
        "panic": ((z <= cfg["panic"]["z"]) & ~bad, build("panic")),
        "squeeze": ((z >= cfg["squeeze"]["z"]) & tight & ~bad, build("squeeze")),
        "overheating": (high & (z20 >= cfg["overheating"]["z_long"]), build("overheating")),
    }


def load_crypto(a):
    d = read("crypto", f"{a}_candles_4h")
    d = d.assign(t=pd.to_datetime(d.t, utc=True)).set_index("t").sort_index()
    f = read("crypto", f"{a}_funding")
    f = f.assign(t=pd.to_datetime(f.t, utc=True).dt.floor("s")).drop_duplicates("t").set_index("t").funding.sort_index()
    o = read("crypto", f"{a}_oi_4h")
    return d[~d.index.duplicated()], f, o.assign(t=pd.to_datetime(o.t, utc=True)).set_index("t").oi.sort_index()


def load_vol_index(name, index):
    x = read("vol", name)
    x = x if x is not None else read("tradfi", name)
    if x is not None:
        v = daily(x).close
    else:
        y = read("macro", name)
        if y is None:
            return None
        v = daily(y).value
    return v.reindex(index, method="ffill", tolerance=pd.Timedelta(days=5))


def load_daily(sym):
    d = daily(read("tradfi", safe(sym)))
    etf = ETF_CHECK.get(sym)
    e = read("tradfi", etf) if etf else None
    etf_z = ret_z(daily(e).close, 60).reindex(d.index) if e is not None else None
    vi = load_vol_index(VOL_INDEX[sym], d.index) if sym in VOL_INDEX else None
    return dict(d=d, etf_z=etf_z, cot=read("cot", safe(sym)), vol_index=vi, is_future=sym.endswith("=F"))


def all_markets(config):
    """Yield (class, market, setups, index)."""
    cl = config["classes"]
    for a in CRYPTO:
        d, f, o = load_crypto(a)
        yield "crypto", a, crypto_setups(cl["crypto"], d, f, o), d.index
    for sym, (cls, _) in MARKETS.items():
        args = load_daily(sym)
        yield cls, sym, daily_setups(cl[cls], **args), args["d"].index


def calibration_mask(index, cfg):
    return index <= pd.Timestamp(cfg["calibration_end"], tz="UTC") + pd.Timedelta(days=1)


def rates(config):
    """Share of calibration-period price triggers meeting each condition, where its data exists."""
    tally = {}
    for cls, _, setups, index in all_markets(config):
        cal = calibration_mask(index, config["classes"][cls])
        for setup, (price, conds) in setups.items():
            m = price.fillna(False).astype(bool).values & cal
            for name, s in conds.items():
                v = s.values[m]
                t = tally.setdefault((cls, setup, name), [0, 0, 0])
                t[0] += int(m.sum())
                t[1] += int(np.nansum(v))
                t[2] += int((~np.isnan(v)).sum())
    return pd.DataFrame([{"class": k[0], "setup": k[1], "condition": k[2], "triggers": v[0], "with_data": v[2], "met": v[1],
                          "share": round(v[1] / v[2], 3) if v[2] else None} for k, v in tally.items()])


def apply_rule(table, rule):
    """Conditions that pass the selectivity rule, by class and setup."""
    scored = {}
    for _, r in table.iterrows():
        keep = r["share"] is not None and not pd.isna(r["share"]) and rule["min_share"] <= r["share"] <= rule["max_share"]
        scored.setdefault(r["class"], {}).setdefault(r["setup"], [])
        if keep:
            scored[r["class"]][r["setup"]].append(r["condition"])
    return scored


def event_rows(cls, market, setups, index, config):
    cfg, out = config["classes"][cls], []
    for setup, (price, conds) in setups.items():
        keep = config["scored"].get(cls, {}).get(setup, [])
        trig = first_of_runs(price.fillna(False).astype(bool), cfg["cooldown_days"])
        delay = config["confirm_bars"][setup] + 1  # enter at the open of the first bar after all information is known
        pos = index.get_indexer(trig)
        for t, i in zip(trig, pos):
            vals = {n: conds[n].iloc[i] for n in conds}
            j = i + delay
            out.append({"class": cls, "market": market, "setup": setup, "trigger": t,
                        "entry": index[j] if j < len(index) else pd.NaT,
                        "score": int(sum(vals[n] == 1 for n in keep)), "max_score": len(keep), **{f"c_{n}": vals[n] for n in conds}})
    return out


def counts(ev, config):
    rows = []
    for (cls, setup), g in ev.groupby(["class", "setup"], sort=False):
        cfg = config["classes"][cls]
        cut = pd.Timestamp(cfg["calibration_end"], tz="UTC") + pd.Timedelta(days=1)
        for n in range(int(g.max_score.max()) + 1):
            x = pd.DatetimeIndex(g[g.score >= n].trigger)
            rows.append({"class": cls, "setup": setup, "min_score": n, "max_score": int(g.max_score.max()), "asset_events": len(x),
                         "clusters": n_clusters(x, cfg["merge_days"]), "calibration": n_clusters(x[x < cut], cfg["merge_days"]),
                         "test": n_clusters(x[x >= cut], cfg["merge_days"])})
    return pd.DataFrame(rows)


def main(argv):
    config = load_config()
    pd.set_option("display.width", 200, "display.max_rows", 500, "display.max_columns", 30)
    cmd = argv[0] if argv else ""
    if cmd == "rates":
        print(rates(config).to_string(index=False))
    elif cmd == "freeze":
        t = rates(config)
        config["scored"] = apply_rule(t, config["selectivity_rule"])
        CONFIG.write_text(json.dumps(config, indent=2) + "\n")
        print(t.to_string(index=False))
        print(json.dumps(config["scored"], indent=1))
        print("sha256", config_hash())
    elif cmd == "events":
        rows = []
        for cls, m, setups, index in all_markets(config):
            rows += event_rows(cls, m, setups, index, config)
        ev = pd.DataFrame(rows)
        ev.to_csv(root() / "events_v1.csv", index=False)
        c = counts(ev, config)
        c.to_csv(root() / "event_counts.csv", index=False)
        print(c.to_string(index=False))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
