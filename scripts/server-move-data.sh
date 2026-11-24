#!/usr/bin/env bash
# Copy data/ and .env to the server: bash scripts/server-move-data.sh user@host
# Safe to run twice. Run it once with the services on, then stop them here, run it again and start them there, so the gap stays small.
set -euo pipefail
host="${1:?usage: server-move-data.sh user@host}"
cd "$(dirname "$0")/.."
rsync -az --partial --exclude '*.lock' --rsync-path="sudo rsync" data/ "$host:/opt/bzd/data/"
rsync -z --chmod=600 --rsync-path="sudo rsync" .env "$host:/opt/bzd/.env"
ssh "$host" 'sudo chown -R bzd:bzd /opt/bzd/data /opt/bzd/.env && sudo chmod 600 /opt/bzd/.env'
