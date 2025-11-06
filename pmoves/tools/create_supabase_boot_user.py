#!/usr/bin/env python3
"""Bootstrap a default Supabase operator and emit a JWT for PMOVES UI."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests


@dataclass
class Env:
    service_url: str
    service_role_key: str


def _read_env() -> Env:
    """Resolve Supabase admin endpoint details from environment."""

    service_url = (
        os.environ.get("SUPABASE_SERVICE_URL")
        or os.environ.get("SUPABASE_URL")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    )
    if not service_url:
        raise SystemExit(
            "Unable to resolve Supabase URL. Set SUPABASE_SERVICE_URL (or SUPABASE_URL)."
        )

    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
        "SUPABASE_SERVICE_KEY"
    )
    if not service_role_key:
        raise SystemExit(
            "Supabase service role key missing. Export SUPABASE_SERVICE_ROLE_KEY before running."
        )

    return Env(service_url.rstrip("/"), service_role_key)


def _random_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or rotate the PMOVES boot Supabase user and print a JWT",
    )
    parser.add_argument("email", help="Email used for the boot operator account")
    parser.add_argument(
        "--password",
        help="Optional password to set (generated when omitted)",
    )
    parser.add_argument(
        "--name",
        help="Optional display name stored in user_metadata.full_name",
    )
    parser.add_argument(
        "--role",
        default="pmoves.operator",
        help="Role stored in app_metadata.role (default: pmoves.operator)",
    )
    parser.add_argument(
        "--rotate-password",
        action="store_true",
        help="Rotate password for existing user even if it already exists",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-friendly JSON instead of formatted text",
    )
    parser.add_argument(
        "--write-env",
        action="append",
        default=[],
        metavar="PATH",
        help="Env file to update with the boot user credentials (repeatable)",
    )
    return parser.parse_args()


def _admin_headers(env: Env) -> Dict[str, str]:
    return {
        "apikey": env.service_role_key,
        "Authorization": f"Bearer {env.service_role_key}",
        "Content-Type": "application/json",
    }


def _get_existing_user(env: Env, email: str) -> Optional[Dict[str, Any]]:
    resp = requests.get(
        f"{env.service_url}/auth/v1/admin/users",
        params={"email": email},
        headers=_admin_headers(env),
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        users = data.get("users") if isinstance(data, dict) else data
        if isinstance(users, list) and users:
            return users[0]
    elif resp.status_code != 404:
        raise SystemExit(
            f"Failed to query existing Supabase user ({resp.status_code}): {resp.text}"
        )
    return None


def _ensure_user(env: Env, email: str, password: str, *, name: Optional[str], role: str, rotate: bool) -> Dict[str, Any]:
    existing = _get_existing_user(env, email)
    payload: Dict[str, Any] = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "app_metadata": {"role": role},
    }
    if name:
        payload["user_metadata"] = {"full_name": name}

    if not existing:
        resp = requests.post(
            f"{env.service_url}/auth/v1/admin/users",
            headers=_admin_headers(env),
            json=payload,
            timeout=10,
        )
        if resp.status_code >= 300:
            raise SystemExit(
                f"Failed to create Supabase user ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    if rotate:
        resp = requests.patch(
            f"{env.service_url}/auth/v1/admin/users/{existing['id']}",
            headers=_admin_headers(env),
            json=payload,
            timeout=10,
        )
        if resp.status_code >= 300:
            raise SystemExit(
                f"Failed to rotate password ({resp.status_code}): {resp.text}"
            )
        return resp.json()

    return existing


def _sign_in(env: Env, email: str, password: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{env.service_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": env.service_role_key, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=10,
    )
    if resp.status_code >= 300:
        raise SystemExit(
            f"Failed to retrieve Supabase JWT ({resp.status_code}): {resp.text}"
        )
    return resp.json()


def _write_env_file(path: Path, values: Dict[str, str], *, quiet: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str]
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    existing: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, _ = raw.split("=", 1)
        existing[key] = idx

    updated = False
    for key, value in values.items():
        entry = f"{key}={value}"
        if key in existing:
            idx = existing[key]
            if lines[idx] != entry:
                lines[idx] = entry
                updated = True
        else:
            updated = True

    comment = "# Managed by create_supabase_boot_user.py"
    comment_present = any(line.strip() == comment for line in lines)

    if updated:
        missing = [k for k in values if k not in existing]
        if missing:
            if lines and lines[-1].strip():
                lines.append("")
            if not comment_present:
                lines.append(comment)
                comment_present = True
            for key in missing:
                lines.append(f"{key}={values[key]}")
        text = "\n".join(lines)
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text, encoding="utf-8")
        if not quiet:
            print(f"Updated {path}")


def _emit_output(
    *,
    email: str,
    password: str,
    token_payload: Dict[str, Any],
    json_mode: bool,
) -> None:
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")

    if not access_token:
        raise SystemExit("Supabase response missing access_token; cannot continue.")

    if json_mode:
        print(
            json.dumps(
                {
                    "email": email,
                    "password": password,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                },
                indent=2,
            )
        )
        return

    print("✅ Supabase boot user ready\n")
    print("Add these entries to pmoves/env.shared (and sync to .env.local):")
    print(f"  SUPABASE_BOOT_USER_EMAIL={email}")
    print(f"  SUPABASE_BOOT_USER_PASSWORD={password}")
    print(f"  SUPABASE_BOOT_USER_JWT={access_token}")
    if refresh_token:
        print(f"  SUPABASE_BOOT_USER_REFRESH={refresh_token}")
    print("\nExpose the JWT to the UI layer:")
    print("  NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT=${SUPABASE_BOOT_USER_JWT}")
    print("  SUPABASE_BOOT_USER_JWT=${SUPABASE_BOOT_USER_JWT}")
    print("\nThen restart the stack: `make supa-stop && make supa-start && make up`\n")


def main() -> None:
    args = _parse_args()
    env = _read_env()
    password = args.password or _random_password()

    user = _ensure_user(
        env,
        email=args.email,
        password=password,
        name=args.name,
        role=args.role,
        rotate=args.rotate_password,
    )
    if not user:
        raise SystemExit("User bootstrap failed unexpectedly")

    tokens = _sign_in(env, args.email, password)

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    values = {
        "SUPABASE_BOOT_USER_EMAIL": args.email,
        "SUPABASE_BOOT_USER_PASSWORD": password,
    }
    if access_token:
        values["SUPABASE_BOOT_USER_JWT"] = access_token
        values["NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT"] = access_token
    if refresh_token:
        values["SUPABASE_BOOT_USER_REFRESH"] = refresh_token

    quiet = bool(args.json)
    if args.write_env:
        for raw in args.write_env:
            path = Path(raw)
            _write_env_file(path, values, quiet=quiet)

    _emit_output(
        email=args.email,
        password=password,
        token_payload=tokens,
        json_mode=args.json,
    )


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise SystemExit(f"Supabase request failed: {exc}") from exc
