#!/usr/bin/env python3
"""Basic layered-env diagnostics for Supabase bootstrap."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
from pathlib import Path

CRITICAL_KEYS = (
    "SUPABASE_URL",
    "SUPABASE_REST_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "SUPABASE_DB_PASSWORD",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _host(value: str) -> str:
    if not value:
        return ""
    candidate = value.strip().strip('"')
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    try:
        return (urllib.parse.urlparse(candidate).hostname or "").lower()
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail on conflicts")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    env_shared = parse_env_file(repo_root / "env.shared")
    env_local = parse_env_file(repo_root / ".env.local")

    conflicts: list[str] = []
    for key in CRITICAL_KEYS:
        shared = env_shared.get(key, "")
        local = env_local.get(key, "")
        host = os.environ.get(key, "")
        shared_host = _host(shared)
        local_host = _host(local)
        expected_split = (
            key in {"SUPABASE_URL", "SUPABASE_REST_URL"}
            and shared_host in {"postgrest", "host.docker.internal"}
            and local_host in {"127.0.0.1", "localhost", "host.docker.internal"}
        )
        if shared and local and shared != local:
            if not expected_split:
                conflicts.append(f"{key}: env.shared != .env.local")
        if shared and host and shared != host:
            conflicts.append(f"{key}: env.shared != host env")

    if conflicts:
        print("Supabase env doctor: conflicts detected")
        for item in conflicts:
            print(f"  - {item}")
        return 1 if args.strict else 0

    print("Supabase env doctor: no critical layered-env conflicts detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
