#!/usr/bin/env python3
"""Low-volume anonymous HTTP regression checks; no credentials or live writes."""
import http.cookies
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://foto.crucio.cz/'
checks = 0


def request(path, headers=None):
    req = urllib.request.Request(urllib.parse.urljoin(BASE, path), headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, response.headers, response.read(), response.url
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read(), error.url


def check(condition, message):
    global checks
    if not condition:
        raise AssertionError(message)
    checks += 1


status, headers, body, _ = request('')
check(status == 200, 'Public home unavailable')
for name, expected in {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'SAMEORIGIN',
    'Referrer-Policy': 'same-origin',
    'Strict-Transport-Security': 'max-age=2592000',
}.items():
    check(headers.get(name) == expected, 'Missing security header: ' + name)
check("frame-ancestors 'self'" in headers.get('Content-Security-Policy', ''), 'Missing framing CSP')
check(headers.get('X-Powered-By') is None, 'PHP version exposed')
check(not any(char.isdigit() for char in headers.get('Server', '')), 'Server version exposed')
status, _, _, final_url = request('http://foto.crucio.cz/')
check(status == 200 and final_url.startswith(BASE), 'HTTP does not redirect to HTTPS')

for path in (
    'install.php', 'upgrade.php', 'image-auth.php', '__gallery_image_auth',
    'local/config/database.inc.php', 'local/config/config.inc.php',
    '_data/logs/', '_data/templates_c/', '_data/tmp/', '.git/config', '.env',
    'galleries/legacy/2010/Tower_servery/1.jpg', 'upload/',
    '%69nstall.php', '%75pgrade.php', 'local%2fconfig%2fdatabase.inc.php',
    '_data/combined/missing.php',
):
    check(request(path)[0] == 404, 'Internal/direct path exposed: ' + path)

for method in ('pwg.users.getList', 'pwg.history.search', 'pwg.getInfos', 'pwg.activity.getList'):
    status, _, payload, _ = request('ws.php?' + urllib.parse.urlencode({'format': 'json', 'method': method}))
    denied = status in (401, 403)
    if status == 200:
        denied = json.loads(payload).get('stat') == 'fail'
    check(denied, 'Anonymous administrative API exposed: ' + method)

for parameter in ('f_min_date_available', 'f_max_date_available', 'f_min_date_created', 'f_max_date_created'):
    query = {'format': 'json', 'method': 'pwg.categories.getImages', 'cat_id': 41, parameter: "2026-01-01'"}
    status, _, payload, _ = request('ws.php?' + urllib.parse.urlencode(query))
    check(status == 200 and json.loads(payload).get('stat') == 'fail', 'Invalid date filter accepted: ' + parameter)
    check(b'SQL syntax' not in payload and b'Warning:' not in payload, 'Database error exposed')

_, _, body, _ = request('identification.php', {'Cookie': 'lang=%3Csecurity-audit-marker%3E'})
check(b'<security-audit-marker>' not in body, 'Raw language cookie reflected')
status, session_headers, _, _ = request('identification.php')
check(status == 200, 'Login page unavailable')
cookies = http.cookies.SimpleCookie()
for value in session_headers.get_all('Set-Cookie', []):
    cookies.load(value)
check('pwg_id' in cookies, 'Session cookie was not issued')
session = cookies['pwg_id']
check(bool(session['secure']) and bool(session['httponly']) and session['samesite'].lower() == 'lax', 'Session cookie flags unsafe')

context = ssl.create_default_context()
with urllib.request.urlopen(BASE, context=context, timeout=20) as response:
    check(response.status == 200, 'Valid TLS unavailable')
print(f'{checks} anonymous path, API, input, cookie, TLS and header checks passed')
