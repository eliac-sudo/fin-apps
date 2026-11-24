"""Second pass on double or nothing (docs/RADDOPPI.md), three questions left open by the first:

1. Hyperliquid's real costs: maintenance 1.25%, maker 0.015% on entry and on the take-profit.
2. Entering only on the tested momentum signal (bzd/zones.py, test v4): long the day after "sale forte" (score >= +50),
   short the day after "scende forte" (<= -50), instead of every day.
3. Banking part of the money at each doubling, by Monte Carlo on the measured chance of one throw.

    .venv/bin/python scripts/research/double_sim2.py DIR     # DIR as for double_sim.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import double_sim as DS
from bzd import zones as Z


def throw_fee(i, lev, mm, side, fee):
    """As double_sim.throw, with a maker fee on entry and on the take-profit, both on the notional."""
    p0, n = DS.O[i], lev
    paid = fee * n  # entry fee comes off the equity
    for j in range(i, len(DS.T)):
        need = (1 + paid + fee * n) / n  # the exit fee too must be covered by the gain
        up = p0 * (1 + need) if side > 0 else p0 * (1 - need)
        dn_move = (1 - paid - mm * n) / n
        if dn_move <= 0:
            return False, j - i
        dn = p0 * (1 - dn_move) if side > 0 else p0 * (1 + dn_move)
        if (DS.L_[j] <= dn) if side > 0 else (DS.H[j] >= dn):
            return False, j - i + 1
        if (DS.H[j] >= up) if side > 0 else (DS.L_[j] <= up):
            return True, j - i + 1
        paid += side * DS.FUND[j] * n * DS.C[j] / p0
    return None


def p_of(starts, lev, mm, side, fee=0.0):
    res = [throw_fee(i, lev, mm, side, fee) for i in starts]
    res = [r for r in res if r is not None]
    return (np.mean([r[0] for r in res]) if res else float("nan")), len(res)


def momentum_starts():
    """Bars at 00:00 UTC the day after a daily close with momentum score >= +50 (long) or <= -50 (short)."""
    idx = pd.to_datetime(DS.T, unit="ms", utc=True)
    h = pd.DataFrame({"open": DS.O, "high": DS.H, "low": DS.L_, "close": DS.C}, index=idx)
    d = h.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    score, _ = Z.indicator_score(d, "1d")
    pos = {t: i for i, t in enumerate(idx)}
    longs, shorts = [], []
    for day, s in score.dropna().items():
        nxt = pos.get(day + pd.Timedelta(days=1))
        if nxt is None:
            continue
        if s >= Z.SZT_ABOVE:
            longs.append(nxt)
        elif s <= Z.BYZ_BELOW:
            shorts.append(nxt)
    return longs, shorts


def bank_mc(p, bank, throws=11, n=1_000_000, seed=7):
    """Start with 1 at stake. After each win the stake doubles and `bank` of it is put aside for good. Stops at the first
    loss or after `throws` wins. Returns the money taken home in units of the first stake."""
    rng = np.random.default_rng(seed)
    wins = rng.random((n, throws)) < p
    streak = np.where(wins.all(axis=1), throws, wins.argmin(axis=1))
    home = np.zeros(n)
    for k in range(1, throws + 1):  # after win k: stake was s, becomes 2s, bank*2s goes home
        stake_before = ((2 * (1 - bank)) ** (k - 1))
        home += np.where(streak >= k, bank * 2 * stake_before, 0.0)
    home += np.where(streak == throws, (2 * (1 - bank)) ** throws * (1 if bank < 1 else 0), 0.0)  # the stake left after the last win
    return home


if __name__ == "__main__":
    days = DS.daily_starts()
    print("1. Hyperliquid: mantenimento 1,25%, maker 0,015% su entrata e uscita")
    for lev in (5, 10, 20, 40):
        pl, _ = p_of(days, lev, .0125, 1, .00015)
        ps, _ = p_of(days, lev, .0125, -1, .00015)
        m = (pl + ps) / 2
        print(f"   {lev:>2}x  long {pl:.1%}  short {ps:.1%}  media {m:.1%}  11 di fila 1 su {1 / m ** 11:,.0f}")

    print("\n2. Solo dopo il segnale di momentum (Deribit: mantenimento 0,5%, maker 0)")
    longs, shorts = momentum_starts()
    print(f"   giorni con segnale: {len(longs)} sale forte, {len(shorts)} scende forte")
    for lev in (5, 10, 20):
        pl, nl = p_of(longs, lev, .005, 1)
        ps, ns = p_of(shorts, lev, .005, -1)
        bl, _ = p_of(days, lev, .005, 1)
        bs, _ = p_of(days, lev, .005, -1)
        both = (pl * nl + ps * ns) / (nl + ns)
        base = (bl * nl + bs * ns) / (nl + ns)  # every day, same mix of sides
        print(f"   {lev:>2}x  long dopo sale forte {pl:.1%} (ogni giorno {bl:.1%}) | short dopo scende forte {ps:.1%} (ogni giorno {bs:.1%}) | insieme {both:.1%} contro {base:.1%}")

    print("\n3. Incassare per strada (Monte Carlo, 1 milione di tentativi, 11 lanci al massimo)")
    for p in (0.49, 0.476):
        print(f"   probabilità di un lancio {p:.1%}")
        for bank in (0.0, 0.25, 0.5):
            home = bank_mc(p, bank)
            print(f"     metti da parte {bank:>4.0%} a ogni raddoppio: torni a casa con qualcosa {np.mean(home > 0):6.1%}, almeno la posta {np.mean(home >= 1):6.1%}, "
                  f"almeno 10 volte {np.mean(home >= 10):6.2%}, almeno 100 volte {np.mean(home >= 100):7.3%}, in media {np.mean(home):.2f} volte la posta")
