"""Option pricing tools, tested on known answers. No data access here.

Black-76 prices an option on its forward, the market standard, and the forward comes from put-call parity, so dividends needn't be guessed.
SVI (Gatheral) is the usual smooth curve through a smile. HAR forecasts volatility from past returns.
US ETF options are American, but on out-of-the-money contracts the early-exercise premium is small, so only those are used.
"""
import math

import numpy as np
import pandas as pd
from scipy.optimize import brentq, least_squares
from scipy.special import ndtr  # the normal CDF as a plain ufunc: the same numbers as the scipy.stats one, many times faster on single values

MAX_FIT_ERROR = .05  # five volatility points, on average across the strikes


def black76(forward, strike, years, vol, is_call, discount=1.0):
    """Value of a European option on a forward. Works on arrays."""
    forward, strike, years, vol = map(lambda x: np.asarray(x, float), (forward, strike, years, vol))
    sq = np.maximum(vol * np.sqrt(years), 1e-12)
    d1 = (np.log(forward / strike) + .5 * sq * sq) / sq
    d2 = d1 - sq
    call = forward * ndtr(d1) - strike * ndtr(d2)
    value = call if np.isscalar(is_call) and is_call else call - forward + strike if np.isscalar(is_call) else np.where(is_call, call, call - forward + strike)
    return discount * value


def delta_gamma(spot, strike, years, vol, is_call):
    """Spot delta and gamma with zero carry. Works on arrays."""
    spot, strike, years, vol = map(lambda x: np.asarray(x, float), (spot, strike, years, vol))
    sq = np.maximum(vol * np.sqrt(years), 1e-12)
    d1 = (np.log(spot / strike) + .5 * sq * sq) / sq
    return np.where(is_call, ndtr(d1), ndtr(d1) - 1), np.exp(-.5 * d1 * d1) / np.sqrt(2 * np.pi) / (spot * sq)


def _black76_one(forward, strike, years, vol, is_call, discount):
    """black76 for one contract in plain floats: the root search below calls it thousands of times, and numpy's overhead dominated."""
    sq = max(vol * math.sqrt(years), 1e-12)
    d1 = (math.log(forward / strike) + .5 * sq * sq) / sq
    cdf = lambda x: .5 * math.erfc(-x / math.sqrt(2))
    call = forward * cdf(d1) - strike * cdf(d1 - sq)
    return discount * (call if is_call else call - forward + strike)


def implied_vol(price, forward, strike, years, is_call, discount=1.0):
    """The volatility that reproduces a price, or None if no volatility can."""
    forward, strike, years, discount, is_call = float(forward), float(strike), float(years), float(discount), bool(is_call)
    intrinsic = discount * max((forward - strike) if is_call else (strike - forward), 0.0)
    if not price > intrinsic or years <= 0:
        return None
    f = lambda v: _black76_one(forward, strike, years, v, is_call, discount) - price
    try:
        return brentq(f, 1e-4, 10.0, xtol=1e-5) if f(1e-4) < 0 < f(10.0) else None
    except ValueError:
        return None


def forward_from_parity(strikes, call_mids, put_mids, discount, near):
    """Forward implied by calls and puts at the strikes closest to `near`, using the median to resist one bad quote."""
    pairs = sorted(zip(strikes, call_mids, put_mids), key=lambda x: abs(x[0] - near))[:5]
    values = [k + (c - p) / discount for k, c, p in pairs]
    return float(np.median(values)) if values else None


def svi_total_variance(k, p):
    a, b, rho, m, s = p
    return a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + s * s))


def svi_gradient(k, p):
    """Derivatives of the total variance by a, b, rho, m and sigma: exact, so the fit needn't estimate them by finite differences."""
    a, b, rho, m, s = p
    x = k - m
    r = np.sqrt(x * x + s * s)
    return np.column_stack([np.ones_like(k), rho * x + r, b * x, -b * (rho + x / r), b * s / r])


def fit_svi(log_moneyness, vols, years, weights=None):
    """Raw SVI through one expiry. Returns the parameters, or None with too few points or a poor fit."""
    k, v = np.asarray(log_moneyness, float), np.asarray(vols, float)
    if len(k) < 6:
        return None
    w = v * v * years
    wt = np.sqrt(np.asarray(weights, float)) if weights is not None else np.ones(len(k))
    atm = float(np.interp(0, np.sort(k), w[np.argsort(k)]))
    start = [max(atm * .5, 1e-5), max(atm, 1e-3), -.3, 0.0, .1]
    bounds = ([-1, 1e-5, -.999, -2, 1e-3], [5, 5, .999, 2, 3])
    try:
        fit = least_squares(lambda p: wt * (svi_total_variance(k, p) - w), start, jac=lambda p: wt[:, None] * svi_gradient(k, p), bounds=bounds, max_nfev=200)
    except ValueError:
        return None
    # stopping at the step limit is fine if the curve fits: the error decides, not the solver's flag
    if np.any(svi_total_variance(k, fit.x) <= 0) or np.sqrt(np.mean((np.sqrt(svi_total_variance(k, fit.x) / years) - v) ** 2)) > MAX_FIT_ERROR:
        return None
    return fit.x.tolist()


def svi_vol(k, p, years):
    return np.sqrt(np.maximum(svi_total_variance(np.asarray(k, float), p), 1e-10) / years)


def har_detail(returns, days, year_days, min_history=400):
    """The HAR forecast with its workings, or None with too little history.

    HAR (Corsi, 2009): future volatility, in logs, explained by volatility of the last 5, 22 and 66 days. It's refitted for each horizon,
    using only periods whose outcome is already known. Out of sample on 7 markets it beat GARCH, EWMA and last month's volatility, with little bias.
    """
    r = pd.Series(np.asarray(returns, float)).dropna()
    h = max(1, int(round(days)))
    if len(r) < min_history + h:
        return None
    v = r ** 2
    x = pd.DataFrame({"week": v.rolling(5).mean(), "month": v.rolling(22).mean(), "quarter": v.rolling(66).mean()}).clip(lower=1e-12)
    x = .5 * np.log(x * year_days)
    y = .5 * np.log((v.rolling(h).mean().shift(-h) * year_days).clip(lower=1e-12))
    known = x.iloc[:len(x) - h].dropna()
    target = y.reindex(known.index).dropna()
    known = known.loc[target.index]
    if len(known) < 100:
        return None
    b = np.linalg.lstsq(np.c_[np.ones(len(known)), known.values], target.values, rcond=None)[0]
    last = x.iloc[-1]
    return {"forecast": float(np.exp(np.r_[1.0, last.values] @ b)), "intercept": float(b[0]), "b_week": float(b[1]), "b_month": float(b[2]), "b_quarter": float(b[3]),
            "vol_week": float(np.exp(last["week"])), "vol_month": float(np.exp(last["month"])), "vol_quarter": float(np.exp(last["quarter"])), "samples": len(known), "horizon": h}


def har_forecast(returns, days, year_days, min_history=400):
    """Annualized volatility expected over the next `days` trading days, or None with too little history."""
    d = har_detail(returns, days, year_days, min_history)
    return d["forecast"] if d else None


def gex_by_strike(strikes, is_call, oi, vols, years, spot, multiplier):
    """Dollars of gamma per 1% move, per contract, before any assumption about who holds what."""
    _, g = delta_gamma(spot, strikes, years, vols, is_call)
    return g * np.asarray(oi, float) * multiplier * spot * spot * .01


def gamma_flip(strikes, is_call, oi, vols, years, spot, multiplier, width=.2, points=81):
    """The spot where total gamma changes sign, assuming dealers are long calls and short puts. None if it doesn't within the range."""
    grid = np.linspace(spot * (1 - width), spot * (1 + width), points)
    sign = np.where(is_call, 1.0, -1.0)
    totals = np.array([float(np.sum(sign * gex_by_strike(strikes, is_call, oi, vols, years, s, multiplier))) for s in grid])
    crossings = [grid[i] - totals[i] * (grid[i + 1] - grid[i]) / (totals[i + 1] - totals[i]) for i in range(len(grid) - 1) if totals[i] * totals[i + 1] < 0]
    return float(min(crossings, key=lambda x: abs(x - spot))) if crossings else None


def max_pain(strikes, is_call, oi, multiplier=1.0):
    """The expiry price at which option holders together would collect the least."""
    k, oi = np.asarray(strikes, float), np.asarray(oi, float)
    grid = np.unique(k)
    if not len(grid):
        return None
    pay = [float(np.sum(oi * np.where(is_call, np.maximum(p - k, 0), np.maximum(k - p, 0)))) for p in grid]
    return float(grid[int(np.argmin(pay))])
