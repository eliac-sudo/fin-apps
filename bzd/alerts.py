"""Experimental alerts: the frozen setups on fresh data, sent to Telegram, and every one logged for paper tracking.

    python -m bzd.alerts once [--dry]  refresh data, detect, send; --dry skips refresh and sending
    python -m bzd.alerts run           repeat until stopped
    python -m bzd.alerts test          send a test message
    python -m bzd.alerts chatid        show the chat id of whoever messaged the bot
    python -m bzd.alerts status        recent alerts and delivery state

Alerts are UNVALIDATED until phase B3 tests the setups. This module never places orders.
"""
import fcntl, gzip, html, json, os, signal, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

import re

import pandas as pd

from . import exits as X
from . import moves as M
from .agents import format_review, review_alerts
from . import history as H
from .events import first_of_runs, ret_z
from .recorder import BASE, UA, load_env
from .setups import all_markets, config_hash, load_config, load_crypto, load_daily
from .thermo import LABELS as THERMO_LABELS, market_position, position_text

MIN_SCORE_TO_SEND = 0  # every trigger is sent, also price alone: about 7 messages a week over the last 12 months
MAX_AGE = {"4h": pd.Timedelta(hours=8), "1d": pd.Timedelta(days=4)}  # older triggers are stale, e.g. after a pause
TELEGRAM_LIMIT = 3900
DAILY_EVERY, COT_EVERY = 6 * 3600, 24 * 3600
DIGEST_HOUR_UTC = 6  # the thermometer goes out once a day from this hour
CRYPTO_HL = {"BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK"}
COMMAND_MAX_AGE = 600  # seconds; a request older than this is ignored, because its prices would be stale
LOOP_SECONDS = 20
BAR_DELAY = 120  # seconds after a 4h close, so the exchange has finished the bar
HL_MARKET = {"ES=F": "xyz:SP500", "NQ=F": "xyz:XYZ100", "CL=F": "xyz:CL", "GC=F": "xyz:GOLD", "SI=F": "xyz:SILVER", "HG=F": "xyz:COPPER",
             "EURUSD=X": "xyz:EUR", "USDJPY=X": "xyz:JPY", "GBPUSD=X": "xyz:GBP", "ZB=F": "xyz:TLT"}
SETUP_IT = {"panic": "PANICO", "squeeze": "SQUEEZE", "overheating": "SURRISCALDAMENTO"}
SETUP_MEANS = {"panic": "Calo violento per gli standard di questo mercato.", "squeeze": "Salita forte per gli standard di questo mercato, spesso con chi era short costretto a chiudere.",
               "overheating": "Salita forte con segnali di eccesso."}
CLASS_IT = {"crypto": "cripto", "equities": "azioni", "bonds": "bond", "commodities": "materie prime", "fx": "forex"}
COND_IT = {"oi_flush": "leva ripulita (OI in forte calo)", "funding_nonpositive": "funding ≤ 0", "volume_spike_fading": "picco di volume in calo",
           "shorts_building": "short in aumento", "funding_mostly_negative": "funding quasi sempre negativo", "volume_high": "volume alto",
           "funding_high": "funding alto", "oi_rising": "OI in salita", "spec_low": "speculatori poco esposti", "spec_high": "speculatori molto esposti",
           "vol_index_high": "volatilità implicita alta", "vol_index_low": "volatilità implicita bassa", "vol_index_drop": "volatilità implicita in calo"}


def alert_dir():
    return Path(os.environ.get("BZD_DATA", BASE / "data")) / "alerts"


def load_state():
    p = alert_dir() / "state.json"
    return json.loads(p.read_text()) if p.exists() else {"seen": [], "pending": [], "last_crypto": 0, "last_daily": 0, "last_cot": 0}


def save_state(st):
    p = alert_dir() / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st))
    tmp.replace(p)


def recent_triggers(price, cooldown_days, bar, now):
    """Triggers, after the same cool-off as the study, that are still fresh enough to act on."""
    trig = first_of_runs(price.fillna(False).astype(bool), cooldown_days)
    return [t for t in trig if now - t <= MAX_AGE[bar]]


def level_plan(d, entry_rules):
    """Indicative stop and 3R target from the last closed bar, using the rule fixed before the exit lab."""
    atr = X.atr_series(d, 14).values
    px = float(d.close.iloc[-1])
    stop, risk = X.initial_stop(d.low.values.astype(float), atr, len(d), px, entry_rules)
    if risk is None:
        return None
    return {"price": px, "stop": stop, "target_3r": px + 3 * risk, "risk_pct": risk / px}


def hl_mark(market, root=None, now=None):
    """Latest Hyperliquid mark from the recorder's snapshots, if recent. Costs nothing, since it reads saved data."""
    name = market if market in CRYPTO_HL else HL_MARKET.get(market)
    if not name:
        return None
    base = Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "raw" / ("hl_ctx_xyz" if name.startswith("xyz:") else "hl_ctx_main")
    files = sorted(base.glob("*/*.gz"), key=lambda p: (p.parent.name, p.name))
    if not files:
        return None
    when = datetime.strptime(files[-1].parent.name + files[-1].name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc)
    if (now or datetime.now(timezone.utc)) - when > pd.Timedelta(hours=1):
        return None
    meta, ctx = json.load(gzip.open(files[-1]))
    for a, x in zip(meta["universe"], ctx):
        if a["name"] == name and x.get("markPx"):
            return float(x["markPx"])
    return None


def freshness(price_df, trigger, plan, market, now):
    """Has the price already moved past the plan? The levels were set at the trigger, which can be days old."""
    last, base = float(price_df.close.iloc[-1]), float(price_df.close.loc[trigger])
    out = {"bars_since_trigger": int(len(price_df.loc[trigger:]) - 1), "latest_close": last, "move_since_trigger_pct": round(100 * (last / base - 1), 2)}
    try:
        mark = hl_mark(market, now=now)
    except Exception:
        mark = None
    ref = last
    if plan and mark:
        out["hl_mark"] = mark
        out["hl_gap_from_plan_pct"] = round(100 * (mark / plan["price"] - 1), 2)
        if market in CRYPTO_HL:  # other markets have a basis against the futures used for the plan, so it is shown, not compared
            ref = mark
    if plan:
        out["plan_broken"] = bool(ref <= plan["stop"])
        out["target_hit"] = bool(ref >= plan["target_3r"])
    return out


def build_alert(cls, market, setup, trigger, price_df, conds, config, bar, now):
    """One alert as plain data, so it can be logged whether or not it gets sent."""
    cfg, keep = config["classes"][cls], config["scored"].get(cls, {}).get(setup, [])
    i = price_df.index.get_loc(trigger)
    values = {n: conds[n].iloc[i] for n in conds}
    z = ret_z(price_df.close, cfg["z_window"]).iloc[i]
    exit_cfg = json.loads(X.CONFIG.read_text())
    delay = config["confirm_bars"][setup] + 1
    plan = level_plan(price_df.loc[:trigger], exit_cfg["initial_stop"])
    return {
        "key": f"{market}|{setup}|{trigger.isoformat()}", "class": cls, "market": market, "setup": setup, "bar": bar,
        "trigger": trigger.isoformat(), "detected": now.isoformat(timespec="seconds"), "z": None if pd.isna(z) else round(float(z), 1),
        "score": int(sum(values[n] == 1 for n in keep)), "max_score": len(keep),
        "met": [n for n in keep if values[n] == 1], "not_met": [n for n in keep if values[n] == 0],
        "unknown": [n for n in keep if pd.isna(values[n])], "entry_after_bars": delay,
        "plan": plan, "fresh": freshness(price_df, trigger, plan, market, now),
        "config_sha256": config_hash(),
    }


def test_verdict(cls, setup):
    """What the one pre-registered test said about this class and setup."""
    p = BASE / "config" / "validation_v1.json"
    if not p.exists():
        return "⚠️ NON VALIDATO: il test finale non è ancora stato fatto."
    t = json.loads(p.read_text())["tests"].get(f"{cls}/{setup}")
    if not t:
        return "⚠️ NON VALIDATO: questo setup non è nel test."
    if t["outcome"] == "supportata":
        return f"✅ Test superato di poco: {100 * t['mean']:+.2f}% su ingressi casuali, media di {t['clusters']} episodi. Effetto piccolo, non regge alla soglia più severa, e può essere un falso positivo."
    if t["outcome"] == "non supportata":
        return f"❌ Test NON superato: nessun vantaggio dimostrato su ingressi casuali ({t['clusters']} episodi)."
    return f"❓ Test non informativo: troppi pochi episodi per dirlo ({t['clusters']})."


def fmt_price(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:.4f}" if x >= 1 else f"{x:.6f}"


def format_item(a):
    """What moved and whether it's cheap or dear. Entries, stops and targets are logged, and shown only where you ask for them."""
    name = THERMO_LABELS.get(a["market"], a["market"])
    out = [f"• <b>{name}</b>" + (f": movimento {a['z']:+.1f} volte il normale" if a["z"] is not None else "")]
    pos = safe_position(a["market"])
    if pos:
        out.append(f"  Prezzo: {position_text(pos)}")
    f = a.get("fresh") or {}
    if f.get("bars_since_trigger"):
        out.append(f"  Da allora: {f['move_since_trigger_pct']:+.1f}%")
    if a["met"]:
        out.append("  Conferme: " + ", ".join(COND_IT[n] for n in a["met"]))
    if a["unknown"]:
        out.append("  Non ancora noto: " + ", ".join(COND_IT[n] for n in a["unknown"]))
    return "\n".join(out)


def format_group(alerts, review=None):
    """One message per class and setup, so a market-wide move doesn't send nine."""
    a0 = alerts[0]
    setup = a0["setup"]
    lines = [f"🧪 <b>{SETUP_IT[setup]}</b> · {CLASS_IT.get(a0['class'], a0['class'])}", SETUP_MEANS[setup], f"Trigger {a0['trigger'][:16].replace('T', ' ')} UTC", ""]
    lines += [format_item(a) for a in alerts] + [""]
    if review:
        lines += [format_review(review), ""]
    lines.append(test_verdict(a0["class"], setup))
    options = safe_options([(a["class"], a["market"]) for a in alerts])
    if options:
        lines += ["", options, ""]
    lines.append("Economico e caro sono rispetto al passato di quel mercato, non a quanto vale. Non è consulenza finanziaria.")
    return "\n".join(lines)


def safe_position(market):
    """Context only: if it fails, the alert still goes out."""
    try:
        return market_position(market)
    except Exception:
        return None


def safe_options(markets):
    """Options are context: if they fail, the alert still goes out."""
    from .options_report import options_note
    try:
        return options_note(markets)
    except Exception:
        return ""


def check_moves(st, telegram_on, now=None, root=None, sigma=M.market_sigma):
    """Strong moves on the Hyperliquid markets we follow. All are logged, and sent as one message when the bot is on."""
    now = now or datetime.now(timezone.utc)
    markets = {**{c: c for c in CRYPTO_HL}, **{v: k for k, v in HL_MARKET.items()}}
    moves = M.apply_cooldown(M.find_moves(markets, st, now, root, sigma), st, now)
    for m in moves:
        pos = safe_position(m["market"])
        m["position"] = position_text(pos) if pos else None
    if moves:
        alert_dir().mkdir(parents=True, exist_ok=True)
        with open(alert_dir() / "moves.jsonl", "a") as f:
            for m in moves:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
        if telegram_on:
            st["pending"] += split_message(M.format_moves(moves, now, safe_options([(m["class"], m["market"]) for m in moves])))
    return moves


def poll_commands(st, log=print, now=None):
    """Answer /piano from your own chat only. Anything else, or anything old after a pause, is ignored. This reads and replies: it never trades."""
    from . import plan
    now = now or time.time()
    updates = telegram_call("getUpdates", {"offset": st.get("tg_offset", 0), "timeout": 0, "allowed_updates": json.dumps(["message"])}).get("result", [])
    for u in updates:
        st["tg_offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        words = str(m.get("text") or "").split()
        if str((m.get("chat") or {}).get("id")) != str(os.environ["TELEGRAM_CHAT_ID"]) or now - m.get("date", 0) > COMMAND_MAX_AGE or not words:
            continue
        cmd = words[0].split("@")[0].lower()
        if cmd in ("/piano", "/plan"):
            for part in split_message(plan.answer(words[1:])):
                send_text(part)
    save_state(st)


def split_message(text, limit=TELEGRAM_LIMIT):
    """Split on line breaks, since Telegram rejects long messages."""
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    return parts + ([cur] if cur else [])


def telegram_call(method, params):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=urllib.parse.urlencode(params).encode(), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"telegram http {e.code}") from None  # the URL holds the token, so it never goes in the error
    except urllib.error.URLError as e:
        raise RuntimeError(f"telegram unreachable: {type(e.reason).__name__}") from None


def send_text(text):
    """Send with light formatting. If Telegram rejects the markup, send the same words plain, so an alert is never lost."""
    base = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text, "disable_web_page_preview": "true"}
    try:
        return telegram_call("sendMessage", {**base, "parse_mode": "HTML"})
    except RuntimeError as e:
        if "http 400" not in str(e):
            raise
        return telegram_call("sendMessage", {**base, "text": html.unescape(re.sub(r"</?(b|a)\b[^>]*>", "", text))})


def telegram_ready():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def sending_enabled():
    """Off until the agents review alerts first: the user wants nothing raw on Telegram, so it takes an explicit switch."""
    return telegram_ready() and os.environ.get("BZD_ALERTS_TELEGRAM") == "on"


def flush(st, send=None, log=print):
    """Send pending messages in order. Anything unsent stays pending for the next cycle."""
    send = send or send_text
    while st["pending"]:
        try:
            send(st["pending"][0])
        except Exception as e:
            log(f"send failed, will retry: {e}")
            return False
        st["pending"].pop(0)
    return True


def detect(config, st, now):
    """New alerts across all markets. Data is read through the same frozen detector as the study."""
    found = []
    for cls, market, setups, index in all_markets(config):
        bar = config["classes"][cls]["bar"]
        d = load_crypto(market)[0] if cls == "crypto" else load_daily(market)["d"]
        for setup, (price, conds) in setups.items():
            for t in recent_triggers(price, config["classes"][cls]["cooldown_days"], bar, now):
                if f"{market}|{setup}|{t.isoformat()}" not in st["seen"]:
                    found.append(build_alert(cls, market, setup, t, d, conds, config, bar, now))
    return found


def worth_sending(a):
    return a["score"] + len(a["unknown"]) >= MIN_SCORE_TO_SEND


def worth_reviewing(a):
    """Paid reviews stay on triggers with some confirmation. A condition not known yet could still be met, so it counts."""
    return a["score"] + len(a["unknown"]) >= 1


def enqueue(found, st, telegram_on, review=None):
    """Log every alert, whatever the agents say, and queue those worth sending. Without a bot, nothing piles up for later.

    Only alerts worth sending get a paid review. A review can add a view, but it can't remove an alert.
    """
    alert_dir().mkdir(parents=True, exist_ok=True)
    groups, reviews = {}, {}
    for a in found:
        if worth_sending(a):
            groups.setdefault((a["class"], a["setup"], a["trigger"]), []).append(a)
    for k, g in groups.items():
        paid = [a for a in g if worth_reviewing(a)]
        if review and paid:
            reviews[k] = review(paid)
    with open(alert_dir() / "log.jsonl", "a") as f:
        for a in found:
            rec = reviews.get((a["class"], a["setup"], a["trigger"])) if worth_reviewing(a) else None
            f.write(json.dumps({**a, "queued_for_telegram": telegram_on and worth_sending(a), "review_status": rec["status"] if rec else None,
                                "review_stance": rec["review"]["lettura"] if rec and rec.get("review") else None}, ensure_ascii=False) + "\n")
            st["seen"].append(a["key"])
    if telegram_on:
        for k, g in groups.items():
            st["pending"] += split_message(format_group(g, reviews.get(k)))
    st["seen"] = st["seen"][-5000:]


def crypto_due(st, now_ts):
    """True once per closed 4h bar, shortly after its close."""
    bar = 4 * 3600
    last_close = int((now_ts - BAR_DELAY) // bar * bar)
    return st["last_crypto"] < last_close


def digest_due(st, now):
    """True once per UTC day, from the set hour, so a paused Codespace doesn't send a backlog."""
    today = now.strftime("%Y-%m-%d")
    return now.hour >= DIGEST_HOUR_UTC and st.get("last_digest") != today


def queue_digest(st, now, log=print):
    from .options_report import build_report
    from .thermo import build_digest
    try:
        st["pending"] += split_message(build_digest(now)[0]) + split_message(build_report(now))
        st["last_digest"] = now.strftime("%Y-%m-%d")
    except Exception as e:
        log(f"thermometer failed, will retry: {type(e).__name__}: {e}")


def cycle(st, log=print, refresh=True):
    now_ts = time.time()
    changed = False
    if refresh:
        try:
            if crypto_due(st, now_ts):
                H.refresh_crypto()
                st["last_crypto"], changed = now_ts, True
            if now_ts - st["last_daily"] >= DAILY_EVERY:
                with_cot = now_ts - st["last_cot"] >= COT_EVERY
                H.refresh_daily(with_cot)
                st["last_daily"], changed = now_ts, True
                if with_cot:
                    st["last_cot"] = now_ts
        except Exception as e:
            log(f"refresh failed, will retry: {e}")
    new = 0
    if changed or not refresh:
        found = detect(load_config(), st, pd.Timestamp.now(tz="UTC"))
        new = len(found)
        enqueue(found, st, sending_enabled(), review_alerts)
        log(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} checked: {new} new alerts")
    try:
        moved = check_moves(st, sending_enabled())
        if moved:
            log(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} strong moves: {len(moved)}")
    except Exception as e:
        log(f"move check failed, will retry: {type(e).__name__}: {e}")
    if sending_enabled():
        now = datetime.now(timezone.utc)
        if digest_due(st, now):
            queue_digest(st, now, log)
        flush(st, log=log)
        try:
            poll_commands(st, log)
        except Exception as e:
            log(f"command check failed, will retry: {type(e).__name__}: {e}")
    save_state(st)
    return new


def cmd_run():
    alert_dir().mkdir(parents=True, exist_ok=True)
    lock = open(alert_dir() / "alerts.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("alerts already running", flush=True)
        return 1
    flag = {"stop": False}
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, lambda *_: flag.update(stop=True))
    log = lambda m: print(m, flush=True)
    log(f"alerts running; telegram {'on' if sending_enabled() else 'off, logging only'}")
    while not flag["stop"]:
        try:
            load_env()
            cycle(load_state(), log)
        except Exception as e:
            log(f"cycle failed: {type(e).__name__}: {e}")
        for _ in range(LOOP_SECONDS):
            if flag["stop"]:
                break
            time.sleep(1)
    return 0


def cmd_status():
    st, p = load_state(), alert_dir() / "log.jsonl"
    print("telegram:", "on" if sending_enabled() else "off (logging only)", "| messages waiting:", len(st["pending"]))
    for k in ("last_crypto", "last_daily", "last_cot"):
        print(k, datetime.fromtimestamp(st[k], timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if st[k] else "never")
    if p.exists():
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        print(f"logged alerts: {len(rows)}")
        for r in rows[-10:]:
            print(f"  {r['trigger'][:16]} {r['market']:<9} {r['setup']:<12} {r['score']}/{r['max_score']} {'sent' if r['queued_for_telegram'] else 'log only'}")
    return 0


def main(argv):
    load_env()
    cmd = argv[0] if argv else ""
    if cmd == "run":
        return cmd_run()
    if cmd == "once":
        alert_dir().mkdir(parents=True, exist_ok=True)
        dry = "--dry" in argv
        st = load_state()
        if dry:
            found = detect(load_config(), st, pd.Timestamp.now(tz="UTC"))
            print(f"{len(found)} alerts would be logged (nothing saved)")
            groups = {}
            for a in found:
                groups.setdefault((a["class"], a["setup"], a["trigger"]), []).append(a)
            for g in groups.values():
                print("\n" + format_group(g))
            return 0
        print(cycle(st), "new alerts")
        return 0
    if cmd == "test":
        if not telegram_ready():
            print("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env first.")
            return 1
        telegram_call("sendMessage", {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": "✅ BZD: il bot funziona."})
        print("sent")
        return 0
    if cmd == "chatid":
        if not os.environ.get("TELEGRAM_BOT_TOKEN"):
            print("Add TELEGRAM_BOT_TOKEN to .env first.")
            return 1
        ids = {(u["message"]["chat"]["id"], u["message"]["chat"].get("first_name") or u["message"]["chat"].get("title")) for u in telegram_call("getUpdates", {}).get("result", []) if "message" in u}
        print(ids or "No messages yet: send your bot any message on Telegram, then run this again.")
        return 0
    if cmd == "status":
        return cmd_status()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
