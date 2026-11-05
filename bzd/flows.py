"""Who buys the dip and who sells the top, and how hard. It describes, it isn't tested as a signal, and it isn't advice.

Two groups on each market, as positions change:
  crypto  retail is the long share of all accounts on Binance and Bybit futures, where each account counts once whatever its size.
          The big side is the long share of top traders' positions, Binance's top 20% of accounts by margin.
          Money is separate: dollars bought minus sold by whoever crossed the spread, on Binance spot and futures. It says which way money pushed, not who pushed it.
  others  retail is the COT "nonreportable" group, positions under the CFTC's reporting limit. The big side is leveraged funds, or managed money on commodities.
          These are contracts, so size counts. Weekly, measured on Tuesday and published days later.

A dip or a top is the BYZ or SZT zone on price indicators alone (`zones.indicator_score`), so there's one definition across the app.
Pressure is where a group's change in position sits among its own earlier changes, from -100 to +100: +90 means more buying than 95% of its past.
Intensity is its size. A group buys or sells only from INTENSITY_MIN up: smaller moves are normal noise.

Two more readings keep this honest:
  beyond  retail moves against price almost by reflex, so the same pressure is measured after removing what the price move alone would predict.
  how     whether a group opened or closed. The COT reports longs and shorts apart, so there it's a fact. On crypto it's inferred from open interest, for the whole market.
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
SHOWN_BARS = {"4h": 540, "1d": 1900, "1w": 522}  # 90 days, all the crypto files, 10 years
INTENSITY_MIN = 50  # chosen by judgment, not tested: the top and bottom quarter of a group's own past
WORDS = ((95, "estrema"), (80, "forte"), (50, "moderata"), (0, "debole"))
MERGE_BARS = 3
BEYOND_MIN = 100  # bars before the slope against price is trusted
BEYOND_BARS = {"4h": 540, "1d": 180, "1w": 104}  # 90 days, 6 months, 2 years: chosen because what's left is uncorrelated with price on BTC, ETH, gold and the S&P, without looking at returns
OI_CLEAR = .5  # % change in open interest below which nobody can say if the market opened or closed
CACHE_SECONDS = 600
_lock, _cache = threading.Lock(), {}


def word(intensity):
    return next(w for limit, w in WORDS if intensity >= limit)


def action(pressure):
    if pressure is None or np.isnan(pressure):
        return None
    return "compra" if pressure >= INTENSITY_MIN else "vende" if pressure <= -INTENSITY_MIN else "fermo"


def pressure_of(flow):
    """From -100 to +100, against the group's own earlier changes only, so the past never changes."""
    return 2 * I.past_percentile(flow.dropna()).reindex(flow.index) - 100


def state_of(score):
    return "dip" if score <= ZN.BYZ_BELOW else "top" if score >= ZN.SZT_ABOVE else None


def _join(names):
    return " e ".join(names)


def verdict(state, retail, big, big_name):
    """One sentence on who acts at the extreme. Without an extreme there's nothing to say."""
    if not state:
        return None
    acts = {"compra": [], "vende": []}
    for name, a in (("il retail", retail), (big_name, big)):
        if a in acts:
            acts[a].append(name)
    plural = lambda names, one, many: one if names == ["il retail"] else many
    parts = []
    if acts["compra"]:
        parts.append(f"{plural(acts['compra'], 'compra', 'comprano')} {_join(acts['compra'])}")
    if acts["vende"]:
        parts.append(f"{plural(acts['vende'], 'vende', 'vendono')} {_join(acts['vende'])}")
    head = "Sul dip" if state == "dip" else "Sul top"
    return f"{head} {', '.join(parts)}." if parts else f"{head} nessuno si muove più del solito."


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


def how_of(act, long_change, short_change):
    """Opened or closed, from the two sides of a report."""
    if act == "compra":
        return "apre long" if long_change >= -short_change else "chiude short"
    if act == "vende":
        return "apre short" if short_change >= -long_change else "chiude long"
    return None


def how_from_oi(act, oi_change):
    """Inferred: with open interest clearly up the market is opening, clearly down it's closing."""
    if act not in ("compra", "vende") or oi_change is None or np.isnan(oi_change) or abs(oi_change) < OI_CLEAR:
        return None
    if oi_change > 0:
        return "apre long" if act == "compra" else "apre short"
    return "chiude short" if act == "compra" else "chiude long"


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


def habit(x):
    """How often each group acted the usual way at past extremes: a description of the group, not of what happened next."""
    out = {}
    for state, act in (("dip", "compra"), ("top", "vende")):
        bars = x[(x.state == state) & x.retail.notna() & x.big.notna()]
        n = len(bars)
        share = lambda col: None if not n else float((bars[col].map(action) == act).mean() * 100)
        out[state] = {"bars": n, "retail": share("retail"), "big": share("big")}
        if "money" in x:
            out[state]["money"] = share("money")
    return out


def episodes(x, tf, big_name):
    """Runs of extreme bars, each with the strongest pressure of each group in the direction that fits the extreme. A run only uses its own bars."""
    out, last_i = [], None
    bars = x[x.state.notna() & x.retail.notna() & x.big.notna()]
    positions = {t: i for i, t in enumerate(x.index)}
    for t, r in bars.iterrows():
        i = positions[t]
        e = out[-1] if out else None
        if e and e["kind"] == r.state and i - last_i <= MERGE_BARS:
            e["to"], e["bars"] = stamp(t, tf), e["bars"] + 1
        else:
            e = {"from": stamp(t, tf), "to": stamp(t, tf), "kind": r.state, "bars": 1, "retail": r.retail, "big": r.big, "start": float(r.close)}
            out.append(e)
        pick = max if r.state == "dip" else min
        e["retail"], e["big"], e["end"] = float(pick(e["retail"], r.retail)), float(pick(e["big"], r.big)), float(r.close)
        last_i = i
    for e in out:
        e["move"] = 100 * (e["end"] / e["start"] - 1)
        e["verdict"] = verdict(e["kind"], action(e["retail"]), action(e["big"]), big_name)
    return out


def group_now(pressure, flow, beyond=None, how=None, inferred=False):
    v = None if pressure is None or np.isnan(pressure) else float(pressure)
    act = action(v)
    side = 0 if act not in ("compra", "vende") else (1 if act == "compra" else -1)
    over = beyond is not None and not np.isnan(beyond) and side != 0 and side * beyond >= INTENSITY_MIN
    return {"pressure": v, "action": act, "intensity": None if v is None else abs(v), "word": None if v is None else word(abs(v)), "flow": float(flow) * 100,
            "beyond": bool(over), "beyond_pressure": None if beyond is None or np.isnan(beyond) else float(beyond), "how": how, "how_inferred": inferred and how is not None}


def group_at(last, name, oi):
    p, a = last[name], action(last[name])
    if f"{name}_long_change" in last.index and a is not None:
        how, inferred = how_of(a, last[f"{name}_long_change"], last[f"{name}_short_change"]), False
    else:
        how, inferred = how_from_oi(a, oi), True
    return group_now(p, last[f"{name}_flow"], last[f"{name}_beyond"], how, inferred)


def series(values):
    return [None if np.isnan(v) else float(v) for v in values]


def frame_view(x, tf, big_name):
    last = x.iloc[-1]
    state = last.state if isinstance(last.state, str) else None
    oi = None if pd.isna(last.oi_change) else float(last.oi_change)
    r, b = group_at(last, "retail", oi), group_at(last, "big", oi)
    shown = x.tail(SHOWN_BARS[tf])
    now = {"date": stamp(x.index[-1], tf), "state": state, "score": None if pd.isna(last.score) else float(last.score), "retail": r, "big": b, "oi_change": oi,
           "verdict": verdict(state, r["action"], b["action"], big_name), "available": last.get("available")}
    if "money" in x:
        bybit = last.get("bybit_flow")
        now["money"] = {**group_now(last.money, last.money_flow), "spot": float(last.spot_net), "perp": float(last.perp_net)}
        now["bybit_flow"] = None if bybit is None or np.isnan(bybit) else float(bybit) * 100
    latest = x.attrs.get("latest")
    if latest:  # a report is old by the time it's read, so say what the price did since
        now["since_pct"] = 100 * (latest["close"] / float(last.close) - 1)
        now["state_today"] = state_of(latest["score"]) if latest["score"] is not None else None
    out = {"now": now, "habit": habit(x), "episodes": episodes(x, tf, big_name), "dates": [stamp(t, tf) for t in shown.index], "close": [float(v) for v in shown.close],
           "retail": series(shown.retail), "big": series(shown.big), "retail_beyond": series(shown.retail_beyond), "big_beyond": series(shown.big_beyond), "state": [s if isinstance(s, str) else None for s in shown.state]}
    if "money" in x:
        out["money"] = series(shown.money)
    return out


SOURCE_CRYPTO = ("Il retail è la quota di conti long su Binance e Bybit, dove ogni conto vale uno: conta quanti, non quanto. I grossi sono le posizioni del 20% di conti con più margine su Binance. "
                 "Il denaro sono i dollari comprati meno quelli venduti da chi attraversa lo spread, su spot e futures Binance: dice dove spinge il denaro, non chi spinge. Dati dal dicembre 2021.")
SOURCE_COT = ("Report COT della CFTC, in contratti: il retail sono le posizioni sotto la soglia di segnalazione, e può comprendere piccoli professionisti. I fondi sono i leveraged funds, o il managed money sulle materie prime. "
              "Dal 2006. Misurato di martedì e pubblicato giorni dopo, e una settimana contiene molti movimenti.")


def market_view(market):
    """Every timeframe of a market, kept for a while since the percentiles read the whole history."""
    with _lock:
        hit = _cache.get(market)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    if market in CRYPTO:
        big_name, source, tables = "i grossi", SOURCE_CRYPTO, {tf: crypto_table(market, tf) for tf in ("1d", "4h")}
    else:
        big_name, source, tables = "i fondi", SOURCE_COT, {"1w": cot_table(market)}
    frames = {tf: frame_view(pressures(t, tf), tf, big_name) for tf, t in tables.items() if t is not None and len(t)}
    out = {"market": market, "big_label": big_name[2:].capitalize(), "source": source, "frames": frames, "main": next(iter(frames), None)} if frames else None
    with _lock:
        _cache[market] = (time.time(), out)
    return out


def overview():
    """Where each market stands now, on its main timeframe, for the table."""
    rows = []
    for m in K.all_markets():
        v = market_view(m)
        if v:
            f = v["frames"][v["main"]]
            rows.append({"market": m, "tf": v["main"], "big_label": v["big_label"], **f["now"], "habit": f["habit"]})
    return rows
