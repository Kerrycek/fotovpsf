"""Verify HTTPS prefix, session boundaries and real edge login throttling."""
from pathlib import Path
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import json
import re
import time
import secrets
import os

if os.geteuid()!=0:raise SystemExit('Root required on the test VPS')
base='https://foto.crucio.cz/kra/'
jar=http.cookiejar.CookieJar()
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def request(url,data=None,headers=None):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    try:response=client.open(urllib.request.Request(url,body,headers or {}),timeout=20)
    except urllib.error.HTTPError as error:response=error
    return response.status,response.read(),response.headers
status,body,headers=request(base+'?t=Login')
assert status==200 and 'WWW-Authenticate' not in headers
cookies=headers.get_all('Set-Cookie',[])
assert any(all(x in c.lower() for x in ['path=/kra/','secure','httponly','samesite=lax']) for c in cookies)
token=re.search(rb'name="photoshow-csrf" content="([a-f0-9]+)"',body)[1].decode()
status,_,_=request(base+'?j=Acc');assert status==403
status,_,_=request('https://foto.crucio.cz/');assert status==200
user='NoSuchPhotoUser'+secrets.token_hex(8)
for i in range(5):
    status,_,headers=request(base+'?t=Login',{'csrf':token,'login':user,'password':'not-an-account-password'})
    assert status==200,'Unexpected pre-existing source budget; inspect before rerunning'
status,_,headers=request(base+'?t=Login',{'csrf':token,'login':user,'password':'not-an-account-password'})
assert status==429 and 'Retry-After' in headers
status,_,_=request(base+'?t=Login',{'csrf':token,'login':user+'other','password':'not-an-account-password'}, {'X-Forwarded-For':'192.0.2.1','X-Real-IP':'192.0.2.2'})
assert status==429,'Client headers bypassed the real source budget'
status,_,_=request(base);assert status==200,'Public browsing stopped with blocked login'
retry=int(headers['Retry-After']);assert 1<=retry<=30
time.sleep(retry+0.5)
credentials=json.loads(Path('/var/backups/photoshow-port/access.json').read_text())
status,body,_=request(base+'?t=Login',{'csrf':token,'login':credentials['username'],'password':credentials['password']})
assert status==200 and credentials['username'].encode() in body and b'Wrong password' not in body
print('PASS HTTPS path/cookies, anonymous admin denial, five-failure budget, spoofed headers rejected, browsing and timed login recovery')
