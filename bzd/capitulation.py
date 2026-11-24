"""BYZ, capitulation: a strong market that fell a lot, then went quiet and sideways. Not tested: chosen by judgment on 7 November 2026.

It fires only when all four hold, on daily closes:
1. Strong market: one of a short list of assets people hold for years (big crypto, US indices, metals), and the high it fell from was
   the highest close of the three years before it. Forex, bonds, energy and grains are left out: they don't trend up over years.
2. Price capitulation: the fall from the high of the last two years is at least 20% and among the deepest 10% of this market's own history.
3. Volatility killed: 20-session volatility is at most half of its peak during the fall, and in the lowest third of the last two years.
4. Time capitulation: no new low for 40 sessions, and the range of those 40 sessions is at most a third of the fall.

In the history it fired on BTC from August 2022 to January 2023, on the S&P 500 in June 2009, on the Russell in 2023, and on silver in
2012 and 2013, which then kept falling. That is a look at the past, not a test: the rule was set after seeing those years.
"""
import math

import numpy as np

from . import technicals as K

STRONG = ("BTC", "ETH", "SOL", "BNB", "ES=F", "NQ=F", "RTY=F", "GC=F", "SI=F", "HG=F")
PEAK_BARS, BEFORE_BARS, QUIET_BARS, VOL_BARS = 500, 750, 40, 20
MIN_FALL, FALL_PCTL = .20, .90
VOL_SHARE, VOL_PCTL = .5, 1 / 3
RANGE_SHARE = 1 / 3


def check(d, crypto=False):
    """The four conditions on the last bar of daily OHLC d, with the numbers behind each. None with too little history."""
    c = d.close.dropna()
    if len(c) < PEAK_BARS + 250:
        return None
    window = c.iloc[-PEAK_BARS:]
    p = len(c) - PEAK_BARS + int(np.argmax(window.values))
    peak, now = float(c.iloc[p]), float(c.iloc[-1])
    prior = c.iloc[max(0, p - BEFORE_BARS):p]
    strong = len(prior) > 250 and peak >= float(prior.max())

    fall = 1 - now / peak
    hist = 1 - c / c.rolling(PEAK_BARS, min_periods=250).max()
    pctl = float((hist.dropna() <= fall).mean())
    deep = fall >= MIN_FALL and pctl >= FALL_PCTL

    vol = np.log(c).diff().rolling(VOL_BARS).std() * math.sqrt(365 if crypto else 252)
    v_now, v_peak = float(vol.iloc[-1]), float(vol.iloc[p:].max())
    v_low = float(vol.iloc[-500:].quantile(VOL_PCTL))
    calm = v_now <= VOL_SHARE * v_peak and v_now <= v_low

    since = c.iloc[p:]
    trough = float(since.min())
    low_at = since.idxmin()
    quiet_from = len(c) - QUIET_BARS
    no_new_low = quiet_from > p and float(c.iloc[quiet_from:].min()) > float(c.iloc[p:quiet_from].min())
    last = c.iloc[quiet_from:]
    width = float(last.max() - last.min())
    tight = peak > trough and width <= RANGE_SHARE * (peak - trough)
    sideways = no_new_low and tight
    bars_since_low = int(len(c) - 1 - c.index.get_loc(low_at))

    conditions = [
        {"key": "forte", "ok": strong, "label": "Asset forte", "short": "massimo di 3 anni" if strong else "no", "detail": f"il massimo da cui è sceso, {c.index[p]:%d/%m/%Y}, era il più alto dei 3 anni prima" if strong else "il massimo da cui è sceso non era un massimo di 3 anni"},
        {"key": "prezzo", "ok": deep, "label": "Capitolazione di prezzo", "short": f"−{100 * fall:.0f}%, {100 * pctl:.0f}° pct", "detail": f"−{100 * fall:.0f}% dal massimo, più profondo del {100 * pctl:.0f}% della sua storia (serve almeno −20% e il 90%)"},
        {"key": "volatilita", "ok": calm, "label": "Volatilità spenta", "short": f"{100 * v_now:.0f}% (picco {100 * v_peak:.0f}%)", "detail": f"volatilità a 20 sedute {100 * v_now:.0f}%, contro {100 * v_peak:.0f}% al picco del calo (serve metà o meno, e nel terzo più basso degli ultimi 2 anni, sotto {100 * v_low:.0f}%)"},
        {"key": "tempo", "ok": sideways, "label": "Capitolazione di tempo", "short": f"minimo {bars_since_low} sedute fa", "detail": f"minimo di {bars_since_low} sedute fa; ampiezza delle ultime 40 pari al {100 * width / (peak - trough):.0f}% del calo (serve nessun nuovo minimo in 40 sedute e al massimo il 33%)" if peak > trough else "nessun calo"},
    ]
    return {"fired": all(x["ok"] for x in conditions), "met": sum(x["ok"] for x in conditions), "fall_pct": 100 * fall, "peak": peak, "peak_date": c.index[p].strftime("%Y-%m-%d"),
            "low": trough, "low_date": low_at.strftime("%Y-%m-%d"), "conditions": conditions}


def of(market):
    """The check for one market, or None when it isn't on the list or has too little history."""
    if market not in STRONG:
        return None
    d = K.daily_ohlc(market)
    return None if d is None else check(d, market in K.CRYPTO)
