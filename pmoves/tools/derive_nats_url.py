#!/usr/bin/env python3
"""Keep NATS_URL's credential in step with NATS_USER / NATS_PASSWORD in env.shared.

NATS_URL is stored as a literal URL with the user:password embedded (see
env.shared.example), and nothing re-derived it. Rotating NATS_PASSWORD therefore
left NATS_URL carrying the OLD password: recreate the broker with the new one and
every client that dials NATS_URL is refused -- a full bus outage, and silent until
the recreate. This step rebuilds only the userinfo, keeping the URL's own scheme,
host and port.

Only a URL that dials THIS node's broker is rewritten. NATS_PASSWORD is the local
broker's password; a node whose NATS_URL points at the fleet hub (or any other
remote broker) authenticates with that broker's credential, and overwriting it
with the local one would silently drop the node off the bus. Remote hosts are
therefore reported and left alone.

Rules:
  * NATS_PASSWORD or NATS_URL absent -> skipped (never invents a URL).
  * NATS_URL without userinfo (creds-file / account auth) -> skipped.
  * NATS_URL host not local (see _is_local_broker) -> "remote", left alone.
  * NATS_USER absent -> "nats" (the compose default).
  * The password is percent-encoded for the URL.
  * Writes through bootstrap_env.rotate_secret -- the same surgical single-line
    writer `make secrets-rotate` uses. Values are never printed.

Run via `make -C pmoves secrets-derive-nats-url`; secrets-rotate and
secrets-funnel call it before chit-export.

Tier files (--check / --promote):
  Compose loads env.shared and then a service's tier file, and the later file
  wins. A tier file still holding an old NATS_URL therefore overrides the fresh
  one in env.shared for every service on that tier. secrets-funnel-sync does not
  write every tier (env.tier-ui is one it leaves alone), so after a rotation the
  NATS keys are mirrored from env.shared into each env.tier-* that DECLARES
  them. A tier that does not declare a key never gains it: that would hand the
  bus credential to services that have no use for it.
  --check   prints "<KEY> <file> match|MISMATCH", exits 1 on any mismatch.
  --promote rewrites the mismatched lines (same surgical writer).
"""

from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

PMOVES = Path(__file__).resolve().parents[1]
REPO_ROOT = PMOVES.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pmoves.tools._secrets_common import normalize_env_value, parse_env_file  # noqa: E402

ENV_SHARED = PMOVES / "env.shared"

# Hosts that resolve to the broker this node's NATS_PASSWORD configures: the
# compose service / container name, and the host loopback forms. Any loopback
# IP literal also counts. Private and tailnet ranges deliberately do NOT: the
# fleet hub lives on one. A node that dials its own broker by another name
# lists it in NATS_LOCAL_BROKER_HOSTS (comma-separated).
LOCAL_BROKER_HOSTS = frozenset(
    {"nats", "pmoves-nats-1", "localhost", "127.0.0.1", "::1", "host.docker.internal"}
)


def _is_local_broker(host: str) -> bool:
    host = host.lower()
    extra = {h.strip().lower() for h in os.environ.get("NATS_LOCAL_BROKER_HOSTS", "").split(",") if h.strip()}
    if host in LOCAL_BROKER_HOSTS or host in extra:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _rotate_secret():
    name = "pmoves_bootstrap_env"
    if name in sys.modules:
        return sys.modules[name].rotate_secret
    spec = importlib.util.spec_from_file_location(name, PMOVES / "scripts" / "bootstrap_env.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load pmoves/scripts/bootstrap_env.py")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: bootstrap_env's @dataclass resolves its own module
    # through sys.modules at class-creation time.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.rotate_secret


def derive(env_path: Path = ENV_SHARED) -> str:
    """Return "updated", "unchanged", "skipped" or "remote". Never prints a value."""
    vals = parse_env_file(env_path)
    password = normalize_env_value(vals.get("NATS_PASSWORD", ""))
    url = normalize_env_value(vals.get("NATS_URL", ""))
    if not password or not url:
        return "skipped"
    parts = urlsplit(url)
    if not parts.netloc or "@" not in parts.netloc or not parts.hostname:
        return "skipped"
    if not _is_local_broker(parts.hostname):
        return "remote"
    user = normalize_env_value(vals.get("NATS_USER", "")) or "nats"
    host = parts.hostname
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    netloc = f"{quote(user, safe='')}:{quote(password, safe='')}@{host}"
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    new_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    if new_url == url:
        return "unchanged"
    _rotate_secret()("NATS_URL", value=new_url, env_path=env_path)
    return "updated"


NATS_KEYS = ("NATS_URL", "NATS_USER", "NATS_PASSWORD")
# Live tier files only: env.tier-<name>, no .example / .urlencoded / backups.
_TIER_NAME = re.compile(r"^env\.tier-[A-Za-z0-9_-]+$")


def tier_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("env.tier-*") if _TIER_NAME.match(p.name) and p.is_file())


def tier_status(env_path: Path = ENV_SHARED) -> list[tuple[str, Path, bool]]:
    """(key, tier file, matches env.shared) for each NATS key a tier declares.

    A key env.shared leaves empty has no source of truth and is not compared.
    """
    shared = parse_env_file(env_path)
    rows = []
    for tier in tier_files(env_path.parent):
        declared = parse_env_file(tier)
        for key in NATS_KEYS:
            want = normalize_env_value(shared.get(key, ""))
            if key in declared and want:
                rows.append((key, tier, normalize_env_value(declared[key]) == want))
    return rows


def promote(env_path: Path = ENV_SHARED) -> list[tuple[str, Path]]:
    """Copy env.shared's NATS keys over each mismatched tier line. Never prints a value."""
    shared = parse_env_file(env_path)
    fixed = []
    for key, tier, ok in tier_status(env_path):
        if not ok:
            _rotate_secret()(key, value=normalize_env_value(shared[key]), env_path=tier)
            fixed.append((key, tier))
    return fixed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-derive NATS_URL credentials from NATS_USER/NATS_PASSWORD.")
    ap.add_argument("--env-file", type=Path, default=ENV_SHARED)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare tier files' NATS keys with env.shared")
    mode.add_argument("--promote", action="store_true", help="mirror env.shared's NATS keys into tier files")
    args = ap.parse_args(argv)
    if args.check:
        rows = tier_status(args.env_file)
        for key, tier, ok in rows:
            print(f"nats-tier-check: {key} {tier.name} {'match' if ok else 'MISMATCH'}")
        if not rows:
            print("nats-tier-check: no tier file declares a NATS key")
        return 0 if all(ok for _, _, ok in rows) else 1
    if args.promote:
        fixed = promote(args.env_file)
        for key, tier in fixed:
            print(f"nats-tier-promote: {key} -> {tier.name} (value not shown)")
        if not fixed:
            print("nats-tier-promote: every tier file already matches env.shared")
        return 0
    result = derive(args.env_file)
    messages = {
        "updated": "NATS_URL credentials re-derived from NATS_USER/NATS_PASSWORD (value not shown)",
        "unchanged": "NATS_URL already consistent with NATS_USER/NATS_PASSWORD",
        "skipped": "NATS_URL derive skipped (no NATS_PASSWORD, no NATS_URL, or URL carries no userinfo)",
        "remote": (
            "NATS_URL points at a non-local broker; its credential is that broker's, left unchanged "
            "(if it is in fact this node's broker, add the host to NATS_LOCAL_BROKER_HOSTS)"
        ),
    }
    print(f"derive-nats-url: {messages[result]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
