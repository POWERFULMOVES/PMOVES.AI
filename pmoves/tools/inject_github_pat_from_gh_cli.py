#!/usr/bin/env python3
"""Inject GITHUB_PAT into pmoves/env.shared from the local gh CLI's auth token.

Phase 9G agent-automation path: eliminates the operator step of creating a
fine-grained PAT manually. Reads `gh auth token` output (must be authenticated
with scopes `admin:org`, `repo`, `workflow` — checked at runtime) and writes
it to env.shared's GITHUB_PAT key, adding the key if absent.

Usage:
  python pmoves/tools/inject_github_pat_from_gh_cli.py
  python pmoves/tools/inject_github_pat_from_gh_cli.py --env-file custom.env
  python pmoves/tools/inject_github_pat_from_gh_cli.py --check

The --check flag validates gh CLI auth + scope without writing anything.
Exit codes:
  0 - success (or --check passed)
  1 - gh CLI missing or not authenticated
  2 - insufficient token scope
  3 - env file write failure

Scope requirements (from services/github-runner-ctl/github/client.py):
  - admin:org (covers /actions/runners at org and repo level)
  OR
  - repo + workflow (covers repo-level runner queries)

Called via `make -C pmoves gha-runner-ctl-setup-pat`.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys


REQUIRED_ANY_OF = [
    {"admin:org"},
    {"repo", "workflow"},
]


def get_gh_token() -> str:
    """Return current gh CLI OAuth/PAT token, or exit 1 if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except FileNotFoundError:
        print("ERROR: gh CLI not found. Install: https://cli.github.com/", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: gh CLI not authenticated. Run: gh auth login", file=sys.stderr)
        print(f"gh stderr: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    token = result.stdout.strip()
    if not token:
        print("ERROR: gh auth token returned empty.", file=sys.stderr)
        sys.exit(1)
    return token


def get_gh_scopes() -> set[str]:
    """Return the set of scopes on the current gh CLI token."""
    try:
        # `gh auth status` writes scopes to stderr
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return set()
    # Merge stdout + stderr — gh outputs to stderr on some versions
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    match = re.search(r"Token scopes:\s*'?([^'\n]+)'?", output)
    if not match:
        return set()
    raw = match.group(1)
    # Format is typically: 'scope1', 'scope2', 'scope3'
    scopes = {s.strip().strip("'\"") for s in raw.split(",")}
    return {s for s in scopes if s}


def verify_scope(scopes: set[str]) -> None:
    """Exit 2 if scopes don't satisfy any of REQUIRED_ANY_OF."""
    for required in REQUIRED_ANY_OF:
        if required.issubset(scopes):
            print(f"OK: gh token scopes satisfy {sorted(required)} requirement.")
            return
    print(
        f"ERROR: gh token scopes {sorted(scopes)} insufficient.\n"
        f"  Need any of: {[sorted(r) for r in REQUIRED_ANY_OF]}\n"
        f"  Re-auth with: gh auth refresh --scopes admin:org,repo,workflow",
        file=sys.stderr,
    )
    sys.exit(2)


def inject_into_env_file(env_path: pathlib.Path, token: str) -> None:
    """Update GITHUB_PAT=<token> in env_path, creating the file if absent."""
    try:
        text = env_path.read_text() if env_path.exists() else ""
    except OSError as e:
        print(f"ERROR: cannot read {env_path}: {e}", file=sys.stderr)
        sys.exit(3)

    new_line = f"GITHUB_PAT={token}"
    if re.search(r"(?m)^GITHUB_PAT=", text):
        text = re.sub(r"(?m)^GITHUB_PAT=.*$", new_line, text)
        action = "updated"
    else:
        sep = "" if not text or text.endswith("\n") else "\n"
        text = f"{text}{sep}{new_line}\n"
        action = "appended"

    # Atomic write: write to temp then rename — avoids partial writes corrupting
    # env.shared (which holds 90+ credentials) on SIGINT/power loss mid-write.
    tmp_path = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp_path.write_text(text)
        tmp_path.replace(env_path)
    except OSError as e:
        print(f"ERROR: cannot write {env_path}: {e}", file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        sys.exit(3)

    # Print length only, never the token itself
    print(f"OK: GITHUB_PAT {action} in {env_path} (token length={len(token)})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default="env.shared",
        help="Path to env file (default: env.shared, relative to cwd)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate gh CLI auth + scopes only; do not write env file",
    )
    args = parser.parse_args()

    token = get_gh_token()
    scopes = get_gh_scopes()
    verify_scope(scopes)

    if args.check:
        print("OK: --check passed. Token available with sufficient scopes.")
        return

    env_path = pathlib.Path(args.env_file)
    inject_into_env_file(env_path, token)
    print(f"Next: cycle the monitor container so it picks up the new env var:")
    print(f"  make -C pmoves gha-runner-ctl-cycle")


if __name__ == "__main__":
    main()
