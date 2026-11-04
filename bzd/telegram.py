"""Backfill public Telegram channels through t.me/s/, newest to oldest. Stop and resume at any time.

    python -m bzd.telegram backfill [channel ...]
    python -m bzd.telegram status

Each saved message keeps its id, so it can be checked by hand at https://t.me/<channel>/<id>.
"""
import gzip, html, json, os, re, signal, sys, time, urllib.error, urllib.request
from pathlib import Path

from .recorder import BASE, UA

GAP = 3.5
# Liquidation and whale flows first: they fill the biggest data gap, and all are numeric enough to parse.
DEFAULT = ["HyperliquidLiquidations", "whale_alert_io", "BinanceLiquidations"]
LIQ = re.compile(r"#([\w.]+(?:\s*:\s*[\w.]+)?)\s+Liquidated\s+(Long|Short):\s*\$([\d.,]+)\s*([KMB]?)\s+at\s+\$([\d.,]+)")
UNIT = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}


def parse_page(body):
    """Return (id, iso time, text) for each message on a channel page."""
    out = []
    for block in re.split(r'(?=<div class="tgme_widget_message_wrap)', body)[1:]:
        post = re.search(r'data-post="[^"/]+/(\d+)"', block)
        when = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if not post or not when:
            continue
        m = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', block, re.S)
        text = re.sub(r"<br\s*/?>", "\n", m.group(1)) if m else ""
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        out.append((int(post.group(1)), when.group(1), " ".join(text.split())))
    return out


def parse_liquidation(text):
    """Return coin, side, usd, price from a liquidation post, or None."""
    m = LIQ.search(text)
    if not m:
        return None
    return {
        "coin": re.sub(r"\s", "", m.group(1)), "side": m.group(2).lower(),
        "usd": float(m.group(3).replace(",", "")) * UNIT[m.group(4)], "price": float(m.group(5).replace(",", "")),
    }


def get_page(channel, before=None):
    url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf8", "replace")


def next_cursor(before, ids):
    """Move to the oldest id seen. A page with no messages means a deleted range, so step past it."""
    return min(ids) if ids else before - 20


def backfill(root, channel, stop, get=get_page, gap=GAP, log=print):
    d = Path(root) / channel
    d.mkdir(parents=True, exist_ok=True)
    prog_path, out = d / "progress.json", d / "messages.jsonl.gz"
    prog = json.loads(prog_path.read_text()) if prog_path.exists() else {"before": None, "count": 0, "done": False}
    fails = 0
    while not prog["done"] and not stop():
        try:
            body = get(channel, prog["before"])
        except urllib.error.HTTPError as e:
            fails += 1
            wait = int(e.headers.get("Retry-After") or 0) if str(e.headers.get("Retry-After") or "").isdigit() else 0
            wait = max(wait, min(60 * 2 ** fails, 3600))
            log(f"{channel}: http {e.code}, waiting {wait}s")
            time.sleep(wait if gap else 0)
            continue
        except Exception as e:
            fails += 1
            wait = min(30 * 2 ** fails, 3600)
            log(f"{channel}: {type(e).__name__}, waiting {wait}s")
            time.sleep(wait if gap else 0)
            continue
        if "tgme_channel_info" not in body and "tgme_widget_message" not in body:
            fails += 1
            log(f"{channel}: unexpected page, waiting")
            time.sleep(min(60 * 2 ** fails, 3600) if gap else 0)
            continue
        fails = 0
        msgs = parse_page(body)
        if prog["before"] is not None:
            msgs = [m for m in msgs if m[0] < prog["before"]]  # never re-save on resume
        if msgs:
            with gzip.open(out, "at") as f:  # each append is one gzip member; readers see one stream
                for i, t, x in msgs:
                    f.write(json.dumps({"id": i, "t": t, "text": x}, ensure_ascii=False) + "\n")
        before = next_cursor(prog["before"] if prog["before"] is not None else 0, [m[0] for m in msgs])
        prog["count"] += len(msgs)
        prog["before"] = before
        prog["oldest"] = msgs[0][1] if msgs else prog.get("oldest")
        prog["done"] = before <= 1
        tmp = prog_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(prog))
        tmp.replace(prog_path)
        if prog["count"] % 2000 < len(msgs):
            log(f"{channel}: {prog['count']} messages, back to {prog.get('oldest')}")
        time.sleep(gap)
    return prog


def main(argv):
    root = Path(os.environ.get("BZD_DATA", BASE / "data")) / "telegram"
    if argv and argv[0] == "backfill":
        flag = {"stop": False}
        for s in (signal.SIGINT, signal.SIGTERM):
            signal.signal(s, lambda *_: flag.update(stop=True))
        for c in argv[1:] or DEFAULT:
            p = backfill(root, c, lambda: flag["stop"], log=lambda m: print(m, flush=True))
            print(f"{c}: {'done' if p['done'] else 'paused'}, {p['count']} messages", flush=True)
        return 0
    if argv and argv[0] == "status":
        for p in sorted(root.glob("*/progress.json")):
            d = json.loads(p.read_text())
            print(f"{p.parent.name:28} {'done' if d['done'] else 'running':8} {d['count']:>8,} messages, back to {d.get('oldest')}, next id {d['before']}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
