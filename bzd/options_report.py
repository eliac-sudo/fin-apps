"""A separate, structured options message: each market against its own past. It describes, it doesn't predict.

    python -m bzd.options_report           print it
    python -m bzd.options_report --send    also send it to Telegram

Costs nothing: no LLM. GEX stays out of this message, because its sign rests on an assumption and it proved unstable.
"""
import html, re, sys
from datetime import datetime, timezone

from . import indicators as I
from .events import daily, read
from .recorder import load_env

BLOCKS = (
    {"name": "Azioni USA", "index": ("vol", "VIX", "VIX"), "iv": "SPY", "chain": "SPY", "short": "VIX9D", "long": "VIX3M", "tail": "SKEW"},
    {"name": "Bond USA", "index": ("tradfi", "MOVE", "MOVE"), "iv": "TLT", "chain": "TLT"},
    {"name": "Oro", "index": ("vol", "GVZ", "GVZ"), "iv": "GLD", "chain": "GLD"},
    {"name": "Petrolio", "index": ("vol", "OVX", "OVX"), "iv": "USO", "chain": "USO"},
    {"name": "Euro/dollaro", "iv": "FXE", "chain": "FXE"},
    {"name": "Bitcoin", "index": ("crypto", "BTC_dvol_1d", "DVOL"), "chain": "BTC"},
    {"name": "Ethereum", "index": ("crypto", "ETH_dvol_1d", "DVOL"), "chain": "ETH"},
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


def build_report(now=None):
    now = now or datetime.now(timezone.utc)
    out, ranks = [], []
    for b in BLOCKS:
        lines = []
        try:
            chain = I.latest_options(b["chain"]) if b.get("chain") else None
        except Exception:
            chain = None
        lv, iv = level_line(b), iv_line(b["iv"]) if b.get("iv") else None
        if lv:
            lines.append(f"Volatilità attesa: <b>{level(lv['pct'])}</b> ({lv['label']} {lv['value']:.1f}, {lv['pct']:.0f}° percentile)")
            ranks.append((lv["pct"], b["name"]))
        elif iv:
            lines.append(f"Volatilità attesa: <b>{level(iv['pct'])}</b> (IV {iv['iv']:.0%}, {iv['pct']:.0f}° percentile)")
            ranks.append((iv["pct"], b["name"]))
        if iv and iv.get("hv"):
            gap = "sopra" if iv["iv"] > iv["hv"] else "sotto"
            lines.append(f"Attesa contro realizzata: {gap} (IV {iv['iv']:.0%}, realizzata {iv['hv']:.0%}, dato del {iv['date']:%d/%m})")
        for extra in (term_line(b, chain), skew_line(b, chain)):
            if extra:
                lines.append(extra)
        if lines:
            out += ["", f"<b>{b['name']}</b>"] + [f"• {x}" for x in lines]
    head = [f"📊 <b>Opzioni</b> · {now:%d/%m %H:%M} UTC", "Quanta paura prezzano le opzioni, rispetto al passato di ogni mercato."]
    if ranks:
        ranks.sort()
        head.append(f"Più tesa: {ranks[-1][1]}. Più calma: {ranks[0][1]}.")
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
