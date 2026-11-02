"""Root-only isolated-preview regression suite; removes only its own fixtures."""
import pathlib
import secrets
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import re
import xml.etree.ElementTree as ET
import hashlib
import shutil
import os
import fcntl
import tempfile

state=pathlib.Path('/var/lib/photoshow-preview')
php='/srv/photoshow-php85-tools/bin/php'
base=os.environ.get('PHOTOSHOW_TEST_URL','http://127.0.0.1:18085/')
if base not in ['http://127.0.0.1:18085/','https://foto.crucio.cz/kra/']: raise SystemExit('Only the named preview URL is allowed')
accounts=state/'generated/Conf/accounts.xml'
if os.geteuid()!=0 or not state.is_dir(): raise SystemExit('Isolated preview root required')
checks=0
def check(condition,label):
    global checks
    if not condition: raise AssertionError(label)
    checks+=1
class Client:
    def __init__(self):self.jar=http.cookiejar.CookieJar();self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar));self.token=''
    def request(self,query='',data=None,headers=None):
        body=urllib.parse.urlencode(data,doseq=True).encode() if data is not None else None
        request=urllib.request.Request(base+query,body,headers or {})
        try: response=self.opener.open(request,timeout=80)
        except urllib.error.HTTPError as error:response=error
        content=response.read()
        match=re.search(rb'name="photoshow-csrf" content="([a-f0-9]+)"',content)
        if match:self.token=match[1].decode()
        return response.status,content,response.headers
    def post(self,query,data):return self.request(query,{**data,'csrf':self.token})
    def login(self,user,password):
        self.request('?t=Login'); before=[c.value for c in self.jar if c.name=='photoshow85']
        status,body,_=self.post('?t=Login',{'login':user,'password':password})
        check(status==200 and b'Wrong password' not in body,'login')
        check(before!=[c.value for c in self.jar if c.name=='photoshow85'],'session rotated')
        check(self.request('?t=Adm')[0]==(200 if user=='PortQAAdmin' else 403),'admin role boundary')

created=set()
def edit_accounts(callback):
    with (state/'request.lock').open('a+') as lock:
        owner=accounts.stat();os.fchown(lock.fileno(),owner.st_uid,owner.st_gid);os.fchmod(lock.fileno(),0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        info=accounts.stat();tree=ET.parse(accounts)
        callback(tree.getroot())
        fd,name=tempfile.mkstemp(prefix='.qa-accounts-',dir=accounts.parent)
        try:
            os.fchmod(fd,0o600);os.fchown(fd,info.st_uid,info.st_gid)
            with os.fdopen(fd,'wb') as stream:tree.write(stream,encoding='utf-8',xml_declaration=True)
            os.replace(name,accounts)
        finally:
            if os.path.exists(name):os.unlink(name)

def add_accounts():
    def add(root):
        for name in roles:
            if any(a.findtext('login')==name for a in root):raise RuntimeError('Fixture identity already exists')
        for name,groups in roles.items():
            a=ET.SubElement(root,'account')
            hashed=hashlib.sha1(password.encode()).hexdigest() if name=='PortQAAdmin' else subprocess.check_output([php,'-r',"echo password_hash(stream_get_contents(STDIN), PASSWORD_ARGON2ID);"],input=password.encode()).decode()
            for field,value in {'login':name,'password':hashed,'name':'','email':'','language':'','key':''}.items():ET.SubElement(a,field).text=value
            g=ET.SubElement(a,'groups')
            for group in groups:ET.SubElement(g,'group').text=group
    edit_accounts(add);created.update(roles)

password="QA ' \\ 🐷 "+secrets.token_urlsafe(64)
roles={'PortQAAdmin':['user','root'],'PortQAUser':['user'],'PortQAUpload':['user','uploaders']}
album='PortQA'+secrets.token_hex(6)
anonymous=Client();admin=Client();member=Client();uploader=Client()
try:
    add_accounts()
    code,body,headers=anonymous.request()
    check(code==200 and b'Fotogalerie' in body and b'Warning:' not in body,'anonymous home')
    check(b'photoshow-csrf' in body,'CSRF meta')
    check(anonymous.request('?t=Login',{'login':'PortQAAdmin','password':password})[0]==403,'login CSRF')
    admin.login('PortQAAdmin',password)
    for action in ['Abo','Sta','VTk','Set','Acc','EdA']:
        check(admin.request('?t=Adm&a='+action)[0]==200,'native admin page '+action)
    entry=next(a for a in ET.parse(accounts).getroot() if a.findtext('login')=='PortQAAdmin')
    check(entry.findtext('password').startswith('$argon2id$'),'native legacy hash upgraded')
    check(admin.request('?a=Upl',{'path':'','newdir':album})[0]==403,'upload CSRF')
    check(admin.post('?a=Upl',{'path':'','newdir':album,'inherit':'1'})[0]==200,'create album')
    folder=state/'photos'/album;check(folder.is_dir(),'album exists')
    status,metadata,_=admin.post('?a=Upl',{'path':album,'newdir':'quote"<x>','inherit':'1'})
    og=re.search(rb'<meta property="og:title" content="([^"]*)"',metadata)
    check(status==200 and og and b'quote&quot;&lt;x&gt;' in og[1],'album metadata escaped')

    # Real browser-compatible multipart upload through the native handler.
    image=subprocess.check_output([php,'-r','$im=imagecreatetruecolor(96,64); imagejpeg($im);'])
    def upload(client,name,content):
        boundary='photoshow'+secrets.token_hex(12)
        fields={'path':album,'newdir':'','inherit':'1','csrf':client.token}
        data=b''
        for key,value in fields.items():data+=f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
        data+=f'--{boundary}\r\nContent-Disposition: form-data; name="images[]"; filename="{name}"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()+content+f'\r\n--{boundary}--\r\n'.encode()
        try:r=client.opener.open(urllib.request.Request(base+'?a=Upl',data,{'Content-Type':'multipart/form-data; boundary='+boundary}),timeout=80)
        except urllib.error.HTTPError as e:r=e
        r.read();return r.status
    check(upload(admin,'native.jpg',image)==200,'native multipart upload')
    check((folder/'native.jpg').read_bytes()==image,'uploaded bytes')
    check(upload(admin,'fake.jpg',b'<?php echo 1;')==415,'fake JPEG blocked')
    check(upload(admin,'payload.php',image)==415,'executable blocked')
    check(not (folder/'fake.jpg').exists() and not (folder/'payload.php').exists(),'bad uploads absent')
    query=urllib.parse.urlencode({'f':album+'/native.jpg'})
    for kind in ['Thb','Img','Big','BDl']:
        status,content,_=anonymous.request('?t='+kind+'&'+query)
        check(status==200 and content.startswith(b'\xff\xd8'),'public image '+kind)
    import io,zipfile
    zip_status,zip_data,_=anonymous.request('?t=Zip&f='+urllib.parse.quote(album))
    check(zip_status==200 and len(zipfile.ZipFile(io.BytesIO(zip_data)).namelist())==1,'native ZIP download')
    admin.request('?f='+urllib.parse.quote(album))
    check(admin.post('?t=Pri&f='+urllib.parse.quote(album),{})[0]==200,'make album private')
    for kind in ['Page','Thb','Img','Big','BDl']:
        check(anonymous.request('?t='+kind+'&'+query)[0]==403,'private anonymous '+kind)
    member.login('PortQAUser',password)
    check(member.request('?t=Big&'+query)[0]==403,'private member original blocked')
    check(admin.request('?t=Big&'+query)[1]==image,'admin private original')
    large=subprocess.check_output([php,'-d','memory_limit=512M','-r','$im=imagecreatetruecolor(8000,6000); imagejpeg($im);'])
    check(upload(admin,'large.jpg',large)==200,'48 MP upload')
    large_query=urllib.parse.urlencode({'f':album+'/large.jpg'})
    check(admin.request('?t=Thb&'+large_query)[1].startswith(b'\xff\xd8'),'48 MP GD thumbnail')
    check(admin.post('?t=Adm&a=Acc',{'edit':'1','login':'PortQAAdmin','old_password':'','password':'','name':"Zkouška & profil",'email':'','language':''})[0]==200,'native account save')
    check(anonymous.request('?j=Acc')[0]==403,'anonymous account panel blocked')
    check(album.encode() not in anonymous.request()[1],'private album excluded from home')
    check(anonymous.request('?t=CTk&f='+urllib.parse.quote(album))[0]==405,'GET mutation blocked')
    check(album.encode() not in anonymous.request('?t=Rss')[1],'private image excluded from RSS')
    check(admin.post('?a=Upl',{'path':'../','newdir':'escape','inherit':'1'})[0]==400,'path traversal upload blocked')
    for bad in ['../generated/Conf/accounts.xml','/etc/passwd']:
        check(anonymous.request('?t=Big&f='+urllib.parse.quote(bad,safe=''))[0]==400,'path traversal read blocked')
    for path in ['config.php','fotky_galerie/','fotky_thumbs/Conf/accounts.xml','src/classes/Account.php','inc/modern.js.php']:
        check(anonymous.request(path)[0]==404,'internal path blocked')
    uploader.login('PortQAUpload',password)
    # Deny destructive actions to upload-only accounts, even with a valid CSRF token.
    check(uploader.post('?a=Del',{'del':album+'/native.jpg'})[0] in [200,403],'uploader deletion request')
    check((folder/'native.jpg').exists(),'uploader cannot delete another photo')
    print('PASS',checks,'live checks; native form/upload/privacy/CSRF/path confinement')
finally:
    if created:
        def cleanup(root):
            for account in list(root):
                if account.findtext('login') in created:root.remove(account)
        edit_accounts(cleanup)
    for path in [state/'photos'/album,state/'generated/Thumbs'/album]:
        if path.exists():shutil.rmtree(path)
