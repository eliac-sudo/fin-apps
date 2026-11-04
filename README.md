# BZD

Research tools for short-term trading setups across crypto, equities, commodities, FX and bonds. Plan: `ROADMAP.md`. Framework: `bzd-agenti-framework.md`.

Not financial advice.

## Recorder

Archives data that has no free history, so gaps can't be filled later. It needs Python 3.10+ and nothing else.

```
cp .env.example .env                 # add your FRED key
python -m bzd.recorder once hl_      # test one group of jobs
python -m bzd.recorder run           # record until stopped
python -m bzd.recorder status        # health; exits 1 if a job is late
python -m unittest discover tests    # tests
```

Data goes to `data/`, or to `BZD_DATA` if set:

- `raw/<job>/<date>/` holds gzipped responses exactly as received. A response identical to the last one isn't stored again.
- `manifest/<date>.jsonl` logs every request with time, status, SHA-256 and path. Failures are logged too, so gaps are visible.

Jobs and request spacing are in `bzd/jobs.py`.

## Moving to another machine

Stop the recorder, copy `data/` and `.env`, then start it on the new machine. Run only one recorder per data directory. Add a process manager such as systemd there so it restarts after crashes and reboots.
