#!/usr/bin/env python3
"""Inject Docker Hub credentials from the local credential helper into env.tier-api.

Reads Docker Hub username + PAT from the platform credential helper
(docker-credential-desktop on Windows, docker-credential-osxkeychain on macOS,
docker-credential-secretservice on Linux) and writes them into env.tier-api.

Mirrors inject_github_pat_from_gh_cli.py — same atomic-write + chmod pattern.

Usage:
  python pmoves/tools/inject_docker_hub_pat_from_cli.py
  python pmoves/tools/inject_docker_hub_pat_from_cli.py --check
  python pmoves/tools/inject_docker_hub_pat_from_cli.py --env-file custom.env

The --check flag validates credential availability without writing anything.
Exit codes:
  0 - success (or --check passed)
  1 - credentials not stored in helper (run: docker login)
  2 - Docker Hub auth validation failed (expired PAT)
  3 - env file write failure

Called via `make -C pmoves docker-hub-inject`.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import platform
import re
import subprocess
import sys

REGISTRY = "https://index.docker.io/v1/"

HELPERS: dict[str, str] = {
    "Windows": "docker-credential-desktop",
    "Darwin": "docker-credential-osxkeychain",
    "Linux": "docker-credential-secretservice",
}


def get_creds() -> tuple[str | None, str | None]:
    """Return (username, token) from the platform credential helper, or (None, None)."""
    helper = HELPERS.get(platform.system(), "docker-credential-desktop")
    try:
        result = subprocess.run(
            [helper, "get"],
            input=REGISTRY + "\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        print(
            f"ERROR: credential helper '{helper}' not found. "
            "Ensure Docker Desktop is installed.",
            file=sys.stderr,
        )
        return None, None
    except subprocess.TimeoutExpired:
        print("ERROR: credential helper timed out.", file=sys.stderr)
        return None, None

    if result.returncode != 0:
        return None, None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("ERROR: credential helper returned non-JSON output.", file=sys.stderr)
        return None, None

    return data.get("Username"), data.get("Secret")


def validate(username: str, token: str) -> bool:
    """Return True if the credentials authenticate successfully against Docker Hub."""
    try:
        result = subprocess.run(
            ["docker", "login", "--username", username, "--password-stdin"],
            input=token,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("ERROR: docker CLI not found.", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print("ERROR: docker login timed out.", file=sys.stderr)
        return False
    return result.returncode == 0


def inject_into_env_file(env_path: pathlib.Path, username: str, token: str) -> None:
    """Update DOCKERHUB_USERNAME and DOCKERHUB_PAT in env_path, appending if absent."""
    try:
        text = env_path.read_text() if env_path.exists() else ""
    except OSError as e:
        print(f"ERROR: cannot read {env_path}: {e}", file=sys.stderr)
        sys.exit(3)

    def _upsert(text: str, key: str, value: str) -> str:
        new_line = f"{key}={value}"
        if re.search(rf"(?m)^{re.escape(key)}=", text):
            return re.sub(rf"(?m)^{re.escape(key)}=.*$", new_line, text)
        sep = "" if not text or text.endswith("\n") else "\n"
        return f"{text}{sep}{new_line}\n"

    text = _upsert(text, "DOCKERHUB_USERNAME", username)
    text = _upsert(text, "DOCKERHUB_PAT", token)

    try:
        env_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: cannot create {env_path.parent}: {e}", file=sys.stderr)
        sys.exit(3)

    tmp_path = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp_path.write_text(text)  # lgtm[py/clear-text-storage-of-sensitive-data]
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass  # no-op on Windows filesystems
        tmp_path.replace(env_path)
    except OSError as e:
        print(f"ERROR: cannot write {env_path}: {e}", file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        sys.exit(3)

    token_len = len(token)
    del token  # clear secret from local scope after write
    print(f"OK: DOCKERHUB_USERNAME={username}, DOCKERHUB_PAT written to {env_path} (token length={token_len})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _default_env = str(pathlib.Path(__file__).parents[1] / "env" / "env.tier-api")
    parser.add_argument(
        "--env-file",
        default=_default_env,
        help="Path to env file (default: <repo>/pmoves/env/env.tier-api)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate credentials only; do not write env file",
    )
    args = parser.parse_args()

    username, token = get_creds()
    if not username or not token:
        print(
            "[docker-hub-inject] No Docker Hub credentials in local helper.\n"
            "  Fix: docker login\n"
            "  Then re-run: make -C pmoves docker-hub-inject",
            file=sys.stderr,
        )
        sys.exit(1)

    if not validate(username, token):
        print(
            "[docker-hub-inject] Credentials found but Docker Hub auth failed — PAT may be expired.\n"
            "  Fix: docker login  (re-authenticate with a fresh PAT)\n"
            "  Then re-run: make -C pmoves docker-hub-inject",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.check:
        del token  # clear secret; check doesn't need it further
        print(f"[docker-hub-inject] --check passed: {username} authenticated")
        return

    env_path = pathlib.Path(args.env_file)
    inject_into_env_file(env_path, username, token)
    del token  # clear secret from local scope after injection
    print(f"[docker-hub-inject] OK -- {username} -> {env_path}")


if __name__ == "__main__":
    main()
