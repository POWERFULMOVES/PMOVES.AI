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
  python pmoves/tools/inject_github_pat_from_gh_cli.py --refresh-if-stale

The --check flag validates gh CLI auth + scope without writing anything.

The --refresh-if-stale flag is the scheduled/idempotent mode (see
`make -C pmoves gha-token-refresh`): it only rewrites env.shared when the
STORED GITHUB_PAT is missing, differs from the current keyring token, or fails
a BEHAVIORAL validation (can it actually reach `actions/runners`?). This is the
durable fix for the stale-env-token poison — a stored snapshot drifts from the
keyring over time and `gh` inside make recipes prefers the stale env var. Run on
a host-side schedule so the snapshot never goes stale.

Behavioral validation hits `repos/<owner>/<repo>/actions/runners` (repo-scoped),
NOT `/user` — a gist-only/wrong-scope token passes `/user` and gives a false
"valid". The token under test is passed via an env-isolated `GH_TOKEN` (with any
ambient GH_TOKEN/GITHUB_TOKEN stripped) so the validation can't be fooled by a
poisoned ambient env var.

Exit codes:
  0  - success (or --check passed, or --refresh-if-stale found nothing to do)
  1  - gh CLI missing or not authenticated
  2  - insufficient token scope (string check) or keyring token fails behavioral validation
  3  - env file write failure
  75 - (--refresh-if-stale only) a refresh WAS performed; caller should run
       secrets-funnel-sync to propagate. Distinct code lets the make target
       skip the funnel re-run on the common no-op tick.

Scope requirements (from services/github-runner-ctl/github/client.py):
  - admin:org (covers /actions/runners at org and repo level)
  OR
  - repo + workflow (covers repo-level runner queries)

Called via `make -C pmoves gha-runner-ctl-setup-pat` (one-shot) and
`make -C pmoves gha-token-refresh` (idempotent/scheduled).
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess
import sys


REQUIRED_ANY_OF = [
    {"admin:org"},
    {"repo", "workflow"},
]

# Distinct exit code meaning "a refresh was performed" — see module docstring.
EXIT_REFRESHED = 75

DEFAULT_REPO = "POWERFULMOVES/PMOVES.AI"


def get_gh_token() -> str:
    """Return the gh CLI's KEYRING token, or exit 1 if unavailable.

    Env-isolated: ambient GH_TOKEN/GITHUB_TOKEN are stripped before calling
    `gh auth token`, because gh PREFERS those env vars over the keyring. A stale
    env token is exactly what we must NOT snapshot — we want the durable keyring
    token. (This is the root cause of the runner-bootstrap poison saga.)
    """
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
            env=env,
        )
    except FileNotFoundError:
        print("ERROR: gh CLI not found. Install: https://cli.github.com/", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("ERROR: gh CLI not authenticated. Run: gh auth login", file=sys.stderr)
        print(f"gh stderr: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    token = result.stdout.strip()
    if not token:
        print("ERROR: gh auth token returned empty.", file=sys.stderr)
        sys.exit(1)
    return token


def get_gh_scopes() -> set[str]:
    """Return the set of scopes on the gh CLI KEYRING token.

    Env-isolated for the same reason as get_gh_token(): without stripping
    GH_TOKEN/GITHUB_TOKEN, `gh auth status` reports the AMBIENT env token's
    scopes (which may be a stale gist-only poison), not the keyring token we
    actually snapshot — producing a false "insufficient scope" failure.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    try:
        # `gh auth status` writes scopes to stderr
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
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


def validate_token_behaviorally(token: str, repo: str) -> bool:
    """Return True if `token` can actually query the repo's actions/runners.

    Repo-scoped behavioral check — NOT `/user` (which a gist-only token passes,
    giving a false positive). The token is injected via an env-isolated
    GH_TOKEN with any ambient GH_TOKEN/GITHUB_TOKEN stripped, so a poisoned
    ambient env var can't mask a bad token under test (the exact failure mode
    that caused the runner-bootstrap saga).
    """
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    env["GH_TOKEN"] = token
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/runners", "--jq", ".total_count"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except FileNotFoundError:
        return False
    except subprocess.SubprocessError:
        return False
    return result.returncode == 0


def read_stored_pat(env_path: pathlib.Path) -> str | None:
    """Return the GITHUB_PAT value currently stored in env_path, or None."""
    if not env_path.exists():
        return None
    try:
        text = env_path.read_text()
    except OSError:
        return None
    match = re.search(r"(?m)^GITHUB_PAT=(.*)$", text)
    return match.group(1).strip() if match else None


def inject_into_env_file(env_path: pathlib.Path, token: str, quiet: bool = False) -> None:
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
    # Also chmod 0o600 so the file is owner-only readable (holds PAT + all other creds).
    tmp_path = env_path.with_suffix(env_path.suffix + ".tmp")
    try:
        tmp_path.write_text(text)
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            # chmod is a no-op on Windows filesystems — not fatal
            pass
        tmp_path.replace(env_path)
    except OSError as e:
        print(f"ERROR: cannot write {env_path}: {e}", file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        sys.exit(3)

    if not quiet:
        # Print length only, never the token itself
        print(f"OK: GITHUB_PAT {action} in {env_path} (token length={len(token)})")


def log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg)


def refresh_if_stale(env_path: pathlib.Path, repo: str, quiet: bool) -> None:
    """Idempotent/scheduled refresh.

    Exit 0 if the stored GITHUB_PAT is current + behaviorally valid (no-op).
    Exit EXIT_REFRESHED (75) if a refresh was written (caller funnel-syncs).
    Exit 2 if the keyring token itself can't reach actions/runners.
    """
    keyring = get_gh_token()
    stored = read_stored_pat(env_path)

    if stored and stored == keyring and validate_token_behaviorally(stored, repo):
        log(
            f"OK: stored GITHUB_PAT is current and valid "
            f"(actions/runners reachable for {repo}) - no refresh needed.",
            quiet,
        )
        return  # exit 0

    # Stored is missing / drifted from keyring / behaviorally invalid.
    # Validate the keyring token BEHAVIORALLY before snapshotting it, so we never
    # write a wrong-scoped token into env.shared (the string-scope check alone
    # missed this on fine-grained PATs).
    if not validate_token_behaviorally(keyring, repo):
        print(
            f"ERROR: keyring token cannot reach repos/{repo}/actions/runners — "
            f"refusing to snapshot it.\n"
            f"  Re-auth with: gh auth refresh --scopes admin:org,repo,workflow",
            file=sys.stderr,
        )
        sys.exit(2)

    reason = (
        "missing" if stored is None
        else "drifted-from-keyring" if stored != keyring
        else "failed-behavioral-validation"
    )
    log(f"STALE ({reason}): refreshing GITHUB_PAT from keyring...", quiet)
    inject_into_env_file(env_path, keyring, quiet)
    log(
        "REFRESHED: GITHUB_PAT re-snapshotted. Caller should run secrets-funnel-sync "
        "to propagate into env.tier-* (the make target does this on exit 75).",
        quiet,
    )
    sys.exit(EXIT_REFRESHED)


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
    parser.add_argument(
        "--refresh-if-stale",
        action="store_true",
        help="Idempotent/scheduled mode: only rewrite when the stored GITHUB_PAT "
        "is missing/drifted/behaviorally-invalid. Exit 75 if a refresh was done.",
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO),
        help=f"owner/repo for the behavioral actions/runners check (default: "
        f"$GITHUB_REPOSITORY or {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error output (for scheduled/cron runs)",
    )
    args = parser.parse_args()

    env_path = pathlib.Path(args.env_file)

    if args.refresh_if_stale:
        # Scheduled path: behavioral validation IS the gate (more reliable than
        # the string-scope parse), so we don't pre-check scopes here.
        refresh_if_stale(env_path, args.repo, args.quiet)
        return

    token = get_gh_token()

    # Behavioral validation is authoritative — it works for fine-grained PATs
    # that report NO classic scopes in `gh auth status` yet CAN reach
    # actions/runners. The string-scope check is only a fallback to produce a
    # clearer "re-auth with these scopes" message when the token genuinely can't.
    if validate_token_behaviorally(token, args.repo):
        print(f"OK: keyring token can reach repos/{args.repo}/actions/runners.")
    else:
        scopes = get_gh_scopes()
        verify_scope(scopes)  # exits 2 with re-auth guidance if scopes also fail
        # String scopes looked sufficient but the endpoint was unreachable.
        print(
            f"ERROR: token scopes {sorted(scopes)} look sufficient but "
            f"repos/{args.repo}/actions/runners was unreachable (network? repo access?).",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.check:
        print("OK: --check passed. Token can perform runner-ctl queries.")
        return

    inject_into_env_file(env_path, token, args.quiet)
    print("Next: cycle the monitor container so it picks up the new env var:")
    print("  make -C pmoves gha-runner-ctl-cycle")


if __name__ == "__main__":
    main()
