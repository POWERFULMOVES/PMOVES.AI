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
DEFAULT_SECRET_MAP = PROJECT_ROOT / "config" / "docker_mcp_secret_map.yaml"


def default_docker_mcp_dir() -> Path:
    """Resolve Docker's MCP config dir (~/.docker/mcp), overridable for tests."""
    import os

    override = os.environ.get("DOCKER_MCP_DIR")
    if override:
        return Path(override)
    return Path.home() / ".docker" / "mcp"


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


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


def load_secret_map(path: Path) -> Dict[str, str | None]:
    """Load the Docker-secret-name -> env.shared-key overrides (may map to None)."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("map", {}) if isinstance(data, Mapping) else {}
    return {k: (v if v else None) for k, v in raw.items()} if isinstance(raw, Mapping) else {}


def build_plan(
    required: Sequence[Required],
    secret_map: Mapping[str, str | None],
    env_shared: Mapping[str, str],
) -> Plan:
    """Resolve each required secret to a source value or classify it as a gap.

    Source key resolution: an explicit map entry wins (``None`` = declared
    operator-only); otherwise fall back to the injected env-var name. A resolved
    key that is absent/placeholder in env.shared is a funnel gap, not a push.
    """
    plan = Plan()
    for req in required:
        if req.docker_name in secret_map:
            source_key = secret_map[req.docker_name]
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
    parser.add_argument("--secret-map", type=Path, default=DEFAULT_SECRET_MAP)
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

    secret_map = load_secret_map(args.secret_map)
    env_shared = parse_env_file(args.env_shared.expanduser().resolve())
    plan = build_plan(required, secret_map, env_shared)

    prefix = "[dry-run] " if args.dry_run else ""
    pushed, errors = hydrate(plan, dry_run=args.dry_run)

    if pushed:
        print(f"{prefix}Funnel-fed {len(pushed)} Docker MCP secret(s) from env.shared:")
        for req, value in plan.pushable:
            print(f"  ✔ {req.docker_name}  ({req.server}) = {_masked(value)}")
    if plan.missing_in_funnel:
        print("\nⓘ Mapped to a funnel key but absent/placeholder in env.shared "
              "(funnel these keys, then re-run):")
        for req, source_key in plan.missing_in_funnel:
            print(f"  – {req.docker_name}  ({req.server})  ← env.shared:{source_key}")
    if plan.operator_only:
        print("\n⚠ Operator-provided, NOT funnel-managed — set once manually "
              "(`<value> | docker mcp secret set NAME`) or add to the funnel:")
        for req in plan.operator_only:
            print(f"  – {req.docker_name}  ({req.server})")
    if errors:
        print("\n✖ Failed to push (resolver down? restart Docker Desktop, then re-run):", file=sys.stderr)
        for name, err in errors:
            print(f"  ✖ {name}: {err}", file=sys.stderr)
        return 1
    if not pushed and not args.dry_run:
        print("No funnel-managed Docker MCP secrets to push "
              "(all required secrets are operator-provided or already sourced elsewhere).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
