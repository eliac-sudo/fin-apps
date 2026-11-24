"""Third pass: does a filter pick the right weeks for DH2m (BTC 25-delta strangle sold as maker, hedged daily)?
Filters fixed before the run:
F1 premium   sell only if ATM implied vol (chosen expiry) > realized vol of the last 30 days
F2 contango  sell only if ATM vol of the nearest expiry with >= 3 days < ATM vol of the chosen expiry
F3 calm      sell only if ATM vol of the chosen expiry < its median over the previous 52 entries
For each: mean P&L of the weeks it sells vs the weeks it skips, and the gap's t (entries overlap about 4 deep).
"""
import json, math, sys
from datetime import timedelta
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import vol_backtest as T
import vol_backtest2 as T2

D = Path(sys.argv[1])


def atm_iv(chain, S):
    near = [o["iv"] for o in chain if abs(o["K"] / S - 1) <= .03 and o["iv"] > 0]
    return float(np.median(near)) if near else None


def features(cur):
    px = json.loads((D / cur / "px0800.json").read_text())
    out = {}
    for f in sorted((D / cur).glob("*.json.gz")):
        snap = T.snapshot(f)
        if not snap:
            continue
        t0, by = snap
        days = {e: (e - t0).total_seconds() / 86400 for e in by}
        cand = [e for e, d in days.items() if 21 <= d <= 45]
        if not cand:
            continue
        exp = min(cand, key=lambda e: abs(days[e] - 30))
        S = by[exp][0]["S"]
        iv30 = atm_iv(by[exp], S)
        shorts = [e for e, d in days.items() if 3 <= d < days[exp]]
        ivs = atm_iv(by[min(shorts, key=lambda e: days[e])], S) if shorts else None
        closes = [px.get((t0 - timedelta(days=k)).strftime("%Y-%m-%d")) for k in range(31)]
        closes = [c for c in closes if c]
        rv = float(np.std(np.diff(np.log(closes[::-1]))) * math.sqrt(365)) if len(closes) > 20 else None
        out[t0] = {"iv": iv30, "ivs": ivs, "rv": rv}
    return out


def gap(a, b):
    a, b = np.array(a), np.array(b)
    if len(a) < 10 or len(b) < 10:
        return float("nan")
    se = math.sqrt(a.var() / (len(a) / 4) + b.var() / (len(b) / 4))
    return (a.mean() - b.mean()) / se


if __name__ == "__main__":
    for cur in sys.argv[2:]:
        tr = [t for t in T2.run(cur) if t["v"] == "DH2m strangle 25Δ coperto, maker"]
        fx = features(cur)
        hist = []
        rows = []
        for t in sorted(tr, key=lambda t: t["t"]):
            f = fx.get(t["t"])
            if not f or f["iv"] is None:
                continue
            med = float(np.median(hist[-52:])) if len(hist) >= 26 else None
            hist.append(f["iv"])
            rows.append({**t, **f, "med": med})
        print(f"\n=== {cur} DH2m, {len(rows)} entrate, medio {np.mean([r['pnl_n'] for r in rows]):.2%} del nozionale")
        tests = {
            "F1 implicita > realizzata": lambda r: r["rv"] is not None and r["iv"] > r["rv"],
            "F2 contango": lambda r: r["ivs"] is not None and r["ivs"] < r["iv"],
            "F3 regime calmo": lambda r: r["med"] is not None and r["iv"] < r["med"],
        }
        need = {"F1 implicita > realizzata": "rv", "F2 contango": "ivs", "F3 regime calmo": "med"}
        for name, rule in tests.items():
            ok = [r for r in rows if r[need[name]] is not None]
            yes = [r["pnl_n"] for r in ok if rule(r)]
            no = [r["pnl_n"] for r in ok if not rule(r)]
            print(f"{name:28} vende {len(yes):3d}: {np.mean(yes):+.2%} | sta fermo {len(no):3d}: {np.mean(no) if no else float('nan'):+.2%} | differenza t {gap(yes, no):+.1f}")
