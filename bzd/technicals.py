"""Technical analysis per market and timeframe, computed from stored prices. It describes, and none of it is tested as a signal.

A reset is the RSI back at an extreme while the slow trend holds: oversold in a rise, overbought in a fall.

Support and resistance are drawn by code: swing highs and lows that repeat at about the same price form a level, and more touches mean a
stronger level. A swing needs bars on both sides to be confirmed, so the newest bars can't form one yet.

Levels are built to stay put. Their width and the size a swing must have come from the median ATR of the window, so one violent bar moves
nothing. Each timeframe also inherits the swings of the slower ones and keeps their price, so a weekly level is the same line on the daily chart.
"""
import numpy as np
import pandas as pd

from . import indicators as I
from .events import daily, read
from .history import CRYPTO, MARKETS, safe

FRAMES = {"4h": {"bars": 360, "swing": 5}, "1d": {"bars": 400, "swing": 5}, "1w": {"bars": 200, "swing": 3}, "1M": {"bars": 120, "swing": 2}}
LEVEL_WIDTH_ATR = .25  # swings closer than this are one level
SWING_SIZE_ATR = 1.0  # a swing smaller than this is noise
FRAME_ORDER = ("4h", "1d", "1w", "1M")
LEVELS_PER_SIDE, LEVEL_CANDIDATES = 3, 6
CHART_BARS = 140
TREND_BARS = 10
RESET_RSI = {"1M": 40, "1w": 40, "1d": 30}  # about 1.3 alerts a week across 30 markets; 30 on weekly and monthly would almost never fire. Chosen for frequency, not tested
APP_RESET_RSI = {**RESET_RSI, "4h": 30}
MAX_STALE_DAYS = 4
TREND_IT = {"rialzo": "in rialzo", "ribasso": "in ribasso", "laterale": "laterale"}
FRAME_IT = {"4h": "4 ore", "1d": "giornaliero", "1w": "settimanale", "1M": "mensile"}


def daily_ohlc(market):
    """Daily bars. Crypto is built from the 4h bars, so today's high and low are included."""
    if market in CRYPTO:
        d = four_hour(market)
        return None if d is None else d.groupby(d.index.floor("D")).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
    x = read("tradfi", safe(market))
    if x is None:
        return None
    d = daily(x)[["open", "high", "low", "close"]].dropna()
    return d[d.low > 0]


def four_hour(market):
    x = read("crypto", f"{market}_candles_4h")
    if x is None:
        return None
    x = x.assign(t=pd.to_datetime(x.t, utc=True, format="ISO8601")).set_index("t").sort_index()
    return x[~x.index.duplicated()][["open", "high", "low", "close"]].dropna()


def resample(d, rule):
    return d.resample(rule, label="left", closed="left" if rule != "W-SUN" else "right").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def frames(market):
    """Every timeframe with data. Other markets have no 4h history, only daily and above."""
    d = daily_ohlc(market)
    if d is None or d.empty:
        return {}
    out = {"1d": d, "1w": resample(d, "W-SUN"), "1M": resample(d, "MS")}
    if market in CRYPTO:
        out["4h"] = four_hour(market)
    return {k: out[k] for k in FRAMES if k in out}


def atr(d, n=14):
    prev = d.close.shift()
    return pd.concat([d.high - d.low, (d.high - prev).abs(), (d.low - prev).abs()], axis=1).max(axis=1).rolling(n).mean()


def swings(d, k, size=0.0):
    """Confirmed swing highs and lows as (bar position, price). With `size`, the price must also have moved that much on both sides of the swing."""
    hi, lo, out = d.high.values, d.low.values, []
    for i in range(k, len(d) - k):
        if hi[i] == hi[i - k:i + k + 1].max() and hi[i] - lo[i - k:i].min() >= size and hi[i] - lo[i + 1:i + k + 1].min() >= size:
            out.append((i, float(hi[i])))
        if lo[i] == lo[i - k:i + k + 1].min() and hi[i - k:i].max() - lo[i] >= size and hi[i + 1:i + k + 1].max() - lo[i] >= size:
            out.append((i, float(lo[i])))
    return out


def find_levels(d, k, width):
    """Swings at about the same price, as one level each, with how many times the price turned there."""
    groups = []
    for i, p in sorted(swings(d, k), key=lambda x: x[1]):
        if groups and p - np.mean([x[1] for x in groups[-1]]) <= width:
            groups[-1].append((i, p))
        else:
            groups.append([(i, p)])
    return [{"price": float(np.mean([x[1] for x in g])), "touches": len(g), "last": d.index[max(x[0] for x in g)].strftime("%Y-%m-%d")} for g in groups if len(g) >= 2]


def typical_atr(d, tf):
    """The median ATR of the window: unlike the last bar's, it barely moves when one bar goes wild."""
    a = atr(d).tail(FRAMES[tf]["bars"]).dropna()
    return float(a.median()) if len(a) else None


def swing_pool(all_frames):
    """Every timeframe's swings and level width, so that all of them can share one set of prices."""
    pool = {}
    for tf, d in all_frames.items():
        size = typical_atr(d, tf)
        if size and tf in FRAMES:
            w = d.tail(FRAMES[tf]["bars"])
            pool[tf] = {"width": LEVEL_WIDTH_ATR * size, "swings": [(p, w.index[i].strftime("%Y-%m-%d")) for i, p in swings(w, FRAMES[tf]["swing"], SWING_SIZE_ATR * size)]}
    return pool


def shared_levels(pool, tf):
    """Levels for one timeframe, built from the slowest down. A level found on a slow timeframe keeps its price on every faster one; a faster swing near it only adds a touch."""
    rank, levels = FRAME_ORDER.index(tf), []
    for f in sorted((x for x in pool if FRAME_ORDER.index(x) >= rank), key=FRAME_ORDER.index, reverse=True):
        groups, width = [], pool[f]["width"]
        for price, last in sorted(pool[f]["swings"]):
            if groups and price - groups[-1][0][0] <= width:
                groups[-1].append((price, last))
            else:
                groups.append([(price, last)])
        for g in groups:
            price, last = float(np.mean([x[0] for x in g])), max(x[1] for x in g)
            known = min(levels, key=lambda x: abs(x["price"] - price), default=None)
            if known and abs(known["price"] - price) <= width:
                known.update(touches=max(known["touches"], len(g)), last=max(known["last"], last))
            else:
                levels.append({"price": price, "touches": len(g), "last": last, "frame": f})
    return levels


def pick_levels(levels, px, tf):
    """The nearest level on each side, then the strongest of the next few, so a small move doesn't reshuffle the list. A lone swing counts only from a slower timeframe, or where a side would be empty."""
    rank = FRAME_ORDER.index(tf)
    solid = lambda x: x["touches"] >= 2 or FRAME_ORDER.index(x["frame"]) > rank
    strength = lambda x: (FRAME_ORDER.index(x["frame"]) + x["touches"], x["touches"])

    def side(rows):
        near = [x for x in rows if solid(x)][:LEVEL_CANDIDATES] or rows[:1]
        return near[:1] + sorted(near[1:], key=strength, reverse=True)[:LEVELS_PER_SIDE - 1]
    below = side(sorted((x for x in levels if x["price"] < px), key=lambda x: -x["price"]))
    above = side(sorted((x for x in levels if x["price"] >= px), key=lambda x: x["price"]))
    return sorted(below, key=lambda x: -x["price"]), sorted(above, key=lambda x: x["price"])


def trend_of(close, ema20, sma50):
    if any(pd.isna(x) for x in (close, ema20, sma50)):
        return "n.d."
    return "rialzo" if close > ema20 > sma50 else "ribasso" if close < ema20 < sma50 else "laterale"


def read_frame(d, tf, pool=None):
    """Indicators and levels for one timeframe."""
    c = d.close  # averages use all the history, so a 200-bar average exists across the whole chart
    ema20, sma50, sma200 = c.ewm(span=20, adjust=False, min_periods=20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    a, rs = atr(d), I.rsi(c)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    px, width = float(c.iloc[-1]), float(a.iloc[-1]) if a.notna().any() else None
    below, above = pick_levels(shared_levels(swing_pool({tf: d}) if pool is None else pool, tf), px, tf)
    bb = (px - mid.iloc[-1]) / (2 * sd.iloc[-1]) if sd.iloc[-1] else None
    tail = d.tail(CHART_BARS)
    series = lambda s: [None if pd.isna(x) else float(x) for x in s.reindex(tail.index).values]
    slow = long_trend(c).iloc[-1]
    low = APP_RESET_RSI[tf]
    in_reset = "ipervenduto" if slow == "rialzo" and rs.iloc[-1] < low else "ipercomprato" if slow == "ribasso" and rs.iloc[-1] > 100 - low else None
    hist = macd - signal
    metric = lambda x: None if pd.isna(x.iloc[-1]) else float(x.iloc[-1])
    metrics = {"rsi": metric(rs), "macd": metric(100 * hist / c), "dist20": metric(100 * (c / ema20 - 1)), "dist50": metric(100 * (c / sma50 - 1)), "dist200": metric(100 * (c / sma200 - 1)),
               "atr": metric(100 * atr(d) / c), "bollinger": metric((c - mid) / (2 * sd.where(sd > 0)))}
    return {"tf": tf, "price": px, "bar": d.index[-1].isoformat(), "metrics": metrics, "trend": trend_of(px, ema20.iloc[-1], sma50.iloc[-1]), "slow_trend": slow if isinstance(slow, str) else None, "reset": in_reset, "reset_low": low, "rsi": rs.iloc[-1], "ema20": ema20.iloc[-1], "sma50": sma50.iloc[-1],
            "sma200": sma200.iloc[-1], "macd_hist": float(macd.iloc[-1] - signal.iloc[-1]), "macd_rising": bool(macd.iloc[-1] - signal.iloc[-1] > macd.iloc[-2] - signal.iloc[-2]) if len(d) > 2 else None,
            "atr_pct": 100 * width / px if width else None, "bollinger": bb, "supports": below, "resistances": above,
            "chart": {"t": [x.strftime("%Y-%m-%d %H:%M" if tf == "4h" else "%Y-%m-%d") for x in tail.index], "o": tail.open.tolist(), "h": tail.high.tolist(), "l": tail.low.tolist(), "c": tail.close.tolist(),
                      "ema20": series(ema20), "sma50": series(sma50), "sma200": series(sma200), "rsi": series(rs)}}


def analyze(market):
    f = frames(market)
    pool = swing_pool(f)
    return {tf: read_frame(d, tf, pool) for tf, d in f.items() if len(d) >= 30}


def summary(market, full=None):
    """One row for the table: trend per timeframe, and the nearest levels on the weekly."""
    a = full if full is not None else analyze(market)
    wk = a.get("1w") or {}
    return {"market": market, "trend": {tf: a[tf]["trend"] for tf in a}, "rsi": {tf: a[tf]["rsi"] for tf in a}, "reset": {tf: a[tf]["reset"] for tf in a}, "metrics": {tf: a[tf]["metrics"] for tf in a}, "slow": {tf: a[tf]["slow_trend"] for tf in a}, "price": (a.get("1d") or {}).get("price"),
            "support": (wk.get("supports") or [None])[0], "resistance": (wk.get("resistances") or [None])[0]}


def long_trend(close):
    """The slow trend: is the 50-bar average rising? The price itself can sit below it during a reset, so the price can't decide this."""
    avg = close.rolling(50).mean()
    return (avg > avg.shift(TREND_BARS)).map({True: "rialzo", False: "ribasso"}).where(avg.shift(TREND_BARS).notna() & (avg != avg.shift(TREND_BARS)))


def reset_state(close, tf):
    """(RSI now, RSI before, slow trend before, threshold in a rise, threshold in a fall), or None without enough data."""
    if tf not in RESET_RSI or len(close) < 60:
        return None
    rs, trend = I.rsi(close), long_trend(close)
    return float(rs.iloc[-1]), float(rs.iloc[-2]), trend.iloc[-2], RESET_RSI[tf], 100 - RESET_RSI[tf]


def find_reset(market, tf, close, fired):
    """A reset is the RSI falling to its low in a slow rise, or climbing to its high in a slow fall. `fired` remembers it until the RSI is back at 50, so one reset is one alert."""
    state = reset_state(close, tf)
    if not state:
        return None
    now, before, trend, low, high = state
    up, down = f"{market}|{tf}|up", f"{market}|{tf}|down"
    if now >= 50:
        fired.pop(up, None)
    if now <= 50:
        fired.pop(down, None)
    if trend == "rialzo" and before >= low > now and up not in fired:
        key, kind = up, "ipervenduto in un trend al rialzo"
    elif trend == "ribasso" and before <= high < now and down not in fired:
        key, kind = down, "ipercomprato in un trend al ribasso"
    else:
        return None
    fired[key] = float(close.index[-1].timestamp())
    return {"market": market, "tf": tf, "rsi": now, "threshold": low if trend == "rialzo" else high, "trend": trend, "kind": kind, "price": float(close.iloc[-1]), "bar": close.index[-1].isoformat()}


def all_markets():
    return [*CRYPTO, *MARKETS]


def check_resets(st, now):
    """New resets on the timeframes that go to the bot. 4h stays in the app."""
    fired, found = st.setdefault("reset_fired", {}), []
    for m in all_markets():
        f = frames(m)
        if "1d" not in f or (now - f["1d"].index[-1].to_pydatetime()).days > MAX_STALE_DAYS:
            continue
        for tf in RESET_RSI:
            if tf in f:
                r = find_reset(m, tf, f[tf].close, fired)
                if r:
                    found.append(r)
    return found


def price_text(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:.4f}" if x >= 1 else f"{x:.6f}"


SAME_INSTRUMENT = 0.15  # a live price this close to the last close is the same instrument; further off it's a proxy, such as TLT for the bond future


def context_line(market, live=None):
    """The picture around an alert: trend and nearest weekly levels. Empty if the data can't say, so it never holds an alert back.

    With a live price of the same instrument, levels are measured from it: after a big move the last close is stale, and a support
    can already be broken. A proxy's price can't be compared with the future's levels, so those stay measured from the last close.
    """
    try:
        a = analyze(market)
    except Exception:
        return ""
    wk, dy = a.get("1w"), a.get("1d")
    if not wk or not dy:
        return ""
    px, label = dy["price"], "Livelli settimanali"
    if live and abs(live / px - 1) < SAME_INSTRUMENT:
        px = live
    elif live:
        label += f" del future (dalla chiusura a {price_text(px)})"
    level = lambda lv: f"{price_text(lv['price'])} ({100 * (lv['price'] / px - 1):+.1f}%)"
    sup = [lv for lv in [*wk["supports"], *wk["resistances"]] if lv["price"] < px]
    res = [lv for lv in [*wk["supports"], *wk["resistances"]] if lv["price"] > px]
    bits = [f"Trend: settimanale {TREND_IT.get(wk['trend'], wk['trend'])}, giornaliero {TREND_IT.get(dy['trend'], dy['trend'])}, RSI giornaliero {dy['rsi']:.0f}"]
    if sup or res:
        bits.append(f"{label}: " + ", ".join(([f"supporto {level(max(sup, key=lambda lv: lv['price']))}"] if sup else ["nessun supporto sotto"]) + ([f"resistenza {level(min(res, key=lambda lv: lv['price']))}"] if res else ["nessuna resistenza sopra"])))
    return "\n".join(f"  {x}" for x in bits)


def format_resets(found, now, name=lambda m: m):
    order = {"1M": 0, "1w": 1, "1d": 2}
    lines = [f"🔄 <b>RESET</b> · {now:%d/%m %H:%M} UTC", "L'RSI è tornato a un estremo mentre il trend di fondo resta quello.", ""]
    for r in sorted(found, key=lambda x: order[x["tf"]]):
        bias = "📈 potenziale long a favore del trend" if r["trend"] == "rialzo" else "📉 potenziale short a favore del trend"
        lines.append(f"• <b>{name(r['market'])}</b> · {FRAME_IT[r['tf']]}: RSI {r['rsi']:.0f} (soglia {r['threshold']}), {r['kind']}. Prezzo {r['price']:,.4g}\n  {bias}")
        context = context_line(r["market"])
        if context:
            lines.append(context)
    lines += ["", "Grafico e livelli sono nell'app, in Analisi tecnica. Soglie scelte da noi: non è testato come segnale e non è consulenza finanziaria."]
    return "\n".join(lines)
