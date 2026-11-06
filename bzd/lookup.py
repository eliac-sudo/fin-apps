"""Search any Hyperliquid perp or Yahoo ticker and analyze it on demand, beyond the fixed list of followed markets.

    python -m bzd.lookup cerca nvidia      what matches, on Hyperliquid and on Yahoo
    python -m bzd.lookup vedi hl:xyz:NVDA  trend, levels and price position, as the app shows them

Nothing here is recorded or enters the alerts: prices are fetched when asked and kept for a few minutes.
Ids are `hl:<name>` for a Hyperliquid perp (on any of its markets, such as xyz) and `yf:<symbol>` for Yahoo.
"""
import json, re, sys, time, urllib.parse, urllib.request

import pandas as pd

from . import technicals as K
from .history import parse_yahoo
from .recorder import UA
from .thermo import price_position, position_text

INFO = "https://api.hyperliquid.xyz/info"
YAHOO_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
YAHOO_SYMBOL = re.compile(r"^[A-Za-z0-9.^=\-]{1,24}$")
UNIVERSE_TTL, BARS_TTL = 3600, 600
_cache = {}


def cached(key, ttl, make):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = make()
    _cache[key] = (time.time(), value)
    return value


def http(url, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---- Hyperliquid

def universe():
    """Every live perp on every Hyperliquid market, with price, volume, open interest and funding."""
    def make():
        dexes = [d["name"] if d else "" for d in json.loads(http(INFO, {"type": "perpDexs"}))]
        out = {}
        for dex in dexes:
            meta, ctxs = json.loads(http(INFO, {"type": "metaAndAssetCtxs", "dex": dex}))
            for u, c in zip(meta["universe"], ctxs):
                if u.get("isDelisted") or not c.get("markPx"):
                    continue
                px = float(c["markPx"])
                out[u["name"]] = {"name": u["name"], "dex": dex or "principale", "price": px, "volume_24h": float(c.get("dayNtlVlm") or 0),
                                  "open_interest": float(c.get("openInterest") or 0) * px, "funding_hourly": float(c.get("funding") or 0),
                                  "change_24h": px / float(c["prevDayPx"]) - 1 if c.get("prevDayPx") and float(c["prevDayPx"]) else None, "max_leverage": u.get("maxLeverage")}
        return out
    return cached("universe", UNIVERSE_TTL, make)


def hl_bars(name, interval, days):
    start = int((time.time() - days * 86400) * 1000)
    rows = json.loads(http(INFO, {"type": "candleSnapshot", "req": {"coin": name, "interval": interval, "startTime": start}}))
    if not rows:
        return None
    d = pd.DataFrame({"t": pd.to_datetime([r["t"] for r in rows], unit="ms", utc=True), **{k: [float(r[x]) for r in rows] for k, x in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c"))}})
    return d.set_index("t").sort_index()


# ---- Yahoo

def yahoo_search(q):
    raw = http(f"{YAHOO_SEARCH}?{urllib.parse.urlencode({'q': q, 'quotesCount': 8, 'newsCount': 0})}", timeout=15)
    return [{"symbol": x["symbol"], "name": x.get("shortname") or x.get("longname") or x["symbol"], "type": x.get("quoteType", ""), "exchange": x.get("exchange", "")}
            for x in json.loads(raw).get("quotes", []) if YAHOO_SYMBOL.match(x.get("symbol", ""))]


def yahoo_bars(symbol):
    raw = http(f"{YAHOO_CHART}{urllib.parse.quote(symbol)}?interval=1d&range=10y", timeout=30)
    d = parse_yahoo(raw)
    d = d.assign(t=pd.to_datetime(d.date, utc=True)).set_index("t").sort_index()[["open", "high", "low", "close"]].dropna()
    return d[d.low > 0], json.loads(raw)["chart"]["result"][0]["meta"]


# ---- search and view

def search(q, limit=10):
    """Hyperliquid perps whose name contains the words, busiest first, then Yahoo's matches. A source that fails is skipped."""
    q = (q or "").strip()
    if not q:
        return []
    words = q.lower().split()
    try:
        yahoo = yahoo_search(q)[:limit]
    except Exception:
        yahoo = []
    # a company name finds its Hyperliquid perp through Yahoo's symbol: "nvidia" gives NVDA, and xyz:NVDA trades it
    symbols = {re.split(r"[.=]", x["symbol"])[0].upper() for x in yahoo}
    hl = []
    try:
        hits = [u for u in universe().values() if all(w in u["name"].lower() for w in words) or u["name"].split(":")[-1].upper() in symbols]
        hl = [{"id": f"hl:{u['name']}", "label": u["name"], "source": "Hyperliquid", "detail": f"mercato {u['dex']}, volume 24h ${u['volume_24h'] / 1e6:,.1f}M"}
              for u in sorted(hits, key=lambda u: -u["volume_24h"])[:limit]]
    except Exception:
        pass
    return hl + [{"id": f"yf:{x['symbol']}", "label": f"{x['symbol']} · {x['name']}", "source": "Yahoo", "detail": " ".join(filter(None, (x["type"].lower(), x["exchange"])))} for x in yahoo]


def valid(ident):
    """Only ids that can be fetched safely: a perp that exists, or a plain Yahoo symbol."""
    if ident.startswith("hl:"):
        return ident[3:] in universe()
    return ident.startswith("yf:") and bool(YAHOO_SYMBOL.match(ident[3:]))


def bars(ident):
    """(daily bars, 4h bars or None, info). Kept for a few minutes."""
    def make():
        if ident.startswith("hl:"):
            name = ident[3:]
            return hl_bars(name, "1d", 5000), hl_bars(name, "4h", 60), {"source": "Hyperliquid", **universe()[name]}
        d, meta = yahoo_bars(ident[3:])
        return d, None, {"source": "Yahoo", "name": meta.get("longName") or meta.get("shortName") or ident[3:], "currency": meta.get("currency"), "exchange": meta.get("fullExchangeName")}
    return cached(("bars", ident), BARS_TTL, make)


def technical(ident):
    """The same shape as the app's technical view of a followed market, plus price position and market facts."""
    daily, four_h, info = bars(ident)
    if daily is None or daily.empty:
        return None
    year = 365 if ident.startswith("hl:") and info.get("dex") == "principale" else 252
    pos = price_position(daily.close, year)
    label = ident[3:] if ident.startswith("hl:") else f"{ident[3:]} · {info.get('name')}"
    if ident.startswith("hl:"):
        try:
            from . import wallets as W
            info = {**info, "wallets": W.flows(W.latest_positions()).get(ident[3:])}
        except Exception:
            pass
    return {"label": label, "plan_key": None, "searched": True, "info": info, "position": pos, "position_text": position_text(pos) if pos else None,
            "history_days": int((daily.index[-1] - daily.index[0]).days), "frames": K.analyze(ident, K.frames_from(daily, four_h))}


def main(argv):
    cmd, arg = (argv + ["", ""])[:2]
    if cmd == "cerca":
        for r in search(" ".join(argv[1:])):
            print(f"{r['id']:28} {r['source']:12} {r['label'][:50]:50} {r['detail']}")
        return 0
    if cmd == "vedi" and valid(arg):
        v = technical(arg)
        if not v:
            print("nessun dato")
            return 1
        print(v["label"], "·", v["position_text"] or "storia troppo breve per dire se è caro")
        for tf, f in v["frames"].items():
            print(f"  {tf:3} trend {f['trend']:9} RSI {f['rsi']:.0f}  supporto {f['supports'][0]['price'] if f['supports'] else '–'}  resistenza {f['resistances'][0]['price'] if f['resistances'] else '–'}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
