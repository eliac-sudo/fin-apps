"""Everything the app shows, read from saved data. No orders, no paid calls, nothing written."""
import gzip, json, math, re, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import flows as FL
from . import wallets as WL
from . import indicators as I
from . import option_lab as L
from . import options_report as O
from . import sentiment as SM
from . import technicals as K
from . import texts as T
from . import thermo as Z
from . import capitulation as CP
from . import zones as ZN
from . import verdicts as VD
from .alerts import CLASS_IT, COND_IT, SETUP_IT, SETUP_MEANS, alert_dir, test_verdict
from .events import crypto_daily, daily, read
from .history import CRYPTO, MARKETS, safe
from .moves import NAMES as MOVE_NAMES, snapshot_files, snapshot_time
from .recorder import BASE

PLAN_KEY = {**{c: c for c in CRYPTO}, "ES=F": "sp500", "NQ=F": "nasdaq", "GC=F": "oro", "SI=F": "argento", "HG=F": "rame", "CL=F": "petrolio", "EURUSD=X": "eur", "USDJPY=X": "jpy", "GBPUSD=X": "gbp", "ZB=F": "tlt"}
SENTIMENT_GROUPS = SM.GROUPS
MIN_MOOD_SIGNALS = 10
CLASS_ORDER = ("crypto", "equities", "bonds", "commodities", "fx")


def clean(x):
    """JSON has no NaN."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) or math.isinf(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def label(market):
    return Z.LABELS.get(market, market).replace("&amp;", "&")


def returns_of(market):
    """Price change over 1, 7 and 30 days, in percent."""
    d = crypto_daily(market) if market in CRYPTO else daily(read("tradfi", safe(market)))
    c = d.close.dropna()
    back = lambda n: 100 * (float(c.iloc[-1]) / float(c.iloc[-1 - n]) - 1) if len(c) > n and c.iloc[-1 - n] > 0 else None
    return {"1g": back(1), "7g": back(7 if market in CRYPTO else 5), "30g": back(30 if market in CRYPTO else 21)}


def class_history(rows):
    """The class heat over time: the plain average of its markets on each day."""
    frame = pd.DataFrame({r["market"]: r["history"] for r in rows if r.get("history")})
    if frame.empty:
        return {"dates": [], "values": []}
    mean = frame.sort_index().ffill(limit=4).mean(axis=1).dropna()
    return {"dates": list(mean.index), "values": [float(x) for x in mean.values]}


def capitulation_of(market):
    try:
        return CP.of(market)
    except Exception:
        return None


def markets_part():
    rows = Z.all_readings()
    out = []
    for r in rows:
        p = Z.market_position(r["market"])
        out.append({**{k: v for k, v in r.items() if k != "history"}, "label": label(r["market"]), "band": Z.band(r["heat"]) if r["heat"] is not None else None, "position": p, "returns": returns_of(r["market"]), "plan_key": PLAN_KEY.get(r["market"]), "byz": capitulation_of(r["market"])})
    summaries = {}
    for c in CLASS_ORDER:
        g = [r for r in rows if r["class"] == c and r["heat"] is not None]
        if g:
            s = Z.class_summary(g)
            ordered = sorted(g, key=lambda r: -r["heat"])
            summaries[c] = {**s, "name": Z.CLASS_IT[c], "why": Z.why_text(s), "history": class_history(g), "hottest": {"label": label(ordered[0]["market"]), "heat": ordered[0]["heat"]}, "coldest": {"label": label(ordered[-1]["market"]), "heat": ordered[-1]["heat"]}}
    return out, summaries, Z.overview(summaries) if summaries else ""


def price_series(market):
    d, bars = (crypto_daily(market), 365) if market in CRYPTO else (read("tradfi", safe(market)), 252)
    if d is None:
        return None
    c = (d if market in CRYPTO else daily(d)).close.dropna().tail(bars)
    return {"dates": [t.strftime("%Y-%m-%d") for t in c.index], "close": [float(x) for x in c.values]}


def known_market(m):
    return m in CRYPTO or m in MARKETS


def one_month(iv):
    """A year of implied volatility scaled to one month: the rough move the options price in."""
    return iv / math.sqrt(12)


def explain(name, level, cost, term, skew):
    """Plain sentences built from today's numbers."""
    out = []
    if level:
        out.append(f"Rispetto al suo passato, la volatilità attesa è {O.level(level['pct'])}: oggi è più alta del {level['pct']:.0f}% dei giorni passati.")
    if cost:
        side = {"care": "Chi compra opzioni paga più di quanto il mercato si sia mosso di recente: gli serve un movimento più grande di quello visto finora.",
                "economiche": "Chi compra opzioni paga meno di quanto il mercato si sia mosso di recente. Può guadagnare se quel ritmo continua, ma se il mercato si calma perde comunque valore col tempo.",
                "nella norma": "Il prezzo è vicino a quanto il mercato si è mosso di recente. Di solito l'attesa sta un po' sopra la realizzata."}[cost["label"]]
        move = f"{100 * one_month(cost['iv']):.1f}".replace(".", ",")
        out.append(f"Le opzioni prezzano circa ±{move}% in un mese. {side}")
    if term:
        out.append("La paura è concentrata sui prossimi giorni: spesso capita attorno a un evento o durante uno scossone." if term["inverted"] else "La paura a breve non supera quella a più lungo termine: è la situazione normale.")
    if skew is not None:
        pts = skew * 100
        out.append("Proteggersi dai ribassi costa più che scommettere sui rialzi." if pts > 1 else "Scommettere sui rialzi costa più che proteggersi dai ribassi: è insolito, e spesso capita quando si teme uno scatto verso l'alto." if pts < -1 else "Put e call costano circa uguale.")
    return out


def vol_history(block):
    """A year of implied volatility from the index, and realized from the underlying, both in percent. Empty if the units don't match."""
    out = {"dates": [], "implied": [], "realized": [], "same_units": False, "implied_name": None}
    if "index" not in block:
        return out
    s = O.index_series(*block["index"][:2])
    if s is None:
        return out
    s = s.tail(252)
    out.update(dates=[t.strftime("%Y-%m-%d") for t in s.index], implied=[float(x) for x in s.values], implied_name=block["index"][2])
    if block["index"][2] == "MOVE" or not block.get("underlying"):  # MOVE is in basis points, so it can't share an axis with realized volatility in percent
        return out
    group, name, year_days = block["underlying"]
    u = O.close_series(group, name)
    if u is not None:
        r = np.log(u.where(u > 0)).diff().rolling(O.RV_DAYS).std() * np.sqrt(year_days) * 100
        out.update(realized=[None if np.isnan(x) else float(x) for x in r.reindex(s.index, method="ffill").values], same_units=True)
    return out


def options_part():
    blocks = []
    for b in O.BLOCKS:
        try:
            chain = I.latest_options(b["chain"]) if b.get("chain") else None
        except Exception:
            chain = None
        level = O.level_line(b)
        cost = O.price_of_options(b, chain)
        term = None
        if b.get("short"):
            x, y = O.index_series("vol", b["short"]), O.index_series("vol", b["long"])
            if x is not None and y is not None:
                term = {"short": float(x.iloc[-1]), "long": float(y.iloc[-1]), "short_name": b["short"], "long_name": b["long"], "inverted": bool(x.iloc[-1] > y.iloc[-1])}
        elif chain and chain.get("iv_7d") and chain.get("iv_30d"):
            term = {"short": 100 * chain["iv_7d"], "long": 100 * chain["iv_30d"], "short_name": "7 giorni", "long_name": "30 giorni", "inverted": bool(chain["term_inverted"])}
        skew = chain.get("skew_25d") if chain else None
        blocks.append({"name": b["name"], "level": {**level, "date": level["date"].strftime("%Y-%m-%d"), "band": O.level(level["pct"])} if level else None, "cost": cost, "term": term,
                       "skew_pts": 100 * skew if skew is not None else None, "snapshot": chain.get("snapshot") if chain else None,
                       "text": explain(b["name"], level, cost, term, skew), "history": vol_history(b)})
    return blocks


def top_words(picked, pattern, n=5):
    """The words behind a count, so you can judge it: "rally" on bonds isn't euphoria."""
    seen = {}
    for x in picked:
        for w in {m.group(0).lower() for m in re.finditer(pattern, x["text"], re.I)}:
            seen[w] = seen.get(w, 0) + 1
    return [{"word": w, "n": c} for w, c in sorted(seen.items(), key=lambda kv: -kv[1])[:n]]


def tilt_of(m):
    n = m["fear"] + m["greed"]
    return "pochi segnali" if n < MIN_MOOD_SIGNALS else "prevale la paura" if m["fear"] / n > .65 else "prevale l'euforia" if m["fear"] / n < .35 else "equilibrio"


def sentiment_part(now):
    items, errors = T.load_items(now=now, hours=24 * 7)
    classes = []
    for family, name, pattern in SENTIMENT_GROUPS:
        rx = re.compile(pattern, re.I)
        week, in_week = Z.mood_of(items, rx, now, hours=24 * 7)
        m, picked = Z.mood_of(in_week, rx, now)  # the last day is a slice of the week: no second pass over every text
        seen, sample = {}, []
        for x in picked:  # balanced across sources, so one busy forum can't fill the list
            source = x["source"].split("_")[1] if x["source"].startswith("soc_") else x["source"]
            if seen.get(source, 0) < 2 and len(sample) < 6:
                seen[source] = seen.get(source, 0) + 1
                sample.append({"source": x["source"], "time": x["time"], "url": x["url"], "text": x["text"][:220]})
        classes.append({"family": family, "name": name, "full": name if family == name else f"{family}: {name}", "tilt": tilt_of(m), **m, "week": {**week, "tilt": tilt_of(week)}, "fear_words": top_words(picked, Z.FEAR), "greed_words": top_words(picked, Z.GREED), "texts_sample": sample})
    return {"classes": classes, "fear_greed": Z.fear_greed(), "attention": Z.attention(), "trends": part(trends_part, errors, "trends", []), "total": sum(x["time"] >= (now - timedelta(hours=24)).isoformat() for x in items), "total_week": len(items), "source_errors": sorted(errors)}


TOPIC_ALL = re.compile("|".join(T.TOPICS.values()), re.I)
TRENDS_JOBS = {"trends_google_us": "USA", "trends_google_it": "Italia"}


def parse_trending(body):
    """Queries from Google's public trending feed, with their rough traffic."""
    out, ns = [], "{https://trends.google.com/trending/rss}"
    for it in ET.fromstring(body).iter("item"):
        title = (it.findtext("title") or "").strip()
        if title:
            out.append({"query": title[:120], "traffic": (it.findtext(ns + "approx_traffic") or "").strip()})
    return out


def trends_part(root=None):
    """Which searches are rising now, and whether any is about markets. It's a snapshot of today: keyword history isn't open to automated reading."""
    out = []
    for job, geo in TRENDS_JOBS.items():
        files = snapshot_files(job, root)
        if not files:
            continue
        rows = parse_trending(gzip.open(files[-1]).read())
        out.append({"geo": geo, "at": snapshot_time(files[-1]).isoformat(), "total": len(rows), "market": [r for r in rows if TOPIC_ALL.search(r["query"])][:6], "top": rows[:5]})
    return out


def read_jsonl(path, limit):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows[::-1]


def since_trigger(plan, price):
    """Where the price is now against the plan, so an old alert can't look fresher than it is."""
    if not plan or not price:
        return {}
    return {"price_now": price, "since_pct": 100 * (price / plan["price"] - 1), "broken": price <= plan["stop"], "target_hit": price >= plan["target_3r"]}


def alerts_part(prices):
    out = []
    for a in read_jsonl(alert_dir() / "log.jsonl", 200):
        plan = a.get("plan") if a["setup"] != "overheating" else None
        out.append({**since_trigger(plan, prices.get(a["market"])), "plan_key": PLAN_KEY.get(a["market"]), "raw_setup": a["setup"], "market": label(a["market"]), "class": CLASS_IT.get(a["class"], a["class"]), "setup": SETUP_IT.get(a["setup"], a["setup"]), "means": SETUP_MEANS.get(a["setup"]),
                    "trigger": a["trigger"], "z": a.get("z"), "score": a.get("score"), "max_score": a.get("max_score"), "met": [COND_IT.get(n, n) for n in a.get("met", [])],
                    "not_met": [COND_IT.get(n, n) for n in a.get("not_met", [])], "unknown": [COND_IT.get(n, n) for n in a.get("unknown", [])],
                    "plan": plan, "entry_after_bars": a.get("entry_after_bars"), "verdict": test_verdict(a["class"], a["setup"])})
    moves = [{**m, "label": MOVE_NAMES.get(m["name"], m["name"]), "plan_key": PLAN_KEY.get(m.get("market"))} for m in read_jsonl(alert_dir() / "moves.jsonl", 100)]
    resets = [{**r, "label": label(r["market"]), "frame": K.FRAME_IT[r["tf"]], "plan_key": PLAN_KEY.get(r["market"])} for r in read_jsonl(alert_dir() / "resets.jsonl", 100)]
    return {"setups": out, "moves": moves, "resets": resets}


def lab_text(r):
    """The whole picture of one market's options, in plain sentences."""
    out = []
    n = r.get("near")
    if n and n.get("forecast"):
        out.append(f"Il mercato delle opzioni si aspetta una volatilità del {100 * n['atm']:.0f}% annuo, pari a circa ±{str(round(n['move_pct'], 1)).replace('.', ',')}% entro {n['days']:.0f} giorni. Il nostro modello prevede il {100 * n['forecast']:.0f}%.")
        out.append({"care": "Le opzioni costano più di quanto il modello giustifichi: chi le compra paga un premio, chi le vende lo incassa ma si prende il rischio.",
                    "economiche": "Le opzioni costano meno di quanto il modello giustifichi: per chi compra è il momento relativamente più favorevole, ma il modello può sbagliare.",
                    "nella norma": "Il prezzo è in linea con il movimento previsto: nel complesso né care né economiche."}.get(r.get("label"), ""))
    g = r.get("gex")
    if g:
        if g["regime"] == "positiva":
            out.append("Gamma positiva: se l'ipotesi sui dealer è giusta, le loro coperture tendono a frenare i movimenti del prezzo.")
        else:
            out.append("Gamma negativa: se l'ipotesi sui dealer è giusta, le loro coperture tendono ad amplificare i movimenti del prezzo.")
    return [x for x in out if x]


def lab_summary(r):
    """What the overview needs: the heavy parts stay for when a market is opened."""
    if r.get("error"):
        return r
    g = r.get("gex") or {}
    return {**{k: r.get(k) for k in ("key", "name", "ticker", "group", "spot", "snapshot", "source", "near", "ratio", "label", "realized", "n_cheap", "n_dear", "n_tradable", "note")},
            "cheap": r["cheap"][:6], "dear": r["dear"][:6], "gex": {k: g.get(k) for k in ("total", "regime", "flip", "call_wall", "put_wall", "max_pain", "put_call_oi")}, "text": lab_text(r)}


def lab_part():
    return [lab_summary(r) for r in L.all_markets()]


def lab_market(key, fresh=False):
    m = L.BY_KEY[key]
    r = L.fetch_live(m) if fresh else L.from_saved(m)
    return {**r, "text": lab_text(r)} if r else None


def sentiment_market(market):
    view = SM.market_view(market)
    return {**view, "label": label(market), "plan_key": PLAN_KEY.get(market)} if view else None


def flows_market(market):
    view = FL.level_now(market)
    return {"market": market, "label": label(market), "pos": view} if view else None


def flows_part():
    cls = {m: ("crypto" if m in CRYPTO else MARKETS[m][0]) for m in K.all_markets()}
    return [{**r, "label": label(r["market"]), "class": cls[r["market"]]} for r in FL.positioning()]


def technical_part():
    return [{**K.summary(m), "label": label(m), "plan_key": PLAN_KEY.get(m)} for m in K.all_markets()]


def technical_market(market):
    return {"label": label(market), "plan_key": PLAN_KEY.get(market), "frames": K.analyze(market)}


SETUP_RULE = {"panic": "il prezzo cade di almeno {z} deviazioni standard in una barra, rispetto alle ultime {w} barre", "squeeze": "il prezzo sale di almeno {z} deviazioni standard in una barra, rispetto alle ultime {w} barre",
              "overheating": "il prezzo è esteso verso l'alto di almeno {z} deviazioni standard rispetto alla sua media lunga"}
CLASS_MARKETS = {"crypto": "BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK", "equities": "S&P 500, Nasdaq, Russell", "bonds": "Treasury USA a 2, 5, 10 e 30 anni",
                 "commodities": "petrolio, gas, oro, argento, rame, mais, grano, soia", "fx": "EUR, JPY, GBP, AUD, CHF, CAD contro il dollaro"}


def test_reading(v, setup):
    """What one result means, in words, built from its own numbers."""
    it = lambda x: f"{x:+.2f}".replace(".", ",")
    pct = it(100 * v["mean"])
    if v["outcome"] == "supportata":
        out = [f"Dopo questo setup il mercato ha fatto in media {pct}% rispetto a ingressi casuali, e il risultato supera la soglia della sua famiglia di test."]
        out.append("Regge anche alla soglia più severa, quella che tiene conto di tutti i 15 test." if v.get("passes_global") else "Non regge però alla soglia più severa, quella che tiene conto di tutti i 15 test: può essere un falso positivo.")
    elif v["outcome"] == "non supportata":
        out = [f"La differenza media è {pct}% rispetto a ingressi casuali, e non basta per dire che il setup abbia un vantaggio. Con questi episodi un vantaggio di media grandezza si sarebbe visto {100 * v['power_d30']:.0f} volte su 100."]
    else:
        out = [f"La differenza media è {pct}%, ma gli episodi sono troppo pochi: un vantaggio di media grandezza si sarebbe visto solo {100 * v['power_d30']:.0f} volte su 100. Non si può concludere né che funzioni né che non funzioni."]
    lo, hi = 100 * v["ci90"][0], 100 * v["ci90"][1]
    out.append(f"Il vero effetto, con il 90% di confidenza, sta tra {it(lo)}% e {it(hi)}%." + (" L'intervallo comprende lo zero." if lo < 0 < hi else ""))
    link = v.get("score_link") or {}
    if link.get("spearman") is not None:
        out.append("Più conferme non hanno significato risultati migliori." if link.get("p", 1) >= .05 or link["spearman"] <= 0 else "Più conferme si sono accompagnate a risultati migliori.")
    return out


def tests_part():
    p = BASE / "config" / "validation_v1.json"
    if not p.exists():
        return None
    t = json.loads(p.read_text())
    config = json.loads((BASE / "config" / "setups_v1.json").read_text())
    rows = []
    for k, v in t["tests"].items():
        if "/" not in k or k.split("/")[1] not in SETUP_IT:
            continue
        c, setup = k.split("/")
        cc = config["classes"][c]
        z = cc[setup].get("z_long", abs(cc[setup].get("z", 0)))
        horizons = {int(n): {"mean": x["mean"], "p": x["p"]} for n, x in (v.get("other_horizons") or {}).items()}
        horizons[int(v["horizon_bars"])] = {"mean": v["mean"], "p": v["p"]}
        unit = "barre da 4 ore" if cc["bar"] == "4h" else "sedute"
        exit_part = v.get("exit_target_3R_descriptive") or {}
        rows.append({"class": c, "class_name": CLASS_IT.get(c, c), "setup": setup, "setup_name": SETUP_IT[setup], "means": SETUP_MEANS[setup], "markets": CLASS_MARKETS.get(c), "rule": SETUP_RULE[setup].format(z=z, w=cc["z_window"]), "conditions": [COND_IT.get(n, n) for n in config["scored"].get(c, {}).get(setup, [])],
                     "calibration_end": cc["calibration_end"], **{f: v.get(f) for f in ("mean", "p", "boot_p", "clusters", "events", "outcome", "passes_global", "ci90", "d", "power_d30", "share_up", "mean_net", "mean_net_stress_slippage", "skipped")},
                     "horizon_bars": v["horizon_bars"], "unit": unit, "unit_one": "barra da 4 ore" if cc["bar"] == "4h" else "seduta", "horizons": [{"bars": n, **horizons[n]} for n in sorted(horizons)], "score_link": v.get("score_link"), "reading": test_reading(v, setup),
                     "exit": {f: exit_part.get(f) for f in ("rule_R", "hold_R", "worst10_rule", "worst10_hold")} if exit_part else None})
    return rows


STUDIES = (  # every historical test, in the order they were run. Each was pre-registered and run once
    ("v3", "Le letture dell'app", "6 novembre 2026", "Ognuna delle 15 letture che l'app mostra, sulla storia 2008–2026: dopo la lettura, il prezzo ha fatto meglio di un giorno qualsiasi?", "docs/PREREGISTRAZIONE_v3.md", "docs/V3_STORICO.md"),
    ("v4", "Il momentum su mercati nuovi", "6 novembre 2026", "Dopo «scende forte» e «sale forte» (ex MOM↓ e MOM↑, e prima BYZ e SZT) il prezzo continua nella stessa direzione anche su 50 mercati mai usati?", "docs/PREREGISTRAZIONE_v4.md", "docs/V4_STORICO.md"),
    ("v5", "BYZ e SZT agli estremi e sul mensile", "6 novembre 2026", "Letti come il loro nome, agli estremi (±70) e sul mensile, su 99 azioni USA mai usate: dopo BYZ si sale, dopo SZT si scende?", "docs/PREREGISTRAZIONE_v5.md", "docs/V5_STORICO.md"),
)
WHERE = {"O": "Opzioni", "Z": "Oggi", "R": "Analisi tecnica", "T": "Oggi", "S": "Sentiment", "F": "Chi compra", "M": "Alert", "L": "Analisi tecnica", "N": "Oggi", "E": "Oggi"}


def study_row(rid, h, r):
    horizon = h.get("horizon_bars")
    return {"id": rid, "reading": h.get("reading"), "rule": h.get("rule"), "trade": h.get("trade"), "horizon": f"{horizon} barre" if horizon else h.get("horizon"),
            "where": WHERE.get(rid[0]), "mean": r.get("mean"), "mean_net": r.get("mean_net"), "p": r.get("p"), "clusters": r.get("clusters"), "power": r.get("power", r.get("power_d30")),
            "outcome": r.get("outcome"), "holm": r.get("holm_threshold")}


def studies_part():
    """Every study with its hypotheses and results, read from the frozen files so the page can't drift from them."""
    out = []
    v2 = BASE / "config" / "validation_v2_storico.json"
    if v2.exists():
        r = json.loads(v2.read_text())
        out.append({"id": "v2", "title": "Il trend lungo", "date": "6 novembre 2026", "question": "Comprare dopo l'incrocio al rialzo della media a 200 sedute e tenere 20 sedute, su cambi e materie prime dal 2008, rende più di un giorno qualsiasi?",
                    "prereg": "docs/PREREGISTRAZIONE_v2.md", "report": "docs/V2_STORICO.md",
                    "rows": [study_row("P", {"reading": "incrocio al rialzo della SMA 200", "rule": "chiusura sopra la media a 200 sedute dopo una chiusura sotto", "trade": "long", "horizon_bars": 20}, r["primary"])]})
    for vid, title, date, question, prereg, report in STUDIES:
        cfg, res = BASE / "config" / f"setups_{vid}.json", BASE / "config" / f"validation_{vid}_storico.json"
        if not (cfg.exists() and res.exists()):
            continue
        hyp, results = json.loads(cfg.read_text())["hypotheses"], json.loads(res.read_text())["results"]
        out.append({"id": vid, "title": title, "date": date, "question": question, "prereg": prereg, "report": report,
                    "rows": [study_row(k, h, results.get(k, {})) for k, h in hyp.items()]})
    return out


def freshness(now):
    files = snapshot_files("hl_ctx_main")
    minutes = max(0, int((now - snapshot_time(files[-1])).total_seconds() // 60)) if files else None  # a file stamped a moment ahead reads as now
    return {"recorder_minutes": minutes, "ok": minutes is not None and minutes <= 40}


def add_zones(markets, sentiment):
    """The momentum tags for every market, each theme's mood coming from the sentiment part."""
    moods = {c["name"]: c for c in sentiment["classes"]} if sentiment else {}
    fear_greed = (sentiment.get("fear_greed") or {}).get("value") if sentiment else None
    for m in markets:
        m["zones"] = ZN.market_zones(m["market"], moods, fear_greed)
        m["theme"] = ZN.SENTIMENT_OF.get(m["market"], (None, 1))[0]


def briefing(markets, classes, lab, tech, alerts):
    """What matters today, in sentences. Each one is built from the numbers on the page."""
    out = []
    by_tag = lambda tag: [m["label"] for m in markets if (m.get("zones") or {}).get("1d", {}).get("tag") == tag]
    down, up = by_tag("GIU"), by_tag("SU")
    if down or up:
        out.append({"tone": "zone", "text": "Momentum sul giornaliero: " + "; ".join(([f"in calo su {', '.join(down)}"] if down else []) + ([f"in salita su {', '.join(up)}"] if up else [])) + "."})
    moved = [m for m in markets if (m.get("returns") or {}).get("7g") is not None]
    if moved:
        up, down = max(moved, key=lambda m: m["returns"]["7g"]), min(moved, key=lambda m: m["returns"]["7g"])
        out.append({"tone": "move", "text": "In una settimana il rialzo più forte è di " + up["label"] + " (" + f"{up['returns']['7g']:+.1f}".replace(".", ",") + "%), il calo più forte di " + down["label"] + " (" + f"{down['returns']['7g']:+.1f}".replace(".", ",") + "%)."})
    change = [(c, s) for c, s in classes.items() if s.get("change_7d") is not None]
    if change:
        c, s = max(change, key=lambda x: abs(x[1]["change_7d"]))
        verb = "si è spostato verso l'alto" if s["change_7d"] > 0 else "si è spostato verso il basso"
        out.append({"tone": "hot" if s["change_7d"] > 0 else "cold", "text": f"Il gruppo che cambia di più è {s['name']}: {verb} di {abs(s['change_7d']):.0f} punti in 7 giorni. {s['why']}"})
    extreme = [t for t in tech if (t["rsi"].get("1d") or 50) <= 30]
    high = [t for t in tech if (t["rsi"].get("1d") or 50) >= 70]
    if extreme or high:
        bits = ([f"ipervenduto su {', '.join(t['label'] for t in extreme)}"] if extreme else []) + ([f"ipercomprato su {', '.join(t['label'] for t in high)}"] if high else [])
        out.append({"tone": "warn", "text": "RSI giornaliero agli estremi: " + "; ".join(bits) + "."})
    resets = [t["label"] for t in tech if any(t["reset"].values())]
    if resets:
        out.append({"tone": "warn", "text": f"Reset in corso su {', '.join(resets)}: l'RSI è a un estremo mentre il trend di fondo resta quello."})
    rated = [b for b in lab if b.get("ratio")]
    if rated:
        top, low = max(rated, key=lambda b: b["ratio"]), min(rated, key=lambda b: b["ratio"])
        out.append({"tone": "options", "text": "Le opzioni più care sono su " + top["name"] + " (" + f"{top['ratio']:.1f}".replace(".", ",") + " volte il movimento previsto), le più economiche su " + low["name"] + " (" + f"{low['ratio']:.1f}".replace(".", ",") + " volte)."})
    return out


def part(fn, errors, name, default):
    """One broken source must not take the whole page down: the page says which part is missing."""
    try:
        return fn()
    except Exception as e:
        errors[name] = type(e).__name__
        return default


def build(now=None):
    now = now or datetime.now(timezone.utc)
    errors = {}
    markets, summaries, overview = part(markets_part, errors, "markets", ([], {}, ""))
    lab = part(lab_part, errors, "lab", [])
    tech = part(technical_part, errors, "technical", [])
    sentiment = part(lambda: sentiment_part(now), errors, "sentiment", None)
    part(lambda: add_zones(markets, sentiment), errors, "zones", None)
    alerts = part(lambda: alerts_part({m["market"]: m["price"] for m in markets}), errors, "alerts", {"setups": [], "moves": [], "resets": []})
    return clean({"at": now.isoformat(timespec="seconds"), "markets": markets, "classes": summaries, "overview": overview, "briefing": part(lambda: briefing(markets, summaries, lab, tech, alerts), errors, "briefing", []),
                  "options": part(options_part, errors, "options", []), "lab": lab, "sentiment": sentiment, "zone_info": {"past": ZN.PAST}, "verdicts": part(VD.all_lines, errors, "verdicts", {}),
                  "alerts": alerts, "tests": part(tests_part, errors, "tests", None), "studies": part(studies_part, errors, "studies", []), "technical": tech, "flows": part(flows_part, errors, "flows", []), "wallets": part(WL.view, errors, "wallets", None),
                  "freshness": part(lambda: freshness(now), errors, "freshness", {"recorder_minutes": None, "ok": False}), "errors": errors})
