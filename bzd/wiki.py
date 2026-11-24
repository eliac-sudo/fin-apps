"""The engine wiki: how BZD works, one page per part, every claim pointing at the code, data folder or document behind it.

    python -m bzd.wiki lint      check every citation, link and data folder; exits 1 on a broken one
    python -m bzd.wiki pagine    list the pages by kind

The pattern follows Karpathy's "LLM Wiki": raw sources stay untouched (here the code, `data/` and `docs/`), the wiki is a
folder of linked markdown pages (`docs/wiki/`), and lint checks the pages against the sources. Pages are written by hand or
by Claude in the repo, never by a model at run time. The app reads them through `pages()` and adds what the files say now:
the line a function starts on, how many files a data folder holds and when it last changed. Standard library only.
"""
import ast, gzip, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "docs" / "wiki"
KINDS = [("fonte", "Fonti"), ("raccolta", "Raccolta"), ("calcolo", "Calcoli"), ("verifica", "Verifiche"), ("uscita", "Uscite")]
LISTS = ("code", "data", "docs", "feeds")
# What the app may show as text. Data stays out except for a short preview, and anything that could hold a secret is refused.
SOURCE_OK = re.compile(r"^(bzd/[\w]+\.(py|html)|docs/[\w/À-ú.-]+\.md|config/[\w.-]+\.json|scripts/[\w.-]+\.sh|deploy/[\w./-]+|README\.md|ROADMAP\.md|tests/[\w]+\.py)$")
SECRET = re.compile(r"(^|/)(\.env|state\.json)$|token|secret|passw|\.session|key", re.I)
STALE_HOURS = {"live": 3, "daily": 30}
CITE = re.compile(r"`((?:bzd|docs|config|scripts|deploy|data|tests)/[^`\s*<>]+|README\.md|ROADMAP\.md)`")  # a path with * or <> is a pattern, not a citation
LINK = re.compile(r"\[\[([\w-]+)(?:\|([^\]]+))?\]\]")


def parse(text):
    """Front matter between --- lines, `key: value`, lists comma-separated. Then the body."""
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    for k in LISTS:
        meta[k] = [x.strip() for x in meta.get(k, "").split(",") if x.strip()]
    return meta, body.strip()


def split_ref(ref):
    path, _, sym = ref.partition("#")
    return path, sym


_LINES, _GRAPH = {}, {}


def _lines(p):
    """A file's lines, read again only when the file changes."""
    key = (p, p.stat().st_mtime_ns)
    if key not in _LINES:
        if len(_LINES) > 200:
            _LINES.clear()
        _LINES[key] = p.read_text(errors="replace").splitlines()
    return _LINES[key]


def find_line(path, sym):
    """Where a name is defined: a Python def, class or constant, a JS function or app tab, or a markdown heading. 0 if missing."""
    p = ROOT / path
    if not p.is_file():
        return 0
    if not sym:
        return 1
    lines = _lines(p)
    e = re.escape(sym)
    for pat in (rf"^\s*(async\s+)?(def|class)\s+{e}\b", rf"^{e}\s*[:=]", rf"\bfunction\s+{e}\b", rf"^{e}\(\)\{{", rf"^#+\s.*{e}", rf"\b{e}\b"):
        for i, line in enumerate(lines, 1):
            if re.search(pat, line, re.I if pat.startswith("^#") else 0):
                return i
    return 0


_FACTS = {}
FACTS_SECONDS = 30


def folder_facts(path, now=None):
    """How many files, how big, and when the newest one changed. Walks at most 20000 files, then says it stopped.

    A walk is reused for FACTS_SECONDS, so one page view walks data/raw once rather than once per page that cites it."""
    now = now or time.time()
    hit = _FACTS.get((ROOT, path))
    if hit and abs(now - hit[0]) < FACTS_SECONDS:
        facts = dict(hit[1])
        if facts.get("newest"):
            facts["age_h"] = (now - facts["newest"]) / 3600
        return facts
    facts = _walk(path, now)
    _FACTS[(ROOT, path)] = (now, facts)
    return dict(facts)


def _walk(path, now):
    p = ROOT / path
    if not p.exists():
        return {"exists": False}
    if p.is_file():
        st = p.stat()
        return {"exists": True, "files": 1, "bytes": st.st_size, "newest": st.st_mtime, "age_h": (now - st.st_mtime) / 3600}
    n = size = 0
    newest = 0.0
    for f in p.rglob("*"):
        if f.is_file():
            st = f.stat()
            n, size, newest = n + 1, size + st.st_size, max(newest, st.st_mtime)
            if n >= 20000:
                break
    return {"exists": True, "files": n, "bytes": size, "newest": newest or None, "age_h": (now - newest) / 3600 if newest else None, "capped": n >= 20000}


def module_graph():
    """Which bzd module imports which, read from the code itself so it can't drift from it. Parsed again only when a file changes."""
    files = sorted((ROOT / "bzd").glob("*.py"))
    key = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    if key not in _GRAPH:
        _GRAPH.clear()
        _GRAPH[key] = _imports(files)
    return _GRAPH[key]


def _imports(files):
    edges = set()
    for f in files:
        try:
            tree = ast.parse(f.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                names = [node.module] if node.module else [a.name for a in node.names]
                for m in names:
                    m = (m or "").split(".")[0]
                    if m and (ROOT / "bzd" / f"{m}.py").exists() and m != f.stem:
                        edges.add((f.stem, m))
    return sorted(edges)


def load():
    out = {}
    for f in sorted(WIKI.glob("*.md")):
        if f.stem in ("index", "log", "README"):
            continue
        meta, body = parse(f.read_text())
        out[f.stem] = {"slug": f.stem, "title": meta.get("title", f.stem), "kind": meta.get("kind", "calcolo"), "status": meta.get("status", ""),
                       "brief": meta.get("brief", ""), "fresh": meta.get("fresh", ""), "tab": meta.get("tab", ""), "body": body, **{k: meta[k] for k in LISTS}}
    return out


def lint(pages=None, now=None):
    """Every problem as a sentence, grouped: broken citations, broken links, modules with no page, stale data."""
    pages = pages if pages is not None else load()
    problems = []
    kinds = {k for k, _ in KINDS}
    for s, p in pages.items():
        if p["kind"] not in kinds:
            problems.append({"page": s, "kind": "tipo", "text": f"tipo «{p['kind']}» sconosciuto"})
        refs = p["code"] + p["docs"] + CITE.findall(p["body"])
        for ref in refs:
            path, sym = split_ref(ref)
            if path.startswith("data/"):
                if not (ROOT / path).exists():
                    problems.append({"page": s, "kind": "dati", "text": f"la cartella {path} non esiste"})
                continue
            if not (ROOT / path).exists():
                problems.append({"page": s, "kind": "citazione", "text": f"{path} non esiste"})
            elif sym and not find_line(path, sym):
                problems.append({"page": s, "kind": "citazione", "text": f"{sym} non è in {path}"})
        for d in p["data"]:
            if not (ROOT / d).exists():
                problems.append({"page": s, "kind": "dati", "text": f"la cartella {d} non esiste"})
        for t in p["feeds"] + [m[0] for m in LINK.findall(p["body"])]:
            if t not in pages:
                problems.append({"page": s, "kind": "link", "text": f"il link [[{t}]] non porta a nessuna pagina"})
    cited = {split_ref(r)[0] for p in pages.values() for r in p["code"] + CITE.findall(p["body"])}
    for f in sorted((ROOT / "bzd").glob("*.py")):
        rel = f"bzd/{f.name}"
        if f.name != "__init__.py" and rel not in cited:
            problems.append({"page": None, "kind": "copertura", "text": f"{rel} non è citato da nessuna pagina"})
    for s, p in pages.items():
        limit = STALE_HOURS.get(p["fresh"])
        if not limit:
            continue
        for d in p["data"]:
            age = folder_facts(d, now).get("age_h")
            if age is not None and age > limit:
                problems.append({"page": s, "kind": "fermo", "text": f"{d} non cambia da {age:.0f} ore (atteso entro {limit})"})
    return problems


def backlinks(pages):
    back = {s: set() for s in pages}
    for s, p in pages.items():
        for t in p["feeds"] + [m[0] for m in LINK.findall(p["body"])]:
            if t in back and t != s:
                back[t].add(s)
    return {s: sorted(v) for s, v in back.items()}


def ref_view(ref):
    path, sym = split_ref(ref)
    return {"ref": ref, "path": path, "sym": sym, "line": find_line(path, sym), "viewable": bool(SOURCE_OK.match(path))}


def pages(now=None):
    """Everything the Motore tab shows: pages with live facts, backlinks, the module graph and the lint."""
    ps = load()
    back = backlinks(ps)
    for s, p in ps.items():
        p["code_refs"] = [ref_view(r) for r in p["code"]]
        p["doc_refs"] = [ref_view(r) for r in p["docs"]]
        p["data_facts"] = [{"path": d, **folder_facts(d, now)} for d in p["data"]]
        p["backlinks"] = back[s]
        p["inline"] = {c: ref_view(c) for c in CITE.findall(p["body"]) if not c.startswith("data/")}
    read = lambda name: (WIKI / name).read_text() if (WIKI / name).exists() else ""
    intro = re.sub(r"^# .*\n", "", read("index.md")).strip()
    return {"kinds": KINDS, "pages": ps, "modules": module_graph(), "lint": lint(ps, now), "log": read("log.md"), "intro": intro}


def source(path):
    """A code or document file as text, for the citation viewer. None if it isn't one the app may show."""
    if not SOURCE_OK.match(path or "") or SECRET.search(path) or ".." in path:
        return None
    p = (ROOT / path).resolve()
    if not p.is_file() or ROOT not in p.parents or p.stat().st_size > 600_000:
        return None
    return {"path": path, "text": p.read_text(errors="replace")}


def data_view(path, now=None):
    """A data folder: its newest files. A data file: its size and its first lines. Never a secret, never outside data/."""
    if not re.match(r"^data(/[\w.@+-]+)*$", path or "") or SECRET.search(path) or ".." in path:
        return None
    p = (ROOT / path).resolve()
    if not p.exists() or not (p == ROOT / "data" or (ROOT / "data") in p.parents):
        return None
    if p.is_dir():
        items = []
        for f in p.iterdir():
            if SECRET.search(f.name):
                continue
            st = f.stat()
            items.append({"name": f.name, "dir": f.is_dir(), "bytes": st.st_size if f.is_file() else None, "mtime": st.st_mtime})
        items.sort(key=lambda x: -x["mtime"])
        return {"path": path, "dir": True, "facts": folder_facts(path, now), "total": len(items), "items": items[:40]}
    st = p.stat()
    head = []
    try:
        opener = gzip.open if p.suffix == ".gz" else open
        with opener(p, "rt", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= 25:
                    break
                head.append(line.rstrip("\n")[:400])
    except (OSError, EOFError):
        head = ["(non leggibile come testo)"]
    return {"path": path, "dir": False, "bytes": st.st_size, "mtime": st.st_mtime, "head": head}


def main(argv):
    cmd = argv[0] if argv else "lint"
    ps = load()
    if cmd == "pagine":
        for k, name in KINDS:
            print(name)
            for s, p in ps.items():
                if p["kind"] == k:
                    print(f"  {s:24} {p['title']}")
        return 0
    if cmd == "lint":
        probs = lint(ps)
        for p in probs:
            print(f"[{p['kind']}] {p['page'] or '-'}: {p['text']}")
        hard = [p for p in probs if p["kind"] in ("citazione", "link", "tipo", "dati", "copertura")]
        print(f"{len(ps)} pagine, {len(probs)} avvisi, {len(hard)} da correggere")
        return 1 if hard else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
