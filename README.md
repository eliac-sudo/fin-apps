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

Reddit and most Telegram responses are deleted after 35 days (`SOCIAL_KEEP_DAYS`), because they can be fetched again. Bluesky, Mastodon, 4chan, Telegram liquidation channels and all other data are kept. The recorder checks at start and once a day. Manifest lines stay, so a path in an old line may no longer exist.

## History and event counts

These need the packages in `requirements.txt`.

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m bzd.history get        # all markets; finished series are skipped
.venv/bin/python -m bzd.history coverage   # dates, gaps and quality per series
.venv/bin/python -m bzd.setups events      # setup events and counts; computes no forward returns
.venv/bin/python -m bzd.exits run          # exit rules, calibration period only
python3 -m bzd.telegram backfill           # liquidation and whale channels; resumable
python3 -m bzd.telegram status
```

## Codespace

`.devcontainer/devcontainer.json` installs Claude Code and the Python packages on creation, and starts the recorder and backfill with `scripts/start-services.sh` on every start. They stop whenever the Codespace pauses, and those gaps can't be filled for data with no history. Claude runs as root, without GitHub credentials. Run `gl` in a normal VS Code terminal to let the running session push: it copies that terminal's token to a file only root can read. `gl off` deletes it. Run `gl` again if the token expires or after a rebuild.

## Moving to another machine

Stop the recorder, copy `data/` and `.env`, then start it on the new machine. Run only one recorder per data directory. Add a process manager such as systemd there so it restarts after crashes and reboots.
