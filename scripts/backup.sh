#!/usr/bin/env bash
# A consistent backup includes the MyISAM tables used by upstream Piwigo.
set -euo pipefail
umask 077
if [[ $(id -u) != 0 ]]; then
  echo 'Run as root on the gallery server' >&2
  exit 1
fi
backup_root=${1:-/srv/foto-migration/backups}
backup_dir="$backup_root/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
chmod 700 "$backup_root" "$backup_dir"
was_active=0
if systemctl is-active --quiet phpfpm-piwigo; then
  was_active=1
  systemctl stop phpfpm-piwigo
fi
finish() {
  if [[ $was_active == 1 ]]; then systemctl start phpfpm-piwigo; fi
}
trap finish EXIT
mariadb-dump --lock-all-tables --hex-blob piwigo > "$backup_dir/piwigo.sql"
tar -C /var/lib --exclude=piwigo/app --exclude=piwigo/sessions -czpf "$backup_dir/piwigo-state.tar.gz" piwigo
if [[ -f /root/fotovpsf-access.json ]]; then
  cp -p /root/fotovpsf-access.json "$backup_dir/access.json"
fi
if [[ -d /var/lib/piwigo-preview ]]; then
  tar -C /var/lib -czpf "$backup_dir/preview-gate.tar.gz" piwigo-preview
fi
git -C /srv/fotovpsf rev-parse HEAD > "$backup_dir/source-revision.txt"
sha256sum "$backup_dir"/* > "$backup_dir/SHA256SUMS"
echo "$backup_dir"
