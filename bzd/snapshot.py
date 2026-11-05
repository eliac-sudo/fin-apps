"""Everything the app shows, read from saved data. No orders, no paid calls, nothing written."""
import gzip, json, math, os, re, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import indicators as I
from . import options_report as O
from . import technicals as K
from . import texts as T
from . import thermo as Z
from .alerts import CLASS_IT, COND_IT, SETUP_IT, SETUP_MEANS, alert_dir, test_verdict
from .events import crypto_daily, daily, read
from .history import CRYPTO, MARKETS, safe
from .moves import NAMES as MOVE_NAMES, snapshot_files, snapshot_time
from .recorder import BASE

CLASS_ORDER = ("crypto", "equities", "bonds", "commodities", "fx")
MOOD_CLASSES = ("crypto", "equities", "bonds", "commodities", "fx")


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


def markets_part():
    rows = Z.all_readings()
    out = []
    for r in rows:
        p = Z.market_position(r["market"])
        out.append({**r, "label": label(r["market"]), "band": Z.band(r["heat"]) if r["heat"] is not None else None, "position": p})
    summaries = {}
    for c in CLASS_ORDER:
        g = [r for r in rows if r["class"] == c and r["heat"] is not None]
        if g:
            s = Z.class_summary(g)
            summaries[c] = {**s, "name": Z.CLASS_IT[c], "why": Z.why_text(s)}
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


def sentiment_part(now):
    items, errors = T.load_items(now=now, hours=24)
    classes, until = [], now.isoformat()
    for c in MOOD_CLASSES:
        m = Z.mood(items, c, now)
        picks = T.select_for(items, c, None, until, per_source=2, total=6)
        classes.append({"class": c, "name": Z.CLASS_IT[c], **m, "texts_sample": [{"source": x["source"], "time": x["time"], "url": x["url"], "text": x["text"][:220]} for x in picks]})
    return {"classes": classes, "fear_greed": Z.fear_greed(), "attention": Z.attention(), "trends": part(trends_part, errors, "trends", []), "total": len(items), "source_errors": sorted(errors)}


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
        out.append({**since_trigger(plan, prices.get(a["market"])), "market": label(a["market"]), "class": CLASS_IT.get(a["class"], a["class"]), "setup": SETUP_IT.get(a["setup"], a["setup"]), "means": SETUP_MEANS.get(a["setup"]),
                    "trigger": a["trigger"], "z": a.get("z"), "score": a.get("score"), "max_score": a.get("max_score"), "met": [COND_IT.get(n, n) for n in a.get("met", [])],
                    "not_met": [COND_IT.get(n, n) for n in a.get("not_met", [])], "unknown": [COND_IT.get(n, n) for n in a.get("unknown", [])],
                    "plan": plan, "entry_after_bars": a.get("entry_after_bars"), "verdict": test_verdict(a["class"], a["setup"])})
    moves = [{**m, "label": MOVE_NAMES.get(m["name"], m["name"])} for m in read_jsonl(alert_dir() / "moves.jsonl", 100)]
    resets = [{**r, "label": label(r["market"]), "frame": K.FRAME_IT[r["tf"]]} for r in read_jsonl(alert_dir() / "resets.jsonl", 100)]
    return {"setups": out, "moves": moves, "resets": resets}


def technical_part():
    return [{**K.summary(m), "label": label(m)} for m in K.all_markets()]


def technical_market(market):
    return {"label": label(market), "frames": K.analyze(market)}


def tests_part():
    p = BASE / "config" / "validation_v1.json"
    if not p.exists():
        return None
    t = json.loads(p.read_text())
    rows = []
    for k, v in t["tests"].items():
        if "/" in k and k.split("/")[1] in SETUP_IT:
            c, s = k.split("/")
            rows.append({"class": c, "class_name": CLASS_IT.get(c, c), "setup": s, "setup_name": SETUP_IT[s], "mean": v.get("mean"), "p": v.get("p"), "clusters": v.get("clusters"), "outcome": v.get("outcome"), "passes_global": v.get("passes_global")})
    return rows


def freshness(now):
    files = snapshot_files("hl_ctx_main")
    minutes = int((now - snapshot_time(files[-1])).total_seconds() // 60) if files else None
    return {"recorder_minutes": minutes, "ok": minutes is not None and minutes <= 40}


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
    return clean({"at": now.isoformat(timespec="seconds"), "markets": markets, "classes": summaries, "overview": overview,
                  "options": part(options_part, errors, "options", []), "sentiment": part(lambda: sentiment_part(now), errors, "sentiment", None),
                  "alerts": part(lambda: alerts_part({m["market"]: m["price"] for m in markets}), errors, "alerts", {"setups": [], "moves": [], "resets": []}), "tests": part(tests_part, errors, "tests", None), "technical": part(technical_part, errors, "technical", []),
                  "freshness": part(lambda: freshness(now), errors, "freshness", {"recorder_minutes": None, "ok": False}), "errors": errors})
