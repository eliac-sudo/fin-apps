"""Market thermometer: how hot each market looks compared with its own past. It describes, it doesn't predict.

    python -m bzd.thermo           print it
    python -m bzd.thermo --send    also send it to Telegram

Options have their own message in options_report. mood() and attention() remain as baselines for the agents.
Heat is the plain average of percentiles against strictly earlier data, equally weighted. No LLM and no cost.
"""
import html, re, sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import indicators as I
from . import texts as T
from .events import align_cot, daily, read
from .history import CRYPTO, MARKETS, safe
from .recorder import BASE, load_env
from .setups import VOL_INDEX, load_crypto, load_vol_index

LABELS = {"ES=F": "S&amp;P 500", "NQ=F": "Nasdaq", "RTY=F": "Russell", "ZT=F": "2 anni", "ZF=F": "5 anni", "ZN=F": "10 anni", "ZB=F": "30 anni", "CL=F": "Petrolio", "NG=F": "Gas",
          "GC=F": "Oro", "SI=F": "Argento", "HG=F": "Rame", "ZC=F": "Mais", "ZW=F": "Grano", "ZS=F": "Soia", "EURUSD=X": "EUR/USD", "USDJPY=X": "USD/JPY", "GBPUSD=X": "GBP/USD",
          "AUDUSD=X": "AUD/USD", "USDCHF=X": "USD/CHF", "USDCAD=X": "USD/CAD"}
BANDS = ((80, "🔥 molto caldo"), (60, "🌡 caldo"), (40, "😐 neutro"), (20, "🧊 freddo"), (0, "🥶 molto freddo"))
FEAR = r"\b(panic|fear|crash|capitulat|liquidat|collapse|plunge|meltdown|bloodbath|recession|sell-?off|tumbl|rekt|paura|crollo)\w*"
GREED = r"\b(moon|euphori|\bath\b|all-time high|fomo|parabolic|skyrocket|soar|surge|rally|lambo|bullrun|bull run|euforia)\w*"


def band(x):
    for lim, name in BANDS:
        if x >= lim:
            return name
    return BANDS[-1][1]


def heat_from(parts):
    vals = {k: float(v) for k, v in parts.items() if v is not None and not pd.isna(v)}
    return (float(np.mean(list(vals.values()))), vals) if vals else (None, {})


def crypto_reading(a):
    d, f, o = load_crypto(a)
    c = d.close
    r42 = np.log(c).diff(42)
    fund7 = f.rolling(21).mean().reindex(d.index, method="ffill")
    oi7 = o.reindex(d.index, method="ffill", limit=2).pct_change(42, fill_method=None)
    rs = I.rsi(c)
    parts = {"slancio": I.past_percentile(r42).iloc[-1], "rsi": rs.iloc[-1], "estensione": I.past_percentile(I.sma_distance(c, 1200)).iloc[-1],
             "funding": I.past_percentile(fund7).iloc[-1], "oi": I.past_percentile(oi7).iloc[-1]}
    return reading(a, "crypto", c, rs, parts, d.index[-1], extra={"sma200_dist": I.sma_distance(c, 1200).iloc[-1], "vwap_dist": I.vwap_distance(d, 42, "volume_usd").iloc[-1]})


def daily_reading(sym, cls):
    d = daily(read("tradfi", safe(sym)))
    c = d.close
    parts = {}
    rs = I.rsi(c)
    parts["slancio"] = I.past_percentile(np.log(c.where(c > 0)).diff(20)).iloc[-1]
    parts["rsi"] = rs.iloc[-1]
    parts["estensione"] = I.past_percentile(I.sma_distance(c, 200)).iloc[-1]
    cot = read("cot", safe(sym))
    if cot is not None:
        spec = align_cot(cot, d.index).spec_net_pct_oi
        parts["posizionamento"] = I.past_percentile(spec.dropna()).reindex(d.index).ffill().iloc[-1]
    vi = load_vol_index(VOL_INDEX[sym], d.index) if sym in VOL_INDEX else None
    if vi is not None and vi.notna().iloc[-1]:
        parts["calma"] = 100 - I.past_percentile(vi).iloc[-1]
    return reading(sym, cls, c, rs, parts, d.index[-1], extra={"sma200_dist": I.sma_distance(c, 200).iloc[-1]})


def reading(name, cls, close, rs, parts, last, extra):
    heat, vals = heat_from(parts)
    return {"market": name, "class": cls, "heat": heat, "parts": vals, "price": float(close.iloc[-1]), "bar": last.isoformat(), "rsi": float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else None, **{k: float(v) for k, v in extra.items() if not pd.isna(v)}}


def all_readings():
    out = []
    for a in CRYPTO:
        out.append(crypto_reading(a))
    for s, (c, _) in MARKETS.items():
        out.append(daily_reading(s, c))
    return out


def mood(items, cls, now, hours=24):
    """Baseline mood from word counts, with no LLM. Crude by design: it is what the LLM has to beat."""
    pat = T.topic_pattern(cls, None)
    start = (now - timedelta(hours=hours)).isoformat()
    fear = greed = n = 0
    for it in items:
        if it["time"] >= start and (pat is None or pat.search(it["text"])):
            n += 1
            fear += bool(re.search(FEAR, it["text"], re.I))
            greed += bool(re.search(GREED, it["text"], re.I))
    return {"texts": n, "fear": fear, "greed": greed}


def attention():
    """Wikipedia views of the last week against the previous year, as a z-score."""
    out = {}
    for a in ("Bitcoin", "Stock_market_crash", "Recession"):
        d = read("attention", a)
        if d is None or len(d) < 400:
            continue
        v = np.log(d.views.replace(0, np.nan)).rolling(7).mean()
        past = v.iloc[-372:-7]
        out[a] = float((v.iloc[-1] - past.mean()) / past.std())
    return out


def fear_greed():
    d = read("macro", "fear_greed")
    return None if d is None else {"value": int(d.value.iloc[-1]), "date": d.date.iloc[-1]}


def build_digest(now=None):
    now = now or datetime.now(timezone.utc)
    rows = all_readings()
    names = {"crypto": "Cripto", "equities": "Azioni", "bonds": "Bond", "commodities": "Materie prime", "fx": "Forex"}
    out = [f"🌡 <b>Termometro</b> · {now:%d/%m %H:%M} UTC", "Quanto è caldo ogni mercato rispetto al suo passato, da 0 a 100."]
    for cls, label in names.items():
        g = sorted([r for r in rows if r["class"] == cls and r["heat"] is not None], key=lambda r: -r["heat"])
        if g:
            avg = float(np.mean([r["heat"] for r in g]))
            out += ["", f"<b>{label}: {avg:.0f}</b> {band(avg)}", " · ".join(f"{LABELS.get(r['market'], r['market'])} {r['heat']:.0f}" for r in g[:9])]
    fg = fear_greed()
    if fg:
        out += ["", f"Fear &amp; Greed cripto: {fg['value']}"]
    out += ["", "Descrive e non prevede: non è testato come segnale e non è consulenza finanziaria."]
    return "\n".join(out), rows


def main(argv):
    load_env()
    text, _ = build_digest()
    print(re.sub(r"</?b>", "", html.unescape(text)))
    if "--send" in argv:
        from .alerts import send_text, split_message
        for part in split_message(text):
            send_text(part)
        print("\n[inviato]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
