"""Create a separate operator account only in the isolated preview's XML state."""
from pathlib import Path
import os
import json
import secrets
import subprocess
import xml.etree.ElementTree as ET

if os.geteuid()!=0:raise SystemExit('Root required')
receipt=Path('/var/backups/photoshow-port/access.json')
accounts=Path('/var/lib/photoshow-preview/generated/Conf/accounts.xml')
if receipt.exists():raise SystemExit('Existing preview access retained')
name='FotoPreviewAdmin'
tree=ET.parse(accounts);root=tree.getroot()
if any(a.findtext('login')==name for a in root):raise SystemExit('Account already exists; inspect before changing it')
password=secrets.token_urlsafe(24)
hashed=subprocess.check_output(['/srv/photoshow-php85-tools/bin/php','-r','echo password_hash(stream_get_contents(STDIN), PASSWORD_ARGON2ID, ["memory_cost"=>65536,"time_cost"=>3,"threads"=>1]);'],input=password.encode()).decode()
a=ET.SubElement(root,'account')
for key,value in {'login':name,'password':hashed,'name':'','email':'','language':'','key':''}.items():ET.SubElement(a,key).text=value
roles=ET.SubElement(a,'groups')
for role in ['user','root']:ET.SubElement(roles,'group').text=role
tree.write(accounts,encoding='utf-8',xml_declaration=True)
fd=os.open(receipt,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:json.dump({'username':name,'password':password},stream)
print('Separate preview operator account created; credentials saved privately')
