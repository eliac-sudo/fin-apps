"""Strong price moves, close to real time, from the Hyperliquid snapshots the recorder already saves.

A move counts when it's large against that market's own recent daily volatility. Thresholds were chosen for how often they fire
(about 2-3 messages a week on crypto over the last year), not for what happens next: this says the price is moving, not where it goes.
It costs nothing, since it only reads saved data, and it never places orders.
"""
import gzip, json, math, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .events import crypto_daily, daily, read
from .history import safe
from .recorder import BASE

K_4H, K_24H = 3.5, 3.0  # in units of daily volatility scaled to the window
SIGMA_DAYS = 90
COOLDOWN_HOURS = 12  # per market and direction
MAX_SNAPSHOT_AGE_MIN = 40
NAMES = {"xyz:SP500": "S&P 500", "xyz:XYZ100": "Nasdaq 100", "xyz:CL": "Petrolio", "xyz:GOLD": "Oro", "xyz:SILVER": "Argento", "xyz:COPPER": "Rame",
         "xyz:EUR": "EUR/USD", "xyz:JPY": "USD/JPY", "xyz:GBP": "GBP/USD", "xyz:TLT": "Bond 30 anni"}
CLASS_OF = {"xyz:SP500": "equities", "xyz:XYZ100": "equities", "xyz:CL": "commodities", "xyz:GOLD": "commodities", "xyz:SILVER": "commodities",
            "xyz:COPPER": "commodities", "xyz:EUR": "fx", "xyz:JPY": "fx", "xyz:GBP": "fx", "xyz:TLT": "bonds"}


def snapshot_files(job, root=None):
    base = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw" / job
    return sorted(base.glob("*/*.gz"), key=lambda p: (p.parent.name, p.name))


def snapshot_time(p):
    return datetime.strptime(p.parent.name + p.name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc)


def read_marks(p):
    meta, ctx = json.load(gzip.open(p))
    return {a["name"]: (float(x["markPx"]), float(x["prevDayPx"]) if x.get("prevDayPx") else None) for a, x in zip(meta["universe"], ctx) if x.get("markPx")}


def nearest(files, when, tolerance_min=30):
    """The saved snapshot closest to a past moment, or None if there's none near it, for example after a pause."""
    best = min(files, key=lambda p: abs((snapshot_time(p) - when).total_seconds()), default=None)
    return best if best and abs((snapshot_time(best) - when).total_seconds()) <= tolerance_min * 60 else None


def daily_sigma(close):
    r = np.log(close.dropna().tail(SIGMA_DAYS + 1)).diff().dropna()  # only the recent part: oil's negative price in 2020 has no log
    return float(r.std()) if len(r) >= SIGMA_DAYS // 2 else None


def market_sigma(market):
    """Daily volatility, from the same stored history the setups use."""
    d = crypto_daily(market) if "=" not in market else read("tradfi", safe(market))
    return daily_sigma((d if "=" not in market else daily(d)).close) if d is not None else None


def assess(name, mark, prev_day, mark_4h, sigma):
    """The larger of the 4h and 24h moves against its threshold, or None if neither is reached."""
    if not sigma:
        return None
    best = None
    for window, base, k, scale in (("4h", mark_4h, K_4H, math.sqrt(4 / 24)), ("24h", prev_day, K_24H, 1)):
        if base:
            limit = k * sigma * scale
            size = math.log(mark / base)
            if abs(size) >= limit and (not best or abs(size) / limit > best["strength"]):
                best = {"name": name, "window": window, "pct": round(100 * (mark / base - 1), 2), "limit_pct": round(100 * (math.exp(math.copysign(limit, size)) - 1), 2),
                        "strength": round(abs(size) / limit, 2), "mark": mark, "down": size < 0}
    return best


def find_moves(markets, st, now, root=None, sigma=market_sigma):
    """`markets` maps the Hyperliquid name to the market in our history. Each new snapshot is checked once."""
    found, seen = [], st.setdefault("move_snapshots", {})
    for job in ("hl_ctx_main", "hl_ctx_xyz"):
        files = snapshot_files(job, root)
        if not files or (now - snapshot_time(files[-1])).total_seconds() > MAX_SNAPSHOT_AGE_MIN * 60 or seen.get(job) == files[-1].name:
            continue
        seen[job] = files[-1].name
        cur = read_marks(files[-1])
        old_file = nearest(files[:-1], snapshot_time(files[-1]) - timedelta(hours=4))
        old = read_marks(old_file) if old_file else {}
        for name, market in markets.items():
            if name in cur and (name.startswith("xyz:") == (job == "hl_ctx_xyz")):
                m = assess(name, cur[name][0], cur[name][1], old.get(name, (None,))[0], sigma(market))
                if m:
                    found.append({**m, "market": market, "class": CLASS_OF.get(name, "crypto"), "at": snapshot_time(files[-1]).isoformat()})
    return found


def apply_cooldown(moves, st, now):
    """One alert per market and direction every 12 hours, so a long slide doesn't send one every 15 minutes."""
    last, out = st.setdefault("move_last", {}), []
    for m in moves:
        k = f"{m['name']}|{'down' if m['down'] else 'up'}"
        if now.timestamp() - last.get(k, 0) >= COOLDOWN_HOURS * 3600:
            last[k] = now.timestamp()
            out.append(m)
    return out


def price_text(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:.4f}" if x >= 1 else f"{x:.6f}"


def format_moves(moves, now, options=""):
    """One message for all moves in a check, so a market-wide drop doesn't send nineteen."""
    lines = [f"⚡ <b>FORTE MOVIMENTO</b> · {now:%d/%m %H:%M} UTC", ""]
    for m in sorted(moves, key=lambda x: -x["strength"]):
        name = NAMES.get(m["name"], m["name"])
        lines.append(f"{'🔻' if m['down'] else '🔺'} <b>{name}</b> {m['pct']:+.1f}% in {m['window']} · ora {price_text(m['mark'])} (soglia {m['limit_pct']:+.1f}%)")
        if m.get("position"):
            lines.append(f"   Prezzo: {m['position']}")
        if m.get("context"):
            lines.append(m["context"])
    if options:
        lines += ["", options]
    lines += ["", "Prezzi Hyperliquid. Dice che il prezzo si muove, non dove andrà: non è testato come segnale e non è consulenza finanziaria."]
    return "\n".join(lines)
