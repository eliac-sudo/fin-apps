"""No-lookahead helpers shared by the setup detector. Nothing here computes forward returns."""
import numpy as np
import pandas as pd

from .history import root

def ret_z(close, win):
    """Log return in units of past volatility. The window excludes the current bar."""
    r = np.log(close.where(close > 0)).diff()
    return r / r.rolling(win).std().shift(1)


def past_quantile(s, q, min_periods=52):
    """Expanding quantile of strictly earlier values."""
    return s.expanding(min_periods).quantile(q).shift(1)


def log_z(v, win):
    x = np.log(v.where(v > 0))
    return (x - x.rolling(win).mean().shift(1)) / x.rolling(win).std().shift(1)


def align_cot(cot, index, qs=(.1, .25, .75, .9)):
    """Spec positioning and its past quantiles, usable only from each report's `available` date."""
    c = cot.copy()
    names = [f"p{round(q * 100)}" for q in qs]
    for q, n in zip(qs, names):
        c[n] = past_quantile(c.spec_net_pct_oi, q)
    c = c.assign(available=pd.to_datetime(c.available, utc=True)).drop_duplicates("available", keep="last").set_index("available").sort_index()
    return c[["spec_net_pct_oi"] + names].reindex(index, method="ffill", tolerance=pd.Timedelta(days=21))


def roll_artefact(d, z, etf_z=None):
    """Flag big futures moves that look like contract rolls, not trading.

    The ETF decides where it has a value: it holds no expiring contract, so a calm ETF means no real move, and a moving
    ETF confirms one even if it all happened overnight. Without an ETF, a move that is nearly all gap is suspect,
    since futures trade nearly all day.
    """
    move = d.close - d.close.shift(1)
    gap_only = (d.close - d.open).abs() < 0.25 * move.abs()
    if etf_z is None:
        return gap_only
    e = etf_z.reindex(d.index)
    return (e.abs() < 1).where(e.notna(), gap_only).astype(bool)


def first_of_runs(mask, days):
    """Keep the first trigger, then ignore more until the cool-off has passed."""
    out, last = [], None
    gap = pd.Timedelta(days=days)
    for t in mask[mask.fillna(False)].index:
        if last is None or t - last >= gap:
            out.append(t)
            last = t
    return pd.DatetimeIndex(out, tz="UTC") if out else pd.DatetimeIndex([], tz="UTC")


def n_clusters(idx, days):
    gap, n, last = pd.Timedelta(days=days), 0, None
    for t in sorted(idx):
        if last is None or t - last > gap:
            n += 1
        last = t
    return n


def read(group, name):
    p = root() / group / f"{name}.csv.gz"
    return pd.read_csv(p) if p.exists() else None


def daily(df):
    d = df.assign(date=pd.to_datetime(df.date, utc=True)).set_index("date").sort_index()
    return d[~d.index.duplicated()]


def crypto_daily(asset):
    """Daily closes from the 4h bars, which stay fresh. The last value is the latest closed bar of today, so it's never a day behind."""
    d = read("crypto", f"{asset}_candles_4h")
    if d is None:
        return None
    d = d.assign(date=pd.to_datetime(d.t.str[:10], utc=True)).sort_values("t")
    return d.drop_duplicates("date", keep="last").set_index("date")


def vol_series(name, index):
    x = read("vol", name)
    if x is None:
        x = read("tradfi", name)
    if x is not None:
        v = daily(x).close
    else:
        y = read("macro", name)
        if y is None:
            return None
        v = daily(y).value
    return v.reindex(index, method="ffill", tolerance=pd.Timedelta(days=5))
