"""AIsetups: twice a day a cheap model (Haiku) reads what the app says and proposes 5 trades worth a look: 2 short-term, 2 medium-term, 1 long-term.

    python -m bzd.aisetups run --paga     one round (the server's timer runs it at 06:30 and 13:30 UTC)
    python -m bzd.aisetups stima          what a round costs, free
    python -m bzd.aisetups invia          send the latest round to Telegram again

They are ideas, not signals: almost nothing the app shows has held up in a test, and a model choosing among those readings adds no proven edge.
So every proposal says which test backs it (usually none), the code checks that each one cites only numbers the app shows and that its
invalidation and target sit on the right side of the price, and every proposal is followed afterwards: the AIsetups tab shows how they went.
That record is the only way to learn whether these ideas are worth anything. Nothing here trades.
"""
import json, os, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import agents as G
from . import commands as C
from . import research as R
from .recorder import BASE, load_env

HORIZONS = {"breve": ("1–10 giorni", 10), "medio": ("2–8 settimane", 56), "lungo": ("3–12 mesi", 365)}
WANT = {"breve": 2, "medio": 2, "lungo": 1}
PURPOSE = "aisetups"

SYSTEM = """Sei l'assistente di ricerca di un'app sui mercati. Ricevi in <dati> tutto ciò che l'app mostra adesso, già calcolato dal codice: prezzi, forza rispetto alla storia, momentum, trend, RSI, livelli, posizionamento di retail e grossi, opzioni, sentiment, alert recenti, e l'esito dei test fatti sulle letture dell'app.

Proponi esattamente 5 operazioni potenzialmente interessanti da approfondire: 2 di breve periodo (1–10 giorni), 2 di medio (2–8 settimane), 1 di lungo (3–12 mesi). Mercati diversi se possibile.

Regole:
- Usa solo i mercati e i numeri presenti in <dati>. Non inventare notizie, livelli o dati. Ogni numero che scrivi deve comparire in <dati>.
- «invalidazione» è il prezzo che, se toccato, dice che l'idea era sbagliata: sotto il prezzo attuale per un long, sopra per uno short. Preferisci un livello di supporto o resistenza presente in <dati>.
- «obiettivo» sta dalla parte opposta: sopra il prezzo per un long, sotto per uno short.
- «test»: il codice della lettura testata su cui l'idea si appoggia, preso da <test>, solo se il suo esito è «supportata»; altrimenti «nessuno». Quasi tutte le letture dell'app non hanno retto ai test: dillo nei rischi quando l'idea si basa su quelle.
- «titolo»: l'idea in poche parole, al massimo 60 caratteri, senza numeri (es. «rimbalzo da ipervenduto verso la resistenza»).
- Tesi breve e concreta, in italiano semplice. Niente consigli finanziari personali, niente dimensione della posizione.
- Se il quadro è confuso, proponi comunque le 5 idee ma dillo in «quadro»."""

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["quadro", "proposte"],
    "properties": {
        "quadro": {"type": "string"},
        "proposte": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["orizzonte", "mercato", "direzione", "titolo", "tesi", "fatti", "test", "invalidazione", "obiettivo", "rischi"],
            "properties": {
                "orizzonte": {"type": "string", "enum": list(HORIZONS)},
                "titolo": {"type": "string"},
                "mercato": {"type": "string"},
                "direzione": {"type": "string", "enum": ["long", "short"]},
                "tesi": {"type": "string"},
                "fatti": {"type": "array", "items": {"type": "string"}},
                "test": {"type": "string"},
                "invalidazione": {"type": "number"},
                "obiettivo": {"type": "number"},
                "rischi": {"type": "string"}}}}}}


def store():
    p = Path(os.environ.get("BZD_DATA", BASE / "data")) / "aisetups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def r(x, d=2):
    return None if x is None else round(x, d)


def context(snap):
    """What the model reads: the app's numbers, trimmed to what matters for a trade idea."""
    tech = {t["market"]: t for t in snap.get("technical", [])}
    flows = {f["market"]: f for f in snap.get("flows", []) if f.get("tf") in (None, "1d")}
    markets = []
    for m in snap.get("markets", []):
        t, f = tech.get(m["market"], {}), flows.get(m["market"], {})
        markets.append({
            "mercato": m["label"], "classe": m.get("class"), "prezzo": m.get("price"),
            "var_pct": {k: r(v) for k, v in (m.get("returns") or {}).items()},
            "forza_0_100": r(m.get("heat"), 0), "forza": m.get("band"), "forza_var_7g": r(m.get("heat_change_7d"), 0),
            "prezzo_ultimo_anno": {k: (r(v, 1) if isinstance(v, float) else v) for k, v in (m.get("position") or {}).items() if k in ("label", "from_high", "from_low")},
            "momentum_giornaliero": {"GIU": "scende forte", "SU": "sale forte"}.get(((m.get("zones") or {}).get("1d") or {}).get("tag"), "nessuno"),
            "trend": {k: v for k, v in (t.get("trend") or {}).items() if k in ("1d", "1w", "1M")},
            "rsi": {k: r(v, 0) for k, v in (t.get("rsi") or {}).items() if k in ("1d", "1w", "1M")},
            "reset": {k: v for k, v in (t.get("reset") or {}).items() if v},
            "supporto": (t.get("support") or {}).get("price"), "resistenza": (t.get("resistance") or {}).get("price"),
            "retail_percentile": r((f.get("retail") or {}).get("pct"), 0), "grossi_percentile": r((f.get("big") or {}).get("pct"), 0),
            "capitolazione_byz": (m.get("byz") or {}).get("fired")})
    options = [{"nome": o["name"], "costo": (o.get("cost") or {}).get("label"), "livello": (o.get("level") or {}).get("band")} for o in snap.get("options", [])]
    lab = [{"nome": b["name"], "opzioni": b.get("label"), "rapporto_prezzo_movimento": r(b.get("ratio"))} for b in snap.get("lab", []) if b.get("ratio")]
    al = snap.get("alerts") or {}
    recent = sorted([(a["trigger"], f"{a['setup']} su {a['market']}") for a in al.get("setups", [])] + [(a["at"], f"{a['label']} {a['pct']:+.1f}% in {a['window']}") for a in al.get("moves", [])], reverse=True)[:10]
    sent = snap.get("sentiment") or {}
    tests = {k: {"esito": v.get("outcome") or "non testato", "cosa": v.get("line", "")[:220]} for k, v in (snap.get("verdicts") or {}).items()}
    tests.update({f"B3-{t['setup']}-{t['class']}": {"esito": t["outcome"], "cosa": t["setup_name"] + " " + t["class_name"] + ": " + t["reading"][0][:200]} for t in snap.get("tests") or []})
    data = {"aggiornato": snap.get("at"), "quadro_app": snap.get("overview"), "frasi_del_giorno": [b["text"] for b in snap.get("briefing", [])],
            "gruppi": {c["name"]: {"forza_0_100": r(c.get("heat"), 0), "forza": c.get("band"), "var_7g": r(c.get("change_7d"), 0), "perche": c.get("why")} for c in (snap.get("classes") or {}).values()},
            "mercati": markets, "opzioni": options, "opzioni_per_mercato": lab, "alert_recenti": [f"{t[:10]} {x}" for t, x in recent],
            "paura_euforia_0_100": (sent.get("fear_greed") or {}).get("value")}
    return data, tests


def prompt(data, tests, retry_note=None):
    body = f"<dati>\n{json.dumps(data, ensure_ascii=False)}\n</dati>\n<test>\n{json.dumps(tests, ensure_ascii=False)}\n</test>"
    return body + (f"\n\nLa risposta precedente non ha passato i controlli del codice: {retry_note} Correggi e rispondi di nuovo." if retry_note else "")


NUM = re.compile(r"\d+(?:[.,]\d+)*")


def readings(token):
    """The values a written number can mean: 1.234,5 and 1,234.5 and 59694.2 and 2,3 (Italian decimal) all read right."""
    out = set()
    if "." in token and "," in token:
        dec = max(token.rfind("."), token.rfind(","))
        out.add(float(re.sub(r"[.,]", "", token[:dec]) + "." + token[dec + 1:]))
    elif token.count(".") + token.count(",") == 1:
        out.add(float(token.replace(",", ".")))
        if re.fullmatch(r"\d{1,3}[.,]\d{3}", token):
            out.add(float(re.sub(r"[.,]", "", token)))
    else:
        out.add(float(re.sub(r"[.,]", "", token)))
    return out


def numbers_ok(text, allowed):
    """Every number in the text must be one the app shows (rounding allowed). Small counts like '2 giorni' pass. Returns the ones that don't."""
    bad = []
    for token in NUM.findall(text or ""):
        vals = readings(token)
        if any(abs(v) <= 12 or any(abs(v - a) <= max(.011 * abs(a), .06) for a in allowed) for v in vals):
            continue
        bad.append(token)
    return bad


def allowed_numbers(data, tests):
    return sorted({v for t in NUM.findall(json.dumps(data, ensure_ascii=False) + json.dumps(tests, ensure_ascii=False)) for v in readings(t)})


def check(out, data, tests):
    """Code checks on the model's answer. Returns a list of problems, empty when it passes."""
    problems = []
    props = out.get("proposte") or []
    counts = {h: sum(p["orizzonte"] == h for p in props) for h in HORIZONS}
    if counts != WANT:
        problems.append(f"servono 2 breve, 2 medio e 1 lungo, invece {counts}")
    by_label = {m["mercato"].lower(): m for m in data["mercati"]}
    allowed = allowed_numbers(data, tests)
    for i, p in enumerate(props, 1):
        m = by_label.get(p["mercato"].lower())
        if not m:
            problems.append(f"proposta {i}: il mercato «{p['mercato']}» non è tra quelli dell'app")
            continue
        price, sign = m["prezzo"], 1 if p["direzione"] == "long" else -1
        if not price or sign * (price - p["invalidazione"]) <= 0:
            problems.append(f"proposta {i} ({p['mercato']}): l'invalidazione {p['invalidazione']} sta dalla parte sbagliata del prezzo {price}")
        if not price or sign * (p["obiettivo"] - price) <= 0:
            problems.append(f"proposta {i} ({p['mercato']}): l'obiettivo {p['obiettivo']} sta dalla parte sbagliata del prezzo {price}")
        if p["test"] != "nessuno" and (tests.get(p["test"]) or {}).get("esito") != "supportata":
            problems.append(f"proposta {i}: il test «{p['test']}» non esiste o non ha retto; scrivi «nessuno»")
        if len(p.get("titolo", "")) > 80:
            problems.append(f"proposta {i}: il titolo supera 60 caratteri")
        bad = numbers_ok(" ".join([p.get("titolo", ""), p["tesi"], p["rischi"], *p["fatti"]]), allowed + [p["invalidazione"], p["obiettivo"]])
        if bad:
            problems.append(f"proposta {i}: numeri che non compaiono nei dati: {', '.join(str(b) for b in bad[:4])}")
    return problems


def ask(client, data, tests):
    """At most two calls: the second only if the code checks failed, with the problems listed."""
    note = None
    for _ in range(2):
        out, err = R.call_json(client, SYSTEM, SCHEMA, prompt(data, tests, note), PURPOSE)
        if err:
            return None, err, []
        problems = check(out, data, tests)
        if not problems:
            return out, None, []
        note = "; ".join(problems)
    return None, "le proposte non hanno passato i controlli", problems


def runs():
    p = store() / "runs.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def run(client=None, get=C.fetch, now=None):
    now = now or datetime.now(timezone.utc)
    snap = get("/api/snapshot")
    data, tests = context(snap)
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    out, err, problems = ask(client, data, tests)
    rec = {"ts": now.isoformat(timespec="seconds"), "model": R.model_for(PURPOSE), "status": "ok" if out else "error", "detail": err, "problems": problems}
    if out:
        prices = {m["mercato"].lower(): m["prezzo"] for m in data["mercati"]}
        keys = {m["label"].lower(): m.get("plan_key") for m in snap.get("markets", [])}
        rec["quadro"] = out["quadro"]
        rec["proposte"] = [{**p, "prezzo": prices[p["mercato"].lower()], "plan_key": keys.get(p["mercato"].lower())} for p in out["proposte"]]
    with open(store() / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def first_sentence(text, limit=70):
    s = re.split(r"(?<=[.:;])\s", text.strip())[0].rstrip(".:;")
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0] + "…"


def format_telegram(rec):
    """The round on Telegram, at a glance: one line per idea with entry, target and invalidation, its idea in a few words."""
    from . import tg
    when = rec["ts"][11:16]
    out = [f"🤖 <b>AI SETUPS</b> · {rec['ts'][8:10]}/{rec['ts'][5:7]} {when} UTC", f"<i>{tg.esc(first_sentence(rec.get('quadro', ''), 110))}</i>"]
    heads = {"breve": "⏱ <b>Breve</b> · 1–10 giorni", "medio": "📅 <b>Medio</b> · 2–8 settimane", "lungo": "🗓 <b>Lungo</b> · 3–12 mesi"}
    for h in HORIZONS:
        props = [p for p in rec.get("proposte") or [] if p["orizzonte"] == h]
        if not props:
            continue
        out += ["", heads[h]]
        for p in props:
            long = p["direzione"] == "long"
            tgt, inv = 100 * (p["obiettivo"] / p["prezzo"] - 1), 100 * (p["invalidazione"] / p["prezzo"] - 1)
            out.append(f"{'🟢' if long else '🔴'} <b>{tg.esc(p['mercato'])} {'long' if long else 'short'}</b> {tg.num(p['prezzo'])} → 🎯 {tg.num(p['obiettivo'])} <i>{tg.pct(tgt, None)}</i> · ✖ {tg.num(p['invalidazione'])} <i>{tg.pct(inv, None)}</i>")
            out.append(f"   {tg.esc(p.get('titolo') or first_sentence(p['tesi']))}" + (" · ✅ testato" if p.get("test", "nessuno") != "nessuno" else ""))
    out += ["", "<i>Idee del modello, non testate: ognuna è seguita nell'app.</i>", tg.app_link("aisetups")]
    return "\n".join(out)


def send(rec):
    """Send the round when the bot is on. A failure never loses the round: it's already saved."""
    from .alerts import send_text, sending_enabled, split_message
    if rec.get("status") != "ok" or not sending_enabled():
        return False
    for part in split_message(format_telegram(rec)):
        send_text(part)
    return True


def follow(prop, ts, now_price, now, history=None):
    """How a proposal went, from the price at proposal time to now. `history` is the list of closes since then, if known,
    so a stop or target touched in between counts. Without it only the current price is used."""
    sign = 1 if prop["direzione"] == "long" else -1
    days = HORIZONS[prop["orizzonte"]][1]
    end = datetime.fromisoformat(ts) + timedelta(days=days)
    path = list(history or []) + ([now_price] if now_price is not None else [])
    for px in path:
        if sign * (px - prop["invalidazione"]) <= 0:
            return {"stato": "invalidata", "rend_pct": round(sign * (prop["invalidazione"] / prop["prezzo"] - 1) * 100, 2)}
        if sign * (px - prop["obiettivo"]) >= 0:
            return {"stato": "obiettivo", "rend_pct": round(sign * (prop["obiettivo"] / prop["prezzo"] - 1) * 100, 2)}
    if now_price is None:
        return {"stato": "senza prezzo", "rend_pct": None}
    ret = round(sign * (now_price / prop["prezzo"] - 1) * 100, 2)
    return {"stato": "scaduta" if now >= end else "aperta", "rend_pct": ret}


def view(get=C.fetch, now=None):
    """For the app: the latest round, and every past proposal with how it went."""
    now = now or datetime.now(timezone.utc)
    rows = runs()
    p = store() / "outcomes.json"
    frozen = json.loads(p.read_text()) if p.exists() else {}  # closed outcomes stay as they closed
    try:
        prices = {m["label"].lower(): m["price"] for m in get("/api/snapshot").get("markets", [])}
    except Exception:
        prices = {}
    hist = []
    for rec in rows:
        for i, prop in enumerate(rec.get("proposte") or []):
            key = f"{rec['ts']}#{i}"
            res = frozen.get(key) or follow(prop, rec["ts"], prices.get(prop["mercato"].lower()), now)
            if res["stato"] in ("invalidata", "obiettivo", "scaduta"):
                frozen[key] = res
            hist.append({**prop, "ts": rec["ts"], **res})
    try:
        p.write_text(json.dumps(frozen))
    except OSError:
        pass
    closed = [h for h in hist if h["stato"] in ("invalidata", "obiettivo", "scaduta") and h["rend_pct"] is not None]
    summary = {"chiuse": len(closed), "aperte": sum(h["stato"] == "aperta" for h in hist),
               "vinte": sum(h["rend_pct"] > 0 for h in closed), "media_pct": round(sum(h["rend_pct"] for h in closed) / len(closed), 2) if closed else None}
    latest = next((x for x in reversed(rows) if x["status"] == "ok"), None)
    last_try = rows[-1] if rows else None
    return {"latest": latest, "last_try": last_try, "history": list(reversed(hist))[:200], "summary": summary,
            "cost_month": round(sum(u["cost_usd"] for u in G.usage_rows() if u.get("purpose") == PURPOSE and u["ts"][:7] == now.strftime("%Y-%m")), 4)}


def estimate(get=C.fetch):
    data, tests = context(get("/api/snapshot"))
    tokens_in = (len(SYSTEM) + len(prompt(data, tests))) / R.CHARS_PER_TOKEN
    i_price, o_price = G.PRICES.get(R.model_for(PURPOSE), G.HIGHEST)
    one = (tokens_in * i_price + 6000 * o_price) / 1e6
    return tokens_in, one


def main(argv):
    load_env()
    cmd = argv[0] if argv else ""
    if cmd == "stima":
        tokens, one = estimate()
        print(f"Un giro con {R.model_for(PURPOSE)}: circa {tokens:,.0f} token in ingresso, {one:.3f} $ (il doppio se serve il secondo tentativo). Due giri al giorno: circa {one * 60:.2f} $ al mese.")
        return 0
    if cmd == "invia":
        last = next((x for x in reversed(runs()) if x["status"] == "ok"), None)
        print("inviato" if last and send(last) else "niente da inviare (nessun giro riuscito o Telegram spento)")
        return 0
    if cmd == "run":
        if "--paga" not in argv:
            print("comando a pagamento: aggiungi --paga")
            return 1
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("nessuna chiave API in .env")
            return 1
        if G.spent_this_month() >= G.budget():
            print(f"tetto mensile di {G.budget():.2f} $ raggiunto: niente AIsetups fino al mese prossimo")
            return 1
        rec = run()
        try:
            send(rec)
        except Exception as e:
            print(f"invio Telegram fallito: {type(e).__name__}: {e}")
        print(rec["status"], rec.get("detail") or "", *(f"\n  {p['orizzonte']:6} {p['direzione']:5} {p['mercato']}: {p['tesi'][:90]}" for p in rec.get("proposte") or []))
        return 0 if rec["status"] == "ok" else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
