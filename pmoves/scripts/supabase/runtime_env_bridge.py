#!/usr/bin/env python3
"""Bridge Supabase CLI runtime env snapshots into container-safe aliases."""

from __future__ import annotations

import argparse
from pathlib import Path


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


def write_env_file(path: Path, values: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in sorted(values.items()) if v]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def to_internal_api(url: str) -> str:
    value = (url or "").rstrip("/")
    if value.startswith("http://127.0.0.1:"):
        return value.replace("http://127.0.0.1:", "http://host.docker.internal:", 1)
    if value.startswith("http://localhost:"):
        return value.replace("http://localhost:", "http://host.docker.internal:", 1)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-file", required=True, help="Input from supabase status --output env")
    parser.add_argument("--output", required=True, help="Output env file path")
    args = parser.parse_args()

    src = parse_env_file(Path(args.status_file))
    external_api_url = src.get("API_URL", "").rstrip("/")
    external_rest_url = f"{external_api_url}/rest/v1" if external_api_url else ""
    internal_api_url = to_internal_api(external_api_url)
    internal_rest_url = f"{internal_api_url}/rest/v1" if internal_api_url else ""

    bridge = {
        # Container-safe defaults
        "SUPABASE_URL": internal_api_url or external_api_url,
        "SUPABASE_INTERNAL_URL": internal_api_url or external_api_url,
        "SUPABASE_REST_URL": internal_rest_url or external_rest_url,
        "SUPA_REST_URL": internal_rest_url or external_rest_url,
        "SUPA_REST_INTERNAL_URL": internal_rest_url or external_rest_url,
        # Explicit external aliases for host tooling.
        "SUPABASE_EXTERNAL_URL": external_api_url,
        "SUPABASE_REST_EXTERNAL_URL": external_rest_url,
        "SUPA_REST_EXTERNAL_URL": external_rest_url,
        # Keys mirrored from supabase status --output env.
        "SUPABASE_ANON_KEY": src.get("ANON_KEY", ""),
        "SUPABASE_PUBLISHABLE_KEY": src.get("ANON_KEY", ""),
        "SUPABASE_SERVICE_ROLE_KEY": src.get("SERVICE_ROLE_KEY", ""),
        "SUPABASE_SECRET_KEY": src.get("SERVICE_ROLE_KEY", ""),
        "SUPABASE_JWT_SECRET": src.get("JWT_SECRET", ""),
    }

    write_env_file(Path(args.output), bridge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
