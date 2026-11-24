"""The literature catalogue: which papers exist on what BZD does, so that a summary can be checked against a real record. Free sources only, and no LLM.

    python -m bzd.literature run              # search every topic, merge into data/literature/catalog.json and write docs/CATALOGO.md
    python -m bzd.literature check "a title"  # is this paper in the catalogue? Prints the closest matches

It lists papers and doesn't read them, so a paper here supports nothing until someone has read it. Summaries are done by hand and checked here.
A reference list from a PDF can be added later with the same record shape.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .recorder import BASE

UA = "BZD research catalogue"
PER_TOPIC, GAP_SECONDS, KEEP_PER_TOPIC = 25, 3, 12  # arXiv asks for one request every 3 seconds
ATOM = "{http://www.w3.org/2005/Atom}"
TOPICS = {
    "Retail e flussi": "retail investors order flow contrarian buying after price declines",
    "Long e short per conti, cripto": "cryptocurrency futures long short ratio retail traders positioning",
    "Posizioni COT": "commitments of traders speculators positions futures returns",
    "Compratori aggressivi e flussi": "order flow imbalance taker trades price impact cryptocurrency",
    "Funding e leva cripto": "perpetual futures funding rate leverage liquidations cryptocurrency",
    "Panico e rimbalzi": "short-term reversal after extreme price declines liquidity provision",
    "Uscite e stop": "stop-loss rules profit taking exit strategy performance",
    "Effetto disposizione": "disposition effect investors sell winners too early",
    "Sentiment": "investor sentiment social media predicts stock or cryptocurrency returns",
    "Volatilità implicita": "implied volatility forecasting HAR realized volatility options",
    "Esposizione gamma": "dealer gamma exposure options market maker hedging volatility",
    "Test multipli": "backtest overfitting multiple testing trading strategies",
    "Premio sulla volatilità": "variance risk premium option returns equity index bitcoin",
    "Opzioni cripto": "bitcoin options implied volatility smile Deribit",
    "Momentum delle serie storiche": "time series momentum futures trend following returns",
    "Correlazione azioni e bond": "stock bond correlation inflation regime change",
    "Liquidazioni cripto": "cryptocurrency liquidation cascades leverage crash",
}
# Market psychology, added on 24 November 2026 for a deep dive: the biases and emotions behind buying lows and selling highs
PSYCH_TOPICS = {
    "Psicologia: avversione alle perdite": "prospect theory loss aversion asset prices investors",
    "Psicologia: eccesso di fiducia": "overconfidence investors excessive trading returns",
    "Psicologia: comportamento gregge": "herding behavior financial markets investors crashes",
    "Psicologia: attenzione limitata": "investor attention limited attention stock returns search volume",
    "Psicologia: aspettative estrapolative": "extrapolative expectations investor surveys returns bubbles",
    "Psicologia: bolle ed euforia": "speculative bubbles investor euphoria overreaction experimental markets",
    "Psicologia: paura e panico": "fear emotions panic selling market crashes investors",
    "Psicologia: ancoraggio ai massimi": "anchoring 52-week high investor behavior momentum",
    "Psicologia: preferenza per la lotteria": "lottery-like stocks gambling preferences retail investors",
    "Psicologia: umore e sentiment": "investor mood weather sports outcomes stock returns",
    "Psicologia: FOMO e cripto retail": "fear of missing out cryptocurrency retail investors speculation",
    "Psicologia: vendere i vincitori": "realization utility selling winners holding losers individual investors",
    "Psicologia: neurofinanza": "neurofinance brain trading decisions risk taking",
    "Psicologia: reazione alle notizie": "investor underreaction overreaction news limited attention",
}
TOPICS.update(PSYCH_TOPICS)
SNOWBALL = "Citano lavori letti"  # newer works that cite a paper the reader found relevant (bzd.research scopri)
RECENT_DAYS = 730


def path(root=None):
    return Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "literature" / "catalog.json"


def fetch(url, tries=4, sleep=time.sleep):
    """Both sources refuse now and then without notice, so a busy answer is retried with a growing pause."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
        sleep(15 * 2 ** attempt)


def openalex_record(w, topic):
    """One work from OpenAlex, or None without a title."""
    if not w.get("title"):
        return None
    oa, names = w.get("open_access") or {}, [(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []]
    venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return {"title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", w["title"])).strip(), "year": w.get("publication_year"), "authors": [n for n in names if n][:4], "venue": venue, "cited": w.get("cited_by_count") or 0,
            "url": w.get("doi") or w.get("id"), "open_url": oa.get("oa_url"), "source": "OpenAlex", "topics": [topic]}


SELECT = "id,doi,title,publication_year,cited_by_count,authorships,open_access,primary_location"


def search_openalex(query, topic, since=None):
    """Most relevant works; with `since` (YYYY-MM-DD) only those published after it, so new work isn't buried under old citations."""
    q = urllib.parse.urlencode({"search": query, "per-page": PER_TOPIC, "select": SELECT, **({"filter": f"from_publication_date:{since}"} if since else {})})
    rows = (openalex_record(w, topic) for w in json.loads(fetch("https://api.openalex.org/works?" + q)).get("results", []))
    return [r for r in rows if r]


def parse_arxiv(raw, topic):
    out = []
    for e in ET.fromstring(raw).findall(f"{ATOM}entry"):
        title, link = e.findtext(f"{ATOM}title"), e.findtext(f"{ATOM}id")
        if title and link:
            out.append({"title": re.sub(r"\s+", " ", title).strip(), "year": int((e.findtext(f"{ATOM}published") or "0")[:4]) or None, "authors": [a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")][:4],
                        "venue": "arXiv", "cited": 0, "url": link, "open_url": link, "source": "arXiv", "topics": [topic]})
    return out


def search_arxiv(query, topic):
    words = " AND ".join(f"all:{w}" for w in query.split()[:4])
    return parse_arxiv(fetch("https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": words, "max_results": PER_TOPIC // 2, "sortBy": "relevance"})), topic)


def key(title):
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def merge(old, new):
    """One record per title. The published version wins over a preprint, and topics add up."""
    out = {key(r["title"]): r for r in old}
    for r in new:
        k = key(r["title"])
        if k not in out:
            out[k] = r
            continue
        have = out[k]
        best, other = (r, have) if have["source"] == "arXiv" and r["source"] != "arXiv" else (have, r)
        out[k] = {**best, "cited": max(have["cited"], r["cited"]), "open_url": best.get("open_url") or other.get("open_url"), "topics": sorted(set(have["topics"]) | set(r["topics"]))}
    return list(out.values())


def citing(work, topic, n=8):
    """The most cited works that cite `work` (an OpenAlex id or a DOI), newest research building on a paper already read."""
    ident = work.rsplit("/", 1)[1] if "openalex.org/" in work else "doi:" + re.sub(r"^https?://(dx\.)?doi\.org/", "", work)
    wid = json.loads(fetch("https://api.openalex.org/works/" + urllib.parse.quote(ident, safe=":/") + "?select=id"))["id"].rsplit("/", 1)[1]
    q = urllib.parse.urlencode({"filter": f"cites:{wid}", "sort": "cited_by_count:desc", "per-page": n, "select": SELECT})
    rows = (openalex_record(w, topic) for w in json.loads(fetch("https://api.openalex.org/works?" + q)).get("results", []))
    return [r for r in rows if r]


def save(rows, root=None):
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(rows, key=lambda r: (-r["cited"], r["title"])), ensure_ascii=False, indent=0))


def load(root=None):
    p = path(root)
    return json.loads(p.read_text()) if p.exists() else []


def run(root=None, sleep=time.sleep, today=None, topics=None):
    """Search every topic, or only `topics` (a dict like TOPICS)."""
    found, failed = [], []
    old = load(root)
    since = ((today or datetime.now(timezone.utc)) - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    for topic, query in (topics or TOPICS).items():
        for name, search in (("OpenAlex", search_openalex), ("OpenAlex recenti", lambda q, t: search_openalex(q, t, since)), ("arXiv", search_arxiv)):
            try:
                found += search(query, topic)
            except Exception as e:  # one source being down must not lose the other
                failed.append(f"{name}/{topic}: {type(e).__name__}")
            sleep(GAP_SECONDS)
    rows = merge(old, found)
    save(rows, root)
    return load(root), failed


def markdown(rows, today=None):
    today = today or datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = ["# Catalogo della letteratura", "", f"Aggiornato al {today}: {len(rows)} lavori da OpenAlex e arXiv, con `python -m bzd.literature run` e, ogni mese, `python -m bzd.research mese`. L'elenco completo è in `data/literature/catalog.json`.", "",
             "Sono risultati di ricerca per pertinenza, ordinati per citazioni. **Esserci non vuol dire che sostenga una tesi**, e alcuni possono essere fuori tema. Quelli letti hanno una nota in `docs/letteratura/NOTE.md`. I preprint arXiv hanno 0 citazioni perché la fonte non le dà.", ""]
    for topic in [*TOPICS, SNOWBALL]:
        picked = [r for r in rows if topic in r["topics"]][:KEEP_PER_TOPIC]
        if not picked:
            continue
        lines += [f"## {topic}", "", "| Anno | Citazioni | Lavoro | Autori | Dove |", "|---|---:|---|---|---|"]
        for r in picked:
            title = r["title"].replace("|", "/")
            names = ", ".join(r["authors"][:2]) + (" e altri" if len(r["authors"]) > 2 else "")
            lines.append(f"| {r['year'] or '–'} | {r['cited']} | [{title}]({r['url']}) | {names} | {(r['venue'] or '–').replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


def check(title, rows, n=3):
    """The closest titles with how close they are, so an invented reference shows up as a poor match."""
    k = key(title)
    return sorted(((round(SequenceMatcher(None, k, key(r["title"])).ratio(), 2), r) for r in rows), key=lambda x: -x[0])[:n]


def main(argv):
    if argv[:1] == ["run"]:
        rows, failed = run()
        (BASE / "docs" / "CATALOGO.md").write_text(markdown(rows))
        print(f"{len(rows)} papers; failed: {failed or 'none'}")
        return 0
    if argv[:1] == ["check"] and len(argv) > 1:
        p = path()
        for score, r in check(" ".join(argv[1:]), json.loads(p.read_text()) if p.exists() else []):
            print(f"{score:.2f}  {r['title']} ({r['year']}) {r['url']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
