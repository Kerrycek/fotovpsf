#!/usr/bin/env python3
"""New-VPS-only auth regression, using a disposable normal user and API key."""
import concurrent.futures
import hashlib
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from client import Session, load_access

access = load_access()
admin = Session()
admin.login(access['admin_username'], access['admin_password'])
name = 'qa-auth-'+secrets.token_hex(6)
password = secrets.token_urlsafe(70)+'čřž"\\'
uid = None
key = None
ui = Session()

# All requests below originate on this VPS. Clear ONLY its own test-source
# bucket, never the operator's Mac or other visitors' throttle state.
with socket.create_connection(('foto.crucio.cz', 443), timeout=10) as connection:
    address = ipaddress.ip_address(connection.getsockname()[0])
if address.version == 6 and address.ipv4_mapped: address = address.ipv4_mapped
packed = address.packed[:8] if address.version == 6 else address.packed
bucket = Path('/var/lib/piwigo/auth-throttle')/(hashlib.sha256(packed).hexdigest()+'.json')

def anonymous_failure(index=0):
    client = Session()  # changing cookies and usernames must not bypass limits
    fields = {'method':'pwg.session.login', 'username':'qa-absent-'+secrets.token_hex(10), 'password':'synthetic-wrong-password'}
    return client.raw('ws.php?format=json', urllib.parse.urlencode(fields).encode(),
                      {'X-Forwarded-For':'192.0.2.'+str(index+1)})

try:
    uid = admin.api('pwg.users.add', {'username':name, 'password':password, 'password_confirm':password})['users'][0]['id']
    hashed = subprocess.check_output(['mariadb','-N','piwigo','-e',f'SELECT password FROM piwigo_users WHERE id={int(uid)}'], text=True).strip()
    assert hashed.startswith('$argon2id$'), 'New account did not use Argon2id'
    member = Session()
    member.login(name, password)
    # A real HTML form login with the same long Unicode/quoted password.
    assert ui.raw('identification.php')[0] == 200
    status, _, _ = ui.raw('identification.php', urllib.parse.urlencode({'login':'1','username':name,'password':password,'redirect':'/'}).encode())
    assert status == 200 and ui.api('pwg.session.getStatus')['username'] == name, 'HTML form login failed'
    ui.token = ui.api('pwg.session.getStatus')['pwg_token']
    created_key = ui.api('pwg.users.api_key.create', {'key_name':'Disposable auth regression','duration':1})
    # The response contains a secret: keep it only in memory, never print it.
    assert isinstance(created_key, dict) and 'auth_key' in created_key and 'apikey_secret' in created_key, 'API key response missing'
    key = created_key['auth_key']+':'+created_key['apikey_secret']
    keyed = Session()
    for _ in range(8):
        status, _, payload = keyed.raw('ws.php?format=json&method=pwg.session.getStatus', headers={'X-PIWIGO-API':key})
        assert status == 200 and json.loads(payload)['result']['username'] == name, 'Repeated valid key authentication failed'
    print('Long Unicode passwords, native form/API logins, Argon2id account and repeated API-key authentication passed')

    bucket.unlink(missing_ok=True)
    # Concurrent attempts prove that the shared file lock cannot overspend.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(anonymous_failure, range(8)))
    admitted = [r for r in responses if r[0] == 200]
    blocked = [r for r in responses if r[0] == 429]
    assert len(admitted) == 5 and len(blocked) == 3, 'Parallel login budget incorrect'
    assert all(json.loads(r[2]).get('stat') == 'fail' for r in admitted)
    assert all(json.loads(r[2]).get('err') == 429 for r in blocked)
    # Both form and API keys must share the exhausted password-login budget.
    form = Session()
    form.raw('identification.php')
    status, headers, payload = form.raw('identification.php', urllib.parse.urlencode({'login':'1','username':name,'password':password,'redirect':'/'}).encode())
    assert status == 429 and b'Chvilku' in payload, 'Form bypassed API failures'
    status, _, payload = Session().raw('ws.php?format=json&method=pwg.session.getStatus', headers={'X-PIWIGO-API':'pkid-20261028-'+'a'*20+':'+'b'*40})
    assert status == 429 and json.loads(payload)['err'] == 429, 'API key bypassed login budget'
    assert Session().raw('')[0] == 200, 'Login limit blocked public browsing'
    assert member.api('pwg.session.getStatus')['username'] == name, 'Login limit blocked existing session'
    retry = int(headers['Retry-After'])
    assert 0 < retry <= 30, 'Retry-After invalid'
    time.sleep(retry+1)
    recovered = Session()
    recovered.login(name, password)
    print('Five-failure shared limit, parallel requests, cookie/XFF/key bypass rejection and timed recovery passed')
finally:
    bucket.unlink(missing_ok=True)
    try:
        if key is not None:
            ui.api('pwg.users.api_key.revoke', {'pkid':key.split(':',1)[0]})
    finally:
        if uid is not None:
            subprocess.run(['mariadb','piwigo','-e',f'DELETE FROM piwigo_user_auth_keys WHERE user_id={int(uid)}'], check=True)
            admin.api('pwg.users.delete', {'user_id':uid})
print('Disposable authentication user/key removed; operator credentials unchanged')
