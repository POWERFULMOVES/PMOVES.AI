#!/usr/bin/env python3
"""Assert the Docker host applies PMOVES log-rotation policy — and that it took.

Why
---
Z890 reported logs eating disk. B850 measured 4.6 GB in
/var/lib/docker/containers and had NO /etc/docker/daemon.json at all, so the
json-file driver ran with no rotation: container logs grow without bound. Only
4 of 110 services in the main compose cap their own logs.

The fix was already written and simply never applied:

    deploy/provision/daemon.json                  50m x 3, live-restore, builder GC
    pmoves/scripts/pmoves-daemon-log-rotation.sh  idempotent merge into daemon.json

Nothing checked whether a node had it. This is that check.

What it measures
----------------
The EFFECTIVE per-container log config, not the contents of daemon.json. A
daemon.json that exists but was written after the last daemon restart is not in
force, and reading the file would report success while every container still
logs unbounded. `docker inspect` reports what the container actually got, which
is the only answer that means anything.

It also surfaces ORPHANED buildx cache volumes. On B850 a single volume,
`buildx_buildkit_pmoves-shared0_state`, held 183.3 GB with LINKS=0 for a builder
that no longer exists — while `docker system df` reported "Build Cache 0B",
because the daemon-local cache genuinely was empty and the 183 GB sat inside a
builder container's volume, counted under Local Volumes. The number an operator
would check hid the thing taking the space.

Refusing to guess
-----------------
No Docker socket, or no running containers, means the policy could not be
measured. That exits 3, not 0. A probe that reports "pass" when it took no
measurement is the failure mode this repo has spent a lot of effort removing.

Usage:
  python pmoves/tools/docker_host_policy_check.py           # gate
  python pmoves/tools/docker_host_policy_check.py --json    # machine-readable

Exit codes:
  0  policy in force on every sampled container
  1  at least one container logs without rotation
  3  could not measure (no docker, no containers) — NOT a pass
  4  usage error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

# Matches deploy/provision/daemon.json. A node may cap tighter, never looser.
MAX_SIZE_CEILING_MB = 50
REQUIRED_MAX_FILE = 1  # at least one rotation file


class Unmeasured(RuntimeError):
    """The host could not be interrogated, so no verdict is possible."""


def _docker(*args: str, timeout: int = 30) -> str:
    if not shutil.which("docker"):
        raise Unmeasured("docker CLI not on PATH")
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise Unmeasured(f"docker {' '.join(args)}: {exc}") from exc
    if result.returncode != 0:
        raise Unmeasured(
            f"docker {' '.join(args)} failed: {(result.stderr or '').strip()[:200]}"
        )
    return result.stdout


def _parse_size_mb(value: str) -> Optional[float]:
    """`10m`, `50M`, `1g`, `512k` -> megabytes. None when unparseable."""
    if not value:
        return None
    text = value.strip().lower()
    units = {"b": 1 / 1_048_576, "k": 1 / 1024, "m": 1.0, "g": 1024.0}
    unit = text[-1]
    if unit in units:
        try:
            return float(text[:-1]) * units[unit]
        except ValueError:
            return None
    try:
        return float(text) / 1_048_576
    except ValueError:
        return None


def running_containers() -> List[str]:
    names = [n for n in _docker("ps", "--format", "{{.Names}}").split() if n]
    if not names:
        raise Unmeasured("no running containers to sample")
    return names


def log_config(name: str) -> Dict[str, Any]:
    raw = _docker("inspect", name, "--format", "{{json .HostConfig.LogConfig}}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Unmeasured(f"{name}: unparseable LogConfig: {exc}") from exc


def audit_logging(names: List[str]) -> Tuple[List[dict], List[dict]]:
    offenders: List[dict] = []
    compliant: List[dict] = []
    for name in names:
        config = log_config(name)
        driver = config.get("Type") or ""
        options = config.get("Config") or {}
        # Drivers that ship their own retention are out of scope.
        if driver and driver not in ("json-file", "local", ""):
            compliant.append({"container": name, "driver": driver, "reason": "external driver"})
            continue
        max_size = options.get("max-size") or ""
        max_file = options.get("max-file") or ""
        size_mb = _parse_size_mb(max_size)
        if not max_size or size_mb is None:
            offenders.append({
                "container": name, "driver": driver or "json-file",
                "reason": "no max-size — this container's log grows without bound",
            })
            continue
        if size_mb > MAX_SIZE_CEILING_MB:
            offenders.append({
                "container": name, "driver": driver, "max_size": max_size,
                "reason": f"max-size {max_size} exceeds the {MAX_SIZE_CEILING_MB}m policy ceiling",
            })
            continue
        try:
            files = int(max_file) if max_file else 0
        except ValueError:
            files = 0
        if files < REQUIRED_MAX_FILE:
            offenders.append({
                "container": name, "driver": driver, "max_size": max_size,
                "reason": "max-file missing or < 1 — rotation cannot retain history",
            })
            continue
        compliant.append({"container": name, "driver": driver,
                          "max_size": max_size, "max_file": max_file})
    return offenders, compliant


def orphaned_build_cache() -> List[dict]:
    """buildx state volumes with no builder. Reported, never removed."""
    try:
        builders = _docker("buildx", "ls")
    except Unmeasured:
        return []
    try:
        raw = _docker("volume", "ls", "--format", "{{.Name}}")
    except Unmeasured:
        return []
    orphans = []
    for volume in (v for v in raw.split() if v.startswith("buildx_buildkit_")):
        # buildx_buildkit_<builder>_state (or ..._state0)
        builder = volume[len("buildx_buildkit_"):].rsplit("_state", 1)[0]
        if builder and builder not in builders:
            orphans.append({"volume": volume, "builder": builder})
    return orphans


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        names = running_containers()
        offenders, compliant = audit_logging(names)
        orphans = orphaned_build_cache()
    except Unmeasured as exc:
        print(f"[unmeasured] {exc}", file=sys.stderr)
        print("[unmeasured] no verdict reached — this is not a pass", file=sys.stderr)
        if args.json:
            print(json.dumps({"status": "unmeasured", "detail": str(exc)}, indent=2))
        return 3

    if args.json:
        print(json.dumps({
            "status": "fail" if offenders else "pass",
            "sampled": len(names),
            "offenders": offenders,
            "compliant": len(compliant),
            "orphaned_build_cache": orphans,
        }, indent=2))
        return 1 if offenders else 0

    print(f"Docker host policy: sampled {len(names)} running container(s)")
    for orphan in orphans:
        print(f"[WARN]  orphaned build cache volume {orphan['volume']} — "
              f"builder '{orphan['builder']}' no longer exists. "
              f"`docker volume rm {orphan['volume']}` reclaims it (build cache only).")
    for bad in offenders:
        detail = f" (max-size={bad['max_size']})" if bad.get("max_size") else ""
        print(f"[ERROR] {bad['container']}: {bad['reason']}{detail}")
    if offenders:
        print(f"\nFAILED: {len(offenders)} of {len(names)} container(s) log without "
              f"the rotation policy.\n"
              f"  Fix (per node, needs sudo):\n"
              f"    sudo bash pmoves/scripts/pmoves-daemon-log-rotation.sh\n"
              f"  Then restart the daemon and recreate the affected containers — a\n"
              f"  daemon.json written after a container started does not apply to it.")
        return 1
    print(f"PASS: rotation in force on all {len(names)} sampled container(s)"
          + (f"; {len(orphans)} orphaned build-cache volume(s) reported above" if orphans else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
