#!/usr/bin/env bash
# Start the services if the recorder isn't running. Safe to run any time: the Codespace doesn't always run postStartCommand on a restart.
cd "$(dirname "$0")/.." || exit 1
pgrep -f '^python3 -u -m bzd[.]recorder run$' > /dev/null && { echo "BZD: i servizi sono accesi"; exit 0; }
[ "$(id -un)" = codespace ] || { echo "BZD: i servizi sono fermi, lancia questo script come utente codespace" >&2; exit 1; }
bash scripts/start-services.sh > /dev/null
echo "BZD: i servizi erano fermi e sono ripartiti"
