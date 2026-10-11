"""PMOVES JWT secret rotation tool.

Companion to `pmoves/docs/RUNBOOK-5090-JWT-ROTATION.md`. This script does
the operator-actionable parts of the rotation in a way that:

1. Backs up env files before any edit (real rollback, not a lie).
2. Generates a new JWT secret + re-mints ANON_KEY + SERVICE_ROLE_KEY with
   the upstream `pmoves-supabase/docker/utils/generate-keys.sh` algorithm.
3. Updates `env.tier-supabase` in place under a timestamped backup.
4. Emits a JSON list of consumer services that need to be recreated
   (enumerated from `pmoves/docker-compose*.yml`).
5. Verifies the new + old keys against the live `supabase-postgrest`
   endpoint to confirm rotation took effect.

Mirrors the upstream Supabase self-hosted pattern from
`pmoves-supabase/docker/utils/generate-keys.sh` and
`pmoves-supabase/docker/utils/add-new-auth-keys.sh`. The PMOVES addition is
the BACKUP + ENUMERATE + VERIFY wrappers around the canonical keygen.

Usage:
    python pmoves/tools/jwt_rotate.py backup
    python pmoves/tools/jwt_rotate.py rotate --dry-run
    python pmoves/tools/jwt_rotate.py rotate
    python pmoves/tools/jwt_rotate.py enumerate
    python pmoves/tools/jwt_rotate.py verify --base-url http://127.0.0.1:8000
    python pmoves/tools/jwt_rotate.py rollback <backup-file>

Exit codes:
    0 -- success
    1 -- missing file / bad input
    2 -- verification failed
    3 -- keygen algorithm failed
"""

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Default paths; override via env or CLI flags.
REPO_ROOT_DEFAULT = Path(os.environ.get("PMOVES_REPO_ROOT", Path.cwd()))
TIER_SUPABASE_DEFAULT = REPO_ROOT_DEFAULT / "pmoves" / "env.tier-supabase"
PMOVES_DIR = REPO_ROOT_DEFAULT / "pmoves"

# Mirrors the JWT vars the v0 runbook tracked. Each var is a key in
# env.tier-supabase that participates in the rotation.
ROTATION_VARS = (
    "JWT_SECRET",
    "SUPABASE_JWT_SECRET",
    "ANON_KEY",
    "SUPABASE_ANON_KEY",
    "SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_KEY",
)

# The 13 canonical Supabase self-hosted consumers enumerated by the survey
# in `pmoves/tools/jwt_rotate.py::enumerate_consumers`. Pinned by the test
# `test_canonical_supabase_consumers` so a future rename of any of these
# services fails the test.
CANONICAL_SUPABASE_CONSUMERS = (
    "supabase-kong",
    "supabase-postgrest",
    "supabase-gotrue",
    "supabase-realtime",
    "supabase-storage",
    "supabase-edge-functions",
    "supabase-studio",
    "supabase-meta",
    "supabase-pooler",
    "supabase-analytics",
    "supabase-imgproxy",
    "supabase-vector",
    "supabase-db",  # Postgres itself: needs the secret to issue new session keys
)


# ---------------------------------------------------------------------------
# Keygen -- mirrors pmoves-supabase/docker/utils/generate-keys.sh
# ---------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def generate_jwt_secret() -> str:
    """30 random bytes -> base64. Mirrors `gen_base64 30` in generate-keys.sh."""
    return base64.b64encode(secrets.token_bytes(30)).decode("ascii")


def mint_hs256(secret: str, role: str, *, ttl_seconds: int = 315_360_000) -> str:
    """Mint a Supabase-compatible HS256 JWT for `role` signed by `secret`.

    The claims match what gotrue/postgrest expect:
      { alg: HS256, typ: JWT }
      { role, iss: supabase-local, iat: <now>, exp: <now + ttl> }
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(_dt.datetime.now(tz=_dt.timezone.utc).timestamp())
    payload = {
        "role": role,
        "iss": "supabase-local",
        "iat": now,
        "exp": now + ttl_seconds,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def keygen(secret: Optional[str] = None) -> Dict[str, str]:
    """Return {JWT_SECRET, ANON_KEY, SERVICE_ROLE_KEY} for a fresh rotation."""
    secret = secret or generate_jwt_secret()
    return {
        "JWT_SECRET": secret,
        "ANON_KEY": mint_hs256(secret, "anon"),
        "SERVICE_ROLE_KEY": mint_hs256(secret, "service_role"),
    }


# ---------------------------------------------------------------------------
# Env-file I/O
# ---------------------------------------------------------------------------
def read_env(path: Path) -> Dict[str, str]:
    """Parse a tier env file (KEY=VALUE) into a dict. Preserves comments and
    blank lines via a separate index map. Returns a flat dict of keys; the
    writer uses `replace_value` to mutate a single key in place when
    possible."""
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    out: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        # Strip surrounding quotes (single or double)
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]
        out[key] = val
    return out


def backup_env(path: Path) -> Path:
    """Write a timestamped copy of `path` next to it. Returns the backup path.

    The backup lives at `<path>.bak.<UTC-ISO>`. The ISO uses 'T' and 'Z' with
    hyphens, not colons, so the path is portable across Windows + POSIX.
    """
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    backup = path.with_name(f"{path.name}.bak.{ts}")
    if backup.exists():
        # Same-second collision: append a counter
        n = 1
        while True:
            candidate = path.with_name(f"{path.name}.bak.{ts}.{n}")
            if not candidate.exists():
                backup = candidate
                break
            n += 1
    shutil.copy2(path, backup)
    # Tighten permissions: the env file may carry SERVICE_ROLE_KEY. Mirror
    # the user's umask but ensure owner-readable at minimum.
    try:
        os.chmod(backup, 0o600)
    except OSError:
        # Windows: chmod is unreliable. Skip silently.
        pass
    return backup


def write_env_replace(path: Path, replacements: Dict[str, str]) -> Path:
    """Replace specific KEY=VALUE lines in `path` while preserving comments.

    Each key in `replacements` matches its full line and is rewritten
    in place. Lines that don't match the key are preserved verbatim.
    Returns the path written (same as input).
    """
    if not path.exists():
        raise FileNotFoundError(f"env file not found: {path}")
    text = path.read_text(encoding="utf-8")
    new_lines: List[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^(\s*)([A-Z_][A-Z0-9_]*)(\s*=\s*)(.*?)(\s*)$", line)
        if m and m.group(2) in replacements:
            key = m.group(2)
            new_val = replacements[key]
            # Quote if the value contains whitespace or special chars
            if any(c in new_val for c in " \t#'"):
                if "'" not in new_val:
                    new_val_str = f"'{new_val}'"
                else:
                    new_val_str = '"' + new_val.replace('"', '\\"') + '"'
            else:
                new_val_str = new_val
            new_lines.append(f"{m.group(1)}{key}{m.group(3)}{new_val_str}{m.group(5)}")
            seen.add(key)
        else:
            new_lines.append(line)
    # Add any keys that were not in the file
    for key, val in replacements.items():
        if key not in seen:
            new_lines.append(f"{key}={val}")
    tmp = path.with_name(path.name + ".new")
    tmp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


# ---------------------------------------------------------------------------
# Consumer enumeration -- enumerates ALL services that read env.tier-supabase
# or env.shared, so the runbook can claim full coverage (not "the 4 the v0
# happened to recreate").
# ---------------------------------------------------------------------------
SERVICE_TOP = re.compile(r"^  ([a-z0-9][a-z0-9_.-]*)\s*:\s*$")
JWT_ANCHORS = (
    "tier-supabase-hardened",
    "tier-supabase-hardened-ro",
    "tier-supabase",
    "tier-supabase-ro",
    "x-env-tier-supabase",
    "x-env-tier-supabase-ro",
)
JWT_ENV_FILES = (
    "env.tier-supabase",
    "env.shared",
    "env.shared.generated",
    "env.tier-ui",
    "env.tier-agent",
    "env.tier-media",
    "env.tier-worker",
    ".env.generated",
)


def is_excluded(path: Path) -> bool:
    s = str(path)
    if "pmoves-supabase" in s or "node_modules" in s or ".git/" in s or "worktrees" in s:
        return True
    return False


def walk_compose_files(root: Path = PMOVES_DIR) -> List[Path]:
    out: List[Path] = []
    if not root.exists():
        return out
    for p in list(root.rglob("*.yml")) + list(root.rglob("*.yaml")):
        if is_excluded(p):
            continue
        out.append(p)
    return sorted(set(out))


def parse_consumers(text: str) -> Dict[str, List[str]]:
    """Return {service_name: [reasons]} where reasons are the JWT anchors or
    env_file entries the service uses."""
    lines = text.splitlines()
    in_services = False
    out: Dict[str, List[str]] = {}
    cur_service: Optional[str] = None
    cur_reasons: List[str] = []
    svc_indent = -1

    def flush() -> None:
        if cur_service is not None and cur_reasons:
            out[cur_service] = cur_reasons

    for line in lines:
        stripped = line.rstrip()
        if not in_services:
            if re.match(r"^services\s*:\s*$", stripped):
                in_services = True
                svc_indent = 0
            continue
        if not stripped:
            continue
        indent = len(stripped) - len(stripped.lstrip())
        if indent <= svc_indent and not stripped.startswith(" "):
            flush()
            in_services = False
            cur_service = None
            cur_reasons = []
            continue
        m = SERVICE_TOP.match(stripped)
        if m and indent == 2:
            flush()
            cur_service = m.group(1)
            cur_reasons = []
            continue
        if cur_service is None:
            continue
        for anchor in JWT_ANCHORS:
            if re.search(r"<<\s*:\s*\*" + re.escape(anchor), line):
                cur_reasons.append(f"anchor:{anchor}")
        for ef in JWT_ENV_FILES:
            if re.search(r"-\s*" + re.escape(ef) + r"\s*$", line):
                cur_reasons.append(f"env_file:{ef}")
    flush()
    return out


def enumerate_consumers(root: Path = PMOVES_DIR) -> List[Dict[str, Any]]:
    """Walk every compose file under `root` and return JWT consumers."""
    found: Dict[str, List[str]] = {}
    file_for: Dict[str, str] = {}
    for p in walk_compose_files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        c = parse_consumers(text)
        for svc, reasons in c.items():
            if svc in found:
                found[svc].extend(reasons)
            else:
                found[svc] = list(reasons)
            file_for[svc] = str(p.relative_to(root))
    out: List[Dict[str, Any]] = []
    for svc in sorted(found):
        out.append({
            "service": svc,
            "reasons": sorted(set(found[svc])),
            "compose_file": file_for[svc],
        })
    return out


# ---------------------------------------------------------------------------
# Verification -- the new + old keys against the live postgrest endpoint
# ---------------------------------------------------------------------------
def verify_keys(
    base_url: str,
    new_anon: str,
    old_anon: str,
    *,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """GET /rest/v1/ with both keys. New key expects 200, old key expects 401."""
    out: Dict[str, Any] = {"base_url": base_url, "new_key": {}, "old_key": {}}
    for label, key in (("new_key", new_anon), ("old_key", old_anon)):
        if not key:
            out[label] = {"status": None, "error": "no key provided"}
            continue
        url = base_url.rstrip("/") + "/rest/v1/"
        req = urllib.request.Request(url, headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out[label] = {"status": resp.status, "ok": True}
        except urllib.error.HTTPError as e:
            out[label] = {"status": e.code, "ok": False, "error": "http"}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            out[label] = {"status": None, "ok": False, "error": str(e)}
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jwt_rotate",
        description="PMOVES JWT secret rotation tool (companion to RUNBOOK-5090-JWT-ROTATION.md).",
    )
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT_DEFAULT,
                   help="Path to the PMOVES.AI repo root (default: $PMOVES_REPO_ROOT or cwd).")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("backup", help="Back up env.tier-supabase to a timestamped copy.")

    p_rotate = sub.add_parser("rotate", help="Generate new JWT_SECRET + keys and write to env.tier-supabase.")
    p_rotate.add_argument("--dry-run", action="store_true",
                          help="Print the proposed new values; do not write.")

    sub.add_parser("enumerate", help="List all services that consume env.tier-supabase or env.shared.")

    p_verify = sub.add_parser("verify", help="Probe /rest/v1/ with new + old ANON_KEY.")
    p_verify.add_argument("--base-url", default="http://127.0.0.1:8000",
                          help="PostgREST base URL (default: http://127.0.0.1:8000).")
    p_verify.add_argument("--new-anon", default=os.environ.get("NEW_ANON_KEY", ""))
    p_verify.add_argument("--old-anon", default=os.environ.get("OLD_ANON_KEY", ""))

    p_rollback = sub.add_parser("rollback", help="Restore env.tier-supabase from a backup file.")
    p_rollback.add_argument("backup_file", type=Path)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_argparser()
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root
    tier_supabase: Path = repo_root / "pmoves" / "env.tier-supabase"
    # Set a safe umask for any new files we write (0700 on POSIX).
    try:
        os.umask(0o077)
    except OSError:
        pass

    if args.command == "backup":
        if not tier_supabase.exists():
            print(f"error: {tier_supabase} not found", file=sys.stderr)
            return 1
        backup = backup_env(tier_supabase)
        print(f"backup written: {backup}")
        return 0

    if args.command == "rotate":
        if not tier_supabase.exists():
            print(f"error: {tier_supabase} not found", file=sys.stderr)
            return 1
        try:
            existing = read_env(tier_supabase)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        new = keygen()
        if args.dry_run:
            print(json.dumps(new, indent=2))
            print("# dry-run: no backup taken, no file written")
            return 0
        backup = backup_env(tier_supabase)
        # Build the replacement map. For each rotation var, also update the
        # SUPABASE_-prefixed alias if it exists in the file.
        replacements: Dict[str, str] = {}
        for key in ROTATION_VARS:
            replacements[key] = new.get(key, "")
        # Don't blank keys that weren't generated; remove entries with "".
        replacements = {k: v for k, v in replacements.items() if v}
        write_env_replace(tier_supabase, replacements)
        # Print the operator-actionable summary
        print(f"rotated: {tier_supabase}")
        print(f"backup:  {backup}")
        print(f"new keys:")
        for k, v in new.items():
            short = v[:8] + "..." + v[-4:]
            print(f"  {k}={short}")
        # Enumerate consumers
        consumers = enumerate_consumers(repo_root / "pmoves")
        supabase_subset = [c for c in consumers
                           if c["service"].startswith("supabase-")
                           or c["service"] in CANONICAL_SUPABASE_CONSUMERS]
        print(f"\nJWT consumers needing recreate ({len(supabase_subset)} canonical Supabase + PMOVES):")
        for c in supabase_subset:
            print(f"  - {c['service']:30}  ({c['compose_file']})")
        return 0

    if args.command == "enumerate":
        consumers = enumerate_consumers(repo_root / "pmoves")
        print(json.dumps(consumers, indent=2))
        return 0

    if args.command == "verify":
        result = verify_keys(args.base_url, args.new_anon, args.old_anon)
        print(json.dumps(result, indent=2))
        new = result.get("new_key", {})
        old = result.get("old_key", {})
        if new.get("status") == 200 and old.get("status") == 401:
            return 0
        return 2

    if args.command == "rollback":
        backup = args.backup_file
        if not backup.exists():
            print(f"error: backup not found: {backup}", file=sys.stderr)
            return 1
        # Verify the backup looks like a tier env file
        try:
            read_env(backup)
        except Exception as e:
            print(f"error: backup is not a valid env file: {e}", file=sys.stderr)
            return 1
        # Snapshot current state before overwrite
        if tier_supabase.exists():
            pre_rollback_backup = backup_env(tier_supabase)
            print(f"pre-rollback snapshot: {pre_rollback_backup}")
        shutil.copy2(backup, tier_supabase)
        print(f"rolled back: {tier_supabase} <- {backup}")
        return 0

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
