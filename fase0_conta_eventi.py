"""Count setup events only. Deliberately computes NO forward returns (keeps the test sample clean)."""
import json,os,sys,time,urllib.request as u
from concurrent.futures import ThreadPoolExecutor as TP
import numpy as np,pandas as pd
C=sys.argv[1]; H={"User-Agent":"Mozilla/5.0 (compatible; bzd-research/0.1)"}
A=["BTC","ETH","SOL","BNB","XRP","DOGE","ADA","AVAX","LINK"]
def get(url,tries=5):
    for i in range(tries):
        try: return json.load(u.urlopen(u.Request(url,headers=H),timeout=30))
        except Exception as e: err=e; time.sleep(1.5*(i+1))
    raise err
def cached(n,fn):
    p=f"{C}/{n}.pkl"
    if os.path.exists(p): return pd.read_pickle(p)
    d=fn(); d.to_pickle(p); return d
START=int(pd.Timestamp("2019-09-01",tz="UTC").timestamp()*1000); NOW=int(time.time()*1000)
def kl(a):
    r=[];s=START
    while s<NOW:
        x=get(f"https://fapi.binance.com/fapi/v1/klines?symbol={a}USDT&interval=4h&limit=1500&startTime={s}")
        if not x: break
        r+=x; s=x[-1][0]+1
        if len(x)<1500: break
    d=pd.DataFrame([(k[0],float(k[4]),float(k[2]),float(k[3]),float(k[7])) for k in r],columns="t c h l v".split())
    d["t"]=pd.to_datetime(d.t,unit="ms",utc=True); return d.set_index("t")
def fu(a):
    r=[];s=START
    while s<NOW:
        x=get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={a}USDT&limit=1000&startTime={s}")
        if not x: break
        r+=x; s=x[-1]["fundingTime"]+1
        if len(x)<1000: break
    d=pd.DataFrame({"t":[k["fundingTime"] for k in r],"f":[float(k["fundingRate"]) for k in r]})
    d["t"]=pd.to_datetime(d.t,unit="ms",utc=True); return d.set_index("t").f
def oi(a):
    r=[];cur=""
    while True:
        x=get(f"https://api.bybit.com/v5/market/open-interest?category=linear&symbol={a}USDT&intervalTime=4h&limit=200&startTime={START}&endTime={NOW}"+(f"&cursor={u.quote(cur,safe='')}" if cur else ""))
        l=x["result"]["list"]; r+=l; cur=x["result"].get("nextPageCursor")
        if not l or not cur: break
    d=pd.DataFrame({"t":[int(k["timestamp"]) for k in r],"oi":[float(k["openInterest"]) for k in r]}).drop_duplicates("t").sort_values("t")
    d["t"]=pd.to_datetime(d.t,unit="ms",utc=True); return d.set_index("t").oi
def load(a):
    k=cached(f"k_{a}",lambda:kl(a)); f=cached(f"f_{a}",lambda:fu(a)); o=cached(f"o_{a}",lambda:oi(a)); return a,k,f,o
def feats(k,f,o):
    # every rolling stat is shifted: a bar is never compared with itself or the future
    d=k.copy(); d=d[~d.index.duplicated()]
    r=np.log(d.c).diff(); d["z"]=r/r.rolling(180).std().shift(1)
    lv=np.log(d.v.replace(0,np.nan)); d["vz"]=(lv-lv.rolling(180).mean().shift(1))/lv.rolling(180).std().shift(1)
    d["vfall"]=d.v.shift(-1)<d.v   # confirmation: usable only at close of the NEXT bar
    d["f"]=f.reindex(d.index,method="ffill")
    d["f7"]=f.rolling(21).mean().reindex(d.index,method="ffill")
    d["fneg3"]=(f<0).rolling(9).sum().reindex(d.index,method="ffill")==9
    d["oi"]=o.reindex(d.index,method="ffill",limit=2)
    d["doi"]=d.oi.pct_change(6,fill_method=None); d["p10"]=d.doi.expanding(180).quantile(.1).shift(1)
    d["oi7"]=d.oi.pct_change(42,fill_method=None)>0
    w=(d.h.rolling(42).max()-d.l.rolling(42).min())/d.c; d["tight"]=w.shift(1)<w.expanding(180).median().shift(2)
    return d
def events(m,hrs=24):
    ix=[];last=None
    for t in m[m].index:
        if last is None or (t-last)>=pd.Timedelta(hours=hrs): ix.append(t);last=t
    return pd.DatetimeIndex(ix)
def clusters(idx,hrs=24):
    s=sorted(idx);n=0;last=None
    for t in s:
        if last is None or (t-last)>pd.Timedelta(hours=hrs): n+=1;last=t
    return n
with TP(4) as p: data=list(p.map(load,A))
for a,k,f,o in data: print(f"{a}: candles from {k.index[0].date()} n={len(k)} | funding from {f.index[0].date()} | OI from {o.index[0].date()}")
P={};Q={};O={}
for a,k,f,o in data:
    d=feats(k,f,o)
    pr=d.z<=-3; s=(d.doi<=d.p10).astype(int)+(d.f<=0).astype(int)+((d.vz>=3)&d.vfall).astype(int)
    for n in (0,1,2,3): P.setdefault(n,[]).append(events(pr&(s>=n)))
    pq=(d.z>=2)&d.tight; s2=((d.f7<0)&d.oi7).astype(int)+d.fneg3.astype(int)+(d.vz>0).astype(int)
    for n in (0,1,2,3): Q.setdefault(n,[]).append(events(pq&(s2>=n)))
    O.setdefault("btc" if a=="BTC" else "x",[])
def show(name,D):
    print(f"\n{name}: conditions met beyond price | asset-events | independent clusters (24h merge) | split <=2024 / 2025+ clusters")
    for n,l in D.items():
        al=l; ev=sum(len(x) for x in al); c=np.concatenate([x.values for x in al]) if ev else []
        idx=pd.DatetimeIndex(c,tz="UTC") if ev else pd.DatetimeIndex([],tz="UTC")
        cut=pd.Timestamp("2025-01-01",tz="UTC")
        print(f"  >={n}: {ev:5d} | {clusters(idx):4d} | {clusters(idx[idx<cut]):4d} / {clusters(idx[idx>=cut]):4d}")
show("PANIC (4h z<=-3)",P); show("SQUEEZE (4h z>=+2 after tight range)",Q)
