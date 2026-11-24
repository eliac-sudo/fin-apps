"""Telegram commands that show the app's basics: /oggi, /ticker, /alert, /bot, /test, /aiuto (and /piano, in bzd.plan).

They read the app's own data (http://127.0.0.1:8787, cached), so Telegram and the app say the same thing. They only read: nothing here trades or
changes the Deribit bot; pausing or closing it stays in the app.
"""
import html, json, os, urllib.request

APP_URL = os.environ.get("BZD_APP_URL", "http://127.0.0.1:8787")
HELP = ("Comandi:\n"
        "/oggi: la frase del giorno, la forza per gruppo, chi sale o scende forte\n"
        "/ticker BTC: un mercato in breve (anche oro, petrolio, S&amp;P…)\n"
        "/alert: gli ultimi alert\n"
        "/bot: il bot Deribit\n"
        "/test: cosa ha retto ai test\n"
        "/piano BTC 5000: dimensione, stop e obiettivo\n\n"
        "Tutto in sola lettura. Il dettaglio è nell'app.")
NAMES = {"oro": "GC=F", "gold": "GC=F", "argento": "SI=F", "silver": "SI=F", "petrolio": "CL=F", "oil": "CL=F", "rame": "HG=F", "gas": "NG=F",
         "sp500": "ES=F", "s&p": "ES=F", "spx": "ES=F", "nasdaq": "NQ=F", "russell": "RTY=F", "mais": "ZC=F", "grano": "ZW=F", "soia": "ZS=F",
         "eur": "EURUSD=X", "eurusd": "EURUSD=X", "euro": "EURUSD=X", "jpy": "USDJPY=X", "usdjpy": "USDJPY=X", "yen": "USDJPY=X", "gbp": "GBPUSD=X",
         "gbpusd": "GBPUSD=X", "aud": "AUDUSD=X", "audusd": "AUDUSD=X", "chf": "USDCHF=X", "usdchf": "USDCHF=X", "cad": "USDCAD=X", "usdcad": "USDCAD=X",
         "bond": "ZN=F", "10y": "ZN=F", "tlt": "ZB=F", "30y": "ZB=F"}
UNAVAILABLE = "L'app non risponde ora (si sta avviando o è ferma). Riprova tra un minuto."


def fetch(path, timeout=90):
    with urllib.request.urlopen(APP_URL + path, timeout=timeout) as r:
        return json.load(r)


def esc(x):
    return html.escape(str(x), quote=False)


def pct(x, digits=1):
    return "n.d." if x is None else f"{x:+.{digits}f}%".replace(".", ",")


def find_market(snap, word):
    """By the app's label or code (BTC, Oro, GC=F), or by a common name."""
    w = word.strip().lower()
    code = NAMES.get(w, w)
    for m in snap.get("markets", []):
        if code in (m["market"].lower(), m["label"].lower()) or NAMES.get(w) == m["market"]:
            return m
    return None


def oggi(snap):
    out = ["📅 <b>Oggi</b>"]
    if snap.get("overview"):
        out.append(esc(snap["overview"]))
    out += [""] + ["• " + esc(b["text"]) for b in snap.get("briefing", [])]
    classes = snap.get("classes") or {}
    if classes:
        out += ["", "<b>Forza</b> (0–100 rispetto alla propria storia)"]
        out += [f"• {esc(c['name'])}: {c['heat']:.0f}, {esc(c['band'])}" + (f" ({c['change_7d']:+.0f} in 7g)" if c.get("change_7d") is not None else "")
                for c in classes.values() if c.get("heat") is not None]
    return "\n".join(out)


def ticker(snap, words):
    if not words:
        return "Scrivi il mercato, per esempio: /ticker BTC oppure /ticker oro"
    m = find_market(snap, " ".join(words))
    if not m:
        names = ", ".join(x["label"] for x in snap.get("markets", []))
        return f"Non trovo «{esc(' '.join(words))}». Mercati seguiti: {esc(names)}.\nPer gli altri c'è la ricerca nell'app."
    r, pos = m.get("returns") or {}, m.get("position") or {}
    out = [f"📈 <b>{esc(m['label'])}</b> · {m['price']:,.6g}".replace(",", " "),
           f"Variazione: 1g {pct(r.get('1g'))}, 7g {pct(r.get('7g'))}, 30g {pct(r.get('30g'))}"]
    if m.get("heat") is not None:
        out.append(f"Forza: {m['heat']:.0f}/100, {esc(m.get('band', ''))}")
    if pos:
        out.append(f"Prezzo: {esc(pos['label'])} rispetto all'ultimo anno ({pct(pos.get('from_high'), 0)} dal massimo, {pct(pos.get('from_low'), 0)} dal minimo)")
    tag = ((m.get("zones") or {}).get("1d") or {}).get("tag")
    if tag in ("GIU", "SU"):
        out.append("Momentum giornaliero: " + ("▼ scende forte" if tag == "GIU" else "▲ sale forte"))
    tech = next((t for t in snap.get("technical", []) if t["market"] == m["market"]), None)
    if tech:
        frames = (("1M", "mensile"), ("1w", "settimanale"), ("1d", "giornaliero"))
        out.append("Trend: " + ", ".join(f"{name} {tech['trend'][tf]}" for tf, name in frames if tech["trend"].get(tf)))
        rsi = tech["rsi"].get("1d")
        if rsi is not None:
            out.append(f"RSI giornaliero {rsi:.0f}" + (" (ipervenduto)" if rsi <= 30 else " (ipercomprato)" if rsi >= 70 else ""))
    recent = [a for a in (snap.get("alerts") or {}).get("setups", []) if a["market"] == m["market"]][-1:]
    for a in recent:
        out.append(f"Ultimo alert: {esc(a['setup'])} del {a['trigger'][8:10]}/{a['trigger'][5:7]}")
    return "\n".join(out) + "\n\nGrafico, livelli, opzioni e chi compra nell'app."


def last_alerts(snap, n=5):
    al = snap.get("alerts") or {}
    rows = [(a["trigger"], f"🧪 {esc(a['setup'])} su {esc(a.get('label') or a['market'])}") for a in al.get("setups", [])]
    rows += [(a["at"], f"⚡ {esc(a['label'])} {pct(a['pct'])} in {esc(a['window'])}") for a in al.get("moves", [])]
    rows += [(r.get("at") or r.get("trigger") or "", f"🔄 reset {esc(r.get('label') or r.get('market', ''))}") for r in al.get("resets", [])]
    rows = sorted((r for r in rows if r[0]), reverse=True)[:n]
    if not rows:
        return "Nessun alert registrato."
    return "<b>Ultimi alert</b>\n" + "\n".join(f"{t[8:10]}/{t[5:7]} {t[11:16]} · {txt}" for t, txt in rows)


def bot(view):
    out = []
    for b in view.get("bots", []):
        s = b.get("status") or {}
        out.append(f"🤖 <b>{esc(b['name'])}</b> ({esc(b['venue'])}, {'testnet' if s.get('net') == 'test' else 'conto vero'}): {esc(b['state'])}")
        if s.get("equity") is not None:
            out.append(f"Conto: {s['equity']:,.0f} USDC".replace(",", " "))
        opts = s.get("options") or []
        out.append(f"Opzioni aperte: {len(opts)}" + (f", perpetuo {s.get('perp', 0):+.3f} BTC, delta netto {s.get('net_delta', 0):+.3f}" if opts or s.get("perp") else ""))
        for flag, text in (("paused", "in pausa"), ("halted", "fermato dal limite di rischio"), ("blocked", "bloccato"), ("error", "errore")):
            if s.get(flag):
                out.append(f"⚠️ {text}" + (f": {esc(s[flag])}" if isinstance(s[flag], str) else ""))
        ev = (b.get("events") or [])[-1:]
        for e in ev:
            out.append(f"Ultimo evento: {esc(e['event'])} il {e['t'][8:10]}/{e['t'][5:7]} {e['t'][11:16]} UTC")
    return "\n".join(out) + "\n\nPausa, dimensione e chiusura si comandano dall'app." if out else "Nessun bot configurato."


def tests(snap):
    out = ["<b>Cosa ha retto ai test</b>"]
    for t in snap.get("tests") or []:
        if t.get("outcome") == "supportata":
            out.append(f"✅ {esc(t['setup_name'])} {esc(t['class_name'])}: {esc(t['reading'][0])}")
    for rid, v in (snap.get("verdicts") or {}).items():
        if v.get("outcome") == "supportata":
            out.append(f"✅ {esc(rid)}: {esc(v['line'])}")
    if len(out) == 1:
        out.append("Nessuna ipotesi ha retto.")
    out.append("\nTutto il resto non ha retto o non è testato: l'elenco completo è nella scheda Test.")
    return "\n".join(out)


def answer(cmd, words, get=fetch):
    """The reply text for a command, or None if it isn't one of ours."""
    if cmd in ("/aiuto", "/help", "/start"):
        return HELP
    if cmd not in ("/oggi", "/ticker", "/alert", "/bot", "/test"):
        return None
    try:
        if cmd == "/bot":
            return bot(get("/api/bots", timeout=15))
        snap = get("/api/snapshot")
    except Exception:
        return UNAVAILABLE
    return {"/oggi": lambda: oggi(snap), "/ticker": lambda: ticker(snap, words), "/alert": lambda: last_alerts(snap), "/test": lambda: tests(snap)}[cmd]()
