"""Implied vol at 30 days against the vol realized over the next 30 days: BTC and ETH from Deribit DVOL, the S&P from VIX.

    .venv/bin/python scripts/research/vol_vrp.py

Exploration, not a test (docs/BOT_DERIBIT_STORICO.md). Reads the saved history in data/hist.
"""
from pathlib import Path

import numpy as np
import pandas as pd

H = str(Path(__file__).resolve().parents[2] / "data" / "hist") + "/"
def stats(name, iv, px, n, ann):
    r=np.log(px).diff()
    rv=(r.rolling(n).std().shift(-n))*np.sqrt(ann)*100   # realized over next n obs
    d=pd.DataFrame({'iv':iv,'rv':rv}).dropna()
    sp=d.iv-d.rv
    pnl=(d.iv**2-d.rv**2)/d.iv**2  # var-swap seller, in units of strike variance
    print(f"{name:5} {d.index[0].date()}..{d.index[-1].date()} n={len(d)} | IV med {d.iv.median():.0f} RV med {d.rv.median():.0f} | IV>RV {100*(sp>0).mean():.0f}% | spread med {sp.median():+.1f} mean {sp.mean():+.1f} pt | varswap pnl mean {pnl.mean():+.2f} med {pnl.median():+.2f} p5 {pnl.quantile(.05):+.2f} worst {pnl.min():+.2f} | mean/sd {pnl.mean()/pnl.std():.2f}")
for c in ['BTC','ETH']:
    v=pd.read_csv(H+f'crypto/{c}_dvol_1d.csv.gz'); v.index=pd.to_datetime(v.t).dt.tz_localize(None).dt.normalize()
    p=pd.read_csv(H+f'crypto/{c}_candles_1d.csv.gz'); p.index=pd.to_datetime(p.t).dt.tz_localize(None).dt.normalize()
    j=pd.concat([v.close.rename('iv'),p.close.rename('px')],axis=1).dropna()
    stats(c, j.iv, j.px, 30, 365)
v=pd.read_csv(H+'vol/VIX.csv.gz',index_col='date',parse_dates=True).close
s=pd.read_csv(H+'tradfi/SPY.csv.gz',index_col='date',parse_dates=True).adjclose
j=pd.concat([v.rename('iv'),s.rename('px')],axis=1).dropna()
stats('SPX', j.iv, j.px, 21, 252)
j2=j[j.index>='2021-03-24']; stats('SPX21', j2.iv, j2.px, 21, 252)
