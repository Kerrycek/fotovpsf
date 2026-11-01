"""Read-only verification of all originals and their PHP-generated views."""
import pathlib
import hashlib
import json
import urllib.request
import urllib.parse
import urllib.error
import concurrent.futures

state=pathlib.Path('/var/lib/photoshow-preview')
original=pathlib.Path('/var/www/foto.vpsfree.cz')
baseline=json.loads(pathlib.Path('/var/backups/photoshow-port/original-manifest.json').read_text())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for name,expected in baseline.items():
    if sha(original/name)!=expected:raise AssertionError('Original source was changed')
photos={name.removeprefix('fotky_galerie/'):value for name,value in baseline.items() if name.startswith('fotky_galerie/')}
assert len(photos)==476,'Original photo baseline changed; inspect intentional user changes'
def verify(item):
    relative,expected=item
    assert sha(state/'photos'/relative)==expected,'Copied original differs'
    query=urllib.parse.urlencode({'f':relative})
    for kind in ['Big','Thb']:
        with urllib.request.urlopen('http://127.0.0.1:18085/?t='+kind+'&'+query,timeout=80) as r:
            body=r.read();assert r.status==200 and body[:2]==b'\xff\xd8','Image request failed'
            if kind=='Big':assert hashlib.sha256(body).hexdigest()==expected,'Served original differs'
            else:assert len(body)<500000,'Thumbnail unexpectedly served a full original'
    with urllib.request.urlopen('http://127.0.0.1:18085/?j=Inf&'+query,timeout=80) as r:
        assert r.status==200 and b'Warning:' not in r.read(),'Metadata view failed'
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(verify,photos.items()))
print('PASS all 476 originals: source/copy/HTTP SHA256, thumbnails and metadata; original code/config unchanged')
