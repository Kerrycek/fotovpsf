"""Maintainer helper: create a patch from an external public-source worktree."""
from pathlib import Path
import subprocess
import difflib
import sys
port=Path(sys.argv[1]); patch=[]
for name in subprocess.check_output(['git','ls-files'],cwd=port,text=True).splitlines():
    f=port/name
    if not f.is_file() or name=='config.php': continue
    before=subprocess.check_output(['git','show','HEAD:'+name],cwd=port)
    try:
        a=before.decode('utf-8').replace('\r\n','\n'); b=f.read_text().replace('\r\n','\n')
    except UnicodeDecodeError:
        try: a=before.decode('latin1').replace('\r\n','\n'); b=f.read_text()
        except UnicodeDecodeError: continue
    if name=='index.php' or name.startswith('src/') and name.endswith(('.php','.css')):
        a=a.rstrip('\n')+'\n'; b=b.rstrip('\n')+'\n'
    if a!=b:
        patch.extend(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
Path(__file__).with_name('php85.patch').write_text(''.join(patch))
print('Patch generated from public code:',len(patch),'lines')
