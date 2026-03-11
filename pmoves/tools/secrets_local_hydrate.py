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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_SHARED = PROJECT_ROOT / "env.shared"

PLACEHOLDER_VALUES = frozenset({
    "", "changeme", "change_me", "none", "null",
    "your_key_here", "placeholder", "example",
})


def _default_local_env() -> Path:
    """Resolve the platform-appropriate local.env path."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", "")
        if not base:
            base = str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", "")
        if not base:
            base = str(Path.home() / ".config")
    return Path(base) / "pmoves" / "secrets" / "local.env"


def _parse_env(path: Path) -> Dict[str, str]:
    """Parse KEY=VALUE lines, skipping comments and blanks."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        # Strip optional 'export ' prefix (some env files use it)
        if line.startswith("export "):
            line = line[7:]
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value
    return values


def _is_empty_or_placeholder(value: str) -> bool:
    """Return True if value is missing, empty, or a known placeholder."""
    stripped = value.strip().lower()
    return stripped in PLACEHOLDER_VALUES or stripped.startswith("placeholder_")


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

    for key, value in updates.items():
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
) -> Dict[str, str]:
    """Overlay local.env values into env.shared for empty/placeholder keys."""
    local_values = _parse_env(local_env_path)
    shared_values = _parse_env(env_shared_path)

    updates: Dict[str, str] = {}
    for key, local_val in sorted(local_values.items()):
        if _is_empty_or_placeholder(local_val):
            continue  # Don't overlay empty local values
        current = shared_values.get(key, "")
        if _is_empty_or_placeholder(current):
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
    updates = hydrate(local_env, env_shared, dry_run=args.dry_run)

    if not updates:
        print("No keys needed hydration — env.shared already has real values.")
        return 0

    print(f"{prefix}Hydrated {len(updates)} keys from {local_env} -> {env_shared}:")
    for key in sorted(updates):
        print(f"  {key}={_masked(updates[key])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
