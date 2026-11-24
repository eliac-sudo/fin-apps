"""Pre-registration v2: the long-trend setup, tested only on data that comes after it was frozen (docs/PREREGISTRAZIONE_v2.md).

    python -m bzd.v2 stato              free: events and clusters so far, and when the test is due. No returns.
    python -m bzd.v2 test --confirm     runs the one test, only once it's due, and only once
    python -m bzd.v2 storico --confirm  the same rule on 2008 to 6 Nov 2026, after the literature that inspired it; once

Until the test is due, nothing here computes a return: `stato` counts events, and a unit test checks it never reads
what came after an entry. The test refuses to run early, refuses to run twice, and refuses if the config changed.
"""
import hashlib, json, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from .b3 import horizon_returns, power_at
from .events import daily, read
from .exits import assign_clusters
from .history import safe
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v2.json"
DOC = BASE / "docs" / "PREREGISTRAZIONE_v2.md"
RESULTS = BASE / "config" / "validation_v2.json"
REPORT = BASE / "docs" / "V2_RISULTATI.md"
MIN_POOL = 20
# Added on 6 Nov 2026, before any return was computed: the same rule on history after the literature that inspired it.
# Park and Irwin's review came out in 2007, so 2008 onward is data the idea's sources never saw.
HISTORICAL = {"from": "2008-01-01", "to": "2026-11-06"}
RESULTS_HIST = BASE / "config" / "validation_v2_storico.json"
REPORT_HIST = BASE / "docs" / "V2_STORICO.md"


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_prices(market):
    return daily(read("tradfi", safe(market)))


def trigger_positions(close, cfg):
    """Bars where the close moves above its long average after closing at or below it, at least `cooldown_bars` apart.

    Uses only closes up to each bar, so the event is known at that bar's close.
    """
    s = cfg["signal"]
    ma = close.rolling(s["length"]).mean()
    above = (close > ma).values
    known = ma.notna().values
    out, last = [], None
    for i in range(1, len(close)):
        if known[i] and known[i - 1] and above[i] and not above[i - 1] and (last is None or i - last >= cfg["cooldown_bars"]):
            out.append(i)
            last = i
    return out


def events(cfg, prices=None, now=None):
    """Every v2 event from the first trigger date on, with whether its whole horizon is in the data. No returns."""
    now = now or datetime.now(timezone.utc)
    first = pd.Timestamp(cfg["first_trigger"], tz="UTC")
    rows = []
    for cls, markets in cfg["markets"].items():
        for m in markets:
            d = prices[m] if prices is not None else load_prices(m)
            for p in trigger_positions(d.close, cfg):
                if d.index[p] < first:
                    continue
                entry = p + cfg["entry_after_bars"]
                rows.append({"class": cls, "market": m, "trigger": d.index[p].isoformat(), "primary": cls in cfg["primary_classes"],
                             "complete": entry + cfg["horizon_bars"] - 1 < len(d)})
    return pd.DataFrame(rows, columns=["class", "market", "trigger", "primary", "complete"])


def clusters(ev, cfg):
    """Primary events pooled across classes: a dollar move can flip currencies and gold together, so they count once."""
    p = ev[ev.primary & ev.complete]
    return int(len(set(assign_clusters(p.trigger, cfg["merge_days"])))) if len(p) else 0


def due(ev, cfg, now=None):
    now = now or datetime.now(timezone.utc)
    n = clusters(ev, cfg)
    deadline = pd.Timestamp(cfg["evaluate"]["deadline"], tz="UTC")
    if n >= cfg["evaluate"]["min_clusters"]:
        return True, f"{n} cluster completi, soglia {cfg['evaluate']['min_clusters']} raggiunta"
    if now >= deadline:
        return True, f"scadenza {cfg['evaluate']['deadline']} raggiunta con {n} cluster"
    return False, f"{n} cluster completi su {cfg['evaluate']['min_clusters']}, scadenza {cfg['evaluate']['deadline']}"


# ---- the one test

def market_excess(d, cfg, first, rng, last=None):
    """(trigger, net, excess) per event on one market: random entries from the same market and year, inside [first, last), away from events."""
    h, cost = cfg["horizon_bars"], 2 * (cfg["costs"]["fee_per_side"] + cfg["costs"]["slippage_per_side"])
    o, c = d.open.values.astype(float), d.close.values.astype(float)
    ret = horizon_returns(o, c, h, cost)
    inside = lambda t: t >= first and (last is None or t < last)
    trig = [p for p in trigger_positions(d.close, cfg) if inside(d.index[p])]
    entries = [p + cfg["entry_after_bars"] for p in trig]
    years, fresh = d.index.year.values, (d.index >= first) & ((d.index < last) if last is not None else True)
    out = []
    for p, e in zip(trig, entries):
        if e >= len(ret) or np.isnan(ret[e]):
            continue
        mask = (years == years[e]) & fresh & ~np.isnan(ret)
        for x in entries:
            mask[max(0, x - h + 1):x + h] = False
        pool = np.flatnonzero(mask)
        if len(pool) < MIN_POOL:
            continue
        out.append((d.index[p].isoformat(), ret[e], ret[e] - ret[rng.choice(pool, cfg["test"]["baseline_draws"])].mean()))
    return out


def cluster_stats(values, cfg):
    v, t_cfg = np.asarray(values, float), cfg["test"]
    n = len(v)
    power = power_at(n, .30, t_cfg["alpha"])
    if n < 3 or v.std(ddof=1) == 0:
        return {"clusters": n, "mean": float(v.mean()) if n else None, "p": None, "power_d30": power,
                "outcome": "non supportata" if power >= .5 else "non informativa"}
    t, p = stats.ttest_1samp(v, 0, alternative="greater")
    means = v[np.random.default_rng(t_cfg["baseline_seed"]).integers(0, n, (t_cfg["bootstrap_reps"], n))].mean(axis=1)
    return {"clusters": n, "mean": float(v.mean()), "sd": float(v.std(ddof=1)), "d": float(v.mean() / v.std(ddof=1)), "t": float(t), "p": float(p),
            "boot_p": float((means <= 0).mean()), "ci90": [float(np.quantile(means, .05)), float(np.quantile(means, .95))], "power_d30": power,
            "outcome": "supportata" if p < t_cfg["alpha"] else ("non supportata" if power >= .5 else "non informativa"), "passes_t3": bool(t >= t_cfg["also_report_t"])}


def run_test(cfg, prices=None, period=None):
    first = pd.Timestamp(period["from"] if period else cfg["first_trigger"], tz="UTC")
    last = pd.Timestamp(period["to"], tz="UTC") if period else None
    rng, rows = np.random.default_rng(cfg["test"]["baseline_seed"]), []
    for cls, markets in cfg["markets"].items():
        for m in markets:
            d = prices[m] if prices is not None else load_prices(m)
            rows += [{"class": cls, "market": m, "trigger": t, "net": net, "excess": x} for t, net, x in market_excess(d, cfg, first, rng, last)]
    df = pd.DataFrame(rows, columns=["class", "market", "trigger", "net", "excess"])

    def group(sub):
        if sub.empty:
            return cluster_stats([], cfg)
        g = sub.assign(cluster=assign_clusters(sub.trigger, cfg["merge_days"])).groupby("cluster")
        res = cluster_stats(g.excess.mean().values, cfg)
        days = cfg["horizon_bars"] * 7 / 5
        return {**res, "events": len(sub), "mean_net": float(g.net.mean().mean()), "mean_net_with_funding": float(g.net.mean().mean() - cfg["costs"]["funding_per_day_sensitivity"] * days),
                "share_up": float((sub.net > 0).mean())}

    primary = df[df["class"].isin(cfg["primary_classes"])]
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": period, "primary": group(primary),
            "per_class": {c: group(df[df["class"] == c]) for c in cfg["markets"]}}


def report(r, cfg):
    p = r["primary"]
    pct = lambda x: "–" if x is None else f"{100 * x:+.2f}%"
    title = f"# Pre-registrazione v2, test storico {r['period']['from'][:4]}–{r['period']['to'][:4]}" if r.get("period") else "# Risultati della pre-registrazione v2"
    lines = [title, "", f"Eseguito il {r['run'][:10]}, una sola volta. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             f"**Ipotesi T1, cambi e materie prime insieme: {p['outcome']}.** Eccesso medio sui cluster {pct(p.get('mean'))}, {p['clusters']} cluster, "
             + (f"t = {p['t']:.2f}, p = {p['p']:.4f}, soglia severa t ≥ {cfg['test']['also_report_t']:g} {'superata' if p['passes_t3'] else 'non superata'}." if p.get("t") is not None else "troppo pochi cluster per un test."), "",
             "| Classe | Ruolo | Eventi | Cluster | Eccesso medio | Netto | Netto con funding | In salita |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for c, x in r["per_class"].items():
        role = "primaria" if c in cfg["primary_classes"] else "controllo"
        lines.append(f"| {c} | {role} | {x.get('events', 0)} | {x['clusters']} | {pct(x.get('mean'))} | {pct(x.get('mean_net'))} | {pct(x.get('mean_net_with_funding'))} | "
                     + (f"{100 * x['share_up']:.0f}%" if x.get("share_up") is not None else "–") + " |")
    lines += ["", "Le righe per classe e il controllo sulle azioni sono descrittivi, come stabilito nella pre-registrazione."]
    return "\n".join(lines) + "\n"


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in DOC.read_text():
        print("la configurazione v2 non coincide con la pre-registrazione: niente test")
        return 1
    if cmd == "stato":
        ev = events(cfg)
        ok, why = due(ev, cfg)
        print(f"Eventi dal {cfg['first_trigger']}: {len(ev)} ({int(ev.primary.sum()) if len(ev) else 0} su cambi e materie prime, {int(ev.complete.sum()) if len(ev) else 0} con l'orizzonte completo).")
        print(f"Test: {'da fare' if ok else 'non ancora'} ({why}).")
        return 0
    if cmd == "storico":
        if RESULTS_HIST.exists():
            print("il test storico è già stato fatto: non si rifà")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test storico si fa una volta sola")
            return 1
        r = run_test(cfg, period=HISTORICAL)
        RESULTS_HIST.write_text(json.dumps(r, indent=1))
        REPORT_HIST.write_text(report(r, cfg))
        print(r["primary"]["outcome"])
        return 0
    if cmd == "test":
        if RESULTS.exists():
            print("il test v2 è già stato fatto: non si rifà")
            return 1
        ok, why = due(events(cfg), cfg)
        if not ok:
            print(f"il test non è ancora dovuto: {why}")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test si fa una volta sola")
            return 1
        r = run_test(cfg)
        RESULTS.write_text(json.dumps(r, indent=1))
        REPORT.write_text(report(r, cfg))
        print(r["primary"]["outcome"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
