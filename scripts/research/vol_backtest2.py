"""Second pass, variants fixed before the run:
M1-M3  put spread 20/7, naked put 20d, put spread 10/3, filled at the mark as a maker: no half-spread, no option fee.
DH1    sell the ATM straddle, delta-hedge with the perpetual once a day at 08:00 UTC, full option costs, 0.05% per perp trade.
DH2    the same with the 25-delta strangle.
DH1m, DH2m  the same two with maker option fills.
Delta from Black-76 at the entry vol of each leg. Funding on the perp hedge is paid or received hour by hour (Deribit history; zero before May 2019). P&L in USD per 1 BTC of notional.

    .venv/bin/python scripts/research/vol_backtest2.py DIR BTC ETH
"""
import json, math, sys
from datetime import timedelta
from pathlib import Path
import numpy as np
from scipy.special import ndtr

sys.path.insert(0, str(Path(__file__).parent))
import vol_backtest as T

D = Path(sys.argv[1])
PERP_FEE = 0.0005


def bs_delta(typ, S, K, iv, years):
    if years <= 0:
        return (1.0 if S > K else 0.0) if typ == "C" else (-1.0 if S < K else 0.0)
    sq = max(iv * math.sqrt(years), 1e-9)
    d1 = (math.log(S / K) + .5 * sq * sq) / sq
    return ndtr(d1) if typ == "C" else ndtr(d1) - 1


def pick_atm(chain, S):
    out = []
    for typ in ("P", "C"):
        side = [o for o in chain if o["typ"] == typ and o["mark"] > 0]
        if not side:
            return None
        out.append(min(side, key=lambda o: abs(o["K"] - S)))
    if out[0]["K"] != out[1]["K"]:
        return None
    return out


def funding_sum(fund_ts, fund_cum, a, b):
    """Sum of hourly funding rates between two datetimes."""
    import bisect
    i, j = bisect.bisect_left(fund_ts, a.timestamp() * 1000), bisect.bisect_left(fund_ts, b.timestamp() * 1000)
    return fund_cum[j] - fund_cum[i]


def run(cur):
    px = json.loads((D / cur / "px0800.json").read_text())
    f = json.loads((D / cur / "funding_1h.json").read_text())
    fund_ts = sorted(int(k) for k in f)
    fund_cum = [0.0]
    for k in fund_ts:
        fund_cum.append(fund_cum[-1] + f[str(k)])
    res = []
    for f in sorted((D / cur).glob("*.json.gz")):
        snap = T.snapshot(f)
        if not snap:
            continue
        t0, by_exp = snap
        exps = [(e, (e - t0).total_seconds() / 86400) for e in by_exp if 21 <= (e - t0).total_seconds() / 86400 <= 45]
        if not exps:
            continue
        exp, days = min(exps, key=lambda x: abs(x[1] - 30))
        ST = px.get(exp.strftime("%Y-%m-%d"))
        if not ST:
            continue
        chain, S0 = by_exp[exp], by_exp[exp][0]["S"]
        years0 = days / 365
        books = {}
        for name, spec in (("M1 put spread 20/7 maker", T.VARIANTS["B put spread 20/7"]), ("M2 put nuda 20Δ maker", T.VARIANTS["A put nuda 20Δ"]),
                           ("M3 put spread 10/3 maker", T.VARIANTS["H put spread 10/3"])):
            legs = T.pick(spec, chain, S0, years0)
            if legs:
                books[name] = (legs, False, True)
        atm = pick_atm(chain, S0)
        strg = T.pick([("P", .25, -1), ("C", .25, -1)], chain, S0, years0)
        if atm:
            atm = [{**o, "qty": -1} for o in atm]
            books["DH1 straddle coperto"] = (atm, True, False)
            books["DH1m straddle coperto, maker"] = (atm, True, True)
        if strg:
            books["DH2 strangle 25Δ coperto"] = (strg, True, False)
            books["DH2m strangle 25Δ coperto, maker"] = (strg, True, True)
        for name, (legs, hedge, maker) in books.items():
            cash_usd = 0.0
            for o in legs:
                hs = 0.0 if maker else T.half_spread(o["mark"])
                fee = 0.0 if maker else T.fee(o["mark"])
                p = o["mark"] - hs if o["qty"] < 0 else o["mark"] + hs
                cash_usd += (-o["qty"] * p - fee) * S0
            pay = sum(o["qty"] * (max(o["K"] - ST, 0) if o["typ"] == "P" else max(ST - o["K"], 0)) for o in legs)
            settle = sum(min(0.00015, .125 * o["mark"]) * ST for o in legs if (o["K"] > ST if o["typ"] == "P" else o["K"] < ST))
            hedge_pnl = 0.0
            if hedge:
                pos, S_prev = 0.0, S0
                day = t0.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
                # first hedge at entry
                d = sum(o["qty"] * bs_delta(o["typ"], S0, o["K"], o["iv"], years0) for o in legs)
                pos = -d
                hedge_pnl -= abs(pos) * S0 * PERP_FEE
                hedge_pnl -= pos * S0 * funding_sum(fund_ts, fund_cum, t0, day - timedelta(days=1))
                while day < exp:
                    S = px.get(day.strftime("%Y-%m-%d"))
                    if S:
                        hedge_pnl += pos * (S - S_prev) - pos * S_prev * funding_sum(fund_ts, fund_cum, day - timedelta(days=1), day)
                        yrs = (exp - day).total_seconds() / (365 * 86400)
                        new = -sum(o["qty"] * bs_delta(o["typ"], S, o["K"], o["iv"], yrs) for o in legs)
                        hedge_pnl -= abs(new - pos) * S * PERP_FEE
                        pos, S_prev = new, S
                    day += timedelta(days=1)
                hedge_pnl += pos * (ST - S_prev) - abs(pos) * ST * PERP_FEE - pos * S_prev * funding_sum(fund_ts, fund_cum, day - timedelta(days=1), exp)
            pnl = cash_usd + pay - settle + hedge_pnl
            res.append({"v": name, "t": t0, "exp": exp, "pnl_n": pnl / S0, "credit_n": cash_usd / S0})
    return res


if __name__ == "__main__":
    for cur in sys.argv[2:]:
        tr = run(cur)
        print(f"\n=== {cur}")
        print(f"{'variante':34} {'n':>4} {'vinte':>6} {'medio % nozionale':>17} {'t':>5} {'peggiore':>8} {'premio medio':>12} | 1a metà  2a metà")
        for v in dict.fromkeys(t["v"] for t in tr):
            x = [t for t in tr if t["v"] == v]
            r = np.array([t["pnl_n"] for t in x])
            se = r.std() / math.sqrt(len(r) / 4)
            m = len(r) // 2
            # portfolio: each entry carries 25% of equity as notional, P&L lands at expiry
            eq, peak, mdd, pend = 1.0, 1.0, 0.0, []
            for t in sorted(x, key=lambda t: t["t"]):
                for q in [q for q in pend if q[0] <= t["t"]]:
                    eq += q[1]; pend.remove(q); peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
                pend.append((t["exp"], .25 * eq * t["pnl_n"]))
            for q in pend:
                eq += q[1]
            mdd = min(mdd, eq / max(peak, eq) - 1)
            yrs = (x[-1]["t"] - x[0]["t"]).days / 365.25
            cagr = max(eq, 1e-9) ** (1 / yrs) - 1
            years = {}
            for t in x:
                years.setdefault(t["t"].year, []).append(t["pnl_n"])
            ylist = " ".join(f"{k % 100:02d}:{np.mean(a) * 100:+.1f}" for k, a in sorted(years.items()))
            print(f"   portafoglio 25%/entrata: {cagr:+.1%} l'anno, max DD {mdd:.0%} | per anno, % nozionale: {ylist}")
            print(f"{v:34} {len(r):4d} {(r > 0).mean():6.0%} {r.mean():17.2%} {r.mean() / se:5.1f} {r.min():8.1%} {np.mean([t['credit_n'] for t in x]):12.2%} | {r[:m].mean():6.2%}  {r[m:].mean():6.2%}")
