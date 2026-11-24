import sys, pandas as pd, numpy as np
D = sys.argv[1]
s = {}
for n in ("PUT", "WPUT", "CNDR", "BFLY", "BXM"):
    x = pd.read_csv(f"{D}/{n}.csv"); x.columns = ["date", "v"]
    x["date"] = pd.to_datetime(x.date, format="%m/%d/%Y", errors="coerce"); s[n] = x.dropna().set_index("date").v
spy = pd.read_csv("/workspaces/fin-apps/data/hist/tradfi/SPY.csv.gz", index_col="date", parse_dates=True).adjclose
s["SPY (S&P)"] = spy
df = pd.DataFrame(s).dropna()
def st(v):
    m = v.resample("ME").last().dropna(); r = m.pct_change().dropna()
    yrs = (v.index[-1] - v.index[0]).days / 365.25
    cagr = (v.iloc[-1] / v.iloc[0]) ** (1 / yrs) - 1
    dd = (v / v.cummax() - 1).min()
    worst = r.min()
    return cagr, r.std() * np.sqrt(12), dd, worst, (r.mean() * 12) / (r.std() * np.sqrt(12))
for start in (df.index[0], pd.Timestamp("2016-01-01"), pd.Timestamp("2021-01-01")):
    d = df[df.index >= start]
    print(f"\n{d.index[0].date()} -> {d.index[-1].date()}")
    print(f"{'':10} {'rend/anno':>9} {'vol':>6} {'max DD':>7} {'mese peggiore':>13} {'Sharpe~':>7}")
    for c in d.columns:
        a = st(d[c]); print(f"{c:10} {a[0]:9.1%} {a[1]:6.1%} {a[2]:7.1%} {a[3]:13.1%} {a[4]:7.2f}")
