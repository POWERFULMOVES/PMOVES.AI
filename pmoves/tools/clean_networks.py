#!/usr/bin/env python3
"""Cross-platform Docker network cleanup for PMOVES."""

from __future__ import annotations

import json
import subprocess


NETWORKS = ("pmoves_data", "pmoves_api", "pmoves_app", "pmoves_bus", "pmoves_monitoring")


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


def main() -> int:
    print("Checking for stale Docker Compose networks...")
    had_warning = False

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
