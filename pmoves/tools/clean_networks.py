#!/usr/bin/env python3
"""Cross-platform Docker network cleanup for PMOVES."""

from __future__ import annotations

import json
import subprocess


# Compose-managed networks: removed if stale (unlabeled) so compose recreates them labeled.
NETWORKS = ("pmoves_data", "pmoves_api", "pmoves_app", "pmoves_bus", "pmoves_monitoring")

# Shared cross-stack network: declared `external: true` in every compose file, so it must
# EXIST before any stack starts (the overlay/NATS stack and the monolith both attach to it).
# It is intentionally NOT in NETWORKS above — it must never be removed for being unlabeled
# (external networks carry no compose label by design, and removing it would break the other
# stack that holds it open). Subnet matches the documented value in the compose files.
EXTERNAL_NETWORK = "pmoves_external"
EXTERNAL_SUBNET = "172.30.6.0/24"
EXTERNAL_GATEWAY = "172.30.6.1"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True)


def network_exists(name: str) -> bool:
    return run(["docker", "network", "inspect", name]).returncode == 0


def labels_for(name: str) -> dict[str, str]:
    out = run(["docker", "network", "inspect", name, "--format", "{{json .Labels}}"])
    if out.returncode != 0:
        return {}
    raw = (out.stdout or "").strip()
    if not raw or raw == "null":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return {str(k): str(v) for k, v in parsed.items()}
    return {}


def ensure_external_network() -> bool:
    """Create the shared external network if it is missing. Returns True on success."""
    if network_exists(EXTERNAL_NETWORK):
        print(f"  OK: {EXTERNAL_NETWORK} (external, present)")
        return True
    print(f"  Creating external network: {EXTERNAL_NETWORK} ({EXTERNAL_SUBNET})")
    create = run([
        "docker", "network", "create", "--driver", "bridge",
        "--subnet", EXTERNAL_SUBNET, "--gateway", EXTERNAL_GATEWAY, EXTERNAL_NETWORK,
    ])
    if create.returncode == 0:
        return True
    # Tolerate a concurrent create (race) by re-checking existence.
    if network_exists(EXTERNAL_NETWORK):
        return True
    msg = (create.stderr or create.stdout or "").strip()
    print(f"  WARN: Failed to create {EXTERNAL_NETWORK}: {msg}")
    return False


def main() -> int:
    print("Checking for stale Docker Compose networks...")
    had_warning = False

    if not ensure_external_network():
        had_warning = True

    for network in NETWORKS:
        if not network_exists(network):
            continue
        labels = labels_for(network)
        if labels:
            print(f"  OK: {network} (properly labeled)")
            continue

        print(f"  Removing stale network: {network} (no labels)")
        rm = run(["docker", "network", "rm", network])
        if rm.returncode != 0:
            had_warning = True
            msg = (rm.stderr or rm.stdout or "").strip()
            if msg:
                print(f"  WARN: Failed to remove {network}: {msg}")
            else:
                print(f"  WARN: Failed to remove {network} - it may be in use")

    if had_warning:
        print("WARN: Network cleanup completed with warnings - run 'make down' first to remove containers")
    else:
        print("OK: Network cleanup complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
