"""Option strategies on paper, on the real quotes the recorder saves (config/options_forward_v1.json, docs/OPZIONI_IN_PROVA.md).

    python -m bzd.option_paper aggiorna   add the new days and settle what expired
    python -m bzd.option_paper stato      one line per strategy

Once a day per market, the first saved chain in the entry window opens every strategy whose condition holds: a sold leg fills
at the bid, a bought leg at the ask, and fees come off. It's held to expiry and settled on the underlying's price then.
The rules were frozen before any entry existed, and the ledger is rebuilt from the raw files, so nothing here can be tuned
after the fact. It never places an order: Deribit and Cboe are read through their public quotes only.
"""
import gzip, hashlib, json, math, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import option_lab as L
from . import option_models as M
from .recorder import BASE

CONFIG = BASE / "config" / "options_forward_v1.json"


def load_config(path=CONFIG):
    return json.loads(path.read_text())


def config_hash(path=CONFIG):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_root(root=None):
    return Path(root or os.environ.get("BZD_DATA", BASE / "data"))


def ledger_path(root=None):
    return data_root(root) / "options_paper" / "ledger.json"


def snapshots(job, root=None):
    """Every saved chain of a job, as (time, path), oldest first."""
    out = []
    for f in (data_root(root) / "raw" / job).glob("*/*.gz"):
        try:
            out.append((datetime.strptime(f.parent.name + f.name[:7], "%Y-%m-%d%H%M%SZ").replace(tzinfo=timezone.utc), f))
        except ValueError:
            continue
    return sorted(out)


def entry_snapshots(market, snaps, cfg):
    """The first chain of each day inside the entry window."""
    e, out = cfg["entry"], {}
    first = datetime.fromisoformat(e["first_day"]).date()
    for ts, f in snaps:
        h = ts.hour + ts.minute / 60
        ok = h >= e["deribit_from_utc_hour"] if market["kind"] == "deribit" else e["cboe_window_utc_hours"][0] <= h <= e["cboe_window_utc_hours"][1]
        if ok and ts.date() >= first and ts.weekday() < (7 if market["kind"] == "deribit" else 5):
            out.setdefault(ts.date(), (ts, f))
    return sorted(out.values())


def read_chain(market, path):
    rows, spot, mult, _ = L.PARSERS[market["kind"]](json.load(gzip.open(path)))
    return rows, spot


# ---- one expiry, its forward and the vol at the money

def pick_expiry(rows, ts, cfg):
    lo, hi = cfg["entry"]["days_range"]
    days = {}
    for r in rows:
        d = (r["expiry"] - ts).total_seconds() / 86400
        if lo <= d <= hi:
            days[r["expiry"]] = d
    return min(days.items(), key=lambda x: abs(x[1] - cfg["entry"]["target_days"])) if days else (None, None)


def quoted(rows):
    return [r for r in rows if r["bid"] > 0 and r["ask"] >= r["bid"]]


def forward_of(chain, spot, disc):
    if chain and chain[0].get("forward"):
        return float(chain[0]["forward"])
    calls = {r["strike"]: r for r in quoted(chain) if r["is_call"]}
    puts = {r["strike"]: r for r in quoted(chain) if not r["is_call"]}
    common = sorted(set(calls) & set(puts))
    if not common:
        return None
    return M.forward_from_parity(common, [(calls[k]["bid"] + calls[k]["ask"]) / 2 for k in common], [(puts[k]["bid"] + puts[k]["ask"]) / 2 for k in common], disc, spot)


def with_deltas(chain, fwd, years, disc):
    """Out-of-the-money quotes with their implied vol and delta, from the mid price."""
    out = []
    for r in quoted(chain):
        if (r["is_call"] and r["strike"] < fwd) or (not r["is_call"] and r["strike"] > fwd):
            continue
        iv = M.implied_vol((r["bid"] + r["ask"]) / 2, fwd, r["strike"], years, r["is_call"], disc)
        if iv:
            out.append({**r, "iv": iv, "delta": float(M.delta_gamma(fwd, r["strike"], years, iv, r["is_call"])[0])})
    return out


def atm_strike(chain, fwd):
    both = {r["strike"] for r in quoted(chain) if r["is_call"]} & {r["strike"] for r in quoted(chain) if not r["is_call"]}
    return min(both, key=lambda k: abs(k - fwd)) if both else None


def atm_vol(chain, fwd, years, disc):
    k = atm_strike(chain, fwd)
    if k is None:
        return None
    ivs = [M.implied_vol((r["bid"] + r["ask"]) / 2, fwd, k, years, r["is_call"], disc) for r in quoted(chain) if r["strike"] == k]
    ivs = [v for v in ivs if v]
    return sum(ivs) / len(ivs) if ivs else None


def forecast_before(market, day, days):
    """HAR on daily returns known before the entry day, so a rebuilt ledger never sees later prices."""
    c = L.under_closes(market)
    if c is None:
        return None
    start = pd.Timestamp(day)
    c = c[c.index < (start.tz_localize("UTC") if c.index.tz is not None else start)]
    if len(c) < 450:
        return None
    year_days = 365 if market["kind"] == "deribit" else 252
    r = np.log(c[c > 0]).diff().dropna().values
    return M.har_forecast(r, days if year_days == 365 else days * 252 / 365, year_days)


def label_of(ratio, cfg):
    t = cfg["thresholds"]
    return None if ratio is None else "economiche" if ratio < t["cheap_below"] else "care" if ratio > t["dear_above"] else "nella norma"


# ---- legs and money

def choose_leg(kind, target, side, chain, deltas, fwd, max_spread=None):
    is_call = kind == "call"
    if target == "atm":
        k = atm_strike(chain, fwd)
        pool = [r for r in quoted(chain) if r["strike"] == k and r["is_call"] == is_call]
    else:
        pool = sorted((r for r in deltas if r["is_call"] == is_call), key=lambda r: abs(abs(r["delta"]) - target))[:1]
    if not pool:
        return None
    r = pool[0]
    if max_spread is not None and (r["ask"] - r["bid"]) > max_spread * (r["ask"] + r["bid"]) / 2:
        return None  # a quote this wide is stale or empty: a fill there says nothing about the strategy
    price = r["ask"] if side > 0 else r["bid"]
    return None if price <= 0 else {"code": r["code"], "is_call": is_call, "strike": r["strike"], "qty": side, "price": price}


def fee_of(market, leg, spot, cfg):
    f = cfg["fees"][market["kind"]]
    return min(f["of_underlying"] * spot, f["cap_of_price"] * leg["price"]) if market["kind"] == "deribit" else f["per_unit"]


def build_legs(spec, chain, deltas, fwd, max_spread=None):
    legs = [choose_leg(kind, target, side, chain, deltas, fwd, max_spread) for kind, target, side in spec["legs"]]
    if any(l is None for l in legs):
        return None
    for kind in ("put", "call"):  # a wing must sit beyond the leg it covers, or the shape isn't what the name says
        side = sorted((l for l in legs if l["is_call"] == (kind == "call")), key=lambda l: l["strike"], reverse=kind == "call")
        if len(side) == 2 and (side[0]["strike"] == side[1]["strike"] or side[0]["qty"] < 0):
            return None
    return legs


def max_loss(legs, cash):
    """For a defined-risk shape: the widest gap between bought and sold strikes, less what was collected."""
    widths = [abs(a["strike"] - b["strike"]) for a in legs for b in legs if a["is_call"] == b["is_call"] and a["qty"] > 0 > b["qty"]]
    return max(widths) - cash if widths else None


def payoff(legs, price):
    return sum(l["qty"] * max(0.0, (price - l["strike"]) if l["is_call"] else (l["strike"] - price)) for l in legs)


def open_entries(market, ts, path, cfg):
    """Every strategy that opens on this chain, or why none does."""
    rows, spot = read_chain(market, path)
    exp, days = pick_expiry(rows, ts, cfg)
    if exp is None or not spot:
        return [], "nessuna scadenza tra 20 e 45 giorni"
    chain = [r for r in rows if r["expiry"] == exp]
    years = days / 365
    disc = math.exp(-L.risk_free() * years) if market["kind"] == "cboe" else 1.0
    fwd = forward_of(chain, spot, disc)
    if not fwd:
        return [], "forward non ricavabile"
    iv = atm_vol(chain, fwd, years, disc)
    fc = forecast_before(market, ts.date(), days)
    ratio = iv / fc if iv and fc else None
    label = label_of(ratio, cfg)
    deltas = with_deltas(chain, fwd, years, disc)
    out = []
    for sid, spec in cfg["strategies"].items():
        if spec["when"] != "sempre" and spec["when"] != label:
            continue
        legs = build_legs(spec, chain, deltas, fwd, cfg.get("max_leg_spread_of_mid"))
        if not legs:
            continue
        fees = sum(fee_of(market, l, spot, cfg) for l in legs)
        cash = -sum(l["qty"] * l["price"] for l in legs) - fees
        gross = abs(sum(l["qty"] * l["price"] for l in legs))
        per = gross if spec["per"] == "premio" else max_loss(legs, cash)
        if not per or per <= 0:
            continue
        out.append({"id": f"{market['key']}|{ts.date()}|{sid}", "market": market["key"], "strategy": sid, "at": ts.isoformat(timespec="minutes"), "expiry": exp.isoformat(timespec="minutes"),
                    "days": round(days, 1), "spot": spot, "forward": fwd, "iv": iv, "forecast": fc, "ratio": ratio, "label": label, "legs": legs, "fees": fees, "cash": cash, "per": per})
    return out, None


def settle_price(market, expiry, snaps, cfg):
    """The underlying at expiry. Deribit settles at 08:00 UTC, so the first chain saved after it, whose delivery price is the index.
    US options settle on the close: the daily close of that day, else the first chain saved well after the close."""
    if market["kind"] == "cboe" and market["key"] != "FXE":  # FXE's history is EUR/USD, not the fund
        c = L.under_closes(market)
        if c is not None:
            same = c[[str(i)[:10] == expiry.strftime("%Y-%m-%d") for i in c.index]]
            if len(same):
                return float(same.iloc[-1]), "chiusura del giorno"
    start = expiry + timedelta(hours=0 if market["kind"] == "deribit" else 2)
    limit = expiry + timedelta(days=cfg["settlement"]["max_days_after_expiry"])
    for ts, f in snaps:
        if start <= ts <= limit:
            _, spot = read_chain(market, f)
            if spot:
                return float(spot), ts.isoformat(timespec="minutes")
    return None, None


def mark(entry, quotes):
    """Value of the open legs at the latest mids, or None when a leg has no quote."""
    v = 0.0
    for l in entry["legs"]:
        q = quotes.get(l["code"])
        if not q or q["bid"] <= 0:
            return None
        v += l["qty"] * (q["bid"] + q["ask"]) / 2
    return v


# ---- the ledger

def update(root=None, now=None, cfg=None):
    cfg = cfg or load_config()
    now = now or datetime.now(timezone.utc)
    path = ledger_path(root)
    led = json.loads(path.read_text()) if path.exists() else {}
    if led.get("config") != config_hash():
        led = {"config": config_hash(), "entries": {}, "days": {}, "skipped": {}}
    for key in cfg["markets"]:
        market = L.BY_KEY[key]
        snaps = snapshots(market["job"], root)
        for ts, f in entry_snapshots(market, snaps, cfg):
            day = f"{key}|{ts.date()}"
            if day in led["days"]:
                continue
            try:
                found, why = open_entries(market, ts, f, cfg)
            except Exception as e:  # a broken file shouldn't stop the other days
                found, why = [], type(e).__name__
            for e in found:
                led["entries"][e["id"]] = e
            led["days"][day] = len(found)
            if why:
                led["skipped"][day] = why
        open_ = [e for e in led["entries"].values() if e["market"] == key and "pnl" not in e]
        for e in open_:
            exp = datetime.fromisoformat(e["expiry"])
            if exp > now:
                continue
            price, src = settle_price(market, exp, snaps, cfg)
            if price is None:
                continue
            pnl = e["cash"] + payoff(e["legs"], price)
            e.update(settle=price, settled_from=src, pnl=pnl, pnl_pct=100 * pnl / e["per"], pnl_spot_pct=100 * pnl / e["spot"])
        if snaps and any("pnl" not in e for e in led["entries"].values() if e["market"] == key):
            ts, f = snaps[-1]
            rows, _ = read_chain(market, f)
            quotes = {r["code"]: r for r in rows}
            for e in led["entries"].values():
                if e["market"] == key and "pnl" not in e:
                    v = mark(e, quotes)
                    e["open_pnl_pct"] = None if v is None else 100 * (e["cash"] + v) / e["per"]
                    e["marked_at"] = ts.isoformat(timespec="minutes")
    led["updated"] = now.isoformat(timespec="minutes")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(led, ensure_ascii=False))
    tmp.replace(path)
    return led


def summary(led, cfg=None):
    """Per strategy: entries, settled, average and worst result, share in profit, and the open ones at their latest mark."""
    cfg = cfg or load_config()
    out = {}
    for sid, spec in cfg["strategies"].items():
        es = [e for e in led.get("entries", {}).values() if e["strategy"] == sid]
        done = [e["pnl_pct"] for e in es if "pnl_pct" in e]
        live = [e["open_pnl_pct"] for e in es if "pnl_pct" not in e and e.get("open_pnl_pct") is not None]
        out[sid] = {"name": spec["name"], "when": spec["when"], "per": spec["per"], "from": spec.get("from"), "baseline": spec.get("baseline"), "entries": len(es), "settled": len(done),
                    "mean": float(np.mean(done)) if done else None, "worst": float(min(done)) if done else None, "share_up": float(np.mean([x > 0 for x in done])) if done else None,
                    "open": len(es) - len(done), "open_mean": float(np.mean(live)) if live else None,
                    "markets": sorted({e["market"] for e in es})}
    return out


def today(led, cfg=None):
    """The latest entry day of each market: how options are priced and which strategies opened."""
    cfg = cfg or load_config()
    last = {}
    for e in led.get("entries", {}).values():
        if e["market"] not in last or e["at"] > last[e["market"]]["at"]:
            last[e["market"]] = {"at": e["at"], "ratio": e["ratio"], "label": e["label"], "iv": e["iv"], "forecast": e["forecast"], "expiry": e["expiry"][:10]}
    for e in led.get("entries", {}).values():
        if e["market"] in last and e["at"] == last[e["market"]]["at"]:
            last[e["market"]].setdefault("opened", []).append(e["strategy"])
    return last



# ---- what the app shows

# Every strategy we talk about, tracked or not. Literature is cited by author and year; the papers' claims are theirs, not tested here
CATALOGUE = [
    {"id": "V1", "family": "vendere volatilità", "what": "Vendi una call e una put allo stesso strike, vicino al prezzo. Guadagni se a scadenza il prezzo si è mosso meno del premio incassato.",
     "risk": "Perdita senza limite se il prezzo scappa in una direzione.", "lit": "Coval e Shumway 2001: gli straddle comprati perdono in media, quindi chi vende incassa un premio. Carr e Wu 2009: il premio per il rischio di varianza.", "v3": "V1"},
    {"id": "V2", "family": "vendere volatilità", "what": "Come lo straddle, ma con strike lontani (delta 16, circa una deviazione standard). Incassi meno, vinci più spesso.",
     "risk": "Perdita senza limite, più rara ma più grande rispetto al premio.", "lit": "Stessa fonte del premio di varianza."},
    {"id": "V3", "family": "vendere volatilità a rischio limitato", "what": "Strangle venduto più due ali comprate più lontano (delta 5): la perdita massima è nota dall'inizio.",
     "risk": "Perdita massima pari alla distanza tra gli strike meno il premio.", "lit": "Le ali costano: parte del premio va a pagare l'assicurazione."},
    {"id": "V4", "family": "vendere volatilità a rischio limitato", "what": "Vendi una put a delta 25 e ne compri una a delta 10: guadagni se il prezzo non scende troppo.",
     "risk": "Perdita massima nota. È una scommessa rialzista lieve.", "lit": "Le put lontane sono le più care rispetto al movimento che segue (skew)."},
    {"id": "V5", "family": "vendere volatilità", "what": "Vendi una put al prezzo corrente (put-write). Equivale alla covered call: azione comprata più call venduta.",
     "risk": "Perdi come chi ha il sottostante se crolla, guadagni al massimo il premio.", "lit": "Indici Cboe PUT e BXM (Whaley 2002): rendimenti simili all'indice con meno volatilità, nel passato studiato."},
    {"id": "V6", "family": "comprare volatilità", "what": "Compra call e put allo stesso strike: guadagni se il prezzo si muove molto, in una direzione qualsiasi.",
     "risk": "Perdi al massimo il premio, ed è il caso più frequente.", "lit": "Coval e Shumway 2001: in media perde. Serve come base per confrontare C1."},
    {"id": "C1", "family": "condizionata", "what": "Compra lo straddle solo nei giorni in cui le opzioni sono economiche rispetto alla previsione HAR.",
     "risk": "Perdi al massimo il premio.", "lit": "Goyal e Saretto 2009: le opzioni con volatilità implicita bassa rispetto a quella storica hanno reso di più. È la lettura O2, l'unica che ha retto nel test storico v3.", "v3": "O2"},
    {"id": "C2", "family": "condizionata", "what": "Vendi lo straddle solo nei giorni in cui le opzioni sono care.",
     "risk": "Perdita senza limite.", "lit": "È la lettura O1: nel test storico v3 non ha reso più che vendere in un giorno qualsiasi.", "v3": "O1"},
    {"id": "C3", "family": "condizionata", "what": "Iron condor solo nei giorni in cui le opzioni sono care: la stessa idea di C2 con la perdita massima nota.",
     "risk": "Perdita massima nota.", "lit": "Nuova: nessuno storico, perché servono le catene vere."},
    {"id": "—", "family": "citata, non in prova", "name": "Calendar spread", "what": "Vendi la scadenza vicina e compri quella lontana, stesso strike: guadagni se la vicina perde valore più in fretta.",
     "risk": "Perdita limitata al costo, ma sensibile a come cambia la curva delle scadenze.", "lit": "Va chiusa prima della scadenza vicina: serve una regola di uscita, che oggi non c'è.", "why": "regola di uscita da scrivere"},
    {"id": "—", "family": "citata, non in prova", "name": "Risk reversal", "what": "Vendi una put lontana e compri una call lontana, o il contrario: una scommessa sullo skew e sulla direzione.",
     "risk": "Perdita ampia sul lato venduto.", "lit": "Serve una regola su quando lo skew è estremo, e oggi non c'è.", "why": "regola sullo skew da scrivere"},
    {"id": "—", "family": "citata, non in prova", "name": "Put di protezione", "what": "Compri put lontane come assicurazione su una posizione long.",
     "risk": "Costo fisso che si ripete.", "lit": "Israelov 2017: in media le put di protezione costano più di quanto proteggono.", "why": "è un costo di copertura, non una strategia da sola"},
    {"id": "—", "family": "citata, non in prova", "name": "Gamma scalping", "what": "Compri uno straddle e ogni giorno compri o vendi il sottostante per restare neutrale: guadagni se il prezzo oscilla più di quanto pagato.",
     "risk": "Perdi il premio se il prezzo resta fermo.", "lit": "Bakshi e Kapadia 2003: in media le opzioni coperte giorno per giorno perdono, cioè la volatilità costa più di quanto si realizza.", "why": "serve simulare le coperture giornaliere"},
]

VIEW_EVERY = 1800  # seconds between ledger updates triggered by the app
_state_memo = {}


def current_state(cfg=None, root=None):
    """How options are priced right now on each market, from the latest saved chain. Nothing is stored."""
    cfg = cfg or load_config()
    free = {**cfg, "entry": {**cfg["entry"], "first_day": "2000-01-01"}}
    out = {}
    for key in cfg["markets"]:
        market = L.BY_KEY[key]
        snaps = snapshots(market["job"], root)
        if not snaps:
            continue
        ts, f = snaps[-1]
        if str(f) not in _state_memo:
            try:
                found, why = open_entries(market, ts, f, free)
            except Exception as e:
                found, why = [], type(e).__name__
            e = found[0] if found else None
            _state_memo[str(f)] = {"at": ts.isoformat(timespec="minutes"), "ratio": e and e["ratio"], "label": e and e["label"], "iv": e and e["iv"], "forecast": e and e["forecast"],
                                   "expiry": e and e["expiry"][:10], "would_open": sorted(x["strategy"] for x in found), "why": why}
        out[key] = {"name": market["name"], **_state_memo[str(f)]}
    return out


def view(root=None):
    cfg = load_config()
    path = ledger_path(root)
    led = json.loads(path.read_text()) if path.exists() else {}
    stale = not led or (datetime.now(timezone.utc) - datetime.fromisoformat(led["updated"])).total_seconds() > VIEW_EVERY or led.get("config") != config_hash()
    if stale:
        led = update(root, cfg=cfg)
    from . import verdicts as VD
    return {"config": config_hash()[:12], "first_day": cfg["entry"]["first_day"], "readout": cfg["readout"], "updated": led.get("updated"), "strategies": summary(led, cfg),
            "now": current_state(cfg, root), "catalogue": CATALOGUE, "unconditional": VD.unconditional(), "verdicts": {k: VD.line(k) for k in ("O1", "O2")},
            "recent": sorted(({k: e.get(k) for k in ("market", "strategy", "at", "expiry", "label", "pnl_pct", "open_pnl_pct")} for e in led.get("entries", {}).values()), key=lambda e: e["at"], reverse=True)[:60]}


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "stato"
    led = update() if cmd == "aggiorna" else json.loads(ledger_path().read_text()) if ledger_path().exists() else {}
    for sid, s in summary(led).items():
        mean = "—" if s["mean"] is None else f"{s['mean']:+.1f}%"
        print(f"{sid} {s['name']}: {s['entries']} entrate, {s['settled']} chiuse, media {mean}, aperte {s['open']}")
    for k, v in today(led).items():
        print(k, v["at"], v["label"], ", ".join(sorted(v.get("opened", []))))


if __name__ == "__main__":
    main(sys.argv)
