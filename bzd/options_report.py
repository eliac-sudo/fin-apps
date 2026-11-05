"""A separate, structured options message: each market against its own past. It describes, it doesn't predict.

    python -m bzd.options_report           print it
    python -m bzd.options_report --send    also send it to Telegram

Costs nothing: no LLM. GEX stays out of this message, because its sign rests on an assumption and it proved unstable.
"""
import html, re, sys
from datetime import datetime, timezone

import numpy as np

from . import indicators as I
from .events import crypto_daily, daily, read
from .option_models import har_forecast
from .recorder import load_env

BLOCKS = (
    {"name": "Azioni USA", "index": ("vol", "VIX", "VIX"), "underlying": ("tradfi", "SPY", 252), "iv": "SPY", "chain": "SPY", "short": "VIX9D", "long": "VIX3M", "tail": "SKEW"},
    {"name": "Bond USA", "index": ("tradfi", "MOVE", "MOVE"), "underlying": ("tradfi", "TLT", 252), "iv": "TLT", "chain": "TLT"},
    {"name": "Oro", "index": ("vol", "GVZ", "GVZ"), "underlying": ("tradfi", "GLD", 252), "iv": "GLD", "chain": "GLD"},
    {"name": "Petrolio", "index": ("vol", "OVX", "OVX"), "underlying": ("tradfi", "USO", 252), "iv": "USO", "chain": "USO"},
    {"name": "Euro/dollaro", "iv": "FXE", "chain": "FXE"},
    {"name": "Bitcoin", "index": ("crypto", "BTC_dvol_1d", "DVOL"), "underlying": ("crypto", "BTC", 365), "chain": "BTC"},
    {"name": "Ethereum", "index": ("crypto", "ETH_dvol_1d", "DVOL"), "underlying": ("crypto", "ETH", 365), "chain": "ETH"},
)


def level(p):
    return "molto bassa" if p < 20 else "bassa" if p < 40 else "media" if p < 60 else "alta" if p < 80 else "molto alta"


def index_series(group, name):
    d = read(group, name)
    if d is None:
        return None
    if "date" not in d:
        d = d.assign(date=d.t.str[:10])
    return daily(d).close.dropna()


def close_series(group, name):
    """Daily closes of the market under the options."""
    if group == "crypto":
        d = crypto_daily(name)
        return None if d is None else d.close.dropna()
    return index_series(group, name)


def level_line(block):
    if "index" not in block:
        return None
    s = index_series(*block["index"][:2])
    if s is None or len(s) < 101:
        return None
    p = I.past_percentile(s).iloc[-1]
    return {"label": block["index"][2], "value": float(s.iloc[-1]), "pct": float(p), "date": s.index[-1]}


def iv_line(sym):
    d = read("vol", f"IV_{sym}")
    if d is None or len(d) < 101:
        return None
    iv = daily(d).iv.dropna()
    hv = daily(d).hv.dropna()
    return {"iv": float(iv.iloc[-1]), "hv": float(hv.iloc[-1]) if len(hv) else None, "pct": float(I.past_percentile(iv).iloc[-1]), "date": iv.index[-1]}


RV_DAYS = 20
CHEAP_BELOW, DEAR_ABOVE = .9, 1.25  # chosen by judgment, not tested: implied usually sits a little above what follows


def realized_vol(close, year_days):
    r = np.log(close.dropna().tail(RV_DAYS + 1)).diff().dropna()
    return float(r.std() * np.sqrt(year_days)) if len(r) == RV_DAYS else None


def forecast_vol(close, year_days, days=30):
    """HAR forecast for about a month, from option_models."""
    r = np.log(close.dropna()[lambda x: x > 0]).diff().dropna().values
    return har_forecast(r, days if year_days == 365 else 21, year_days)


def price_of_options(block, chain):
    """Are options dear or cheap? Implied volatility at 30 days against how much the market is forecast to move."""
    if not (chain and chain.get("iv_30d") and block.get("underlying")):
        return None
    group, name, year_days = block["underlying"]
    s = close_series(group, name)
    fc = forecast_vol(s, year_days) if s is not None else None
    if not fc:
        return None
    ratio = chain["iv_30d"] / fc
    return {"iv": chain["iv_30d"], "rv": fc, "ratio": ratio, "label": "economiche" if ratio < CHEAP_BELOW else "care" if ratio > DEAR_ABOVE else "nella norma"}


def term_line(block, chain):
    """Is near-term fear above longer-term fear?"""
    if block.get("short"):
        a, b = index_series("vol", block["short"]), index_series("vol", block["long"])
        if a is not None and b is not None:
            r = float(a.iloc[-1] / b.iloc[-1])
            state = "breve sopra lunga: paura immediata" if r > 1 else "normale"
            return f"Breve contro lunga: {state} ({block['short']} {a.iloc[-1]:.1f}, {block['long']} {b.iloc[-1]:.1f})"
    if chain and chain.get("iv_7d") and chain.get("iv_30d"):
        state = "breve sopra lunga: paura immediata" if chain["term_inverted"] else "normale"
        return f"Breve contro lunga: {state} (7g {chain['iv_7d']:.0%}, 30g {chain['iv_30d']:.0%})"
    return None


def skew_line(block, chain):
    parts = []
    if chain and chain.get("skew_25d") is not None:
        s = chain["skew_25d"] * 100
        side = "put più care delle call" if s > 1 else "call più care delle put" if s < -1 else "put e call simili"
        parts.append(f"{side} ({s:+.1f} pt)")
    if block.get("tail"):
        t = index_series("vol", block["tail"])
        if t is not None and len(t) > 100:
            parts.append(f"SKEW {t.iloc[-1]:.0f}, {level(I.past_percentile(t).iloc[-1])}")
    return "Protezione dai ribassi: " + " · ".join(parts) if parts else None


MARKET_BLOCK = {"crypto": "Bitcoin", "ETH": "Ethereum", "equities": "Azioni USA", "bonds": "Bond USA", "GC=F": "Oro", "CL=F": "Petrolio", "EURUSD=X": "Euro/dollaro"}


def block_lines(b):
    """The lines for one market, its percentile if there is one, and what its options cost."""
    lines, pct = [], None
    try:
        chain = I.latest_options(b["chain"]) if b.get("chain") else None
    except Exception:
        chain = None
    lv, iv = level_line(b), iv_line(b["iv"]) if b.get("iv") else None
    if lv:
        lines.append(f"Volatilità attesa: <b>{level(lv['pct'])}</b> ({lv['label']} {lv['value']:.1f} del {lv['date']:%d/%m}, {lv['pct']:.0f}° percentile)")
        pct = lv["pct"]
    elif iv:
        lines.append(f"Volatilità attesa: <b>{level(iv['pct'])}</b> (IV {iv['iv']:.0%}, {iv['pct']:.0f}° percentile)")
        pct = iv["pct"]
    if iv and iv.get("hv"):
        gap = "sopra" if iv["iv"] > iv["hv"] else "sotto"
        lines.append(f"Attesa contro realizzata: {gap} (IV {iv['iv']:.0%}, realizzata {iv['hv']:.0%}, dato del {iv['date']:%d/%m})")
    cost = price_of_options(b, chain)
    if cost:
        lines.append(f"Prezzo opzioni: <b>{cost['label']}</b> (attesa {cost['iv']:.0%} contro prevista {cost['rv']:.0%}, {cost['ratio']:.1f}x)")
    for extra in (term_line(b, chain), skew_line(b, chain)):
        if extra:
            lines.append(extra)
    return lines, pct, cost


def options_note(markets):
    """The options context for an alert: `markets` is a list of (class, market). Empty if there's no data, so it can never hold an alert back."""
    names = []
    for cls, market in markets:
        name = MARKET_BLOCK.get(market) or MARKET_BLOCK.get(cls)
        if name and name not in names:
            names.append(name)
    out = []
    for b in BLOCKS:
        if b["name"] in names:
            try:
                lines = block_lines(b)[0]
            except Exception:
                lines = []
            if lines:
                out += [f"<b>{b['name']}</b>"] + [f"• {x}" for x in lines]
    return "\n".join(["📊 Opzioni (contesto, non testato come segnale)"] + out) if out else ""


def build_report(now=None):
    now = now or datetime.now(timezone.utc)
    out, ranks, costs = [], [], []
    for b in BLOCKS:
        lines, pct, cost = block_lines(b)
        if pct is not None:
            ranks.append((pct, b["name"]))
        if cost:
            costs.append((cost["ratio"], b["name"]))
        if lines:
            out += ["", f"<b>{b['name']}</b>"] + [f"• {x}" for x in lines]
    head = [f"📊 <b>Opzioni</b> · {now:%d/%m %H:%M} UTC", "Quanta paura prezzano le opzioni, rispetto al passato di ogni mercato."]
    if ranks:
        ranks.sort()
        head.append(f"Più tesa: {ranks[-1][1]}. Più calma: {ranks[0][1]}.")
    if costs:
        costs.sort()
        head.append(f"Opzioni più care rispetto al movimento previsto: {costs[-1][1]}. Più economiche: {costs[0][1]}.")
    return "\n".join(head + out + ["", "Solo descrittivo: non è testato come segnale e non è consulenza finanziaria."])


def main(argv):
    load_env()
    text = build_report()
    print(re.sub(r"</?b>", "", html.unescape(text)))
    if "--send" in argv:
        from .alerts import send_text, split_message
        for part in split_message(text):
            send_text(part)
        print("\n[inviato]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
