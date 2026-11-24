"""Descriptive indicators and option metrics. Rolling values use data up to each bar only. None of this enters the frozen score."""
import bisect, gzip, json, math, os, re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .recorder import BASE


def rsi(close, n=14):
    """Wilder's RSI."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + up / down)
    return out.where(down != 0, 100.0).where(up.notna())


def sma_distance(close, n):
    """Percent distance of the close from its moving average."""
    return close / close.rolling(n).mean() - 1


def vwap_distance(d, n, volume="volume"):
    """Percent distance of the close from a rolling VWAP, using typical price."""
    typical = (d.high + d.low + d.close) / 3
    v = d[volume].fillna(0)
    denom = v.rolling(n).sum()
    return d.close / ((typical * v).rolling(n).sum() / denom).where(denom > 0) - 1


def past_percentile(s, min_periods=100):
    """Percentile of each value among strictly earlier values, 0 to 100."""
    v, out = s.values.astype(float), np.full(len(s), np.nan)
    hist = []
    for i, x in enumerate(v):
        if not np.isnan(x):
            if len(hist) >= min_periods:
                out[i] = 100 * bisect.bisect_left(hist, x) / len(hist)
            bisect.insort(hist, x)
    return pd.Series(out, index=s.index)


INVERSION_MARGIN = 1.05  # small gaps between two single strikes are noise


def norm_cdf(x):
    return .5 * (1 + math.erf(x / math.sqrt(2)))


def bs_greeks(spot, strike, years, iv, is_call):
    """Black-Scholes delta and gamma, with zero rates. Returns None for unusable inputs."""
    if min(spot, strike, years, iv) <= 0:
        return None
    sq = iv * math.sqrt(years)
    d1 = (math.log(spot / strike) + .5 * iv * iv * years) / sq
    pdf = math.exp(-.5 * d1 * d1) / math.sqrt(2 * math.pi)
    return (norm_cdf(d1) if is_call else norm_cdf(d1) - 1), pdf / (spot * sq)


def option_metrics(rows, spot, now, multiplier):
    """rows: dicts with strike, expiry (datetime), is_call, iv, oi, volume.

    GEX is dollars of gamma per 1% move, with two conventions, because who is long or short is an assumption:
    `gex_call_long` assumes dealers are long calls and short puts; `gex_all_short` assumes they are short everything.
    """
    good = []
    for r in rows:
        years = (r["expiry"] - now).total_seconds() / (365.25 * 86400)
        g = bs_greeks(spot, r["strike"], years, r["iv"], r["is_call"]) if r["iv"] else None
        if g:
            good.append({**r, "days": years * 365.25, "delta": g[0], "gamma": g[1]})
    if not good:
        return None
    unit = sum(x["gamma"] * x["oi"] * multiplier * spot * spot * .01 * (1 if x["is_call"] else -1) for x in good)
    all_short = -sum(x["gamma"] * x["oi"] * multiplier * spot * spot * .01 for x in good)

    def atm_iv(target):
        exps = sorted({x["expiry"] for x in good if x["days"] >= 2}, key=lambda e: abs((e - now).days - target))
        if not exps:
            return None, None
        e = exps[0]
        chain = [x for x in good if x["expiry"] == e]
        return min(chain, key=lambda x: abs(x["strike"] - spot))["iv"], e

    iv30, e30 = atm_iv(30)
    iv7, e7 = atm_iv(7)
    skew = None
    if e30:
        # An option nobody bids for has a made-up IV: on illiquid chains that alone created a false 12-point skew.
        chain = [x for x in good if x["expiry"] == e30 and x.get("bid", 1) > 0]
        puts, calls = [x for x in chain if not x["is_call"]], [x for x in chain if x["is_call"]]
        if puts and calls:
            p = min(puts, key=lambda x: abs(x["delta"] + .25))
            c = min(calls, key=lambda x: abs(x["delta"] - .25))
            if abs(p["delta"] + .25) < .1 and abs(c["delta"] - .25) < .1:
                skew = p["iv"] - c["iv"]
    oi_c, oi_p = sum(x["oi"] for x in good if x["is_call"]), sum(x["oi"] for x in good if not x["is_call"])
    return {"contracts": len(good), "spot": spot, "iv_30d": iv30, "iv_7d": iv7, "term_inverted": bool(iv7 and iv30 and e7 != e30 and iv7 > iv30 * INVERSION_MARGIN),
            "skew_25d": skew, "put_call_oi": oi_p / oi_c if oi_c else None, "gex_call_long": unit, "gex_all_short": all_short}


def parse_cboe(data):
    d, rows = data["data"], []
    symbol = str(d.get("symbol", "")).lstrip("_")
    for o in d["options"]:
        m = re.search(r"^(.*?)(\d{6})([CP])(\d{8})$", o["option"])
        if m and (not symbol or m.group(1) == symbol):  # other roots, such as B1SPY, aren't standard contracts on this underlying
            m = re.search(r"(\d{6})([CP])(\d{8})$", o["option"])
            rows.append({"strike": int(m.group(3)) / 1000, "expiry": datetime.strptime(m.group(1), "%y%m%d").replace(hour=20, tzinfo=timezone.utc), "is_call": m.group(2) == "C",
                         "iv": float(o.get("iv") or 0), "oi": float(o.get("open_interest") or 0), "volume": float(o.get("volume") or 0), "bid": float(o.get("bid") or 0)})
    return rows, float(d["current_price"]), 100


def parse_deribit(data):
    rows, spot = [], None
    for o in data["result"]:
        m = re.match(r"\w+-(\d{1,2}[A-Z]{3}\d{2})-(\d+)-([CP])$", o["instrument_name"])
        if m and o.get("mark_iv"):
            spot = o.get("underlying_price") or o.get("estimated_delivery_price") or spot
            rows.append({"strike": float(m.group(2)), "expiry": datetime.strptime(m.group(1).title(), "%d%b%y").replace(hour=8, tzinfo=timezone.utc), "is_call": m.group(3) == "C",
                         "iv": o["mark_iv"] / 100, "oi": float(o.get("open_interest") or 0), "volume": float(o.get("volume") or 0)})
    return rows, spot, 1


OPTION_SOURCES = {"SPY": ("opt_cboe_spy", parse_cboe), "GLD": ("opt_cboe_gld", parse_cboe), "TLT": ("opt_cboe_tlt", parse_cboe), "USO": ("opt_cboe_uso", parse_cboe), "FXE": ("opt_cboe_fxe", parse_cboe),
                  "BTC": ("opt_deribit_btc", parse_deribit), "ETH": ("opt_deribit_eth", parse_deribit)}


def latest_options(name, root=None):
    """Metrics from the newest saved chain, or None. Time to expiry counts from the snapshot, not from today."""
    job, parse = OPTION_SOURCES[name]
    base = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw" / job
    files = sorted(base.glob("*/*.gz"), key=lambda p: (p.parent.name, p.name))
    if not files:
        return None
    now = datetime.strptime(files[-1].parent.name + files[-1].name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc)
    rows, spot, mult = parse(json.load(gzip.open(files[-1])))
    if not rows or not spot:
        return None
    m = option_metrics(rows, spot, now, mult)
    return {**m, "snapshot": now.isoformat(), "file": str(files[-1].relative_to(base.parent.parent))} if m else None
