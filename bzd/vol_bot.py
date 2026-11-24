"""Deribit bot: sells the 25-delta BTC strangle in USDC as a maker and hedges its delta on the perpetual (config/vol_bot_v2.json,
docs/BOT_DERIBIT.md). It is DH2m of docs/BOT_DERIBIT_STORICO.md, the only variant of fifteen that held on real Deribit marks.

    python -m bzd.vol_bot run        loop forever
    python -m bzd.vol_bot once       one cycle, then stop
    python -m bzd.vol_bot stato      equity, open strangles, delta, margin
    python -m bzd.vol_bot pausa      no new entries; hedging and safety keep running
    python -m bzd.vol_bot riprendi   entries again, also after the kill switch
    python -m bzd.vol_bot chiudi     buy back every option and flatten the hedge now

Testnet unless DERIBIT_NETWORK=live and BZD_BOT_LIVE=ho-capito are both set by hand.

Every Monday 10-16 UTC it offers the put and the call nearest 25 delta, 21-45 days out, at the mid of the order book with
post-only orders, re-pricing as the book moves; what isn't filled by 16:00 is cancelled. The strangle is held to expiry.
The delta of every open option is hedged on the perpetual once a day at 08:00 UTC and right after a fill, as in the backtest.
Safety beyond the backtest: an emergency hedge when the net delta drifts past a threshold, no entries with margin above 50%
of equity, everything closed above 80% so the exchange never liquidates, and no entries after a 15% drawdown.
A strangle has no wing: these rules are what stands between the account and the tail.
"""
import fcntl, json, math, os, sys, time, urllib.error, urllib.request, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .option_models import delta_gamma
from .recorder import BASE, UA, load_env

CONFIG = BASE / "config" / "vol_bot_v2.json"
URLS = {"test": "https://test.deribit.com/api/v2", "live": "https://www.deribit.com/api/v2"}
LIVE_SWITCH = "ho-capito"
EPS = 1e-9


def load_config(path=CONFIG):
    return json.loads(Path(path).read_text())


def bot_dir(root=None):
    return Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "vol_bot"


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


# ---- pure rules

def parse_name(name):
    """BTC_USDC-25DEC26-55000-P -> (expiry date, strike, is_put). Strikes like 7d5 mean 7.5."""
    _, exp, k, kind = name.split("-")
    return datetime.strptime(exp, "%d%b%y").date(), float(k.replace("d", ".")), kind == "P"


def expiry_time(name):
    return datetime.combine(parse_name(name)[0], datetime.min.time(), timezone.utc) + timedelta(hours=8)


def tick_for(inst, price):
    t = inst["tick_size"]
    for s in sorted(inst.get("tick_size_steps") or [], key=lambda s: s["above_price"]):
        if price > s["above_price"]:
            t = s["tick_size"]
    return t


def maker_price(bid, ask, inst):
    """A sell at the mid of the book, on the tick, never at or below the bid (post-only would refuse it)."""
    mid = (bid + ask) / 2
    t = tick_for(inst, mid)
    px = math.ceil(mid / t - EPS) * t
    if px <= bid + EPS:
        px = bid + t
    return round(px, 8)


def choose_expiry(instruments, now, cfg):
    lo, hi = cfg["entry"]["days_range"]
    best = None
    for ts in {i["expiration_timestamp"] for i in instruments}:
        d = (ts / 1000 - now.timestamp()) / 86400
        if lo <= d <= hi and (best is None or abs(d - cfg["entry"]["target_days"]) < abs(best[1] - cfg["entry"]["target_days"])):
            best = (ts, d)
    return best[0] if best else None


def choose_strangle(book, exp_ms, now, cfg):
    """Book summary rows of one expiry -> the put and the call nearest the target delta, out of the money, by Black-76 at the
    mark vol (as in the backtest). None if nothing sits near enough."""
    e = cfg["entry"]
    years = (exp_ms / 1000 - now.timestamp()) / (365 * 86400)
    best = {}
    for b in book:
        _, k, is_put = parse_name(b["instrument_name"])
        f, iv = b.get("underlying_price"), b.get("mark_iv")
        if not (f and iv and years > 0) or (is_put and k >= f) or (not is_put and k <= f):
            continue
        d = abs(float(delta_gamma(f, k, years, iv / 100, not is_put)[0]))
        side = "put" if is_put else "call"
        if abs(d - e["delta"]) <= e["max_delta_gap"] and (side not in best or abs(d - e["delta"]) < best[side][1]):
            best[side] = (b["instrument_name"], abs(d - e["delta"]), f)
    if "put" not in best or "call" not in best:
        return None
    return {"put": best["put"][0], "call": best["call"][0], "under": best["put"][2]}


def entry_amount(equity, under, open_amount, cfg, lot):
    """BTC of strangle so this entry carries notional_per_entry of equity and all open ones at most max_notional."""
    s = cfg["size"]
    btc = min(equity * s["notional_per_entry"] / under, equity * s["max_notional"] / under - open_amount)
    n = math.floor(btc / lot + EPS)
    return round(n * lot, 8) if n >= 1 else 0.0


def hedge_trade(option_delta, perp_size, min_trade):
    """Perpetual to buy (+) or sell (-) so the account is delta-flat. Zero if the gap is smaller than the minimum trade."""
    want = -option_delta
    diff = round(want - perp_size, 4)
    return diff if abs(diff) >= min_trade else 0.0


def hedge_sane(trade, option_btc, perp_size):
    """No hedge may move more than 1.5 times the BTC of options open (plus what flattens the current hedge): a bigger number
    means a reading went wrong, and the bot stops instead of trading it."""
    return abs(trade) <= 1.5 * option_btc + abs(perp_size) + 0.01


def week_key(now):
    y, w, _ = now.isocalendar()
    return f"{y}-W{w:02d}"


def in_entry_window(now, cfg):
    e = cfg["entry"]
    lo, hi = e["window_utc_hours"]
    return now.weekday() == e["weekday"] and lo <= now.hour < hi


def hedge_due(now, last_day, cfg):
    return now.hour >= cfg["hedge"]["hour_utc"] and last_day != now.date().isoformat()


# ---- state

def new_state():
    return {"book": [], "closed": [], "working": None, "peak": None, "last_week": None, "last_hedge_day": None,
            "paused": False, "halted": None, "blocked": None, "resumed": None, "sent": {}}


def load_state(root=None):
    p = bot_dir(root) / "state.json"
    return {**new_state(), **json.loads(p.read_text())} if p.exists() else new_state()


def save_state(st, root=None):
    d = bot_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json.tmp").write_text(json.dumps(st, indent=1, default=str))
    (d / "state.json.tmp").replace(d / "state.json")


def journal(event, root=None, **kw):
    d = bot_dir(root)
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
    def __init__(self, client, cfg=None, root=None, notify=None, now=lambda: datetime.now(timezone.utc), log=print):
        self.c, self.cfg, self.root = client, cfg or load_config(), root
        self.notify_fn, self.now, self.log = notify, now, log
        self.st = load_state(root)
        self.net = "test" if client.base == URLS["test"] else "live"
        self._inst = {}

    def save(self):
        save_state(self.st, self.root)

    def say(self, text, key=None, every_s=3600):
        """Message on Telegram; a repeated problem goes out at most once an hour."""
        self.log(text)
        if key:
            if time.time() - self.st["sent"].get(key, 0) < every_s:
                return
            self.st["sent"][key] = time.time()
        if self.notify_fn:
            try:
                self.notify_fn(f"🤖 Bot Deribit ({'TESTNET' if self.net == 'test' else 'CONTO VERO'})\n{text}")
            except Exception as e:  # noqa: BLE001 - a lost message must not stop the bot
                self.log(f"telegram: {e}")

    # -- exchange reads

    def inst(self, name):
        if name not in self._inst:
            self._inst[name] = self.c.call("public/get_instrument", instrument_name=name)
        return self._inst[name]

    def quote(self, name):
        """Bid and ask from the order book itself: on the testnet the ticker lagged the book."""
        ob = self.c.call("public/get_order_book", instrument_name=name, depth=1)
        return {"bid": ob.get("best_bid_price") or 0, "ask": ob.get("best_ask_price") or 0, "under": ob.get("underlying_price")}

    def account(self):
        a = self.c.call("private/get_account_summary", currency=self.cfg["settlement"])
        return float(a["equity"]), float(a.get("maintenance_margin") or 0)

    def positions(self):
        """(options of this underlying, perpetual size) as the exchange sees them."""
        opts = [p for p in self.c.call("private/get_positions", currency=self.cfg["settlement"], kind="option")
                if p["instrument_name"].startswith(f"{self.cfg['underlying']}_{self.cfg['settlement']}-") and abs(p["size"]) > EPS]
        perp = [p for p in self.c.call("private/get_positions", currency=self.cfg["settlement"], kind="future") if p["instrument_name"] == self.cfg["perp"]]
        return opts, (float(perp[0]["size_currency"]) if perp else 0.0)  # "size" of the USDC perpetual is in dollars, size_currency in BTC

    # -- orders

    def take(self, side, name, amount, reduce_only=False, label="bzd"):
        """Cross the spread now (hedges, closing): limit at the far side of the book, immediate or cancel."""
        inst = self.inst(name)
        lot = inst["min_trade_amount"]
        amount = round(math.floor(amount / lot + EPS) * lot, 8)
        if amount < lot - EPS:
            return 0.0
        q = self.quote(name)
        px = q["ask"] if side == "buy" else q["bid"]
        if not px:
            self.log(f"{name}: nessun prezzo per {side}")
            return 0.0
        o = self.c.call(f"private/{side}", instrument_name=name, amount=amount, type="limit", price=px, label=label,
                        reduce_only=reduce_only, time_in_force="immediate_or_cancel")["order"]
        got = float(o.get("filled_amount") or 0)
        journal("ordine", self.root, side=side, name=name, amount=amount, filled=got, price=o.get("average_price"), state=o["order_state"])
        return got

    # -- safety

    def check(self, opts):
        """The exchange against the book: any difference stops new entries."""
        want = {}
        for p in self.st["book"]:
            for leg in ("put", "call"):
                if p[f"{leg}_amount"] > EPS:
                    want[p[leg]] = round(want.get(p[leg], 0) - p[f"{leg}_amount"], 8)
        have = {p["instrument_name"]: round(p["size"], 8) for p in opts}
        diff = {k: (want.get(k, 0), have.get(k, 0)) for k in set(want) | set(have) if abs(want.get(k, 0) - have.get(k, 0)) > EPS}
        if diff:
            text = ", ".join(f"{k}: atteso {w}, sul conto {h}" for k, (w, h) in sorted(diff.items()))
            if self.st["blocked"] != text:
                self.say(f"⚠️ Il conto non torna con il registro: {text}. Niente entrate nuove finché non si sistema.", key="diff")
            self.st["blocked"] = text
        else:
            self.st["blocked"] = None

    def settle_expired(self, opts):
        have = {p["instrument_name"] for p in opts}
        now = self.now()
        for p in list(self.st["book"]):
            if now >= expiry_time(p["put"]) and p["put"] not in have and p["call"] not in have:
                pay = None
                try:
                    d = self.c.call("public/get_delivery_prices", index_name=f"{self.cfg['underlying'].lower()}_usd", count=5)["data"]
                    s = next(x["delivery_price"] for x in d if x["date"] == parse_name(p["put"])[0].isoformat())
                    kp, kc = parse_name(p["put"])[1], parse_name(p["call"])[1]
                    pay = p["put_amount"] * max(kp - s, 0) + p["call_amount"] * max(s - kc, 0)
                except (StopIteration, DeribitError, KeyError):
                    pass
                self.close_record(p, "scaduto", None if pay is None else round(p["cash_in"] - pay, 2))

    def close_record(self, p, reason, pnl):
        self.st["book"].remove(p)
        self.st["closed"].append({**p, "closed": self.now().isoformat(timespec="seconds"), "reason": reason, "pnl_options": pnl})
        journal("chiuso", self.root, id=p["id"], reason=reason, pnl_options=pnl)
        self.say(f"Chiuso lo strangle {p['put']} / {p['call']} ({reason})" + (f": opzioni {pnl:+.2f} USDC, copertura a parte" if pnl is not None else ""))
        self.save()

    def kill_switch(self, equity):
        self.st["peak"] = max(self.st["peak"] or equity, equity)
        dd = 1 - equity / self.st["peak"]
        if dd >= self.cfg["risk"]["kill_drawdown"] and not self.st["halted"]:
            self.st["halted"] = f"{self.now().isoformat(timespec='seconds')}: drawdown {dd:.1%}"
            self.say(f"🛑 Drawdown {dd:.1%} dal massimo: niente entrate nuove. Le aperte restano coperte. Per ripartire: python -m bzd.vol_bot riprendi")

    def margin_guard(self, equity, maint):
        """Above margin_close_all of equity the bot closes everything itself, before the exchange liquidates."""
        r = maint / equity if equity > 0 else 1.0
        if r >= self.cfg["risk"]["margin_close_all"] and self.st["book"]:
            self.say(f"🛑 Margine al {r:.0%} del conto: chiudo tutto prima che lo faccia Deribit.", key="margin_close")
            self.close_all("margine")
            return True
        if r >= self.cfg["risk"]["margin_block"]:
            self.say(f"⚠️ Margine al {r:.0%} del conto: niente entrate nuove.", key="margin_block")
            return True
        return False

    # -- hedging

    def hedge(self, reason):
        opts, perp = self.positions()
        delta = sum(float(p.get("delta") or 0) for p in opts)
        trade = hedge_trade(delta, perp, self.cfg["hedge"]["min_trade"])
        option_btc = sum(abs(p["size"]) for p in opts)
        if trade and not hedge_sane(trade, option_btc, perp):
            self.st["blocked"] = f"copertura assurda: {trade:+.4f} BTC con {option_btc:.4f} BTC di opzioni"
            self.say(f"🛑 Copertura rifiutata: {trade:+.4f} BTC sul perpetuo con {option_btc:.4f} BTC di opzioni. Controlla il conto.", key="hedge_insane")
            return
        if trade:
            got = self.take("buy" if trade > 0 else "sell", self.cfg["perp"], abs(trade), label="bzd-hedge")
            journal("copertura", self.root, reason=reason, option_delta=round(delta, 4), perp_before=perp, trade=trade, filled=got)
            if got < abs(trade) - EPS:
                self.say(f"⚠️ Copertura incompleta: {got} su {abs(trade):.4f} BTC. Riprovo al prossimo giro.", key="hedge_short")

    def emergency(self):
        opts, perp = self.positions()
        size = sum(abs(p["size"]) for p in opts) / 2  # BTC of strangle: each one is a put and a call
        net = sum(float(p.get("delta") or 0) for p in opts) + perp
        if size and abs(net) > self.cfg["hedge"]["emergency_delta_per_btc"] * size:
            self.say(f"⚡ Delta netto {net:+.3f} BTC su {size:.2f} BTC di strangle: copertura subito, fuori orario.", key="emergency", every_s=900)
            self.hedge("emergenza")

    # -- entry as a maker

    def entry(self, equity):
        now, w = self.now(), self.st["working"]
        if w and (not in_entry_window(now, self.cfg) or w["week"] != week_key(now)):
            return self.end_entry()
        if not in_entry_window(now, self.cfg):
            return None
        if not w:
            if self.st["last_week"] == week_key(now) or self.st["paused"] or self.st["halted"] or self.st["blocked"]:
                return None
            insts = [i for i in self.c.call("public/get_instruments", currency=self.cfg["settlement"], kind="option", expired=False)
                     if i["instrument_name"].startswith(f"{self.cfg['underlying']}_{self.cfg['settlement']}-")]
            self._inst.update({i["instrument_name"]: i for i in insts})
            self.st["last_week"] = week_key(now)  # one try a week, filled or not
            exp = choose_expiry(insts, now, self.cfg)
            if not exp:
                return self.skip("nessuna scadenza tra %d e %d giorni" % tuple(self.cfg["entry"]["days_range"]))
            names = {i["instrument_name"] for i in insts if i["expiration_timestamp"] == exp}
            book = [b for b in self.c.call("public/get_book_summary_by_currency", currency=self.cfg["settlement"], kind="option") if b["instrument_name"] in names]
            legs = choose_strangle(book, exp, now, self.cfg)
            if not legs:
                return self.skip("nessuna opzione vicina a 25 delta")
            open_amt = sum(max(p["put_amount"], p["call_amount"]) for p in self.st["book"])
            amount = entry_amount(equity, legs["under"], open_amt, self.cfg, self.inst(legs["put"])["min_trade_amount"])
            if amount <= 0:
                return self.skip("nozionale già al tetto o conto troppo piccolo")
            w = self.st["working"] = {"week": week_key(now), "id": uuid.uuid4().hex[:8], "amount": amount,
                                      "legs": {leg: {"name": legs[leg], "order_id": None, "price": None, "filled": 0.0, "order_filled": 0.0, "cash": 0.0}
                                               for leg in ("put", "call")}}
            self.save()
            self.say(f"Offro lo strangle {legs['put']} / {legs['call']}, {amount} BTC, al prezzo medio fino alle 16 UTC.")
        self.work_orders()
        return w

    def absorb(self, leg, o):
        """Add what an order filled since we last looked."""
        got = float(o.get("filled_amount") or 0)
        new = got - leg["order_filled"]
        if new > EPS:
            leg["cash"] += new * float(o["average_price"])  # average over the whole order; fine for one maker order at a time
            leg["filled"] = round(leg["filled"] + new, 8)
            leg["order_filled"] = got
            return True
        return False

    def work_orders(self):
        w, new_fill = self.st["working"], False
        for leg in w["legs"].values():
            if leg["order_id"]:
                o = self.c.call("private/get_order_state", order_id=leg["order_id"])
                new_fill |= self.absorb(leg, o)
                if o["order_state"] != "open":
                    leg["order_id"], leg["order_filled"] = None, 0.0
            left = round(w["amount"] - leg["filled"], 8)
            if left < self.inst(leg["name"])["min_trade_amount"] - EPS:
                continue
            q = self.quote(leg["name"])
            if not (q["bid"] > 0 and q["ask"] > q["bid"]):
                continue
            px = maker_price(q["bid"], q["ask"], self.inst(leg["name"]))
            if not leg["order_id"]:
                o = self.c.call("private/sell", instrument_name=leg["name"], amount=left, type="limit", price=px, post_only=True,
                                label=f"bzd-{w['id']}", time_in_force="good_til_cancelled")["order"]
                leg["order_id"], leg["price"], leg["order_filled"] = o["order_id"], px, 0.0
                new_fill |= self.absorb(leg, o)
                if o["order_state"] != "open":
                    leg["order_id"], leg["order_filled"] = None, 0.0
            elif abs(px - (leg["price"] or 0)) > EPS:
                o = self.c.call("private/edit", order_id=leg["order_id"], amount=round(leg["order_filled"] + left, 8), price=px, post_only=True)["order"]
                leg["price"] = px
                new_fill |= self.absorb(leg, o)
        self.sync_working()
        self.save()
        if new_fill:
            self.hedge("entrata")

    def sync_working(self):
        """Keep the book's record of this week's strangle equal to what has filled so far."""
        w = self.st["working"]
        filled = {k: v["filled"] for k, v in w["legs"].items()}
        if max(filled.values()) < EPS:
            return
        p = next((p for p in self.st["book"] if p["id"] == w["id"]), None)
        if p is None:
            p = {"id": w["id"], "opened": self.now().isoformat(timespec="seconds"), "put": w["legs"]["put"]["name"], "call": w["legs"]["call"]["name"]}
            self.st["book"].append(p)
        p.update({"put_amount": filled["put"], "call_amount": filled["call"], "cash_in": round(w["legs"]["put"]["cash"] + w["legs"]["call"]["cash"], 2)})

    def end_entry(self):
        w = self.st["working"]
        for leg in w["legs"].values():
            if leg["order_id"]:
                try:
                    self.absorb(leg, self.c.call("private/cancel", order_id=leg["order_id"]))
                except DeribitError:
                    pass
                leg["order_id"] = None
        self.sync_working()
        p = next((p for p in self.st["book"] if p["id"] == w["id"]), None)
        self.st["working"] = None
        self.save()
        if p:
            journal("entrata", self.root, id=p["id"], put=p["put"], call=p["call"], put_amount=p["put_amount"], call_amount=p["call_amount"], cash_in=p["cash_in"])
            self.say(f"Venduto lo strangle {p['put']} ({p['put_amount']}) / {p['call']} ({p['call_amount']}), premio {p['cash_in']:.2f} USDC. Coperto sul perpetuo.")
            self.hedge("entrata")
        else:
            self.skip("nessun ordine eseguito entro le 16 UTC")
        return p

    def skip(self, why):
        self.log(f"entrata saltata: {why}")
        journal("saltata", self.root, why=why)
        return None

    # -- the cycle

    def apply_control(self):
        ctrl = read_control(self.root)
        self.st["paused"] = bool(ctrl.get("paused"))
        if ctrl.get("resume") and ctrl["resume"] != self.st.get("resumed"):
            self.st["halted"], self.st["resumed"], self.st["peak"] = None, ctrl["resume"], None

    def cycle(self):
        self.apply_control()
        equity, maint = self.account()
        self.kill_switch(equity)
        opts, _ = self.positions()
        self.settle_expired(opts)
        if not self.st["working"]:
            self.check(opts)  # while orders work, fills land between reads; the check waits for the window to close
        stop = self.margin_guard(equity, maint)
        now = self.now()
        if hedge_due(now, self.st["last_hedge_day"], self.cfg):
            self.hedge("08:00 UTC")
            self.st["last_hedge_day"] = now.date().isoformat()
            journal("conto", self.root, equity=equity, maintenance=maint)
        else:
            self.emergency()
        if not stop or self.st["working"]:
            self.entry(equity)
        self.save()

    def close_all(self, reason="a mano"):
        if self.st["working"]:
            self.end_entry()
        for p in list(self.st["book"]):
            for leg in ("put", "call"):
                if p[f"{leg}_amount"] > EPS:
                    ask = self.quote(p[leg])["ask"]
                    got = self.take("buy", p[leg], p[f"{leg}_amount"], reduce_only=True, label=f"bzd-{p['id']}")
                    p[f"{leg}_amount"] = round(p[f"{leg}_amount"] - got, 8)
                    p["cash_in"] = round(p["cash_in"] - got * ask, 2)
                    self.save()
            if p["put_amount"] < EPS and p["call_amount"] < EPS:
                self.close_record(p, reason, p["cash_in"])
        self.hedge("chiusura")
        self.save()

    def status(self):
        eq, maint = self.account()
        opts, perp = self.positions()
        delta = sum(float(p.get("delta") or 0) for p in opts)
        lines = [f"Rete: {self.net}. Conto {eq:.2f} USDC, massimo {self.st['peak'] or eq:.2f}, margine {maint / eq if eq else 0:.0%}."]
        for k, label in (("paused", "In pausa."), ("halted", "Fermo: {}."), ("blocked", "Bloccato: {}.")):
            if self.st[k]:
                lines.append(label.format(self.st[k]))
        for p in self.st["book"]:
            lines.append(f"  {p['put']} ({p['put_amount']}) / {p['call']} ({p['call_amount']}): premio {p['cash_in']:.2f} USDC")
        if self.st["working"]:
            w = self.st["working"]
            lines.append("  in vendita adesso: " + ", ".join(f"{v['name']} {v['filled']}/{w['amount']}" for v in w["legs"].values()))
        lines.append(f"Delta opzioni {delta:+.4f} BTC, perpetuo {perp:+.4f}, netto {delta + perp:+.4f}.")
        done = [c for c in self.st["closed"] if c.get("pnl_options") is not None]
        if done:
            lines.append(f"Chiusi: {len(self.st['closed'])}, opzioni {sum(c['pnl_options'] for c in done):+.2f} USDC (la copertura è nel conto).")
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
    bot = Bot(client_from_env(), notify=telegram_notify())
    if cmd == "stato":
        print(bot.status())
    elif cmd == "chiudi":
        _l = lock()
        bot.close_all()
        print(bot.status())
    elif cmd in ("once", "run"):
        _l = lock()
        bot.say(f"Acceso sul {'testnet' if bot.net == 'test' else 'CONTO VERO'}: strangle BTC coperto.")
        while True:
            try:
                bot.cycle()
            except DeribitError as e:
                bot.say(f"Errore da Deribit: {e}", key=f"err:{str(e)[:60]}")
            except Exception as e:  # noqa: BLE001 - keep running, but say so
                bot.say(f"Errore: {type(e).__name__}: {e}", key=f"err:{type(e).__name__}")
            if cmd == "once":
                break
            time.sleep(bot.cfg["loop_seconds"])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
