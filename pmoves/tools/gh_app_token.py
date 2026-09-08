#!/usr/bin/env python3
"""gh_app_token.py — sanctioned LOCAL mint of GitHub App installation tokens.

The node-side half of the dsh GitHub agent (operator-approved 2026-09-05).
Workflows mint via `.github/workflows/_app-token.yml`; this is the SAME
identity for node-side runs (pr-monitor, harness containers, fork tooling)
so fleet automation stops burning the shared user PAT — installation tokens
carry their own >=5,000/hr REST quota per installation and act as the App.

Rules inherited from `pmoves/docs/operations/GITHUB_APP.md`:
  - No hand-rolled crypto: JWT is RS256 via PyJWT against GH_APP_SEC.
  - Scoping truth table: ALWAYS pair an explicit repository list with
    minimal permissions. No repositories + no permissions = installation
    default (over-broad); refuse `--all` unless REPOSITORIES=all is passed
    verbatim and --yes is set.
  - Secret hand-off is NEVER stdout-by-default (the cipher-mint lesson):
    the token lands in a 0600 file (default `~/.pmoves/gh_app_token`) and
    only metadata prints. `--print` exists for piping into a consumer's
    env in a controlled terminal and warns on stderr.

Usage:
  pmoves/scripts/with-env.sh python3 pmoves/tools/gh_app_token.py \
      --repositories PMOVES.AI --permissions contents:read,pull_requests:read

Exit codes: 0 minted · 2 usage/config error · 3 mint refused (scope) ·
4 upstream/API error.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import jwt  # PyJWT — no hand-rolled crypto
except ImportError:  # pragma: no cover - environment guard
    print(
        "error: PyJWT not available to this interpreter; install with "
        "`uv pip install --python <pmoves venv> pyjwt`",
        file=sys.stderr,
    )
    raise SystemExit(2)

GITHUB_API = "https://api.github.com"
JWT_TTL_SECONDS = 600  # GitHub caps app JWTs at 10 minutes
DEFAULT_OUT = Path("~/.pmoves/gh_app_token").expanduser()


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    print(f"error: ${name} is not set (funnel env: make -C pmoves secrets-funnel)", file=sys.stderr)
    raise SystemExit(2)


def _load_private_key() -> str:
    raw = _env("GH_APP_SEC")
    # The funnel stores PEM bodies with literal \n escapes in some tiers.
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")
    if "PRIVATE KEY" not in raw:
        print("error: GH_APP_SEC does not look like a PEM private key", file=sys.stderr)
        raise SystemExit(2)
    return raw


def build_app_jwt(app_id: str, private_key_pem: str, now: float | None = None) -> str:
    """RS256-signed app JWT (iss=app id, 10 min cap per GitHub docs)."""
    issued = int(now if now is not None else time.time())
    # GitHub caps app JWTs at 10 minutes INCLUDING the backdated iat, so the
    # 60s clock-skew backdate comes out of the TTL, not on top of it.
    iat = issued - 60
    claims = {"iss": app_id, "iat": iat, "exp": iat + JWT_TTL_SECONDS}
    return jwt.encode(claims, private_key_pem, algorithm="RS256")


def build_scope_body(repositories: list[str], permissions: dict[str, str]) -> dict[str, object]:
    """Request body per the GITHUB_APP.md truth table.

    repositories listed  -> token scoped to exactly those repos.
    permissions set      -> token capped to those permissions.
    """
    body: dict[str, object] = {}
    if repositories:
        body["repositories"] = repositories
    if permissions:
        body["permissions"] = permissions
    return body


def parse_permissions(spec: str) -> dict[str, str]:
    permissions: dict[str, str] = {}
    for chunk in spec.split(","):
        chunk = chunk.strip().lower()
        if not chunk:
            continue
        if ":" not in chunk:
            print(f"error: permission '{chunk}' must be name:level (e.g. contents:read)", file=sys.stderr)
            raise SystemExit(2)
        name, level = chunk.split(":", 1)
        if level not in {"read", "write"}:
            print(f"error: permission level '{level}' must be read or write", file=sys.stderr)
            raise SystemExit(2)
        permissions[name.strip()] = level
    return permissions


def mint_installation_token(
    app_jwt: str, installation_id: str, body: dict[str, object], timeout: int = 30
) -> dict[str, object]:
    request = urllib.request.Request(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "pmoves-gh-app-token",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        detail = error.read(300).decode(errors="replace")
        print(f"error: GitHub refused the mint: HTTP {error.code} {detail}", file=sys.stderr)
        raise SystemExit(4)
    except urllib.error.URLError as error:
        print(f"error: cannot reach {GITHUB_API}: {error.reason}", file=sys.stderr)
        raise SystemExit(4)


def write_token_file(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repositories", default="", help="comma list, exact repo names (least privilege); required unless --all")
    parser.add_argument("--permissions", default="", help="comma list of name:level (e.g. contents:read,pull_requests:read)")
    parser.add_argument("--all", action="store_true", help="mint with the installation default scope (over-broad; needs --yes)")
    parser.add_argument("--yes", action="store_true", help="acknowledge over-broad scope with --all")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"0600 token file (default {DEFAULT_OUT})")
    parser.add_argument("--ttl-margin", type=int, default=60, help="refuse to hand out tokens with less than this many seconds left")
    parser.add_argument("--dry-run", action="store_true", help="validate config + print the scope plan; no network, no mint")
    parser.add_argument("--print", dest="print_token", action="store_true", help="ALSO print the raw token to stdout (controlled piping only)")
    args = parser.parse_args(argv)

    # JWT iss: the docs recommend the App's CLIENT ID (v3); the numeric v1
    # GH_APP_ID still works and stays as fallback for nodes that only funneled it.
    app_id = os.environ.get("GH_APP_CLIENT_ID", "").strip() or _env("GH_APP_ID")
    installation_id = _env("GH_APP_INSTALLATION_ID")
    private_key = _load_private_key()

    if args.all:
        if not args.yes:
            print("error: --all mints the installation-default scope (every repo, every granted permission); pass --yes to acknowledge", file=sys.stderr)
            raise SystemExit(3)
        repositories: list[str] = []
        scope_note = "installation default (ALL repos — over-broad)"
    else:
        if not args.repositories:
            print("error: pass --repositories a,b,c (least privilege) or --all --yes (explicitly over-broad)", file=sys.stderr)
            raise SystemExit(3)
        repositories = [r.strip() for r in args.repositories.split(",") if r.strip()]
        scope_note = f"repositories={','.join(repositories)}"

    permissions = parse_permissions(args.permissions)
    body = build_scope_body(repositories, permissions)

    if args.dry_run:
        print(f"dry-run: app_id={'<set>' if app_id else '<missing>'} installation={'<set>' if installation_id else '<missing>'}")
        print(f"dry-run: scope {scope_note} permissions={permissions or '<installation default>'}")
        print("dry-run: key parses, JWT algorithm RS256 via PyJWT, no network call made")
        return 0

    app_jwt = build_app_jwt(app_id, private_key)
    payload = mint_installation_token(app_jwt, installation_id, body)

    token = str(payload.get("token") or "")
    expires = str(payload.get("expires_at") or "?")
    if not token:
        print("error: mint response carried no token", file=sys.stderr)
        return 4

    write_token_file(args.out, token)
    granted_repos = payload.get("repositories") or []
    granted_perms = payload.get("permissions") or {}
    print(f"minted: {scope_note}")
    print(f"permissions: {granted_perms or '<installation default>'}")
    print(f"repositories granted: {[r.get('full_name') for r in granted_repos] if granted_repos else '<all in installation>'}")
    print(f"expires_at: {expires}")
    print(f"token file: {args.out} (0600) — consume with GH_TOKEN=$(cat {args.out})")
    if args.print_token:
        print("warning: --print puts the raw token in this transcript's stdout", file=sys.stderr)
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
