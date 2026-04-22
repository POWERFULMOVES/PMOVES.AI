#!/usr/bin/env python3
"""Overlay real secrets from local.env into env.shared for empty/placeholder keys.

The GitHub Actions ``sync-secrets-local.yml`` workflow writes real API keys to
``$APPDATA/pmoves/secrets/local.env`` (Windows) or
``$XDG_CONFIG_HOME/pmoves/secrets/local.env`` (Unix).  This script merges those
values into ``env.shared`` **only** for keys that are currently empty or contain
placeholder values, preserving any values already set.

Intended to run **before** ``chit-export`` so the CHIT bundle contains real
credentials that flow through the rest of the secrets-funnel pipeline.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Sequence

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from pmoves.tools._secrets_common import (
    PROJECT_ROOT,
    is_placeholder,
    local_env_path as _default_local_env,
    parse_env_file as _parse_env,
    validate_secret_value,
)

DEFAULT_ENV_SHARED = PROJECT_ROOT / "env.shared"


def _masked(value: str) -> str:
    if len(value) < 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def _write_updates(env_path: Path, updates: Dict[str, str]) -> None:
    """Write updated values back into the env file, preserving structure."""
    lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Build index of key -> line number
    index: Dict[str, int] = {}
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        index[key] = idx

    validated_updates = {}
    for key, value in updates.items():
        # Validate each value before writing
        is_valid, error = validate_secret_value(key, value)
        if not is_valid:
            # Log only key name and error type (CodeQL safe: no value taint)
            value_len = len(value)
            print(f"WARNING: Skipping malformed secret '{key}': {error} (length={value_len})", file=sys.stderr)
            continue
        validated_updates[key] = value

    for key, value in validated_updates.items():
        entry = f"{key}={value}"
        if key in index:
            lines[index[key]] = entry
        else:
            lines.append(entry)

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    env_path.write_text(text, encoding="utf-8")


def hydrate(
    local_env_path: Path,
    env_shared_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> Dict[str, str]:
    """Overlay local.env values into env.shared for empty/placeholder keys.

    When force=True, overwrites ALL matching keys in env.shared with values
    from local.env, even if the current value is non-placeholder. This is
    needed when GH Secrets are rotated and the stale local value must be
    replaced.
    """
    local_values = _parse_env(local_env_path)
    shared_values = _parse_env(env_shared_path)

    updates: Dict[str, str] = {}
    for key, local_val in sorted(local_values.items()):
        if is_placeholder(local_val):
            continue  # Don't overlay empty local values
        current = shared_values.get(key, "")
        if force or is_placeholder(current):
            updates[key] = local_val

    if updates and not dry_run:
        _write_updates(env_shared_path, updates)

    return updates


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-env",
        type=Path,
        default=None,
        help="Path to local.env (default: platform-appropriate APPDATA/XDG path)",
    )
    parser.add_argument(
        "--env-shared",
        type=Path,
        default=DEFAULT_ENV_SHARED,
        help="Path to env.shared (default: pmoves/env.shared)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing non-placeholder values (use after rotating GH Secrets)",
    )
    args = parser.parse_args(argv)

    local_env = args.local_env or _default_local_env()
    env_shared = args.env_shared.expanduser().resolve()

    if not local_env.exists():
        print(f"ℹ local.env not found at {local_env} — skipping hydration")
        print("  (Optional: run sync-secrets-local.yml workflow or provide --local-env path)")
        return 0

    if not env_shared.exists():
        print(f"⚠ env.shared not found at {env_shared}")
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    if args.force:
        prefix = "[force] " + prefix
    updates = hydrate(local_env, env_shared, dry_run=args.dry_run, force=args.force)

    if not updates:
        if args.force:
            local_values = _parse_env(local_env)
            if not local_values:
                print(f"WARNING: --force specified but {local_env} contains no keys", file=sys.stderr)
            else:
                real_count = sum(1 for v in local_values.values() if not is_placeholder(v))
                if real_count == 0:
                    print(f"WARNING: --force specified but all {len(local_values)} keys in {local_env} are placeholders", file=sys.stderr)
        print("No keys needed hydration — env.shared already has real values.")
        return 0

    print(f"{prefix}Hydrated {len(updates)} keys from {local_env} -> {env_shared}:")
    for key in sorted(updates):
        print(f"  {key}={_masked(updates[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
