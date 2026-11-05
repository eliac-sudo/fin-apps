"""The BYZ and SZT tags: how stretched a market is on each timeframe. It describes a state, it isn't tested as a signal, and it isn't advice.

BYZ, Buy Ze dip: the market is stretched downward and the mood is fearful. SZT, Sell Ze Top: stretched upward and the mood is euphoric.
The score runs from -100 to +100. Indicators weigh 70% and sentiment 30%, and without enough texts the indicators count alone, and the tag says so.
"""
import pandas as pd

from . import indicators as I
from . import technicals as K

WEIGHT_INDICATORS, WEIGHT_SENTIMENT = .7, .3
FRAMES = ("4h", "1d", "1w", "1M", "12M")
SETTINGS = {"4h": {"ema": 20, "sma": 50, "range": 180}, "1d": {"ema": 20, "sma": 50, "range": 252}, "1w": {"ema": 20, "sma": 50, "range": 104},
            "1M": {"ema": 12, "sma": 36, "range": 48}, "12M": {"ema": 12, "sma": 60, "range": 12}}
BYZ_BELOW, SZT_ABOVE = -50, 50  # on the indicators alone, about 15% of bars on each side in the past
MIN_SIGNALS = 10
# Theme and sign: good mood about the yen means USD/JPY falls, so the sign flips on pairs quoted the other way round
SENTIMENT_OF = {**{c: ("Cripto", 1) for c in K.CRYPTO}, "ES=F": ("Azioni", 1), "NQ=F": ("Azioni", 1), "RTY=F": ("Azioni", 1), "ZT=F": ("USA", 1), "ZF=F": ("USA", 1), "ZN=F": ("USA", 1), "ZB=F": ("USA", 1),
                "CL=F": ("Energia", 1), "NG=F": ("Energia", 1), "GC=F": ("Metalli preziosi", 1), "SI=F": ("Metalli preziosi", 1), "HG=F": ("Metalli rari e industriali", 1), "ZC=F": ("Agricoli", 1), "ZW=F": ("Agricoli", 1), "ZS=F": ("Agricoli", 1),
                "EURUSD=X": ("Euro", 1), "GBPUSD=X": ("Sterlina", 1), "USDJPY=X": ("Yen", -1), "USDCHF=X": ("Franco svizzero", -1), "AUDUSD=X": ("Dollaro", -1), "USDCAD=X": ("Dollaro", 1)}
# Descriptive only, from the run in docs/ZONE_BYZ_SZT.md: bars overlap and these data were already used, so it's no test
PAST = {"4h": {"bars": "24 ore", "byz": .02, "szt": .47}, "1d": {"bars": "5 sedute", "byz": .02, "szt": .36}, "1w": {"bars": "4 settimane", "byz": -.43, "szt": 1.20}, "1M": {"bars": "3 mesi", "byz": 2.33, "szt": -.77}, "12M": {"bars": "3 mesi", "byz": 1.91, "szt": .68}}
PART_IT = {"rsi": "RSI", "bollinger": "Bande di Bollinger", "ema": "Distanza dalla media breve", "sma": "Distanza dalla media lunga", "range": "Posizione nel range", "macd": "MACD"}


def clip(x):
    return x.clip(-1, 1)


def indicator_parts(d, tf):
    """Each indicator as a series from -1, stretched down, to +1, stretched up. Each bar uses only bars up to itself."""
    s, c = SETTINGS[tf], d.close
    a = K.atr(d).where(lambda x: x > 0)
    ema, sma = c.ewm(span=s["ema"], adjust=False, min_periods=s["ema"]).mean(), c.rolling(s["sma"]).mean()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    low, high = d.low.rolling(s["range"]).min(), d.high.rolling(s["range"]).max()
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    return {"rsi": clip((I.rsi(c) - 50) / 25), "bollinger": clip((c - mid) / (2 * sd.where(sd > 0))), "ema": clip((c - ema) / (2 * a)), "sma": clip((c - sma) / (4 * a)),
            "range": clip(2 * (c - low) / (high - low).where(high > low) - 1), "macd": clip((macd - macd.ewm(span=9, adjust=False).mean()) / a)}


def indicator_score(d, tf):
    """The plain average of the parts, from -100 to +100, with its parts."""
    parts = indicator_parts(d, tf)
    return 100 * pd.concat(parts, axis=1).mean(axis=1, skipna=True), parts


def frames_of(market):
    f = K.frames(market)
    if "1M" in f:
        f["12M"] = f["1M"]  # the same monthly bars, read over a year: the settings decide the window
    return f


def sentiment_score(market, moods, fear_greed=None):
    """From -100, fear, to +100, euphoria, for this market's theme. None when there are too few signals to say."""
    theme, sign = SENTIMENT_OF.get(market, (None, 1))
    m = moods.get(theme)
    value = None
    if m and m["fear"] + m["greed"] >= MIN_SIGNALS:
        value = 100 * sign * (m["greed"] - m["fear"]) / (m["greed"] + m["fear"])
    if theme == "Cripto" and fear_greed is not None:
        index = 2 * (float(fear_greed) - 50)
        value = index if value is None else (value + index) / 2
    return value


def tag_of(score):
    return "BYZ" if score <= BYZ_BELOW else "SZT" if score >= SZT_ABOVE else "NTR"


def blend(indicators, sentiment):
    return indicators if sentiment is None else WEIGHT_INDICATORS * indicators + WEIGHT_SENTIMENT * sentiment


def market_zones(market, moods, fear_greed=None):
    """The tag on every timeframe with enough data."""
    sent, out = sentiment_score(market, moods, fear_greed), {}
    for tf, d in frames_of(market).items():
        if tf not in SETTINGS or len(d) < 30:
            continue
        score, parts = indicator_score(d, tf)
        if pd.isna(score.iloc[-1]):
            continue
        ind = float(score.iloc[-1])
        total = blend(ind, sent)
        slow = K.long_trend(d.close).iloc[-1]
        tag = tag_of(total)
        with_trend = (tag == "BYZ" and slow == "rialzo") or (tag == "SZT" and slow == "ribasso")
        out[tf] = {"tag": tag, "score": total, "indicators": ind, "sentiment": sent, "slow": slow if isinstance(slow, str) else None, "with_trend": with_trend,
                   "parts": {PART_IT[k]: None if pd.isna(v.iloc[-1]) else 100 * float(v.iloc[-1]) for k, v in parts.items()}}
    return out
