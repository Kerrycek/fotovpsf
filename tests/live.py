#!/usr/bin/env python3
"""New-VPS integration checks using disposable QA albums, never source photos."""
import base64
import atexit
import http.cookiejar
import json
from pathlib import Path
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request

access = json.loads(Path('/root/fotovpsf-access.json').read_text())
base = 'https://foto.crucio.cz'
basic = 'Basic '+base64.b64encode((access['preview_username']+':'+access['preview_password']).encode()).decode()

class Session:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token = None
    def raw(self, url, data=None, headers=None):
        if not url.startswith(base): url = base+'/'+url.lstrip('/')
        request = urllib.request.Request(url, data=data, headers={'Authorization':basic, **(headers or {})})
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

admin=Session();admin.login(access['admin_username'], access['admin_password'])
anonymous=Session()
member_name='qa-uploader-'+secrets.token_hex(5)
member_password=secrets.token_urlsafe(24)
member_id=admin.api('pwg.users.add',{'username':member_name,'password':member_password,'password_confirm':member_password})['users'][0]['id']
atexit.register(lambda: admin.api('pwg.users.delete',{'user_id':member_id}))
group_id=admin.api('pwg.groups.getList',{'name':'uploaders'})['groups'][0]['id']
admin.api('pwg.groups.addUser',{'group_id':group_id,'user_id':member_id})
member=Session();member.login(member_name,member_password)
member.api('pwg.users.getList',expect='fail')
anonymous.api('pwg.categories.add',{'name':'should-not-exist'},expect='fail')
public=anonymous.api('pwg.images.getInfo',{'image_id':1})
assert anonymous.raw(public['derivatives']['thumb']['url'])[0]==200
print('Public browsing, member login and administrator isolation passed')

def fixture_png():
    return subprocess.check_output(['php','-r', '$im=imagecreatetruecolor(640,480);$bg=imagecolorallocate($im,31,57,89);imagefill($im,0,0,$bg);$orange=imagecolorallocate($im,246,145,75);imagefilledrectangle($im,120,100,520,380,$orange);imagesetpixel($im,0,0,imagecolorallocate($im,random_int(0,255),random_int(0,255),random_int(0,255)));imagepng($im);'])
png=fixture_png()
categories=[]
images=[]
try:
    private=admin.api('pwg.categories.add',{'name':'QA private '+secrets.token_hex(4),'status':'private'})['id'];categories.append(private)
    admin.api('pwg.permissions.add',{'cat_id':private,'user_id':1})
    uploaded=admin.api('pwg.images.addSimple',{'category':private,'name':'QA private image'},('qa-private.png',png,'image/png'))
    images.append(uploaded['image_id'])
    admin.api('pwg.images.uploadCompleted',{'category_id':private,'image_id':uploaded['image_id']})
    info=admin.api('pwg.images.getInfo',{'image_id':uploaded['image_id']})
    derivative=info['derivatives']['thumb']['url']
    Path('/srv/foto-migration/private-image-diagnostic.json').write_text(json.dumps({'derivative':derivative,'element':info['element_url'],'image_id':uploaded['image_id']}))
    derivative_response=admin.raw(derivative)
    assert derivative_response[0]==200, f'Admin private derivative HTTP {derivative_response[0]}: {derivative_response[2][:80]!r}'
    assert anonymous.raw(derivative)[0]==403, 'Anonymous can view private derivative'
    assert member.raw(derivative)[0]==403, 'Unprivileged member can view private derivative'
    # Cached derivatives must be protected as well as i.php generation.
    cached=derivative.replace('/i.php?/','/_data/i/')
    assert admin.raw(cached)[0]==200
    assert anonymous.raw(cached)[0]==403
    assert member.raw(cached)[0]==403
    anonymous.api('pwg.images.getInfo',{'image_id':uploaded['image_id']},expect='fail')
    member.api('pwg.images.getInfo',{'image_id':uploaded['image_id']},expect='fail')
    for url in [info['element_url'],f'action.php?id={uploaded["image_id"]}&part=e']:
        assert anonymous.raw(url)[0] in (401,403,404), 'Private original is accessible'
    for url in ['local/config/database.inc.php','_data/tmp/test','install.php','upgrade.php','image-auth.php','galleries/legacy/2010/Tower_servery/1.jpg']:
        assert anonymous.raw(url)[0]==404, 'Internal/direct original path exposed'
    print('Private original, generated/cached derivative and internal-path protection passed')
    public_album=admin.api('pwg.categories.add',{'name':'QA upload '+secrets.token_hex(4),'status':'public'})['id'];categories.append(public_album)
    good=member.api('pwg.images.addSimple',{'category':public_album,'name':'QA contributor image'},('qa-member.png',fixture_png(),'image/png'))
    images.append(good['image_id'])
    member.api('pwg.images.uploadCompleted',{'category_id':public_album,'image_id':good['image_id']})
    assert good['image_id']>uploaded['image_id']
    anonymous.api('pwg.images.getInfo',{'image_id':good['image_id']},expect='fail')
    for filename,content,mime in [('unsafe.php',b'<?php echo "test";','application/x-php'),('fake.jpg',b'not an image','image/jpeg'),('unsafe.svg',b'<svg xmlns="http://www.w3.org/2000/svg"/>','image/svg+xml')]:
        before=subprocess.check_output(['mariadb','-N','piwigo','-e','SELECT COUNT(*) FROM piwigo_images'])
        admin.api('pwg.images.addSimple',{'category':public_album},(filename,content,mime),expect='fail')
        assert before==subprocess.check_output(['mariadb','-N','piwigo','-e','SELECT COUNT(*) FROM piwigo_images']), 'Rejected upload created an image'
    print('Contributor upload/moderation and PHP, fake-JPEG, SVG rejection passed')
finally:
    for image in images:
        admin.api('pwg.images.delete',{'image_id':image})
    for category in reversed(categories):
        admin.api('pwg.categories.delete',{'category_id':category,'photo_deletion_mode':'delete_orphans'})
print('Disposable QA albums removed; source photographs untouched')
