#!/usr/bin/env python3
r"""Generate a compose override that mounts host media folders into Jellyfin.

Input file: pmoves/jellyfin.hosts
Each non-empty, non-comment line: <host_path>[:<library_subdir>[:ro|rw]]
Examples:
  /mnt/c/Media               # mounts to /hostmedia/Media (rw)
  \\\NAS\Share\Movies:Movies:ro  # Windows/Samba path mounted at /hostmedia/Movies (ro)

Output: pmoves/docker-compose.jellyfin.hosts.yml
"""
from __future__ import annotations
import os
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
hosts_file = ROOT / 'jellyfin.hosts'
out_file = ROOT / 'docker-compose.jellyfin.hosts.yml'

if not hosts_file.exists():
    print(f"No host mounts file found at {hosts_file}. Create it with one path per line.")
    sys.exit(0)

vols = []
for line in hosts_file.read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    # Parse from the right to avoid confusing Windows drive-colon (e.g., D:) with field separators
    mode = 'rw'
    base = line
    rsplit1 = line.rsplit(':', 1)
    if len(rsplit1) == 2 and rsplit1[1] in ('ro', 'rw'):
        base, mode = rsplit1[0], rsplit1[1]
    host = base
    sub = None
    rsplit2 = base.rsplit(':', 1)
    if len(rsplit2) == 2:
        host, sub = rsplit2
    if not sub:
        sub = Path(host).name or 'host'
    # Normalize Windows paths:
    # - Drive letters (e.g., D:\Media) -> /mnt/d/Media
    # - UNC (e.g., \\SERVER\Share) -> //SERVER/Share (docker-compatible)
    host_norm = host
    try:
        if len(host) >= 2 and host[1] == ':' and (host[0].isalpha()):
            # Drive path like D:\something or D:/something
            drive = host[0].lower()
            rest = host[2:].lstrip('\\/').replace('\\', '/').replace('//', '/')
            host_norm = f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"
        elif host.startswith('\\\\') or host.startswith('\\'):
            # UNC path \\SERVER\Share or \SERVER\Share
            unc = host.lstrip('\\')
            unc_norm = unc.replace('\\', '/')
            host_norm = f"//{unc_norm}"
    except Exception:
        host_norm = host
    vols.append(f"{host_norm}:/media/host/{sub}:{mode}")

override = {
    'services': {
        'jellyfin-ext': {
            'volumes': vols,
        }
    }
}

out_file.write_text(yaml.safe_dump(override, sort_keys=False), encoding='utf-8')
print(f"Wrote {out_file} with {len(vols)} mount(s).")
