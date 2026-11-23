#!/usr/bin/env bash
# Start the recorder, the Telegram backfill, the wallet tracker, the alerts and the app in the background. Safe to run twice: each takes a lock.
cd "$(dirname "$0")/.." || exit 1
mkdir -p data
setsid nohup python3 -u -m bzd.recorder run >> data/recorder.log 2>&1 < /dev/null &
setsid nohup python3 -u -m bzd.telegram backfill >> data/telegram-backfill.log 2>&1 < /dev/null &
setsid nohup python3 -u -m bzd.wallets run >> data/wallets.log 2>&1 < /dev/null &
setsid nohup .venv/bin/python -u -m bzd.alerts run >> data/alerts.log 2>&1 < /dev/null &
setsid nohup .venv/bin/python -u -m bzd.app >> data/app.log 2>&1 < /dev/null &
# The Deribit bot only once its keys are in .env (testnet unless .env says otherwise, docs/BOT_DERIBIT.md)
if grep -q '^DERIBIT_CLIENT_ID=.' .env 2>/dev/null; then
    setsid nohup .venv/bin/python -u -m bzd.vol_bot run >> data/vol_bot.log 2>&1 < /dev/null &
fi
echo "recorder, backfill, wallets, alerts and app started (and the Deribit bot if it has keys); check with: python3 -m bzd.recorder status"
