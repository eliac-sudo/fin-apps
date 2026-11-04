"""Download and clean past data for every market class. Needs pandas. Re-running skips finished series.

    python -m bzd.history get [group ...]     crypto tradfi vol cot macro attention
    python -m bzd.history coverage

Raw responses go to hist/raw with a hash in hist/manifest.jsonl. Clean tables go to hist/<group>/<name>.csv.gz.
"""
import gzip, hashlib, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .jobs import Job
from .recorder import BASE, UA, load_env, redact

CRYPTO = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK"]
HL_COINS = ["BTC", "ETH", "SOL", "xyz:SP500", "xyz:XYZ100", "xyz:CL", "xyz:GOLD", "xyz:SILVER", "xyz:EUR", "xyz:JPY", "xyz:TLT"]
# Yahoo symbol -> (market class, CFTC contract code)
MARKETS = {
    "ES=F": ("equities", "13874A"), "NQ=F": ("equities", "209742"), "RTY=F": ("equities", "239742"),
    "ZT=F": ("bonds", "042601"), "ZF=F": ("bonds", "044601"), "ZN=F": ("bonds", "043602"), "ZB=F": ("bonds", "020601"),
    "CL=F": ("commodities", "067651"), "NG=F": ("commodities", "023651"), "GC=F": ("commodities", "088691"),
    "SI=F": ("commodities", "084691"), "HG=F": ("commodities", "085692"), "ZC=F": ("commodities", "002602"),
    "ZW=F": ("commodities", "001602"), "ZS=F": ("commodities", "005602"),
    "EURUSD=X": ("fx", "099741"), "USDJPY=X": ("fx", "097741"), "GBPUSD=X": ("fx", "096742"),
    "AUDUSD=X": ("fx", "232741"), "USDCHF=X": ("fx", "092741"), "USDCAD=X": ("fx", "090741"),
}
# ETFs spot futures roll artefacts, and they are the underlyings of the recorded option chains
ETF_CHECK = {"ES=F": "SPY", "NQ=F": "QQQ", "RTY=F": "IWM", "ZN=F": "IEF", "ZB=F": "TLT", "GC=F": "GLD", "SI=F": "SLV", "CL=F": "USO"}
VOL_YAHOO = ["^MOVE"]
VOL_CBOE = {"VIX": "CLOSE", "VIX9D": "CLOSE", "VIX3M": "CLOSE", "VVIX": "VVIX", "SKEW": "SKEW", "OVX": "OVX", "GVZ": "GVZ"}
IV_SYMBOLS = ["SPY", "QQQ", "IWM", "TLT", "IEF", "GLD", "SLV", "USO", "FXE"]
DOLTHUB = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q="
FRED = ["DFF", "DGS2", "DGS10", "T10Y2Y", "BAMLH0A0HYM2", "DTWEXBGS", "EVZCLS"]
WIKI = ["Bitcoin", "Cryptocurrency", "Stock_market_crash", "Recession", "Inflation", "Gold_as_an_investment"]
GAPS = {"www.dolthub.com": 2, "cdn.cboe.com": 20, "query1.finance.yahoo.com": 2, "api.stlouisfed.org": 1, "publicreporting.cftc.gov": 1.5}
_last = {}


def root():
    return Path(os.environ.get("BZD_DATA", BASE / "data")) / "hist"


def get(group, name, n, url, body=None, secrets=()):
    """Polite request with retries. Saves the raw response and logs its hash. `secrets` never reach logs."""
    host = urllib.parse.urlsplit(url).netloc
    wait = GAPS.get(host, 0.4) - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    job = Job(name, url, 0, needs=secrets)
    data = json.dumps(body).encode() if body else None
    headers = {"User-Agent": UA, **({"Content-Type": "application/json"} if body else {})}
    err = None
    for attempt in range(6):
        _last[host] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=90) as r:
                raw = r.read()
            break
        except urllib.error.HTTPError as e:
            err = f"http {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(redact(f"{name}: {err}", job)) from None
        except Exception as e:
            err = type(e).__name__
        time.sleep(10 * 2 ** attempt)
    else:
        raise RuntimeError(f"{name}: failed after retries: {err}")
    r0 = root()
    rel = Path("raw") / group / name / f"{n:05d}.gz"
    (r0 / rel).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(r0 / rel, "wb") as f:
        f.write(raw)
    with open(r0 / "manifest.jsonl", "a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "group": group, "name": name, "url": redact(url, job),
                            "request": body, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "path": str(rel)}) + "\n")
    return raw


def save(group, name, df, quiet=False):
    p = root() / group / f"{name}.csv.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    df.to_csv(tmp, index=False, compression={"method": "gzip"})
    tmp.replace(p)
    if not quiet:
        print(f"  {group}/{name}: {len(df):,} rows", flush=True)


def done(group, name):
    return (root() / group / f"{name}.csv.gz").exists()


def safe(s):
    return s.replace("=", "").replace("^", "").replace(":", "_")


def to_utc(ms):
    return pd.to_datetime(ms, unit="ms", utc=True)


def binance_paged(name, path, sym, key_time, parse, limit):
    rows, s, n = [], 1567296000000, 0
    sep = "&" if "?" in path else "?"
    while True:
        x = json.loads(get("crypto", name, n, f"https://fapi.binance.com/fapi/v1/{path}{sep}symbol={sym}USDT&limit={limit}&startTime={s}"))
        n += 1
        if not x:
            break
        rows += [parse(k) for k in x]
        s = key_time(x[-1]) + 1
        if len(x) < limit:
            break
    return rows


def get_crypto():
    for a in CRYPTO:
        for iv in ("4h", "1d"):
            n = f"{a}_candles_{iv}"
            if not done("crypto", n):
                r = binance_paged(n, f"klines?interval={iv}", a, lambda k: k[0],
                                  lambda k: (k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])), 1500)
                d = pd.DataFrame(r, columns="t open high low close volume_usd".split())
                d["t"] = to_utc(d.t)
                save("crypto", n, d.iloc[:-1])  # the last bar may still be open
        n = f"{a}_funding"
        if not done("crypto", n):
            r = binance_paged(n, "fundingRate", a, lambda k: k["fundingTime"], lambda k: (k["fundingTime"], float(k["fundingRate"])), 1000)
            d = pd.DataFrame(r, columns=["t", "funding"])
            d["t"] = to_utc(d.t)
            save("crypto", n, d)
        n = f"{a}_oi_4h"
        if not done("crypto", n):
            rows, cur, i = [], "", 0
            while True:
                q = f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={a}USDT&intervalTime=4h&limit=200&startTime=1567296000000&endTime={int(time.time() * 1000)}"
                x = json.loads(get("crypto", n, i, q + (f"&cursor={urllib.parse.quote(cur, safe='')}" if cur else "")))["result"]
                i += 1
                rows += [(int(k["timestamp"]), float(k["openInterest"])) for k in x["list"]]
                cur = x.get("nextPageCursor")
                if not x["list"] or not cur:
                    break
            d = pd.DataFrame(rows, columns=["t", "oi"]).drop_duplicates("t").sort_values("t")
            d["t"] = to_utc(d.t)
            save("crypto", n, d)
    for c in HL_COINS:
        n = f"hl_{safe(c)}_funding"
        if not done("crypto", n):
            rows, s, i = [], 1672531200000, 0
            while True:
                x = json.loads(get("crypto", n, i, "https://api.hyperliquid.xyz/info", {"type": "fundingHistory", "coin": c, "startTime": s}))
                i += 1
                if not x:
                    break
                rows += [(k["time"], float(k["fundingRate"]), float(k["premium"])) for k in x]
                if x[-1]["time"] + 1 <= s or len(x) < 100:
                    break
                s = x[-1]["time"] + 1
            d = pd.DataFrame(rows, columns=["t", "funding", "premium"]).drop_duplicates("t")
            d["t"] = to_utc(d.t)
            save("crypto", n, d)
    for c in ("BTC", "ETH"):
        n = f"{c}_dvol_1d"
        if not done("crypto", n):
            rows, end, i = [], int(time.time() * 1000), 0
            while True:
                r = json.loads(get("crypto", n, i, f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}&start_timestamp=1546300800000&end_timestamp={end}&resolution=1D"))["result"]
                i += 1
                rows += r["data"]
                if not r.get("continuation") or not r["data"]:
                    break
                end = r["continuation"]
            d = pd.DataFrame(rows, columns="t open high low close".split()).drop_duplicates("t").sort_values("t")
            d["t"] = to_utc(d.t)
            save("crypto", n, d)


def parse_yahoo(raw):
    """Return one row per session, dated in the exchange's timezone. Bars with no close are dropped.

    `gmtoffset` is only today's offset. Applying it to history moves daylight-saving bars to the previous day,
    so dates come from the named timezone.
    """
    r = json.loads(raw)["chart"]["result"][0]
    q, tz = r["indicators"]["quote"][0], r["meta"]["exchangeTimezoneName"]
    d = pd.DataFrame({"t": r["timestamp"], "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"], "volume": q.get("volume")})
    if r["indicators"].get("adjclose"):
        d["adjclose"] = r["indicators"]["adjclose"][0]["adjclose"]
    d["date"] = pd.to_datetime(d.t, unit="s", utc=True).dt.tz_convert(tz).dt.strftime("%Y-%m-%d")
    return d.dropna(subset=["close"]).drop(columns="t").drop_duplicates("date", keep="last")


def get_tradfi():
    """Clean tables are rebuilt from saved raw responses when those exist, so parsing fixes need no new download."""
    for s in list(MARKETS) + list(ETF_CHECK.values()) + VOL_YAHOO:
        n = safe(s)
        if done("tradfi", n):
            continue
        saved = root() / "raw" / "tradfi" / n / "00000.gz"
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?interval=1d&period1=0&period2={int(time.time())}"
        raw = gzip.open(saved).read() if saved.exists() else get("tradfi", n, 0, u)
        d = parse_yahoo(raw)
        d = d[d.date < datetime.now(timezone.utc).strftime("%Y-%m-%d")]  # today's bar may still be open
        save("tradfi", n, d[["date", "open", "high", "low", "close", "volume"] + (["adjclose"] if "adjclose" in d else [])])


def get_vol(force=False):
    for name, col in VOL_CBOE.items():
        if done("vol", name) and not force:
            continue
        raw = get("vol", name, 0, f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv")
        if raw[:1] == b"<":
            raise RuntimeError(f"{name}: got html instead of csv")
        x = pd.read_csv(io.BytesIO(raw))
        d = pd.DataFrame({"date": pd.to_datetime(x["DATE"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d"), "close": pd.to_numeric(x[col], errors="coerce")})
        save("vol", name, d.dropna(), quiet=force)


def cot_available(report_date):
    """First session a report can be used without lookahead.

    COT is measured on Tuesday and normally out on Friday afternoon, later around holidays.
    The next Monday (Tuesday + 6 days) is deliberately conservative.
    """
    return report_date + pd.Timedelta(days=6)


def get_cot(force=False):
    for sym, (_, code) in MARKETS.items():
        n = safe(sym)
        if done("cot", n) and not force:
            continue
        q = {"cftc_contract_market_code": code, "$limit": 50000, "$order": "report_date_as_yyyy_mm_dd",
             "$select": "report_date_as_yyyy_mm_dd,market_and_exchange_names,open_interest_all,noncomm_positions_long_all,noncomm_positions_short_all,comm_positions_long_all,comm_positions_short_all"}
        d = pd.DataFrame(json.loads(get("cot", n, 0, "https://publicreporting.cftc.gov/resource/6dca-aqww.json?" + urllib.parse.urlencode(q))))
        if d.empty:
            print(f"  cot/{n}: NO ROWS for code {code}", flush=True)
            continue
        for c in d.columns:
            if c.endswith("_all"):
                d[c] = pd.to_numeric(d[c])
        rep = pd.to_datetime(d.report_date_as_yyyy_mm_dd)
        out = pd.DataFrame({"report_date": rep.dt.strftime("%Y-%m-%d"), "available": cot_available(rep).dt.strftime("%Y-%m-%d"),
                            "market": d.market_and_exchange_names, "oi": d.open_interest_all,
                            "spec_long": d.noncomm_positions_long_all, "spec_short": d.noncomm_positions_short_all,
                            "comm_long": d.comm_positions_long_all, "comm_short": d.comm_positions_short_all})
        out["spec_net_pct_oi"] = (out.spec_long - out.spec_short) / out.oi
        save("cot", n, out.drop_duplicates("report_date"), quiet=force)


def dolthub_iv_year(sym, year):
    """One year of daily implied and realized volatility. Filtered by date and symbol, because wider queries time out."""
    sql = f"select date,iv_current,hv_current from volatility_history where date>='{year}-01-01' and date<'{year + 1}-01-01' and act_symbol='{sym}' order by date"
    d = json.loads(get("vol", f"IV_{sym}", int(time.time() * 10), DOLTHUB + urllib.parse.quote(sql)))
    if d.get("query_execution_status") != "Success":
        raise RuntimeError(f"dolthub {sym} {year}: {str(d.get('query_execution_message'))[:60]}")
    return [(r["date"][:10], float(r["iv_current"]) if r.get("iv_current") else None, float(r["hv_current"]) if r.get("hv_current") else None) for r in d.get("rows", [])]


def get_iv(force=False, years=None):
    this_year = datetime.now(timezone.utc).year
    for sym in IV_SYMBOLS:
        p = f"IV_{sym}"
        if done("vol", p) and not force:
            continue
        rows, failed = [], 0
        for y in years or range(2015, this_year + 1):
            try:
                rows += dolthub_iv_year(sym, y)
            except Exception as e:
                failed += 1
                print(f"  {e}", flush=True)
        if not rows:
            continue
        new = pd.DataFrame(rows, columns=["date", "iv", "hv"])
        if done("vol", p):
            new = merge_tail(pd.read_csv(root() / "vol" / f"{p}.csv.gz"), new, "date")
        save("vol", p, new, quiet=force)
        if failed:
            print(f"  {sym}: {failed} years missing", flush=True)


def refresh_dvol():
    tag, end = int(time.time()), int(time.time() * 1000)
    for c in ("BTC", "ETH"):
        n = f"{c}_dvol_1d"
        x = json.loads(get("live", n, tag, f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}&start_timestamp={end - 40 * 86400000}&end_timestamp={end}&resolution=1D"))["result"]["data"]
        d = pd.DataFrame(x, columns="t open high low close".split())
        d["t"] = to_utc(d.t).astype(str)
        save("crypto", n, merge_tail(pd.read_csv(root() / "crypto" / f"{n}.csv.gz"), d, "t"), quiet=True)


def get_macro(force=False):
    key = os.environ.get("FRED_API_KEY")
    if not key:
        print("  FRED_API_KEY missing: skipping FRED", flush=True)
    for s in FRED if key else []:
        if done("macro", s):
            continue
        u = f"https://api.stlouisfed.org/fred/series/observations?series_id={s}&api_key={key}&file_type=json"
        x = json.loads(get("macro", s, 0, u, secrets=("FRED_API_KEY",)))["observations"]
        d = pd.DataFrame({"date": [o["date"] for o in x], "value": pd.to_numeric([o["value"] for o in x], errors="coerce")}).dropna()
        save("macro", s, d)
    if force or not done("macro", "fear_greed"):
        x = json.loads(get("macro", "fear_greed", 0, "https://api.alternative.me/fng/?limit=0"))["data"]
        d = pd.DataFrame({"date": pd.to_datetime([int(o["timestamp"]) for o in x], unit="s").strftime("%Y-%m-%d"), "value": [int(o["value"]) for o in x]})
        save("macro", "fear_greed", d.sort_values("date"), quiet=force)


def get_attention(force=False):
    end = datetime.now(timezone.utc).strftime("%Y%m%d")
    for a in WIKI:
        if done("attention", a) and not force:
            continue
        u = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{a}/daily/20150701/{end}"
        x = json.loads(get("attention", a, 0, u))["items"]
        save("attention", a, pd.DataFrame({"date": [f"{o['timestamp'][:4]}-{o['timestamp'][4:6]}-{o['timestamp'][6:8]}" for o in x], "views": [o["views"] for o in x]}), quiet=force)


def merge_tail(old, new, key):
    """Add new rows to a stored table. For the same timestamp the newer row wins, since sources revise recent bars."""
    both = pd.concat([old, new], ignore_index=True)
    if key == "t":  # stored timestamps can mix whole seconds and milliseconds
        both[key] = pd.to_datetime(both[key], utc=True, format="ISO8601")
    return both.drop_duplicates(key, keep="last").sort_values(key).reset_index(drop=True)


def closed_klines(rows, now_ms):
    """Binance candles whose close time has passed. An open bar must never reach the detector."""
    return [k for k in rows if k[6] < now_ms]


def refresh_crypto():
    """Fetch the latest closed 4h bars, funding and open interest."""
    now_ms, tag = int(time.time() * 1000), int(time.time())
    for a in CRYPTO:
        n = f"{a}_candles_4h"
        x = closed_klines(json.loads(get("live", n, tag, f"https://fapi.binance.com/fapi/v1/klines?interval=4h&symbol={a}USDT&limit=60")), now_ms)
        d = pd.DataFrame([(k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[7])) for k in x], columns="t open high low close volume_usd".split())
        d["t"] = to_utc(d.t).astype(str)
        save("crypto", n, merge_tail(pd.read_csv(root() / "crypto" / f"{n}.csv.gz"), d, "t"), quiet=True)
        n = f"{a}_funding"
        x = json.loads(get("live", n, tag, f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={a}USDT&limit=30"))
        d = pd.DataFrame({"t": to_utc(pd.Series([k["fundingTime"] for k in x])).astype(str), "funding": [float(k["fundingRate"]) for k in x]})
        save("crypto", n, merge_tail(pd.read_csv(root() / "crypto" / f"{n}.csv.gz"), d, "t"), quiet=True)
        n = f"{a}_oi_4h"
        x = json.loads(get("live", n, tag, f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={a}USDT&intervalTime=4h&limit=60"))["result"]["list"]
        d = pd.DataFrame({"t": to_utc(pd.Series([int(k["timestamp"]) for k in x])).astype(str), "oi": [float(k["openInterest"]) for k in x]})
        save("crypto", n, merge_tail(pd.read_csv(root() / "crypto" / f"{n}.csv.gz"), d, "t"), quiet=True)


def get_macro_fng_and_attention():
    """Thermometer inputs that are free and small. FRED series aren't needed for it, so its key isn't used here."""
    x = json.loads(get("live", "fear_greed", int(time.time()), "https://api.alternative.me/fng/?limit=30"))["data"]
    new = pd.DataFrame({"date": pd.to_datetime([int(o["timestamp"]) for o in x], unit="s").strftime("%Y-%m-%d"), "value": [int(o["value"]) for o in x]})
    save("macro", "fear_greed", merge_tail(pd.read_csv(root() / "macro" / "fear_greed.csv.gz"), new, "date"), quiet=True)
    get_attention(force=True)


def refresh_daily(with_cot=False):
    """Fetch recent daily bars and volatility indices, and the COT reports when asked."""
    tag, today = int(time.time()), datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for s in list(MARKETS) + list(ETF_CHECK.values()) + VOL_YAHOO:
        n = safe(s)
        d = parse_yahoo(get("live", n, tag, f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}?interval=1d&range=1mo"))
        d = d[d.date < today]
        old = pd.read_csv(root() / "tradfi" / f"{n}.csv.gz")
        save("tradfi", n, merge_tail(old, d[[c for c in old.columns if c in d]], "date"), quiet=True)
    get_vol(force=True)
    get_macro_fng_and_attention()
    refresh_dvol()
    try:
        get_iv(force=True, years=[datetime.now(timezone.utc).year])
    except Exception as e:  # a third-party archive being down must not stop the rest
        print(f"  implied volatility not refreshed: {e}", flush=True)
    if with_cot:
        get_cot(force=True)


GROUPS = {"crypto": get_crypto, "tradfi": get_tradfi, "vol": get_vol, "iv": get_iv, "cot": get_cot, "macro": get_macro, "attention": get_attention}


def quality(df):
    """Facts a reader needs before trusting a series."""
    tcol = "date" if "date" in df else "report_date" if "report_date" in df else "t"
    t = pd.to_datetime(df[tcol], utc=True, format="ISO8601")
    out = {"rows": len(df), "start": t.min().strftime("%Y-%m-%d"), "end": t.max().strftime("%Y-%m-%d"),
           "dupes": int(t.duplicated().sum()), "max_gap_days": int(t.sort_values().diff().dt.days.max()) if len(t) > 1 else 0}
    if {"open", "high", "low", "close"} <= set(df.columns):
        out["nonpositive"] = int((df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum())
        out["bad_ohlc"] = int(((df.high < df[["open", "close"]].max(axis=1) * 0.9999) | (df.low > df[["open", "close"]].min(axis=1) * 1.0001)).sum())
    return out


def coverage():
    rows = []
    for p in sorted(root().glob("*/*.csv.gz")):
        rows.append({"group": p.parent.name, "name": p.name[:-7], **quality(pd.read_csv(p))})
    r = pd.DataFrame(rows).fillna(0)
    r.to_csv(root() / "coverage.csv", index=False)
    pd.set_option("display.width", 200, "display.max_rows", 500)
    print(r.to_string(index=False))
    return r


def main(argv):
    load_env()
    root().mkdir(parents=True, exist_ok=True)
    if argv and argv[0] == "get":
        failed = []
        for g in argv[1:] or GROUPS:
            print(f"== {g}", flush=True)
            try:
                GROUPS[g]()
            except Exception as e:
                failed.append(g)
                print(f"  {g} stopped: {e}", flush=True)
        print("failed groups:", failed or "none", flush=True)
        return 1 if failed else 0
    if argv and argv[0] == "coverage":
        coverage()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
