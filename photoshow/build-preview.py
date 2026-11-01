"""Build a reproducible standalone preview without rebuilding the shared host."""
from pathlib import Path
import subprocess
import os
import json

repo=Path(__file__).resolve().parent.parent
pin=json.loads((repo/'flake.lock').read_text())['nodes']['nixpkgs']['locked']['rev']
if len(pin)!=40 or any(c not in '0123456789abcdef' for c in pin):raise SystemExit('Invalid nixpkgs pin')
for name,file in [('app','package.nix'),('tools','tools.nix')]:
    expr=f'let pkgs = import (builtins.getFlake "github:NixOS/nixpkgs/{pin}").outPath {{ system = "x86_64-linux"; }}; in import {repo}/photoshow/{file} {{ inherit pkgs; }}'
    subprocess.run(['nix','build','--impure','--expr',expr,'--out-link','/srv/photoshow-php85-'+name],check=True)
print('PhotoShow package and PHP 8.5 tools built from pinned nixpkgs')
