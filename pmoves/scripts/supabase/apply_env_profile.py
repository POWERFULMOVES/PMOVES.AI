#!/usr/bin/env python3
"""Apply a lightweight Supabase env profile to a target env file."""

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
        values[key.strip()] = value.strip()
    return values


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines() if path.exists() else []
    index: dict[str, int] = {}
    for i, raw in enumerate(lines):
        if "=" not in raw or raw.strip().startswith("#"):
            continue
        key = raw.split("=", 1)[0].strip()
        index[key] = i

    for key, value in updates.items():
        if not value:
            continue
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)

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
    parser.add_argument("--profile", choices=("local", "remote"), required=True)
    parser.add_argument("--runtime", default="cli")
    parser.add_argument("--target", required=True, help="Target env file to update")
    parser.add_argument("--status-file", default=".supabase.status.env")
    args = parser.parse_args()

    status = parse_env_file(Path(args.status_file))
    target = Path(args.target)

    if args.profile == "local":
        api_url = status.get("API_URL", "").rstrip("/")
        rest_url = f"{api_url}/rest/v1" if api_url else ""
        internal_api_url = to_internal_api(api_url)
        internal_rest_url = f"{internal_api_url}/rest/v1" if internal_api_url else ""
        updates = {
            "SUPABASE_URL": api_url,
            "SUPABASE_INTERNAL_URL": internal_api_url,
            "SUPABASE_REST_URL": rest_url,
            "SUPA_REST_URL": rest_url,
            "SUPA_REST_INTERNAL_URL": internal_rest_url or rest_url,
            "SUPABASE_ANON_KEY": status.get("ANON_KEY", ""),
            "SUPABASE_SERVICE_ROLE_KEY": status.get("SERVICE_ROLE_KEY", ""),
            "SUPABASE_JWT_SECRET": status.get("JWT_SECRET", ""),
        }
    else:
        updates = {}

    upsert_env(target, updates)
    print(f"Applied Supabase profile '{args.profile}' to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
