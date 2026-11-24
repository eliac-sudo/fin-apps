"""Pre-registration v7: a sweep of every pair of readings, with the history split in three (docs/PREREGISTRAZIONE_v7.md).

    python -m bzd.v7 cerca               search 2008-2018, check 2019-2022. Writes the shortlist; never computes a return after 2022
    python -m bzd.v7 esame --confirm     the one exam, 2023-2026, on the shortlist only. Refuses to run twice

Readings are rebuilt day by day from strictly earlier data. An event's holding period must end inside its own period,
so no search or check return ever uses a price from the exam years.
"""
import hashlib, json, sys
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
import pandas as pd

from . import indicators as I
from . import liquidity as LQ
from . import v3 as V3
from . import zones as ZN
from .b3 import horizon_returns
from .events import align_cot, read
from .exits import assign_clusters
from .history import CRYPTO, safe
from .recorder import BASE
from .setups import VOL_INDEX, load_vol_index
from .thermo import COT_AGAINST_PAIR
from .v6 import bars_of, on_bars, top_third, weekly

CONFIG = BASE / "config" / "setups_v7.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v7.md"
SHORTLIST = BASE / "config" / "v7_shortlist.json"
RESULTS = BASE / "config" / "validation_v7_esame.json"
REPORT = BASE / "docs" / "V7_ESAME.md"
LOW, HIGH = 20, 80


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- readings

def rolling_past_pct(s, n):
    """Percentile of each value among the n values before it."""
    v = s.values.astype(float)
    out = np.full(len(v), np.nan)
    for i in range(n // 2, len(v)):
        w = v[max(0, i - n):i]
        w = w[~np.isnan(w)]
        if len(w) >= n // 2 and not np.isnan(v[i]):
            out[i] = 100 * (w < v[i]).mean()
    return pd.Series(out, s.index)


def macro_states(cfg):
    """Weekly macro states as (dates public, low flags, high flags)."""
    out = {}
    net = LQ.net_liquidity()
    d = net.diff(13)
    out["liquidita_fed"] = (d, cfg["publication_lag_days"]["fed_balance_sheet"])
    usd = weekly(LQ._fred("DTWEXBGS")).pct_change(13)
    out["dollaro"] = (usd, cfg["publication_lag_days"]["dollar"])
    states = {}
    for k, (x, lag) in out.items():
        lo = x <= x.shift(1).rolling(cfg["lookback_weeks"], min_periods=cfg["lookback_weeks"]).quantile(1 / 3)
        hi = top_third(x, cfg["lookback_weeks"])
        ok = x.shift(1).rolling(cfg["lookback_weeks"], min_periods=cfg["lookback_weeks"]).count() >= cfg["lookback_weeks"]
        idx = x.index + pd.Timedelta(days=lag)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx
        states[k] = pd.DataFrame({"lo": (lo & ok).values, "hi": (hi & ok).values}, index=idx)
    return states


def as_of(states, index):
    """A weekly state carried onto daily bars from the day it was public until the next one."""
    s = states.reindex(index, method="ffill", tolerance=pd.Timedelta(days=14))
    return s.lo.fillna(False).astype(bool).values, s.hi.fillna(False).astype(bool).values


def market_frame(m):
    """Daily OHLC and dollar volume for one market."""
    if m in CRYPTO:
        d = read("crypto", f"{m}_candles_4h")
        if d is None:
            return None
        d = d.assign(t=pd.to_datetime(d.t, utc=True, format="ISO8601")).drop_duplicates("t", keep="last").sort_values("t")
        g = d.groupby(d.t.dt.floor("D")).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), dollar=("volume_usd", "sum"), n=("close", "size"))
        g = g[g.n == 6].drop(columns="n")
        g["volume"] = g.dollar
        return g
    d = read("tradfi", safe(m))
    if d is None:
        return None
    d.index = pd.to_datetime(d.date, utc=True).dt.normalize()
    d = d[~d.index.duplicated(keep="last")]
    d = d[(d.open > 0) & (d.close > 0) & (d.high >= d.low)][["open", "high", "low", "close", "volume"]].copy()
    d["dollar"] = d.close * d.volume.where(d.volume > 0)
    return d


def features(m, d, macro):
    """Every reading's low and high state on every bar, as boolean arrays. A reading with no data is all False."""
    c = d.close
    f = {}
    def put(name, x, lo=LOW, hi=HIGH):
        x = pd.Series(x, d.index).astype(float)
        f[name] = ((x <= lo).fillna(False).values, (x >= hi).fillna(False).values)
    put("slancio", I.past_percentile(np.log(c).diff(20)))
    put("rsi", I.rsi(c), 30, 70)
    put("estensione", I.past_percentile(I.sma_distance(c, 200)))
    put("momentum", ZN.indicator_score(d, "1d")[0], -50, 50)
    put("posizione", rolling_past_pct(c, 252))
    cot = read("cot", safe(m)) if m not in CRYPTO else None
    if cot is not None:
        spec = align_cot(cot, d.index).spec_net_pct_oi
        p = I.past_percentile(spec.dropna()).reindex(d.index).ffill()
        put("cot", 100 - p if m in COT_AGAINST_PAIR else p)
    else:
        f["cot"] = (np.zeros(len(d), bool), np.zeros(len(d), bool))
    vi = load_vol_index(VOL_INDEX[m], d.index) if m in VOL_INDEX else None
    put("volatilita", I.past_percentile(vi) if vi is not None else pd.Series(np.nan, d.index))
    vol = d.volume.where(d.volume > 0)
    if vol.notna().sum() > 300:
        n = 3 * 252
        put("volumi", rolling_past_pct(vol.rolling(20, min_periods=10).mean(), n))
        am = (np.log(c).diff().abs() / d.dollar).rolling(20, min_periods=10).mean()
        put("impatto", rolling_past_pct(am, n))
    else:
        f["volumi"] = f["impatto"] = (np.zeros(len(d), bool), np.zeros(len(d), bool))
    for k, st in macro.items():
        f[k] = as_of(st, d.index)
    return f


def conditions(names):
    """Each state alone, then each pair of states of two different readings."""
    out = [((n, s),) for n in names for s in ("lo", "hi")]
    for a, b in combinations(names, 2):
        for sa in ("lo", "hi"):
            for sb in ("lo", "hi"):
                out.append(((a, sa), (b, sb)))
    return out


def label(cond, trade):
    word = {"lo": "basso", "hi": "alto"}
    return " + ".join(f"{n} {word[s]}" for n, s in cond) + f" → {trade}"


# ---- events and the fast comparison used in search and check

def prepare(cfg):
    macro = macro_states(cfg)
    out = {}
    for m in cfg["markets"]:
        d = market_frame(m)
        if d is None or len(d) < 400:
            continue
        h = cfg["horizon_bars"]
        ret = horizon_returns(d.open.values.astype(float), d.close.values.astype(float), h, 0.0)
        out[m] = {"index": d.index, "ret": ret, "year": d.index.year.values, "f": features(m, d, macro)}
    return out


def events(data, cond, period, h):
    """(market, trigger, ret, year mean) for every spaced event whose holding period ends inside the period."""
    a, b = (pd.Timestamp(x, tz="UTC") for x in period)
    rows = []
    for m, x in data.items():
        idx, ret = x["index"], x["ret"]
        flags = np.ones(len(idx), bool)
        for n, s in cond:
            flags &= x["f"][n][0 if s == "lo" else 1]
        inside = (idx >= a) & (idx < b)
        last_ok = np.searchsorted(idx, b) - 1  # the exit bar (entry + h - 1) must be before the next period
        for p in V3.spaced(flags & inside, h):
            e = p + 1
            if e + h - 1 > last_ok or np.isnan(ret[e]):
                continue
            rows.append((m, idx[p].isoformat(), ret[e], x["year"][e]))
    return rows


def year_means(data, period, h):
    """Average 10-session return of every bar of the same market and year whose holding period ends inside the period."""
    a, b = (pd.Timestamp(x, tz="UTC") for x in period)
    out = {}
    for m, x in data.items():
        idx = x["index"]
        last_ok = np.searchsorted(idx, b) - 1
        pos = np.arange(len(idx))
        inside = (idx >= a) & (idx < b) & (pos + h - 1 <= last_ok)
        r = pd.Series(x["ret"][inside], x["year"][inside]).dropna()
        out[m] = r.groupby(level=0).mean().to_dict()
    return out


def fast_stats(rows, sign, ym, cfg):
    if not rows:
        return {"events": 0, "clusters": 0, "mean": None, "t": None}
    df = pd.DataFrame(rows, columns=["market", "trigger", "ret", "year"])
    df["excess"] = sign * (df.ret - [ym[m].get(y, np.nan) for m, y in zip(df.market, df.year)])
    df = df.dropna(subset=["excess"])
    if df.empty:
        return {"events": 0, "clusters": 0, "mean": None, "t": None}
    g = df.assign(cl=assign_clusters(df.trigger, cfg["test"]["merge_days"])).groupby("cl").excess.mean()
    n = len(g)
    t = float(g.mean() / (g.std(ddof=1) / np.sqrt(n))) if n > 2 and g.std(ddof=1) > 0 else None
    return {"events": int(len(df)), "clusters": int(n), "mean": float(g.mean()), "t": t}


def search(cfg, log=print):
    data = prepare(cfg)
    names = list(cfg["features"])
    conds = conditions(names)
    h = cfg["horizon_bars"]
    ym_s, ym_c = year_means(data, cfg["periods"]["search"], h), year_means(data, cfg["periods"]["check"], h)
    found = []
    for cond in conds:
        ev = events(data, cond, cfg["periods"]["search"], h)
        for trade, sign in (("long", 1), ("short", -1)):
            s = fast_stats(ev, sign, ym_s, cfg)
            found.append({"cond": cond, "trade": trade, "label": label(cond, trade), "search": s})
    log(f"{len(found)} regole provate sul periodo di ricerca")
    ok = [r for r in found if r["search"]["clusters"] >= cfg["search"]["min_clusters"] and r["search"]["t"] is not None]
    top = sorted(ok, key=lambda r: -r["search"]["t"])[:cfg["search"]["keep_top"]]
    for r in top:
        ev = events(data, r["cond"], cfg["periods"]["check"], h)
        r["check"] = fast_stats(ev, 1 if r["trade"] == "long" else -1, ym_c, cfg)
        r["passes_check"] = bool(r["check"]["clusters"] >= cfg["check"]["min_clusters"] and (r["check"]["t"] or 0) >= cfg["check"]["min_t"] and (r["check"]["mean"] or 0) > 0)
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tried": len(found), "eligible": len(ok),
            "markets": sorted(data), "top": top, "t_all": sorted([r["search"]["t"] for r in ok])}


# ---- the exam: the v3-v6 method on the survivors only

def exam(cfg, shortlist):
    from .v5 import pick_excess
    data = prepare(cfg)
    a, b = (pd.Timestamp(x, tz="UTC") for x in cfg["periods"]["exam"])
    rng = np.random.default_rng(cfg["test"]["baseline_seed"])
    cost = 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    h = cfg["horizon_bars"]
    keep = [r for r in shortlist["top"] if r["passes_check"]]
    res = {}
    for i, r in enumerate(keep):
        rows = []
        for m, x in data.items():
            flags = np.ones(len(x["index"]), bool)
            for n, s in r["cond"]:
                flags &= x["f"][n][0 if s == "lo" else 1]
            sign = 1 if r["trade"] == "long" else -1
            for t, net, exc in pick_excess(x["index"], x["ret"], flags, h, sign, cfg, rng, a, b, x["year"]):
                rows.append(("cripto" if m in CRYPTO else "futures", m, t, net - cost, exc))
        res[f"C{i + 1}"] = {**V3.summarise(rows, "greater", cfg, len(keep)), "label": r["label"]}
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": cfg["periods"]["exam"],
            "results": V3.holm(res, cfg) if res else {}}


def shortlist_page(s, cfg):
    pct = lambda x: "–" if x is None else f"{100 * x:+.2f}%"
    tt = lambda x: "–" if x is None else f"{x:.2f}"
    t = np.array(s["t_all"])
    lines = ["", "## Risultato della ricerca e del controllo", "",
             f"Eseguiti il {s['run'][:10]}. Regole provate: {s['tried']}; con almeno {cfg['search']['min_clusters']} cluster: {s['eligible']}. "
             f"Sul periodo di ricerca il t delle regole va da {t.min():.1f} a {t.max():.1f}; per puro caso, su {len(t)} regole, ce ne aspetteremmo circa {round(0.05 * len(t))} con t sopra 1,65.", "",
             "| # | Regola | Cluster ricerca | Eccesso ricerca | t ricerca | Cluster controllo | Eccesso controllo | t controllo | Passa |", "|---:|---|---:|---:|---:|---:|---:|---:|:---:|"]
    for i, r in enumerate(s["top"]):
        c = r.get("check", {})
        lines.append(f"| {i + 1} | {r['label']} | {r['search']['clusters']} | {pct(r['search']['mean'])} | {tt(r['search']['t'])} | {c.get('clusters', 0)} | {pct(c.get('mean'))} | {tt(c.get('t'))} | {'sì' if r.get('passes_check') else 'no'} |")
    n = sum(r.get("passes_check", False) for r in s["top"])
    lines += ["", f"Passano il controllo **{n}** regole su {len(s['top'])}. Solo queste vanno all'esame 2023–2026, una volta sola."]
    return "\n".join(lines) + "\n"


def exam_page(r):
    pct = lambda x: "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.2f}%"
    lines = [f"# Pre-registrazione v7, esame {r['period'][0][:4]}–{r['period'][1][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta, sulle regole che avevano passato ricerca e controllo ([PREREGISTRAZIONE_v7.md](PREREGISTRAZIONE_v7.md)). "
             "Stesso metodo di v3–v6: ingressi casuali sullo stesso mercato nello stesso anno, cluster di 3 giorni, Holm al 5%. Non è consulenza finanziaria.", "",
             "| ID | Regola | Esito | Eventi | Cluster | Eccesso medio | p | Soglia Holm | Netto medio |", "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for k, x in r["results"].items():
        lines.append(f"| {k} | {x['label']} | **{x['outcome']}** | {x.get('events', 0)} | {x['clusters']} | {pct(x.get('mean'))} | " + (f"{x['p']:.4f}" if x.get("p") is not None else "–")
                     + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–") + f" | {pct(x.get('mean_net'))} |")
    if not r["results"]:
        lines.append("| – | nessuna regola ha passato il controllo | – | – | – | – | – | – | – |")
    lines += ["", "Una regola supportata qui va ancora provata sui dati futuri prima di diventare un setup."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v7 non coincide con la pre-registrazione: niente ricerca e niente esame")
        return 1
    if cmd == "cerca":
        if SHORTLIST.exists():
            print("la ricerca v7 è già stata fatta: non si rifà")
            return 1
        s = search(cfg)
        SHORTLIST.write_text(json.dumps(s, indent=1, ensure_ascii=False, default=str))
        with open(DOC, "a") as f:
            f.write(shortlist_page(s, cfg))
        print(f"{sum(r.get('passes_check', False) for r in s['top'])} regole passano il controllo")
        return 0
    if cmd == "esame":
        if RESULTS.exists():
            print("l'esame v7 è già stato fatto: non si rifà")
            return 1
        if not SHORTLIST.exists():
            print("prima la ricerca: python -m bzd.v7 cerca")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: l'esame si fa una volta sola")
            return 1
        r = exam(cfg, json.loads(SHORTLIST.read_text()))
        RESULTS.write_text(json.dumps(r, indent=1, ensure_ascii=False))
        REPORT.write_text(exam_page(r))
        for k, x in r["results"].items():
            print(f"{k} {x['label']}: {x['outcome']}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
