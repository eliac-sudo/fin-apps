"""Which option contracts look cheap or dear, and why. It's a model's view on delayed data: it isn't tested, and it isn't advice.

Fair value keeps the market's own smile but moves its level to what HAR forecasts for that expiry. So:
  cheap  the ask is below fair value, so a buyer pays less than the model says it's worth
  dear   the bid is above fair value, so a seller gets more than the model says it's worth
The spread is on the right side of both, so a gap smaller than the spread never counts.
"""
import gzip, json, math, os, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import option_models as M
from .events import crypto_daily, daily, read
from .recorder import BASE, UA

CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/{}.json"
DERIBIT_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={}&kind=option"
MARKETS = (
    {"key": "SPY", "name": "S&P 500", "ticker": "SPY", "job": "opt_cboe_spy", "kind": "cboe", "under": ("tradfi", "SPY"), "group": "Azioni"},
    {"key": "QQQ", "name": "Nasdaq 100", "ticker": "QQQ", "job": "opt_cboe_qqq", "kind": "cboe", "under": ("tradfi", "QQQ"), "group": "Azioni"},
    {"key": "IWM", "name": "Russell 2000", "ticker": "IWM", "job": "opt_cboe_iwm", "kind": "cboe", "under": ("tradfi", "IWM"), "group": "Azioni"},
    {"key": "TLT", "name": "Bond USA 20+ anni", "ticker": "TLT", "job": "opt_cboe_tlt", "kind": "cboe", "under": ("tradfi", "TLT"), "group": "Bond"},
    {"key": "GLD", "name": "Oro", "ticker": "GLD", "job": "opt_cboe_gld", "kind": "cboe", "under": ("tradfi", "GLD"), "group": "Materie prime"},
    {"key": "SLV", "name": "Argento", "ticker": "SLV", "job": "opt_cboe_slv", "kind": "cboe", "under": ("tradfi", "SLV"), "group": "Materie prime"},
    {"key": "USO", "name": "Petrolio", "ticker": "USO", "job": "opt_cboe_uso", "kind": "cboe", "under": ("tradfi", "USO"), "group": "Materie prime"},
    {"key": "FXE", "name": "Euro", "ticker": "FXE", "job": "opt_cboe_fxe", "kind": "cboe", "under": ("tradfi", "EURUSDX"), "group": "Forex"},
    {"key": "BTC", "name": "Bitcoin", "ticker": "BTC", "job": "opt_deribit_btc", "kind": "deribit", "under": ("crypto", "BTC"), "group": "Cripto"},
    {"key": "ETH", "name": "Ethereum", "ticker": "ETH", "job": "opt_deribit_eth", "kind": "deribit", "under": ("crypto", "ETH"), "group": "Cripto"},
)
BY_KEY = {m["key"]: m for m in MARKETS}
MIN_DAYS, MAX_DAYS = 5, 120
LIST_MIN_DAYS, LIST_MAX_DAYS = 7, 75
MAX_LOG_MONEYNESS = .5
MAX_SPREAD = .25  # of the mid price; wider quotes say little
MIN_OI = {"cboe": 50, "deribit": 5}
DELTA_RANGE = (.15, .55)  # far from the money, a small volatility gap looks like a huge percentage gap
CHEAP_BELOW, DEAR_ABOVE = .9, 1.25  # implied over forecast, chosen by judgment and not tested
FX_NOTE = "Volatilità prevista dal tasso EUR/USD, perché non ho i prezzi storici di FXE."
_memo = {}


def parse_cboe_chain(data):
    d, out = data["data"], []
    symbol = str(d.get("symbol", "")).lstrip("_")
    for o in d["options"]:
        m = re.search(r"^(.*?)(\d{6})([CP])(\d{8})$", o["option"])
        if not m or (symbol and m.group(1) != symbol):
            continue
        out.append({"code": o["option"], "expiry": datetime.strptime(m.group(2), "%y%m%d").replace(hour=20, tzinfo=timezone.utc), "is_call": m.group(3) == "C", "strike": int(m.group(4)) / 1000,
                    "bid": float(o.get("bid") or 0), "ask": float(o.get("ask") or 0), "oi": float(o.get("open_interest") or 0), "volume": float(o.get("volume") or 0)})
    return out, float(d["current_price"]), 100, None


def parse_deribit_chain(data):
    """Deribit quotes in coins. Prices are converted to dollars at each expiry's own future, which is also its forward."""
    out, spot = [], None
    for o in data["result"]:
        m = re.match(r"\w+-(\d{1,2}[A-Z]{3}\d{2})-(\d+)-([CP])$", o["instrument_name"])
        fwd = o.get("underlying_price")
        if not m or not fwd:
            continue
        spot = o.get("estimated_delivery_price") or spot
        out.append({"code": o["instrument_name"], "expiry": datetime.strptime(m.group(1).title(), "%d%b%y").replace(hour=8, tzinfo=timezone.utc), "is_call": m.group(3) == "C", "strike": float(m.group(2)),
                    "bid": float(o.get("bid_price") or 0) * fwd, "ask": float(o.get("ask_price") or 0) * fwd, "oi": float(o.get("open_interest") or 0), "volume": float(o.get("volume") or 0), "forward": float(fwd)})
    return out, spot, 1, None


PARSERS = {"cboe": parse_cboe_chain, "deribit": parse_deribit_chain}


def risk_free():
    d = read("macro", "DFF")
    return float(d.value.dropna().iloc[-1]) / 100 if d is not None and len(d) else .04


def under_closes(market):
    group, name = market["under"]
    if group == "crypto":
        d = crypto_daily(name)
    else:
        x = read(group, name)
        d = daily(x) if x is not None else None
    return None if d is None else d.close.dropna()


def vol_model(market):
    """Daily returns for the forecast, and realized volatility of the last 20 days."""
    c = under_closes(market)
    if c is None or len(c) < 260:
        return None, None, None
    year_days = 365 if market["kind"] == "deribit" else 252
    r = np.log(c[c > 0]).diff().dropna()
    return r.values, float(r.tail(20).std() * math.sqrt(year_days)), year_days


def forecast_at(returns, days, year_days):
    return M.har_forecast(returns, days if year_days == 365 else days * 252 / 365, year_days)


def analyze_chain(market, rows, spot, multiplier, snapshot, fit, realized, year_days, rate):
    """Everything about one market, as plain numbers."""
    now = snapshot
    by_exp = {}
    for r in rows:
        days = (r["expiry"] - now).total_seconds() / 86400
        if MIN_DAYS <= days <= MAX_DAYS and r["strike"] > 0:
            by_exp.setdefault(r["expiry"], []).append(r)
    expiries, contracts = [], []
    for exp, chain in sorted(by_exp.items(), key=lambda x: x[0]):
        days = (exp - now).total_seconds() / 86400
        years = days / 365
        disc = math.exp(-rate * years) if market["kind"] == "cboe" else 1.0
        calls = {r["strike"]: r for r in chain if r["is_call"] and r["bid"] > 0 and r["ask"] > 0}
        puts = {r["strike"]: r for r in chain if not r["is_call"] and r["bid"] > 0 and r["ask"] > 0}
        common = sorted(set(calls) & set(puts))
        fwd = chain[0].get("forward") or (M.forward_from_parity(common, [(calls[k]["bid"] + calls[k]["ask"]) / 2 for k in common], [(puts[k]["bid"] + puts[k]["ask"]) / 2 for k in common], disc, spot) if common else None)
        if not fwd:
            continue
        pts = []
        for r in chain:
            if r["bid"] <= 0 or r["ask"] <= r["bid"] or (r["is_call"] and r["strike"] < fwd) or (not r["is_call"] and r["strike"] > fwd):
                continue  # out of the money only: these have the cleanest prices and almost no early-exercise value
            mid = (r["bid"] + r["ask"]) / 2
            iv = M.implied_vol(mid, fwd, r["strike"], years, r["is_call"], disc)
            if iv:
                pts.append({**r, "mid": mid, "iv": iv, "k": math.log(r["strike"] / fwd), "spread": (r["ask"] - r["bid"]) / mid})
        tight = [p for p in pts if p["spread"] <= .5]
        svi = M.fit_svi([p["k"] for p in tight], [p["iv"] for p in tight], years, [1 / max(p["spread"], .01) for p in tight]) if len(tight) >= 6 else None
        atm = float(M.svi_vol(0.0, svi, years)) if svi else None
        if atm is None or not (.01 < atm < 5):
            continue
        fc = forecast_at(fit, days, year_days) if fit is not None else None
        scale = fc / atm if fc else None
        straddle = float(M.black76(fwd, fwd, years, atm, True, disc) + M.black76(fwd, fwd, years, atm, False, disc))
        expiries.append({"expiry": exp.strftime("%Y-%m-%d"), "days": round(days, 1), "forward": fwd, "atm": atm, "forecast": fc, "move_pct": 100 * straddle / fwd, "points": len(tight), "svi": svi, "discount": disc})
        for p in (x for x in pts if abs(x["k"]) <= MAX_LOG_MONEYNESS):
            curve = float(M.svi_vol(p["k"], svi, years))
            delta = float(M.delta_gamma(fwd, p["strike"], years, p["iv"], p["is_call"])[0])
            item = {"code": p["code"], "expiry": exp.strftime("%Y-%m-%d"), "days": round(days, 1), "type": "call" if p["is_call"] else "put", "strike": p["strike"], "bid": p["bid"], "ask": p["ask"], "mid": p["mid"], "iv": p["iv"], "curve_iv": curve,
                    "off_curve": 100 * (p["iv"] - curve), "delta": delta, "oi": p["oi"], "volume": p["volume"], "spread_pct": 100 * p["spread"]}
            if scale:
                fair_iv = curve * scale
                fair = float(M.black76(fwd, p["strike"], years, fair_iv, p["is_call"], disc))
                item.update(fair=fair, fair_iv=fair_iv)
                item["verdict"] = "economica" if p["ask"] < fair else "cara" if p["bid"] > fair else "neutra"
                item["gap_pct"] = 100 * (fair - p["ask"]) / p["ask"] if p["ask"] < fair else 100 * (p["bid"] - fair) / fair if p["bid"] > fair else 0.0
                if item["verdict"] != "neutra":  # volatility points, at the price you'd really trade
                    side = M.implied_vol(p["ask"] if item["verdict"] == "economica" else p["bid"], fwd, p["strike"], years, p["is_call"], disc)
                    item["gap_vol"] = 100 * abs(fair_iv - side) if side else 0.0
            contracts.append(item)
    if not expiries:
        return None
    near = min(expiries, key=lambda e: abs(e["days"] - 30))
    ratio = near["atm"] / near["forecast"] if near["forecast"] else None
    label = None if ratio is None else "economiche" if ratio < CHEAP_BELOW else "care" if ratio > DEAR_ABOVE else "nella norma"
    tradable = [c for c in contracts if LIST_MIN_DAYS <= c["days"] <= LIST_MAX_DAYS and c["spread_pct"] <= 100 * MAX_SPREAD and c["oi"] >= MIN_OI[market["kind"]] and DELTA_RANGE[0] <= abs(c["delta"]) <= DELTA_RANGE[1] and c.get("verdict")]
    cheap = sorted((c for c in tradable if c["verdict"] == "economica"), key=lambda c: -c.get("gap_vol", 0))
    dear = sorted((c for c in tradable if c["verdict"] == "cara"), key=lambda c: -c.get("gap_vol", 0))
    smile_rows = [c for c in contracts if c["expiry"] == near["expiry"]]
    return {"key": market["key"], "name": market["name"], "ticker": market["ticker"], "group": market["group"], "spot": spot, "snapshot": snapshot.isoformat(timespec="seconds"), "source": source_of(market),
            "note": FX_NOTE if market["key"] == "FXE" else None, "near": near, "ratio": ratio, "label": label, "realized": realized, "expiries": expiries, "cheap": cheap[:15], "dear": dear[:15], "n_cheap": len(cheap), "n_dear": len(dear), "n_tradable": len(tradable),
            "smile": sorted(smile_rows, key=lambda c: c["strike"]), "gex": gex_part(rows, spot, multiplier, now, contracts), "model": worked_example(cheap, dear, contracts, expiries, fit, year_days, rate)}


def worked_example(cheap, dear, contracts, expiries, returns, year_days, rate):
    """One real contract through every step of the model, using the same numbers the tables use. The app shows this as the method's proof."""
    near = min(expiries, key=lambda e: abs(e["days"] - 30))
    usable = [c for c in contracts if c.get("fair") is not None]
    pick = (cheap or dear or sorted((c for c in usable if c["expiry"] == near["expiry"]), key=lambda c: abs(abs(c["delta"]) - .3)) or usable or [None])[0]
    if pick is None:
        return {"rate": rate, "year_days": year_days, "example": None}
    e = next(x for x in expiries if x["expiry"] == pick["expiry"])
    years, k = e["days"] / 365, math.log(pick["strike"] / e["forward"])
    sq = pick["fair_iv"] * math.sqrt(years)
    d1 = (math.log(e["forward"] / pick["strike"]) + .5 * sq * sq) / sq
    har = M.har_detail(returns, e["days"] if year_days == 365 else e["days"] * 252 / 365, year_days) if returns is not None else None
    return {"rate": rate, "year_days": year_days, "har": har, "example": {**pick, "forward": e["forward"], "atm": e["atm"], "forecast": e["forecast"], "discount": e["discount"], "years": years, "k": k, "svi": dict(zip(("a", "b", "rho", "m", "sigma"), e["svi"])), "scale": e["forecast"] / e["atm"], "d1": d1, "d2": d1 - sq}}


def gex_part(rows, spot, multiplier, now, contracts):
    """Gamma exposure by strike. Who holds what isn't known: the usual assumption is that dealers are long calls and short puts."""
    use = [r for r in rows if r["oi"] > 0 and MIN_DAYS <= (r["expiry"] - now).total_seconds() / 86400 <= MAX_DAYS]
    vols = {(c["expiry"]): {} for c in contracts}
    for c in contracts:
        vols[c["expiry"]][c["strike"]] = c["curve_iv"]
    k, call, oi, iv, yrs = [], [], [], [], []
    for r in use:
        table = vols.get(r["expiry"].strftime("%Y-%m-%d"))
        if not table:
            continue
        near = min(table, key=lambda s: abs(s - r["strike"]))
        k.append(r["strike"]); call.append(r["is_call"]); oi.append(r["oi"]); iv.append(table[near]); yrs.append((r["expiry"] - now).total_seconds() / 86400 / 365)
    if not k:
        return None
    k, call, oi, iv, yrs = map(np.array, (k, call, oi, iv, yrs))
    g = M.gex_by_strike(k, call, oi, iv, yrs, spot, multiplier)
    signed = np.where(call, g, -g)
    total = float(signed.sum())
    frame = pd.DataFrame({"strike": k, "call": np.where(call, g, 0), "put": np.where(call, 0, g)}).groupby("strike").sum().reset_index()
    window = frame[(frame.strike >= spot * .8) & (frame.strike <= spot * 1.2)]
    top = window.assign(size=window.call + window.put).nlargest(40, "size").sort_values("strike")
    c_oi, p_oi = float(oi[call].sum()), float(oi[~call].sum())
    return {"total": total, "regime": "positiva" if total > 0 else "negativa", "flip": M.gamma_flip(k, call, oi, iv, yrs, spot, multiplier), "call_wall": float(window.loc[window.call.idxmax(), "strike"]) if len(window) else None,
            "put_wall": float(window.loc[window.put.idxmax(), "strike"]) if len(window) else None, "max_pain": M.max_pain(k, call, oi), "put_call_oi": p_oi / c_oi if c_oi else None,
            "by_strike": [{"strike": float(a), "call": float(b), "put": float(c)} for a, b, c in zip(top.strike, top.call, top.put)]}


def source_of(m):
    if m["kind"] == "deribit":
        return {"name": "Deribit", "url": f"https://www.deribit.com/options/{m['ticker']}", "delay": "prezzi in tempo reale al momento del salvataggio", "buy": "Si comprano su Deribit, dove il codice è quello in tabella. Non si comprano su Hyperliquid."}
    return {"name": "Cboe", "url": f"https://www.cboe.com/delayed_quotes/{m['ticker'].lower()}/quote_table", "delay": "prezzi ritardati di circa 15 minuti", "buy": f"Opzioni USA su {m['ticker']}: si comprano da un broker con accesso alle opzioni americane, cercando {m['ticker']}, scadenza, strike e tipo. Non si comprano su Hyperliquid."}


def latest_file(job, root=None):
    base = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw" / job
    files = sorted(base.glob("*/*.gz"), key=lambda p: (p.parent.name, p.name))
    return files[-1] if files else None


def from_saved(market, root=None):
    f = latest_file(market["job"], root)
    if not f:
        return None
    key = (market["key"], str(f))
    if key not in _memo:
        snap = datetime.strptime(f.parent.name + f.name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc)
        _memo[key] = build(market, json.load(gzip.open(f)), snap)
    return _memo[key]


def fetch_live(market):
    """A fresh chain on request, for checking prices before acting. Not saved: the archive stays the recorder's job."""
    url = DERIBIT_URL.format(market["ticker"]) if market["kind"] == "deribit" else CBOE_URL.format(market["ticker"])
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return build(market, json.load(r), datetime.now(timezone.utc))


def build(market, data, snapshot):
    rows, spot, mult, _ = PARSERS[market["kind"]](data)
    if not rows or not spot:
        return None
    fit, realized, year_days = vol_model(market)
    return analyze_chain(market, rows, spot, mult, snapshot, fit, realized, year_days or 252, risk_free())


def all_markets(root=None):
    """The summary for every market with a saved chain."""
    out = []
    for m in MARKETS:
        try:
            r = from_saved(m, root)
        except Exception as e:
            r = {"key": m["key"], "name": m["name"], "error": type(e).__name__}
        if r:
            out.append(r)
    return out
