"""Experimental alerts: the frozen setups on fresh data, sent to Telegram, and every one logged for paper tracking.

    python -m bzd.alerts once [--dry]  refresh data, detect, send; --dry skips refresh and sending
    python -m bzd.alerts run           repeat until stopped
    python -m bzd.alerts test          send a test message
    python -m bzd.alerts chatid        show the chat id of whoever messaged the bot
    python -m bzd.alerts status        recent alerts and delivery state

Alerts are UNVALIDATED until phase B3 tests the setups. This module never places orders.
"""
import fcntl, json, os, signal, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import exits as X
from . import history as H
from .events import first_of_runs, ret_z
from .recorder import BASE, UA, load_env
from .setups import all_markets, config_hash, load_config, load_crypto, load_daily

MIN_SCORE_TO_SEND = 1  # about 5 alerts a week in the last 12 months; lower scores are logged, not sent
MAX_AGE = {"4h": pd.Timedelta(hours=8), "1d": pd.Timedelta(days=4)}  # older triggers are stale, e.g. after a pause
TELEGRAM_LIMIT = 3900
DAILY_EVERY, COT_EVERY = 6 * 3600, 24 * 3600
BAR_DELAY = 120  # seconds after a 4h close, so the exchange has finished the bar
HL_MARKET = {"ES=F": "xyz:SP500", "NQ=F": "xyz:XYZ100", "CL=F": "xyz:CL", "GC=F": "xyz:GOLD", "SI=F": "xyz:SILVER", "HG=F": "xyz:COPPER",
             "EURUSD=X": "xyz:EUR", "USDJPY=X": "xyz:JPY", "GBPUSD=X": "xyz:GBP", "ZB=F": "xyz:TLT"}
SETUP_IT = {"panic": "PANICO", "squeeze": "SQUEEZE", "overheating": "SURRISCALDAMENTO"}
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


def build_alert(cls, market, setup, trigger, price_df, conds, config, bar, now):
    """One alert as plain data, so it can be logged whether or not it gets sent."""
    cfg, keep = config["classes"][cls], config["scored"].get(cls, {}).get(setup, [])
    i = price_df.index.get_loc(trigger)
    values = {n: conds[n].iloc[i] for n in conds}
    z = ret_z(price_df.close, cfg["z_window"]).iloc[i]
    exit_cfg = json.loads(X.CONFIG.read_text())
    delay = config["confirm_bars"][setup] + 1
    return {
        "key": f"{market}|{setup}|{trigger.isoformat()}", "class": cls, "market": market, "setup": setup, "bar": bar,
        "trigger": trigger.isoformat(), "detected": now.isoformat(timespec="seconds"), "z": None if pd.isna(z) else round(float(z), 1),
        "score": int(sum(values[n] == 1 for n in keep)), "max_score": len(keep),
        "met": [n for n in keep if values[n] == 1], "not_met": [n for n in keep if values[n] == 0],
        "unknown": [n for n in keep if pd.isna(values[n])], "entry_after_bars": delay,
        "plan": level_plan(price_df.loc[:trigger], exit_cfg["initial_stop"]),
        "config_sha256": config_hash(),
    }


def calibration_note(cls, setup):
    """What the exit lab found for this class and setup, in the calibration period only."""
    p = H.root() / "exits_v1_calibration.csv"
    if setup == "overheating" or not p.exists():
        return None
    t = pd.read_csv(p)
    t = t[(t["class"] == cls) & (t.setup == setup)].set_index("rule")
    if not {"hold", "target_3R"} <= set(t.index):
        return None
    return f"Storico di calibrazione ({int(t.loc['hold', 'events'])} eventi): tieni {t.loc['hold', 'mean_R_per_event']:+.2f}R, stop + 3R {t.loc['target_3R', 'mean_R_per_event']:+.2f}R per evento."


def fmt_price(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:.4f}" if x >= 1 else f"{x:.6f}"


def format_item(a):
    hl = a["market"] if a["class"] == "crypto" else HL_MARKET.get(a["market"])
    head = f"• {a['market']}" + (f" → {hl}" if hl and hl != a["market"] else "" if hl else " (non su Hyperliquid, solo contesto)")
    out = [head + f": punteggio {a['score']}/{a['max_score']}" + (f", z {a['z']:+.1f}" if a["z"] is not None else "")]
    if a["met"]:
        out.append("  ✓ " + ", ".join(COND_IT[n] for n in a["met"]))
    if a["unknown"]:
        out.append("  ? " + ", ".join(COND_IT[n] for n in a["unknown"]) + " (dato non ancora noto)")
    p = a.get("plan")
    if p and a["setup"] != "overheating":
        line = f"  Prezzo {fmt_price(p['price'])} · stop {fmt_price(p['stop'])} (−{p['risk_pct']:.1%}) · obiettivo 3R {fmt_price(p['target_3r'])}"
        if p["risk_pct"] > .10:
            line += " ⚠️ stop molto largo: con la leva la liquidazione può arrivare prima"
        out.append(line)
    return "\n".join(out)


def format_group(alerts):
    """One message per class and setup, so a market-wide move doesn't send nine."""
    a0 = alerts[0]
    setup, wait = a0["setup"], a0["entry_after_bars"]
    action = {"overheating": "Se hai una posizione: valuta di ridurla o stringere lo stop. Non è un segnale di short.",
              "panic": f"Ingresso dello studio: non prima dell'apertura di {wait} barre dopo il trigger, per la conferma del volume.",
              "squeeze": "Ingresso dello studio: apertura della barra successiva."}[setup]
    lines = [f"🧪 {SETUP_IT[setup]} · {a0['class']} · barre {a0['bar']}", f"Trigger {a0['trigger'][:16].replace('T', ' ')} UTC", ""]
    lines += [format_item(a) for a in alerts] + ["", action]
    note = calibration_note(a0["class"], setup)
    if note:
        lines.append(note)
    lines.append("⚠️ NON VALIDATO: i test finali non sono ancora stati fatti. Stop e obiettivo sono indicativi. Non è consulenza finanziaria.")
    return "\n".join(lines)


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


def telegram_ready():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def sending_enabled():
    """Off until the agents review alerts first: the user wants nothing raw on Telegram, so it takes an explicit switch."""
    return telegram_ready() and os.environ.get("BZD_ALERTS_TELEGRAM") == "on"


def flush(st, send=None, log=print):
    """Send pending messages in order. Anything unsent stays pending for the next cycle."""
    send = send or (lambda text: telegram_call("sendMessage", {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text, "disable_web_page_preview": "true"}))
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
    """A condition that isn't known yet could still be met, so it can't be what keeps an alert from being sent."""
    return a["score"] + len(a["unknown"]) >= MIN_SCORE_TO_SEND


def enqueue(found, st, telegram_on):
    """Log every alert, mark it seen, and queue those worth sending. With no bot set up, nothing piles up for later."""
    alert_dir().mkdir(parents=True, exist_ok=True)
    with open(alert_dir() / "log.jsonl", "a") as f:
        for a in found:
            send = telegram_on and worth_sending(a)
            f.write(json.dumps({**a, "queued_for_telegram": send}) + "\n")
            st["seen"].append(a["key"])
    groups = {}
    for a in found:
        if telegram_on and worth_sending(a):
            groups.setdefault((a["class"], a["setup"], a["trigger"]), []).append(a)
    for g in groups.values():
        st["pending"] += split_message(format_group(g))
    st["seen"] = st["seen"][-5000:]


def crypto_due(st, now_ts):
    """True once per closed 4h bar, shortly after its close."""
    bar = 4 * 3600
    last_close = int((now_ts - BAR_DELAY) // bar * bar)
    return st["last_crypto"] < last_close


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
        enqueue(found, st, sending_enabled())
        log(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} checked: {new} new alerts")
    if sending_enabled():
        flush(st, log=log)
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
        for _ in range(60):
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
