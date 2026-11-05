#!/usr/bin/env bash
# Set up BZD on a fresh Ubuntu server: run once as root, from a copy of this repository.
#   sudo bash scripts/server-install.sh
# It installs packages, creates the bzd user, puts the code in /opt/bzd and installs the services without starting them.
# Start them only after the Codespace's bot has stopped, because the Telegram bot must run in one place (docs/SERVER.md).
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
src="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update -q
apt-get install -y -q python3 python3-venv rsync
id bzd > /dev/null 2>&1 || useradd --system --create-home --home-dir /home/bzd --shell /usr/sbin/nologin bzd
mkdir -p /opt/bzd
[ "$src" = /opt/bzd ] || rsync -a --exclude data --exclude .venv "$src/" /opt/bzd/
mkdir -p /opt/bzd/data
python3 -m venv /opt/bzd/.venv
/opt/bzd/.venv/bin/pip install -q -r /opt/bzd/requirements.txt
chown -R bzd:bzd /opt/bzd
cp /opt/bzd/deploy/*.service /opt/bzd/deploy/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable bzd-recorder bzd-backfill bzd-alerts bzd-app bzd-backup.timer
echo "Installed. Copy data/ and .env, then: sudo systemctl start bzd-recorder bzd-backfill bzd-alerts bzd-app bzd-backup.timer"
