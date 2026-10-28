#!/usr/bin/env python3
"""New-VPS integration checks using disposable QA albums, never source photos."""
import atexit
import json
from pathlib import Path
import secrets
import subprocess
from client import Session, load_access

access = load_access()

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
member.api('pwg.history.search',expect='fail')
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
    admin.api('pwg.categories.setInfo',{'category_id':public_album,'name':'QA valid-token album'})
    for session in (admin,member):
        saved_token=session.token
        session.token=None
        try:
            session.api('pwg.categories.add',{'name':'QA missing-token rejection','parent':public_album},expect='fail')
            session.api('pwg.categories.setInfo',{'category_id':public_album,'name':'QA missing-token rejection'},expect='fail')
        finally:
            session.token=saved_token
    member_album=member.api('pwg.categories.add',{'name':'QA contributor album '+secrets.token_hex(4),'parent':public_album})['id'];categories.append(member_album)
    admin.api('pwg.categories.delete',{'category_id':public_album,'pwg_token':'invalid-audit-token'},expect='fail')
    high=admin.api('pwg.images.addSimple',{'category':public_album,'name':'QA privacy level','level':8},('qa-level.png',fixture_png(),'image/png'))
    images.append(high['image_id'])
    admin.api('pwg.images.uploadCompleted',{'category_id':public_album,'image_id':high['image_id']})
    high_info=admin.api('pwg.images.getInfo',{'image_id':high['image_id']})
    admin.api('pwg.images.setInfo',{'image_id':high['image_id'],'name':'QA valid-token photo','single_value_mode':'replace'})
    saved_token=admin.token
    admin.token=None
    try:
        admin.api('pwg.images.setInfo',{'image_id':high['image_id'],'name':'QA missing-token rejection'},expect='fail')
    finally:
        admin.token=saved_token
    high_derivative=high_info['derivatives']['thumb']['url']
    high_status=admin.raw(high_derivative)[0]
    assert high_status==200, f'Admin photo-level derivative HTTP {high_status}'
    for session in (anonymous,member):
        session.api('pwg.images.getInfo',{'image_id':high['image_id']},expect='fail')
        assert session.raw(high_derivative)[0]==403
        assert session.raw(high_derivative.replace('/i.php?/','/_data/i/'))[0]==403
    print('Invalid CSRF token and photo-level privacy in a public album passed')
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
    large_jpeg=subprocess.check_output(['php','-d','memory_limit=512M','-r', '$im=imagecreatetruecolor(8000,6000);imagefill($im,0,0,imagecolorallocate($im,31,57,89));imagefilledrectangle($im,1000,1000,7000,5000,imagecolorallocate($im,246,145,75));imagejpeg($im,null,85);'])
    large=admin.api('pwg.images.addSimple',{'category':public_album,'name':'QA 48 megapixel image'},('qa-large.jpg',large_jpeg,'image/jpeg'))
    images.append(large['image_id'])
    admin.api('pwg.images.uploadCompleted',{'category_id':public_album,'image_id':large['image_id']})
    large_info=admin.api('pwg.images.getInfo',{'image_id':large['image_id']})
    assert admin.raw(large_info['derivatives']['medium']['url'])[0]==200, 'Large-image derivative failed'
    print('48-megapixel JPEG upload and derivative generation passed')
finally:
    for image in images:
        admin.api('pwg.images.delete',{'image_id':image})
    for category in reversed(categories):
        admin.api('pwg.categories.delete',{'category_id':category,'photo_deletion_mode':'delete_orphans'})
print('Disposable QA albums removed; source photographs untouched')
