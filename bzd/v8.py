"""Pre-registration v8 (docs/PREREGISTRAZIONE_v8.md): crypto fear and euphoria on history, and a forward test.

    python -m bzd.v8 conta               free: events and clusters of the historical part. No returns
    python -m bzd.v8 storico --confirm   the historical test of G1 and G2, once
    python -m bzd.v8 futuro              the forward test: counts only, and a look at 20, 40 and 60 clusters (or 24 Nov 2028)
                                         with O'Brien-Fleming thresholds (config/setups_v8_sequenziale.json). Safe to run every day

G1 measures size, not direction: the absolute return over 3 days against random entries.
The forward part uses only bars after the start date. Since the amendment of 25 November 2026, written before any event,
only P1 and A1 are tested, at 2.5% each (5% for the other once one is supported); D1, G1 and G2 are closed unseen.
"""
import hashlib, json, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import v3 as V3
from . import v6 as V6
from . import v7 as V7
from .b3 import horizon_returns
from .events import read
from .exits import assign_clusters
from .history import CRYPTO
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v8.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v8.md"
SEQ = BASE / "config" / "setups_v8_sequenziale.json"
RESULTS = BASE / "config" / "validation_v8_storico.json"
REPORT = BASE / "docs" / "V8_STORICO.md"
# Forward results live in data/, which deploys never touch: a frozen verdict must survive every update of the code
def forward_dir():
    from .history import root
    d = root().parent / "v8"
    d.mkdir(parents=True, exist_ok=True)
    return d
SIGN = {"long": 1, "short": -1, "ampiezza": 1}


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fear_greed_dates(cfg, lo=None, hi=None):
    d = read("macro", "fear_greed")
    t = pd.to_datetime(d.date, utc=True)
    f = (d.value <= lo) if lo is not None else (d.value >= hi)
    return pd.DatetimeIndex(t[f.values]) + pd.Timedelta(days=cfg["historical"]["publication_lag_days"])


def returns_for(b, h, trade):
    r = horizon_returns(b.open.values.astype(float), b.close.values.astype(float), h, 0.0)
    return np.abs(r) if trade == "ampiezza" else r


def flags_for(k, b, m, cfg, cache):
    if k == "G1":
        return V6.on_bars(b.index, cache.setdefault("g1", fear_greed_dates(cfg, lo=20)))
    if k == "G2":
        return V6.on_bars(b.index, cache.setdefault("g2", fear_greed_dates(cfg, hi=80)))
    if k == "D1":
        return V6.on_bars(b.index, cache.setdefault("d1", V6.l3_dates(cfg)))
    if k == "A1":
        return V6.l4_flags(b, cfg)
    if k == "P1":
        return (V7.rolling_past_pct(b.close, 252) <= 20).fillna(False).values
    raise KeyError(k)


def collect(cfg, hyps, markets_of, first, last, count_only=False):
    rng = np.random.default_rng(cfg["test"]["baseline_seed"])
    cost = 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    rows, cache, bars = {k: [] for k in hyps}, {}, {}
    from .v5 import pick_excess
    for k, h in hyps.items():
        for m in markets_of(k):
            if m not in bars:
                bars[m] = V6.bars_of(m)
            b = bars[m]
            if b is None or len(b) < cfg["min_bars"]:
                continue
            flags = flags_for(k, b, m, cfg, cache)
            n = h["horizon_bars"]
            klass = "cripto" if m in CRYPTO else "futures"
            if count_only:
                inside = (b.index >= first) & (b.index < last)
                rows[k] += [(klass, m, b.index[p].isoformat(), None, None) for p in V3.spaced(flags & inside, n)]
                continue
            ev = pick_excess(b.index, returns_for(b, n, h["trade"]), flags, n, SIGN[h["trade"]], cfg, rng, first, last, b.index.year.values)
            # size has no trading cost to subtract: it is a measure, not a trade
            rows[k] += [(klass, m, t, x - (0 if h["trade"] == "ampiezza" else cost), e) for t, x, e in ev]
    return rows


def clusters(rows, cfg):
    df = pd.DataFrame(rows, columns=["class", "market", "trigger", "net", "excess"])
    return int(len(set(assign_clusters(df.trigger, cfg["test"]["merge_days"])))) if len(df) else 0


def historical(cfg, count_only=False):
    H = cfg["historical"]
    first, last = (pd.Timestamp(H["period"][k], tz="UTC") for k in ("from", "to"))
    return collect(cfg, H["hypotheses"], lambda k: H["markets"], first, last, count_only)


def load_looks():
    return json.loads(SEQ.read_text())


def seq_hash():
    return hashlib.sha256(SEQ.read_bytes()).hexdigest()


def look_reached(L, clusters, now):
    """Index of the last look a hypothesis has reached: 20, 40, 60 clusters, or the final date whatever the count."""
    i = None
    for j, x in enumerate(L["looks"]):
        if clusters >= x["clusters"] or ("or_on" in x and now >= pd.Timestamp(x["or_on"], tz="UTC")):
            i = j
    return i


def forward_state(cfg, now=None):
    """Counts for the hypotheses still open, and the results already judged (frozen, never recomputed). The three closed
    by the amendment of 25 November 2026 (config/setups_v8_sequenziale.json) are neither counted nor tested."""
    F, L = cfg["forward"], load_looks()
    now = now or pd.Timestamp.now(tz="UTC")
    first = pd.Timestamp(F["start"], tz="UTC")
    fp, lp = forward_dir() / "giudicate.json", forward_dir() / "sguardi.json"
    done = json.loads(fp.read_text()) if fp.exists() else {}
    seen = json.loads(lp.read_text()) if lp.exists() else {}
    open_ = {k: F["hypotheses"][k] for k in L["open"]}
    counts = collect(cfg, open_, lambda k: F["markets"][F["hypotheses"][k]["markets"]], first, now, count_only=True)
    state = {}
    for k, h in F["hypotheses"].items():
        if k in L["closed"]:
            state[k] = {"reading": h["reading"], "events": None, "clusters": None, "due": False, "judged": True,
                        "result": {"outcome": "chiusa senza guardare", "judged_on": "2026-11-25", "why": L["closed"][k], "seq_sha256": seq_hash()}}
            continue
        c = clusters(counts[k], cfg)
        i = look_reached(L, c, now)
        taken = seen.get(k, [])
        nxt = next((x["clusters"] for x in L["looks"] if x["look"] > len(taken) and x["clusters"] > c), None)
        state[k] = {"reading": h["reading"], "events": len(counts[k]), "clusters": c, "due": i is not None and i + 1 not in taken and k not in done,
                    "look": i, "looks_done": len(taken), "next_look_clusters": nxt, "judged": k in done, "result": done.get(k)}
    return state, done, seen


def judge_forward(cfg, now=None):
    """At each look a hypothesis reaches, its p is compared with the O'Brien-Fleming threshold for its alpha: 2.5%, or 5%
    once the other open one is supported. Supported is final; not supported only at the last look."""
    F, L = cfg["forward"], load_looks()
    now = now or pd.Timestamp.now(tz="UTC")
    state, done, seen = forward_state(cfg, now)
    last = len(L["looks"]) - 1
    res = {}
    for k, s in state.items():
        if s["due"]:
            h = F["hypotheses"][k]
            rows = collect(cfg, {k: h}, lambda _: F["markets"][h["markets"]], pd.Timestamp(F["start"], tz="UTC"), now)[k]
            res[k] = V3.summarise(rows, h["alternative"], cfg, len(L["open"]))
    changed = True
    while changed:
        changed = False
        for k, r in res.items():
            if k in done:
                continue
            other_won = any(done.get(o, {}).get("outcome") == "supportata" for o in L["open"] if o != k)
            a = "0.05" if other_won else "0.025"
            i = state[k]["look"]
            thr = L["p_below"][a][i]
            if r.get("p") is not None and r["p"] < thr and r.get("mean", 0) > 0:
                done[k] = {**r, "outcome": "supportata", "threshold": thr, "look": i + 1, "judged_on": now.isoformat(timespec="seconds"),
                           "config_sha256": config_hash(), "seq_sha256": seq_hash()}
                changed = True
    for k, r in res.items():
        i = state[k]["look"]
        if k not in done and i == last:
            other_won = any(done.get(o, {}).get("outcome") == "supportata" for o in L["open"] if o != k)
            done[k] = {**r, "outcome": "non supportata" if r.get("p") is not None else "non informativa", "threshold": L["p_below"]["0.05" if other_won else "0.025"][i],
                       "look": i + 1, "judged_on": now.isoformat(timespec="seconds"), "config_sha256": config_hash(), "seq_sha256": seq_hash()}
        seen.setdefault(k, []).append(i + 1)
        state[k].update(judged=k in done, result=done.get(k), looks_done=len(seen[k]), due=False)
    (forward_dir() / "giudicate.json").write_text(json.dumps(done, indent=1, ensure_ascii=False))
    (forward_dir() / "sguardi.json").write_text(json.dumps(seen, indent=1, ensure_ascii=False))
    (forward_dir() / "stato.json").write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "start": F["start"], "state": state}, indent=1, ensure_ascii=False, default=str))
    return state


def report(r, cfg):
    H = cfg["historical"]["hypotheses"]
    pct = lambda x: "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.2f}%"
    lines = [f"# Pre-registrazione v8, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}", "",
             f"Eseguito il {r['run'][:10]}, una sola volta, sulle 9 cripto. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             "Due idee del supervisore degli agenti di ricerca, dalla letteratura sulla psicologia dei mercati ([PREREGISTRAZIONE_v8.md](PREREGISTRAZIONE_v8.md)). "
             "G1 misura l'ampiezza: quanto si muove il prezzo in valore assoluto, in più di ingressi casuali. G2 è uno short: quanto rende in più di ingressi casuali. Holm al 5% sulle due.", "",
             "| ID | Lettura | Misura | Esito | Eventi | Cluster | Eccesso medio | p | Soglia Holm |", "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for k, x in r["results"].items():
        h = H[k]
        lines.append(f"| {k} | {h['reading']} | {h['measure']}, {h['horizon_bars']} giorni | **{x['outcome']}** | {x.get('events', 0)} | {x['clusters']} | {pct(x.get('mean'))} | "
                     + (f"{x['p']:.4f}" if x.get("p") is not None else "–") + " | " + (f"{x['holm_threshold']:.4f}" if x.get("holm_threshold") else "–") + " |")
    lines += ["", "Una lettura supportata qui va comunque provata sui dati futuri (`python -m bzd.v8 futuro`) prima di entrare in un setup."]
    return "\n".join(lines) + "\n"


def forward_page(state, cfg):
    F = cfg["forward"]
    pct = lambda x: "–" if x is None else f"{100 * x:+.2f}%"
    lines = ["# v8, prova sui dati futuri", "", f"Dal {F['start']}. Con l'emendamento del 25 novembre 2026 (scritto con 0 eventi) restano aperte P1 e A1, al 2,5% ciascuna: "
             "si guardano a 20, 40 e 60 cluster, o comunque il 24 novembre 2028, con soglie di O'Brien-Fleming (0,0001, 0,006, 0,023). "
             "D1, G1 e G2 sono chiuse senza guardare. Tra uno sguardo e l'altro si contano solo gli eventi.",
             f"Aggiornato il {datetime.now(timezone.utc):%Y-%m-%d}.", "",
             "| ID | Lettura | Eventi | Cluster | Stato | Eccesso medio | p |", "|---|---|---:|---:|---|---:|---:|"]
    for k, s in state.items():
        r = s["result"] or {}
        st = f"**{r['outcome']}** il {r['judged_on'][:10]}" if s["judged"] else f"in raccolta, sguardi fatti {s['looks_done']}"
        lines.append(f"| {k} | {s['reading']} | {s['events'] if s['events'] is not None else '–'} | {s['clusters'] if s['clusters'] is not None else '–'} | {st} | {pct(r.get('mean'))} | " + (f"{r['p']:.4f}" if r.get("p") is not None else "–") + " |")
    return "\n".join(lines) + "\n"


def daily():
    """Called by the alerts service once a day: counts, and judges a hypothesis once it is due. Never raises."""
    try:
        cfg = load_config()
        doc = DOC.read_text()
        if config_hash() in doc and seq_hash() in doc:
            state = judge_forward(cfg)
            (forward_dir() / "V8_FUTURO.md").write_text(forward_page(state, cfg))
    except Exception as e:  # noqa: BLE001 - a forward count must never stop the alerts
        print(f"v8 futuro non aggiornato: {type(e).__name__}: {e}", flush=True)


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v8 non coincide con la pre-registrazione: niente conteggi e niente test")
        return 1
    if cmd == "conta":
        rows = historical(cfg, count_only=True)
        for k, r in rows.items():
            print(f"{k}: {len(r)} eventi, {clusters(r, cfg)} cluster")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test storico v8 è già stato fatto: non si rifà")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test si fa una volta sola")
            return 1
        rows = historical(cfg)
        H = cfg["historical"]["hypotheses"]
        res = V3.holm({k: V3.summarise(rows[k], H[k]["alternative"], cfg, len(H)) for k in H}, cfg)
        r = {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": cfg["historical"]["period"], "results": res}
        RESULTS.write_text(json.dumps(r, indent=1, ensure_ascii=False))
        REPORT.write_text(report(r, cfg))
        for k, x in res.items():
            print(f"{k}: {x['outcome']}")
        return 0
    if cmd == "futuro":
        state = judge_forward(cfg)
        (forward_dir() / "V8_FUTURO.md").write_text(forward_page(state, cfg))
        for k, s in state.items():
            print(f"{k}: " + (f"{s['clusters']} cluster, " if s["clusters"] is not None else "") + (s["result"]["outcome"] if s["judged"] else "in raccolta"))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
