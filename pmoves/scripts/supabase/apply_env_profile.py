#!/usr/bin/env python3
"""Apply a lightweight Supabase env profile to a target env file."""

from __future__ import annotations

import argparse
from pathlib import Path


def _strip_wrapping_quotes(value: str) -> str:
    raw = value.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = _strip_wrapping_quotes(value)
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
        anon_key = status.get("ANON_KEY", "")
        service_role_key = status.get("SERVICE_ROLE_KEY", "")
        jwt_secret = status.get("JWT_SECRET", "")
        updates = {
            "SUPABASE_URL": api_url,
            "SUPABASE_INTERNAL_URL": internal_api_url,
            "SUPABASE_REST_URL": rest_url,
            "SUPA_REST_URL": rest_url,
            "SUPA_REST_INTERNAL_URL": internal_rest_url or rest_url,
            "SUPABASE_ANON_KEY": anon_key,
            "ANON_KEY": anon_key,
            "SUPABASE_SERVICE_ROLE_KEY": service_role_key,
            "SERVICE_ROLE_KEY": service_role_key,
            # NOTE: SUPABASE_SECRET_KEY is deliberately NOT set here, and neither is
            # SUPABASE_PUBLISHABLE_KEY. Those two are Supabase's NEW opaque API-key
            # model (sb_secret_… / sb_publishable_…), not aliases for the legacy
            # JWTs. This line used to read
            #     "SUPABASE_SECRET_KEY": service_role_key,
            # which made Kong's declarative config declare the SAME key twice for
            # the service_role consumer (once as $SUPABASE_SERVICE_KEY, once as
            # $SUPABASE_SECRET_KEY). Kong requires keyauth_credentials.key to be
            # globally unique, so it rejected the entire kong.yml with
            #     uniqueness violation: 'keyauth_credentials' entity with key … already declared
            # and crash-looped, taking every /rest/v1, /auth/v1 and /storage/v1
            # route down with it.
            # Upstream ships both EMPTY (PMOVES-supabase/docker/.env.example:47,49)
            # and its entrypoint strips blank key entries (kong-entrypoint.sh:47),
            # so leaving them unset is the SUPPORTED state, not an omission.
            # Populate them only on a real migration to the opaque key model, with
            # genuine sb_* values.
            # See docs/handoffs/supabase-kong-declarative-config-boot-failure-2026-08-18.md
            "SUPABASE_JWT_SECRET": jwt_secret,
        }
    else:
        updates = {}

    upsert_env(target, updates)
    print(f"Applied Supabase profile '{args.profile}' to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
