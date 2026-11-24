"""The perpetual's price at 08:00 UTC each day, when Deribit settles options, into DIR/<coin>/px0800.json.

    .venv/bin/python scripts/research/vol_fetch_px.py DIR BTC ETH
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
OUT = Path(sys.argv[1])
for cur in sys.argv[2:]:
    out = {}
    s = int(datetime(2018, 12, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp() * 1000)
    while s < end:
        e = min(s + 150 * 86400 * 1000, end)
        u = f"https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name={cur}-PERPETUAL&start_timestamp={s}&end_timestamp={e}&resolution=60"
        r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "bzd-research"}), timeout=30))["result"]
        for t, o in zip(r["ticks"], r["open"]):
            dt = datetime.fromtimestamp(t / 1000, timezone.utc)
            if dt.hour == 8:
                out[dt.strftime("%Y-%m-%d")] = o
        s = e; time.sleep(.2)
    (OUT / cur).mkdir(parents=True, exist_ok=True); (OUT / cur / "px0800.json").write_text(json.dumps(out))
    print(cur, len(out), min(out), max(out))
