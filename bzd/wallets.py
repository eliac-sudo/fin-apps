"""Hyperliquid's profitable accounts and vaults: what they hold, recorded hourly, and how they trade, rebuilt from their fills.
Standard library only, like the recorder. Read-only public API: no keys, no orders.

    python -m bzd.wallets run        loop: leaderboard, vaults and fills once a day, positions every hour
    python -m bzd.wallets once       one full round, then exit
    python -m bzd.wallets flussi     net positions per market, from the latest round
    python -m bzd.wallets profilo <indirizzo>   the strategy profile of one account

Followed: the most profitable active traders of all time and of the month, and the open vaults with a profit, some history
and real money in them. Nobody keeps a free history of positions, and Hyperliquid only serves an account's latest 10,000
fills, so every day not recorded is lost. It describes; it isn't tested as a signal. Profit so far doesn't prove skill:
a winner can be lucky, a hedger, or one leg of a trade made elsewhere.
"""
import fcntl, gzip, json, os, signal, statistics, sys, threading, time, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .recorder import BASE, UA

LEADERBOARD = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
VAULTS = "https://stats-data.hyperliquid.xyz/Mainnet/vaults"
INFO = "https://api.hyperliquid.xyz/info"
DEXES = ("", "xyz")  # main perps, then the builder market for indices, commodities, FX and stocks
GAP = 0.5  # seconds between position requests
FILLS_GAP = 1.5  # fills requests weigh more on Hyperliquid's limits
POSITIONS_EVERY = 3600
KEEP_ACCOUNT_MIN = 10_000  # leaderboard rows saved each day
# Traders followed, checked on the leaderboard of 6 Nov 2026: of accounts above $100K, half trade less than once their
# capital a month (vaults, holders) and the top 1% turn it over 350 times or more (market makers).
MIN_CAPITAL = 100_000
TURNOVER = (0.5, 100)  # monthly volume / capital
COHORTS = {"vincenti storici": ("allTime", 150), "vincenti del mese": ("month", 50)}
VAULT = "vault"
VAULT_MIN_TVL, VAULT_MIN_DAYS, VAULTS_MAX = 100_000, 90, 40
PROTOCOL_VAULTS = ("Hyperliquidity Provider", "HLP ")  # the exchange's own market making, not a strategy anyone runs
FILLS_FIRST_DAYS, FILLS_KEEP_DAYS, FILL_PAGES = 30, 180, 5
DETAIL_SECONDS = 600
_lock, _detail = threading.Lock(), {}


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


# ---- who is followed

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
    """The most profitable active traders, leaving out market makers and accounts that barely trade. An address keeps its first list."""
    lo, hi = TURNOVER
    active = [r for r in rows if r[1] >= MIN_CAPITAL and lo <= r[6] / r[1] <= hi]
    out = {}
    for cohort, (window, n) in COHORTS.items():
        for r in sorted(active, key=lambda r: r[PNL[window]], reverse=True)[:n]:
            if r[PNL[window]] > 0:
                out.setdefault(r[0], cohort)
    return out


def vault_pnl(v):
    series = dict(v.get("pnls", [])).get("allTime") or []
    return float(series[-1]) if series else 0.0


def choose_vaults(raw, now):
    """Open vaults with real money, some history and a profit, best first. The exchange's own market-making vaults are left out."""
    out = {}
    for v in raw:
        s = v["summary"]
        age = (now.timestamp() * 1000 - (s.get("createTimeMillis") or 0)) / 86_400_000
        if s.get("isClosed") or float(s["tvl"]) < VAULT_MIN_TVL or age < VAULT_MIN_DAYS or vault_pnl(v) <= 0 or s["name"].startswith(PROTOCOL_VAULTS):
            continue
        out[s["vaultAddress"]] = {"name": s["name"], "tvl": round(float(s["tvl"])), "apr": v.get("apr"), "pnl_all": round(vault_pnl(v)), "leader": s.get("leader"), "days": round(age)}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["pnl_all"])[:VAULTS_MAX])


def take_leaderboard(now=None):
    now = now or datetime.now(timezone.utc)
    rows = slim(http(LEADERBOARD, timeout=180))
    write_gz(root() / "leaderboard" / f"{now:%Y-%m-%d}.json.gz", {"fields": FIELDS, "rows": rows, "at": now.isoformat(timespec="seconds")})
    cohorts = choose(rows)
    try:
        vaults = choose_vaults(http(VAULTS, timeout=180), now)
    except Exception:
        vaults = (followed() or {}).get("vaults", {})
    cohorts.update({a: VAULT for a in vaults})
    names = {r[0]: r[8] for r in rows if r[0] in cohorts and r[8]}
    (root() / "cohorts.json").write_text(json.dumps({"at": now.isoformat(timespec="seconds"), "wallets": cohorts, "names": names, "vaults": vaults}))
    return rows, cohorts


def followed():
    p = root() / "cohorts.json"
    return json.loads(p.read_text()) if p.exists() else None


def leaderboard_rows():
    files = sorted((root() / "leaderboard").glob("*.json.gz"))
    return {r[0]: dict(zip(FIELDS, r)) for r in read_gz(files[-1])["rows"]} if files else {}


# ---- positions

def state_of(address, dex):
    return http(INFO, {"type": "clearinghouseState", "user": address, "dex": dex}, timeout=30)


def positions_of(address, sleep=time.sleep):
    """Open positions on each dex: [dex, coin, size, entry, value, leverage, unrealized pnl, liquidation]. Size is negative for shorts."""
    out, capital = [], 0.0
    for dex in DEXES:
        d = state_of(address, dex)
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
    log(f"{now:%Y-%m-%d %H:%M} posizioni: {len(snap)} conti, {failed} errori")
    return snap


def latest_positions():
    files = sorted((root() / "positions").glob("*/*.json.gz"))
    return read_gz(files[-1]) if files else None


def position_files(days, now=None):
    now = now or datetime.now(timezone.utc)
    first = f"{now - timedelta(days=days):%Y-%m-%d}"
    return sorted(f for f in (root() / "positions").glob("*/*.json.gz") if f.parent.name >= first)


# ---- fills: the trade history, kept from the day an account is followed

def compact(f):
    return [f["time"], f["coin"], float(f["px"]), float(f["sz"]), f["side"], float(f["startPosition"]), f["dir"], float(f["closedPnl"]), float(f["fee"]),
            not f.get("crossed", True), f.get("twapId") is not None, f["tid"]]


def fills_path(address):
    return root() / "fills" / f"{address}.json.gz"


def stored_fills(address):
    p = fills_path(address)
    return read_gz(p) if p.exists() else []


def merge_fills(*lists, keep_from=None):
    seen, out = set(), []
    for f in sorted((f for l in lists for f in l), key=lambda f: (f[0], f[11])):
        if f[11] in seen or (keep_from and f[0] < keep_from):
            continue
        seen.add(f[11])
        out.append(f)
    return out


def fetch_fills(address, start_ms, sleep=time.sleep):
    """Fills from start_ms on, oldest first, a page of up to 2000 at a time. Hyperliquid serves only the latest 10,000."""
    out = []
    for _ in range(FILL_PAGES):
        page = http(INFO, {"type": "userFillsByTime", "user": address, "startTime": int(start_ms), "aggregateByTime": True}, timeout=60)
        sleep(FILLS_GAP)
        if not page:
            break
        out += [compact(f) for f in page]
        if len(page) < 2000:
            break
        start_ms = max(f["time"] for f in page) + 1
    return out


def update_fills(cohorts, now=None, sleep=time.sleep, log=print):
    now = now or datetime.now(timezone.utc)
    now_ms, done, failed = now.timestamp() * 1000, 0, 0
    for address in cohorts:
        old = stored_fills(address)
        start = old[-1][0] + 1 if old else now_ms - FILLS_FIRST_DAYS * 86_400_000
        try:
            new = fetch_fills(address, start, sleep)
        except Exception:
            failed += 1
            continue
        write_gz(fills_path(address), merge_fills(old, new, keep_from=now_ms - FILLS_KEEP_DAYS * 86_400_000))
        done += 1
    log(f"{now:%Y-%m-%d %H:%M} fill: {done} conti aggiornati, {failed} errori")


# ---- the strategy, rebuilt from fills

STYLE = ((1 / 24, "scalper"), (1, "trader intraday"), (14, "swing trader"), (float("inf"), "trader di posizione"))


def round_trips(fills):
    """Each position from flat to flat on one market: open time, close time, side, pnl net of fees. A position already open
    when the history starts is left out, because its opening isn't known."""
    trips, open_ = [], {}
    for f in fills:
        t, coin, px, sz, side, start = f[0], f[1], f[2], f[3], f[4], f[5]
        after = start + (sz if side == "B" else -sz)
        cur = open_.get(coin)
        if cur is None and abs(start) < 1e-12 and abs(after) > 1e-12:
            cur = open_[coin] = {"coin": coin, "open": t, "side": 1 if after > 0 else -1, "pnl": 0.0, "volume": 0.0}
        if cur is not None:
            cur["pnl"] += f[7] - f[8]
            cur["volume"] += px * sz
            if abs(after) < 1e-12 or (after > 0) != (cur["side"] > 0):
                cur["close"] = t
                trips.append(open_.pop(coin))
                if abs(after) > 1e-12:  # flipped: the rest opens a new position the other way
                    open_[coin] = {"coin": coin, "open": t, "side": 1 if after > 0 else -1, "pnl": 0.0, "volume": 0.0}
    return trips


def profile(fills, gross=None):
    """How an account trades, in numbers and in one sentence. Empty when there's nothing to read.

    With few positions opened and closed in the window, the holding time is estimated from turnover instead:
    gross exposure now divided by half the daily volume, the time it takes to trade the book once in and once out."""
    if not fills:
        return None
    vol = lambda fs: sum(f[2] * f[3] for f in fs)
    total = vol(fills) or 1.0
    by_coin = defaultdict(list)
    for f in fills:
        by_coin[f[1]].append(f)
    coins = sorted(({"coin": c, "share": vol(fs) / total, "pnl": sum(f[7] - f[8] for f in fs), "fills": len(fs)} for c, fs in by_coin.items()), key=lambda c: -c["share"])
    opens = [f for f in fills if f[6].startswith("Open")]
    long_share = vol([f for f in opens if f[6] == "Open Long"]) / (vol(opens) or 1.0) if opens else None
    maker = vol([f for f in fills if f[9]]) / total
    twap = vol([f for f in fills if f[10]]) / total
    trips = round_trips(fills)
    holds = [(t["close"] - t["open"]) / 86_400_000 for t in trips]
    hold = statistics.median(holds) if holds else None
    wins = [t for t in trips if t["pnl"] > 0]
    hours = Counter(datetime.fromtimestamp(f[0] / 1000, timezone.utc).hour for f in fills)
    days = (fills[-1][0] - fills[0][0]) / 86_400_000
    closes = [f for f in fills if f[6].startswith("Close")]
    turnover_hold = gross / (total / max(days, 1 / 24) / 2) if gross and total else None
    out = {"fills": len(fills), "from": fills[0][0], "to": fills[-1][0], "days": days, "volume": total, "fees": sum(f[8] for f in fills), "realized": sum(f[7] for f in fills),
           "coins": coins[:12], "markets": len(coins), "long_share": long_share, "maker_share": maker, "twap_share": twap, "trips": len(trips), "hold_days": hold if len(trips) >= 5 else None, "hold_estimate": turnover_hold,
           "close_win": sum(f[7] > 0 for f in closes) / len(closes) if closes else None,
           "win_rate": len(wins) / len(trips) if trips else None, "avg_win": statistics.mean(t["pnl"] for t in wins) if wins else None,
           "avg_loss": statistics.mean(t["pnl"] for t in trips if t["pnl"] <= 0) if len(wins) < len(trips) else None,
           "hours": [hours.get(h, 0) for h in range(24)], "trades_per_day": len(trips) / days if days >= 1 else None}
    out["sentence"] = describe(out)
    return out


def describe(p):
    """One sentence a person can read: style, direction, focus, how it executes."""
    bits = []
    hold, how_known = (p["hold_days"], "in media") if p["hold_days"] is not None else (p["hold_estimate"], "circa")
    if hold is not None:
        style = next(w for limit, w in STYLE if hold < limit)
        held = f"{hold * 24 * 60:.0f} minuti" if hold < 1 / 24 else f"{hold * 24:.0f} ore" if hold < 1 else f"{hold:.1f} giorni".replace(".", ",")
        bits.append(f"{style.capitalize()}: tiene una posizione {how_known} {held}")
    else:
        bits.append("Tiene a lungo: nel periodo non ha mai chiuso del tutto una posizione")
    if p["long_share"] is not None:
        bits.append("apre soprattutto long" if p["long_share"] >= .7 else "apre soprattutto short" if p["long_share"] <= .3 else "apre sia long sia short")
    top = p["coins"][0]
    if top["share"] >= .5:
        bits.append(f"concentrato su {top['coin']} ({top['share']:.0%} del volume)")
    else:
        bits.append(f"su {p['markets']} mercati, il primo è {top['coin']} ({top['share']:.0%})")
    if p["win_rate"] is not None and p["trips"] >= 5:
        bits.append(f"chiude in utile il {p['win_rate']:.0%} delle operazioni")
    elif p["close_win"] is not None:
        bits.append(f"il {p['close_win']:.0%} delle chiusure è in utile")
    how = "ordini limite" if p["maker_share"] >= .6 else "ordini a mercato" if p["maker_share"] <= .2 else "ordini limite e a mercato"
    bits.append(f"usa {how}" + (" e TWAP" if p["twap_share"] >= .3 else ""))
    return ", ".join(bits) + "."


# ---- one account in detail, on request

def portfolio_curve(address):
    p = dict(http(INFO, {"type": "portfolio", "user": address}, timeout=30))
    a = p.get("allTime", {})
    pnl = [[int(t), float(v)] for t, v in a.get("pnlHistory", [])]
    value = [[int(t), float(v)] for t, v in a.get("accountValueHistory", [])]
    peak, dd = float("-inf"), 0.0
    for _, v in pnl:
        peak = max(peak, v)
        dd = min(dd, v - peak)
    return {"pnl": pnl, "value": value, "max_drawdown": dd, "volume": float(a.get("vlm") or 0)}


def open_positions(address):
    """Positions now, with how far each is from liquidation, and the account's exposure."""
    rows, value, margin = [], 0.0, 0.0
    for dex in DEXES:
        d = state_of(address, dex)
        m = d.get("marginSummary", {})
        value += float(m.get("accountValue") or 0)
        margin += float(m.get("totalMarginUsed") or 0)
        for p in d.get("assetPositions", []):
            x = p["position"]
            size, pv = float(x["szi"]), float(x.get("positionValue") or 0)
            mark = pv / abs(size) if size else None
            liq = float(x["liquidationPx"]) if x.get("liquidationPx") else None
            rows.append({"coin": x["coin"], "side": "long" if size > 0 else "short", "value": pv, "size": abs(size), "entry": float(x.get("entryPx") or 0), "mark": mark,
                         "upnl": float(x.get("unrealizedPnl") or 0), "roe": float(x.get("returnOnEquity") or 0), "leverage": (x.get("leverage") or {}).get("value"),
                         "lev_type": (x.get("leverage") or {}).get("type"), "liq": liq, "liq_dist": 100 * abs(mark - liq) / mark if liq and mark else None,
                         "funding": -float((x.get("cumFunding") or {}).get("sinceOpen") or 0)})
    rows.sort(key=lambda r: -r["value"])
    long_, short = sum(r["value"] for r in rows if r["side"] == "long"), sum(r["value"] for r in rows if r["side"] == "short")
    return {"positions": rows, "value": value, "margin": margin, "long": long_, "short": short, "net": long_ - short, "leverage": (long_ + short) / value if value else None,
            "structure": structure(rows, value)}


def structure(rows, capital):
    """The shape of the book now, in one sentence: one bet, a hedged bet, a basket, or both sides."""
    if not rows:
        return "Oggi non ha posizioni aperte."
    name = lambda r: r["coin"].replace("xyz:", "")
    pct = lambda v: f"{100 * v / capital:.0f}% del capitale" if capital else ""
    longs, shorts = [r for r in rows if r["side"] == "long"], [r for r in rows if r["side"] == "short"]
    gross = sum(r["value"] for r in rows)
    top = rows[0]
    if len(rows) == 1:
        return f"Oggi ha una sola scommessa: {top['side']} {name(top)} ({pct(top['value'])})."
    if top["value"] >= .5 * gross:
        others = shorts if top["side"] == "long" else longs
        if others and sum(r["value"] for r in others) >= .2 * top["value"]:
            return (f"Oggi è {top['side']} {name(top)} ({pct(top['value'])}), coperto da {'short' if top['side'] == 'long' else 'long'} su {len(others)} "
                    f"{'mercato' if len(others) == 1 else 'mercati'} ({pct(sum(r['value'] for r in others))} in tutto): una scommessa su {name(top)} contro il resto.")
        return f"Oggi la posizione principale è {top['side']} {name(top)} ({pct(top['value'])}), il resto è piccolo."
    if longs and shorts and min(sum(r["value"] for r in longs), sum(r["value"] for r in shorts)) >= .3 * gross:
        return f"Oggi è long su {len(longs)} e short su {len(shorts)} mercati, in misura simile: un portafoglio long-short più che una scommessa di direzione."
    side = "long" if sum(r["value"] for r in longs) > sum(r["value"] for r in shorts) else "short"
    return f"Oggi è soprattutto {side}, su {len(longs if side == 'long' else shorts)} mercati: il più grande è {name(top)} ({pct(top['value'])})."


def exposure_history(address, days=30):
    """Net and gross dollars held, and the net on the largest markets, from our hourly rounds."""
    t, net, gross, per = [], [], [], defaultdict(dict)
    for f in position_files(days):
        try:
            w = read_gz(f)["wallets"].get(address)
        except Exception:
            continue
        if w is None:
            continue
        stamp = f"{f.parent.name}T{f.name[:2]}:{f.name[2:4]}"
        signed = defaultdict(float)
        for _dex, coin, size, _e, value, *_ in w["positions"]:
            signed[coin] += value if size > 0 else -value
        t.append(stamp)
        net.append(sum(signed.values()))
        gross.append(sum(abs(v) for v in signed.values()))
        for c, v in signed.items():
            per[c][stamp] = v
    top = sorted(per, key=lambda c: -max(abs(v) for v in per[c].values()))[:4]
    return {"t": t, "net": net, "gross": gross, "coins": {c: [per[c].get(s, 0.0) for s in t] for c in top}}


def vault_info(address):
    d = http(INFO, {"type": "vaultDetails", "vaultAddress": address}, timeout=30)
    return {"name": d.get("name"), "description": d.get("description"), "leader": d.get("leader"), "apr": d.get("apr"), "followers": len(d.get("followers") or []),
            "leader_share": d.get("leaderFraction"), "commission": d.get("leaderCommission"), "deposits": d.get("allowDeposits")}


def detail(address, now=None):
    """Everything about one followed account. Fresh from Hyperliquid, kept a few minutes."""
    with _lock:
        hit = _detail.get(address)
    if hit and time.time() - hit[0] < DETAIL_SECONDS:
        return hit[1]
    f = followed() or {}
    address = next((a for a in f.get("wallets", {}) if a.lower() == address.lower()), None)
    if address is None:
        return None
    cohort = f["wallets"][address]
    now = now or datetime.now(timezone.utc)
    stored = stored_fills(address)
    since = stored[-1][0] + 1 if stored else now.timestamp() * 1000 - FILLS_FIRST_DAYS * 86_400_000
    fills = merge_fills(stored, fetch_fills(address, since, sleep=lambda s: time.sleep(.2)), keep_from=now.timestamp() * 1000 - 30 * 86_400_000)
    pos = open_positions(address)
    lb = leaderboard_rows().get(address, {})
    out = {"address": address, "cohort": cohort, "name": f.get("names", {}).get(address) or (f.get("vaults", {}).get(address) or {}).get("name"),
           "leaderboard": lb or None, "now": pos, "curve": portfolio_curve(address), "profile": profile(fills, pos["long"] + pos["short"]),
           "history": exposure_history(address), "vault": vault_info(address) if cohort == VAULT else None, "at": now.isoformat(timespec="seconds")}
    with _lock:
        _detail[address] = (time.time(), out)
    return out


# ---- what the app lists

def flows(snap, groups=None):
    """Per market: how many followed accounts are long or short, and their net dollars, per group. Short is negative."""
    out = {}
    for w in (snap or {}).get("wallets", {}).values():
        g = w["cohort"] if groups is None else groups(w["cohort"])
        for dex, coin, size, _entry, value, *_ in w["positions"]:
            side = out.setdefault(coin, {}).setdefault(g, {"long": 0, "short": 0, "net": 0.0})
            side["long" if size > 0 else "short"] += 1
            side["net"] += value if size > 0 else -value
    return out


def kind_of(cohort):
    return "vault" if cohort == VAULT else "trader"


def view():
    """The followed accounts with what they hold now, and where they stand per market."""
    snap, f = latest_positions(), followed() or {}
    if not snap:
        return None
    lb, vaults, names = leaderboard_rows(), f.get("vaults", {}), f.get("names", {})
    accounts = []
    for address, w in snap["wallets"].items():
        if w["cohort"] not in COHORTS and w["cohort"] != VAULT:
            continue  # a round taken before the losers stopped being followed
        if w["capital"] < KEEP_ACCOUNT_MIN:
            continue  # emptied since it made the list: nothing left to read
        signed = defaultdict(float)
        for _dex, coin, size, _e, value, *_ in w["positions"]:
            signed[coin] += value if size > 0 else -value
        long_, short = sum(v for v in signed.values() if v > 0), -sum(v for v in signed.values() if v < 0)
        row, v = lb.get(address, {}), vaults.get(address, {})
        accounts.append({"address": address, "kind": kind_of(w["cohort"]), "cohort": w["cohort"], "name": names.get(address) or v.get("name"),
                         "capital": w["capital"], "pnl_all": row.get("pnl_all", v.get("pnl_all")), "pnl_month": row.get("pnl_month"), "apr": v.get("apr"),
                         "long": long_, "short": short, "net": long_ - short, "leverage": (long_ + short) / w["capital"] if w["capital"] else None,
                         "top": [[c, signed[c]] for c in sorted(signed, key=lambda c: -abs(signed[c]))[:3]], "positions": len(signed)})
    accounts.sort(key=lambda a: -(a["pnl_all"] or 0))
    per = flows({"wallets": {a: w for a, w in snap["wallets"].items() if w["cohort"] in COHORTS or w["cohort"] == VAULT}}, kind_of)
    markets = [{"market": c, "trader": per[c].get("trader"), "vault": per[c].get("vault")} for c in sorted(per, key=lambda c: -sum(abs(g["net"]) for g in per[c].values()))[:30]]
    return {"at": snap["at"], "accounts": accounts, "markets": markets, "counts": Counter(a["kind"] for a in accounts)}


def flows_text(snap, top=15):
    f = flows(snap, kind_of)
    if not f:
        return "nessuna posizione registrata"
    lines = [f"Posizioni del {snap['at'][:16].replace('T', ' ')} UTC. Netto in dollari, + long e - short. Descrive, non è testato come segnale.", f"{'mercato':14}{'trader':>22}{'vault':>22}"]
    cell = lambda s: "–" if not s else f"{s['net'] / 1e6:+.1f}M ({s['long']}L/{s['short']}S)"
    for c in sorted(f, key=lambda c: -sum(abs(g["net"]) for g in f[c].values()))[:top]:
        lines.append(f"{c:14}{cell(f[c].get('trader')):>22}{cell(f[c].get('vault')):>22}")
    return "\n".join(lines)


# ---- loop

def cycle(st, now=None, log=print):
    now = now or datetime.now(timezone.utc)
    today = f"{now:%Y-%m-%d}"
    if st.get("leaderboard") != today:
        try:
            rows, cohorts = take_leaderboard(now)
            st["leaderboard"], st["cohorts"] = today, cohorts
            log(f"{today} classifica: {len(rows)} conti, seguiti {sum(v != VAULT for v in cohorts.values())} trader e {sum(v == VAULT for v in cohorts.values())} vault")
        except Exception as e:
            log(f"classifica non scaricata, riprovo: {type(e).__name__}: {e}")
    if not st.get("cohorts"):
        st["cohorts"] = (followed() or {}).get("wallets", {})
    if st["cohorts"] and now.timestamp() - st.get("positions", 0) >= POSITIONS_EVERY:
        st["positions"] = now.timestamp() // POSITIONS_EVERY * POSITIONS_EVERY
        take_positions(st["cohorts"], now, log=log)
    if st["cohorts"] and st.get("fills") != today:
        st["fills"] = today
        update_fills(st["cohorts"], now, log=log)


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
    if cmd == "profilo" and len(argv) > 1:
        pos = open_positions(argv[1])
        fills = merge_fills(stored_fills(argv[1]), fetch_fills(argv[1], time.time() * 1000 - FILLS_FIRST_DAYS * 86_400_000))
        p = profile(fills, pos["long"] + pos["short"])
        print(p["sentence"] if p else "nessun fill")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
