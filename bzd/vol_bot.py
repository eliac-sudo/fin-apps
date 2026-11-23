"""Deribit bot that sells put spreads, one book per collateral: BTC in USDC, BTC in BTC, ETH in ETH (config/vol_bot_v1.json, docs/BOT_DERIBIT.md).

    python -m bzd.vol_bot run        loop forever
    python -m bzd.vol_bot once       one cycle, then stop
    python -m bzd.vol_bot stato      equity, open spreads, risk in use
    python -m bzd.vol_bot pausa      no new entries; exits and repairs keep running
    python -m bzd.vol_bot riprendi   entries again, also after the kill switch
    python -m bzd.vol_bot chiudi     close every spread now

It runs on the Deribit testnet unless DERIBIT_NETWORK=live and BZD_BOT_LIVE=ho-capito are both set by hand.
Risk is defined before any order: the wing is always bought before the put is sold, and closed after it, so the
account never holds a sold put without its wing. The worst case of all open spreads together is capped by the config.
With coin collateral (BTC options paid in BTC) the loss in coin grows as the price falls even past the wing, so those books
size the worst case at a stress price, half the wing's strike, not at the wing. Every cycle it checks the exchange's positions against its own book: a sold leg with no wing gets bought back at once,
any other difference stops new entries and sends a message.
"""
import fcntl, json, math, os, sys, time, urllib.error, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path

from .option_models import delta_gamma
from .recorder import BASE, UA, load_env

CONFIG = BASE / "config" / "vol_bot_v1.json"
URLS = {"test": "https://test.deribit.com/api/v2", "live": "https://www.deribit.com/api/v2"}
LIVE_SWITCH = "ho-capito"
EPS = 1e-9


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text())


def bot_dir(root=None):
    return Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "vol_bot"


def book_cfg(cfg, book):
    """The shared rules with one book's market and collateral on top."""
    return {**cfg, **book}


def enabled_books(cfg):
    books = [book_cfg(cfg, b) for b in cfg["books"] if b.get("enabled")]
    coll = [b["settlement"] for b in books]
    if len(set(coll)) < len(coll):
        raise SystemExit("Due libri accesi usano la stessa garanzia: i tetti di rischio si sommerebbero. Lasciane acceso uno per valuta.")
    return books


def is_coin(cfg):
    """Options paid and margined in the underlying itself (BTC-25DEC26-55000-P), not in USDC."""
    return cfg["settlement"] == cfg["underlying"]


def prefix(cfg):
    return f"{cfg['underlying']}-" if is_coin(cfg) else f"{cfg['underlying']}_{cfg['settlement']}-"


def network():
    """Testnet unless live is asked for twice: the network and the switch."""
    n = os.environ.get("DERIBIT_NETWORK", "test")
    if n not in URLS:
        raise SystemExit(f"DERIBIT_NETWORK deve essere test o live, non {n!r}")
    if n == "live" and os.environ.get("BZD_BOT_LIVE") != LIVE_SWITCH:
        raise SystemExit(f"Per il conto vero serve anche BZD_BOT_LIVE={LIVE_SWITCH} in .env")
    return n


# ---- the exchange

class DeribitError(RuntimeError):
    pass


class Client:
    """JSON-RPC over HTTPS POST, so the secret never sits in a URL or a log line."""

    def __init__(self, net, client_id, secret, timeout=20):
        self.base, self.id, self.secret, self.timeout = URLS[net], client_id, secret, timeout
        self.token, self.expires = None, 0

    def _post(self, method, params, auth=True):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        h = {"Content-Type": "application/json", "User-Agent": UA}
        if auth and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base, data=body, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                out = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                out = json.load(e)
            except ValueError:
                raise DeribitError(f"{method}: http {e.code}") from None
        except urllib.error.URLError as e:
            raise DeribitError(f"{method}: deribit non raggiungibile ({type(e.reason).__name__})") from None
        if "error" in out:
            err = out["error"]
            raise DeribitError(f"{method}: {err.get('message')} {err.get('data') or ''}".strip())
        return out["result"]

    def auth(self):
        r = self._post("public/auth", {"grant_type": "client_credentials", "client_id": self.id, "client_secret": self.secret}, auth=False)
        self.token, self.expires = r["access_token"], time.time() + r["expires_in"]

    def call(self, method, **params):
        for wait in (1, 3, 10, None):
            if method.startswith("private/") and time.time() > self.expires - 60:
                self.auth()
            try:
                return self._post(method, params)
            except DeribitError as e:
                if "too_many_requests" not in str(e) or wait is None:
                    raise
                time.sleep(wait)


def client_from_env():
    cid, sec = os.environ.get("DERIBIT_CLIENT_ID"), os.environ.get("DERIBIT_CLIENT_SECRET")
    if not (cid and sec):
        raise SystemExit("Aggiungi DERIBIT_CLIENT_ID e DERIBIT_CLIENT_SECRET a .env (chiave del testnet: lettura e trading, niente prelievi)")
    return Client(network(), cid, sec)


# ---- pure rules: what to trade, how much, when to leave

def parse_name(name):
    """BTC_USDC-25DEC26-55000-P -> (expiry date, strike, is_put). Strikes like 7d5 mean 7.5."""
    _, exp, k, kind = name.split("-")
    return datetime.strptime(exp, "%d%b%y").date(), float(k.replace("d", ".")), kind == "P"


def tick_for(inst, price):
    t = inst["tick_size"]
    for s in sorted(inst.get("tick_size_steps") or [], key=lambda s: s["above_price"]):
        if price > s["above_price"]:
            t = s["tick_size"]
    return t


def limit_price(side, bid, ask, step, steps, inst):
    """Start at the mid and walk to the far side of the quote, on the instrument's tick, never past bid or ask."""
    mid = (bid + ask) / 2
    px = mid + (ask - mid) * step / steps if side == "buy" else mid - (mid - bid) * step / steps
    t = tick_for(inst, px)
    px = math.ceil(px / t - EPS) * t if side == "buy" else math.floor(px / t + EPS) * t
    return round(min(max(px, bid), ask), 8)


def choose_expiry(instruments, now, cfg):
    """The expiry closest to the target days inside the allowed range, as an expiration timestamp in ms."""
    lo, hi = cfg["entry"]["days_range"]
    best = None
    for ts in {i["expiration_timestamp"] for i in instruments}:
        d = (ts / 1000 - now.timestamp()) / 86400
        if lo <= d <= hi and (best is None or abs(d - cfg["entry"]["target_days"]) < abs(best[1] - cfg["entry"]["target_days"])):
            best = (ts, d)
    return best[0] if best else None


def chain_quotes(book, exp_ms, now):
    """Book summary rows of one expiry -> puts with bid, ask and a Black-76 delta from the mark vol: one request for the whole chain."""
    years = (exp_ms / 1000 - now.timestamp()) / (365 * 86400)
    out = []
    for b in book:
        _, k, is_put = parse_name(b["instrument_name"])
        f, iv = b.get("underlying_price"), b.get("mark_iv")
        if not (is_put and f and iv and 0.5 * f <= k < f and years > 0):
            continue
        out.append({"name": b["instrument_name"], "strike": k, "bid": b.get("bid_price") or 0, "ask": b.get("ask_price") or 0,
                    "delta": float(delta_gamma(f, k, years, iv / 100, False)[0]), "under": f})
    return out


def quote_ok(q, max_spread):
    bid, ask = q.get("bid") or 0, q.get("ask") or 0
    return bid > 0 and ask >= bid and (ask - bid) / ((ask + bid) / 2) <= max_spread


def choose_legs(puts, cfg):
    """puts: [{name, strike, bid, ask, delta}] of one expiry. The sold put nearest short_delta, the wing nearest long_delta
    below it. None if a quote is too wide or the credit too thin for the width."""
    e = cfg["entry"]
    ok = [p for p in puts if p.get("delta") is not None and quote_ok(p, e["max_spread_frac"])]
    if not ok:
        return None
    short = min(ok, key=lambda p: abs(abs(p["delta"]) - e["short_delta"]))
    wings = [p for p in ok if p["strike"] < short["strike"]]
    if not wings:
        return None
    wing = min(wings, key=lambda p: abs(abs(p["delta"]) - e["long_delta"]))
    width = short["strike"] - wing["strike"]
    credit = short["bid"] - wing["ask"]  # what it gets if both fill at the far side, in the price's currency
    credit_usd = credit * (short.get("under") or 0) if is_coin(cfg) else credit
    if credit <= 0 or credit_usd / width < e["min_credit_frac_of_width"]:
        return None
    return {"short": short, "long": wing, "width": width, "credit": credit}


def unit_loss(width, long_strike, credit, cfg):
    """Worst case per contract, in the collateral's currency. In USDC: width less credit. In coin the put spread pays
    width / price in coin, which keeps growing as the price falls, so it is measured at the stress price."""
    if is_coin(cfg):
        return width / (long_strike * cfg["risk"]["coin_stress"]) - credit
    return width - credit


def size(equity, open_risk, per_unit, lot, cfg):
    """Contracts, in steps of the exchange's lot, so this spread loses at most max_loss_per_trade of equity and all of them together max_loss_open."""
    r = cfg["risk"]
    budget = min(equity * r["max_loss_per_trade"], equity * r["max_loss_open"] - open_risk)
    if per_unit <= 0 or budget <= 0:
        return 0.0
    n = math.floor(budget / per_unit / lot + EPS)
    return round(n * lot, 8) if n >= 1 else 0.0


def max_loss(pos):
    """Worst case of the part still open (see unit_loss)."""
    per = pos.get("unit_loss", pos["width"] - pos["credit"])
    return max(per, 0) * pos["short_amount"]


def exit_reason(pos, short_ask, long_bid, now, cfg):
    x = cfg["exit"]
    days_left = (datetime.fromisoformat(pos["expiry"]).replace(tzinfo=timezone.utc) - now).total_seconds() / 86400 + 1/3  # expiry is 08:00 UTC
    if days_left <= x["close_days_left"]:
        return "scadenza vicina"
    if short_ask and long_bid is not None and short_ask - long_bid <= pos["credit"] * (1 - x["take_profit_frac"]):
        return "profitto preso"
    return None


def uncovered(positions):
    """Exchange positions -> {instrument: amount sold with no wing}. A put is covered by a bought put of the same expiry and a
    lower strike; the bot never sells calls, so a sold call is uncovered in full."""
    by_exp = {}
    for p in positions:
        if abs(p["size"]) < EPS:
            continue
        exp, k, is_put = parse_name(p["instrument_name"])
        by_exp.setdefault(exp, []).append((k, is_put, p["size"], p["instrument_name"]))
    out = {}
    for legs in by_exp.values():
        pool = 0.0
        for k, is_put, s, name in sorted(legs, key=lambda x: (x[0], x[2] > 0)):  # at equal strike a long does not cover
            if not is_put:
                if s < 0:
                    out[name] = -s
                continue
            if s > 0:
                pool += s
            else:
                use = min(pool, -s)
                pool -= use
                if -s - use > EPS:
                    out[name] = round(-s - use, 8)
    return out


def expected_sizes(book):
    want = {}
    for pos in book:
        want[pos["short"]] = want.get(pos["short"], 0) - pos["short_amount"]
        want[pos["long"]] = want.get(pos["long"], 0) + pos["long_amount"]
    return {k: round(v, 8) for k, v in want.items() if abs(v) > EPS}


def differences(book, positions):
    have = {p["instrument_name"]: round(p["size"], 8) for p in positions if abs(p["size"]) > EPS}
    want = expected_sizes(book)
    return {k: (want.get(k, 0), have.get(k, 0)) for k in set(want) | set(have) if abs(want.get(k, 0) - have.get(k, 0)) > EPS}


# ---- state

def new_state():
    return {"book": [], "closed": [], "peak": None, "last_entry": None, "paused": False, "halted": None, "blocked": None, "sent": {}}


def load_state(root=None, book="btc_usdc"):
    p = bot_dir(root) / book / "state.json"
    return {**new_state(), **json.loads(p.read_text())} if p.exists() else new_state()


def save_state(st, root=None, book="btc_usdc"):
    d = bot_dir(root) / book
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.json.tmp"
    tmp.write_text(json.dumps(st, indent=1, default=str))
    tmp.replace(d / "state.json")


def journal(event, root=None, book="btc_usdc", **kw):
    d = bot_dir(root) / book
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "journal.jsonl", "a") as f:
        f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **kw}, default=str) + "\n")


def read_control(root=None):
    p = bot_dir(root) / "control.json"
    return json.loads(p.read_text()) if p.exists() else {}


def write_control(ctrl, root=None):
    """pausa and riprendi go through their own file, so the CLI never writes over the running bot's book."""
    d = bot_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "control.json.tmp").write_text(json.dumps(ctrl))
    (d / "control.json.tmp").replace(d / "control.json")


# ---- the bot

class Bot:
    def __init__(self, client, cfg=None, root=None, notify=None, sleep=time.sleep, now=lambda: datetime.now(timezone.utc), log=print):
        self.c, self.root = client, root
        self.cfg = cfg or enabled_books(load_config())[0]
        self.book, self.cur = self.cfg["name"], self.cfg["settlement"]
        self.notify_fn, self.sleep, self.now, self.log = notify, sleep, now, log
        self.st = load_state(root, self.book)
        self.net = "test" if client.base == URLS["test"] else "live"
        self._inst = {}

    def save(self):
        save_state(self.st, self.root, self.book)

    def money(self, x):
        return f"{x:.5f} {self.cur}" if is_coin(self.cfg) else f"{x:.2f} {self.cur}"

    def say(self, text, key=None, every_s=3600):
        """Message on Telegram; a repeated problem goes out at most once an hour."""
        self.log(text)
        if key:
            last = self.st["sent"].get(key, 0)
            if time.time() - last < every_s:
                return
            self.st["sent"][key] = time.time()
        if self.notify_fn:
            try:
                self.notify_fn(f"🤖 Bot Deribit {self.book} ({'TESTNET' if self.net == 'test' else 'CONTO VERO'})\n{text}")
            except Exception as e:  # noqa: BLE001 - a lost message must not stop the bot
                self.log(f"telegram: {e}")

    # -- exchange reads

    def instruments(self):
        r = self.c.call("public/get_instruments", currency=self.cfg["settlement"], kind="option", expired=False)
        self._inst = {i["instrument_name"]: i for i in r}
        return [i for i in r if i["instrument_name"].startswith(prefix(self.cfg))]

    def inst(self, name):
        if name not in self._inst:
            self._inst[name] = self.c.call("public/get_instrument", instrument_name=name)
        return self._inst[name]

    def ticker(self, name):
        t = self.c.call("public/ticker", instrument_name=name)
        return {"bid": t.get("best_bid_price") or 0, "ask": t.get("best_ask_price") or 0, "delta": (t.get("greeks") or {}).get("delta"),
                "mark": t.get("mark_price"), "under": t.get("underlying_price")}

    def equity(self):
        return float(self.c.call("private/get_account_summary", currency=self.cfg["settlement"])["equity"])

    def positions(self):
        r = self.c.call("private/get_positions", currency=self.cfg["settlement"], kind="option")
        return [p for p in r if p["instrument_name"].startswith(prefix(self.cfg))]

    # -- orders

    def execute(self, side, name, amount, reduce_only=False, label=None):
        """A limit order that starts at the mid and moves to the far side in steps. Returns (filled, average price)."""
        inst = self.inst(name)
        amount = round(math.floor(amount / inst["min_trade_amount"] + EPS) * inst["min_trade_amount"], 8)
        if amount < inst["min_trade_amount"] - EPS:
            return 0.0, None
        o = self.cfg["orders"]
        q = self.ticker(name)
        if not (q["bid"] > 0 and q["ask"] >= q["bid"]):
            if side == "buy" and q["ask"] > 0:
                q["bid"] = q["ask"]  # no bid: a buy can still pay the ask
            else:
                self.log(f"{name}: nessun prezzo per {side}")
                return 0.0, None
        order = None
        for step in range(o["steps"] + 1):
            px = limit_price(side, q["bid"], q["ask"], step, o["steps"], inst)
            if order is None:
                order = self.c.call(f"private/{side}", instrument_name=name, amount=amount, type="limit", price=px,
                                    label=label or "bzd", reduce_only=reduce_only, time_in_force="good_til_cancelled")["order"]
            else:
                order = self.c.call("private/edit", order_id=order["order_id"], amount=amount, price=px)["order"]
            if order["order_state"] == "filled":
                break
            self.sleep(o["wait_s"])
            order = self.c.call("private/get_order_state", order_id=order["order_id"])
            if order["order_state"] in ("filled", "cancelled", "rejected"):
                break
        if order["order_state"] == "open":
            try:
                order = self.c.call("private/cancel", order_id=order["order_id"])
            except DeribitError:
                order = self.c.call("private/get_order_state", order_id=order["order_id"])
        filled = float(order.get("filled_amount") or 0)
        journal("ordine", self.root, self.book, side=side, name=name, amount=amount, filled=filled, price=order.get("average_price"), state=order["order_state"])
        return filled, (float(order["average_price"]) if filled > 0 else None)

    # -- the cycle

    def check(self, positions):
        """Buy back any sold put with no wing, then compare the book with the exchange."""
        naked = uncovered(positions)
        for name, amt in naked.items():
            self.say(f"⚠️ {name}: {amt} vendute senza ala. Le ricompro subito.", key=f"naked:{name}")
            got, px = self.execute("buy", name, amt, reduce_only=True, label="bzd-ripara")
            for pos in self.st["book"]:
                if pos["short"] == name and got > 0:
                    take = min(got, pos["short_amount"])
                    pos["short_amount"], got = round(pos["short_amount"] - take, 8), got - take
                    pos["paid_back"] = pos.get("paid_back", 0) + take * px
            self.save()
        if naked:
            positions = self.positions()
        self.settle_expired(positions)
        diff = differences(self.st["book"], positions)
        if diff:
            text = ", ".join(f"{k}: atteso {w}, sul conto {h}" for k, (w, h) in sorted(diff.items()))
            if self.st["blocked"] != text:
                self.say(f"⚠️ Il conto non torna con il registro: {text}. Niente entrate nuove finché non si sistema.", key="diff")
            self.st["blocked"] = text
        else:
            self.st["blocked"] = None
        return positions

    def settle_expired(self, positions):
        """Spreads past expiry that the exchange no longer shows were settled by Deribit."""
        have = {p["instrument_name"] for p in positions if abs(p["size"]) > EPS}
        today = self.now().date()
        for pos in list(self.st["book"]):
            if datetime.fromisoformat(pos["expiry"]).date() <= today and pos["short"] not in have and pos["long"] not in have:
                self.close_record(pos, "scaduta", None)

    def close_record(self, pos, reason, pnl):
        self.st["book"].remove(pos)
        self.st["closed"].append({**pos, "closed": self.now().isoformat(timespec="seconds"), "reason": reason, "pnl": pnl})
        journal("chiusa", self.root, self.book, id=pos["id"], reason=reason, pnl=pnl)
        self.say(f"Chiuso {pos['short']} / {pos['long']} ({reason})" + (f": {'+' if pnl >= 0 else ''}{self.money(pnl)}" if pnl is not None else ""))
        self.save()

    def close(self, pos, reason):
        """Buy back the sold put first, then sell the wing: never a sold put without its wing, even halfway."""
        if pos["short_amount"] > EPS:
            got, px = self.execute("buy", pos["short"], pos["short_amount"], reduce_only=True, label=f"bzd-{pos['id']}")
            if got > 0:
                pos["short_amount"] = round(pos["short_amount"] - got, 8)
                pos["paid_back"] = pos.get("paid_back", 0) + got * px
                self.save()
        return self.trim(pos, reason)

    def trim(self, pos, reason):
        """Sell the wing beyond what the sold put needs. When nothing is left, the spread is closed."""
        extra = pos["long_amount"] - pos["short_amount"]
        if extra > EPS:
            got, px = self.execute("sell", pos["long"], extra, reduce_only=True, label=f"bzd-{pos['id']}")
            if got > 0:
                pos["long_amount"] = round(pos["long_amount"] - got, 8)
                pos["wing_back"] = pos.get("wing_back", 0) + got * px
                self.save()
        if pos["short_amount"] < EPS and pos["long_amount"] < EPS:
            pnl = pos["cash_in"] - pos.get("paid_back", 0) + pos.get("wing_back", 0)
            self.close_record(pos, reason, round(pnl, 8))
            return True
        return False

    def exits(self):
        for pos in list(self.st["book"]):
            if pos["short_amount"] < EPS:  # only a leftover wing: sell it
                self.close(pos, pos.get("closing") or "ala rimasta")
                continue
            s, l = self.ticker(pos["short"]), self.ticker(pos["long"])
            reason = pos.get("closing") or exit_reason(pos, s["ask"], l["bid"], self.now(), self.cfg)
            if reason:
                pos["closing"] = reason
                self.close(pos, reason)

    def open_risk(self):
        return sum(max_loss(p) for p in self.st["book"])

    def entry(self, equity):
        e, now = self.cfg["entry"], self.now()
        if self.st["paused"] or self.st["halted"] or self.st["blocked"]:
            return None
        last = self.st["last_entry"]
        if last and (now - datetime.fromisoformat(last)).total_seconds() < e["every_days"] * 86400:
            return None
        insts = self.instruments()
        exp = choose_expiry(insts, now, self.cfg)
        if not exp:
            return self.skip("nessuna scadenza tra %d e %d giorni" % tuple(e["days_range"]))
        names = {i["instrument_name"] for i in insts if i["expiration_timestamp"] == exp and i["option_type"] == "put"}
        book = [b for b in self.c.call("public/get_book_summary_by_currency", currency=self.cfg["settlement"], kind="option") if b["instrument_name"] in names]
        legs = choose_legs(chain_quotes(book, exp, now), self.cfg)
        if not legs:
            return self.skip("prezzi troppo larghi o premio troppo basso")
        per = unit_loss(legs["width"], legs["long"]["strike"], legs["credit"], self.cfg)
        amount = size(equity, self.open_risk(), per, self.inst(legs["short"]["name"])["min_trade_amount"], self.cfg)
        if amount <= 0:
            return self.skip("rischio già al tetto")
        pid = uuid.uuid4().hex[:8]
        self.st["last_entry"] = now.isoformat(timespec="seconds")  # one attempt per period, filled or not
        self.save()
        got_l, px_l = self.execute("buy", legs["long"]["name"], amount, label=f"bzd-{pid}")
        if got_l <= 0:
            return self.skip("l'ala non si è comprata")
        pos = {"id": pid, "opened": now.isoformat(timespec="seconds"), "expiry": parse_name(legs["short"]["name"])[0].isoformat(),
               "short": legs["short"]["name"], "long": legs["long"]["name"], "width": legs["width"],
               "short_amount": 0.0, "long_amount": got_l, "cash_in": -got_l * px_l, "credit": 0.0}
        self.st["book"].append(pos)
        self.save()  # the wing is on the book before the put is sold, so a crash leaves only a bought put
        got_s, px_s = self.execute("sell", legs["short"]["name"], got_l, label=f"bzd-{pid}")
        if got_s > 0:
            pos["short_amount"] = got_s
            pos["cash_in"] += got_s * px_s
            pos["credit"] = round(px_s - px_l, 8)
            pos["unit_loss"] = unit_loss(pos["width"], legs["long"]["strike"], pos["credit"], self.cfg)
        self.save()
        if got_s < got_l - EPS:
            self.trim(pos, "entrata a metà")
        if got_s > 0:
            worst = "perdita massima" if not is_coin(self.cfg) else f"perdita con {self.cfg['underlying']} a {legs['long']['strike'] * self.cfg['risk']['coin_stress']:.0f}"
            self.say(f"Aperto put spread {legs['short']['name']} / {legs['long']['strike']:.0f}, {got_s} {self.cfg['underlying']}, premio {self.money(pos['credit'] * got_s)}, "
                     f"{worst} {self.money(max_loss(pos))} ({max_loss(pos) / equity:.1%} del conto). Rischio aperto totale {self.open_risk() / equity:.1%}.")
        return pos

    def skip(self, why):
        self.log(f"entrata saltata: {why}")
        journal("saltata", self.root, self.book, why=why)
        return None

    def kill_switch(self, equity):
        self.st["peak"] = max(self.st["peak"] or equity, equity)
        dd = 1 - equity / self.st["peak"]
        if dd >= self.cfg["risk"]["kill_drawdown"] and not self.st["halted"]:
            self.st["halted"] = f"{self.now().isoformat(timespec='seconds')}: drawdown {dd:.1%}"
            self.say(f"🛑 Drawdown {dd:.1%} dal massimo: niente entrate nuove. Le aperte restano protette dall'ala. "
                     f"Per ripartire: python -m bzd.vol_bot riprendi")

    def apply_control(self):
        ctrl = read_control(self.root)  # shared by every book
        self.st["paused"] = bool(ctrl.get("paused"))
        if ctrl.get("resume") and ctrl["resume"] != self.st.get("resumed"):
            self.st["halted"], self.st["resumed"] = None, ctrl["resume"]
            self.st["peak"] = None  # the drawdown counts again from here

    def cycle(self):
        self.apply_control()
        equity = self.equity()
        self.kill_switch(equity)
        self.check(self.positions())
        self.exits()
        self.check(self.positions())
        self.entry(self.equity())
        self.save()

    def close_all(self):
        for pos in list(self.st["book"]):
            pos["closing"] = "a mano"
            self.close(pos, "a mano")
        self.save()

    def status(self):
        eq = self.equity() or EPS
        lines = [f"[{self.book}] Rete: {self.net}. Conto: {self.money(eq)}, massimo {self.money(self.st['peak'] or eq)}."]
        for k in ("paused", "halted", "blocked"):
            if self.st[k]:
                lines.append({"paused": "In pausa.", "halted": f"Fermo: {self.st['halted']}.", "blocked": f"Bloccato: {self.st['blocked']}."}[k])
        for p in self.st["book"]:
            lines.append(f"  {p['short']} / {p['long']}: {p['short_amount']} vendute, premio {self.money(p['credit'] * p['short_amount'])}, perdita massima {self.money(max_loss(p))}")
        lines.append(f"Rischio aperto {self.money(self.open_risk())} ({self.open_risk() / eq:.1%} del conto, tetto {self.cfg['risk']['max_loss_open']:.0%}).")
        done = [c for c in self.st["closed"] if c["pnl"] is not None]
        if done:
            lines.append(f"Chiusi: {len(self.st['closed'])}, somma {self.money(sum(c['pnl'] for c in done))}.")
        return "\n".join(lines)


def telegram_notify():
    if os.environ.get("BZD_BOT_TELEGRAM") != "on":
        return None
    from .alerts import send_text, telegram_ready
    return send_text if telegram_ready() else None


def lock(root=None):
    d = bot_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    f = open(d / "bot.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("Il bot sta già girando") from None
    return f


def main(argv):
    load_env()
    cmd = argv[1] if len(argv) > 1 else "stato"
    if cmd in ("pausa", "riprendi"):
        write_control({"paused": True} if cmd == "pausa" else {"paused": False, "resume": datetime.now(timezone.utc).isoformat()})
        print("In pausa: niente entrate nuove." if cmd == "pausa" else "Ripreso.")
        return
    cfg, client, notify = load_config(), client_from_env(), telegram_notify()
    bots = [Bot(client, b, notify=notify) for b in enabled_books(cfg)]
    if cmd == "stato":
        print("\n\n".join(b.status() for b in bots))
    elif cmd == "chiudi":
        _l = lock()
        for b in bots:
            b.close_all()
        print("\n\n".join(b.status() for b in bots))
    elif cmd in ("once", "run"):
        _l = lock()
        bots[0].say(f"Acceso sul {'testnet' if bots[0].net == 'test' else 'CONTO VERO'}: {', '.join(b.book for b in bots)}.")
        while True:
            for bot in bots:  # one book failing does not stop the others
                try:
                    bot.cycle()
                except DeribitError as e:
                    bot.say(f"Errore da Deribit: {e}", key=f"err:{str(e)[:60]}")
                except Exception as e:  # noqa: BLE001 - keep running, but say so
                    bot.say(f"Errore: {type(e).__name__}: {e}", key=f"err:{type(e).__name__}")
            if cmd == "once":
                break
            time.sleep(cfg["loop_seconds"])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
