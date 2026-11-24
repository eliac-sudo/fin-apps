"""B4: your labels on 100 texts, to check whether the sentiment word count reads texts the way you do.

    python -m bzd.labels prepara     choose the 100 texts once and save them (free)
    python -m bzd.labels stato       how many you have labelled
    python -m bzd.labels confronta   agreement between your labels and the word count (Cohen's kappa)

You label in the app, under Sentiment. The set is chosen once with a fixed seed and never changes, so later
methods (an LLM labeller, new word lists) are measured on the same texts. The roadmap gate is kappa >= 0.6.
"""
import json, os, random, re, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .recorder import BASE

LABELS = ("paura", "neutro", "euforia", "non pertinente")
SIZE = {"paura": 25, "euforia": 25, "altro": 50}  # half where the words see a mood, half without, to catch both false alarms and misses
SEED = 20261106
DAYS = 30


def root():
    p = Path(os.environ.get("BZD_DATA", BASE / "data")) / "sentiment"
    p.mkdir(parents=True, exist_ok=True)
    return p


def word_label(text):
    """What the word count says about one text: fear words, euphoria words, both, or neither."""
    from .thermo import FEAR, GREED
    f, g = bool(re.search(FEAR, text, re.I)), bool(re.search(GREED, text, re.I))
    return "paura" if f and not g else "euforia" if g and not f else "misto" if f and g else "neutro"


def prepare(items, seed=SEED):
    """100 market texts: 25 the words read as fear, 25 as euphoria, 50 with neither. Shuffled, so you don't see the strata."""
    from .sentiment import GROUPS
    market = re.compile("|".join(g[2] for g in GROUPS), re.I)
    seen, pool = set(), {k: [] for k in SIZE}
    for it in items:
        key = re.sub(r"\W+", " ", it["text"].lower())[:120]
        if key in seen or not market.search(it["text"]) or len(it["text"]) < 40:
            continue
        seen.add(key)
        stratum = {"paura": "paura", "euforia": "euforia", "neutro": "altro"}.get(word_label(it["text"]))
        if stratum:  # texts with both kinds of words are left out: the count can't read them either way
            pool[stratum].append(it)
    rng, chosen = random.Random(seed), []
    for k, n in SIZE.items():
        chosen += rng.sample(sorted(pool[k], key=lambda x: x["id"]), min(n, len(pool[k])))
    rng.shuffle(chosen)
    return [{"id": x["id"], "text": x["text"], "source": x["source"], "time": x["time"], "url": x["url"], "raw_file": x["raw_file"], "raw_sha256": x["raw_sha256"]} for x in chosen]


def label_set():
    p = root() / "label_set.json"
    return json.loads(p.read_text())["texts"] if p.exists() else []


def labels():
    """Your latest label per text."""
    p, out = root() / "labels.jsonl", {}
    for line in (p.read_text().splitlines() if p.exists() else []):
        r = json.loads(line)
        out[r["id"]] = r["label"]
    return out


def save_label(text_id, label):
    if label not in LABELS or text_id not in {t["id"] for t in label_set()}:
        raise ValueError("testo o etichetta sconosciuti")
    with open(root() / "labels.jsonl", "a") as f:
        f.write(json.dumps({"id": text_id, "label": label, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")


def next_text():
    """The first text you haven't labelled, with progress, for the app."""
    s, done = label_set(), labels()
    todo = [t for t in s if t["id"] not in done]
    return {"total": len(s), "done": len(s) - len(todo), "labels": list(LABELS), "text": todo[0] if todo else None, "counts": Counter(done.values())}


def kappa(a, b):
    """Cohen's kappa between two lists of labels on the same texts."""
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return None if pe == 1 else (po - pe) / (1 - pe)


def compare(method=word_label):
    """Agreement with your labels, on the texts you judged relevant. A word count can't say 'not relevant', so those are left out."""
    s, mine = {t["id"]: t for t in label_set()}, labels()
    rows = [(mine[i], method(s[i]["text"])) for i in mine if i in s and mine[i] != "non pertinente"]
    a, b = [x for x, _ in rows], [("neutro" if y == "misto" else y) for _, y in rows]
    table = Counter(zip(a, b))
    return {"n": len(rows), "not_relevant": sum(v == "non pertinente" for v in mine.values()), "kappa": kappa(a, b),
            "agreement": sum(x == y for x, y in zip(a, b)) / len(rows) if rows else None, "table": {f"{x}→{y}": n for (x, y), n in sorted(table.items())}}


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "prepara":
        if label_set():
            print("il set esiste già e non cambia: le etichette restano confrontabili")
            return 1
        from .texts import load_items
        items, _ = load_items(hours=24 * DAYS)
        chosen = prepare(items)
        (root() / "label_set.json").write_text(json.dumps({"made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": SEED, "texts": chosen}, ensure_ascii=False, indent=1))
        print(f"{len(chosen)} testi scelti")
        return 0
    if cmd == "stato":
        n = next_text()
        print(f"{n['done']} su {n['total']} etichettati: {dict(n['counts'])}")
        return 0
    if cmd == "confronta":
        r = compare()
        k = "–" if r["kappa"] is None else f"{r['kappa']:.2f}"
        print(f"Conteggio di parole contro te, su {r['n']} testi pertinenti: kappa {k}, accordo {100 * (r['agreement'] or 0):.0f}%. Soglia della roadmap: 0,60.")
        print("Tu → parole:", r["table"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
