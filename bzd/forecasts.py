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
import io, json, os, time

import pandas as pd

from . import history as H
from .jobs import ECB_SPF, FRED_FORECASTS, OECD_EO, PHILLY_SPF

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
