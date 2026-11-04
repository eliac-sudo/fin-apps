"""Exit lab: replay the rules in config/exits_v1.json on setup entries, in the calibration period ONLY.

    python -m bzd.exits run

Prices are cut at the end of the calibration period before any simulation, so the test period can't be read.
Within a bar the stop is checked before targets, because 4h and daily bars don't show which came first.
"""
import json, sys

import numpy as np
import pandas as pd

from .events import daily, read
from .history import MARKETS, root, safe
from .recorder import BASE
from .setups import load_config, load_crypto

CONFIG = BASE / "config" / "exits_v1.json"


def calibration_end(cfg):
    return pd.Timestamp(cfg["calibration_end"], tz="UTC") + pd.Timedelta(days=1)


def cut_to_calibration(d, cfg):
    return d[d.index < calibration_end(cfg)]


def atr_series(d, bars):
    """Average true range using data up to and including each bar's close."""
    prev = d.close.shift(1)
    tr = pd.concat([d.high - d.low, (d.high - prev).abs(), (d.low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(bars).mean()


def initial_stop(low, atr, entry_i, entry_price, p):
    """Stop from what is known at the close before entry. Returns (stop, risk per unit)."""
    s = entry_i - 1
    start = max(0, s - p["low_lookback_bars"] + 1)
    a = atr[s]
    if np.isnan(a) or a <= 0:
        return None, None
    stop = np.min(low[start:s + 1]) - p["atr_below_low"] * a
    risk = max(entry_price - stop, p["min_atr_distance"] * a)
    return entry_price - risk, risk


def simulate(o, h, l, c, atr, e, stop0, risk, rule, last, exit_flags=None):
    """Replay one long trade from the open of bar e to the close of bar `last` at the latest.

    A trailing stop or a stop moved to breakeven takes effect from the next bar. Returns fills as
    (fraction, price, bar, reason) and the highest high reached before the final exit.
    """
    entry, rem, fills = o[e], 1.0, []
    stop = stop0 if rule.get("stop") else -np.inf
    targets = [[entry + k * risk, f] for k, f in rule.get("targets", [])]
    any_filled, peak_close, mfe_high = False, entry, entry
    for i in range(e, last + 1):
        if i > e and exit_flags is not None and exit_flags[i]:
            fills.append((rem, o[i], i, "signal"))
            return fills, mfe_high
        if o[i] <= stop:
            fills.append((rem, o[i], i, "stop_gap"))
            return fills, max(mfe_high, o[i])
        if l[i] <= stop:
            fills.append((rem, stop, i, "stop"))
            return fills, max(mfe_high, h[i])
        mfe_high = max(mfe_high, h[i])
        for t in targets:
            if t[1] > 0 and h[i] >= t[0]:
                f = min(t[1], rem)
                fills.append((f, max(t[0], o[i]), i, "target"))
                rem -= f
                t[1] = 0
                any_filled = True
        if rem <= 1e-9:
            return fills, mfe_high
        if i == last:
            break
        peak_close = max(peak_close, c[i])
        if rule.get("trail_atr") and not np.isnan(atr[i]):
            stop = max(stop, peak_close - rule["trail_atr"] * atr[i])
        if rule.get("breakeven_after_first") and any_filled:
            stop = max(stop, entry)
    fills.append((rem, c[last], last, "time"))
    return fills, mfe_high


def net_result(fills, entry, risk, e, cost_per_side, funding=None):
    """Net return after fees, slippage and funding, as a fraction of entry and in multiples of risk (R)."""
    gross = sum(f * (p / entry - 1) for f, p, _, _ in fills)
    fund = 0.0
    if funding is not None:
        rem, by_bar = 1.0, {}
        for f, _, i, _ in fills:
            by_bar[i] = by_bar.get(i, 0) + f
        for i in range(e + 1, max(by_bar) + 1):
            rem -= by_bar.get(i - 1, 0)
            fund += rem * funding[i]
    net = gross - 2 * cost_per_side - fund
    return net, net / (risk / entry), gross


def horizon_end(rule, e, c):
    return e + {"horizon": c["horizon_bars"], "half_horizon": c["horizon_bars"] // 2, "max": c["max_hold_bars"]}[rule["exit_at"]]


def path_ok(o, h, l, c, e, last):
    """Skip paths with impossible bars rather than simulate on bad data."""
    a, b, cc, d = o[e:last + 1], h[e:last + 1], l[e:last + 1], c[e:last + 1]
    if not np.isfinite(np.r_[a, b, cc, d]).all() or (cc <= 0).any():
        return False
    return not ((b < np.maximum(a, d) * .9999) | (cc > np.minimum(a, d) * 1.0001)).any()


def run_market(d, ev, cls_exit, config, cfg, funding=None):
    """d must already be cut to the calibration period. Returns one row per event and rule, and a count of skips."""
    if len(d) and d.index.max() >= calibration_end(cfg):
        raise ValueError("exit lab received bars from the test period")
    o, h, l, c = (d[x].values.astype(float) for x in ("open", "high", "low", "close"))
    atr = atr_series(d, config["atr_bars"]).values
    fund = funding.values if funding is not None else None
    index = d.index
    flags = np.zeros(len(d), bool)
    over = ev[(ev.setup == "overheating") & ev.entry.notna()]
    pos = index.get_indexer(pd.to_datetime(over.entry, utc=True, format="ISO8601"))
    flags[pos[pos >= 0]] = True
    rows, skipped = [], 0
    cost = cls_exit["fee_per_side"] + cls_exit["slippage_per_side"]
    for _, x in ev[ev.setup.isin(config["entries"]) & ev.entry.notna()].iterrows():
        e = index.get_indexer([pd.Timestamp(x.entry)])[0]
        if e < 1 or e + cls_exit["max_hold_bars"] >= len(d):
            skipped += e >= 1  # path would run past the calibration period
            continue
        if not path_ok(o, h, l, c, e, e + cls_exit["max_hold_bars"]):
            skipped += 1
            continue
        stop0, risk = initial_stop(l, atr, e, o[e], config["initial_stop"])
        if risk is None or risk <= 0:
            skipped += 1
            continue
        for name, rule in config["rules"].items():
            ex = flags if rule.get("exit_on_overheating") else None
            fills, high = simulate(o, h, l, c, atr, e, stop0, risk, rule, horizon_end(rule, e, cls_exit), ex)
            net, r, gross = net_result(fills, o[e], risk, e, cost, fund)
            mfe = high / o[e] - 1
            rows.append({"setup": x.setup, "market": x.market, "trigger": x.trigger, "score": x.score, "rule": name,
                         "net": net, "r": r, "gross": gross, "risk_pct": risk / o[e], "giveback_r": (mfe - gross) / (risk / o[e]),
                         "bars": fills[-1][2] - e + 1, "reason": fills[-1][3]})
    return rows, skipped


def assign_clusters(triggers, merge_days):
    t = pd.to_datetime(pd.Series(triggers).reset_index(drop=True), utc=True, format="ISO8601")
    order = t.sort_values()
    ids = (order.diff() > pd.Timedelta(days=merge_days)).cumsum()
    return ids.reindex(t.index).values


def cluster_means(values, clusters):
    return pd.Series(values).groupby(clusters).mean().values


def boot_ci(values, reps, seed, level=.9):
    """Bootstrap interval of the mean, resampling clusters."""
    if len(values) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), (reps, len(values)))].mean(axis=1)
    return float(np.quantile(means, (1 - level) / 2)), float(np.quantile(means, (1 + level) / 2))


def summarize(rows, cfg, boot):
    """Rule table for one class and setup. Means are per cluster, so one market episode counts once."""
    if rows.empty:
        return pd.DataFrame()
    triggers = rows[rows.rule == "hold"].set_index(["market", "trigger"]).index
    uniq = pd.DataFrame(list(triggers), columns=["market", "trigger"])
    uniq["cluster"] = assign_clusters(uniq.trigger, cfg["merge_days"])
    rows = rows.merge(uniq, on=["market", "trigger"])
    wide = rows.pivot(index=["market", "trigger", "cluster"], columns="rule", values="r").reset_index()
    out = []
    for rule, g in rows.groupby("rule"):
        cm = cluster_means(g.r.values, g.cluster.values)
        diff = (wide[rule] - wide["hold"]).values
        dm = cluster_means(diff, wide.cluster.values)
        lo, hi = boot_ci(dm, boot["reps"], boot["seed"])
        out.append({"rule": rule, "events": len(g), "clusters": len(cm), "mean_R": cm.mean(), "mean_R_per_event": g.r.mean(), "median_R": g.r.median(),
                    "win_share": (g.r > 0).mean(), "p10_R": g.r.quantile(.1), "mean_net_pct": 100 * cluster_means(g.net.values, g.cluster.values).mean(),
                    "giveback_R": cluster_means(g.giveback_r.values, g.cluster.values).mean(), "mean_bars": g.bars.mean(),
                    "diff_vs_hold": dm.mean(), "diff_lo90": lo, "diff_hi90": hi})
    return pd.DataFrame(out).sort_values("mean_R", ascending=False)


def select_rule(table):
    """The criterion fixed in config/exits_v1.json before any result was seen."""
    t = table[table.rule != "hold"].sort_values("mean_R", ascending=False)
    if len(t) and t.iloc[0].diff_lo90 > 0:
        return t.iloc[0].rule
    return "hold"


def load_all(config):
    setups = load_config()
    ev = pd.read_csv(root() / "events_v1.csv")
    for cls, cls_exit in config["classes"].items():
        cfg = setups["classes"][cls]
        rows, skipped = [], 0
        members = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK"] if cls == "crypto" else [m for m, (c, _) in MARKETS.items() if c == cls]
        for m in members:
            e = ev[(ev["class"] == cls) & (ev.market == m) & (pd.to_datetime(ev.trigger, utc=True, format="ISO8601") < calibration_end(cfg))]
            if cls == "crypto":
                d, f, _ = load_crypto(m)
                d = cut_to_calibration(d, cfg)
                bars = f[f.index < calibration_end(cfg)].resample("4h").sum().reindex(d.index).fillna(0.0)
            else:
                d, bars = cut_to_calibration(daily(read("tradfi", safe(m))), cfg), None
            r, s = run_market(d, e, cls_exit, config, cfg, bars)
            rows += r
            skipped += s
        yield cls, cfg, pd.DataFrame(rows), skipped


def main(argv):
    if not argv or argv[0] != "run":
        print(__doc__)
        return 2
    config = json.loads(CONFIG.read_text())
    pd.set_option("display.width", 220, "display.max_rows", 500, "display.max_columns", 30, "display.float_format", "{:.2f}".format)
    tables, selected = [], {}
    for cls, cfg, rows, skipped in load_all(config):
        for setup in config["entries"]:
            t = summarize(rows[rows.setup == setup], cfg, config["bootstrap"])
            if t.empty:
                continue
            pick = select_rule(t)
            selected.setdefault(cls, {})[setup] = pick
            t.insert(0, "setup", setup)
            t.insert(0, "class", cls)
            tables.append(t)
            print(f"\n== {cls} / {setup}: selected {pick}; {skipped} paths skipped in this class")
            print(t.drop(columns=["class", "setup"]).to_string(index=False))
    pd.concat(tables).to_csv(root() / "exits_v1_calibration.csv", index=False)
    (BASE / "config" / "exits_selected_v1.json").write_text(json.dumps(selected, indent=2) + "\n")
    print("\nselected:", json.dumps(selected))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
