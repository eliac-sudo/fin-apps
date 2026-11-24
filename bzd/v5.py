"""Pre-registration v5: BYZ and SZT at the extremes and on monthly bars, read as their names say, on single US stocks (docs/PREREGISTRAZIONE_v5.md).

    python -m bzd.v5 scarica             free: download the daily bars of the stocks. No returns
    python -m bzd.v5 conta               free: events and clusters per hypothesis. No returns
    python -m bzd.v5 storico --confirm   the one test, once. Refuses to run twice or if the config changed

v4 found momentum after the tags, but at -70 the price bounced, and a descriptive look had the names right on monthly bars only.
Both were seen after the fact, so they're tested here on 100 single stocks the program never used. Same score, same method;
the monthly comparison draws from the whole period of the same stock, because a year has only twelve months.
"""
import hashlib, json, sys, time, urllib.parse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import history as HI
from . import v3 as V3
from . import zones as ZN
from .b3 import horizon_returns
from .exits import assign_clusters
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v5.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v5.md"
RESULTS = BASE / "config" / "validation_v5_storico.json"
REPORT = BASE / "docs" / "V5_STORICO.md"
GROUP = "v5"
SIGN = {"E1": 1, "E2": -1, "E3": 1, "E4": -1}


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---- data

def download(cfg, log=print):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for m in cfg["markets"]:
        name = HI.safe(m)
        if HI.done(GROUP, name):
            continue
        try:
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(m)}?interval=1d&period1=0&period2={int(time.time())}"
            d = HI.parse_yahoo(HI.get(GROUP, name, 0, u))
        except Exception as e:
            log(f"  {m}: {e}")
            continue
        HI.save(GROUP, name, d[d.date < today][["date", "open", "high", "low", "close", "volume"]])


def daily_bars(m):
    p = HI.root() / GROUP / f"{HI.safe(m)}.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d.index = pd.to_datetime(d.date, utc=True).dt.normalize()
    d = d[~d.index.duplicated(keep="last")][["open", "high", "low", "close"]].dropna()
    return d[(d.low > 0) & (d.high >= d.low)]


def monthly_bars(d, last_day):
    """Calendar months from the sessions, dated on the month's first day. The month still running on last_day is dropped."""
    m = d.resample("MS").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return m[m.index + pd.offsets.MonthBegin(1) <= last_day]


# ---- the test

def flags_of(d, frame):
    s = ZN.indicator_score(d, frame)[0].values
    with np.errstate(invalid="ignore"):
        if frame == "1d":
            return {"E1": s <= -70, "E2": s >= 70}
        return {"E3": s <= ZN.BYZ_BELOW, "E4": s >= ZN.SZT_ABOVE}


def pick_excess(index, ret, signals, h, sign, cfg, rng, first, last, group):
    """v3's comparison with the pool drawn from bars sharing `group` with the entry: the year on daily bars, one group on monthly bars."""
    inside = (index >= first) & (index < last)
    events = [p for p in V3.spaced(signals & inside, h) if p + 1 < len(ret)]
    entries = [p + 1 for p in events]
    base = inside & ~np.isnan(ret)
    for x in entries:
        base[max(0, x - h + 1):x + h] = False
    out = []
    for p, e in zip(events, entries):
        if np.isnan(ret[e]):
            continue
        pool = np.flatnonzero(base & (group == group[e]))
        if len(pool) < cfg["test"]["min_pool"]:
            continue
        out.append((index[p].isoformat(), float(sign * ret[e]), float(sign * (ret[e] - ret[rng.choice(pool, cfg["test"]["baseline_draws"])].mean()))))
    return out


def collect(cfg, count_only=False):
    first, last = (pd.Timestamp(cfg["period"][k], tz="UTC") for k in ("from", "to"))
    H, rng = cfg["hypotheses"], np.random.default_rng(cfg["test"]["baseline_seed"])
    cost = 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    rows, used = {k: [] for k in H}, []
    for m in cfg["markets"]:
        d = daily_bars(m)
        if d is None:
            continue
        frames = {"1d": d, "1M": monthly_bars(d, last)}
        if len(frames["1d"]) < cfg["min_bars"]["1d"]:
            continue
        used.append(m)
        for frame, bars in frames.items():
            if len(bars) < cfg["min_bars"][frame]:
                continue
            o, cl = bars.open.values.astype(float), bars.close.values.astype(float)
            group = bars.index.year.values if frame == "1d" else np.zeros(len(bars), int)
            for k, flags in flags_of(bars, frame).items():
                h = H[k]["horizon_bars"]
                if count_only:
                    inside = (bars.index >= first) & (bars.index < last)
                    rows[k] += [("azioni", m, bars.index[p].isoformat(), None, None) for p in V3.spaced(flags & inside, h)]
                    continue
                ev = pick_excess(bars.index, horizon_returns(o, cl, h, 0.0), flags, h, SIGN[k], cfg, rng, first, last, group)
                rows[k] += [("azioni", m, t, n - cost, x) for t, n, x in ev]
    return rows, used


def counts(cfg):
    rows, used = collect(cfg, count_only=True)
    out = {}
    for k, r in rows.items():
        df = pd.DataFrame(r, columns=["class", "market", "trigger", "net", "excess"])
        out[k] = {"events": len(df), "clusters": int(len(set(assign_clusters(df.trigger, cfg["test"]["merge_days"])))) if len(df) else 0}
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
    lines = [f"# Pre-registrazione v5, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta, su {len(r['markets_used'])} azioni USA mai usate dal programma. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             "BYZ e SZT letti come il loro nome: dopo BYZ long, dopo SZT short. Giornaliero agli estremi (±70, 10 sedute) e mensile (±50, 3 mesi). «Eccesso» è quanto l'operazione "
             "ha reso in più di ingressi casuali sullo stesso titolo (stesso anno sul giornaliero, tutto il periodo sul mensile), nel verso dell'operazione. Holm al 5% sulle quattro.", "",
             "| ID | Lettura | Operazione | Esito | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |", "|---|---|---|---|---:|---:|---:|---:|---:|:---:|"]
    for k, x in r["results"].items():
        h = H[k]
        lines.append(f"| {k} | {h['reading']} | {h['trade']}, {h['horizon_bars']} {'sedute' if h['frame'] == '1d' else 'mesi'} | **{x['outcome']}** | {x['clusters']} | {pct(x.get('mean'))} | "
                     + (f"{x['p']:.4f}" if x.get("p") is not None else "–") + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–")
                     + f" | {pct(x.get('mean_net'))} | " + ("sì" if x.get("passes_t3") else "no") + " |")
    lines += ["", "Una lettura supportata qui torna nell'app con il suo nome, ma diventa una regola solo dopo i dati futuri."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if cmd == "scarica":
        download(cfg)
        return 0
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v5 non coincide con la pre-registrazione: niente conteggi e niente test")
        return 1
    if cmd == "conta":
        out, used = counts(cfg)
        print(f"{len(used)} azioni")
        for k, c in out.items():
            print(f"{k}: {c['events']} eventi, {c['clusters']} cluster")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test v5 è già stato fatto: non si rifà")
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
