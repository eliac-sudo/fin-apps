"""Forecasts by important actors, as tables with the date each forecast was made.

    python -m bzd.history get forecasts

- fomc_sep: the Fed's Summary of Economic Projections, every edition since 2012 (ALFRED vintages of FRED).
- us_spf: the Philadelphia Fed's Survey of Professional Forecasters, medians, every survey since 1968.
- ecb_spf: the ECB's Survey of Professional Forecasters, averages, every survey since 1999.
- oecd_outlook: the latest OECD Economic Outlook. Older editions are kept from now on by the recorder's daily copy.
- prediction markets (Kalshi, Polymarket): no free history, so only the recorder's copies every 6 hours.

Every table has `made` (when the forecast was published), `target` (the period forecast) and `value`.
A forecast is what someone expected, not what happened: tests must use only rows with `made` before the test date.
"""
import gzip, io, json, os, re, time

import pandas as pd

from . import history as H
from .jobs import ECB_SPF, FRED_FORECASTS, KALSHI, OECD_EO, PHILLY_SPF, POLYMARKET_TAGS

# Annual SEP series. FEDTARMDLR is the longer run, with no target year.
SEP_NAMES = {"FEDTARMD": "fed_funds_median", "FEDTARRH": "fed_funds_high", "FEDTARRL": "fed_funds_low", "FEDTARMDLR": "fed_funds_longer_run",
             "GDPC1MD": "real_gdp_growth", "UNRATEMD": "unemployment", "PCECTPIMD": "pce_inflation", "JCXFEMD": "core_pce_inflation"}
# Philadelphia sheets kept: inflation, growth, jobs and rates. Columns 1-6 are the survey quarter (1, the nowcast for the
# previous quarter, is mostly known) to five quarters ahead; A-D are annual averages for this year to three years ahead.
SPF_SHEETS = ("CPI", "CORECPI", "PCE", "COREPCE", "UNEMP", "RGDP", "NGDP", "INDPROD", "HOUSING", "TBILL", "TBOND", "BAABOND",
              "CPI5YR", "PCE5YR", "CPI10", "PCE10", "RGDP10", "PROD10", "STOCK10", "BOND10", "BILL10")


def sep_editions(by_series):
    """Every SEP publication date. A target year whose value didn't change keeps its old realtime_start, so editions come from all series."""
    return sorted({o["realtime_start"] for s, obs in by_series.items() if s != "FEDTARMDLR" for o in obs})


def parse_sep(series, observations, editions):
    """ALFRED rows -> one row per edition and target year: the value in force on the day each edition came out."""
    rows = []
    for o in observations:
        if o["value"] in (".", ""):
            continue
        if series == "FEDTARMDLR":  # dated by the edition itself, so only the latest vintage of each date is needed
            if o["realtime_end"] == "9999-12-31":
                rows.append({"made": o["date"], "series": SEP_NAMES[series], "target": "longer_run", "value": float(o["value"])})
            continue
        target = o["date"][:4]
        for e in editions:
            if o["realtime_start"] <= e <= o["realtime_end"] and int(target) >= int(e[:4]):
                rows.append({"made": e, "series": SEP_NAMES.get(series, series), "target": target, "value": float(o["value"])})
    return pd.DataFrame(rows, columns=["made", "series", "target", "value"])


def parse_philly(xlsx_bytes):
    sheets = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=[s for s in SPF_SHEETS])
    out = []
    for name, d in sheets.items():
        d = d.rename(columns=str.upper)
        q = d.YEAR.astype(int).astype(str) + "Q" + d.QUARTER.astype(int).astype(str)
        for c in d.columns[2:]:
            h = c[len(name):]
            if not h:
                continue
            if h.isdigit():  # quarters ahead of the survey: 1 is the quarter before it, 2 the survey quarter
                p = pd.PeriodIndex(q, freq="Q") + (int(h) - 2)
                target = p.astype(str)
            else:  # A this year, B next year...
                target = (d.YEAR.astype(int) + "ABCD".index(h)).astype(str) if h in "ABCD" else pd.Series([h] * len(d))
            out.append(pd.DataFrame({"made": q.values, "series": name.lower(), "target": list(target), "value": pd.to_numeric(d[c], errors="coerce").values}))
    d = pd.concat(out, ignore_index=True).dropna(subset=["value"])
    return d.sort_values(["made", "series", "target"]).reset_index(drop=True)


def parse_ecb_spf(csv_text):
    d = pd.read_csv(io.StringIO(csv_text), dtype={"FCT_HORIZON": str})
    # FCT_HORIZON is a calendar year, LT for the longer term (about five years ahead), or a rolling horizon such as P21M.
    # For the first two TIME_PERIOD is the survey quarter; rolling horizons date the row by the target, so they are left out.
    d = d[d.FCT_HORIZON.str.fullmatch(r"\d{4}|LT")]
    return pd.DataFrame({"made": d.TIME_PERIOD.str.replace("-", ""), "series": d.FCT_TOPIC.str.lower(), "target": d.FCT_HORIZON.astype(str),
                         "value": pd.to_numeric(d.OBS_VALUE, errors="coerce")}).dropna().sort_values(["made", "series", "target"]).reset_index(drop=True)


def parse_oecd(csv_text, edition_seen):
    d = pd.read_csv(io.StringIO(csv_text))
    edition = str(d.STRUCTURE_NAME.iloc[0]) if "STRUCTURE_NAME" in d and len(d) else "Economic Outlook"
    return pd.DataFrame({"made": edition_seen, "edition": edition, "area": d.REF_AREA, "series": d.MEASURE, "target": d.TIME_PERIOD.astype(str),
                         "value": pd.to_numeric(d.OBS_VALUE, errors="coerce")}).dropna(subset=["value"])


def get_forecasts(force=False):
    key, n = os.environ.get("FRED_API_KEY"), int(time.time()) if force else 0
    if key and (force or not H.done("forecasts", "fomc_sep")):
        raw = {}
        for s in FRED_FORECASTS:
            if s == "GDPNOW":
                continue  # a quarterly nowcast with its own history in macro/GDPNOW, revised as data arrive
            u = (f"https://api.stlouisfed.org/fred/series/observations?series_id={s}&api_key={key}&file_type=json"
                 "&realtime_start=1776-07-04&realtime_end=9999-12-31")
            raw[s] = json.loads(H.get("forecasts", s, n, u, secrets=("FRED_API_KEY",)))["observations"]
        editions = sep_editions(raw)
        parts = [parse_sep(s, obs, editions) for s, obs in raw.items()]
        H.save("forecasts", "fomc_sep", pd.concat(parts, ignore_index=True).drop_duplicates().sort_values(["made", "series", "target"]), quiet=force)
    if force or not H.done("forecasts", "us_spf"):
        H.save("forecasts", "us_spf", parse_philly(H.get("forecasts", "us_spf", n, PHILLY_SPF)), quiet=force)
    if force or not H.done("forecasts", "ecb_spf"):
        H.save("forecasts", "ecb_spf", parse_ecb_spf(H.get("forecasts", "ecb_spf", n, ECB_SPF).decode()), quiet=force)
    today = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    new = parse_oecd(H.get("forecasts", "oecd_outlook", int(time.time()), OECD_EO).decode(), today)
    if H.done("forecasts", "oecd_outlook"):
        old = pd.read_csv(H.root() / "forecasts" / "oecd_outlook.csv.gz", dtype={"target": str})
        known = set(old.edition)
        new = pd.concat([old, new[~new.edition.isin(known)]], ignore_index=True)  # an edition is kept as first seen
    H.save("forecasts", "oecd_outlook", new, quiet=force)


# ---- the app's Forecasts tab -------------------------------------------------------------------------------------------

KALSHI_LABELS = {"KXFEDDECISION": "Fed, prossime riunioni", "KXFED": "Tasso Fed (limite alto) dopo la riunione", "KXFEDFUNDSYEAR": "Tasso Fed a fine anno",
                 "KXRATECUTCOUNT": "Numero di tagli della Fed", "KXCPIYOY": "Inflazione USA annua", "KXCPI": "Inflazione USA del mese",
                 "KXCPICORE": "Inflazione core USA del mese", "KXCPICOREYOY": "Inflazione core USA annua", "KXPCECORE": "PCE core del mese",
                 "KXUSCPIYEAR": "Inflazione USA a fine anno", "KXGDP": "PIL reale USA del trimestre", "KXPAYROLLS": "Posti di lavoro del mese",
                 "KXU3": "Disoccupazione USA", "KXRECSSNBER": "Recessione USA", "KXINXY": "S&P 500 a fine anno", "KXNASDAQ100Y": "Nasdaq-100 a fine anno",
                 "KXBTCMAXY": "Bitcoin entro fine anno", "KXWTIMAX": "Petrolio WTI, massimo", "KXEURUSD": "Euro/dollaro"}
SEP_LABELS = {"fed_funds_median": "Tasso Fed, mediana", "fed_funds_low": "Tasso Fed, il più basso", "fed_funds_high": "Tasso Fed, il più alto",
              "real_gdp_growth": "PIL reale", "unemployment": "Disoccupazione", "pce_inflation": "Inflazione PCE", "core_pce_inflation": "Inflazione PCE core"}
OECD_AREAS = {"USA": "USA", "EA17": "Area euro", "DEU": "Germania", "ITA": "Italia", "FRA": "Francia", "GBR": "Regno Unito", "JPN": "Giappone", "CHN": "Cina", "W": "Mondo"}
OECD_SERIES = {"GDPV_ANNPCT": "PIL", "CPI_YTYPCT": "Inflazione", "CPIH_YTYPCT": "Inflazione", "UNR": "Disoccupazione", "IRS": "Tasso a 3 mesi", "IRL": "Bond 10 anni"}
SHOWN = (0.03, 0.97)  # outcomes the market sees as near certain either way say little


def _read(name):
    p = H.root() / "forecasts" / f"{name}.csv.gz"
    return pd.read_csv(p, dtype={"target": str, "made": str}) if p.exists() else None


def _raw(job):
    from .option_lab import latest_file
    f = latest_file(job, H.root().parent)
    if not f:
        return None, None
    ts = pd.Timestamp(f.parent.name + "T" + f.name[:6], tz="UTC").isoformat()
    return json.loads(gzip.open(f).read()), ts


def _quarter_date(q):
    return f"{q[:4]}-{int(q[-1]) * 3 - 2:02d}-01"


def fed_view(d):
    if d is None or d.empty:
        return None
    # editions come from the annual series: the longer-run rows are dated by their own observation, which may not match
    eds = sorted(d[d.series != "fed_funds_longer_run"].made.unique())
    if not eds:
        return None
    last, prev = eds[-1], eds[-2] if len(eds) > 1 else None
    cur = d[d.made == last]
    targets = sorted(t for t in cur.target.unique() if t != "longer_run")
    rows = []
    for s, label in SEP_LABELS.items():
        x = cur[cur.series == s].set_index("target").value
        p = d[(d.made == prev) & (d.series == s)].set_index("target").value if prev else pd.Series(dtype=float)
        rows.append({"label": label, "values": {t: x.get(t) for t in targets}, "prev": {t: p.get(t) for t in targets}})
    lr = d[(d.series == "fed_funds_longer_run")].sort_values("made")
    # How the expected rate for the end of next year moved, edition by edition
    nxt = d[(d.series.isin(["fed_funds_median", "core_pce_inflation", "unemployment"])) & (d.target.str.isdigit())]
    nxt = nxt[nxt.target.astype(int) == nxt.made.str[:4].astype(int) + 1]
    nxt = nxt.drop_duplicates(["made", "series"]).set_index(["made", "series"]).value
    shown = ("fed_funds_median", "core_pce_inflation", "unemployment")
    ch_eds = [e for e in eds if any((e, s) in nxt.index for s in shown)]
    chart = {"dates": ch_eds, **{s: [nxt.get((e, s)) for e in ch_eds] for s in shown}}
    return {"made": last, "prev_made": prev, "targets": targets, "rows": rows, "longer_run": lr.value.iloc[-1] if len(lr) else None,
            "longer_run_prev": lr.value.iloc[-2] if len(lr) > 1 else None, "chart": chart}


def survey_view(d, series, labels, since):
    """Latest survey: this year and the next two. Chart: the forecast for next year, survey by survey."""
    if d is None or d.empty:
        return None
    d = d[d.series.isin(series)]
    last = d.made.max()
    year = int(last[:4])
    years = [str(year + i) for i in range(3)]
    cur = d[d.made == last].set_index(["series", "target"]).value
    prev_q = sorted(d.made.unique())[-2]
    prev = d[d.made == prev_q].set_index(["series", "target"]).value
    rows = [{"label": labels[s], "values": {y: cur.get((s, y)) for y in years + ["LT"]}, "prev": {y: prev.get((s, y)) for y in years + ["LT"]}} for s in series]
    eds = sorted(m for m in d.made.unique() if m >= since)
    nxt = d[d.target.str.fullmatch(r"\d{4}")]
    nxt = nxt[nxt.target.astype(int) == nxt.made.str[:4].astype(int) + 1].set_index(["made", "series"]).value
    chart = {"dates": [_quarter_date(m) for m in eds], **{s: [nxt.get((m, s)) for m in eds] for s in series}}
    return {"made": last, "prev_made": prev_q, "years": years, "has_lt": any(r["values"]["LT"] is not None for r in rows), "rows": rows, "chart": chart}


def oecd_view(d):
    if d is None or d.empty:
        return None
    ed = d[d.made == d.made.max()]
    year = int(pd.Timestamp.now(tz="UTC").year)
    years = [str(year), str(year + 1)]
    rows = []
    for a, name in OECD_AREAS.items():
        x = ed[ed.area == a]
        row = {"label": name}
        for code, lab in OECD_SERIES.items():
            for y in years:
                v = x[(x.series == code) & (x.target == y)].value
                if len(v):
                    row[f"{lab} {y}"] = round(float(v.iloc[0]), 2)
        rows.append(row)
    cols = [f"{lab} {y}" for lab in dict.fromkeys(OECD_SERIES.values()) for y in years]
    return {"edition": ed.edition.iloc[0], "seen": ed.made.iloc[0], "cols": [c for c in cols if any(c in r for r in rows)], "rows": rows}


def _prob(m):
    """Midpoint when the spread is 10 cents or less, else the last trade. Prices compared in whole cents to avoid float noise."""
    bid, ask, last = (round(float(m.get(k) or 0) * 100) for k in ("yes_bid_dollars", "yes_ask_dollars", "last_price_dollars"))
    return (bid + ask) / 200 if bid and ask and ask - bid <= 10 else (last / 100 if last else None)


def _strike(name):
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", name or "")
    return float(m.group().replace(",", "")) if m else None


def by_strike(opts):
    """Ladders («Above 2.8%», «7,400 to 7,599.99») read best from the highest level down."""
    k = [_strike(o["name"]) for o in opts]
    return [o for _, o in sorted(zip(k, opts), key=lambda x: -x[0])] if all(v is not None for v in k) else opts


MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1)}
MESI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


def event_period(event_ticker):
    """KXFED-27JAN -> «gen 2027», KXINXY-26DEC31 -> «dic 2026», KXRECSSNBER-27 -> «2027». None when the ticker says nothing."""
    tail = event_ticker.rsplit("-", 1)[-1]
    m = re.fullmatch(r"(\d{2})([A-Z]{3})\d{0,2}", tail)
    if m and m.group(2) in MONTHS:
        return f"{MESI[MONTHS[m.group(2)] - 1]} 20{m.group(1)}"
    return f"20{tail}" if re.fullmatch(r"\d{2}", tail) else None


MAX_OPTIONS = 10
_market_errors = []  # sources that failed in the last view(), shown in the tab


def kalshi_view():
    out = []
    for s in KALSHI:
        label = KALSHI_LABELS.get(s, s)
        try:
            x, ts = _raw(f"fc_kalshi_{s.lower()}")
            events = {}
            for m in (x or {}).get("markets", []):
                events.setdefault(m["event_ticker"], []).append(m)
            shown = 0
            # the nearest two events that still have an open question
            for ev, ms in sorted(events.items(), key=lambda kv: min(m["close_time"] for m in kv[1])):
                opts = [{"name": m.get("yes_sub_title") or m.get("subtitle") or m["title"], "p": _prob(m), "vol": float(m.get("volume_fp") or 0)} for m in ms]
                opts = [o for o in opts if o["p"] is not None and SHOWN[0] <= o["p"] <= SHOWN[1]]
                if not opts:
                    continue
                # keep the most traded answers, then order them as a ladder
                keep = sorted(opts, key=lambda o: -o["vol"])[:MAX_OPTIONS]
                period = event_period(ev)
                out.append({"source": "Kalshi", "label": label + (f" · {period}" if period else ""), "question": label, "closes": min(m["close_time"] for m in ms),
                            "seen": ts, "options": by_strike(keep), "volume": sum(o["vol"] for o in keep)})
                shown += 1
                if shown == 2:
                    break
        except Exception as e:  # one broken series must not hide the others
            _market_errors.append(f"Kalshi {s}: {type(e).__name__}")
    return out


def polymarket_view():
    out, seen_ids = [], set()
    for t in POLYMARKET_TAGS:
        try:
            x, ts = _raw(f"fc_polymarket_{t}")
            fresh = [e for e in sorted(x or [], key=lambda e: -(e.get("volume24hr") or 0)) if e.get("id") not in seen_ids]
            for e in fresh[:10]:
                seen_ids.add(e.get("id"))
                opts = []
                for m in e.get("markets", []):
                    if m.get("closed") or not m.get("active", True):
                        continue
                    try:
                        p = float(json.loads(m["outcomePrices"])[0])
                    except (KeyError, ValueError, TypeError, IndexError):
                        continue
                    if SHOWN[0] <= p <= SHOWN[1]:
                        opts.append({"name": m.get("groupItemTitle") or m.get("question"), "p": p})
                if opts and e.get("title"):
                    out.append({"source": "Polymarket", "label": e["title"], "question": e["title"], "closes": e.get("endDate") or "", "seen": ts,
                                "options": sorted(opts, key=lambda o: -o["p"])[:8], "volume": e.get("volume24hr") or 0})
        except Exception as e:
            _market_errors.append(f"Polymarket {t}: {type(e).__name__}")
    return out


def gdpnow_view():
    p = H.root() / "macro" / "GDPNOW.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    return {"quarter": d.date.iloc[-1], "value": float(d.value.iloc[-1]), "prev_quarter": d.date.iloc[-2], "prev": float(d.value.iloc[-2])}


def view():
    """Everything the Forecasts tab shows. Each part is optional: a missing file leaves its part out."""
    parts, errors = {}, []
    _market_errors.clear()
    for k, f in (("fed", lambda: fed_view(_read("fomc_sep"))),
                 ("us_spf", lambda: survey_view(_read("us_spf"), ["cpi", "corepce", "unemp", "tbill", "tbond"],
                                                {"cpi": "Inflazione CPI", "corepce": "Inflazione PCE core", "unemp": "Disoccupazione", "tbill": "Treasury 3 mesi", "tbond": "Treasury 10 anni"}, "2015Q1")),
                 ("ecb_spf", lambda: survey_view(_read("ecb_spf"), ["hicp", "core", "rgdp", "unem"],
                                                 {"hicp": "Inflazione", "core": "Inflazione core", "rgdp": "PIL reale", "unem": "Disoccupazione"}, "2015Q1")),
                 ("oecd", lambda: oecd_view(_read("oecd_outlook"))), ("gdpnow", gdpnow_view),
                 ("kalshi", lambda: sorted(kalshi_view(), key=lambda e: e["closes"])), ("polymarket", polymarket_view)):
        try:
            parts[k] = f()
        except Exception as e:  # one broken source must not hide the others
            parts[k], errors = None, errors + [f"{k}: {type(e).__name__}"]
    return {**parts, "markets": (parts.get("kalshi") or []) + (parts.get("polymarket") or []), "errors": errors + _market_errors}
