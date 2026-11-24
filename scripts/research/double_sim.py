"""Double or nothing on the BTC perpetual: how often does an all-in leveraged position reach 2x before it is liquidated?

    .venv/bin/python scripts/research/double_sim.py DIR     # DIR holds BTC/perp_1h.json and BTC/funding_1h.json

All the capital is margin for a position of L times the capital. A throw wins when equity reaches 2x (take-profit as a maker
limit: no fee) and loses when equity falls to the maintenance margin and the exchange liquidates (everything is gone).
Funding is paid hour by hour on the notional (longs pay when the rate is positive). Entry at the hour's open, as a maker.
If one hour touches both the target and the liquidation price, the throw counts as lost. One throw starts every day at
00:00 UTC; chains of throws, one after the other, start every Monday.
"""
import json, sys
from pathlib import Path

import numpy as np

D = Path(sys.argv[1]) / "BTC"
BARS = json.loads((D / "perp_1h.json").read_text())
T = np.array([b[0] for b in BARS])
O, H, L_, C = (np.array([b[i] for b in BARS], float) for i in (1, 2, 3, 4))
_f = json.loads((D / "funding_1h.json").read_text())
FT = sorted(int(k) for k in _f)
FR = {int(k): v for k, v in _f.items()}
FUND = np.array([FR.get(int(t), 0.0) for t in T])  # hourly rate at each bar's start; zero before Deribit's history


def throw(i, lev, mm, side):
    """From bar i: (won, bars held), or None if the data ends first."""
    p0, n, paid = O[i], lev, 0.0
    for j in range(i, len(T)):
        up = p0 * (1 + side * (1 + paid) / n) if side > 0 else p0 * (1 - (1 + paid) / n)
        dn_move = (1 - paid - mm * n) / n
        if dn_move <= 0:
            return False, j - i
        dn = p0 * (1 - dn_move) if side > 0 else p0 * (1 + dn_move)
        hit_up = H[j] >= up if side > 0 else L_[j] <= up
        hit_dn = L_[j] <= dn if side > 0 else H[j] >= dn
        if hit_dn:
            return False, j - i + 1  # also when both are touched in the same hour
        if hit_up:
            return True, j - i + 1
        paid += side * FUND[j] * n * C[j] / p0  # longs pay a positive rate, shorts receive it
    return None


def daily_starts():
    return [i for i in range(len(T)) if (T[i] // 3600000) % 24 == 0]


def weekly_starts():
    return [i for i in daily_starts() if ((T[i] // 86400000) + 3) % 7 == 0]  # 1970-01-01 was a Thursday


def chain(i, lev, mm, side, cap=11):
    wins = 0
    while wins < cap:
        r = throw(i, lev, mm, side)
        if r is None:
            return None
        ok, held = r
        if not ok:
            return wins
        wins += 1
        i += held
        if i >= len(T):
            return None
    return wins


if __name__ == "__main__":
    days, weeks = daily_starts(), weekly_starts()
    print(f"{len(T)} ore, {len(days)} lanci giornalieri, {len(weeks)} catene settimanali")
    print(f"{'leva':>4} {'mant.':>6} {'lato':>5} | {'p lancio':>8} {'durata mediana':>14} | {'p^11':>10} | catene: {'≥1':>5} {'≥3':>5} {'≥5':>5} {'≥8':>5} {'11':>3} {'max':>4}")
    for lev in (5, 10, 20, 40, 50):
        for mm in (0.005, 0.0125):
            if mm * lev >= 1:
                continue
            for side, name in ((1, "long"), (-1, "short")):
                res = [throw(i, lev, mm, side) for i in days]
                res = [r for r in res if r is not None]
                p = np.mean([r[0] for r in res])
                med = np.median([r[1] for r in res])
                ch = [chain(i, lev, mm, side) for i in weeks]
                ch = np.array([c for c in ch if c is not None])
                dur = f"{med / 24:.1f} giorni" if med >= 48 else f"{med:.0f} ore"
                print(f"{lev:>3}x {mm:6.2%} {name:>5} | {p:8.1%} {dur:>14} | 1 su {1 / p ** 11:>5.0f} | {np.mean(ch >= 1):6.0%}{np.mean(ch >= 3):6.0%}{np.mean(ch >= 5):6.1%}{np.mean(ch >= 8):6.1%}{int((ch >= 11).sum()):>4}{ch.max():>5}")
