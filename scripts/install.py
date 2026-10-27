#!/usr/bin/env python3
"""One-time local installer. Run as root on the NEW server only."""
import grp
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

os.umask(0o077)
if os.geteuid() != 0:
    raise SystemExit("Run as root on the new server")
if subprocess.check_output(["mariadb", "-N", "-e", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='piwigo'"]).strip() != b"0":
    raise SystemExit("Database is not empty; refusing to run the installer again")
access_file = Path("/root/fotovpsf-access.json")
if access_file.exists():
    raise SystemExit("Credentials already exist; inspect the previous installation")
accounts = ET.parse("/srv/foto-migration/source/foto.vpsfree.cz/fotky_thumbs/Conf/accounts.xml").getroot()
email = next((a.findtext("email") for a in accounts if a.findtext("email")), "admin@example.invalid")
access = {"url": "https://foto.crucio.cz", "admin_username": "foto-admin", "admin_password": secrets.token_urlsafe(24), "preview_username": "galerie", "preview_password": secrets.token_urlsafe(18)}
access_file.write_text(json.dumps(access, indent=2) + "\n")
fields = {"install": "Start Install", "language": "cs_CZ", "dbhost": "localhost", "dbuser": "piwigo", "dbpasswd": "", "dbname": "piwigo", "prefix": "piwigo_", "admin_name": access["admin_username"], "admin_pass1": access["admin_password"], "admin_pass2": access["admin_password"], "admin_mail": email}
request = urllib.request.Request("http://127.0.0.1:8080/install.php?language=cs_CZ", data=urllib.parse.urlencode(fields).encode(), headers={"Host": "foto.crucio.cz"})
with urllib.request.urlopen(request, timeout=90) as response:
    body = response.read()
Path("/srv/foto-migration/install-result.html").write_bytes(body)
config_file = Path("/var/lib/piwigo/local/config/database.inc.php")
if not config_file.exists():
    raise SystemExit("Installation failed; inspect the private result HTML")
os.chown(config_file, 0, grp.getgrnam("piwigo").gr_gid)
config_file.chmod(0o640)
print("Installed; credentials saved to /root/fotovpsf-access.json (root only)")
