"""Weekly snapshots of Deribit option trades (Monday 10:00-16:00 UTC) and daily delivery prices, BTC and ETH, 2019-2026."""
import json, sys, time, urllib.request, gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path
OUT = Path(sys.argv[1])
H = "https://history.deribit.com/api/v2/public/"
def get(url):
    for w in (1, 3, 10, 30):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bzd-research"}), timeout=30) as r:
                return json.load(r)["result"]
        except Exception as e:
            print("retry", e, flush=True); time.sleep(w)
    raise RuntimeError(url)
for cur in ("BTC", "ETH"):
    d = OUT / cur; d.mkdir(parents=True, exist_ok=True)
    # delivery prices
    rows, off = [], 0
    while True:
        r = get(f"https://www.deribit.com/api/v2/public/get_delivery_prices?index_name={cur.lower()}_usd&offset={off}&count=1000")
        rows += r["data"]; off += 1000
        if off >= r["records_total"]: break
    (d / "delivery.json").write_text(json.dumps(rows))
    t = datetime(2019, 1, 7, 10, tzinfo=timezone.utc)
    while t < datetime(2026, 11, 20, tzinfo=timezone.utc):
        f = d / f"{t:%Y-%m-%d}.json.gz"
        if not f.exists():
            s = int(t.timestamp() * 1000); e = s + 6 * 3600 * 1000
            trades = []
            while True:
                r = get(f"{H}get_last_trades_by_currency_and_time?currency={cur}&kind=option&start_timestamp={s}&end_timestamp={e}&count=1000&include_old=true&sorting=asc")
                trades += r["trades"]
                if not r.get("has_more") or not r["trades"] or len(trades) >= 5000: break
                s = r["trades"][-1]["timestamp"] + 1
            f.write_bytes(gzip.compress(json.dumps([{k: x[k] for k in ("timestamp", "instrument_name", "price", "mark_price", "iv", "index_price", "amount")} for x in trades]).encode()))
            time.sleep(0.15)
        t += timedelta(days=7)
    print(cur, "done", flush=True)
