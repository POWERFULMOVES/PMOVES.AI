#!/usr/bin/env python3
"""Re-push funnel-managed values into the Docker MCP Toolkit secret store.

Recovery road for when a Docker Desktop VMM/backend migration wedges or wipes the
MCP secret resolver (observed 2026-08-17 on the 5090: ``ResolverService/GetSecrets``
timed out, a fresh ``mcp-toolkit.db`` and a stuck ``.mcp-toolkit-migration.lock``).
Docker then re-prompts for API keys the operator already entered by hand — the fear
being that unrecoverable keys force a rotation that cascades into GitHub secrets.

This tool removes both the re-typing and the rotation: the current values already
live in ``env.shared`` (funnelled, matching GitHub), so we push them straight into
``docker mcp secret set`` from STDIN — no manual entry, no rotation.

It discovers each ENABLED server's required secrets dynamically from Docker's own
catalog (``~/.docker/mcp/catalogs/docker-mcp.yaml`` keyed by ``registry.yaml``), maps
each Docker secret ``name`` to an ``env.shared`` key via
``pmoves/config/docker_mcp_secret_map.yaml`` (falling back to the injected env-var
name), reads ``env.shared``, and pushes every resolvable non-placeholder value.

Secrets that are not funnel-managed are reported by name as manual gaps — never
guessed. Values are piped via STDIN and masked in output (CodeQL-safe: no value taint).

NOTE: ``docker mcp secret set`` goes through the same resolver that must be healthy —
run this AFTER Docker Desktop has been restarted and the resolver responds.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Sequence

import yaml

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import (
    PROJECT_ROOT,
    force_utf8_stdio,
    is_placeholder,
    parse_env_file,
)

DEFAULT_ENV_SHARED = PROJECT_ROOT / "env.shared"
DEFAULT_KEY_MAPPING = PROJECT_ROOT / "config" / "docker_mcp_secret_map.yaml"


def default_docker_mcp_dir() -> Path:
    """Resolve Docker's MCP config dir (~/.docker/mcp), overridable for tests."""
    import os

    override = os.environ.get("DOCKER_MCP_DIR")
    if override:
        return Path(override)
    return Path.home() / ".docker" / "mcp"


# Bounded to 64 like emit_local_env._reportable_name: an env key is short and
# key-shaped, whereas a value that lands in the key position (malformed bundle)
# is long. The length bound is what separates them, not the charset alone.
_ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


def _safe_name(name: str) -> str:
    """Echo an env/secret KEY NAME only when it is provably a name, not a value.

    Key names are the useful diagnostic here; values never are. Anything that
    does not match the env-key shape came out of a decoded bundle unvalidated,
    so it is replaced rather than echoed -- that covers both a malformed key and
    a value that ended up where a key was expected.
    """
    if _ENV_KEY_RE.fullmatch(name or ""):
        return name
    return "<non-conforming-key>"


@dataclass
class Required:
    """One secret an enabled server needs."""

    server: str
    docker_name: str  # `docker mcp secret set` id (namespaced, e.g. hostinger-mcp-server.api_token)
    env_var: str      # var the server container reads (e.g. APITOKEN)


@dataclass
class Plan:
    pushable: List[tuple[Required, str]] = field(default_factory=list)   # (req, value)
    missing_in_funnel: List[tuple[Required, str]] = field(default_factory=list)  # (req, source_key)
    operator_only: List[Required] = field(default_factory=list)


def load_required(docker_mcp_dir: Path) -> List[Required]:
    """Discover required secrets for ENABLED servers from Docker's catalog+registry."""
    registry_path = docker_mcp_dir / "registry.yaml"
    catalog_path = docker_mcp_dir / "catalogs" / "docker-mcp.yaml"
    if not registry_path.exists():
        raise FileNotFoundError(f"Docker MCP registry not found: {registry_path}")
    if not catalog_path.exists():
        raise FileNotFoundError(f"Docker MCP catalog not found: {catalog_path}")

    enabled = (yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}).get("registry", {})
    catalog = (yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}).get("registry", {})

    required: List[Required] = []
    for server in sorted(enabled):
        spec = catalog.get(server) or {}
        for sec in spec.get("secrets") or []:
            name = sec.get("name")
            env_var = sec.get("env", "")
            if not name:
                continue
            required.append(Required(server=server, docker_name=name, env_var=env_var))
    return required


def load_key_mapping(path: Path) -> Dict[str, str | None]:
    """Load the Docker-secret-NAME -> env.shared-KEY-NAME overrides (may map to None).

    This file holds names on both sides and never a value. It was called a
    "secret map", which is a misnomer that misleads a reader and is also why
    static analysis treated the key names read out of it as secret material
    flowing into a log line.
    """
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("map", {}) if isinstance(data, Mapping) else {}
    return {k: (v if v else None) for k, v in raw.items()} if isinstance(raw, Mapping) else {}


def build_plan(
    required: Sequence[Required],
    key_mapping: Mapping[str, str | None],
    env_shared: Mapping[str, str],
) -> Plan:
    """Resolve each required secret to a source value or classify it as a gap.

    Source key resolution: an explicit map entry wins (``None`` = declared
    operator-only); otherwise fall back to the injected env-var name. A resolved
    key that is absent/placeholder in env.shared is a funnel gap, not a push.
    """
    plan = Plan()
    for req in required:
        if req.docker_name in key_mapping:
            source_key = key_mapping[req.docker_name]
            if source_key is None:
                plan.operator_only.append(req)
                continue
        else:
            source_key = req.env_var or req.docker_name
        value = env_shared.get(source_key, "")
        if is_placeholder(value):
            plan.missing_in_funnel.append((req, source_key))
        else:
            plan.pushable.append((req, value))
    return plan


def _docker_secret_setter(name: str, value: str, *, timeout: int = 30) -> tuple[bool, str | None]:
    """Push one secret via `docker mcp secret set NAME` (value on STDIN, never argv)."""
    try:
        proc = subprocess.run(
            ["docker", "mcp", "secret", "set", name],
            input=value,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "docker CLI not found"
    except subprocess.TimeoutExpired:
        return False, "timeout — is the MCP resolver up? (restart Docker Desktop first)"
    if proc.returncode != 0:
        # stderr may echo the resolver timeout; keep only a short reason, no value.
        err = (proc.stderr or "").strip().splitlines()
        return False, (err[-1] if err else f"exit {proc.returncode}")
    return True, None


def hydrate(
    plan: Plan,
    *,
    dry_run: bool = False,
    setter: Callable[[str, str], tuple[bool, str | None]] = _docker_secret_setter,
) -> tuple[List[str], List[tuple[str, str]]]:
    """Push pushable secrets. Returns (pushed_names, [(name, error)])."""
    pushed: List[str] = []
    errors: List[tuple[str, str]] = []
    if dry_run:
        return [req.docker_name for req, _ in plan.pushable], []
    for req, value in plan.pushable:
        ok, err = setter(req.docker_name, value)
        if ok:
            pushed.append(req.docker_name)
        else:
            errors.append((req.docker_name, err or "unknown error"))
    return pushed, errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-shared", type=Path, default=DEFAULT_ENV_SHARED)
    parser.add_argument(
        "--secret-map",
        dest="key_mapping",
        type=Path,
        default=DEFAULT_KEY_MAPPING,
        help="Docker-secret-NAME -> env.shared-KEY-NAME overrides (names only, never values).",
    )
    parser.add_argument("--docker-mcp-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pushed; touch nothing")
    args = parser.parse_args(argv)
    force_utf8_stdio()

    docker_mcp_dir = args.docker_mcp_dir or default_docker_mcp_dir()
    try:
        required = load_required(docker_mcp_dir)
    except FileNotFoundError as exc:
        print(f"⚠ {exc}", file=sys.stderr)
        return 1

    if not required:
        print("No enabled Docker MCP servers require secrets — nothing to hydrate.")
        return 0

    key_mapping = load_key_mapping(args.key_mapping)
    env_shared = parse_env_file(args.env_shared.expanduser().resolve())
    plan = build_plan(required, key_mapping, env_shared)

    prefix = "[dry-run] " if args.dry_run else ""
    pushed, errors = hydrate(plan, dry_run=args.dry_run)

    if pushed:
        print(f"{prefix}Funnel-fed {len(pushed)} Docker MCP secret(s) from env.shared:")
        for req, _value in plan.pushable:
            # Deliberately prints NO value-derived material -- not even a mask.
            # A first-4/last-4 mask is still partial disclosure of a live secret
            # into CI logs, and the line's job is to say WHICH secret was pushed.
            print(f"  ✔ {req.docker_name}  ({req.server})  ← funnel")
    if plan.missing_in_funnel:
        print("\nⓘ Mapped to a funnel key but absent/placeholder in env.shared "
              "(funnel these keys, then re-run):")
        for req, source_key in plan.missing_in_funnel:
            print(f"  – {req.docker_name}  ({req.server})  ← env.shared:{_safe_name(source_key)}")
    if plan.operator_only:
        print("\n⚠ Operator-provided, NOT funnel-managed — set once manually "
              "(`<value> | docker mcp secret set NAME`) or add to the funnel:")
        for req in plan.operator_only:
            print(f"  – {req.docker_name}  ({req.server})")
    if errors:
        print("\n✖ Failed to push (resolver down? restart Docker Desktop, then re-run):", file=sys.stderr)
        for name, _err in errors:
            # Name only. `err` is whatever `docker mcp secret set` wrote to stderr,
            # and the value was piped into that command -- a resolver that echoes
            # its input would put a live secret in CI logs. The failure mode the
            # operator needs is "which one, and go restart Docker Desktop".
            print(f"  ✖ {name}: push failed (see `docker mcp secret set` output)", file=sys.stderr)
        return 1
    if not pushed and not args.dry_run:
        print("No funnel-managed Docker MCP secrets to push "
              "(all required secrets are operator-provided or already sourced elsewhere).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
