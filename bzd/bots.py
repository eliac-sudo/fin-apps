"""The BOTS tab: what the app shows about each bot and the few commands it may send. For now only the Deribit bot.

The app never holds the exchange keys and never places an order. It reads data/vol_bot/status.json, which the bot writes every
cycle, and writes data/vol_bot/control.json, which the bot reads every 10 seconds: pause, resume, emergency close, and a
smaller size per entry. The size can only go down, because a bigger one would change the rules of the test on future data.
"""
import fcntl, json
from datetime import datetime, timezone

from . import vol_bot as VB

STALE_MINUTES = 15
EVENTS = 30


def running(root=None):
    """True if a bot process holds the lock. Taking the lock ourselves means nobody had it; it's released at once."""
    p = VB.bot_dir(root) / "bot.lock"
    if not p.exists():
        return False
    with open(p, "a") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
        return False


def read_json(p):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def events(root=None, n=EVENTS):
    p = VB.bot_dir(root) / "journal.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out[::-1]


def view(root=None, now=None):
    now = now or datetime.now(timezone.utc)
    cfg = VB.load_config()
    st = read_json(VB.bot_dir(root) / "status.json")
    age = None
    if st and st.get("t"):
        age = (now - datetime.fromisoformat(st["t"])).total_seconds() / 60
    alive = running(root)
    ctrl = VB.read_control(root)
    state = ("spento" if not alive else "fermo" if st and st.get("halted") else "bloccato" if st and st.get("blocked")
             else "in pausa" if ctrl.get("paused") else "acceso")
    if alive and age is not None and age > STALE_MINUTES:
        state = "non risponde"
    pending_close = bool(ctrl.get("close_all")) and (not st or ctrl["close_all"] != (read_json(VB.bot_dir(root) / "state.json") or {}).get("close_done"))
    return {"bots": [{
        "id": "deribit", "name": "Strangle BTC coperto", "venue": "Deribit", "state": state, "running": alive, "age_min": age,
        "status": st, "control": ctrl, "pending_close": pending_close, "events": events(root),
        "rules": {"strategy": cfg["strategy"], "entry": cfg["entry"], "size": cfg["size"], "hedge": cfg["hedge"], "risk": cfg["risk"],
                  "readout": cfg["readout"], "frozen": cfg["frozen"], "safety": cfg["safety_not_in_backtest"]},
        "backtest": {"per_entry": 0.0081, "t": 1.9, "yearly": 0.073, "max_dd": -0.12, "doc": "docs/BOT_DERIBIT_STORICO.md"},
    }]}


def act(body, root=None):
    """One command from the app. Returns the new view, or raises ValueError with a sentence for the page."""
    if body.get("bot") != "deribit":
        raise ValueError("bot sconosciuto")
    a, now = body.get("action"), datetime.now(timezone.utc).isoformat(timespec="seconds")
    if a == "pausa":
        VB.update_control(root, paused=True)
    elif a == "riprendi":
        VB.update_control(root, paused=False, resume=now)
    elif a == "chiudi":
        if body.get("confirm") != "CHIUDI":
            raise ValueError("per chiudere tutto scrivi CHIUDI")
        VB.update_control(root, paused=True, close_all=now)
    elif a == "dimensione":
        top = VB.load_config()["size"]["notional_per_entry"]
        try:
            v = float(body.get("value"))
        except (TypeError, ValueError):
            raise ValueError("dimensione non valida") from None
        if not 0 <= v <= top:
            raise ValueError(f"la dimensione va da 0 a {top:.0%}: più alta cambierebbe la prova")
        VB.update_control(root, notional_per_entry=None if abs(v - top) < 1e-9 else round(v, 4))
    else:
        raise ValueError("comando sconosciuto")
    return view(root)
