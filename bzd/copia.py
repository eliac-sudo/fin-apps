"""Copy trading on paper (v9, docs/PREREGISTRAZIONE_v9.md): two paper portfolios that mirror Hyperliquid accounts every 5 minutes.

    python -m bzd.copia run     loop, the bzd-copia service
    python -m bzd.copia once    one step, then exit
    python -m bzd.copia stato   where the two portfolios stand

C copies the 20 accounts with the most profit this month, R copies 20 accounts drawn at random from the same pool, both
reselected every Monday. Each portfolio holds the average of its accounts' positions as a share of their capital, each
account's leverage capped at 3, and trades only when a position is off by more than 1% of equity, at the mid price plus
fees and slippage, paying funding every hour. Read-only public API: no keys and no orders. Nothing here can trade.
"""
import fcntl, json, random, signal, sys, time
from datetime import datetime, timedelta, timezone

from . import wallets as W
from .recorder import BASE

CONFIG = BASE / "config" / "setups_v9.json"
N_LEADERS = 20
GAP = 0.25
PORTFOLIOS = ("C", "R")


def load_config():
    return json.loads(CONFIG.read_text())


def root():
    d = W.root().parent / "v9"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- who is copied

def pool(rows, cfg):
    """The accounts either portfolio may copy, as on the day of the board: real capital, and trading neither too little nor like a market maker."""
    lo, hi = cfg["turnover_month"]
    return [r for r in rows if r["capital"] >= cfg["min_capital"] and lo <= r["vlm_month"] / r["capital"] <= hi]


def best(p, n=N_LEADERS):
    return [r["address"] for r in sorted((r for r in p if r["pnl_month"] > 0 and r["pnl_all"] > 0), key=lambda r: -r["pnl_month"])[:n]]


def monday(now):
    return (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")


def drawn(p, week, seed, n=N_LEADERS):
    """The random accounts of a week: the same draw every time for the same week and pool."""
    rng = random.Random(seed + int(week.replace("-", "")))
    addresses = sorted(r["address"] for r in p)
    return rng.sample(addresses, min(n, len(addresses)))


def select(cfg, now):
    rows = list(W.leaderboard_rows().values())
    p = pool(rows, cfg["historical"]["pool"])
    week = monday(now)
    return {"week": week, "C": best(p), "R": drawn(p, week, cfg["test"]["seed"])}


# ---- what they hold

def account(address, dexes, sleep=time.sleep):
    """Capital over all dexes and each position's signed dollar value, keyed by coin."""
    cap, held = 0.0, {}
    for dex in dexes:
        d = W.state_of(address, dex)
        cap += float(d.get("marginSummary", {}).get("accountValue") or 0)
        for x in (p["position"] for p in d.get("assetPositions", [])):
            v = float(x.get("positionValue") or 0)
            held[x["coin"]] = held.get(x["coin"], 0.0) + (v if float(x["szi"]) > 0 else -v)
        sleep(GAP)
    return cap, held


def weights(accounts, max_leverage):
    """The average of the accounts' positions as a share of their capital, each account's gross leverage capped first.
    An emptied account counts as cash."""
    out = {}
    for cap, held in accounts:
        if cap <= 0:
            continue
        gross = sum(abs(v) for v in held.values()) / cap
        k = min(1.0, max_leverage / gross) if gross > 0 else 0.0
        for c, v in held.items():
            out[c] = out.get(c, 0.0) + v / cap * k
    n = len(accounts)
    return {c: w / n for c, w in out.items()} if n else {}


# ---- the paper portfolio

def new_book(capital):
    return {"cash": float(capital), "units": {}, "fees": 0.0, "funding": 0.0, "trades": 0}


def equity(book, mids):
    return book["cash"] + sum(q * mids[c] for c, q in book["units"].items() if c in mids)


def rebalance(book, target, mids, cfg):
    """Trade each market whose position is off target by more than the deadband, or that the accounts have left. A market
    with no price is held as it is."""
    c_ = cfg["copy"]
    e = equity(book, mids)
    cost = c_["fee_per_side"] + c_["slippage_per_side"]
    for c in sorted(set(target) | set(book["units"])):
        if c not in mids or mids[c] <= 0:
            continue
        q = book["units"].get(c, 0.0)
        want, have = target.get(c, 0.0) * e, q * mids[c]
        gap = want - have
        if abs(gap) <= c_["deadband_of_equity"] * e and (want != 0 or q == 0):
            continue
        book["units"][c] = q + gap / mids[c]
        book["cash"] -= gap + abs(gap) * cost
        book["fees"] += abs(gap) * cost
        book["trades"] += 1
        if abs(book["units"][c] * mids[c]) < 1e-6:
            del book["units"][c]


def pay_funding(book, rates, mids, hours):
    """Hyperliquid funding is hourly: a long pays position value times the rate when the rate is positive, a short receives it."""
    paid = sum(q * mids[c] * rates[c] * hours for c, q in book["units"].items() if c in rates and c in mids)
    book["cash"] -= paid
    book["funding"] += paid


# ---- prices and funding

def mids(dexes):
    out = {}
    for dex in dexes:
        for c, px in W.http(W.INFO, {"type": "allMids", "dex": dex}, timeout=30).items():
            if not c.startswith(("@", "#")):
                out[c] = float(px)
    return out


def funding_rates(dexes):
    out = {}
    for dex in dexes:
        meta, ctxs = W.http(W.INFO, {"type": "metaAndAssetCtxs", "dex": dex}, timeout=30)
        for u, x in zip(meta["universe"], ctxs):
            if x.get("funding") is not None:
                out[u["name"]] = float(x["funding"])
    return out


# ---- state

def state_path():
    return root() / "carta.json"


def load_state(cfg):
    p = state_path()
    if p.exists():
        return json.loads(p.read_text())
    return {"books": {k: new_book(cfg["forward"]["capital"]) for k in PORTFOLIOS}, "leaders": None, "mids": {}, "funding_at": None, "day": None}


def save_state(st):
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(st, separators=(",", ":")))
    tmp.replace(state_path())


DAY_FIELDS = ("date", "C", "R", "BTC", "C_fees", "R_fees", "C_funding", "R_funding", "C_trades", "R_trades", "C_read", "R_read")


def write_day(st, now, read):
    """One line a day with the equity at the first step after midnight UTC: the daily returns of the test come from these."""
    p = root() / "giorni.csv"
    if not p.exists():
        p.write_text(",".join(DAY_FIELDS) + "\n")
    b, m = st["books"], st["mids"]
    row = [f"{now:%Y-%m-%d}", *(f"{equity(b[k], m):.4f}" for k in PORTFOLIOS), f"{m.get('BTC', 0):.2f}",
           *(f"{b[k]['fees']:.4f}" for k in PORTFOLIOS), *(f"{b[k]['funding']:.4f}" for k in PORTFOLIOS), *(str(b[k]["trades"]) for k in PORTFOLIOS),
           *(str(read.get(k, 0)) for k in PORTFOLIOS)]
    with p.open("a") as f:
        f.write(",".join(row) + "\n")


def step(st, cfg, now=None, log=print, sleep=time.sleep):
    now = now or datetime.now(timezone.utc)
    F = cfg["forward"]
    if now < datetime.fromisoformat(F["start"]).replace(tzinfo=timezone.utc):
        return False
    dexes = F["copy"]["dexes"]
    if not st["leaders"] or st["leaders"]["week"] != monday(now):
        st["leaders"] = select(cfg, now)
        log(f"{now:%Y-%m-%d %H:%M} copiati scelti per la settimana del {st['leaders']['week']}: C {len(st['leaders']['C'])}, R {len(st['leaders']['R'])}")
    m = mids(dexes)
    st["mids"].update(m)
    m = st["mids"]
    # funding for the hours since the last payment, on the positions held through them
    last = datetime.fromisoformat(st["funding_at"]) if st["funding_at"] else now
    hours = int((now - last).total_seconds() // 3600)
    if hours >= 1:
        rates = funding_rates(dexes)
        for k in PORTFOLIOS:
            pay_funding(st["books"][k], rates, m, hours)
        last += timedelta(hours=hours)
    st["funding_at"] = last.isoformat(timespec="seconds")
    if st["day"] != f"{now:%Y-%m-%d}":
        write_day(st, now, st.get("read", {}))
        st["day"] = f"{now:%Y-%m-%d}"
    cache, read = {}, {}
    for k in PORTFOLIOS:
        accounts = []
        for a in st["leaders"][k]:
            if a not in cache:
                try:
                    cache[a] = account(a, dexes, sleep)
                except Exception:
                    cache[a] = None
            if cache[a] is not None:
                accounts.append(cache[a])
        read[k] = len(accounts)
        # with more than a quarter of the accounts unread the average would be another portfolio: hold, and try again next step
        if len(accounts) >= 0.75 * len(st["leaders"][k]):
            rebalance(st["books"][k], weights(accounts, F["copy"]["max_leverage"]), m, cfg["forward"])
    st["read"] = read
    save_state(st)
    return True


def cmd_run():
    lock = open(root() / "copia.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("copia already running", flush=True)
        return 1
    flag = {"stop": False}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: flag.update(stop=True))
    log = lambda m: print(m, flush=True)
    cfg = load_config()
    st = load_state(cfg)
    log("copia sulla carta avviata")
    every = cfg["forward"]["every_seconds"]
    while not flag["stop"]:
        t0 = time.time()
        try:
            step(st, cfg, log=log)
        except Exception as e:
            log(f"passo fallito: {type(e).__name__}: {e}")
        while not flag["stop"] and time.time() - t0 < every:
            time.sleep(1)
    return 0


def summary(st):
    b, m = st["books"], st["mids"]
    cap = load_config()["forward"]["capital"]
    lines = []
    for k in PORTFOLIOS:
        e = equity(b[k], m)
        gross = sum(abs(q * m.get(c, 0)) for c, q in b[k]["units"].items()) / e if e else 0
        lines.append(f"{k}: {e:,.2f} ({100 * (e / cap - 1):+.2f}%), leva {gross:.2f}, {b[k]['trades']} scambi, commissioni {b[k]['fees']:.2f}, funding pagato {b[k]['funding']:+.2f}")
    return "\n".join(lines)


def view():
    """Where the two paper portfolios stand, for the app: return since the start, leverage, costs, what C holds most."""
    p = state_path()
    if not p.exists():
        return None
    st, cfg = json.loads(p.read_text()), load_config()
    cap, m = cfg["forward"]["capital"], st["mids"]
    out = {"start": cfg["forward"]["start"], "judge_on": cfg["forward"]["judge_on"], "week": (st.get("leaders") or {}).get("week")}
    for k in PORTFOLIOS:
        b = st["books"][k]
        e = equity(b, m)
        held = sorted(((c, q * m.get(c, 0)) for c, q in b["units"].items()), key=lambda x: -abs(x[1]))
        out[k] = {"return": e / cap - 1, "leverage": sum(abs(v) for _, v in held) / e if e else 0, "trades": b["trades"],
                  "fees": b["fees"] / cap, "funding": b["funding"] / cap, "top": [[c, v / e] for c, v in held[:4]]}
    days = root() / "giorni.csv"
    if days.exists():
        lines = days.read_text().splitlines()
        first = dict(zip(lines[0].split(","), lines[1].split(","))) if len(lines) > 1 else {}
        out["days"] = len(lines) - 2 if len(lines) > 2 else 0
        out["btc"] = m.get("BTC", 0) / float(first["BTC"]) - 1 if first.get("BTC") and float(first["BTC"]) else None
    return out


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "run":
        return cmd_run()
    if cmd == "once":
        cfg = load_config()
        st = load_state(cfg)
        print("fatto" if step(st, cfg) else f"la prova parte il {cfg['forward']['start']}")
        return 0
    if cmd == "stato":
        p = state_path()
        print(summary(json.loads(p.read_text())) if p.exists() else "nessun passo ancora")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
