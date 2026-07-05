#!/usr/bin/env python3
"""Inject Docker Hub credentials from the local credential helper into env.tier-api.

Reads Docker Hub username + PAT from the platform credential helper
(auto-detected from ~/.docker/config.json credsStore; falls back to
docker-credential-desktop on Windows and docker-credential-osxkeychain on macOS)
and writes them into env.tier-api.

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
import urllib.error
import urllib.request

REGISTRY = "https://index.docker.io/v1/"

_PLATFORM_HELPERS: dict[str, str] = {
    "Windows": "docker-credential-desktop",
    "Darwin": "docker-credential-osxkeychain",
}

_USERNAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}")


def _resolve_helper() -> str:
    """Return the active credential helper name.

    Checks per-registry credHelpers first (Docker Hub domains), then falls
    back to global credsStore, then platform defaults.
    """
    _DOCKERHUB_DOMAINS = {"index.docker.io", "docker.io", "https://index.docker.io/v1/"}
    config_path = pathlib.Path.home() / ".docker" / "config.json"
    if config_path.exists():
        try:
            with config_path.open() as f:
                config = json.load(f)
            for domain, helper in config.get("credHelpers", {}).items():
                if domain in _DOCKERHUB_DOMAINS:
                    return f"docker-credential-{helper}"
            store = config.get("credsStore")
            if store:
                return f"docker-credential-{store}"
        except (json.JSONDecodeError, OSError):
            pass
    return _PLATFORM_HELPERS.get(platform.system(), "docker-credential-desktop")


def get_creds() -> tuple[str | None, str | None]:
    """Return (username, token) from the platform credential helper, or (None, None)."""
    helper = _resolve_helper()
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
    """Return True if the credentials authenticate against Docker Hub (read-only probe).

    Uses the Docker Hub login API rather than `docker login` to avoid mutating
    the operator's active credential store.
    """
    payload = json.dumps({"username": username, "password": token}).encode()
    req = urllib.request.Request(
        "https://hub.docker.com/v2/users/login/",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.HTTPError:
        return False
    except OSError:
        return False


def inject_into_env_file(env_path: pathlib.Path, username: str, token: str) -> None:
    """Update DOCKERHUB_USERNAME and DOCKERHUB_PAT in env_path, appending if absent."""
    try:
        text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    except OSError as e:
        print(f"ERROR: cannot read {env_path}: {e}", file=sys.stderr)
        sys.exit(3)

    def _upsert(content: str, key: str, value: str) -> str:
        new_line = f"{key}={value}"
        if re.search(rf"(?m)^{re.escape(key)}=", content):
            return re.sub(rf"(?m)^{re.escape(key)}=.*$", new_line, content)
        sep = "" if not content or content.endswith("\n") else "\n"
        return f"{content}{sep}{new_line}\n"

    text = _upsert(text, "DOCKERHUB_USERNAME", username)
    text = _upsert(text, "DOCKERHUB_PAT", token)  # lgtm[py/clear-text-storage-of-sensitive-data]

    try:
        env_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as e:
        print(f"ERROR: cannot create {env_path.parent}: {e}", file=sys.stderr)
        sys.exit(3)

    tmp_path = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")  # lgtm[py/clear-text-storage-of-sensitive-data]
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
    del token  # break name binding (best-effort; not a memory wipe)
    print(f"OK: DOCKERHUB_PAT written to {env_path} (token length={token_len})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _default_env = str(pathlib.Path(__file__).resolve().parents[1] / "env.tier-api")
    parser.add_argument(
        "--env-file",
        default=_default_env,
        help="Path to env file (default: <repo>/pmoves/env.tier-api)",
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

    if not _USERNAME_RE.fullmatch(username):
        print(
            f"ERROR: invalid username '{username}' from credential helper.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not validate(username, token):
        print(
            "[docker-hub-inject] Credentials found but Docker Hub auth failed -- PAT may be expired.\n"
            "  Fix: docker login  (re-authenticate with a fresh PAT)\n"
            "  Then re-run: make -C pmoves docker-hub-inject",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.check:
        del token  # break name binding (best-effort; not a memory wipe)
        print("[docker-hub-inject] --check passed: credentials valid")
        return

    env_path = pathlib.Path(args.env_file)
    inject_into_env_file(env_path, username, token)
    del token  # break name binding (best-effort; not a memory wipe)


if __name__ == "__main__":
    main()
