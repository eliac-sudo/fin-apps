"""Market thermometer: how stretched each market looks compared with its own past. It describes, it doesn't predict.

    python -m bzd.thermo           print it
    python -m bzd.thermo --send    also send it to Telegram

Options have their own message in options_report. attention() is the Wikipedia baseline the app shows.
The tension, called heat in the code, is the plain average of percentiles against strictly earlier data, equally weighted. No LLM and no cost.
"""
import html, re, sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import indicators as I
from .events import align_cot, crypto_daily, daily, read
from .history import CRYPTO, MARKETS, safe
from .recorder import load_env
from .setups import VOL_INDEX, load_crypto, load_vol_index

LABELS = {"ES=F": "S&amp;P 500", "NQ=F": "Nasdaq", "RTY=F": "Russell", "ZT=F": "2 anni", "ZF=F": "5 anni", "ZN=F": "10 anni", "ZB=F": "30 anni", "CL=F": "Petrolio", "NG=F": "Gas",
          "GC=F": "Oro", "SI=F": "Argento", "HG=F": "Rame", "ZC=F": "Mais", "ZW=F": "Grano", "ZS=F": "Soia", "EURUSD=X": "EUR/USD", "USDJPY=X": "USD/JPY", "GBPUSD=X": "GBP/USD",
          "AUDUSD=X": "AUD/USD", "USDCHF=X": "USD/CHF", "USDCAD=X": "USD/CAD"}
BANDS = ((80, "🔺 molto tirato in alto"), (60, "↗ tirato in alto"), (40, "⚖ in equilibrio"), (20, "↘ tirato in basso"), (0, "🔻 molto tirato in basso"))
COT_AGAINST_PAIR = {"USDJPY=X", "USDCHF=X", "USDCAD=X"}  # the futures are long the yen, franc or Canadian dollar, so long speculators are betting on the pair falling
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


def crypto_series(a):
    """The parts of the tension on every 4h bar, each from strictly earlier data. Also used by the v3 historical test."""
    d, f, o = load_crypto(a)
    c = d.close
    r42 = np.log(c).diff(42)
    fund7 = f.rolling(21).mean().reindex(d.index, method="ffill")
    oi7 = o.reindex(d.index, method="ffill", limit=2).pct_change(42, fill_method=None)
    rs = I.rsi(c)
    return d, c, rs, {"slancio": I.past_percentile(r42), "rsi": rs, "estensione": I.past_percentile(I.sma_distance(c, 1200)),
                      "funding": I.past_percentile(fund7), "oi": I.past_percentile(oi7)}


def crypto_reading(a):
    d, c, rs, series = crypto_series(a)
    return reading(a, "crypto", c, rs, series, d.index[-1], 42, extra={"sma200_dist": I.sma_distance(c, 1200).iloc[-1], "vwap_dist": I.vwap_distance(d, 42, "volume_usd").iloc[-1]})


def daily_series(sym):
    """The parts of the tension on every daily bar, each from strictly earlier data. Also used by the v3 historical test."""
    d = daily(read("tradfi", safe(sym)))
    c = d.close
    rs = I.rsi(c)
    series = {"slancio": I.past_percentile(np.log(c.where(c > 0)).diff(20)), "rsi": rs, "estensione": I.past_percentile(I.sma_distance(c, 200))}
    cot = read("cot", safe(sym))
    if cot is not None:
        spec = align_cot(cot, d.index).spec_net_pct_oi
        spec_pct = I.past_percentile(spec.dropna()).reindex(d.index).ffill()
        series["posizionamento"] = 100 - spec_pct if sym in COT_AGAINST_PAIR else spec_pct
    vi = load_vol_index(VOL_INDEX[sym], d.index) if sym in VOL_INDEX else None
    if vi is not None and vi.notna().iloc[-1]:
        series["calma"] = 100 - I.past_percentile(vi)
    return d, c, rs, series


def daily_reading(sym, cls):
    d, c, rs, series = daily_series(sym)
    return reading(sym, cls, c, rs, series, d.index[-1], 5, extra={"sma200_dist": I.sma_distance(c, 200).iloc[-1]})


def at(series, i):
    return {k: v.iloc[i] for k, v in series.items() if len(v) >= abs(i)}


HISTORY_DAYS = 120


def heat_history(series):
    """Daily heat of one market for the last few months, as {date: heat}. Same plain average as today's number, on the same strictly-past percentiles."""
    h = pd.concat(series, axis=1).mean(axis=1, skipna=True).dropna()
    h = h.groupby(pd.to_datetime(h.index, utc=True).strftime("%Y-%m-%d")).last().tail(HISTORY_DAYS)
    return {k: float(v) for k, v in h.items()}


def reading(name, cls, close, rs, series, last, week_bars, extra):
    heat, vals = heat_from(at(series, -1))
    week_ago = heat_from(at(series, -1 - week_bars))[0]
    return {"market": name, "history": heat_history(series), "class": cls, "heat": heat, "heat_change_7d": heat - week_ago if heat is not None and week_ago is not None else None, "parts": vals, "price": float(close.iloc[-1]), "bar": last.isoformat(), "rsi": float(rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else None, **{k: float(v) if not pd.isna(v) else None for k, v in extra.items()}}


def all_readings():
    out = []
    for a in CRYPTO:
        out.append(crypto_reading(a))
    for s, (c, _) in MARKETS.items():
        out.append(daily_reading(s, c))
    return out


PRICE_BANDS = ((80, "molto caro"), (60, "caro"), (40, "nella media"), (20, "economico"), (0, "molto economico"))


def price_position(close, year_bars):
    """Where the price sits in its own last year. This is cheap or dear against its recent past: it says nothing about what the market is worth."""
    c = close.dropna().tail(year_bars)
    if len(c) < year_bars // 2:
        return None
    last = float(c.iloc[-1])
    pct = 100 * float((c.iloc[:-1] < last).mean())
    return {"pct": pct, "label": next(name for lim, name in PRICE_BANDS if pct >= lim), "from_high": 100 * (last / float(c.max()) - 1), "from_low": 100 * (last / float(c.min()) - 1)}


def market_position(market):
    """Price position of a market from stored daily closes, or None."""
    d, bars = (crypto_daily(market), 365) if market in CRYPTO else (read("tradfi", safe(market)), 252)
    if d is None:
        return None
    return price_position((d if market in CRYPTO else daily(d)).close, bars)


def position_text(p):
    return f"{p['label']} rispetto all'ultimo anno ({p['from_high']:+.0f}% dal massimo, {p['from_low']:+.0f}% dal minimo)"


def mood_of(items, pattern, now, hours=24):
    """Crude word count for any topic pattern. Returns the counts and the matching texts."""
    start = (now - timedelta(hours=hours)).isoformat()
    picked = [it for it in items if it["time"] >= start and pattern.search(it["text"])]
    return {"texts": len(picked), "fear": sum(bool(re.search(FEAR, it["text"], re.I)) for it in picked), "greed": sum(bool(re.search(GREED, it["text"], re.I)) for it in picked)}, picked


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


PART_IT = {"slancio": "slancio", "rsi": "RSI", "estensione": "distanza dalla media", "funding": "funding", "oi": "leva (OI)", "posizionamento": "speculatori", "calma": "volatilità bassa"}
PART_COLD = {"calma": "volatilità alta"}  # calm that is low means volatility that is high
CLASS_IT = {"crypto": "Cripto", "equities": "Azioni", "bonds": "Bond", "commodities": "Materie prime", "fx": "Forex"}


def class_summary(rows):
    """One market class in words: how hot, how it changed, and what is driving it."""
    avg = float(np.mean([r["heat"] for r in rows]))
    changes = [r["heat_change_7d"] for r in rows if r.get("heat_change_7d") is not None]
    parts = {}
    for r in rows:
        for k, v in r["parts"].items():
            parts.setdefault(k, []).append(v)
    means = {k: float(np.mean(v)) for k, v in parts.items()}
    hot = [PART_IT[k] for k, v in sorted(means.items(), key=lambda x: -x[1]) if v >= 60][:2]
    cold = [PART_COLD.get(k, PART_IT[k]) for k, v in sorted(means.items(), key=lambda x: x[1]) if v <= 40][:2]
    return {"heat": avg, "band": band(avg), "change_7d": float(np.mean(changes)) if changes else None, "hot": hot, "cold": cold, "parts": means}


def why_text(s):
    bits = ([f"Spinge: {', '.join(s['hot'])}."] if s["hot"] else []) + ([f"Frena: {', '.join(s['cold'])}."] if s["cold"] else [])
    return " ".join(bits) or "Nessun fattore estremo."


def overview(summaries):
    """The whole picture in one sentence, without the reader having to compare numbers."""
    names = {b: [CLASS_IT[c] for c, s in summaries.items() if s["band"] == b] for b in {s["band"] for s in summaries.values()}}
    hot = [c for b, g in names.items() if "in alto" in b for c in g]
    cold = [c for b, g in names.items() if "in basso" in b for c in g]
    moved = max(((c, s) for c, s in summaries.items() if s["change_7d"] is not None), key=lambda x: abs(x[1]["change_7d"]), default=None)
    text = (f"Tirati in alto: {', '.join(hot)}. " if hot else "Nessun gruppo tirato in alto. ") + (f"Tirati in basso: {', '.join(cold)}." if cold else "Nessun gruppo tirato in basso.")
    if moved and abs(moved[1]["change_7d"]) >= 5:
        text += f" Il cambiamento più forte degli ultimi 7 giorni riguarda {CLASS_IT[moved[0]]} ({moved[1]['change_7d']:+.0f})."
    return text


def build_digest(now=None):
    now = now or datetime.now(timezone.utc)
    rows = all_readings()
    groups = {c: sorted([r for r in rows if r["class"] == c and r["heat"] is not None], key=lambda r: -r["heat"]) for c in CLASS_IT}
    groups = {c: g for c, g in groups.items() if g}
    summaries = {c: class_summary(g) for c, g in groups.items()}
    out = [f"🌡 <b>Termometro</b> · {now:%d/%m %H:%M} UTC", "Tensione da 0 a 100 rispetto al suo passato: 0 tirato in basso, 50 la sua norma, 100 tirato in alto.", "", f"<b>{overview(summaries)}</b>"]
    for c, g in groups.items():
        s = summaries[c]
        change = f" ({s['change_7d']:+.0f} in 7 giorni)" if s["change_7d"] is not None else ""
        name = lambda r: LABELS.get(r["market"], r["market"])
        extremes = f"Più in alto {name(g[0])} {g[0]['heat']:.0f} · più in basso {name(g[-1])} {g[-1]['heat']:.0f}" if len(g) > 1 else f"{name(g[0])} {g[0]['heat']:.0f}"
        out += ["", f"<b>{CLASS_IT[c]}: {s['heat']:.0f}</b> {s['band']}{change}", extremes, why_text(s)]
    pos = sorted((p["pct"], LABELS.get(m, m)) for m, p in ((m, market_position(m)) for m in [*CRYPTO, *MARKETS]) if p)
    if pos:
        out += ["", "<b>Prezzo rispetto all'ultimo anno</b>", "Più economici: " + " · ".join(n for _, n in pos[:5]), "Più cari: " + " · ".join(n for _, n in pos[:-6:-1])]
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
