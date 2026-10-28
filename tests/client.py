"""Private-credential HTTP helper for checks on the NEW preview only."""
import http.cookiejar
import json
from pathlib import Path
import secrets
import urllib.error
import urllib.parse
import urllib.request

base = "https://foto.crucio.cz"

def load_access():
    return json.loads(Path("/root/fotovpsf-access.json").read_text())

class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token = None
    def raw(self, url, data=None, headers=None):
        if not url.startswith(base): url = base+'/'+url.lstrip('/')
        request = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with self.opener.open(request, timeout=90) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()
    def api(self, method, fields=None, image=None, expect='ok'):
        fields = {'method':method, **(fields or {})}
        if self.token: fields.setdefault('pwg_token', self.token)
        headers = {}
        if image:
            boundary = 'galleryqa'+secrets.token_hex(12)
            chunks=[]
            for key,value in fields.items():
                chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()])
            filename,content,mime=image
            chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'.encode(), content, f'\r\n--{boundary}--\r\n'.encode()])
            data=b''.join(chunks);headers['Content-Type']='multipart/form-data; boundary='+boundary
        else:
            data=urllib.parse.urlencode(fields).encode()
            headers['Content-Type']='application/x-www-form-urlencoded'
        status,_,body=self.raw('ws.php?format=json',data,headers)
        try: result=json.loads(body)
        except ValueError:
            # Legacy addSimple uses plain-text rejection for forbidden types.
            if expect=='fail' and body.strip() in (b'unexpected file type',b'forbidden file type'):
                return None
            raise AssertionError(f'{method}: non-JSON HTTP {status}')
        assert result.get('stat')==expect, f'{method}: expected {expect}, HTTP {status}, API code {result.get("err")} message {result.get("message")}'
        return result.get('result')
    def login(self, username, password):
        self.api('pwg.session.login', {'username':username,'password':password})
        self.token=self.api('pwg.session.getStatus')['pwg_token']

