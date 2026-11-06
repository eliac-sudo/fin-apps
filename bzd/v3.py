"""Pre-registration v3: every reading the app shows that was never tested, on 2008 to 6 Nov 2026 (docs/PREREGISTRAZIONE_v3.md).

    python -m bzd.v3 conta              free: events and clusters per hypothesis. No returns.
    python -m bzd.v3 storico --confirm  the one test, once. Refuses to run twice or if the config changed

Fifteen hypotheses, one per reading: option prices (O), BYZ and SZT zones (Z), resets (R), tension (T), sentiment extremes (S),
who buys the dip (F), strong moves (M) and support and resistance (L). Each reading is rebuilt bar by bar from data known at that
bar, with the same functions the app uses. A trade starts at the next bar, and is compared with random entries on the same market
in the same year. Holm's correction keeps the chance of any false "supportata" across all fifteen at 5%.
"""
import hashlib, json, sys
from datetime import datetime, timezone
from math import erf, sqrt

import numpy as np
import pandas as pd
from scipy import stats

from . import flows as FL
from . import sentiment as SM
from . import technicals as K
from . import thermo as Z
from . import zones as ZN
from .b3 import horizon_returns, power_at
from .events import crypto_daily, daily, read
from .exits import assign_clusters
from .history import CRYPTO, MARKETS, safe
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v3.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v3.md"
RESULTS = BASE / "config" / "validation_v3_storico.json"
REPORT = BASE / "docs" / "V3_STORICO.md"
SHORT = {"Z2", "R2", "T2", "S2"}  # the reading points down: the trade is short


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def class_of(m):
    return "crypto" if m in CRYPTO else MARKETS[m][0]


def all_markets():
    return [*CRYPTO, *MARKETS]


# ---- signals, each known at the close of its bar

def spaced(flags, gap):
    """Bars where the reading holds, at least `gap` bars apart, so holding periods on one market never overlap."""
    out, last = [], None
    for i in np.flatnonzero(np.asarray(flags, bool)):
        if last is None or i - last >= gap:
            out.append(int(i))
            last = i
    return out


def zone_flags(d):
    s = ZN.indicator_score(d, "1d")[0].values
    return {"Z1": s <= ZN.BYZ_BELOW, "Z2": s >= ZN.SZT_ABOVE}


def reset_flags(d):
    """The app's reset, with its memory: after one fires, the next waits until the RSI is back at 50."""
    rs, trend = K.I.rsi(d.close).values, K.long_trend(d.close).values
    low, high = K.RESET_RSI["1d"], 100 - K.RESET_RSI["1d"]
    up, down = np.zeros(len(rs), bool), np.zeros(len(rs), bool)
    fired_up = fired_down = False
    for i in range(1, len(rs)):
        if np.isnan(rs[i]) or np.isnan(rs[i - 1]):
            continue
        if rs[i] >= 50:
            fired_up = False
        if rs[i] <= 50:
            fired_down = False
        if trend[i - 1] == "rialzo" and rs[i - 1] >= low > rs[i] and not fired_up:
            up[i], fired_up = True, True
        elif trend[i - 1] == "ribasso" and rs[i - 1] <= high < rs[i] and not fired_down:
            down[i], fired_down = True, True
    return {"R1": up, "R2": down}


def tension(m, index):
    """The tension on each daily bar: the app's plain average of strictly-past percentiles, the last 4h value of each day on crypto."""
    if m in CRYPTO:
        _, _, _, series = Z.crypto_series(m)
    else:
        _, _, _, series = Z.daily_series(m)
    h = pd.concat(series, axis=1).mean(axis=1, skipna=True).dropna()
    h = h.groupby(pd.to_datetime(h.index, utc=True).normalize()).last()
    return h.reindex(index).values


def tension_flags(m, d):
    h = tension(m, d.index)
    with np.errstate(invalid="ignore"):
        return {"T1": h < 20, "T2": h >= 80}


def sentiment_flags(m, d):
    g = SM.gauge(m)
    if g is None:
        return {"S1": np.zeros(len(d), bool), "S2": np.zeros(len(d), bool)}
    s = g["series"]
    s = s.groupby(pd.to_datetime(s.index, utc=True).normalize()).last().reindex(d.index).values
    with np.errstate(invalid="ignore"):
        return {"S1": s <= g["low"], "S2": s >= g["high"]}


def move_flags(d, cfg):
    """A daily close-to-close move of k times the standard deviation of the 90 sessions before it. Sign: +1 up, -1 down."""
    r = np.log(d.close.where(d.close > 0)).diff()
    sd = r.shift(1).rolling(cfg["moves"]["sigma_days"], min_periods=cfg["moves"]["sigma_days"] // 2).std()
    big = (r.abs() >= cfg["moves"]["k_sigma"] * sd).fillna(False).values
    return big, np.sign(r.fillna(0).values)


def level_flags(d, cfg):
    """Supports and resistances computed every few bars on data up to that bar, then used on the following bars only."""
    every, keep = cfg["levels"]["recompute_every_bars"], cfg["levels"]["history_bars"]
    sup, res = np.zeros(len(d), bool), np.zeros(len(d), bool)
    lo, hi, cl = d.low.values, d.high.values, d.close.values
    for i in range(300, len(d) - 1, every):
        f = K.frames_from(d.iloc[max(0, i + 1 - keep):i + 1])
        pool = K.swing_pool(f)
        if "1d" not in pool:
            continue
        below, above = K.pick_levels(K.shared_levels(pool, "1d"), float(cl[i]), "1d")
        half = pool["1d"]["width"] / 2
        for j in range(i + 1, min(i + 1 + every, len(d))):
            if below and abs(lo[j] - below[0]["price"]) <= half and cl[j] >= below[0]["price"] - half:
                sup[j] = True
            if above and abs(hi[j] - above[0]["price"]) <= half and cl[j] <= above[0]["price"] + half:
                res[j] = True
    return {"L1": sup, "L2": res}


def flow_signals(m, d):
    """(F1 bars, F2 bars, dip bars) on the daily index. On the COT a report counts from the first bar on or after the day it was published."""
    if m in CRYPTO:
        x = FL.crypto_table(m, "1d")
        tf = "1d"
    else:
        x = FL.cot_table(m)
        tf = "1w"
    dip = np.asarray([FL.state_of(s) == "dip" if pd.notna(s) else False for s in ZN.indicator_score(d, "1d")[0].values])
    f1, f2 = np.zeros(len(d), bool), np.zeros(len(d), bool)
    if x is None or x.empty:
        return f1, f2, dip
    y = FL.pressures(x, tf)
    when = pd.to_datetime(y["available"], utc=True) if "available" in y else y.index
    pos = d.index.searchsorted(pd.DatetimeIndex(when).normalize())
    for p, (_, r) in zip(pos, y.iterrows()):
        if p >= len(d) or r.state != "dip":
            continue
        if r.big >= FL.INTENSITY_MIN:
            f1[p] = True
        if r.retail >= FL.INTENSITY_MIN:
            f2[p] = True
    return f1, f2, dip


def price_signals(m, d, cfg):
    """Every price hypothesis's raw flags on one market, plus the pool restriction for F and the direction for M."""
    out = {**zone_flags(d), **reset_flags(d), **tension_flags(m, d), **sentiment_flags(m, d), **level_flags(d, cfg)}
    f1, f2, dip = flow_signals(m, d)
    out.update(F1=f1, F2=f2)
    big, sign = move_flags(d, cfg)
    out["M1"] = big
    return out, {"F1": dip, "F2": dip}, sign


# ---- options

def norm_cdf(x):
    return .5 * (1 + erf(x / sqrt(2)))


def har_path(close, days, year_days, min_history=400):
    """The app's HAR forecast (option_models.har_detail) for every day, fitted each day only on targets already known.

    Running sums of the normal equations give the same fit as refitting from scratch each day, without the cost."""
    c = close[close > 0]
    r = np.log(c).diff().dropna()
    h = int(round(days))
    v = r ** 2
    x = pd.DataFrame({"week": v.rolling(5).mean(), "month": v.rolling(22).mean(), "quarter": v.rolling(66).mean()}).clip(lower=1e-12)
    x = .5 * np.log(x * year_days)
    y = .5 * np.log((v.rolling(h).mean().shift(-h) * year_days).clip(lower=1e-12))
    X = np.c_[np.ones(len(x)), x.values]
    ok = ~np.isnan(X).any(axis=1) & ~np.isnan(y.values)
    out = pd.Series(np.nan, index=r.index)
    xtx, xty, n = np.zeros((4, 4)), np.zeros(4), 0
    for j in range(len(r)):
        k = j - h  # the newest row whose target is known at day j
        if k >= 0 and ok[k]:
            xtx += np.outer(X[k], X[k])
            xty += X[k] * y.values[k]
            n += 1
        if j + 1 < min_history + h or n < 100 or np.isnan(X[j]).any():
            continue
        b = np.linalg.solve(xtx, xty)
        out.iloc[j] = float(np.exp(X[j] @ b))
    return out


def option_series(name, spec):
    g, n = spec["iv"]
    iv = read(g, n)
    if iv is None:
        return None
    iv = daily(iv.assign(date=iv.t.str[:10]) if "date" not in iv else iv)
    col = "close" if "close" in iv else iv.columns[-1]
    iv = iv[col].astype(float) / 100
    pg, pn = spec["price"]
    px = (crypto_daily(pn) if pg == "crypto" else daily(read(pg, safe(pn)))).close.astype(float)
    px.index = pd.to_datetime(px.index, utc=True).normalize()
    iv.index = pd.to_datetime(iv.index, utc=True).normalize()
    iv = iv[~iv.index.duplicated(keep="last")]
    px = px[~px.index.duplicated(keep="last")]
    fc = har_path(px, spec["days"], spec["year_days"])
    df = pd.DataFrame({"close": px, "iv": iv.reindex(px.index), "forecast": fc.reindex(px.index)})
    df["ratio"] = df.iv / df.forecast
    return df


def straddle_pnl(df, spec):
    """Seller's result on a 30-day at-the-money straddle opened at each close, as a share of the premium. Black-Scholes at the index level, no carry."""
    c, iv = df.close.values, df.iv.values
    T = 30 / 365
    out = np.full(len(df), np.nan)
    for i in range(len(df) - spec["days"]):
        if np.isnan(iv[i]) or iv[i] <= 0 or np.isnan(c[i]) or np.isnan(c[i + spec["days"]]):
            continue
        prem = 2 * (2 * norm_cdf(iv[i] * sqrt(T) / 2) - 1)
        out[i] = 1 - abs(c[i + spec["days"]] / c[i] - 1) / prem
    return out


# ---- the test

def pick_excess(index, ret, signals, h, sign, cfg, rng, first, last, pool_mask=None):
    """(trigger, net, excess) per event: entry at the next bar, random entries from the same market and year as the comparison."""
    years = index.year.values
    inside = (index >= first) & (index < last)
    events = [p for p in spaced(signals & inside, h) if p + 1 < len(ret)]
    entries = [p + 1 for p in events]
    base = inside & ~np.isnan(ret)
    if pool_mask is not None:
        base &= np.r_[False, pool_mask[:-1]]  # the comparison enters the bar after a pool day, like the events
    for x in entries:
        base[max(0, x - h + 1):x + h] = False
    out = []
    for p, e in zip(events, entries):
        if np.isnan(ret[e]):
            continue
        pool = np.flatnonzero(base & (years == years[e]))
        if len(pool) < cfg["test"]["min_pool"]:
            continue
        s = sign[p] if isinstance(sign, np.ndarray) else sign
        out.append((index[p].isoformat(), float(s * ret[e]), float(s * (ret[e] - ret[rng.choice(pool, cfg["test"]["baseline_draws"])].mean()))))
    return out


def stats_of(values, alternative, cfg, m_tests):
    v = np.asarray(values, float)
    n = len(v)
    a = cfg["test"]["family_alpha"] / m_tests
    power = power_at(n, cfg["test"]["power_d"], a / (2 if alternative == "two-sided" else 1))
    if n < 3 or v.std(ddof=1) == 0:
        return {"clusters": n, "mean": float(v.mean()) if n else None, "p": None, "power": power}
    t, p = stats.ttest_1samp(v, 0, alternative=alternative)
    means = v[np.random.default_rng(cfg["test"]["baseline_seed"]).integers(0, n, (cfg["test"]["bootstrap_reps"], n))].mean(axis=1)
    boot = {"greater": (means <= 0).mean(), "less": (means >= 0).mean(), "two-sided": 2 * min((means <= 0).mean(), (means >= 0).mean())}[alternative]
    return {"clusters": n, "mean": float(v.mean()), "sd": float(v.std(ddof=1)), "d": float(v.mean() / v.std(ddof=1)), "t": float(t), "p": float(p),
            "boot_p": float(boot), "ci90": [float(np.quantile(means, .05)), float(np.quantile(means, .95))], "power": power, "passes_t3": bool(abs(t) >= cfg["test"]["also_report_t"])}


def holm(results, cfg):
    """Holm's step-down: the k-th smallest p must beat alpha / (m - k + 1), and the first failure stops it."""
    m, alpha = len(results), cfg["test"]["family_alpha"]
    order = sorted((r["p"], k) for k, r in results.items() if r.get("p") is not None)
    rejected, stop = set(), False
    for rank, (p, k) in enumerate(order):
        if not stop and p < alpha / (m - rank):
            rejected.add(k)
        else:
            stop = True
    for k, r in results.items():
        r["holm_threshold"] = None
        if r.get("p") is not None:
            rank = [x[1] for x in order].index(k)
            r["holm_threshold"] = alpha / (m - rank)
        r["outcome"] = "supportata" if k in rejected else ("non supportata" if r["power"] >= cfg["test"]["power_min"] else "non informativa")
    return results


def summarise(rows, alternative, cfg, m_tests):
    df = pd.DataFrame(rows, columns=["class", "market", "trigger", "net", "excess"])
    if df.empty:
        return {**stats_of([], alternative, cfg, m_tests), "events": 0}
    g = df.assign(cluster=assign_clusters(df.trigger, cfg["test"]["merge_days"])).groupby("cluster")
    res = stats_of(g.excess.mean().values, alternative, cfg, m_tests)
    return {**res, "events": len(df), "mean_net": float(g.net.mean().mean()), "share_positive": float((df.net > 0).mean()),
            "per_class": {c: {"events": int((df["class"] == c).sum()), "mean_excess": float(df[df["class"] == c].excess.mean()), "mean_net": float(df[df["class"] == c].net.mean())} for c in sorted(df["class"].unique())}}


def collect(cfg, count_only=False):
    """Every event of every hypothesis. With count_only, no return is ever computed: the events and their dates alone."""
    first, last = (pd.Timestamp(cfg["period"][k], tz="UTC") for k in ("from", "to"))
    H, rng = cfg["hypotheses"], np.random.default_rng(cfg["test"]["baseline_seed"])
    cost = 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    rows = {k: [] for k in H}
    for m in all_markets():
        d = K.daily_ohlc(m)
        if d is None or len(d) < 400:
            continue
        d = d.copy()
        d.index = pd.to_datetime(d.index, utc=True).normalize()
        d = d[~d.index.duplicated(keep="last")]
        sig, pools, move_sign = price_signals(m, d, cfg)
        o, c = d.open.values.astype(float), d.close.values.astype(float)
        for k, flags in sig.items():
            h = H[k]["horizon_bars"]
            if count_only:
                inside = (d.index >= first) & (d.index < last)
                rows[k] += [(class_of(m), m, d.index[p].isoformat(), None, None) for p in spaced(flags & inside, h)]
                continue
            sign = move_sign if k == "M1" else (-1 if k in SHORT else 1)
            ev = pick_excess(d.index, horizon_returns(o, c, h, 0.0), flags, h, sign, cfg, rng, first, last, pools.get(k))
            rows[k] += [(class_of(m), m, t, n - cost, x) for t, n, x in ev]  # costs are paid on shorts too
    th = cfg["option_thresholds"]
    opt_rows, uncond = {"O1": [], "O2": []}, {}
    for name, spec in cfg["options_markets"].items():
        df = option_series(name, spec)
        if df is None:
            continue
        ratio = df.ratio.values
        with np.errstate(invalid="ignore"):
            flags = {"O1": ratio > th["dear_above"], "O2": ratio < th["cheap_below"]}
        if count_only:
            inside = (df.index >= first) & (df.index < last)
            for k in flags:
                opt_rows[k] += [("options", name, df.index[p].isoformat(), None, None) for p in spaced(flags[k] & inside, spec["days"])]
            continue
        seller = straddle_pnl(df, spec)
        spread = 2 * cfg["costs"]["option_spread_of_premium_per_side"][name]
        inside = (df.index >= first) & (df.index < last) & ~np.isnan(seller)
        uncond[name] = {"days": int(inside.sum()), "seller_mean_on_premium": float(np.nanmean(seller[inside])), "seller_net_mean": float(np.nanmean(seller[inside]) - spread),
                        "seller_share_positive": float((seller[inside] > 0).mean()), "worst": float(np.nanmin(seller[inside])) if inside.any() else None,
                        "dear_days_share": float(np.nanmean(flags["O1"][inside])), "cheap_days_share": float(np.nanmean(flags["O2"][inside]))}
        for k, sign in (("O1", 1), ("O2", -1)):
            ev = pick_excess(df.index, seller, flags[k], spec["days"], sign, cfg, rng, first, last)
            opt_rows[k] += [("options", name, t, n - spread, x) for t, n, x in ev]
    rows.update(opt_rows)
    return rows, uncond


def run(cfg):
    rows, uncond = collect(cfg)
    H = cfg["hypotheses"]
    res = {k: summarise(rows[k], H[k]["alternative"], cfg, len(H)) for k in H}
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": cfg["period"],
            "results": holm(res, cfg), "options_unconditional": uncond}


def counts(cfg):
    rows, _ = collect(cfg, count_only=True)
    out = {}
    for k, r in rows.items():
        df = pd.DataFrame(r, columns=["class", "market", "trigger", "net", "excess"])
        out[k] = {"events": len(df), "clusters": int(len(set(assign_clusters(df.trigger, cfg["test"]["merge_days"])))) if len(df) else 0}
    return out


def report(r, cfg):
    H = cfg["hypotheses"]
    pct = lambda x: "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.2f}%"
    unit = lambda k: "del premio" if k.startswith("O") else ""
    lines = [f"# Pre-registrazione v3, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             "Ogni riga è un'ipotesi della pre-registrazione. «Eccesso» è quanto l'operazione ha reso in più di ingressi casuali sullo stesso mercato nello stesso anno, "
             "nel verso della lettura (per le opzioni, in quota del premio). La soglia di Holm tiene al 5% la probabilità di anche un solo falso «supportata» su tutte e quindici.", "",
             "| ID | Lettura | Operazione | Esito | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |", "|---|---|---|---|---:|---:|---:|---:|---:|:---:|"]
    for k, x in r["results"].items():
        h = H[k]
        lines.append(f"| {k} | {h['tool']}: {h['reading']} | {h['trade']} | **{x['outcome']}** | {x['clusters']} | {pct(x.get('mean'))} {unit(k)} | "
                     + (f"{x['p']:.4f}" if x.get("p") is not None else "–") + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–")
                     + f" | {pct(x.get('mean_net'))} | " + ("sì" if x.get("passes_t3") else "no") + " |")
    lines += ["", "## Opzioni senza condizioni", "", "Vendere ogni giorno uno straddle a 30 giorni, prezzato all'indice di volatilità: quanto resta al venditore, in quota del premio.", "",
              "| Mercato | Giorni | Medio lordo | Medio netto dello spread | Positivi | Peggiore | Giorni «care» | Giorni «economiche» |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for m, u in r["options_unconditional"].items():
        lines.append(f"| {m} | {u['days']} | {pct(u['seller_mean_on_premium'])} | {pct(u['seller_net_mean'])} | {100 * u['seller_share_positive']:.0f}% | {pct(u['worst'])} | {100 * u['dear_days_share']:.0f}% | {100 * u['cheap_days_share']:.0f}% |")
    lines += ["", "## Per classe (descrittivo)", ""]
    for k, x in r["results"].items():
        if x.get("per_class"):
            lines.append(f"- **{k}**: " + "; ".join(f"{c} {v['events']} eventi, eccesso {pct(v['mean_excess'])}, netto {pct(v['mean_net'])}" for c, v in x["per_class"].items()))
    lines += ["", "Le righe per classe e la tabella delle opzioni senza condizioni sono descrittive, come stabilito nella pre-registrazione."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in DOC.read_text():
        print("la configurazione v3 non coincide con la pre-registrazione: niente test")
        return 1
    if cmd == "conta":
        for k, c in counts(cfg).items():
            print(f"{k}: {c['events']} eventi, {c['clusters']} cluster")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test v3 è già stato fatto: non si rifà")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test si fa una volta sola")
            return 1
        r = run(cfg)
        RESULTS.write_text(json.dumps(r, indent=1, default=float))
        REPORT.write_text(report(r, cfg))
        for k, x in r["results"].items():
            print(f"{k}: {x['outcome']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
