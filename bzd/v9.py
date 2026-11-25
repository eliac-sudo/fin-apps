"""Pre-registration v9 (docs/PREREGISTRAZIONE_v9.md): copying Hyperliquid traders.

    python -m bzd.v9 conta               free: the pool of 6 November and how many accounts the final board still has. No returns
    python -m bzd.v9 storico --confirm   did 6 November's winners keep winning until 25 November? Once
    python -m bzd.v9 futuro              the paper copy (bzd/copia.py): days counted until the judging date, then judged once and frozen

The historical part needs no prices: Hyperliquid's own all-time pnl, which leaves out deposits and withdrawals, read on the
two leaderboards; an account missing from the second is left out once and put last once. The forward part is the paper copy run by the bzd-copia service.
"""
import hashlib, json, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

from . import copia as CP
from . import wallets as W
from .recorder import BASE

CONFIG = CP.CONFIG
DOC = BASE / "docs" / "PREREGISTRAZIONE_v9.md"
RESULTS = BASE / "config" / "validation_v9_storico.json"
REPORT = BASE / "docs" / "V9_STORICO.md"


def load_config():
    return json.loads(CONFIG.read_text())


def config_hash():
    return hashlib.sha256(CONFIG.read_bytes()).hexdigest()


def board(day):
    d = W.read_gz(W.root() / "leaderboard" / f"{day}.json.gz")
    return {r[0]: dict(zip(W.FIELDS, r)) for r in d["rows"]}


def start_pool(cfg):
    H = cfg["historical"]
    return CP.pool(list(board(H["from_board"]).values()), H["pool"])


def returns(cfg):
    """Each pool account's return from the first board to the second. An account missing from the second board has no
    reliable pnl (the portfolio API doesn't match the leaderboard), so its return is NaN."""
    H = cfg["historical"]
    end = board(H["to_board"])
    out = []
    for r in start_pool(cfg):
        later = end.get(r["address"], {}).get("pnl_all")
        out.append({**r, "after": np.nan if later is None else (later - r["pnl_all"]) / r["capital"], "roi_month": r["pnl_month"] / r["capital"]})
    return pd.DataFrame(out)


def top(df, col, n):
    return set(df[df[col] > 0].sort_values(col, ascending=False).address[:n])


def group_test(df, members):
    a, b = df[df.address.isin(members)].after, df[~df.address.isin(members)].after
    p = float(stats.mannwhitneyu(a, b, alternative="greater").pvalue) if len(a) and len(b) else None
    return {"n": int(len(a)), "n_rest": int(len(b)), "p": p, "median": float(a.median()), "median_rest": float(b.median()),
            "share_up": float((a > 0).mean()), "share_up_rest": float((b > 0).mean())}


def holm(res, alpha):
    order = sorted((r["p"], k) for k, r in res.items() if r.get("p") is not None)
    m, stop = len(res), False
    for rank, (p, k) in enumerate(order):
        res[k]["holm_threshold"] = alpha / (m - rank)
        ok = not stop and p < alpha / (m - rank)
        stop = stop or not ok
        res[k]["outcome"] = "supportata" if ok else "non supportata"
    for r in res.values():
        r.setdefault("outcome", "non informativa")
    return res


def family(df, alpha):
    rho, p1 = stats.spearmanr(df.roi_month, df.after)
    res = {"P1": {"n": int(len(df)), "rho": float(rho), "p": float(p1 / 2 if rho > 0 else 1 - p1 / 2)},
           "P2": group_test(df, top(df, "pnl_month", 50)),
           "P3": group_test(df, top(df, "pnl_all", 150))}
    return holm(res, alpha)


def historical(cfg):
    """The test twice: missing accounts left out, and missing accounts given the worst return. Supported only if both say so."""
    df = returns(cfg)
    miss = df.after.isna()
    groups = {"P2": top(df, "pnl_month", 50), "P3": top(df, "pnl_all", 150)}
    alpha = cfg["test"]["family_alpha"]
    out = family(df[~miss], alpha)
    worst = family(df.assign(after=df.after.fillna(df.after.min() - 1)), alpha)
    for k, r in out.items():
        r["excluded"] = {kk: r[kk] for kk in ("p", "holm_threshold", "outcome")}
        r["worst"] = {kk: worst[k][kk] for kk in ("p", "holm_threshold", "outcome")}
        r["outcome"] = "supportata" if r["outcome"] == worst[k]["outcome"] == "supportata" else "non supportata"
        if k in groups:
            r["missing"] = int((miss & df.address.isin(groups[k])).sum())
            r["missing_rest"] = int((miss & ~df.address.isin(groups[k])).sum())
    return {"config_sha256": config_hash(), "run": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pool": int(len(df)),
            "missing": int(miss.sum()), "median_after": float(df.after.median()), "results": out}


def report(r, cfg):
    H = cfg["historical"]
    pct = lambda x: f"{100 * x:+.1f}%"
    res = r["results"]
    lines = [f"# Pre-registrazione v9, chi vinceva il {H['from_board'][8:]} novembre ha continuato a vincere?", "",
             f"Eseguito il {r['run'][:10]}, una sola volta. Configurazione `{r['config_sha256'][:12]}…`. Non è consulenza finanziaria.", "",
             f"Gruppo di partenza: i {r['pool']} conti della classifica Hyperliquid del {H['from_board']} con almeno $100.000 e un giro d'affari da trader "
             f"(né fermi né market maker). Rendimento dopo: profitto dal {H['from_board']} al {H['to_board']} diviso il capitale del {H['from_board']}. "
             f"{r['missing']} conti sono usciti dalla classifica e non hanno un profitto affidabile: il test si fa escludendoli e mettendoli all'ultimo posto, e regge solo se regge in entrambi i modi. "
             f"Rendimento mediano dei conti rimasti: {pct(r['median_after'])}. Holm al 5% sulle tre.", "",
             "| ID | Domanda | Esito | p (esclusi / ultimi) | Cosa si vede |", "|---|---|---|---:|---|"]
    p1 = res["P1"]
    pp = lambda x: f"{x['excluded']['p']:.4f} / {x['worst']['p']:.4f}"
    lines.append(f"| P1 | {H['hypotheses']['P1']['reading']} | **{p1['outcome']}** | {pp(p1)} | correlazione di rango {p1['rho']:+.3f} su {p1['n']} conti |")
    for k in ("P2", "P3"):
        x = res[k]
        lines.append(f"| {k} | {H['hypotheses'][k]['reading']} | **{x['outcome']}** | {pp(x)} | mediana {pct(x['median'])} contro {pct(x['median_rest'])}; "
                     f"in utile {100 * x['share_up']:.0f}% contro {100 * x['share_up_rest']:.0f}% ({x['n']} contro {x['n_rest']} conti; usciti dalla classifica {x['missing']} contro {x['missing_rest']}) |")
    lines += ["", "Sono 19 giorni e un solo momento di mercato: se tutti i vincenti erano long e il mercato è salito, vincono insieme per lo stesso motivo. "
              "Dice se la classifica ha qualche memoria, non che copiarla renda. Quello lo dice la copia sulla carta (`python -m bzd.v9 futuro`)."]
    return "\n".join(lines) + "\n"


# ---- forward: the paper copy, judged once

def block_p(x, reps, block, seed):
    """One-sided p that the mean is above zero: circular block bootstrap of the series centred on zero."""
    x = np.asarray(x, float)
    n, rng = len(x), np.random.default_rng(seed)
    c = x - x.mean()
    starts = rng.integers(0, n, size=(reps, -(-n // block)))
    idx = (starts[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n] % n
    return float((1 + (c[idx].mean(axis=1) >= x.mean()).sum()) / (reps + 1))


def daily_returns():
    p = CP.root() / "giorni.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p).drop_duplicates("date", keep="first").set_index("date")
    return d[list(CP.PORTFOLIOS) + ["BTC"]].pct_change().dropna()


def forward_state(cfg, now=None):
    F, T = cfg["forward"], cfg["test"]
    now = now or datetime.now(timezone.utc)
    fp = CP.root() / "giudicate.json"
    done = json.loads(fp.read_text()) if fp.exists() else {}
    r = daily_returns()
    days = 0 if r is None else len(r)
    if not done and now >= datetime.fromisoformat(F["judge_on"]).replace(tzinfo=timezone.utc):
        series = {"H1": r.C - r.R, "H2": r.C} if days else {}
        res = {}
        for k in F["hypotheses"]:
            if days < F["min_days"]:
                res[k] = {"days": days, "p": None, "outcome": "non informativa"}
                continue
            x = series[k]
            res[k] = {"days": days, "mean": float(x.mean()), "p": block_p(x, T["bootstrap_reps"], T["block_days"], T["seed"]),
                      "t_p": float(stats.ttest_1samp(x, 0, alternative="greater").pvalue)}
        res = holm(res, T["family_alpha"])
        for x in res.values():
            x.update(judged_on=now.isoformat(timespec="seconds"), config_sha256=config_hash())
        done = res
        fp.write_text(json.dumps(done, indent=1, ensure_ascii=False))
    total = {} if r is None else {k: float((1 + r[k]).prod() - 1) for k in (*CP.PORTFOLIOS, "BTC")}
    state = {"at": now.isoformat(timespec="seconds"), "start": F["start"], "judge_on": F["judge_on"], "days": days, "total": total,
             "hypotheses": {k: {"reading": h["reading"], "judged": k in done, "result": done.get(k)} for k, h in F["hypotheses"].items()}}
    (CP.root() / "stato.json").write_text(json.dumps(state, indent=1, ensure_ascii=False))
    return state


def daily():
    """Called by the alerts service once a day. Never raises."""
    try:
        cfg = load_config()
        if config_hash() in DOC.read_text():
            forward_state(cfg)
    except Exception as e:  # noqa: BLE001 - a forward count must never stop the alerts
        print(f"v9 futuro non aggiornato: {type(e).__name__}: {e}", flush=True)


def main(argv):
    cmd = argv[0] if argv else ""
    cfg = load_config()
    if config_hash() not in (DOC.read_text() if DOC.exists() else ""):
        print("la configurazione v9 non coincide con la pre-registrazione: niente conteggi e niente test")
        return 1
    if cmd == "conta":
        H = cfg["historical"]
        p, end = start_pool(cfg), board(H["to_board"])
        print(f"gruppo di partenza {len(p)} conti; nella classifica finale {sum(r['address'] in end for r in p)}, usciti {sum(r['address'] not in end for r in p)}")
        return 0
    if cmd == "storico":
        if RESULTS.exists():
            print("il test storico v9 è già stato fatto: non si rifà")
            return 1
        if "--confirm" not in argv:
            print("aggiungi --confirm: il test si fa una volta sola")
            return 1
        r = historical(cfg)
        RESULTS.write_text(json.dumps(r, indent=1, ensure_ascii=False))
        REPORT.write_text(report(r, cfg))
        for k, x in r["results"].items():
            print(f"{k}: {x['outcome']} (p {x['excluded']['p']:.4f} / {x['worst']['p']:.4f})")
        return 0
    if cmd == "futuro":
        s = forward_state(cfg)
        print(f"{s['days']} giorni; " + ", ".join(f"{k} {100 * v:+.2f}%" for k, v in s["total"].items()))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
