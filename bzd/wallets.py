"""Hyperliquid wallets: what the most and least profitable accounts hold, recorded hourly. Standard library only, like the recorder.

    python -m bzd.wallets run        loop: leaderboard once a day, positions of the chosen wallets every hour
    python -m bzd.wallets once       one leaderboard and one round of positions, then exit
    python -m bzd.wallets flussi     net positions of winners and losers per market, from the latest round

Nobody keeps a free history of the leaderboard or of positions, so every day not recorded is lost.
It describes who holds what. It isn't tested as a signal: profit so far doesn't prove skill, and a big winner
can be lucky, a hedger, or one leg of a trade made elsewhere.
"""
import fcntl, gzip, json, os, signal, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .recorder import BASE, UA

LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
INFO = "https://api.hyperliquid.xyz/info"
DEXES = ("", "xyz")  # main perps, then the builder market for indices, commodities, FX and stocks
GAP = 0.5  # seconds between position requests; Hyperliquid allows far more
POSITIONS_EVERY = 3600
KEEP_ACCOUNT_MIN = 10_000  # leaderboard rows saved each day
# Wallets followed, checked on the leaderboard of 6 Nov 2026: of accounts above $100K, half trade less than once their
# capital a month (vaults, holders) and the top 1% turn it over 350 times or more (market makers).
MIN_CAPITAL = 100_000
TURNOVER = (0.5, 100)  # monthly volume / capital
# All-time lists come first. The month's lists are partly circular: after a fall, the month's winners are mostly those who were short.
COHORTS = {"vincenti storici": ("allTime", 150, True), "perdenti storici": ("allTime", 150, False),
           "vincenti del mese": ("month", 50, True), "perdenti del mese": ("month", 50, False)}


def root():
    p = Path(os.environ.get("BZD_DATA", BASE / "data")) / "hl_wallets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def http(url, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def write_gz(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump(obj, f, separators=(",", ":"))
    tmp.replace(path)


def read_gz(path):
    with gzip.open(path, "rt") as f:
        return json.load(f)


# ---- leaderboard and cohorts

def slim(raw):
    """One row per account above the minimum: address, capital, pnl per window, volume for the month and all time, name."""
    out = []
    for r in raw.get("leaderboardRows", []):
        w = {k: v for k, v in r["windowPerformances"]}
        av = float(r["accountValue"])
        if av < KEEP_ACCOUNT_MIN:
            continue
        out.append([r["ethAddress"], round(av), *(round(float(w[k]["pnl"])) for k in ("day", "week", "month", "allTime")),
                    round(float(w["month"]["vlm"])), round(float(w["allTime"]["vlm"])), r.get("displayName")])
    return out


FIELDS = ("address", "capital", "pnl_day", "pnl_week", "pnl_month", "pnl_all", "vlm_month", "vlm_all", "name")
PNL = {"day": 2, "week": 3, "month": 4, "allTime": 5}


def choose(rows):
    """Winners and losers among active, non-market-making accounts. An address keeps the first list it lands in."""
    lo, hi = TURNOVER
    active = [r for r in rows if r[1] >= MIN_CAPITAL and lo <= r[6] / r[1] <= hi]
    out = {}
    for cohort, (window, n, winners) in COHORTS.items():
        ranked = sorted(active, key=lambda r: r[PNL[window]], reverse=winners)
        for r in ranked[:n]:
            if (r[PNL[window]] > 0) == winners:
                out.setdefault(r[0], cohort)
    return out


def take_leaderboard(now=None):
    now = now or datetime.now(timezone.utc)
    rows = slim(http(LEADERBOARD, timeout=180))
    write_gz(root() / "leaderboard" / f"{now:%Y-%m-%d}.json.gz", {"fields": FIELDS, "rows": rows, "at": now.isoformat(timespec="seconds")})
    cohorts = choose(rows)
    (root() / "cohorts.json").write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "wallets": cohorts}))
    return rows, cohorts


# ---- positions

def positions_of(address, sleep=time.sleep):
    """Open positions on each dex: [dex, coin, size, entry, value, leverage, unrealized pnl, liquidation]. Size is negative for shorts."""
    out, capital = [], 0.0
    for dex in DEXES:
        d = http(INFO, {"type": "clearinghouseState", "user": address, "dex": dex}, timeout=30)
        capital += float(d.get("marginSummary", {}).get("accountValue") or 0)
        for p in d.get("assetPositions", []):
            x = p["position"]
            out.append([dex, x["coin"], float(x["szi"]), float(x.get("entryPx") or 0), float(x.get("positionValue") or 0),
                        (x.get("leverage") or {}).get("value"), float(x.get("unrealizedPnl") or 0), float(x["liquidationPx"]) if x.get("liquidationPx") else None])
        sleep(GAP)
    return capital, out


def take_positions(cohorts, now=None, sleep=time.sleep, log=print):
    now = now or datetime.now(timezone.utc)
    snap, failed = {}, 0
    for address, cohort in cohorts.items():
        try:
            capital, pos = positions_of(address, sleep)
            snap[address] = {"cohort": cohort, "capital": round(capital), "positions": pos}
        except Exception:
            failed += 1
    write_gz(root() / "positions" / f"{now:%Y-%m-%d}" / f"{now:%H%M}Z.json.gz", {"at": now.isoformat(timespec="seconds"), "wallets": snap, "failed": failed})
    log(f"{now:%Y-%m-%d %H:%M} posizioni: {len(snap)} wallet, {failed} errori")
    return snap


# ---- reading

def latest_positions():
    files = sorted((root() / "positions").glob("*/*.json.gz"))
    return read_gz(files[-1]) if files else None


def flows(snap):
    """Per market: how many winners and losers are long or short, and their net dollars. Short is negative."""
    out = {}
    for w in (snap or {}).get("wallets", {}).values():
        for dex, coin, size, _entry, value, *_ in w["positions"]:
            m = out.setdefault(coin, {c: {"long": 0, "short": 0, "net": 0.0} for c in COHORTS})
            if w["cohort"] not in m:
                continue
            side = m[w["cohort"]]
            side["long" if size > 0 else "short"] += 1
            side["net"] += value if size > 0 else -value
    return out


def positions_near(when, tolerance_hours=3):
    """The round closest to `when`, within the tolerance, or None."""
    best, gap = None, tolerance_hours * 3600
    for f in (root() / "positions").glob("*/*.json.gz"):
        t = datetime.strptime(f"{f.parent.name} {f.name[:5]}", "%Y-%m-%d %H%MZ").replace(tzinfo=timezone.utc)
        if abs((t - when).total_seconds()) <= gap:
            best, gap = f, abs((t - when).total_seconds())
    return read_gz(best) if best else None


def view(top=40):
    """What the app shows: net positions per market and group now, and the change in 24 hours."""
    from datetime import timedelta
    snap = latest_positions()
    if not snap:
        return None
    now = flows(snap)
    before_snap = positions_near(datetime.fromisoformat(snap["at"]) - timedelta(hours=24))
    before = flows(before_snap) if before_snap else {}
    counts = {c: sum(w["cohort"] == c for w in snap["wallets"].values()) for c in COHORTS}
    rows = []
    for coin in sorted(now, key=lambda c: -sum(abs(now[c][k]["net"]) for k in COHORTS))[:top]:
        rows.append({"market": coin, "groups": {k: {**now[coin][k], "change_24h": (now[coin][k]["net"] - before[coin][k]["net"]) if coin in before else None} for k in COHORTS}})
    return {"at": snap["at"], "groups": list(COHORTS), "wallets": counts, "has_24h": bool(before_snap), "rows": rows}


def flows_text(snap, top=15):
    f = flows(snap)
    if not f:
        return "nessuna posizione registrata"
    lines = [f"Posizioni del {snap['at'][:16].replace('T', ' ')} UTC. Netto in dollari, + long e - short. Descrive, non è testato come segnale.",
             f"{'mercato':14}" + "".join(f"{c:>22}" for c in COHORTS)]
    busiest = sorted(f, key=lambda c: -sum(abs(f[c][k]["net"]) for k in COHORTS))[:top]
    cell = lambda s: f"{s['net'] / 1e6:+.1f}M ({s['long']}L/{s['short']}S)"
    for c in busiest:
        lines.append(f"{c:14}" + "".join(f"{cell(f[c][k]):>22}" for k in COHORTS))
    return "\n".join(lines)


# ---- loop

def cycle(st, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    today = f"{now:%Y-%m-%d}"
    if st.get("leaderboard") != today:
        try:
            rows, cohorts = take_leaderboard(now)
            st["leaderboard"], st["cohorts"] = today, cohorts
            log(f"{today} classifica: {len(rows)} conti, seguiti " + ", ".join(f"{sum(v == c for v in cohorts.values())} {c}" for c in COHORTS))
        except Exception as e:
            log(f"classifica non scaricata, riprovo: {type(e).__name__}: {e}")
    if not st.get("cohorts"):
        p = root() / "cohorts.json"
        st["cohorts"] = json.loads(p.read_text())["wallets"] if p.exists() else {}
    if st["cohorts"] and now.timestamp() - st.get("positions", 0) >= POSITIONS_EVERY:
        st["positions"] = now.timestamp() // POSITIONS_EVERY * POSITIONS_EVERY
        take_positions(st["cohorts"], now, log=log)


def cmd_run():
    lock = open(root() / "wallets.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("wallets already running", flush=True)
        return 1
    flag, st = {"stop": False}, {}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: flag.update(stop=True))
    log = lambda m: print(m, flush=True)
    log("wallets running")
    while not flag["stop"]:
        try:
            cycle(st, log=log)
        except Exception as e:
            log(f"cycle failed: {type(e).__name__}: {e}")
        for _ in range(60):
            if flag["stop"]:
                break
            time.sleep(1)
    return 0


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "run":
        return cmd_run()
    if cmd == "once":
        cycle({})
        return 0
    if cmd == "flussi":
        print(flows_text(latest_positions()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
