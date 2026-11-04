#!/usr/bin/env bash
# Start the recorder and the Telegram backfill in the background. Safe to run twice: each takes a lock.
cd "$(dirname "$0")/.." || exit 1
mkdir -p data
setsid nohup python3 -u -m bzd.recorder run >> data/recorder.log 2>&1 < /dev/null &
setsid nohup python3 -u -m bzd.telegram backfill >> data/telegram-backfill.log 2>&1 < /dev/null &
echo "recorder and backfill started; check with: python3 -m bzd.recorder status"
