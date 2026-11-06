"""Pre-registration v4: BYZ and SZT read as momentum, on markets the program never used (docs/PREREGISTRAZIONE_v4.md).

    python -m bzd.v4 scarica             free: download the daily bars of the new markets. No returns
    python -m bzd.v4 conta               free: events and clusters per hypothesis. No returns
    python -m bzd.v4 storico --confirm   the one test, once. Refuses to run twice or if the config changed

In v3, after BYZ the price kept falling and after SZT it kept rising. That was seen on the program's own 30 markets, so here
the same score, unchanged, is tested the other way round on 50 markets it never touched: altcoins, sector and country ETFs,
other futures and currency pairs. Same method as v3: next-bar entry, random entries on the same market and year, Holm at 5%.
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

CONFIG = BASE / "config" / "setups_v4.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v4.md"
RESULTS = BASE / "config" / "validation_v4_storico.json"
REPORT = BASE / "docs" / "V4_STORICO.md"
GROUP = "v4"
SIGN = {"N1": -1, "N2": 1, "N3": -1, "N4": 1, "N5": -1, "N6": 1}


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markets(cfg):
    return [(c, m) for c, ms in cfg["markets"].items() for m in ms]


# ---- data

def binance_daily(asset):
    """Every daily spot bar since listing, paged 1000 at a time."""
    rows, start = [], 0
    for n in range(40):
        raw = HI.get(GROUP, asset, n, f"https://api.binance.com/api/v3/klines?symbol={asset}USDT&interval=1d&limit=1000&startTime={start}")
        k = json.loads(raw)
        if not k:
            break
        rows += [(HI.to_utc(x[0]).strftime("%Y-%m-%d"), float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])) for x in k]
        if len(k) < 1000:
            break
        start = k[-1][0] + 1
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"]).drop_duplicates("date", keep="last")


def yahoo_daily(sym):
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?interval=1d&period1=0&period2={int(time.time())}"
    d = HI.parse_yahoo(HI.get(GROUP, HI.safe(sym), 0, u))
    return d[["date", "open", "high", "low", "close", "volume"]]


def download(cfg, log=print):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for cls, m in markets(cfg):
        name = HI.safe(m)
        if HI.done(GROUP, name):
            continue
        try:
            d = binance_daily(m) if cls == "crypto" else yahoo_daily(m)
        except Exception as e:
            log(f"  {m}: {e}")
            continue
        HI.save(GROUP, name, d[d.date < today])  # today's bar may still be open


def daily_bars(m):
    p = HI.root() / GROUP / f"{HI.safe(m)}.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d.index = pd.to_datetime(d.date, utc=True).dt.normalize()
    d = d[~d.index.duplicated(keep="last")][["open", "high", "low", "close"]].dropna()
    return d[(d.low > 0) & (d.high >= d.low)]


# ---- signals

def streak_start(flags, n):
    """The bar where a run of `flags` reaches n bars, once per run."""
    out, run = np.zeros(len(flags), bool), 0
    for i, f in enumerate(flags):
        run = run + 1 if f else 0
        out[i] = run == n
    return out


def flags_of(d):
    s = ZN.indicator_score(d, "1d")[0].values
    with np.errstate(invalid="ignore"):
        byz, szt = s <= ZN.BYZ_BELOW, s >= ZN.SZT_ABOVE
        return {"N1": byz, "N2": szt, "N3": streak_start(byz, 3), "N4": streak_start(szt, 3), "N5": s <= -70, "N6": s >= 70}


# ---- the test

def collect(cfg, count_only=False):
    first, last = (pd.Timestamp(cfg["period"][k], tz="UTC") for k in ("from", "to"))
    H, rng = cfg["hypotheses"], np.random.default_rng(cfg["test"]["baseline_seed"])
    rows, used = {k: [] for k in H}, []
    for cls, m in markets(cfg):
        d = daily_bars(m)
        if d is None or len(d) < cfg["min_bars"]:
            continue
        used.append(m)
        c = cfg["costs"]["crypto" if cls == "crypto" else "other"]
        cost = 2 * (c["fee_per_side"] + c["slippage_per_side"])
        o, cl = d.open.values.astype(float), d.close.values.astype(float)
        for k, flags in flags_of(d).items():
            h = H[k]["horizon_bars"]
            if count_only:
                inside = (d.index >= first) & (d.index < last)
                rows[k] += [(cls, m, d.index[p].isoformat(), None, None) for p in V3.spaced(flags & inside, h)]
                continue
            ev = V3.pick_excess(d.index, horizon_returns(o, cl, h, 0.0), flags, h, SIGN[k], cfg, rng, first, last)
            rows[k] += [(cls, m, t, n - cost, x) for t, n, x in ev]
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
    lines = [f"# Pre-registrazione v4, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta, su {len(r['markets_used'])} mercati mai usati dal programma. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             "BYZ e SZT letti al contrario del nome: dopo BYZ short, dopo SZT long, per 10 sedute. «Eccesso» è quanto l'operazione ha reso in più di ingressi casuali "
             "sullo stesso mercato nello stesso anno, nel verso dell'operazione. La soglia di Holm tiene al 5% la probabilità di anche un solo falso «supportata» su tutte e sei.", "",
             "| ID | Lettura | Operazione | Esito | Cluster | Eccesso medio | p | Soglia Holm | Netto medio | t ≥ 3 |", "|---|---|---|---|---:|---:|---:|---:|---:|:---:|"]
    for k, x in r["results"].items():
        h = H[k]
        lines.append(f"| {k} | {h['reading']} | {h['trade']} | **{x['outcome']}** | {x['clusters']} | {pct(x.get('mean'))} | "
                     + (f"{x['p']:.4f}" if x.get("p") is not None else "–") + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–")
                     + f" | {pct(x.get('mean_net'))} | " + ("sì" if x.get("passes_t3") else "no") + " |")
    lines += ["", "## Per classe (descrittivo)", ""]
    for k, x in r["results"].items():
        if x.get("per_class"):
            lines.append(f"- **{k}**: " + "; ".join(f"{c} {v['events']} eventi, eccesso {pct(v['mean_excess'])}, netto {pct(v['mean_net'])}" for c, v in x["per_class"].items()))
    lines += ["", "Le righe per classe sono descrittive, come stabilito nella pre-registrazione. Una lettura supportata qui diventa una regola solo dopo i dati futuri."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if cmd == "scarica":
        download(cfg)
        return 0
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v4 non coincide con la pre-registrazione: niente conteggi e niente test")
        return 1
    if cmd == "conta":
        out, used = counts(cfg)
        print(f"{len(used)} mercati")
        for k, c in out.items():
            print(f"{k}: {c['events']} eventi, {c['clusters']} cluster")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test v4 è già stato fatto: non si rifà")
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
