import json, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
OUT = Path(sys.argv[1])
for cur in ("BTC", "ETH"):
    out = {}
    s = int(datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    end = int(datetime(2026, 11, 24, tzinfo=timezone.utc).timestamp() * 1000)
    while s < end:
        e = min(s + 30 * 86400 * 1000, end)
        u = f"https://www.deribit.com/api/v2/public/get_funding_rate_history?instrument_name={cur}-PERPETUAL&start_timestamp={s}&end_timestamp={e}"
        for w in (1, 5, 20):
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "bzd-research"}), timeout=30))["result"]; break
            except Exception as ex:
                time.sleep(w)
        for x in r:
            out[str(x["timestamp"])] = x["interest_1h"]
        s = e; time.sleep(.15)
    (OUT / cur / "funding_1h.json").write_text(json.dumps(out))
    ts = sorted(int(k) for k in out)
    print(cur, len(out), datetime.fromtimestamp(ts[0]/1000, timezone.utc).date(), "mean 1h", sum(out.values())/len(out), flush=True)
