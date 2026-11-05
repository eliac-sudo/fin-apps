"""Agent 3: turn saved news and social responses into dated, deduplicated texts, each traceable to its raw file.

Everything here is untrusted third-party text. It is only ever passed on as data.
"""
import gzip, hashlib, html, json, os, re, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from .recorder import BASE
from .telegram import parse_page

MAX_CHARS = 600  # per text, so one long post can't dominate the prompt
FILES_PER_JOB = 12
SKIP_JOBS = ("news_gdelt_tone", "soc_tg_binanceliquidations", "soc_tg_hyperliquidliquidations")  # numbers, not readable text
TOPICS = {
    "crypto": r"crypto|bitcoin|btc|ethereum|\beth\b|solana|altcoin|stablecoin|liquidat|binance|hyperliquid|funding",
    "equities": r"stock|s&p|nasdaq|russell|equit|wall street|\bfed\b|powell|earnings|recession",
    "bonds": r"treasur|bond|yield|\bfed\b|\becb\b|powell|lagarde|inflation|rate cut|rate hike",
    "commodities": r"commodit|\boil\b|crude|\bgold\b|silver|copper|natural gas|wheat|\bcorn\b|soybean|grain|opec",
    "fx": r"forex|dollar|\beuro\b|\byen\b|sterling|\bfed\b|\becb\b|boj|intervention|currency",
    "CL=F": r"\boil\b|crude|wti|brent|opec|barrel|refiner|hormuz",
    "NG=F": r"natural gas|\blng\b|henry hub",
    "GC=F": r"\bgold\b|bullion|\bfed\b|real yield|safe haven",
    "SI=F": r"silver|precious metal",
    "HG=F": r"copper|china demand",
    "ZC=F": r"\bcorn\b|grain|usda", "ZW=F": r"wheat|grain|usda", "ZS=F": r"soybean|grain|usda",
    "BTC": r"bitcoin|btc", "ETH": r"ethereum|\beth\b", "SOL": r"solana|\bsol\b", "BNB": r"\bbnb\b|binance coin", "XRP": r"\bxrp\b|ripple",
    "DOGE": r"doge", "ADA": r"cardano|\bada\b", "AVAX": r"avalanche|avax", "LINK": r"chainlink",
}


def clean(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_time(s):
    if not s:
        return None
    s = s.strip()
    try:
        if re.fullmatch(r"\d{8}T\d{6}Z", s):
            return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if s[:4].isdigit():
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_feed(body):
    """RSS and Atom. Returns (time, url, text)."""
    out = []
    root = ET.fromstring(body)
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            name = local(c.tag)
            if name == "link":
                f.setdefault("link", (c.text or "").strip() or c.get("href", ""))
            elif name not in f:
                f[name] = c.text or ""
        text = clean(f.get("title", "")) + (". " + clean(f.get("description") or f.get("summary") or f.get("content")) if (f.get("description") or f.get("summary") or f.get("content")) else "")
        out.append((parse_time(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date")), f.get("link", ""), text))
    return out


def parse_bluesky(body):
    out = []
    for p in json.loads(body).get("posts", []):
        rkey, handle = p["uri"].rsplit("/", 1)[-1], p.get("author", {}).get("handle", "")
        out.append((parse_time(p.get("record", {}).get("createdAt")), f"https://bsky.app/profile/{handle}/post/{rkey}", clean(p.get("record", {}).get("text"))))
    return out


def parse_mastodon(body):
    return [(parse_time(p.get("created_at")), p.get("url", ""), clean(p.get("content"))) for p in json.loads(body)]


def parse_4chan(body):
    out = []
    for page in json.loads(body):
        for t in page.get("threads", []):
            if t.get("sticky"):
                continue
            text = (clean(t.get("sub")) + ". " + clean(t.get("com"))).strip(". ")
            out.append((datetime.fromtimestamp(t["time"], timezone.utc), f"https://boards.4chan.org/biz/thread/{t['no']}", text))
    return out


def parse_gdelt(body):
    return [(parse_time(a.get("seendate")), a.get("url", ""), clean(a.get("title"))) for a in json.loads(body).get("articles", [])]


def parse_tg(body, job):
    channel = job.removeprefix("soc_tg_")
    return [(parse_time(t), f"https://t.me/s/{channel}/{i}", x) for i, t, x in parse_page(body.decode("utf8", "replace"))]


def parse_job(job, body):
    if job.startswith("soc_bluesky"):
        return parse_bluesky(body)
    if job.startswith("soc_mastodon"):
        return parse_mastodon(body)
    if job.startswith("soc_4chan"):
        return parse_4chan(body)
    if job.startswith("news_gdelt_art"):
        return parse_gdelt(body)
    if job.startswith("soc_tg_"):
        return parse_tg(body, job)
    return parse_feed(body)


def item_id(url, text):
    return "t" + hashlib.sha256((url or text).encode()).hexdigest()[:10]


def load_items(root=None, now=None, hours=72):
    """All readable texts of the last `hours`, newest first, with the raw file each came from."""
    root = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw"
    now = now or datetime.now(timezone.utc)
    start, items, errors = now - timedelta(hours=hours), {}, {}
    days = {(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(hours // 24 + 2)}
    for job_dir in sorted(root.iterdir()) if root.exists() else []:
        job = job_dir.name
        if not job.startswith(("news_", "soc_")) or job.startswith(SKIP_JOBS):
            continue
        files = sorted((p for d in job_dir.iterdir() if d.name in days for p in d.glob("*.gz")), key=lambda p: (p.parent.name, p.name))[-FILES_PER_JOB:]
        for path in files:
            try:
                body = gzip.open(path).read()
                rows = parse_job(job, body)
            except Exception as e:  # one malformed response must not stop the others
                errors[job] = type(e).__name__
                continue
            sha = hashlib.sha256(body).hexdigest()
            for t, url, text in rows:
                if not text or t is None or not (start <= t <= now):
                    continue
                i = item_id(url, text)
                if i not in items:
                    items[i] = {"id": i, "source": job, "time": iso(t), "url": url, "text": text[:MAX_CHARS], "raw_file": str(path.relative_to(root.parent)), "raw_sha256": sha}
    return sorted(items.values(), key=lambda x: x["time"], reverse=True), errors


def topic_pattern(cls, market):
    parts = [TOPICS[k] for k in (market, cls) if k in TOPICS]
    return re.compile("|".join(parts), re.I) if parts else None


def select_for(items, cls, market, until, per_source=6, total=60):
    """Texts on this market's topic, published no later than the alert, balanced across sources."""
    pat, counts, out = topic_pattern(cls, market), {}, []
    for it in items:
        if it["time"] > until or (pat and not pat.search(it["text"])):
            continue
        family = it["source"].split("_")[1] if it["source"].startswith("soc_") else it["source"]
        if counts.get(family, 0) >= per_source:
            continue
        counts[family] = counts.get(family, 0) + 1
        out.append(it)
        if len(out) >= total:
            break
    return out
