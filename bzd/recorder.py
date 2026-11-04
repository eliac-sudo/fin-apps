"""Archive raw responses with timestamps and hashes. Standard library only, so it moves to any machine.

    python -m bzd.recorder once [name-prefix]   run each job once and print results
    python -m bzd.recorder run                  run until stopped
    python -m bzd.recorder status               show job health; exits 1 if any job is late
"""
import fcntl, gzip, hashlib, json, os, re, shutil, signal, sys, threading, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import jobs as J

UA = "Mozilla/5.0 (compatible; bzd-research/0.1)"
MAX_BYTES = 64 * 1024 * 1024
FULL_PARSE_LIMIT = 5 * 1024 * 1024
BASE = Path(__file__).resolve().parent.parent


def load_env(path=None):
    p = Path(path or BASE / ".env")
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def expand(url):
    return re.sub(r"\{([A-Z_]+)\}", lambda m: os.environ[m.group(1)], url)


def redact(text, job):
    """Remove every secret a job uses from text bound for logs."""
    for k in job.needs:
        v = os.environ.get(k)
        if v:
            text = text.replace(v, "***")
    return text


def validate(kind, body):
    """Return an error, or None. A 200 can still be a block page or an API error."""
    head = body[:200].lstrip(b"\xef\xbb\xbf \r\n\t")
    if not body:
        return "empty body"
    if kind == "xml":
        return None if head[:1] == b"<" and not head[:15].lower().startswith((b"<!doctype html", b"<html")) else "not xml"
    if kind == "tg":
        return None if b"tgme_widget_message" in body else "no telegram messages"
    if kind == "csv":
        return "html, not csv" if head[:1] == b"<" else None
    if head[:1] not in (b"{", b"["):
        return "not json"
    if body.strip() in (b"{}", b"[]"):
        return "empty result"
    if len(body) > FULL_PARSE_LIMIT:
        return None if body.rstrip()[-1:] in (b"}", b"]") else "truncated json"
    try:
        d = json.loads(body)
    except ValueError:
        return "invalid json"
    if isinstance(d, dict):
        if str(d.get("code", "0")) != "0":
            return f"api code {d['code']}: {str(d.get('msg'))[:80]}"
        if d.get("retCode", 0) != 0:
            return f"api retCode {d['retCode']}: {str(d.get('retMsg'))[:80]}"
        if d.get("error"):
            return f"api error: {str(d['error'])[:80]}"
    return None


def fetch(job):
    data, headers = None, {"User-Agent": UA, "Accept": "*/*"}
    if job.body:
        data, headers["Content-Type"] = json.dumps(dict(job.body)).encode(), "application/json"
    req = urllib.request.Request(expand(job.url), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                return r.status, b"", "response too large", None
            return r.status, body, validate(job.kind, body), None
    except urllib.error.HTTPError as e:
        return e.code, b"", f"http {e.code}", e.headers.get("Retry-After")
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {e}", None


class Archive:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "manifest").mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.state_path = self.root / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def _save_state(self):
        tmp = self.state_path.with_name(f"state.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(self.state))
        tmp.replace(self.state_path)

    def record(self, job, now, status, body, error, ms):
        """Save the body if it changed and append one manifest line. Failures keep no body."""
        rec = {"ts": now.isoformat(timespec="seconds"), "job": job.name, "url": job.url, "status": status,
               "ok": error is None, "bytes": len(body), "ms": ms}
        if job.body:
            rec["request"] = dict(job.body)
        if error:
            rec["error"] = redact(error, job)[:300]
        with self.lock:
            st = self.state.setdefault(job.name, {})
            if error is None:
                sha = hashlib.sha256(body).hexdigest()
                rec["sha256"] = sha
                if st.get("sha256") == sha:
                    rec["unchanged"], rec["path"] = True, st["path"]
                else:
                    rel = Path("raw") / job.name / now.strftime("%Y-%m-%d") / (now.strftime("%H%M%SZ") + f".{job.kind}.gz")
                    dest = self.root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dest.with_suffix(".tmp")
                    with gzip.open(tmp, "wb", compresslevel=6) as f:
                        f.write(body)
                    tmp.replace(dest)
                    rec["path"], rec["stored"] = str(rel), dest.stat().st_size
                    st["path"], st["sha256"] = str(rel), sha
                st["last_ok"], st["fails"] = now.timestamp(), 0
            else:
                st["fails"] = st.get("fails", 0) + 1
            with open(self.root / "manifest" / f"{now:%Y-%m-%d}.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")
            self._save_state()
        return rec

    def prune(self, jobs, now):
        """Delete whole days older than each job's `keep`, except the day holding its latest response."""
        removed = 0
        for job in jobs:
            if not job.keep:
                continue
            cutoff = (now - timedelta(days=job.keep)).strftime("%Y-%m-%d")
            with self.lock:
                latest = Path(self.state.get(job.name, {}).get("path", "")).parent.name
            for d in (self.root / "raw" / job.name).glob("????-??-??"):
                if d.name < cutoff and d.name != latest:
                    shutil.rmtree(d)
                    removed += 1
        return removed


def retry_delay(job, fails, retry_after=None):
    delay = min(max(job.every, 60) * 2 ** (fails - 1), 3600)
    if retry_after and str(retry_after).isdigit():
        delay = max(delay, int(retry_after))
    return delay


def run_one(arc, job):
    t0, now = time.monotonic(), datetime.now(timezone.utc)
    status, body, error, retry_after = fetch(job)
    rec = arc.record(job, now, status, body, error, int((time.monotonic() - t0) * 1000))
    return rec, retry_after


def host_worker(arc, host, jobs, stop):
    gap = J.HOST_GAP.get(host, J.DEFAULT_GAP)
    due = {j.name: arc.state.get(j.name, {}).get("last_ok", 0) + j.every for j in jobs}
    while not stop.is_set():
        job = min(jobs, key=lambda j: due[j.name])
        wait = due[job.name] - time.time()
        if wait > 0:
            stop.wait(min(wait, 5))
            continue
        rec, retry_after = run_one(arc, job)
        due[job.name] = time.time() + (job.every if rec["ok"] else retry_delay(job, arc.state[job.name]["fails"], retry_after))
        stop.wait(gap)


def active_jobs():
    return [j for j in J.all_jobs() + J.candle_jobs() if all(os.environ.get(k) for k in j.needs)]


def by_host(jobs):
    d = defaultdict(list)
    for j in jobs:
        d[urlsplit(j.url).netloc].append(j)
    return d


def cmd_run(arc):
    lock = open(arc.root / "recorder.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("another recorder is already using this data directory")
    stop = threading.Event()
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: stop.set())
    jobs = active_jobs()
    threads = [threading.Thread(target=host_worker, args=(arc, h, js, stop), daemon=True) for h, js in by_host(jobs).items()]
    print(f"recording {len(jobs)} jobs on {len(threads)} hosts to {arc.root}", flush=True)
    for t in threads:
        t.start()
    while True:
        removed = arc.prune(jobs, datetime.now(timezone.utc))
        if removed:
            print(f"pruned {removed} old day folders", flush=True)
        if stop.wait(J.DAY):
            break
    for t in threads:
        t.join(timeout=100)


def cmd_once(arc, prefix=""):
    jobs = [j for j in active_jobs() if j.name.startswith(prefix)]
    results, mu = [], threading.Lock()

    def worker(host, js):
        for j in js:
            rec, _ = run_one(arc, j)
            with mu:
                results.append(rec)
            time.sleep(J.HOST_GAP.get(host, J.DEFAULT_GAP))

    ts = [threading.Thread(target=worker, args=x) for x in by_host(jobs).items()]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    results.sort(key=lambda r: r["job"])
    for r in results:
        print(f"{'ok  ' if r['ok'] else 'FAIL'} {r['job']:<38} {r['status']:>3} {r['bytes']:>10,} {r.get('error', '')}")
    bad = sum(not r["ok"] for r in results)
    print(f"\n{len(results) - bad}/{len(results)} ok, {sum(r['bytes'] for r in results) / 1e6:.1f} MB raw, {sum(r.get('stored', 0) for r in results) / 1e6:.1f} MB stored")
    return 1 if bad else 0


def cmd_status(arc, now=None):
    now = now or datetime.now(timezone.utc)
    cutoff, stats = now - timedelta(hours=24), defaultdict(lambda: {"ok": 0, "fail": 0, "err": ""})
    stored = 0
    for f in sorted((arc.root / "manifest").glob("*.jsonl"))[-2:]:
        for line in open(f):
            r = json.loads(line)
            if datetime.fromisoformat(r["ts"]) < cutoff:
                continue
            s = stats[r["job"]]
            s["ok" if r["ok"] else "fail"] += 1
            stored += r.get("stored", 0)
            if not r["ok"]:
                s["err"] = r.get("error", "")
    late, jobs = [], active_jobs()
    for j in jobs:
        last = arc.state.get(j.name, {}).get("last_ok")
        age = now.timestamp() - last if last else None
        if age is None or age > max(3 * j.every, j.every + 600):
            late.append((j.name, age, stats[j.name]["err"]))
    print(f"{len(jobs)} jobs, {len(jobs) - len(late)} on time, {len(late)} late; stored in last 24h: {stored / 1e6:.1f} MB")
    print(f"requests in last 24h: {sum(s['ok'] for s in stats.values())} ok, {sum(s['fail'] for s in stats.values())} failed")
    for name, age, err in late:
        print(f"LATE {name:<38} last ok: {'never' if age is None else f'{age / 3600:.1f}h ago'}  {err}")
    return 1 if late else 0


def main(argv):
    load_env()
    arc = Archive(os.environ.get("BZD_DATA", BASE / "data"))
    cmd = argv[0] if argv else ""
    if cmd == "run":
        return cmd_run(arc)
    if cmd == "once":
        return cmd_once(arc, argv[1] if len(argv) > 1 else "")
    if cmd == "status":
        return cmd_status(arc)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
