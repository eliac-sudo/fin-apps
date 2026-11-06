"""The read-only desktop app: python -m bzd.app, then open http://127.0.0.1:8787

It serves saved data on this machine only. It holds no trading keys, places no orders, and makes no paid calls.
A plan calculated here isn't logged, since trying numbers isn't a decision.
"""
import json, os, sys, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import labels as LB
from . import lookup as LK
from . import option_lab as L
from . import plan as P
from . import snapshot as S
from . import wiki as WK
from .recorder import load_env

PORT = 8787
CACHE_SECONDS = 120
LIVE_SECONDS = 300
PAGE = Path(__file__).with_name("app.html")
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONTS = {"Orbitron.ttf", "Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf", "ShareTechMono.ttf"}  # free fonts (OFL), served from here because the page only loads its own files
_cache, _lock, _live = {"at": 0, "data": None}, threading.Lock(), {}


def refresh():
    try:
        data = json.dumps(S.build()).encode()
        with _lock:
            _cache.update(data=data, at=time.time())
    except Exception as e:
        print(f"refresh failed: {type(e).__name__}", flush=True)
    finally:
        with _lock:
            _cache["busy"] = False


def snapshot():
    """Old data at once and new data in the background, so nobody waits for a rebuild. Only the very first reading blocks."""
    with _lock:
        have, stale = _cache["data"] is not None, time.time() - _cache["at"] > CACHE_SECONDS
        start = stale and not _cache.get("busy")
        if start:
            _cache["busy"] = True
    if start:
        if have:
            threading.Thread(target=refresh, daemon=True).start()
        else:
            refresh()
    for _ in range(600):
        with _lock:
            if _cache["data"] is not None:
                return _cache["data"]
        time.sleep(.5)
    raise TimeoutError("first reading is still running")


def option_market(key, fresh):
    """Fresh prices are fetched at most once per market every few minutes, however often the button is pressed."""
    if not fresh:
        return S.lab_market(key)
    with _lock:
        hit = _live.get(key)
    if hit and time.time() - hit[0] < LIVE_SECONDS:
        return hit[1]
    data = S.lab_market(key, fresh=True)
    with _lock:
        _live[key] = (time.time(), data)
    return data


def warm():
    """The first reading takes a while, so it happens before anyone waits for it."""
    try:
        snapshot()
        S.SM.word_days()  # the per-market sentiment view needs the word counts: about 8 seconds the first time
    except Exception as e:
        print(f"warm-up failed: {type(e).__name__}", flush=True)


def plan_reply(q):
    """The form's fields become the same words as /piano, so there's one set of rules."""
    words = [q.get("market", [""])[0], q.get("capital", [""])[0]]
    if q.get("risk", [""])[0]:
        words.append(q["risk"][0])
    for key in ("stop", "target", "leva", "entrata"):
        if q.get(key, [""])[0]:
            words += [key, q[key][0]]
    try:
        if not all(words[:2]):
            raise P.PlanError("Indica mercato e capitale.")
        return 200, {"plan": P.make_plan(words)[1]}
    except P.PlanError as e:
        return 400, {"error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, kind="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        try:
            if url.path == "/":
                self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif url.path.startswith("/fonts/") and url.path[7:] in FONTS:
                self.send(200, (FONT_DIR / url.path[7:]).read_bytes(), "font/ttf")
            elif url.path == "/api/snapshot":
                self.send(200, snapshot())
            elif url.path == "/api/price":
                m = q.get("market", [""])[0]
                self.send(*((200, json.dumps(S.clean(S.price_series(m))).encode()) if S.known_market(m) else (404, b'{"error":"mercato sconosciuto"}')))
            elif url.path == "/api/technical":
                m = q.get("market", [""])[0]
                if S.known_market(m):
                    self.send(200, json.dumps(S.clean(S.technical_market(m))).encode())
                elif m[:3] in ("hl:", "yf:") and LK.valid(m):
                    view = LK.technical(m)
                    self.send(*((200, json.dumps(S.clean(view)).encode()) if view else (404, b'{"error":"nessun dato"}')))
                else:
                    self.send(404, b'{"error":"mercato sconosciuto"}')
            elif url.path == "/api/lookup":
                self.send(200, json.dumps(LK.search(q.get("q", [""])[0][:60])).encode())
            elif url.path == "/api/sentiment":
                m = q.get("market", [""])[0]
                self.send(*((200, json.dumps(S.clean(S.sentiment_market(m))).encode()) if S.known_market(m) else (404, b'{"error":"mercato sconosciuto"}')))
            elif url.path == "/api/flows":
                m = q.get("market", [""])[0]
                self.send(*((200, json.dumps(S.clean(S.flows_market(m))).encode()) if S.known_market(m) else (404, b'{"error":"mercato sconosciuto"}')))
            elif url.path == "/api/options":
                key = q.get("market", [""])[0]
                if key not in L.BY_KEY:
                    self.send(404, b'{"error":"mercato sconosciuto"}')
                else:
                    self.send(200, json.dumps(S.clean(option_market(key, q.get("fresh", [""])[0] == "1"))).encode())
            elif url.path == "/api/labels":
                self.send(200, json.dumps(LB.next_text()).encode())
            elif url.path == "/api/wiki":
                self.send(200, json.dumps(WK.pages()).encode())
            elif url.path in ("/api/source", "/api/data"):
                view = (WK.source if url.path == "/api/source" else WK.data_view)(q.get("path", [""])[0][:300])
                self.send(*((200, json.dumps(view).encode()) if view else (404, b'{"error":"non disponibile"}')))
            elif url.path == "/api/plan":
                code, reply = plan_reply(q)
                self.send(code, json.dumps(S.clean(reply)).encode())
            else:
                self.send(404, b'{"error":"non trovato"}')
        except BrokenPipeError:
            pass
        except Exception as e:  # the type only: no paths or data in a reply
            self.send(500, json.dumps({"error": type(e).__name__}).encode())

    def do_POST(self):
        """The only write: your sentiment labels. The custom header can't be sent by another site's page, so only this app can label."""
        try:
            if urllib.parse.urlsplit(self.path).path != "/api/labels" or self.headers.get("X-BZD") != "1":
                self.send(403, b'{"error":"non permesso"}')
                return
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 4096)) or b"{}")
            LB.save_label(str(body.get("id", "")), str(body.get("label", "")))
            self.send(200, json.dumps(LB.next_text()).encode())
        except ValueError as e:
            self.send(400, json.dumps({"error": str(e)}).encode())
        except Exception as e:
            self.send(500, json.dumps({"error": type(e).__name__}).encode())

    def log_message(self, *_):
        pass


def main(argv):
    load_env()
    host = os.environ.get("BZD_APP_HOST", "127.0.0.1")
    print(f"BZD app on http://{host}:{PORT}", flush=True)
    threading.Thread(target=warm, daemon=True).start()
    ThreadingHTTPServer((host, PORT), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
