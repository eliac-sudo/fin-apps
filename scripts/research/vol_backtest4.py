"""Fourth pass: the strangle bot as built (bzd/vol_bot.py, config/vol_bot_v2.json) on BTC, hour by hour.

DH2m as in vol_backtest2.py: the 25-delta strangle sold as a maker each Monday, held to expiry. The hedge now runs on hourly
bars of the perpetual, with funding hour by hour and 0.05% per hedge trade, in two versions:
  08:00      once a day at 08:00 UTC, as in the backtest
  08:00+emg  the same, plus an emergency hedge in any hour when the net delta passes 0.2 BTC per BTC of strangle, as the bot does
Delta from Black-76 at each leg's entry vol, at the hour's close.

    .venv/bin/python scripts/research/vol_backtest4.py DIR     # DIR holds BTC/*.json.gz, BTC/perp_1h.json, BTC/funding_1h.json, BTC/px0800.json
"""
import bisect, json, math, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vol_backtest as T
import vol_backtest2 as T2

D = Path(sys.argv[1]) / "BTC"
BARS = json.loads((D / "perp_1h.json").read_text())
BT = [b[0] for b in BARS]
BC = [b[4] for b in BARS]
_f = json.loads((D / "funding_1h.json").read_text())
FUND = {int(k): v for k, v in _f.items()}
PX = json.loads((D / "px0800.json").read_text())
FEE = 0.0005
EMERGENCY = 0.2


def run():
    out = {"08:00": [], "08:00+emg": []}
    for f in sorted(D.glob("*.json.gz")):
        snap = T.snapshot(f)
        if not snap:
            continue
        t0, by = snap
        exps = [(e, (e - t0).total_seconds() / 86400) for e in by if 21 <= (e - t0).total_seconds() / 86400 <= 45]
        if not exps:
            continue
        exp, days = min(exps, key=lambda x: abs(x[1] - 30))
        ST = PX.get(exp.strftime("%Y-%m-%d"))
        chain, S0 = by[exp], by[exp][0]["S"]
        legs = T.pick([("P", .25, -1), ("C", .25, -1)], chain, S0, days / 365)
        if not (ST and legs):
            continue
        cash = sum(-o["qty"] * o["mark"] * S0 for o in legs)  # maker at the mark
        pay = sum(o["qty"] * (max(o["K"] - ST, 0) if o["typ"] == "P" else max(ST - o["K"], 0)) for o in legs)
        settle = sum(min(0.00015, .125 * o["mark"]) * ST for o in legs if (o["K"] > ST if o["typ"] == "P" else o["K"] < ST))
        i0 = bisect.bisect_left(BT, int(t0.timestamp() * 1000))
        i1 = bisect.bisect_left(BT, int(exp.timestamp() * 1000))
        if i1 >= len(BT) or i0 >= i1:
            continue

        def opt_delta(S, t_ms):
            yrs = (exp.timestamp() * 1000 - t_ms) / (365 * 86400 * 1000)
            return sum(o["qty"] * T2.bs_delta(o["typ"], S, o["K"], o["iv"], yrs) for o in legs)

        for name in out:
            pos = -opt_delta(S0, BT[i0])
            hedge = -abs(pos) * S0 * FEE
            S_prev, n_emg = S0, 0
            for j in range(i0, i1):
                S = BC[j]
                hedge += pos * (S - S_prev) - pos * S_prev * FUND.get(BT[j], 0.0)
                S_prev = S
                hour = (BT[j] // 3600000) % 24
                target = -opt_delta(S, BT[j] + 3600000)
                due = hour == 7  # the bar that closes at 08:00
                if name == "08:00+emg" and not due and abs(target - pos) > EMERGENCY:
                    due, n_emg = True, n_emg + 1
                if due and abs(target - pos) >= 0.001:
                    hedge -= abs(target - pos) * S * FEE
                    pos = target
            hedge += pos * (ST - S_prev) - abs(pos) * ST * FEE
            pnl = cash + pay - settle + hedge
            out[name].append({"t": t0, "exp": exp, "pnl_n": pnl / S0, "emg": n_emg})
    return out


def portfolio(x):
    eq, peak, mdd, pend = 1.0, 1.0, 0.0, []
    for t in sorted(x, key=lambda t: t["t"]):
        for q in [q for q in pend if q[0] <= t["t"]]:
            eq += q[1]; pend.remove(q); peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
        pend.append((t["exp"], .25 * eq * t["pnl_n"]))
    for q in pend:
        eq += q[1]
    mdd = min(mdd, eq / max(peak, eq) - 1)
    yrs = (x[-1]["t"] - x[0]["t"]).days / 365.25
    return eq ** (1 / yrs) - 1, mdd


if __name__ == "__main__":
    res = run()
    for name, x in res.items():
        r = np.array([t["pnl_n"] for t in x])
        se = r.std() / math.sqrt(len(r) / 4)
        cagr, mdd = portfolio(x)
        emg = np.mean([t["emg"] for t in x])
        print(f"{name:10} {len(r)} entrate | medio {r.mean():+.2%} del nozionale, t {r.mean() / se:.1f}, peggiore {r.min():+.1%}, "
              f"5% peggiori {np.mean(np.sort(r)[:max(1, len(r) // 20)]):+.1%} | {cagr:+.1%} l'anno, max DD {mdd:.0%} | coperture d'emergenza per entrata {emg:.1f}")
