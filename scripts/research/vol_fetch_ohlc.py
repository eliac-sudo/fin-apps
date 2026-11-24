"""Hourly OHLC of the BTC perpetual on Deribit, 2019-2026, into DIR/BTC/perp_1h.json.

    .venv/bin/python scripts/research/vol_fetch_ohlc.py DIR
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(sys.argv[1]) / "BTC"
OUT.mkdir(parents=True, exist_ok=True)
rows = {}
s = int(datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
end = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp() * 1000)
while s < end:
    e = min(s + 150 * 86400 * 1000, end)
    u = f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name=BTC-PERPETUAL&start_timestamp={s}&end_timestamp={e}&resolution=60"
    r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "bzd-research"}), timeout=30))["result"]
    for t, o, h, l, c in zip(r["ticks"], r["open"], r["high"], r["low"], r["close"]):
        rows[t] = (o, h, l, c)
    s = e
    time.sleep(.2)
ts = sorted(rows)
(OUT / "perp_1h.json").write_text(json.dumps([[t, *rows[t]] for t in ts]))
print(len(ts), datetime.fromtimestamp(ts[0] / 1000, timezone.utc), datetime.fromtimestamp(ts[-1] / 1000, timezone.utc))
