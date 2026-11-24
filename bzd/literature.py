"""The literature catalogue: which papers exist on what BZD does, so that a summary can be checked against a real record. Free sources only, and no LLM.

    python -m bzd.literature run              # search every topic, merge into data/literature/catalog.json and write docs/CATALOGO.md
    python -m bzd.literature check "a title"  # is this paper in the catalogue? Prints the closest matches

It lists papers and doesn't read them, so a paper here supports nothing until someone has read it. Summaries are done by hand and checked here.
A reference list from a PDF can be added later with the same record shape.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
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
}


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


def search_openalex(query, topic):
    q = urllib.parse.urlencode({"search": query, "per-page": PER_TOPIC, "select": "id,doi,title,publication_year,cited_by_count,authorships,open_access,primary_location"})
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


def run(root=None, sleep=time.sleep):
    p, found, failed = path(root), [], []
    old = json.loads(p.read_text()) if p.exists() else []
    for topic, query in TOPICS.items():
        for name, search in (("OpenAlex", search_openalex), ("arXiv", search_arxiv)):
            try:
                found += search(query, topic)
            except Exception as e:  # one source being down must not lose the other
                failed.append(f"{name}/{topic}: {type(e).__name__}")
            sleep(GAP_SECONDS)
    rows = sorted(merge(old, found), key=lambda r: (-r["cited"], r["title"]))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    return rows, failed


def markdown(rows, today=None):
    today = today or datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = ["# Catalogo della letteratura", "", f"Aggiornato al {today}: {len(rows)} lavori da OpenAlex e arXiv, con `python -m bzd.literature run`. L'elenco completo è in `data/literature/catalog.json`.", "",
             "Sono risultati di ricerca per pertinenza, ordinati per citazioni. **Nessuno è stato letto**: esserci non vuol dire che sostenga una tesi, e alcuni possono essere fuori tema. I preprint arXiv hanno 0 citazioni perché la fonte non le dà.", ""]
    for topic in TOPICS:
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
