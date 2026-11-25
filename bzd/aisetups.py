"""AIsetups: twice a day a cheap model (Haiku) reads what the app says and writes 15 candidate trades; the code keeps the 5 best
(2 short-term, 2 medium-term, 1 long-term) and changes the ones already on the board only when that makes sense.

    python -m bzd.aisetups run --paga     one round (the server's timer runs it at 06:30 and 13:30 UTC)
    python -m bzd.aisetups stima          what a round costs, free
    python -m bzd.aisetups invia          send the latest round to Telegram again

They are ideas, not signals: almost nothing the app shows has held up in a test, and a model choosing among those readings adds no proven edge.
So every proposal says which test backs it (usually none), the code checks that each one cites only numbers the app shows and that its
invalidation and target sit on the right side of the price, and every proposal is followed afterwards: the AIsetups tab shows how they went.

How the 5 are chosen (`pick`): a candidate that fails a check is dropped, not the whole round. Score = the model's conviction (1–5)
+ reward/risk capped at 3 (a target closer than the invalidation is dropped) + 2 when a test that held backs it. One market at a time.
A setup on the board stays until it reaches its target, its invalidation or the end of its horizon, unless the model says the picture
has changed («superata») and there is a candidate to put in its place, or a new candidate scores at least REPLACE_MARGIN more.
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
CANDIDATES = {"breve": 6, "medio": 6, "lungo": 3}
REPLACE_MARGIN = 2.0
CLOSED = ("invalidata", "obiettivo", "scaduta", "sostituita")
PURPOSE = "aisetups"

SYSTEM = """Sei l'assistente di ricerca di un'app sui mercati. Ricevi in <dati> tutto ciò che l'app mostra adesso, già calcolato dal codice: prezzi, forza rispetto alla storia, momentum, trend, RSI, livelli, posizionamento di retail e grossi, opzioni, sentiment, alert recenti, e l'esito dei test fatti sulle letture dell'app. In <attivi> ci sono le idee già in bacheca, proposte nei giri precedenti.

Scrivi 15 candidati da approfondire: 6 di breve periodo (1–10 giorni), 6 di medio (2–8 settimane), 3 di lungo (3–12 mesi), su mercati diversi il più possibile. Il codice ne terrà 5. Poi giudica ogni idea in <attivi>: «valida» se la sua tesi regge ancora con i dati di oggi, «superata» se i dati la contraddicono; il motivo in una frase.

Regole:
- Usa solo i mercati e i numeri presenti in <dati>. Non inventare notizie, livelli o dati. Ogni numero che scrivi deve comparire in <dati>.
- «invalidazione» è il prezzo che, se toccato, dice che l'idea era sbagliata: sotto il prezzo attuale per un long, sopra per uno short. Preferisci un livello di supporto o resistenza presente in <dati>.
- «obiettivo» sta dalla parte opposta, e più lontano dal prezzo dell'invalidazione: un obiettivo più vicino dell'invalidazione viene scartato.
- «convinzione» da 1 a 5: quanto le letture dei dati vanno nella stessa direzione. Usa tutta la scala; 5 solo se quasi tutto concorda.
- «test»: il codice della lettura testata su cui l'idea si appoggia, preso da <test>, solo se il suo esito è «supportata»; altrimenti «nessuno». Quasi tutte le letture dell'app non hanno retto ai test: dillo nei rischi quando l'idea si basa su quelle.
- «titolo»: l'idea in poche parole, al massimo 60 caratteri, senza numeri (es. «rimbalzo da ipervenduto verso la resistenza»).
- Tesi breve e concreta, in italiano semplice. Niente consigli finanziari personali, niente dimensione della posizione.
- Se il quadro è confuso, scrivi comunque i candidati ma dillo in «quadro»."""

SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["quadro", "candidati", "attivi"],
    "properties": {
        "quadro": {"type": "string"},
        "attivi": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "giudizio", "motivo"],
                                              "properties": {"id": {"type": "string"}, "giudizio": {"type": "string", "enum": ["valida", "superata"]}, "motivo": {"type": "string"}}}},
        "candidati": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["orizzonte", "mercato", "direzione", "titolo", "tesi", "fatti", "test", "convinzione", "invalidazione", "obiettivo", "rischi"],
            "properties": {
                "orizzonte": {"type": "string", "enum": list(HORIZONS)},
                "titolo": {"type": "string"},
                "mercato": {"type": "string"},
                "direzione": {"type": "string", "enum": ["long", "short"]},
                "tesi": {"type": "string"},
                "fatti": {"type": "array", "items": {"type": "string"}},
                "test": {"type": "string"},
                "convinzione": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
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


def prompt(data, tests, retry_note=None, board=()):
    act = [{"id": e["key"], "mercato": e["mercato"], "direzione": e["direzione"], "orizzonte": e["orizzonte"], "titolo": e.get("titolo", ""), "tesi": e["tesi"],
            "proposta_il": e["ts"][:10], "prezzo_allora": e["prezzo"], "invalidazione": e["invalidazione"], "obiettivo": e["obiettivo"]} for e in board]
    body = (f"<dati>\n{json.dumps(data, ensure_ascii=False)}\n</dati>\n<test>\n{json.dumps(tests, ensure_ascii=False)}\n</test>\n"
            f"<attivi>\n{json.dumps(act, ensure_ascii=False)}\n</attivi>")
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


def problems_of(p, data, tests, allowed):
    """Code checks on one candidate. An empty list means it passes."""
    m = {x["mercato"].lower(): x for x in data["mercati"]}.get(p["mercato"].lower())
    if not m:
        return [f"il mercato «{p['mercato']}» non è tra quelli dell'app"]
    out = []
    price, sign = m["prezzo"], 1 if p["direzione"] == "long" else -1
    if not price or sign * (price - p["invalidazione"]) <= 0:
        out.append(f"l'invalidazione {p['invalidazione']} sta dalla parte sbagliata del prezzo {price}")
    if not price or sign * (p["obiettivo"] - price) <= 0:
        out.append(f"l'obiettivo {p['obiettivo']} sta dalla parte sbagliata del prezzo {price}")
    elif not out and reward_risk(p, price) < 1:
        out.append("l'obiettivo è più vicino dell'invalidazione")
    if p["test"] != "nessuno" and (tests.get(p["test"]) or {}).get("esito") != "supportata":
        out.append(f"il test «{p['test']}» non esiste o non ha retto; scrivi «nessuno»")
    if len(p.get("titolo", "")) > 80:
        out.append("il titolo supera 60 caratteri")
    bad = numbers_ok(" ".join([p.get("titolo", ""), p["tesi"], p["rischi"], *p["fatti"]]), allowed + [p["invalidazione"], p["obiettivo"]])
    if bad:
        out.append(f"numeri che non compaiono nei dati: {', '.join(str(b) for b in bad[:4])}")
    return out


def reward_risk(p, price):
    return abs(p["obiettivo"] - price) / max(abs(price - p["invalidazione"]), 1e-12)


def score(p, price, tests):
    """Conviction 1–5, plus reward/risk capped at 3, plus 2 if a test that held backs it."""
    backed = p.get("test", "nessuno") != "nessuno" and (tests.get(p["test"]) or {}).get("esito") == "supportata"
    return round(p.get("convinzione", 3) + min(reward_risk(p, price), 3) + (2 if backed else 0), 2)


def screen(out, data, tests):
    """Every candidate with its problems and score. The round fails only when too few pass for 2 short, 2 medium, 1 long."""
    allowed, prices = allowed_numbers(data, tests), {m["mercato"].lower(): m["prezzo"] for m in data["mercati"]}
    cands = []
    for p in out.get("candidati") or []:
        pr = problems_of(p, data, tests, allowed)
        cands.append({**p, "problemi": pr, "punteggio": None if pr else score(p, prices[p["mercato"].lower()], tests)})
    ok = {h: sum(1 for c in cands if c["orizzonte"] == h and not c["problemi"]) for h in HORIZONS}
    short = [f"{h}: {ok[h]} validi su {WANT[h]} necessari" for h in HORIZONS if ok[h] < WANT[h]]
    if short:
        why = "; ".join(f"{c['mercato']} {c['direzione']} ({c['orizzonte']}): {', '.join(c['problemi'])}" for c in cands if c["problemi"])[:1500]
        return cands, [f"troppo pochi candidati validi ({', '.join(short)}). Scartati: {why or 'nessuno'}"]
    return cands, []


def check(out, data, tests):
    """Problems that make a round fail (too few valid candidates). Single bad candidates are only dropped."""
    return screen(out, data, tests)[1]


def ask(client, data, tests, board=()):
    """At most two calls: the second only if too few candidates passed the code checks, with the problems listed."""
    note = None
    for _ in range(2):
        out, err = R.call_json(client, SYSTEM, SCHEMA, prompt(data, tests, note, board), PURPOSE)
        if err:
            return None, err, []
        problems = check(out, data, tests)
        if not problems:
            return out, None, []
        note = "; ".join(problems)
    return None, "troppo pochi candidati hanno passato i controlli", problems


def load_board():
    """The setups on the board. The first time, the latest successful round of the old kind (5 proposals) becomes the board."""
    p = store() / "attivi.json"
    if p.exists():
        return json.loads(p.read_text())
    last = next((x for x in reversed(runs()) if x["status"] == "ok"), None)
    return [{**q, "key": f"{last['ts']}#{i}", "ts": last["ts"], "punteggio": q.get("punteggio") or 5.0} for i, q in enumerate(last.get("proposte") or [])] if last else []


def pick(board, cands, verdicts, prices, now):
    """Which setups stay, leave and come in. Returns (new board, entering, leaving with outcome, changes in words, candidate fates)."""
    fate = {id(c): ("scartato: " + ", ".join(c["problemi"])) if c["problemi"] else "non scelto" for c in cands}
    valid = sorted([c for c in cands if not c["problemi"]], key=lambda c: -c["punteggio"])
    keep, leaving, changes = [], [], []
    for e in board:
        st = follow(e, e["ts"], prices.get(e["mercato"].lower()), now)
        if st["stato"] in CLOSED:
            leaving.append((e, st))
            changes.append(f"Chiusa {e['mercato']} {e['direzione']} ({e['orizzonte']}): {st['stato']}, {st['rend_pct']:+.1f}%".replace(".", ","))
        else:
            keep.append({**e, "_now": st})
    used = {e["mercato"].lower() for e in keep}
    for c in valid:  # same market and side as a setup that stays: it confirms it, it doesn't duplicate it
        if any(e["mercato"].lower() == c["mercato"].lower() and e["direzione"] == c["direzione"] for e in keep):
            fate[id(c)] = "conferma un'idea già in bacheca"
    free = lambda h: [c for c in valid if c["orizzonte"] == h and c["mercato"].lower() not in used and fate[id(c)] == "non scelto"]
    entering = []

    def take(c):
        entering.append(c)
        used.add(c["mercato"].lower())
        fate[id(c)] = "scelto"

    for h in HORIZONS:
        mine = sorted([e for e in keep if e["orizzonte"] == h], key=lambda e: e.get("punteggio") or 0)
        for e in mine:  # weakest first: replace when the model says it's overtaken, or a candidate is clearly better
            v = verdicts.get(e["key"], {})
            best = next(iter(free(h)), None)
            if best is None:
                continue
            if v.get("giudizio") == "superata" or best["punteggio"] >= (e.get("punteggio") or 0) + REPLACE_MARGIN:
                why = f"superata: {v.get('motivo', '')}" if v.get("giudizio") == "superata" else f"{best['mercato']} ha {best['punteggio']:.1f} punti contro {(e.get('punteggio') or 0):.1f}"
                keep.remove(e)
                used.discard(e["mercato"].lower())
                leaving.append((e, {"stato": "sostituita", "rend_pct": e["_now"]["rend_pct"]}))
                take(best)
                changes.append(f"Sostituita {e['mercato']} {e['direzione']} ({h}) con {best['mercato']} {best['direzione']}: {why}")
        while sum(e["orizzonte"] == h for e in keep) + sum(c["orizzonte"] == h for c in entering) < WANT[h]:
            best = next(iter(free(h)), None)
            if best is None:
                break
            take(best)
            changes.append(f"Nuova {best['mercato']} {best['direzione']} ({h}), {best['punteggio']:.1f} punti".replace(".", ","))
    return [{k: v for k, v in e.items() if k != "_now"} for e in keep], entering, leaving, changes, fate


def runs():
    p = store() / "runs.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def run(client=None, get=C.fetch, now=None):
    now = now or datetime.now(timezone.utc)
    ts = now.isoformat(timespec="seconds")
    snap = get("/api/snapshot")
    data, tests = context(snap)
    board = load_board()
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    out, err, problems = ask(client, data, tests, board)
    rec = {"ts": ts, "model": R.model_for(PURPOSE), "status": "ok" if out else "error", "detail": err, "problems": problems}
    if out:
        prices = {m["mercato"].lower(): m["prezzo"] for m in data["mercati"]}
        keys = {m["label"].lower(): m.get("plan_key") for m in snap.get("markets", [])}
        cands, _ = screen(out, data, tests)
        verdicts = {v["id"]: v for v in out.get("attivi") or []}
        kept, entering, leaving, changes, fate = pick(board, cands, verdicts, prices, now)
        clean = lambda c: {k: v for k, v in c.items() if k != "problemi"}
        new = [{**clean(c), "prezzo": prices[c["mercato"].lower()], "plan_key": keys.get(c["mercato"].lower())} for c in entering]
        rec["quadro"] = out["quadro"]
        rec["proposte"] = new  # only what enters the board: each setup is followed once, from the round it entered
        rec["attivi"] = kept + [{**c, "key": f"{ts}#{i}", "ts": ts} for i, c in enumerate(new)]
        rec["cambi"] = changes
        rec["giudizi"] = list(verdicts.values())
        rec["candidati"] = [{"orizzonte": c["orizzonte"], "mercato": c["mercato"], "direzione": c["direzione"], "titolo": c.get("titolo", ""),
                             "convinzione": c.get("convinzione"), "punteggio": c["punteggio"], "esito": fate[id(c)]} for c in cands]
        p = store() / "outcomes.json"
        frozen = json.loads(p.read_text()) if p.exists() else {}
        for e, st in leaving:
            frozen.setdefault(e["key"], st)
        p.write_text(json.dumps(frozen))
        (store() / "attivi.json").write_text(json.dumps(rec["attivi"], ensure_ascii=False))
    with open(store() / "runs.jsonl", "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def first_sentence(text, limit=70):
    s = re.split(r"(?<=[.:;])\s", text.strip())[0].rstrip(".:;")
    return s if len(s) <= limit else s[:limit - 1].rsplit(" ", 1)[0] + "…"


def format_telegram(rec):
    """The board on Telegram, at a glance: one line per idea with entry, target and invalidation, its idea in a few words; 🆕 marks what came in this round."""
    from . import tg
    when = rec["ts"][11:16]
    out = [f"🤖 <b>AI SETUPS</b> · {rec['ts'][8:10]}/{rec['ts'][5:7]} {when} UTC", f"<i>{tg.esc(first_sentence(rec.get('quadro', ''), 110))}</i>"]
    heads = {"breve": "⏱ <b>Breve</b> · 1–10 giorni", "medio": "📅 <b>Medio</b> · 2–8 settimane", "lungo": "🗓 <b>Lungo</b> · 3–12 mesi"}
    for h in HORIZONS:
        props = [p for p in rec.get("attivi") or rec.get("proposte") or [] if p["orizzonte"] == h]
        if not props:
            continue
        out += ["", heads[h]]
        for p in props:
            long = p["direzione"] == "long"
            tgt, inv = 100 * (p["obiettivo"] / p["prezzo"] - 1), 100 * (p["invalidazione"] / p["prezzo"] - 1)
            new = "🆕 " if p.get("ts", rec["ts"]) == rec["ts"] and "attivi" in rec else ""
            out.append(f"{new}{'🟢' if long else '🔴'} <b>{tg.esc(p['mercato'])} {'long' if long else 'short'}</b> {tg.num(p['prezzo'])} → 🎯 {tg.num(p['obiettivo'])} <i>{tg.pct(tgt, None)}</i> · ✖ {tg.num(p['invalidazione'])} <i>{tg.pct(inv, None)}</i>")
            out.append(f"   {tg.esc(p.get('titolo') or first_sentence(p['tesi']))}" + (" · ✅ testato" if p.get("test", "nessuno") != "nessuno" else ""))
    gone = [c for c in rec.get("cambi") or [] if c.startswith(("Sostituita", "Chiusa"))]
    if gone:
        out += ["", *(f"↩ {tg.esc(c if len(c) <= 110 else c[:109] + '…')}" for c in gone[:4])]
    out += ["", "<i>Idee del modello, non testate: ognuna è seguita nell'app.</i>", tg.app_link("aisetups")]
    return "\n".join(out)


def send(rec):
    """Send the round when the bot is on. A failure never loses the round: it's already saved."""
    from .alerts import send_text, sending_enabled, split_message
    if rec.get("status") != "ok" or not rec.get("proposte") or not sending_enabled():
        return False  # nothing new on the board: no message
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
            if res["stato"] in CLOSED:
                frozen[key] = res
            hist.append({**prop, "ts": rec["ts"], **res})
    try:
        p.write_text(json.dumps(frozen))
    except OSError:
        pass
    closed = [h for h in hist if h["stato"] in CLOSED and h["rend_pct"] is not None]
    summary = {"chiuse": len(closed), "aperte": sum(h["stato"] == "aperta" for h in hist),
               "vinte": sum(h["rend_pct"] > 0 for h in closed), "media_pct": round(sum(h["rend_pct"] for h in closed) / len(closed), 2) if closed else None}
    latest = next((x for x in reversed(rows) if x["status"] == "ok"), None)
    last_try = rows[-1] if rows else None
    board = []
    for e in load_board() if latest else []:
        st = frozen.get(e["key"]) or follow(e, e["ts"], prices.get(e["mercato"].lower()), now)
        board.append({**e, **st, "nuova": bool(latest) and e["ts"] == latest["ts"]})
    return {"latest": latest, "board": board, "last_try": last_try, "history": list(reversed(hist))[:200], "summary": summary,
            "cost_month": round(sum(u["cost_usd"] for u in G.usage_rows() if u.get("purpose") == PURPOSE and u["ts"][:7] == now.strftime("%Y-%m")), 4)}


def estimate(get=C.fetch):
    data, tests = context(get("/api/snapshot"))
    tokens_in = (len(SYSTEM) + len(prompt(data, tests))) / R.CHARS_PER_TOKEN
    i_price, o_price = G.PRICES.get(R.model_for(PURPOSE), G.HIGHEST)
    one = (tokens_in * i_price + 14000 * o_price) / 1e6  # 15 candidates
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
        print(rec["status"], rec.get("detail") or "", *(f"\n  {c}" for c in rec.get("cambi") or []) or "nessun cambio",
              *(f"\n  {p['orizzonte']:6} {p['direzione']:5} {p['mercato']}: {p['tesi'][:90]}" for p in rec.get("attivi") or []))
        return 0 if rec["status"] == "ok" else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
