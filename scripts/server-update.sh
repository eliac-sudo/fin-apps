#!/usr/bin/env bash
# Update the server with one command: bash scripts/server-update.sh user@host from the Codespace, or bash scripts/server-update.sh local from the development copy on the server itself.
# It sends the code as it is here, not data/ or .env, reinstalls the packages and restarts the services.
set -euo pipefail
host="${1:?usage: server-update.sh user@host}"
cd "$(dirname "$0")/.."
finish='sudo chown -R bzd:bzd /opt/bzd && sudo -u bzd /opt/bzd/.venv/bin/pip install -q -r /opt/bzd/requirements.txt && sudo cp /opt/bzd/deploy/*.service /opt/bzd/deploy/*.timer /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable -q bzd-copia && sudo systemctl restart bzd-recorder bzd-backfill bzd-wallets bzd-copia bzd-alerts bzd-vol-bot bzd-app && systemctl is-active bzd-recorder bzd-backfill bzd-wallets bzd-copia bzd-alerts bzd-vol-bot bzd-app'
excl=(--exclude data --exclude .venv --exclude .env --exclude .git --exclude __pycache__ --exclude .claude --exclude .pytest_cache --exclude .sul-server)
if [ "$host" = local ]; then
    sudo rsync -a --delete "${excl[@]}" ./ /opt/bzd/
    bash -c "$finish"; exit
fi
rsync -az --delete "${excl[@]}" --rsync-path="sudo rsync" ./ "$host:/opt/bzd/"
ssh "$host" "$finish"
