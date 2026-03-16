#!/usr/bin/env python3
"""Audit docker-compose services for internal:true DNS gap.

Reports which services have pmoves_external and which are only on
internal networks (potential DNS resolution failures).
"""
import yaml
import sys
from pathlib import Path

compose_path = Path(__file__).parent.parent / "docker-compose.yml"
with open(compose_path) as f:
    doc = yaml.safe_load(f)

networks = doc.get("networks", {})
internal_nets = set()
for name, cfg in networks.items():
    if isinstance(cfg, dict) and cfg.get("internal"):
        internal_nets.add(name)

services = doc.get("services", {})
has_external = []
only_internal = []

for svc_name, svc_cfg in services.items():
    svc_networks = svc_cfg.get("networks", [])
    if isinstance(svc_networks, dict):
        svc_networks = list(svc_networks)
    if "pmoves_external" in svc_networks:
        has_external.append(svc_name)
    elif svc_networks and all(n in internal_nets for n in svc_networks):
        only_internal.append(svc_name)

print(f"Services with pmoves_external: {len(has_external)}")
for s in sorted(has_external):
    print(f"  + {s}")

print(f"\nServices ONLY on internal networks: {len(only_internal)}")
for s in sorted(only_internal):
    print(f"  - {s}")

print(f"\nTotal services: {len(services)}")
print(f"\nInternal networks: {sorted(internal_nets)}")

if only_internal:
    sys.exit(0)  # informational, not a failure
