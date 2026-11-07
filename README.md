# BZD

Research tools for short-term trading setups across crypto, equities, commodities, FX and bonds: a recorder, a read-only desktop app and Telegram alerts. It holds no trading keys and places no orders. Not financial advice.

Where it stands: `docs/STATO.md`. Plan: `ROADMAP.md`. How each part works, with links into the code: `docs/wiki/` (the Motore tab in the app). The first design is in `docs/archivio/`.

## Setup

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                 # add your FRED key
python -m unittest discover tests    # tests
```

The recorder needs Python 3.10+ and nothing else; everything else uses `.venv`.

## Services

| Service | Command |
|---|---|
| Recorder | `python3 -u -m bzd.recorder run` |
| Telegram history | `python3 -u -m bzd.telegram backfill` |
| Hyperliquid wallets | `python3 -u -m bzd.wallets run` |
| Alerts and bot | `.venv/bin/python -u -m bzd.alerts run` |
| App | `.venv/bin/python -u -m bzd.app` |

`scripts/start-services.sh` starts all five in the background; each takes a lock, so running it twice is safe. In the Codespace, `.devcontainer/devcontainer.json` installs the packages on creation and runs that script on every start, but the start command doesn't always run. After a restart run `bash scripts/ensure-services.sh` as the `codespace` user: it starts the services only if the recorder is down. They stop whenever the Codespace pauses, and gaps in data with no history can't be filled.

Claude runs as root, without GitHub credentials. Run `gl` in a normal VS Code terminal to let the running session push: it copies that terminal's token to a file only root can read. `gl off` deletes it. Run `gl` again if the token expires or after a rebuild.

## App

`python -m bzd.app` serves the app on port 8787. In a Codespace, open it from the Ports tab and keep the port private. It reads saved data, holds no keys and places no orders. Its only write is `data/sentiment/days.json`, which keeps daily word counts after the raw social files are deleted.

- **Oggi:** strength per market and class, from 0 to 100 against its own past (oversold, below normal, normal, above normal, overbought; `bzd/thermo.py`). Momentum per asset, «scende forte» or «sale forte», on 4h, daily, weekly, monthly and 12-month views, from 70% indicators and 30% sentiment (`bzd/zones.py`, `docs/ZONE_MOMENTUM.md`); after it, the price tended to keep going the same way for 10 sessions, about 0.6% more than a random day, on 50 markets the program never used (test v4). BYZ, capitulation (`bzd/capitulation.py`): a rare, untested signal for a strong market that fell a lot, then went quiet and sideways for weeks.
- **Ticker page:** clicking any asset opens a page that sums up what each tab says about it.
- **Opzioni:** options cheap or dear against a volatility forecast, with gamma exposure (`docs/OPZIONI_MODELLI.md`).
- **Analisi tecnica:** charts with levels drawn by code, and a search over any Hyperliquid perpetual or Yahoo ticker.
- **Sentiment:** fear and euphoria word counts over 24 hours and 7 days, past mood extremes on the price chart, Google's public trending searches (`bzd/sentiment.py`).
- **Chi compra:** how long retail and the big players are against their last 3 years, and profitable Hyperliquid wallets (`docs/CHI_COMPRA.md`).
- **Alert, Piano, Test, Motore:** the alerts with their levels, the position calculator, every test with its hypotheses and results, and the wiki.

The Layout button switches between four looks: BZD Neon, Arasaka, Militech and Kang Tao.

## Alerts

`python -m bzd.alerts` runs the frozen setups on fresh data and logs every alert to `data/alerts/log.jsonl`. With `BZD_ALERTS_TELEGRAM=on` in `.env`, each trigger also goes to Telegram as insight: what moved, whether the price is cheap or dear against its own last year, what the B3 test said, and the options context. Entries, stops and targets are logged but not sent: they belong in the app.

Strong price moves (`bzd/moves.py`) go out within about 15 minutes and are logged to `data/alerts/moves.jsonl`: large against the market's own volatility, on the Hyperliquid snapshots, not tested as a signal. RSI resets (`bzd/technicals.py`) go out on monthly, weekly and daily bars: the RSI back at an extreme while the slow trend holds. They aren't tested either, and 4h stays in the app. Once a day the strength digest goes out too (`python -m bzd.thermo` prints it).

To connect Telegram:

1. Message @BotFather, send `/newbot`, and put the token in `.env` as `TELEGRAM_BOT_TOKEN=`.
2. Send your new bot any message, run `.venv/bin/python -m bzd.alerts chatid`, and put the number in `.env` as `TELEGRAM_CHAT_ID=`.
3. Run `.venv/bin/python -m bzd.alerts test`. The running service reads `.env` again on its own.

## Plan

`python -m bzd.plan BTC 5000`, or `/piano BTC 5000` to the bot, gives the position size, leverage, stop, target and time exit for a chosen risk (`docs/A3_REGOLE.md`). You place the orders by hand. It reads public prices only and logs each plan to `data/alerts/plans.jsonl`.

## Agents

Alerts with score 1 or more get a review from `bzd/agents.py`: it reads recent news and social, gives a view with citations, and code discards any quote or number it can't trace. A view never changes the numbers or blocks an alert. It needs `ANTHROPIC_API_KEY` in `.env`.

```
.venv/bin/python -m bzd.agents costi    # what has been spent
.venv/bin/python -m bzd.agents prova    # review the latest alert; costs money
```

Automatic reviews are off unless `BZD_AGENTS=on` is in `.env`. `prova` always runs, because you asked for it by hand. Reviews stop at `BZD_LLM_BUDGET_USD` per calendar month (default 5), and alerts carry on without them. `BZD_MODEL` sets the model (default `claude-opus-5-5`). Reviews are logged to `data/agents/reviews.jsonl`, with the raw file and hash of every cited text.

## Recorder data

It archives data that has no free history, so gaps can't be filled later. Data goes to `data/`, or to `BZD_DATA` if set:

- `raw/<job>/<date>/` holds gzipped responses exactly as received. A response identical to the last one isn't stored again.
- `manifest/<date>.jsonl` logs every request with time, status, SHA-256 and path. Failures are logged too, so gaps are visible.

```
python -m bzd.recorder once hl_      # test one group of jobs
python -m bzd.recorder status        # health; exits 1 if a job is late
```

Jobs and request spacing are in `bzd/jobs.py`. Reddit and most Telegram responses are deleted after 35 days (`SOCIAL_KEEP_DAYS`), because they can be fetched again. Bluesky, Mastodon, 4chan, Telegram liquidation channels and all other data are kept. The recorder checks at start and once a day. Manifest lines stay, so a path in an old line may no longer exist.

## History, research and tests

```
.venv/bin/python -m bzd.history get        # all markets; finished series are skipped
.venv/bin/python -m bzd.history coverage   # dates, gaps and quality per series
.venv/bin/python -m bzd.history get positions  # who holds what, for the Chi compra tab; about 30 minutes
.venv/bin/python -m bzd.setups events      # setup events and counts; computes no forward returns
.venv/bin/python -m bzd.exits run          # exit rules, calibration period only
python3 -m bzd.telegram status             # Telegram history progress
.venv/bin/python -m bzd.literature run     # paper catalogue from OpenAlex and arXiv, written to docs/CATALOGO.md
.venv/bin/python -m bzd.literature check "a title"  # is this paper real?
.venv/bin/python -m bzd.research verifica  # do the papers the Gemini report cites exist? free
.venv/bin/python -m bzd.research stima     # cost of the research agents before any paid call
.venv/bin/python -m bzd.research leggi --paga   # notes on abstracts, checked in code (paid)
.venv/bin/python -m bzd.research idee --paga    # untested setup drafts for a pre-registration (paid)
.venv/bin/python -m bzd.wiki lint          # every citation in the wiki points to something real
```

Each historical test (`bzd/b3.py`, `bzd/v2.py` to `bzd/v5.py`) was pre-registered in `docs/PREREGISTRAZIONE_v*.md` and runs once; its results are frozen in `config/validation_*.json`.

## Moving to another machine

Stop the recorder, copy `data/` and `.env`, then start it on the new machine. Run only one recorder per data directory. `docs/SERVER.md` has the server kit, backups and one-command updates, with systemd units in `deploy/`.
