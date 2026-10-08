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
  * NATS_URL host not in LOCAL_BROKER_HOSTS -> "remote", left alone.
  * NATS_USER absent -> "nats" (the compose default).
  * The password is percent-encoded for the URL.
  * Writes through bootstrap_env.rotate_secret -- the same surgical single-line
    writer `make secrets-rotate` uses. Values are never printed.

Run via `make -C pmoves secrets-derive-nats-url`; secrets-rotate and
secrets-funnel call it before chit-export.
"""

from __future__ import annotations

import argparse
import importlib.util
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
# compose service / container name, and the host loopback forms.
LOCAL_BROKER_HOSTS = frozenset(
    {"nats", "pmoves-nats-1", "localhost", "127.0.0.1", "::1", "host.docker.internal"}
)


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
    if parts.hostname.lower() not in LOCAL_BROKER_HOSTS:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-derive NATS_URL credentials from NATS_USER/NATS_PASSWORD.")
    ap.add_argument("--env-file", type=Path, default=ENV_SHARED)
    args = ap.parse_args(argv)
    result = derive(args.env_file)
    messages = {
        "updated": "NATS_URL credentials re-derived from NATS_USER/NATS_PASSWORD (value not shown)",
        "unchanged": "NATS_URL already consistent with NATS_USER/NATS_PASSWORD",
        "skipped": "NATS_URL derive skipped (no NATS_PASSWORD, no NATS_URL, or URL carries no userinfo)",
        "remote": "NATS_URL points at a non-local broker; its credential is that broker's, left unchanged",
    }
    print(f"derive-nats-url: {messages[result]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
