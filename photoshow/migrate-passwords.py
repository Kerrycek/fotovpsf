"""Wrap existing SHA1 verifiers in Argon2id without resetting users' passwords.

Run once as root on the named preview, after deploying verification support and
taking a consistent private checkpoint. Successful logins replace the wrapper
with a direct Argon2id password hash. No credential material is printed.
"""
import fcntl
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

state = Path('/var/lib/photoshow-preview')
accounts = state / 'generated/Conf/accounts.xml'
if os.geteuid() != 0 or not accounts.is_file():
    raise SystemExit('Root on isolated PhotoShow preview required')
with (state / 'request.lock').open('r+') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    owner = accounts.stat()
    tree = ET.parse(accounts)
    changed = 0
    for entry in tree.getroot():
        value = entry.findtext('password') or ''
        if not re.fullmatch('[0-9a-f]{40}', value):
            continue
        wrapped = subprocess.check_output([
            '/srv/photoshow-php85-tools/bin/php', '-r',
            'echo password_hash(stream_get_contents(STDIN), PASSWORD_ARGON2ID, '
            '["memory_cost"=>65536,"time_cost"=>3,"threads"=>1]);'
        ], input=value.encode()).decode()
        if not wrapped.startswith('$argon2id$'):
            raise RuntimeError('Hashing failed; state not replaced')
        entry.find('password').text = 'legacy-sha1:' + wrapped
        changed += 1
    if changed:
        fd, name = tempfile.mkstemp(prefix='.password-upgrade-', dir=accounts.parent)
        try:
            os.fchmod(fd, 0o600)
            os.fchown(fd, owner.st_uid, owner.st_gid)
            with os.fdopen(fd, 'wb') as stream:
                tree.write(stream, encoding='utf-8', xml_declaration=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, accounts)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    print(f'Protected {changed} legacy verifiers with Argon2id; passwords unchanged')
