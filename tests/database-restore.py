#!/usr/bin/env python3
"""Rehearse a trusted checkpoint with NEW binaries on a private socket only."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time

assert os.geteuid() == 0, 'Run on the NEW VPS as root'
backup = Path(sys.argv[1]).resolve(strict=True)
package = Path(sys.argv[2]).resolve(strict=True)
assert backup.parent == Path('/var/backups/piwigo'), 'Use a managed private checkpoint'
expected = sys.argv[3] if len(sys.argv) > 3 else '476\t42\t4'
subprocess.run(['sha256sum','-c','SHA256SUMS'], cwd=backup, stdout=subprocess.DEVNULL, check=True)
with tempfile.TemporaryDirectory(prefix='db-restore-', dir='/srv/foto-migration') as temporary:
    work = Path(temporary)
    work.chmod(0o700)
    data = work/'data'
    socket = work/'mysql.sock'
    log_path = Path('/srv/foto-migration/database-restore.log')
    with log_path.open('w') as log:
        log_path.chmod(0o600)
        subprocess.run([str(package/'bin/mariadb-install-db'),'--no-defaults',f'--datadir={data}',
                        '--auth-root-authentication-method=normal','--skip-test-db'], stdout=log, stderr=log, check=True)
        process = subprocess.Popen([str(package/'bin/mysqld'),'--no-defaults','--user=root',f'--datadir={data}',
                                    f'--socket={socket}',f'--pid-file={work}/pid','--skip-networking',
                                    '--innodb-buffer-pool-size=64M'], stdout=log, stderr=log)
        client = [str(package/'bin/mariadb'),'--no-defaults',f'--socket={socket}','--user=root','-N']
        try:
            for _ in range(150):
                if process.poll() is not None: raise RuntimeError('Rehearsal database exited; inspect private log')
                if socket.exists() and subprocess.run(client+['-e','SELECT 1'],stdout=subprocess.DEVNULL,stderr=log).returncode == 0: break
                time.sleep(0.2)
            else: raise RuntimeError('Rehearsal database did not start')
            subprocess.run(client+['-e','CREATE DATABASE piwigo CHARACTER SET utf8mb4'], stdout=log, stderr=log, check=True)
            with (backup/'piwigo.sql').open('rb') as dump:
                subprocess.run(client+['piwigo'],stdin=dump,stdout=log,stderr=log,check=True)
            counts = subprocess.check_output(client+['piwigo','-e','SELECT (SELECT COUNT(*) FROM piwigo_images), '
                '(SELECT COUNT(*) FROM piwigo_categories), (SELECT COUNT(*) FROM piwigo_users)'],text=True,stderr=log).strip()
            assert counts == expected, 'Restored image/album/user counts differ from checkpoint'
            subprocess.run([str(package/'bin/mariadb-check'),'--no-defaults',f'--socket={socket}','--user=root','piwigo'],stdout=log,stderr=log,check=True)
            version = subprocess.check_output(client+['-e','SELECT VERSION()'],text=True,stderr=log).strip()
            assert version.startswith('11.4.13'), 'Unexpected rehearsal version'
            print('MariaDB 11.4.13 private-socket restore, table checks and checkpoint counts passed')
        finally:
            if process.poll() is None:
                subprocess.run([str(package/'bin/mariadb-admin'),'--no-defaults',f'--socket={socket}','--user=root','shutdown'],stdout=log,stderr=log)
                try: process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
