"""Put spreads and friends on real Deribit marks, one entry every Monday, held to expiry.

Prices: the mark price of each instrument's last trade in the Monday 10:00-16:00 UTC window (real smile and basis).
Costs: half-spread max(0.0001, 4% of price) per leg in and out of the position, Deribit fee 0.0003 coin per leg capped at
12.5% of the price, delivery fee 0.00015 coin capped at 12.5% on legs that finish in the money.
Settlement: the perpetual at 08:00 UTC on the expiry day (vol_fetch_px.py), when Deribit settles.
Variants fixed before the run (A..H). No parameter is tuned on the result. NOCOST=1 drops every cost.

    .venv/bin/python scripts/research/vol_backtest.py DIR BTC ETH
"""
import gzip, json, math, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from scipy.special import ndtr

D = Path(sys.argv[1])
VARIANTS = {
    "A put nuda 20Δ":          [("P", .20, -1)],
    "B put spread 20/7":       [("P", .20, -1), ("P", .07, 1)],
    "C put spread 20/10":      [("P", .20, -1), ("P", .10, 1)],
    "D put spread 30/10":      [("P", .30, -1), ("P", .10, 1)],
    "E put spread 20, ala 5%": [("P", .20, -1), ("P", "5%", 1)],
    "F iron condor 20/7":      [("P", .20, -1), ("P", .07, 1), ("C", .20, -1), ("C", .07, 1)],
    "G strangle 20Δ":          [("P", .20, -1), ("C", .20, -1)],
    "H put spread 10/3":       [("P", .10, -1), ("P", .03, 1)],
}
STRESS = 0.4  # naked legs: risk measured at a 60% fall (puts) or 2.5x rise (calls)


import os
COSTS = os.environ.get("NOCOST") != "1"


def half_spread(px):
    return max(0.0001, 0.04 * px) if COSTS else 0.0


def fee(px):
    return min(0.0003, 0.125 * px) if COSTS else 0.0


def snapshot(f):
    trades = json.loads(gzip.decompress(f.read_bytes()))
    if not trades:
        return None
    t0 = datetime.fromtimestamp(trades[0]["timestamp"] / 1000, timezone.utc)
    last = {}
    for x in trades:
        last[x["instrument_name"]] = x
    by_exp = {}
    for n, x in last.items():
        _, e, k, typ = n.split("-")
        exp = datetime.strptime(e, "%d%b%y").replace(hour=8, tzinfo=timezone.utc)
        by_exp.setdefault(exp, []).append({"name": n, "K": float(k), "typ": typ, "mark": x["mark_price"], "iv": x["iv"] / 100, "S": x["index_price"]})
    return t0, by_exp


def delta(o, S, years):
    sq = max(o["iv"] * math.sqrt(years), 1e-9)
    d1 = (math.log(S / o["K"]) + .5 * sq * sq) / sq
    return ndtr(d1) if o["typ"] == "C" else ndtr(d1) - 1


def pick(legs_spec, chain, S, years):
    chosen = []
    for typ, target, qty in legs_spec:
        side = [o for o in chain if o["typ"] == typ and o["mark"] > 0 and (o["K"] < S if typ == "P" else o["K"] > S)]
        if target == "5%":
            short = chosen[0]
            cands = [o for o in side if o["K"] < short["K"]]
            if not cands:
                return None
            o = min(cands, key=lambda o: abs(o["K"] - .95 * short["K"]))
        else:
            if not side:
                return None
            o = min(side, key=lambda o: abs(abs(delta(o, S, years)) - target))
            if abs(abs(delta(o, S, years)) - target) > target * .5 + .02:
                return None  # nothing traded near that delta
        if qty > 0 and chosen:
            ref = chosen[-1]
            if (typ == "P" and o["K"] >= ref["K"]) or (typ == "C" and o["K"] <= ref["K"]):
                return None  # wing must sit beyond the sold leg
        chosen.append({**o, "qty": qty})
    return chosen


def run(cur):
    deliv = json.loads((D / cur / "px0800.json").read_text())  # perpetual at 08:00 UTC, when Deribit settles
    trades = []
    for f in sorted((D / cur).glob("*.json.gz")):
        snap = snapshot(f)
        if not snap:
            continue
        t0, by_exp = snap
        exps = [(e, (e - t0).total_seconds() / 86400) for e in by_exp if 21 <= (e - t0).total_seconds() / 86400 <= 45]
        if not exps:
            continue
        exp, days = min(exps, key=lambda x: abs(x[1] - 30))
        ST = deliv.get(exp.strftime("%Y-%m-%d"))
        if not ST:
            continue
        chain = by_exp[exp]
        S0 = chain[0]["S"]
        for name, spec in VARIANTS.items():
            legs = pick(spec, chain, S0, days / 365)
            if not legs:
                continue
            cash = 0.0  # coin
            for o in legs:
                px = o["mark"] - half_spread(o["mark"]) if o["qty"] < 0 else o["mark"] + half_spread(o["mark"])
                cash += -o["qty"] * px - fee(o["mark"])
            pay_usd = sum(o["qty"] * (max(o["K"] - ST, 0) if o["typ"] == "P" else max(ST - o["K"], 0)) for o in legs)
            settle_fee = COSTS * sum(min(0.00015, .125 * o["mark"]) for o in legs if (o["K"] > ST if o["typ"] == "P" else o["K"] < ST))
            pnl_coin = cash + pay_usd / ST - settle_fee
            pnl_usd = cash * S0 + pay_usd - settle_fee * ST
            # risk per contract, USD for USDC books, coin for coin books
            def payoff_at(S):
                return sum(o["qty"] * (max(o["K"] - S, 0) if o["typ"] == "P" else max(S - o["K"], 0)) for o in legs)
            grid = [S0 * x for x in np.linspace(STRESS, 2.5, 400)]
            risk_usd = max(-(cash * S0 + payoff_at(S)) for S in grid)
            longp = [o["K"] for o in legs if o["typ"] == "P" and o["qty"] > 0]
            s_stress = (min(longp) * .5) if longp else S0 * STRESS
            risk_coin = max(-(cash + payoff_at(S) / S) for S in grid + [s_stress])
            trades.append({"v": name, "t": t0, "exp": exp, "pnl_usd": pnl_usd, "pnl_coin": pnl_coin, "risk_usd": risk_usd, "risk_coin": risk_coin,
                           "credit_usd": cash * S0, "S0": S0})
    return trades


def portfolio(tr, key):
    """The bot's sizing: each trade risks 3% of equity, all open at most 12%; P&L lands at expiry."""
    eq, peak, mdd, open_ = 1.0, 1.0, 0.0, []
    curve = []
    for t in sorted(tr, key=lambda x: x["t"]):
        for o in [o for o in open_ if o[0] <= t["t"]]:
            eq += o[1]; open_.remove(o)
            peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
        r = t[f"risk_{key}"]
        if r <= 0 or eq <= 0:
            continue
        used = sum(o[2] for o in open_)
        budget = min(.03 * eq, .12 * eq - used)
        if budget <= 0:
            continue
        n = budget / r
        open_.append((t["exp"], n * t[f"pnl_{key}"], n * r))
        curve.append((t["t"], eq))
    for o in open_:
        eq += o[1]
    peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    yrs = (tr[-1]["t"] - tr[0]["t"]).days / 365.25 if tr else 1
    return (max(eq, 1e-9)) ** (1 / yrs) - 1, mdd


if __name__ == "__main__":
    for cur in sys.argv[2:]:
        tr = run(cur)
        print(f"\n=== {cur}  ({min(t['t'] for t in tr):%Y-%m} -> {max(t['t'] for t in tr):%Y-%m})")
        print(f"{'variante':24} {'n':>4} {'vinte':>6} {'medio/rischio':>13} {'t':>5} {'peggiore':>8} | {'USDC: /anno':>11} {'maxDD':>6} | {'moneta: /anno':>13} {'maxDD':>6} | 1a metà  2a metà")
        for v in VARIANTS:
            x = [t for t in tr if t["v"] == v]
            if not x:
                continue
            r = np.array([t["pnl_usd"] / t["risk_usd"] for t in x])
            se = r.std() / math.sqrt(len(r) / 4)  # weekly entries overlap ~4 deep
            cu, du = portfolio(x, "usd")
            cc, dc = portfolio(x, "coin")
            mid = len(x) // 2
            h1, h2 = r[:mid].mean(), r[mid:].mean()
            print(f"{v:24} {len(x):4d} {(r > 0).mean():6.0%} {r.mean():13.1%} {r.mean() / se:5.1f} {r.min():8.0%} | {cu:11.1%} {du:6.0%} | {cc:13.1%} {dc:6.0%} | {h1:6.1%}  {h2:6.1%}")
