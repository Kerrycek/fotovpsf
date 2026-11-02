"""Root-only, explicitly owned accounts for browser tests on the named test VPS."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
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
        expected = sys.argv[2] if len(sys.argv) == 3 else ''
        if not re.fullmatch('[0-9a-f]{64}', expected):
            raise SystemExit('Cleanup requires the known synthetic image SHA256')
        pattern = re.compile(re.escape(data['album']) + r'[0-9]{13}')
        folders = [p for p in (state / 'photos').iterdir() if pattern.fullmatch(p.name)]
        for folder in folders:
            for file in folder.rglob('*'):
                if file.is_symlink():
                    raise SystemExit('Unexpected symlink: cleanup refused')
                if file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                    raise SystemExit('Unexpected photo content: cleanup refused')
        names = {a['username'] for a in data['accounts'].values()}
        for entry in list(root):
            if entry.findtext('login') in names:
                root.remove(entry)
        for folder in folders:
            shutil.rmtree(folder)
            metadata = state / 'generated/Thumbs' / folder.name
            if metadata.exists():
                shutil.rmtree(metadata)
        # Remove only receipt-owned fixture comments/shares, preserving real entries.
        for filename, tag in [('comments.xml', 'path'), ('guest_tokens.xml', 'path')]:
            target = state / 'generated/Conf' / filename
            if not target.exists():
                continue
            metadata_tree = ET.parse(target)
            for entry in list(metadata_tree.getroot()):
                if pattern.fullmatch((entry.findtext(tag) or '').split('/')[0]):
                    metadata_tree.getroot().remove(entry)
            info = target.stat()
            fd, temporary = tempfile.mkstemp(prefix='.browser-cleanup-', dir=target.parent)
            try:
                os.fchmod(fd, 0o600); os.fchown(fd, info.st_uid, info.st_gid)
                with os.fdopen(fd, 'wb') as stream:
                    metadata_tree.write(stream, encoding='utf-8', xml_declaration=True)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
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
        print(f'Removed only receipt-owned browser fixtures ({len(folders)} albums)')
