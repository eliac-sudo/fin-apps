"""Who is long and who is short, against each group's own last three years. It describes, it isn't tested as a signal, and it isn't advice.

Two groups on each market:
  crypto  retail is the long share of all accounts on Binance and Bybit futures, where each account counts once whatever its size.
          The big side is the long share of top traders' positions, Binance's top 20% of accounts by margin. Daily, from December 2021.
  others  retail is the COT "nonreportable" group, positions under the CFTC's reporting limit. The big side is leveraged funds, or managed
          money on commodities. Net position as a share of open interest. Weekly, measured on Tuesday and published days later.

The tab reads the level: where today's position sits among the last three years of the same group, from 0 to 100. On the COT
this is the usual "COT index". Above 90 the group is more long than almost ever lately, below 10 more short.

The change tables below the levels (crypto_table, cot_table, pressures) are what the frozen test v3 used for F1 and F2: they
stay as they were, so that test can be rerun on the same code. Neither reading beat random entries.
"""
import threading, time

import numpy as np
import pandas as pd

from . import indicators as I
from . import technicals as K
from . import thermo as Z
from . import zones as ZN
from .events import read
from .history import CRYPTO, safe

WINDOW = {"4h": 6, "1d": 3, "1w": 1}  # bars over which the change is measured: one day, three days, one report
INTENSITY_MIN = 50  # chosen by judgment, not tested: the top and bottom quarter of a group's own past
BEYOND_MIN = 100  # bars before the slope against price is trusted
BEYOND_BARS = {"4h": 540, "1d": 180, "1w": 104}  # 90 days, 6 months, 2 years: chosen because what's left is uncorrelated with price on BTC, ETH, gold and the S&P, without looking at returns
CACHE_SECONDS = 600
_lock, _level_cache = threading.Lock(), {}


def pressure_of(flow):
    """From -100 to +100, against the group's own earlier changes only, so the past never changes."""
    return 2 * I.past_percentile(flow.dropna()).reindex(flow.index) - 100


def state_of(score):
    return "dip" if score <= ZN.BYZ_BELOW else "top" if score >= ZN.SZT_ABOVE else None


def _time_index(d):
    return d.assign(t=pd.to_datetime(d.t, utc=True, format="ISO8601")).set_index("t").sort_index()


def crypto_table(asset, tf):
    p, frames = read("positions", asset), K.frames(asset)
    if p is None or tf not in frames:
        return None
    bybit, taker = read("positions", f"{asset}_bybit"), read("positions", f"{asset}_taker")
    p, w = _time_index(p), WINDOW[tf]
    daily = tf == "1d"
    p = p.groupby(p.index.normalize()).last() if daily else p
    d = frames[tf].copy()
    d.index = pd.to_datetime(d.index, utc=True)
    if daily:
        d.index = d.index.normalize()
    score = ZN.indicator_score(frames[tf], tf)[0]
    score.index = d.index
    binance = p.retail_long.diff(w)
    x = pd.DataFrame({"retail_flow": binance, "big_flow": p.big_long.diff(w), "oi_change": p.oi.pct_change(w, fill_method=None) * 100})
    if bybit is not None:
        b = _time_index(bybit).bybit_long
        b = (b.groupby(b.index.normalize()).last() if daily else b).reindex(x.index).diff(w)
        x["bybit_flow"] = b
        x["retail_flow"] = pd.concat([binance, b], axis=1).mean(axis=1, skipna=True).where(binance.notna())  # one vote each where both exist
    if taker is not None:
        m = _time_index(taker).fillna(0)
        m = (m.groupby(m.index.normalize()).sum() if daily else m).rolling(w).sum().reindex(x.index)
        x["spot_net"], x["perp_net"] = 2 * m.spot_buy - m.spot_vol, 2 * m.perp_buy - m.perp_vol
        x["money_flow"] = (x.spot_net + x.perp_net) / (m.spot_vol + m.perp_vol).where(lambda v: v > 0)
    return x.assign(close=d.close.reindex(x.index), score=score.reindex(x.index)).dropna(subset=["close", "retail_flow", "big_flow"])


def cot_table(market):
    c, frames = read("positions", safe(market)), K.frames(market)
    if c is None or "1d" not in frames:
        return None
    c = c.dropna(subset=["big_long", "big_short"]).assign(date=lambda z: pd.to_datetime(z.report_date, utc=True)).set_index("date").sort_index()
    if c.empty:
        return None
    sign = -1 if market in Z.COT_AGAINST_PAIR else 1  # the futures are on the foreign currency, so buying them is selling the pair
    change = lambda col: (c[col] / c.oi).diff()
    long_side, short_side = {"small": "small_long", "big": "big_long"}, {"small": "small_short", "big": "big_short"}
    if sign < 0:  # long the currency is short the pair
        long_side, short_side = short_side, long_side
    x = pd.DataFrame({"retail_flow": change(long_side["small"]) - change(short_side["small"]), "big_flow": change(long_side["big"]) - change(short_side["big"]),
                      "retail_long_change": change(long_side["small"]), "retail_short_change": change(short_side["small"]), "big_long_change": change(long_side["big"]), "big_short_change": change(short_side["big"]),
                      "oi_change": c.oi.pct_change(fill_method=None) * 100, "available": c.available})
    d = frames["1d"]
    score = ZN.indicator_score(d, "1d")[0]
    idx = pd.to_datetime(d.index, utc=True)
    close, score = pd.Series(d.close.values, index=idx), pd.Series(score.values, index=idx)
    tol = pd.Timedelta(days=5)
    x = x.assign(close=close.reindex(x.index, method="ffill", tolerance=tol), score=score.reindex(x.index, method="ffill", tolerance=tol)).dropna(subset=["close", "retail_flow", "big_flow"])
    x.attrs["latest"] = {"close": float(close.dropna().iloc[-1]), "score": None if pd.isna(score.iloc[-1]) else float(score.iloc[-1])}
    return x


def beyond_move(flow, move, bars=180):
    """The flow minus what the price move alone would predict, as pressure. The slope uses earlier bars only, and a rolling window because the reflex changes over time."""
    f, m = flow.where(move.notna()), move.where(flow.notna())
    mean = lambda v: v.rolling(bars, min_periods=BEYOND_MIN).mean()
    slope = ((mean(f * m) - mean(f) * mean(m)) / (mean(m * m) - mean(m) ** 2)).shift(1)
    return pressure_of(f - slope * m)


def pressures(x, tf):
    move = x.close.pct_change(1 if tf == "1w" else WINDOW[tf], fill_method=None)
    y = x.assign(retail=pressure_of(x.retail_flow), big=pressure_of(x.big_flow), retail_beyond=beyond_move(x.retail_flow, move, BEYOND_BARS[tf]), big_beyond=beyond_move(x.big_flow, move, BEYOND_BARS[tf]),
                 state=[state_of(s) if pd.notna(s) else None for s in x.score])
    if "money_flow" in x:
        y["money"] = pressure_of(x.money_flow)
    y.attrs = x.attrs
    return y


def stamp(t, tf):
    return t.strftime("%Y-%m-%d %H:%M") if tf == "4h" else t.strftime("%Y-%m-%d")


def series(values):
    return [None if np.isnan(v) else float(v) for v in values]


# ---- positioning: where each group stands now against its own last three years

LEVEL_BARS = {"1d": 3 * 365, "1w": 3 * 52}  # three years, the usual window for the COT index
LEVEL_MIN = {"1d": 365, "1w": 104}
LEVEL_CHANGE = {"1d": 3, "1w": 1}  # three days on crypto, one report on the COT
LEVEL_WORDS = ((90, "molto long"), (70, "più long del solito"), (30, "nella norma"), (10, "più short del solito"), (-1, "molto short"))


def level_word(pct):
    return None if pct is None else next(w for limit, w in LEVEL_WORDS if pct >= limit)


def rolling_pct(s, bars, min_bars):
    """Where each value sits among the window ending on it, from 0 to 100. Only that bar and earlier ones."""
    def pct(w):
        last = w[-1]
        return 100 * ((w < last).sum() + .5 * ((w == last).sum() - 1)) / max(len(w) - 1, 1)
    return s.rolling(bars, min_periods=min_bars).apply(pct, raw=True)


def crypto_levels(asset):
    """Daily: retail is the share of accounts long, averaging Binance and Bybit where both exist. The big side is the long share of top traders' positions on Binance."""
    p = read("positions", asset)
    if p is None:
        return None
    p = _time_index(p)
    p = p.groupby(p.index.normalize()).last()
    retail = p.retail_long
    bybit = read("positions", f"{asset}_bybit")
    if bybit is not None:
        b = _time_index(bybit).bybit_long
        b = b.groupby(b.index.normalize()).last().reindex(p.index)
        retail = pd.concat([retail, b], axis=1).mean(axis=1, skipna=True).where(retail.notna())
    d = K.frames(asset).get("1d")
    close = None
    if d is not None:
        close = pd.Series(d.close.values, index=pd.to_datetime(d.index, utc=True).normalize())
        close = close[~close.index.duplicated(keep="last")].reindex(p.index)
    return pd.DataFrame({"retail": retail, "big": p.big_long, "close": close})


def cot_levels(market):
    """Weekly: each group's net position as a share of open interest, signed for the pair as quoted."""
    c = read("positions", safe(market))
    if c is None:
        return None
    c = c.dropna(subset=["big_long", "big_short"]).assign(date=lambda z: pd.to_datetime(z.report_date, utc=True)).set_index("date").sort_index()
    if c.empty:
        return None
    sign = -1 if market in Z.COT_AGAINST_PAIR else 1
    x = pd.DataFrame({"retail": sign * (c.small_long - c.small_short) / c.oi, "big": sign * (c.big_long - c.big_short) / c.oi, "available": c.available})
    d = K.frames(market).get("1d")
    if d is not None:
        close = pd.Series(d.close.values, index=pd.to_datetime(d.index, utc=True))
        x["close"] = close.reindex(x.index, method="ffill", tolerance=pd.Timedelta(days=5))
        x.attrs["latest_close"] = float(close.dropna().iloc[-1])
    return x


def level_table(market):
    tf = "1d" if market in CRYPTO else "1w"
    x = crypto_levels(market) if tf == "1d" else cot_levels(market)
    if x is None or x.retail.dropna().empty:
        return None, tf
    for g in ("retail", "big"):
        x[f"{g}_pct"] = rolling_pct(x[g], LEVEL_BARS[tf], LEVEL_MIN[tf])
    return x, tf


def side_of(pct):
    return 0 if pct is None else 1 if pct >= 70 else -1 if pct <= 30 else 0


def positioning():
    """Every market's levels now, without the history, for the overview."""
    rows = []
    for m in K.all_markets():
        v = level_now(m)
        if v:
            rows.append({"market": m, **{k: x for k, x in v.items() if k != "history"}})
    return rows


def level_now(market):
    """Where retail and the big side stand now, how that changed lately, and whether they disagree. Cached like the rest of the tab."""
    with _lock:
        hit = _level_cache.get(market)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    x, tf = level_table(market)
    out = None
    if x is not None:
        x = x.dropna(subset=["retail", "big"])
        last, back = x.iloc[-1], x.iloc[-1 - LEVEL_CHANGE[tf]] if len(x) > LEVEL_CHANGE[tf] else None
        g = lambda k: {"value": 100 * float(last[k]), "pct": None if pd.isna(last[f"{k}_pct"]) else float(last[f"{k}_pct"]),
                       "word": level_word(None if pd.isna(last[f"{k}_pct"]) else float(last[f"{k}_pct"])),
                       "change": None if back is None else 100 * float(last[k] - back[k]),
                       "pct_change": None if back is None or pd.isna(back[f"{k}_pct"]) or pd.isna(last[f"{k}_pct"]) else float(last[f"{k}_pct"] - back[f"{k}_pct"])}
        r, b = g("retail"), g("big")
        out = {"tf": tf, "date": stamp(x.index[-1], "1d"), "retail": r, "big": b, "split": side_of(r["pct"]) * side_of(b["pct"]) < 0,
               "available": last.get("available") if "available" in x else None}
        if "latest_close" in x.attrs and not pd.isna(last.get("close")):
            out["since_pct"] = 100 * (x.attrs["latest_close"] / float(last.close) - 1)
        shown = x.tail(LEVEL_BARS[tf] * 2)
        out["history"] = {"dates": [stamp(t, "1d") for t in shown.index], "close": series(shown.close.astype(float).values) if "close" in shown else None,
                          "retail": series(shown.retail_pct.values), "big": series(shown.big_pct.values),
                          "retail_value": series(100 * shown.retail.values), "big_value": series(100 * shown.big.values)}
    with _lock:
        _level_cache[market] = (time.time(), out)
    return out
