"""Sentiment over time for one market: a price chart can then show when the mood reached an extreme. It describes, and it isn't tested as a signal.

The recorded texts start on 4 Nov 2026, so they can't give history yet. The long series uses what the crowd did instead:
  crypto  the Fear & Greed index from alternative.me, which is one number for the whole crypto market
  others  speculators' positions from the COT report and, where it exists, the calm of the market's volatility index, each as a percentile of its own past

Word counts per day are added on top as they build up. Reddit and most Telegram files are deleted after 35 days, so closed days are kept in
data/sentiment/days.json: this module writes only that file, and it holds nothing that isn't derived from saved data.
"""
import gzip, json, os, re, threading, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import indicators as I
from . import texts as T
from . import thermo as Z
from . import zones as ZN
from .events import align_cot, crypto_daily, daily, read
from .history import CRYPTO, safe
from .recorder import BASE
from .setups import VOL_INDEX, load_vol_index

GROUPS = (
    ("Cripto", "Cripto", T.TOPICS["crypto"]), ("Azioni", "Azioni", T.TOPICS["equities"]),
    ("Bond", "USA", r"treasur|\bt-bill|u\.?s\.? (bond|yield)|10-year yield|2-year yield"), ("Bond", "Europa", r"\bbunds?\b|\bbtps?\b|\bgilts?\b|euro(zone|pe\w*) (bond|yield)|\becb\b"),
    ("Bond", "Giappone", r"\bjgbs?\b|japan\w* (bond|yield)|\bboj\b|bank of japan"), ("Bond", "Cina", r"chin\w+ (government )?(bond|yield)|\bpboc\b"),
    ("Materie prime", "Energia", r"\boil\b|crude|\bwti\b|brent|opec|natural gas|\blng\b|gasoline|refiner"), ("Materie prime", "Metalli preziosi", r"\bgold\b|silver|platinum|palladium|bullion|precious metal"),
    ("Materie prime", "Metalli rari e industriali", r"copper|alumini?um|lithium|nickel|cobalt|rare earth|uranium|\bzinc\b"), ("Materie prime", "Agricoli", r"\bcorn\b|wheat|soybean|\bgrains?\b|\bcocoa\b|\bcoffee\b|\bsugar\b"),
    ("Forex", "Dollaro", r"\bdollar\b|\bdxy\b|\busd\b"), ("Forex", "Euro", r"\beuro\b|\beur\b|eurusd"), ("Forex", "Yen", r"\byen\b|\bjpy\b"), ("Forex", "Sterlina", r"\bsterling\b|\bpound\b|\bgbp\b"), ("Forex", "Franco svizzero", r"swiss franc|\bchf\b"), ("Forex", "Yuan", r"\byuan\b|\brenminbi\b|\bcny\b"),
)
CRYPTO_LOW, CRYPTO_HIGH = 25, 75  # alternative.me's own limits for extreme fear and extreme greed
OTHER_LOW, OTHER_HIGH = 15, 85  # chosen by judgment, not tested: from 1% to 20% of days on each side, depending on the market
MERGE_DAYS = 3
MIN_WORDS, WORD_SHARE = 10, .8  # a day counts as extreme with at least this many signals, and this share on one side
YEARS_SHOWN = 10
KEEP_AFTER_DAYS = 3  # a feed can still bring texts from the last few days, so only older days are final
WORDS_SECONDS = 1800
_lock, _words = threading.Lock(), {"at": 0, "days": None}


def gauge(market):
    """The market's mood from 0, fear, to 100, euphoria, with what it is made of. None without any source."""
    if market in CRYPTO:
        d = read("macro", "fear_greed")
        if d is None:
            return None
        s = pd.Series(d.value.values.astype(float), index=pd.to_datetime(d.date, utc=True)).sort_index()
        return {"series": s, "name": "Fear & Greed", "sources": ["Fear & Greed di alternative.me: è un solo numero per tutto il mercato cripto, non per la singola moneta"], "low": CRYPTO_LOW, "high": CRYPTO_HIGH}
    x = read("tradfi", safe(market))
    if x is None:
        return None
    index, parts, sources = daily(x).index, {}, []
    cot = read("cot", safe(market))
    if cot is not None:
        spec = I.past_percentile(align_cot(cot, index).spec_net_pct_oi.dropna()).reindex(index).ffill(limit=10)
        parts["spec"] = 100 - spec if market in Z.COT_AGAINST_PAIR else spec
        sources.append("posizioni degli speculatori (COT), come percentile del loro passato" + (": la coppia è quotata al contrario, quindi il segno è invertito" if market in Z.COT_AGAINST_PAIR else ""))
    vi = load_vol_index(VOL_INDEX[market], index) if market in VOL_INDEX else None
    if vi is not None:
        parts["calm"] = 100 - I.past_percentile(vi)
        sources.append(f"calma del suo indice di volatilità ({VOL_INDEX[market].replace('EVZCLS', 'EVZ, fermo a marzo 2025')}): volatilità alta vuol dire paura")
    if not parts:
        return None
    return {"series": pd.concat(parts, axis=1).mean(axis=1).dropna(), "name": "Umore degli operatori", "sources": sources, "low": OTHER_LOW, "high": OTHER_HIGH}


def state(v, low, high):
    return "paura" if v <= low else "euforia" if v >= high else None


def episodes(s, low, high, merge_days=MERGE_DAYS):
    """Runs of extreme days. A pause of a few days doesn't split a run, and a run only ever uses its own days, so the past can't change."""
    out = []
    for day, v in s.items():
        kind = state(v, low, high)
        if not kind:
            continue
        last = out[-1] if out else None
        if last and last["kind"] == kind and (day - pd.Timestamp(last["to"], tz="UTC")).days <= merge_days:
            last["to"], last["days"] = day.strftime("%Y-%m-%d"), last["days"] + 1
            if (v < last["peak"]) if kind == "paura" else (v > last["peak"]):
                last["peak"] = float(v)
        else:
            out.append({"from": day.strftime("%Y-%m-%d"), "to": day.strftime("%Y-%m-%d"), "kind": kind, "peak": float(v), "days": 1})
    return out


def _store(root=None):
    return Path(root or os.environ.get("BZD_DATA", BASE / "data")) / "sentiment" / "days.json"


def count_days(items_by_day):
    """Fear and greed words per theme, for each day."""
    patterns = [(name, re.compile(p, re.I)) for _, name, p in GROUPS]
    out = {}
    for day, items in items_by_day.items():
        out[day] = {}
        for name, pat in patterns:
            picked = [x for x in items if pat.search(x)]
            out[day][name] = {"texts": len(picked), "fear": sum(bool(re.search(Z.FEAR, x, re.I)) for x in picked), "greed": sum(bool(re.search(Z.GREED, x, re.I)) for x in picked)}
    return out


def read_days(root=None, now=None):
    """Counts per day and theme: final days from the store, recent ones from the raw files, and any final day not stored yet is added to it."""
    now, path = now or datetime.now(timezone.utc), _store(root)
    final = json.loads(path.read_text()) if path.exists() else {}
    raw = path.parents[1] / "raw"
    limit = (now - timedelta(days=KEEP_AFTER_DAYS)).strftime("%Y-%m-%d")
    folders = set()
    for job_dir in (p for p in sorted(raw.iterdir()) if p.name.startswith(("news_", "soc_")) and not p.name.startswith(T.SKIP_JOBS)) if raw.exists() else []:
        folders |= {(job_dir, d.name) for d in job_dir.iterdir() if d.is_dir()}
    first = min((d for _, d in folders), default=None)
    days_with_files = sorted({d for _, d in folders})
    oldest_open = min((d for d in days_with_files if d not in final), default=limit)
    seen, texts = set(), {}
    for job_dir, day in sorted(folders, key=lambda x: (x[0].name, x[1])):
        if (datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=KEEP_AFTER_DAYS)).strftime("%Y-%m-%d") < min(limit, oldest_open):
            continue  # this folder can only hold texts of days already stored
        for path_gz in sorted((job_dir / day).glob("*.gz")):
            try:
                rows = T.parse_job(job_dir.name, gzip.open(path_gz).read())
            except Exception:  # one malformed response must not stop the others
                continue
            for t, url, text in rows:
                if not text or t is None:
                    continue
                d, i = t.strftime("%Y-%m-%d"), T.item_id(url, text)
                if d >= first and d not in final and (d, i) not in seen:
                    seen.add((d, i))
                    texts.setdefault(d, []).append(text[:T.MAX_CHARS])
    counted = count_days(texts)
    new_final = {d: c for d, c in counted.items() if d < limit}
    if new_final:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({**final, **new_final}, sort_keys=True))
        os.replace(tmp, path)
    return {**final, **counted}


def word_days(root=None, now=None):
    """Counting reads every saved text, so the result is kept for a while."""
    with _lock:
        if _words["days"] is None or time.time() - _words["at"] > WORDS_SECONDS:
            _words.update(days=read_days(root, now), at=time.time())
        return _words["days"]


def word_marks(market, days):
    """The days on which this market's theme was extreme in the word count. On pairs quoted the other way round, good mood means the opposite."""
    theme, sign = ZN.SENTIMENT_OF.get(market, (None, 1))
    out = []
    for day in sorted(days):
        c = days[day].get(theme)
        if not c or c["fear"] + c["greed"] < MIN_WORDS:
            continue
        share = c["greed"] / (c["fear"] + c["greed"])
        kind = "euforia" if share >= WORD_SHARE else "paura" if share <= 1 - WORD_SHARE else None
        if kind and sign < 0:
            kind = "paura" if kind == "euforia" else "euforia"
        if kind:
            out.append({"date": day, "kind": kind, "fear": c["fear"], "greed": c["greed"], "texts": c["texts"]})
    return theme, out


def market_view(market, days=None):
    """Price, mood and extremes on the same dates, ready to draw."""
    g = gauge(market)
    if market in CRYPTO:
        d = crypto_daily(market)
    else:
        x = read("tradfi", safe(market))
        d = daily(x) if x is not None else None
    if d is None:
        return None
    close = d.close.dropna()
    close = close[close.index >= close.index[-1] - pd.Timedelta(days=int(365.25 * YEARS_SHOWN))]
    close.index = pd.to_datetime(close.index, utc=True).normalize()
    close = close[~close.index.duplicated(keep="last")]
    theme, marks = word_marks(market, word_days() if days is None else days)
    out = {"market": market, "theme": theme, "dates": [t.strftime("%Y-%m-%d") for t in close.index], "close": [float(x) for x in close.values], "word_marks": marks, "words_from": min(days, default=None) if days is not None else min(word_days(), default=None)}
    if g is None:
        return {**out, "gauge": None, "episodes": [], "sources": [], "gauge_name": None, "low": None, "high": None, "now": None}
    s = g["series"].copy()
    s.index = pd.to_datetime(s.index, utc=True).normalize()
    s = s[~s.index.duplicated(keep="last")]
    aligned = s.reindex(close.index, method="ffill", tolerance=pd.Timedelta(days=5))
    shown = aligned.dropna()
    now = float(s.iloc[-1])
    return {**out, "gauge": [None if np.isnan(x) else float(x) for x in aligned.values], "episodes": episodes(shown, g["low"], g["high"]), "sources": g["sources"], "gauge_name": g["name"], "low": g["low"], "high": g["high"],
            "now": {"value": now, "kind": state(now, g["low"], g["high"]), "date": s.index[-1].strftime("%Y-%m-%d")}}
