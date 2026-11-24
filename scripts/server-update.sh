#!/usr/bin/env bash
# Update the server with one command, from the Codespace: bash scripts/server-update.sh user@host
# It sends the code as it is here, not data/ or .env, reinstalls the packages and restarts the services.
set -euo pipefail
host="${1:?usage: server-update.sh user@host}"
cd "$(dirname "$0")/.."
rsync -az --delete --exclude data --exclude .venv --exclude .env --exclude .git --exclude __pycache__ --rsync-path="sudo rsync" ./ "$host:/opt/bzd/"
ssh "$host" 'sudo chown -R bzd:bzd /opt/bzd && sudo -u bzd /opt/bzd/.venv/bin/pip install -q -r /opt/bzd/requirements.txt && sudo cp /opt/bzd/deploy/*.service /opt/bzd/deploy/*.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart bzd-recorder bzd-backfill bzd-wallets bzd-alerts bzd-app && systemctl is-active bzd-recorder bzd-backfill bzd-wallets bzd-alerts bzd-app'
