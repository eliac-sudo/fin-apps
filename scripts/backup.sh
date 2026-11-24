#!/usr/bin/env bash
# Save data/ to a dated archive and check that it reads back: bash scripts/backup.sh
#   BZD_BACKUP_DIR  where archives go, default ~/bzd-backups; keep it off this disk if you can
#   BZD_BACKUP_TO   optional rsync target, such as user@host:bzd-backups
#   BZD_BACKUP_KEEP archives kept here, default 7
# .env isn't included, since an archive travels and .env holds keys: keep a copy of it in your password manager.
set -euo pipefail
cd "$(dirname "$0")/.."
dir="${BZD_BACKUP_DIR:-$HOME/bzd-backups}"
keep="${BZD_BACKUP_KEEP:-7}"
mkdir -p "$dir"
out="$dir/bzd-data-$(date -u +%Y%m%dT%H%M%SZ).tar"
# Files change while services run, so tar's "file changed" warning (exit 1) is expected. Lock files aren't needed.
tar --exclude='*.lock' --exclude='*.tmp' --warning=no-file-changed -cf "$out.part" data || [ $? -eq 1 ]
want=$(find data -type f ! -name '*.lock' ! -name '*.tmp' | wc -l)
got=$(tar -tf "$out.part" | grep -vc '/$')
# A file created or removed during the run can move the count a little, but a big drop means a broken archive.
[ "$got" -ge $((want * 99 / 100)) ] || { echo "backup failed: $got files in the archive, $want on disk" >&2; rm -f "$out.part"; exit 1; }
mv "$out.part" "$out"
echo "saved $out: $got files, $(du -h "$out" | cut -f1)"
ls -1t "$dir"/bzd-data-*.tar | tail -n +"$((keep + 1))" | xargs -r rm -f
if [ -n "${BZD_BACKUP_TO:-}" ]; then
  rsync -a --partial "$out" "$BZD_BACKUP_TO/"
  echo "copied to $BZD_BACKUP_TO"
fi
