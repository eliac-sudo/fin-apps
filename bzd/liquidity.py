"""Liquidity: how much money is around (the Fed, M2, stablecoins, credit) and how easily each market trades.

Two kinds, shown in Oggi and on each ticker page:
- macro(): dollar liquidity. Fed net liquidity is the balance sheet minus the Treasury's account and the reverse repo,
  the money the Fed leaves in the system. Each indicator is compared with 13 weeks earlier.
- markets(): for each market, average dollar volume over 20 sessions and the price impact per dollar traded (Amihud),
  both as a percentile of the last 3 years; for the 11 Hyperliquid markets also the spread and the depth of the book.

It describes, it doesn't predict: no liquidity reading has been tested as a signal here.
"""
import gzip, json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .events import read
from .history import CRYPTO, MARKETS, root, safe

WINDOW, YEARS = 20, 3
# Hyperliquid books recorded every 5 minutes, and the market each one stands for in the app
HL_BOOKS = {"BTC": "BTC", "ETH": "ETH", "SOL": "SOL", "xyz:SP500": "ES=F", "xyz:XYZ100": "NQ=F", "xyz:CL": "CL=F", "xyz:GOLD": "GC=F",
            "xyz:SILVER": "SI=F", "xyz:EUR": "EURUSD=X", "xyz:JPY": "USDJPY=X", "xyz:TLT": "ZB=F"}
BOOK_BAND = 0.005  # depth counted within 0.5% of the mid price
BANDS = ((80, "abbondante"), (60, "sopra la norma"), (40, "nella norma"), (20, "sotto la norma"), (0, "scarsa"))


def band(x):
    return None if x is None or pd.isna(x) else next(w for lo, w in BANDS if x >= lo)


def pct_rank(s, x):
    """Percentile of x among the values of s, 0-100."""
    s = s.dropna()
    return float((s < x).mean() * 100 + (s == x).mean() * 50) if len(s) and x is not None and not pd.isna(x) else None


# ---- dollar liquidity -------------------------------------------------------------------------------------------------

def _fred(name):
    d = read("macro", name)
    if d is None or d.empty:
        return None
    return d.assign(date=pd.to_datetime(d.date)).set_index("date").value.sort_index()


def net_liquidity():
    """Fed net liquidity in billions of dollars, weekly (Wednesdays): WALCL - WTREGEN - RRPONTSYD."""
    walcl, tga, rrp = _fred("WALCL"), _fred("WTREGEN"), _fred("RRPONTSYD")
    if walcl is None or tga is None or rrp is None:
        return None
    idx = walcl.index
    net = walcl / 1000 - tga.reindex(idx, method="ffill", tolerance=pd.Timedelta(days=7)) / 1000 - rrp.reindex(idx, method="ffill", tolerance=pd.Timedelta(days=7)).fillna(0)
    return net.dropna()


def stablecoins():
    d = read("macro", "stablecoins")
    if d is None or d.empty:
        return None
    return d.assign(date=pd.to_datetime(d.date)).set_index("date").usd_bn.sort_index()


def _change(s, days):
    """Change over `days` calendar days, from the last value at or before that date."""
    if s is None or len(s) < 2:
        return None
    past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return None if past.empty else float(s.iloc[-1] - past.iloc[-1])


def _indicator(key, label, s, unit, more_when, meaning, days=91, ratio=False, digits=1):
    """One row: last value, change over `days` (as a % of the old value when ratio), and whether that means more liquidity."""
    if s is None or s.dropna().empty:
        return None
    s = s.dropna()
    ch = _change(s, days)
    if ratio and ch is not None:
        past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)].iloc[-1]
        ch = ch / past * 100 if past else None
    tone = None if ch is None or abs(ch) < 1e-9 else ("più" if (ch > 0) == (more_when == "up") else "meno")
    hist = s[s.index >= s.index[-1] - pd.Timedelta(days=365 * YEARS)]
    return {"key": key, "label": label, "value": round(float(s.iloc[-1]), digits), "unit": unit, "date": s.index[-1].strftime("%Y-%m-%d"),
            "change": None if ch is None else round(ch, 2), "change_unit": "%" if ratio else unit, "days": days, "tone": tone,
            "pct_3y": pct_rank(hist, s.iloc[-1]), "meaning": meaning}


def macro():
    net, sc = net_liquidity(), stablecoins()
    m2 = _fred("M2SL")
    m2_yoy = (m2 / m2.shift(12) - 1).dropna() * 100 if m2 is not None else None
    rows = [
        _indicator("net", "Liquidità netta della Fed", net, " mld $", "up", "Bilancio della Fed meno il conto del Tesoro e il reverse repo: i soldi che la Fed lascia nel sistema. Sale: più liquidità per tutti i mercati.", digits=0),
        _indicator("m2", "M2 USA, crescita annua", m2_yoy, "%", "up", "Quanto cresce la moneta in circolo negli USA rispetto a un anno prima.", days=92),
        _indicator("stable", "Stablecoin in circolazione", sc, " mld $", "up", "Dollari digitali pronti a comprare cripto. Salgono: entra liquidità nel mercato cripto.", days=30, ratio=True, digits=0),
        _indicator("nfci", "Condizioni finanziarie (Chicago Fed)", _fred("NFCI"), "", "down", "Sotto zero sono più facili della media storica. Scende: prendere a prestito costa meno e il credito gira di più.", digits=2),
        _indicator("hy", "Spread high yield", _fred("BAMLH0A0HYM2"), " punti", "down", "Quanto in più pagano le aziende più rischiose. Si stringe: il credito è abbondante.", digits=2),
        _indicator("usd", "Dollaro (indice ampio)", _fred("DTWEXBGS"), "", "down", "Un dollaro forte stringe la liquidità nel mondo, perché molti debiti sono in dollari.", ratio=True, digits=1),
    ]
    rows = [r for r in rows if r]
    more = sum(r["tone"] == "più" for r in rows)
    less = sum(r["tone"] == "meno" for r in rows)
    since = lambda s, days: s[s.index >= s.index[-1] - pd.Timedelta(days=days)] if s is not None and len(s) else None
    charts = {}
    for k, s in (("net", since(net, 730)), ("stable", since(sc, 730))):
        if s is not None and len(s) > 1:
            charts[k] = {"dates": s.index.strftime("%Y-%m-%d").tolist(), "values": [round(float(v), 1) for v in s]}
    return {"rows": rows, "more": more, "less": less, "charts": charts}


# ---- market liquidity -------------------------------------------------------------------------------------------------

def volume_liquidity(close, dollar_volume, volume=None):
    """Volume and Amihud impact over 20 sessions, each as a percentile of the last 3 years, plus a 0-100 score.

    `volume` is what is compared for size: contracts for futures, since price times contracts also grows with the price;
    dollars for crypto. The impact always uses dollars.
    """
    dv = dollar_volume.where(dollar_volume > 0)
    if dv.dropna().size < WINDOW * 3:
        return None
    ret = np.log(close.where(close > 0)).diff().abs()
    size = dv if volume is None else volume.where(volume > 0)
    vol20 = size.rolling(WINDOW, min_periods=WINDOW // 2).mean()
    amihud = (ret / dv).rolling(WINDOW, min_periods=WINDOW // 2).mean()
    last = vol20.index[-1]
    past = lambda s: s[(s.index > last - pd.Timedelta(days=365 * YEARS))]
    vp, ip = pct_rank(past(vol20), vol20.iloc[-1]), pct_rank(past(amihud), amihud.iloc[-1])
    if vp is None or ip is None:
        return None
    score = (vp + (100 - ip)) / 2
    return {"volume_pct": round(vp), "impact_pct": round(ip), "score": round(score), "band": band(score), "bar": last.strftime("%Y-%m-%d")}


def _daily(group, name):
    d = read(group, name)
    if d is None or d.empty:
        return None
    t = "date" if "date" in d else "t"
    d = d.assign(**{t: pd.to_datetime(d[t], utc=True, format="ISO8601")}).set_index(t).sort_index()
    return d[~d.index.duplicated(keep="last")]


def crypto_days(asset):
    """Daily close and dollar volume from the 4h bars, which stay fresh (the daily file stops when its first download did).
    Today is left out: it is not complete."""
    d = read("crypto", f"{asset}_candles_4h")
    if d is None or d.empty or "volume_usd" not in d:
        return None
    t = pd.to_datetime(d.t, utc=True, format="ISO8601")
    d = d.assign(t=t).drop_duplicates("t", keep="last").sort_values("t")
    day = d.t.dt.floor("D")
    g = d.groupby(day).agg(close=("close", "last"), volume_usd=("volume_usd", "sum"), bars=("close", "size"))
    return g[g.bars == 6].drop(columns="bars")


def book_row(snap):
    """Spread in basis points and dollar depth within 0.5% of the mid, from one Hyperliquid l2Book response."""
    bids, asks = snap["levels"]
    if not bids or not asks:
        return None
    b, a = float(bids[0]["px"]), float(asks[0]["px"])
    mid = (a + b) / 2
    depth = lambda side, ok: sum(float(x["px"]) * float(x["sz"]) for x in side if ok(float(x["px"])))
    return {"t": pd.Timestamp(snap["time"], unit="ms", tz="UTC"), "spread_bps": (a - b) / mid * 1e4,
            "depth_usd": depth(bids, lambda p: p >= mid * (1 - BOOK_BAND)) + depth(asks, lambda p: p <= mid * (1 + BOOK_BAND))}


def refresh_books():
    """Add one book per hour per market to hist/liquidity/books, from the recorder's copies. Only new hours are read."""
    out = root() / "liquidity" / "books.csv.gz"
    old = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["coin", "t", "spread_bps", "depth_usd"])
    raw = root().parent / "raw"
    new = []
    for coin in HL_BOOKS:
        job = "hl_l2_" + coin.replace(":", "_").lower()
        have = set(old[old.coin == coin].t.astype(str).str[:13])
        for day in sorted((raw / job).glob("????-??-??")):
            hours = {}
            for f in sorted(day.glob("*.gz")):
                hours.setdefault(f.name[:2], f)  # the first copy of each hour
            for hh, f in hours.items():
                if f"{day.name} {hh}" in have or f"{day.name}T{hh}" in have:
                    continue
                try:
                    r = book_row(json.loads(gzip.open(f).read()))
                except (OSError, ValueError, KeyError, IndexError, TypeError):
                    continue
                if r:
                    new.append({"coin": coin, **r, "t": r["t"].strftime("%Y-%m-%d %H:%M:%S")})
    if new:
        out.parent.mkdir(parents=True, exist_ok=True)
        both = pd.concat([old, pd.DataFrame(new)], ignore_index=True).sort_values(["coin", "t"])
        tmp = out.with_name(out.name + ".tmp")
        both.to_csv(tmp, index=False, compression={"method": "gzip"})
        tmp.replace(out)
        return both
    return old


def book_view(books, coin):
    """Latest hour against the median of everything recorded so far, which is only weeks at first."""
    b = books[books.coin == coin]
    if len(b) < 2:
        return None
    last = b.iloc[-1]
    hist = b.iloc[:-1]
    return {"coin": coin, "t": str(last.t), "spread_bps": round(float(last.spread_bps), 2), "depth_usd": float(last.depth_usd),
            "spread_median": round(float(hist.spread_bps.median()), 2), "depth_median": float(hist.depth_usd.median()),
            "depth_pct": pct_rank(hist.depth_usd, last.depth_usd), "since": str(b.t.iloc[0])[:10], "hours": int(len(b))}


def markets():
    out = {}
    for a in CRYPTO:
        d = crypto_days(a)
        if d is not None:
            v = volume_liquidity(d.close, d.volume_usd)
            if v:
                out[a] = v
    for s, (cls, _) in MARKETS.items():
        d = _daily("tradfi", safe(s))
        if d is None or "volume" not in d or cls == "fx":  # Yahoo gives no volume for currency pairs
            continue
        d = d.iloc[:-1] if len(d) > 1 and d.volume.iloc[-1] == d.volume.iloc[-2] else d  # Yahoo repeats the last bar while the day is open
        v = volume_liquidity(d.close, d.close * d.volume, d.volume)
        if v:
            out[s] = v
    try:
        books = refresh_books()
    except OSError:
        books = None
    if books is not None and len(books):
        for coin, market in HL_BOOKS.items():
            b = book_view(books, coin)
            if b:
                out.setdefault(market, {})["book"] = b
    return out


def view():
    return {"macro": macro(), "markets": markets(), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
