"""B3: the one pre-registered test of the frozen setups, as specified in docs/PREREGISTRAZIONE_v1.md.

    python -m bzd.b3 run --confirm

It runs once. It refuses to run again once results exist, because a repeated look would no longer be a clean test.

Choices the pre-registration left open, fixed here before any result: a trade runs from the open of the entry bar to
the close of bar entry + H - 1; only events in the saved events_v1.csv count; events whose path runs past the data
are skipped; baseline entries come from the test period only.
"""
import hashlib, json, sys

import numpy as np
import pandas as pd
from scipy import stats

from . import exits as X
from .events import daily, read
from .history import CRYPTO, MARKETS, root, safe
from .recorder import BASE
from .setups import config_hash, load_config, load_crypto

ALPHA_FAMILY, ALPHA_GLOBAL = .05 / 3, .05 / 15
PRIMARY = {"crypto": 6, "equities": 5, "bonds": 5, "commodities": 5, "fx": 5}
SECONDARY = {"crypto": (1, 6, 18), "equities": (1, 5, 10, 20), "bonds": (1, 5, 10, 20), "commodities": (1, 5, 10, 20), "fx": (1, 5, 10, 20)}
FEE = .00045
SLIPPAGE = {"crypto": .0005, "equities": .0002, "bonds": .0002, "commodities": .0002, "fx": .0002}
STRESS_SLIPPAGE = .002
BASELINE_DRAWS, BOOT_REPS, SEED, MIN_POOL = 200, 5000, 20261104, 20
DIRECTION = {"panic": "greater", "squeeze": "greater", "overheating": "less"}
RESULTS = BASE / "config" / "validation_v1.json"
REPORT = BASE / "docs" / "B3_RISULTATI.md"


def horizon_returns(o, c, h, cost, funding=None):
    """Net return of a long from the open of each bar to the close of bar i + h - 1. NaN where it can't be computed."""
    n = len(o)
    out = np.full(n, np.nan)
    if n < h:
        return out
    fund = np.cumsum(funding) if funding is not None else np.zeros(n)
    idx = np.arange(n - h + 1)
    last = idx + h - 1
    valid = (o[idx] > 0) & (c[last] > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = c[last] / o[idx] - 1 - cost - (fund[last] - fund[idx])
    out[idx[valid]] = r[valid]
    return out


def baseline_pool(ret, years, event_pos, h, year, in_test):
    """Bars usable as random entries: same year, in the test period, at least one horizon from any event."""
    mask = (years == year) & in_test & ~np.isnan(ret)
    for e in event_pos:
        mask[max(0, e - h + 1):e + h] = False
    return np.flatnonzero(mask)


def event_excess(ret, years, event_pos, h, rng, in_test):
    """(position, net return, excess over random entries) per event. Events without a usable pool are left out."""
    out = []
    for e in event_pos:
        if np.isnan(ret[e]):
            continue
        pool = baseline_pool(ret, years, event_pos, h, years[e], in_test)
        if len(pool) < MIN_POOL:
            continue
        out.append((e, ret[e], ret[e] - ret[rng.choice(pool, BASELINE_DRAWS)].mean()))
    return out


def power_at(n, d, alpha):
    if n < 3:
        return 0.0
    return float(stats.nct.sf(stats.t.ppf(1 - alpha, n - 1), n - 1, d * np.sqrt(n)))


def outcome(p, power, alpha=ALPHA_FAMILY):
    """The three-outcome rule: `not supported` can be said only with enough power."""
    if p is not None and not np.isnan(p) and p < alpha:
        return "supportata"
    return "non supportata" if power >= .5 else "non informativa"


def cluster_test(values, direction, seed=SEED, reps=BOOT_REPS):
    """One-sided t test on cluster values, with a cluster bootstrap as a check."""
    v = np.asarray(values, float)
    n = len(v)
    power = power_at(n, .30, ALPHA_FAMILY)
    if n < 3 or v.std(ddof=1) == 0:
        return {"clusters": n, "mean": float(v.mean()) if n else None, "p": None, "power_d30": power, "outcome": outcome(None, power)}
    t, p = stats.ttest_1samp(v, 0, alternative=direction)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, n, (reps, n))].mean(axis=1)
    return {"clusters": n, "mean": float(v.mean()), "sd": float(v.std(ddof=1)), "d": float(v.mean() / v.std(ddof=1)), "t": float(t), "p": float(p),
            "boot_p": float((means <= 0).mean() if direction == "greater" else (means >= 0).mean()), "ci90": [float(np.quantile(means, .05)), float(np.quantile(means, .95))],
            "power_d30": power, "outcome": outcome(float(p), power), "passes_global": bool(p < ALPHA_GLOBAL)}


def load_market(cls, m):
    if cls == "crypto":
        d, f, _ = load_crypto(m)
        return d, f.resample("4h").sum().reindex(d.index).fillna(0.0).values
    return daily(read("tradfi", safe(m))), None


def members(cls):
    return CRYPTO if cls == "crypto" else [m for m, (c, _) in MARKETS.items() if c == cls]


def study(ev, cls, setup, cfg, h, slippage=None):
    """Event-level results for one class, setup and horizon, in the test period only."""
    start = X.calibration_end(cfg)
    cost = (FEE + (SLIPPAGE[cls] if slippage is None else slippage)) * (1 if setup == "overheating" else 2)
    rng, rows, skipped = np.random.default_rng(SEED), [], 0
    for m in members(cls):
        e = ev[(ev["class"] == cls) & (ev.market == m) & (ev.setup == setup)]
        e = e[(pd.to_datetime(e.trigger, utc=True, format="ISO8601") >= start)]
        if e.empty:
            continue
        d, fund = load_market(cls, m)
        o, c = d.open.values.astype(float), d.close.values.astype(float)
        ret = horizon_returns(o, c, h, cost, fund)
        in_test = d.index >= start
        known = e[e.entry.notna()]
        pos = d.index.get_indexer(pd.to_datetime(known.entry, utc=True, format="ISO8601"))
        skipped += len(e) - int((pos >= 0).sum())
        keep = pos >= 0
        results = {p: (r, x) for p, r, x in event_excess(ret, d.index.year.values, pos[keep], h, rng, in_test)}
        skipped += int(keep.sum()) - len(results)
        for (_, row), p in zip(known[keep].iterrows(), pos[keep]):
            if p in results:
                rows.append({"market": m, "trigger": row.trigger, "score": row.score, "net": results[p][0], "excess": results[p][1]})
    return pd.DataFrame(rows), skipped


def summarize(df, cfg, setup):
    if df.empty:
        return {"events": 0, **cluster_test([], DIRECTION[setup])}, df
    df = df.assign(cluster=X.assign_clusters(df.trigger, cfg["merge_days"]))
    g = df.groupby("cluster").agg(excess=("excess", "mean"), net=("net", "mean"), score=("score", "mean"))
    res = cluster_test(g.excess.values, DIRECTION[setup])
    res["events"] = len(df)
    res["mean_net"] = float(g.net.mean())
    res["share_up"] = float((df.net > 0).mean())
    return res, g


def score_link(g):
    """Secondary: does a higher score go with a stronger effect? Descriptive only."""
    if len(g) < 5 or g.score.nunique() < 2:
        return None
    r = stats.spearmanr(g.score, g.excess)
    return {"spearman": float(r.statistic), "p": float(r.pvalue)}


def exit_test(ev, cls, setup, cfg, exit_cfg, rule_name):
    """Selected exit rule against plain holding, in R, per cluster, on the test period."""
    ce, rules = exit_cfg["classes"][cls], exit_cfg["rules"]
    start, rows = X.calibration_end(cfg), []
    cost = ce["fee_per_side"] + ce["slippage_per_side"]
    for m in members(cls):
        e = ev[(ev["class"] == cls) & (ev.market == m) & (ev.setup == setup) & ev.entry.notna()]
        e = e[pd.to_datetime(e.trigger, utc=True, format="ISO8601") >= start]
        if e.empty:
            continue
        d, fund = load_market(cls, m)
        o, h, l, c = (d[x].values.astype(float) for x in ("open", "high", "low", "close"))
        atr = X.atr_series(d, exit_cfg["atr_bars"]).values
        flags = np.zeros(len(d), bool)
        over = ev[(ev["class"] == cls) & (ev.market == m) & (ev.setup == "overheating") & ev.entry.notna()]
        p = d.index.get_indexer(pd.to_datetime(over.entry, utc=True, format="ISO8601"))
        flags[p[p >= 0]] = True
        for _, row in e.iterrows():
            i = d.index.get_indexer([pd.Timestamp(row.entry)])[0]
            if i < 1 or i + ce["max_hold_bars"] >= len(d) or not X.path_ok(o, h, l, c, i, i + ce["max_hold_bars"]):
                continue
            stop0, risk = X.initial_stop(l, atr, i, o[i], exit_cfg["initial_stop"])
            if not risk or risk <= 0:
                continue
            res = {}
            for name in {rule_name, "hold"}:
                r = rules[name]
                fills, _ = X.simulate(o, h, l, c, atr, i, stop0, risk, r, X.horizon_end(r, i, ce), flags if r.get("exit_on_overheating") else None)
                res[name] = X.net_result(fills, o[i], risk, i, cost, fund)[1]
            rows.append({"trigger": row.trigger, "hold": res["hold"], "rule": res[rule_name]})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["cluster"] = X.assign_clusters(df.trigger, cfg["merge_days"])
    g = df.groupby("cluster")[["hold", "rule"]].mean()
    t = cluster_test((g.rule - g.hold).values, "greater")
    return {"rule": rule_name, "events": len(df), "rule_R": float(g.rule.mean()), "hold_R": float(g.hold.mean()), "worst10_rule": float(df.rule.quantile(.1)), "worst10_hold": float(df.hold.quantile(.1)), **t}


def run_all():
    config = load_config()
    ev = pd.read_csv(root() / "events_v1.csv")
    exit_cfg = json.loads(X.CONFIG.read_text())
    selected = json.loads((BASE / "config" / "exits_selected_v1.json").read_text())
    results = {"config_sha256": config_hash(), "events_sha256": hashlib.sha256((root() / "events_v1.csv").read_bytes()).hexdigest(), "alpha_family": ALPHA_FAMILY, "alpha_global": ALPHA_GLOBAL, "tests": {}}
    for cls, cfg in config["classes"].items():
        for setup in ("panic", "squeeze", "overheating"):
            df, skipped = study(ev, cls, setup, cfg, PRIMARY[cls])
            res, g = summarize(df, cfg, setup)
            res.update(skipped=skipped, horizon_bars=PRIMARY[cls], direction=DIRECTION[setup], score_link=score_link(g) if len(df) else None)
            res["other_horizons"] = {}
            for h in SECONDARY[cls]:
                if h != PRIMARY[cls]:
                    r2, _ = summarize(study(ev, cls, setup, cfg, h)[0], cfg, setup)
                    res["other_horizons"][str(h)] = {"mean": r2.get("mean"), "p": r2.get("p"), "clusters": r2.get("clusters")}
            if setup == "panic":
                res["mean_net_stress_slippage"] = summarize(study(ev, cls, setup, cfg, PRIMARY[cls], STRESS_SLIPPAGE)[0], cfg, setup)[0].get("mean_net")
            if setup != "overheating":
                pick = selected.get(cls, {}).get(setup, "hold")
                res["exit_selected"] = exit_test(ev, cls, setup, cfg, exit_cfg, pick) if pick != "hold" else {"rule": "hold"}
                res["exit_target_3R_descriptive"] = exit_test(ev, cls, setup, cfg, exit_cfg, "target_3R")
            results["tests"][f"{cls}/{setup}"] = res
            print(f"{cls}/{setup}: {res['outcome']}", flush=True)
    return results


def pct(x):
    return "—" if x is None else f"{100 * x:+.2f}%"


def report(r):
    names = {"panic": "Panico", "squeeze": "Squeeze", "overheating": "Surriscaldamento"}
    lines = ["# B3 — risultati del test pre-registrato (v1)", "",
             f"Configurazione `{r['config_sha256'][:12]}`, eventi `{r['events_sha256'][:12]}`. Regole in `docs/PREREGISTRAZIONE_v1.md`, codice in `bzd/b3.py`. Eseguito una sola volta. Non è consulenza finanziaria.", "",
             "## Test primari", "", "Eccesso = rendimento netto rispetto a ingressi casuali su stesso mercato e stesso anno. Per il surriscaldamento ci si aspetta un eccesso negativo.", "",
             "| Mercato | Setup | Episodi | Eccesso medio | IC 90% | d | p | Potenza d=0,3 | Rend. netto medio | Esito |", "|---|---|---:|---:|---|---:|---:|---:|---:|---|"]
    for k, t in r["tests"].items():
        cls, s = k.split("/")
        ci = f"{pct(t['ci90'][0])} … {pct(t['ci90'][1])}" if t.get("ci90") else "—"
        p = "—" if t.get("p") is None else f"{t['p']:.3f}"
        d = "—" if t.get("d") is None else f"{t['d']:+.2f}"
        star = " ★" if t.get("passes_global") else ""
        lines.append(f"| {cls} | {names[s]} | {t['clusters']} | {pct(t.get('mean'))} | {ci} | {d} | {p} | {t['power_d30']:.0%} | {pct(t.get('mean_net'))} | **{t['outcome']}**{star} |")
    lines += ["", f"★ = regge anche alla soglia globale {r['alpha_global']:.4f}. Soglia per test {r['alpha_family']:.4f}.", "", "## Altri orizzonti (solo descrittivi)", ""]
    for k, t in r["tests"].items():
        o = ", ".join(f"{h} barre {pct(v['mean'])}" for h, v in t["other_horizons"].items())
        link = t.get("score_link")
        lines.append(f"- {k}: {o or '—'}" + (f"; punteggio ed effetto, Spearman {link['spearman']:+.2f}" if link else ""))
    lines += ["", "## Uscite (test H3 sulle regole selezionate, in R)", ""]
    for k, t in r["tests"].items():
        sel, tgt = t.get("exit_selected"), t.get("exit_target_3R_descriptive")
        if sel and sel.get("rule") != "hold":
            lines.append(f"- {k}: `{sel['rule']}` {sel['rule_R']:+.2f}R contro tieni {sel['hold_R']:+.2f}R, p {sel.get('p')}, esito **{sel['outcome']}**")
        if tgt:
            lines.append(f"- {k}, descrittivo: stop + 3R {tgt['rule_R']:+.2f}R (peggior 10% {tgt['worst10_rule']:+.2f}R), tieni {tgt['hold_R']:+.2f}R (peggior 10% {tgt['worst10_hold']:+.2f}R)")
    return "\n".join(lines) + "\n"


def main(argv):
    if argv[:2] != ["run", "--confirm"]:
        print(__doc__)
        return 2
    if RESULTS.exists():
        print(f"Results already exist in {RESULTS}. This test runs once.")
        return 1
    r = run_all()
    RESULTS.write_text(json.dumps(r, indent=1) + "\n")
    REPORT.write_text(report(r))
    print(REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
