"""Consistent private checkpoint with an isolated restore drill; no live restore."""
from pathlib import Path
import os
import time
import json
import hashlib
import subprocess
import tarfile
import tempfile

if os.geteuid()!=0:raise SystemExit('Root required')
state=Path('/var/lib/photoshow-preview').resolve()
private=Path('/var/backups/photoshow-port')
checkpoint=private/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
checkpoint.mkdir(mode=0o700)
def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def manifest(path):
    result={}
    for component in ['photos','generated']:
        for file in sorted((path/component).rglob('*')):
            if file.is_symlink():raise RuntimeError('Unexpected state symlink; inspect before checkpoint')
            if file.is_file():result[str(file.relative_to(path))]=digest(file)
    return result
was_active=subprocess.run(['systemctl','is-active','--quiet','photoshow-preview']).returncode==0
try:
    if was_active:subprocess.run(['systemctl','stop','photoshow-preview'],check=True)
    expected=manifest(state)
    (checkpoint/'manifest.json').write_text(json.dumps(expected,indent=2))
    with tarfile.open(checkpoint/'state.tar.gz','w:gz',compresslevel=1) as tar:
        for component in ['photos','generated']:tar.add(state/component,arcname='state/'+component)
    for file in checkpoint.iterdir():file.chmod(0o600)
    (checkpoint/'SHA256SUMS').write_text(''.join(digest(checkpoint/name)+'  '+name+'\n' for name in ['manifest.json','state.tar.gz']))
    (checkpoint/'SHA256SUMS').chmod(0o600)
    for line in (checkpoint/'SHA256SUMS').read_text().splitlines():
        expected_hash,name=line.split('  ')
        assert digest(checkpoint/name)==expected_hash,'Checkpoint checksum mismatch'
    with tempfile.TemporaryDirectory(prefix='restore-',dir=private) as temporary:
        with tarfile.open(checkpoint/'state.tar.gz','r:gz') as tar:tar.extractall(temporary,filter='data')
        assert manifest(Path(temporary)/'state')==expected,'Restored state differs'
    print('PASS consistent preview checkpoint and isolated restore;',len([p for p in expected if p.startswith('photos/')]),'original photographs')
finally:
    if was_active:subprocess.run(['systemctl','start','photoshow-preview'],check=True)
