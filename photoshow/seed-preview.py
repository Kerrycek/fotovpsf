"""One-time root-only copy and checkpoint, never a write to the original tree."""
import pathlib
import hashlib
import json
import shutil
import tarfile
import os
import time

if os.geteuid()!=0:raise SystemExit('Root required')
source=pathlib.Path('/var/www/foto.vpsfree.cz')
state=pathlib.Path('/var/lib/photoshow-preview')
private=pathlib.Path('/var/backups/photoshow-port')
if state.exists():raise SystemExit('Preview state already exists; refusing to replace it')
private.mkdir(mode=0o700,parents=True,exist_ok=True)
def manifest(path):
    result={}
    for p in sorted(path.rglob('*')):
        if p.is_file() and not p.is_symlink():
            with p.open('rb') as stream:result[str(p.relative_to(path))]=hashlib.file_digest(stream,'sha256').hexdigest()
    return result
before=manifest(source)
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
archive=private/('original-'+stamp+'.tar.gz')
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:tar.add(source,arcname='foto.vpsfree.cz')
archive.chmod(0o600)
(private/'original-manifest.json').write_text(json.dumps(before,indent=2));(private/'original-manifest.json').chmod(0o600)
state.mkdir(mode=0o700)
shutil.copytree(source/'fotky_galerie',state/'photos',symlinks=True)
shutil.copytree(source/'fotky_thumbs',state/'generated',symlinks=True)
(state/'sessions').mkdir(mode=0o700)
# Keep copied previews on loopback and disable self-registration / outbound links.
settings=state/'generated/Conf/admin_settings.ini'
lines=settings.read_text().splitlines()
lines=[l for l in lines if not l.startswith(('site_address','forcehttps','noregister','like','plusone','encode_video'))]
lines+=['site_address = "http://127.0.0.1:18085/"','noregister = "on"']
settings.write_text('\n'.join(lines)+'\n')
assert manifest(source)==before,'Original changed during copy'
photos=manifest(source/'fotky_galerie')
assert manifest(state/'photos')==photos,'Photo copy differs'
print('Original checkpoint created; preview copy verified:',len(photos),'photos')
