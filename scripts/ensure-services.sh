#!/usr/bin/env bash
# Start the services if the recorder isn't running. Safe to run any time: the Codespace doesn't always run postStartCommand on a restart.
cd "$(dirname "$0")/.." || exit 1
if [ -s .sul-server ]; then
    bash scripts/start-services.sh
    echo "BZD: i servizi girano sul server $(cat .sul-server); qui solo il tunnel per l'app"; exit 0
fi
# The Deribit bot can stop on its own; with keys in .env it is restarted here too, since a sold strangle needs its hedge.
bot_down() { grep -q '^DERIBIT_CLIENT_ID=.' .env 2>/dev/null && ! pgrep -f '^.venv/bin/python -u -m bzd[.]vol_bot run$' > /dev/null; }
if pgrep -f '^python3 -u -m bzd[.]recorder run$' > /dev/null; then
    bot_down || { echo "BZD: i servizi sono accesi"; exit 0; }
    [ "$(id -un)" = codespace ] || { echo "BZD: il bot Deribit è fermo, lancia questo script come utente codespace" >&2; exit 1; }
    setsid nohup .venv/bin/python -u -m bzd.vol_bot run >> data/vol_bot.log 2>&1 < /dev/null &
    echo "BZD: il bot Deribit era fermo ed è ripartito"; exit 0
fi
[ "$(id -un)" = codespace ] || { echo "BZD: i servizi sono fermi, lancia questo script come utente codespace" >&2; exit 1; }
bash scripts/start-services.sh > /dev/null
echo "BZD: i servizi erano fermi e sono ripartiti"
