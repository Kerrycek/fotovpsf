#!/usr/bin/env python3
"""Read-only health check on the configured preview VPS; never prints secrets."""
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def command(*args):
    return subprocess.check_output(args, text=True).strip()


if subprocess.run(['systemctl', 'is-active', '--quiet', 'piwigo-backup']).returncode == 0:
    print('Consistent backup running; PHP is intentionally paused. Check again later.')
    sys.exit(0)

base = 'https://foto.crucio.cz/'


def request(path):
    req = urllib.request.Request(urllib.parse.urljoin(base, path))
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b''


for service in ('mysql', 'nginx', 'phpfpm-piwigo', 'piwigo-backup.timer'):
    assert command('systemctl', 'is-active', service) == 'active', service
assert not command('systemctl', '--failed', '--no-legend'), 'Failed systemd unit'
assert request('')[0] == 200, 'Anonymous gallery browsing unavailable'
status, payload = request('ws.php?format=json&method=pwg.users.getList')
assert status in (401, 403) or (status == 200 and json.loads(payload)['stat'] == 'fail'), 'Anonymous administration API is accessible'
status, payload = request('ws.php?format=json&method=pwg.images.getInfo&image_id=1')
assert status == 200
info = json.loads(payload)
assert info['stat'] == 'ok', 'Public image API unavailable'
assert request(info['result']['derivatives']['thumb']['url'])[0] == 200, 'Thumbnail unavailable'
for path in ('install.php', 'upgrade.php', 'image-auth.php', 'local/config/database.inc.php'):
    assert request(path)[0] == 404, 'Internal endpoint exposed: ' + path
counts = command('mariadb', '-N', 'piwigo', '-e',
    'SELECT (SELECT COUNT(*) FROM piwigo_images), '
    '(SELECT COUNT(*) FROM piwigo_categories), (SELECT COUNT(*) FROM piwigo_users)')
# This is the migrated preview baseline. Update after intentional user changes.
assert counts == '476\t42\t4', 'Unexpected preview data counts'
assert ':3306 ' not in command('ss', '-lnt'), 'MariaDB TCP listener exposed'
if '--full' in sys.argv:
    import hashlib
    manifest = json.loads(Path('/srv/foto-migration/import-manifest.json').read_text())
    assert len(manifest) == 476
    for item in manifest:
        path = Path('/var/lib/piwigo/galleries/legacy') / item['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], 'Original checksum mismatch'
    print('All 476 original SHA256 checksums match')
print('HTTPS/certificate, public browsing, admin authentication, thumbnail, internal paths, services and data counts passed')
