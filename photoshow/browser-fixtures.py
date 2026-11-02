"""Root-only, explicitly owned accounts for browser tests on the named test VPS."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

state = Path('/var/lib/photoshow-preview')
receipt = Path('/var/backups/photoshow-port/browser-audit-fixtures.json')
accounts = state / 'generated/Conf/accounts.xml'
if os.geteuid() != 0 or not accounts.is_file():
    raise SystemExit('Root on the isolated PhotoShow test VPS required')

with (state / 'request.lock').open('a+') as lock:
    owner = accounts.stat()
    os.fchown(lock.fileno(), owner.st_uid, owner.st_gid)
    os.fchmod(lock.fileno(), 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX)
    tree = ET.parse(accounts)
    root = tree.getroot()
    if sys.argv[1] == 'create':
        if receipt.exists():
            raise SystemExit('Existing fixture receipt requires inspection/cleanup')
        run = 'Audit' + secrets.token_hex(6)
        data = {'album': run, 'accounts': {}}
        for role, groups in {'admin': ['user', 'root'], 'member': ['user'],
                             'uploader': ['user', 'uploaders']}.items():
            name = run + role
            if any(a.findtext('login') == name for a in root):
                raise SystemExit('Fixture identity collision')
            password = secrets.token_urlsafe(32)
            hashed = subprocess.check_output([
                '/srv/photoshow-php85-tools/bin/php', '-r',
                'echo password_hash(stream_get_contents(STDIN), PASSWORD_ARGON2ID);'
            ], input=password.encode()).decode()
            entry = ET.SubElement(root, 'account')
            for field, value in {'login': name, 'password': hashed, 'name': '',
                                 'email': '', 'language': '', 'key': ''}.items():
                ET.SubElement(entry, field).text = value
            group_node = ET.SubElement(entry, 'groups')
            for group in groups:
                ET.SubElement(group_node, 'group').text = group
            data['accounts'][role] = {'username': name, 'password': password}
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
    elif sys.argv[1] == 'cleanup':
        data = json.loads(receipt.read_text())
        names = {a['username'] for a in data['accounts'].values()}
        for entry in list(root):
            if entry.findtext('login') in names:
                root.remove(entry)
        # Photo removal is deliberately separate: review its own fixture tree first.
    else:
        raise SystemExit('Use create or cleanup')
    fd, temporary = tempfile.mkstemp(prefix='.browser-fixtures-', dir=accounts.parent)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, owner.st_uid, owner.st_gid)
        with os.fdopen(fd, 'wb') as stream:
            tree.write(stream, encoding='utf-8', xml_declaration=True)
        os.replace(temporary, accounts)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if sys.argv[1] == 'create':
        # Caller must capture stdout directly into a mode-0600 file, never a log.
        print(json.dumps(data))
    else:
        receipt.unlink()
        print('Removed only receipt-owned browser fixture accounts')
