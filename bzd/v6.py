"""Pre-registration v6: the liquidity readings and the Fed's projections added on 24 November 2026 (docs/PREREGISTRAZIONE_v6.md).

    python -m bzd.v6 conta               free: events and clusters per hypothesis. No returns
    python -m bzd.v6 storico --confirm   the one test, once. Refuses to run twice or if the config changed

Same method as v3-v5: each event's return against random entries on the same market in the same year, clusters of
events within 3 days counted once, one-sided t-test with bootstrap, Holm at 5% across the family.
Macro readings are dated on the day the number was public, not the day it refers to.
"""
import hashlib, json, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import history as HI
from . import liquidity as LQ
from . import v3 as V3
from .b3 import horizon_returns
from .events import read
from .exits import assign_clusters
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v6.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v6.md"
RESULTS = BASE / "config" / "validation_v6_storico.json"
REPORT = BASE / "docs" / "V6_STORICO.md"
SIGN = {"long": 1, "short": -1}
CRYPTO = set(HI.CRYPTO)


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- bars

def bars_of(m):
    """Daily open, close and dollar volume. Crypto from the 4h bars, complete days only; futures from Yahoo."""
    if m in CRYPTO:
        d = read("crypto", f"{m}_candles_4h")
        if d is None:
            return None
        d = d.assign(t=pd.to_datetime(d.t, utc=True, format="ISO8601")).drop_duplicates("t", keep="last").sort_values("t")
        g = d.groupby(d.t.dt.floor("D")).agg(open=("open", "first"), close=("close", "last"), dollar=("volume_usd", "sum"), n=("close", "size"))
        return g[g.n == 6].drop(columns="n")
    d = read("tradfi", HI.safe(m))
    if d is None:
        return None
    d.index = pd.to_datetime(d.date, utc=True).dt.normalize()
    d = d[~d.index.duplicated(keep="last")]
    d = d[(d.open > 0) & (d.close > 0)]
    return pd.DataFrame({"open": d.open, "close": d.close, "dollar": d.close * d.volume.where(d.volume > 0)})


# ---- readings, each as the dates they became public

def top_third(x, lookback):
    """True where x is in the top third of its `lookback` previous values (strictly earlier)."""
    q = x.shift(1).rolling(lookback, min_periods=lookback).quantile(2 / 3)
    return (x >= q) & q.notna()


def weekly(s):
    return s.resample("W-WED").last().dropna()


def l1_dates(cfg):
    net = LQ.net_liquidity()
    d13 = net.diff(13)
    f = top_third(d13, cfg["lookback_weeks"])
    return f[f].index + pd.Timedelta(days=cfg["publication_lag_days"]["fed_balance_sheet"])


def l2_dates(cfg):
    sc = LQ.stablecoins()
    g = (sc / sc.reindex(sc.index - pd.Timedelta(days=30), method="ffill").values - 1).dropna()
    w = weekly(g)
    f = top_third(w, cfg["lookback_weeks"])
    return f[f].index + pd.Timedelta(days=cfg["publication_lag_days"]["stablecoins"])


def l3_dates(cfg):
    usd = LQ._fred("DTWEXBGS")
    w = weekly(usd)
    ch = w.pct_change(13)
    f = top_third(ch, cfg["lookback_weeks"])
    return f[f].index + pd.Timedelta(days=cfg["publication_lag_days"]["dollar"])


def f1_dates(cfg):
    d = read("forecasts", "fomc_sep")
    d = d[(d.series == "fed_funds_median") & d.target.astype(str).str.fullmatch(r"\d{4}")].copy()
    d["target"] = d.target.astype(int)
    eds = sorted(d.made.unique())
    out = []
    for prev, cur in zip(eds, eds[1:]):
        y = int(cur[:4]) + 1
        a = d[(d.made == cur) & (d.target == y)].value
        b = d[(d.made == prev) & (d.target == y)].value
        if len(a) and len(b) and a.iloc[0] - b.iloc[0] >= 0.25 - 1e-9:
            out.append(pd.Timestamp(cur, tz="UTC"))
    return pd.DatetimeIndex(out)


def l4_flags(bars, cfg):
    """Amihud over 20 sessions at or above the 90th percentile of the 3 years before, on the same market."""
    ret = np.log(bars.close).diff().abs()
    am = (ret / bars.dollar).rolling(LQ.WINDOW, min_periods=LQ.WINDOW).mean()
    n = cfg["lookback_weeks"] * 5
    q = am.shift(1).rolling(n, min_periods=n // 2).quantile(0.9)
    return ((am >= q) & q.notna()).values


def on_bars(index, dates):
    """The first session on or after each date."""
    flags = np.zeros(len(index), bool)
    dates = pd.DatetimeIndex(dates)
    dates = dates.tz_localize("UTC") if dates.tz is None else dates
    pos = index.searchsorted(dates)
    flags[pos[pos < len(index)]] = True
    return flags


# ---- the test

def collect(cfg, count_only=False):
    first, last = (pd.Timestamp(cfg["period"][k], tz="UTC") for k in ("from", "to"))
    H, rng = cfg["hypotheses"], np.random.default_rng(cfg["test"]["baseline_seed"])
    cost = 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    dates = {"L1": l1_dates(cfg), "L2": l2_dates(cfg), "L3": l3_dates(cfg), "F1": f1_dates(cfg)}
    rows, used, bars_cache = {k: [] for k in H}, set(), {}
    for k, h in H.items():
        for m in cfg["markets"][h["markets"]]:
            if m not in bars_cache:
                bars_cache[m] = bars_of(m)
            b = bars_cache[m]
            if b is None or len(b) < cfg["min_bars"]:
                continue
            used.add(m)
            flags = l4_flags(b, cfg) if k == "L4" else on_bars(b.index, dates[k])
            klass = "cripto" if m in CRYPTO else "futures"
            if count_only:
                inside = (b.index >= first) & (b.index < last)
                rows[k] += [(klass, m, b.index[p].isoformat(), None, None) for p in V3.spaced(flags & inside, h["horizon_bars"])]
                continue
            o, c = b.open.values.astype(float), b.close.values.astype(float)
            ev = pick_excess(b.index, horizon_returns(o, c, h["horizon_bars"], 0.0), flags, h["horizon_bars"], SIGN[h["trade"]], cfg, rng, first, last, b.index.year.values)
            rows[k] += [(klass, m, t, n - cost, x) for t, n, x in ev]
    return rows, sorted(used)


def pick_excess(index, ret, signals, h, sign, cfg, rng, first, last, group):
    from .v5 import pick_excess as v5_pick  # the same comparison as v5, kept in one place
    return v5_pick(index, ret, signals, h, sign, cfg, rng, first, last, group)


def counts(cfg):
    rows, used = collect(cfg, count_only=True)
    out = {}
    for k, r in rows.items():
        df = pd.DataFrame(r, columns=["class", "market", "trigger", "net", "excess"])
        out[k] = {"events": len(df), "clusters": int(len(set(assign_clusters(df.trigger, cfg["test"]["merge_days"])))) if len(df) else 0,
                  "first": df.trigger.min()[:10] if len(df) else None}
    return out, used


def run(cfg):
    rows, used = collect(cfg)
    H = cfg["hypotheses"]
    res = {k: V3.summarise(rows[k], H[k]["alternative"], cfg, len(H)) for k in H}
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": cfg["period"], "markets_used": used,
            "results": V3.holm(res, cfg)}


def report(r, cfg):
    H = cfg["hypotheses"]
    pct = lambda x: "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.2f}%"
    lines = [f"# Pre-registrazione v6, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             "Le letture della liquidità e le proiezioni della Fed aggiunte all'app il 24 novembre 2026 ([PREREGISTRAZIONE_v6.md](PREREGISTRAZIONE_v6.md)). "
             "«Eccesso» è quanto l'operazione ha reso in più di ingressi casuali sullo stesso mercato nello stesso anno, nel verso dell'operazione. "
             "Eventi entro 3 giorni su mercati diversi contano una volta. Holm al 5% sulle cinque.", "",
             "| ID | Lettura | Operazione | Esito | Eventi | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|:---:|"]
    for k, x in r["results"].items():
        h = H[k]
        lines.append(f"| {k} | {h['reading']} | {h['trade']}, {h['horizon_bars']} sedute | **{x['outcome']}** | {x.get('events', 0)} | {x['clusters']} | {pct(x.get('mean'))} | "
                     + (f"{x['p']:.4f}" if x.get("p") is not None else "–") + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–")
                     + f" | {pct(x.get('mean_net'))} | " + ("sì" if x.get("passes_t3") else "no") + " |")
    lines += ["", "## Per tipo di mercato", "", "| ID | Tipo | Eventi | Eccesso medio | Netto medio |", "|---|---|---:|---:|---:|"]
    for k, x in r["results"].items():
        for c, v in (x.get("per_class") or {}).items():
            lines.append(f"| {k} | {c} | {v['events']} | {pct(v['mean_excess'])} | {pct(v['mean_net'])} |")
    lines += ["", "Una lettura supportata qui resta «non testata sui dati futuri» finché non passa una prova sui dati che arrivano da ora in avanti."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v6 non coincide con la pre-registrazione: niente conteggi e niente test")
        return 1
    if cmd == "conta":
        out, used = counts(cfg)
        print(f"{len(used)} mercati")
        for k, c in out.items():
            print(f"{k}: {c['events']} eventi, {c['clusters']} cluster, dal {c['first']}")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test v6 è già stato fatto: non si rifà")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test si fa una volta sola")
            return 1
        r = run(cfg)
        RESULTS.write_text(json.dumps(r, indent=1, ensure_ascii=False))
        REPORT.write_text(report(r, cfg))
        for k, x in r["results"].items():
            print(f"{k}: {x['outcome']}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
