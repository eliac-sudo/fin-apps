"""A3: how much to buy, where to get out, before entering. You place the orders by hand: this never trades.

    python -m bzd.plan BTC 5000                 rule stop, 1% risk
    python -m bzd.plan oro 5000 0.5 stop 3900 target 2 leva 3
    On Telegram, the same words after /piano

It reads public prices only. Every plan is logged to data/alerts/plans.jsonl.
"""
import gzip, json, math, os, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import exits as X
from .recorder import BASE, UA, load_env
from .setups import load_crypto, load_daily

INFO_URL = "https://api.hyperliquid.xyz/info"
CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK"}
XYZ = {"xyz:SP500": "ES=F", "xyz:XYZ100": "NQ=F", "xyz:CL": "CL=F", "xyz:GOLD": "GC=F", "xyz:SILVER": "SI=F", "xyz:COPPER": "HG=F",
       "xyz:EUR": "EURUSD=X", "xyz:JPY": "USDJPY=X", "xyz:GBP": "GBPUSD=X", "xyz:TLT": "ZB=F"}
ALIASES = {"sp500": "xyz:SP500", "s&p": "xyz:SP500", "es": "xyz:SP500", "nasdaq": "xyz:XYZ100", "nq": "xyz:XYZ100", "xyz100": "xyz:XYZ100",
           "petrolio": "xyz:CL", "oil": "xyz:CL", "cl": "xyz:CL", "oro": "xyz:GOLD", "gold": "xyz:GOLD", "argento": "xyz:SILVER", "silver": "xyz:SILVER",
           "rame": "xyz:COPPER", "copper": "xyz:COPPER", "eur": "xyz:EUR", "eurusd": "xyz:EUR", "euro": "xyz:EUR", "jpy": "xyz:JPY", "usdjpy": "xyz:JPY",
           "gbp": "xyz:GBP", "gbpusd": "xyz:GBP", "tlt": "xyz:TLT", "bond": "xyz:TLT"}
LABELS = {"xyz:SP500": "S&amp;P 500", "xyz:XYZ100": "Nasdaq 100", "xyz:CL": "Petrolio", "xyz:GOLD": "Oro", "xyz:SILVER": "Argento", "xyz:COPPER": "Rame",
          "xyz:EUR": "EUR/USD", "xyz:JPY": "USD/JPY", "xyz:GBP": "GBP/USD", "xyz:TLT": "TLT"}
USAGE = ("Scrivi: /piano MERCATO CAPITALE [RISCHIO%] [stop PREZZO] [target R] [leva X] [entrata PREZZO]\n"
         "Esempi:\n/piano BTC 5000\n/piano oro 5000 0.5 stop 3900 leva 3\n\nSenza stop uso la regola fissata prima dei test. Rischio predefinito: 1%.")
WIDE_STOP, MAX_SANE_RISK = .10, 2
MIN_ORDER_USD = 10
TIME_EXIT = {"crypto": "14 giorni", "other": "20 sedute"}  # max_hold_bars in config/exits_v1.json
TEST_NOTE = ("Nel test sul panico cripto, stop + 3R ha tagliato il peggior 10% dei casi (−1.11R contro −3.88R), "
             "ma ha reso meno del tenere senza stop (−0.02R contro +0.31R). È una scelta contro i disastri e contro il greed, non per guadagnare di più.")


class PlanError(ValueError):
    """A message for the user, in Italian."""


def number(text, what):
    try:
        x = float(text.replace(",", "."))
    except ValueError:
        raise PlanError(f"{what}: «{text}» non è un numero.\n\n{USAGE}") from None
    if not math.isfinite(x) or x <= 0:
        raise PlanError(f"{what} deve essere maggiore di zero.")
    return x


def parse_request(words):
    """MARKET CAPITAL [RISK] then keyword pairs. The capital can come from BZD_CAPITAL."""
    if not words:
        raise PlanError(USAGE)
    req = {"market": words[0], "target_r": 3.0, "risk_pct": 1.0}
    rest, keys = list(words[1:]), {"stop": "stop", "target": "target_r", "leva": "leverage", "entrata": "entry"}
    names = {"stop": "Stop", "target": "Target", "leva": "Leva", "entrata": "Entrata"}
    positional = []
    while rest and rest[0].lower() not in keys:
        positional.append(rest.pop(0))
    if len(rest) % 2 or len(positional) > 2:
        raise PlanError(USAGE)
    for key, value in zip(rest[::2], rest[1::2]):
        if key.lower() not in keys:
            raise PlanError(USAGE)
        req[keys[key.lower()]] = number(value, names[key.lower()])
    if positional:
        req["capital"] = number(positional[0], "Capitale")
    elif os.environ.get("BZD_CAPITAL"):
        req["capital"] = number(os.environ["BZD_CAPITAL"], "Capitale")
    else:
        raise PlanError(USAGE)
    if len(positional) == 2:
        req["risk_pct"] = number(positional[1].rstrip("%"), "Rischio")
    return req


def resolve(name):
    up = name.strip().upper()
    if up in CRYPTO:
        return up
    low = name.strip().lower()
    if low in ALIASES:
        return ALIASES[low]
    if low.startswith("xyz:") and f"xyz:{up[4:]}" in XYZ:
        return f"xyz:{up[4:]}"
    raise PlanError(f"Mercato «{name}» non seguito. Puoi usare: {', '.join(sorted(CRYPTO))}, sp500, nasdaq, oro, argento, rame, petrolio, eur, jpy, gbp, tlt.")


def parse_hl(body, name):
    meta, ctx = body
    for a, x in zip(meta["universe"], ctx):
        if a["name"] == name and x.get("markPx"):
            return {"mark": float(x["markPx"]), "funding": float(x.get("funding") or 0), "max_leverage": int(a["maxLeverage"]), "decimals": int(a["szDecimals"])}
    return None


def snapshot_body(name, root=None):
    base = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw" / ("hl_ctx_xyz" if name.startswith("xyz:") else "hl_ctx_main")
    files = sorted(base.glob("*/*.gz"), key=lambda p: (p.parent.name, p.name))
    if not files:
        return None, None
    when = datetime.strptime(files[-1].parent.name + files[-1].name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc)
    return json.load(gzip.open(files[-1])), when


def market_info(name, now=None):
    """Live public price, or the recorder's last snapshot if it's under an hour old. No price means no plan."""
    now = now or datetime.now(timezone.utc)
    q = {"type": "metaAndAssetCtxs", **({"dex": "xyz"} if name.startswith("xyz:") else {})}
    try:
        req = urllib.request.Request(INFO_URL, json.dumps(q).encode(), {"Content-Type": "application/json", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            info = parse_hl(json.load(r), name)
        if info:
            return {**info, "price_age_min": 0}
    except Exception:
        pass
    body, when = snapshot_body(name)
    if body and (now - when).total_seconds() <= 3600:
        info = parse_hl(body, name)
        if info:
            return {**info, "price_age_min": int((now - when).total_seconds() // 60)}
    return None


def history_levels(name, rule):
    """The rule stop as a share of the last close, and ATR as a share of it, from closed bars only."""
    d = load_crypto(name)[0] if name in CRYPTO else load_daily(XYZ[name])["d"]
    atr = X.atr_series(d, 14).values
    px = float(d.close.iloc[-1])
    stop, risk = X.initial_stop(d.low.values.astype(float), atr, len(d), px, rule)
    if risk is None:
        return None
    return {"close": px, "stop": float(stop), "stop_share": risk / px, "atr_share": float(atr[-1]) / px}


def liquidation(entry, leverage, max_leverage, is_long):
    """Isolated margin, from the formula in Hyperliquid's docs. Maintenance margin is half of the initial margin at max leverage."""
    l = 1 / (2 * max_leverage)
    side = 1 if is_long else -1
    return max(0.0, entry - side * entry * (1 / leverage - l) / (1 - l * side))


def build_plan(capital, risk_pct, entry, stop, target_r, info, costs, leverage=None, atr_share=None):
    """Pure arithmetic: the same numbers come back for the same inputs."""
    if entry == stop:
        raise PlanError("Stop ed entrata coincidono.")
    is_long = stop < entry
    side, dist = (1 if is_long else -1), abs(entry - stop)
    per_unit_cost = 2 * entry * costs
    budget = capital * risk_pct / 100
    size = budget / (dist + per_unit_cost)
    warnings, max_lev = [], info["max_leverage"]
    limit = leverage if leverage and leverage <= max_lev else max_lev
    if leverage and leverage > max_lev:
        warnings.append(f"Leva {leverage:g}x non disponibile: il massimo qui è {max_lev}x.")
    if size * entry > capital * limit:
        size = capital * limit / entry
        warnings.append(f"Lo stop è così stretto che servirebbe più della leva {limit:g}x: la posizione è ridotta, quindi rischi meno del previsto.")
    unit = 10 ** info["decimals"]
    size = math.floor(size * unit + 1e-9) / unit
    if size <= 0:
        raise PlanError("Con questo capitale e questo rischio la posizione è sotto la dimensione minima del mercato.")
    notional = size * entry
    lev = leverage if leverage and leverage <= max_lev else float(max(1, math.ceil(notional / capital - 1e-9)))
    liq = liquidation(entry, lev, max_lev, is_long)
    if (is_long and liq >= stop) or (not is_long and liq <= stop):
        l = 1 / (2 * max_lev)
        safe = 1 / (1.2 * (dist / entry) * (1 - l * side) + l)
        warnings.append(f"❌ Con leva {lev:g}x la liquidazione ({liq:,.2f}) arriva prima dello stop: resta sotto {max(1, math.floor(safe))}x.")
    share = dist / entry
    if share > WIDE_STOP:
        warnings.append(f"Stop molto largo ({share:.1%}): la posizione viene piccola, ed è giusto così.")
    if atr_share and share < .5 * atr_share:
        warnings.append(f"Stop molto stretto: è meno di metà del movimento normale di una barra ({atr_share:.1%}). Rischi di uscire per il rumore.")
    if risk_pct > MAX_SANE_RISK:
        warnings.append(f"Rischi il {risk_pct:g}% su un solo trade. Con 10 stop di fila perdi circa il {100 * (1 - (1 - risk_pct / 100) ** 10):.0f}% del capitale.")
    if notional < MIN_ORDER_USD:
        warnings.append(f"Sotto il minimo d'ordine di circa {MIN_ORDER_USD} $: Hyperliquid può rifiutarlo.")
    target = entry + side * target_r * dist
    if target <= 0:
        raise PlanError("Con questo stop il target andrebbe sotto zero: riduci il target.")
    cost = per_unit_cost * size
    return {"side": "long" if is_long else "short", "entry": entry, "stop": stop, "target": target, "target_r": target_r, "size": size, "decimals": info["decimals"],
            "notional": notional, "leverage": lev, "margin": notional / lev, "liquidation": liq, "stop_share": share, "target_share": abs(target - entry) / entry,
            "loss_at_stop": dist * size + cost, "gain_at_target": target_r * dist * size - cost, "capital": capital, "risk_pct": risk_pct, "budget": budget,
            "funding_per_day": -side * info["funding"] * 24 * notional, "warnings": warnings}


def price_text(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:.4f}" if x >= 1 else f"{x:.6f}"


def format_plan(name, p, info, stop_source, time_exit, notes=()):
    label = LABELS.get(name, name)
    money = lambda x: f"{x:,.0f} $" if abs(x) >= 100 else f"{x:,.2f} $"
    sign = "+" if p["side"] == "long" else "−"
    other = "−" if p["side"] == "long" else "+"
    fund = p["funding_per_day"]
    age = f", dato di {info['price_age_min']} min fa" if info.get("price_age_min") else ""
    lines = [f"🧮 <b>Piano {label} · {p['side'].upper()}</b>", f"Entrata {price_text(p['entry'])}{age}",
             f"Capitale {money(p['capital'])} · rischio {p['risk_pct']:g}% = {money(p['budget'])}", "",
             f"<b>Quanto:</b> {p['size']:.{p['decimals']}f} ({money(p['notional'])})",
             f"<b>Leva:</b> {p['leverage']:g}x, margine isolato {money(p['margin'])}" + (f", liquidazione {price_text(p['liquidation'])}" if p["liquidation"] > 0 else ""),
             f"<b>Stop:</b> {price_text(p['stop'])} ({other}{p['stop_share']:.1%}) → perdi circa {money(p['loss_at_stop'])}. {stop_source}",
             f"<b>Obiettivo {p['target_r']:g}R:</b> {price_text(p['target'])} ({sign}{p['target_share']:.1%}) → guadagni circa {money(p['gain_at_target'])}. Chiudi tutto lì.",
             f"<b>Tempo:</b> se dopo {time_exit} non hai toccato né stop né obiettivo, esci.",
             f"<b>Funding:</b> ai tassi di ora {'paghi' if fund < 0 else 'incassi'} circa {money(abs(fund))} al giorno."]
    extra = list(p["warnings"]) + list(notes)
    if extra:
        lines += [""] + [f"⚠️ {w}" if not w.startswith("❌") else w for w in extra]
    lines += ["", "Metti stop e obiettivo appena entri, e non spostare lo stop contro di te. Nei gap lo stop può eseguire peggio.", TEST_NOTE,
              "Calcolo, non consulenza finanziaria. Gli ordini li metti tu."]
    return "\n".join(lines)


def make_plan(words, now=None):
    """From the user's words to the text, and the data to log. Raises PlanError with a message for the user."""
    req = parse_request(words)
    name = resolve(req["market"])
    info = market_info(name, now)
    if not info and not req.get("entry"):
        raise PlanError("Non ho un prezzo Hyperliquid recente. Riprova, o indica tu l'entrata: entrata PREZZO.")
    if not info:
        raise PlanError("Non ho i dati del mercato su Hyperliquid (leva massima, decimali), quindi non calcolo la posizione. Riprova tra poco.")
    entry = req.get("entry") or info["mark"]
    rule = json.loads(X.CONFIG.read_text())["initial_stop"]
    try:
        levels = history_levels(name, rule)
    except Exception:
        levels = None
    costs = json.loads(X.CONFIG.read_text())["classes"]["crypto" if name in CRYPTO else "commodities"]
    notes = []
    if req.get("stop"):
        stop, source = req["stop"], "Lo hai scelto tu."
    elif not levels:
        raise PlanError("Non ho lo storico per la regola di stop: indicalo tu con stop PREZZO.")
    elif name in CRYPTO:
        stop, source = entry - max(entry - levels["stop"], .5 * levels["atr_share"] * levels["close"]), "Regola: minimo delle ultime 3 barre meno mezzo ATR."
    else:
        stop, source = entry * (1 - levels["stop_share"]), "Regola: minimo delle ultime 3 barre meno mezzo ATR."
        notes.append("Stop calcolato sul future in percentuale, perché il prezzo Hyperliquid può differire: ricontrolla il livello sul grafico.")
    if name.startswith("xyz:"):
        notes.append("Mercato di terzi su Hyperliquid (dex xyz): commissioni, oracolo e rischi del gestore non sono verificati.")
    p = build_plan(req["capital"], req["risk_pct"], entry, stop, req["target_r"], info, costs["fee_per_side"] + costs["slippage_per_side"],
                   req.get("leverage"), levels["atr_share"] if levels else None)
    text = format_plan(name, p, info, source, TIME_EXIT["crypto" if name in CRYPTO else "other"], notes)
    return text, {**p, "market": name, "label": LABELS.get(name, name), "stop_source": source, "notes": notes, "time_exit": TIME_EXIT["crypto" if name in CRYPTO else "other"],
                  "funding_side": "paghi" if p["funding_per_day"] < 0 else "incassi", "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}


def log_plan(rec):
    d = Path(os.environ.get("BZD_DATA", BASE / "data")) / "alerts"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "plans.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def answer(words):
    """The reply to a request, whatever happens: the user always gets words back."""
    try:
        text, rec = make_plan(words)
    except PlanError as e:
        return str(e)
    log_plan(rec)
    return text


def main(argv):
    load_env()
    if not argv:
        print(__doc__)
        return 2
    import html, re
    print(html.unescape(re.sub(r"</?b>", "", answer(argv))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
