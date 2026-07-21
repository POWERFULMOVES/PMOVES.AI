#!/usr/bin/env python3
"""
launcher_profile_select.py

Select and apply a PMOVES launcher profile to a local Hermes profile.

Reads a launcher profile JSON from pmoves/launcher/profiles/ and merges the
canonical Hermes config overrides into the Hermes profile at:
    %LOCALAPPDATA%/hermes/profiles/<profile>/config.yaml   (Windows)
    ~/.hermes/profiles/<profile>/config.yaml                (POSIX)

Preserves existing non-empty values unless --force is given. Always creates a
backup before writing. Never writes secret values into the launcher JSON.

Usage:
    python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890
    python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890 --write
    python pmoves/tools/launcher_profile_select.py --profile pmoves-hermes-z890 --write --force
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


# ═══════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════

TOOL_DIR = Path(__file__).resolve().parent
PMOVES_ROOT = TOOL_DIR.parent
LAUNCHER_PROFILES_DIR = PMOVES_ROOT / "launcher" / "profiles"


def hermes_profiles_dir() -> Path:
    """Return the Hermes profiles directory for the current platform."""
    if sys.platform == "win32":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / "hermes" / "profiles"
    return Path.home() / ".hermes" / "profiles"


# ═══════════════════════════════════════════════════════════════════════════
# Merge logic
# ═══════════════════════════════════════════════════════════════════════════

def is_empty(value: Any) -> bool:
    """Treat None, '', and [] as empty so we can overlay launcher defaults."""
    if value is None:
        return True
    if isinstance(value, str) and value == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def deep_merge(base: dict[str, Any], overlay: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """
    Merge overlay into base. Recursively combine dicts. For non-dict values,
    preserve existing non-empty base values unless force is True.
    """
    result: dict[str, Any] = {}
    for key in set(base.keys()) | set(overlay.keys()):
        base_val = base.get(key)
        overlay_val = overlay.get(key)
        if isinstance(overlay_val, dict) and isinstance(base_val, dict):
            result[key] = deep_merge(base_val, overlay_val, force)
        elif force or is_empty(base_val):
            result[key] = overlay_val
        else:
            result[key] = base_val
    return result


# ═══════════════════════════════════════════════════════════════════════════
# I/O helpers
# ═══════════════════════════════════════════════════════════════════════════

def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=120,
        )


def render_env_template(secrets: list[str]) -> str:
    lines = [
        "# PMOVES launcher profile environment template",
        "# 1. Copy these keys into your Hermes profile .env file",
        "#    (e.g. %LOCALAPPDATA%/hermes/profiles/<profile>/.env)",
        "# 2. Copy PMOVES-specific keys into pmoves/env.shared and/or .env.local",
        "# 3. Never commit this file or .env to the repo.",
        "",
    ]
    for secret in secrets:
        lines.append(f"{secret}=")
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════

def validate_launcher_profile(launcher: dict[str, Any], path: Path) -> None:
    """Fail fast if the launcher profile is missing required fields."""
    required = ["node_id", "pmoves_profile", "hermes_profile", "room"]
    missing = [f for f in required if f not in launcher]
    if missing:
        raise ValueError(f"Launcher profile {path} missing required fields: {missing}")
    room = launcher.get("room", {})
    if "room_id" not in room:
        raise ValueError(f"Launcher profile {path} missing room.room_id")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply a PMOVES launcher profile to a local Hermes profile."
    )
    parser.add_argument(
        "--profile",
        default="pmoves-hermes-z890",
        help="Launcher profile name (basename of a JSON file in pmoves/launcher/profiles/)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the merged config to the Hermes profile (default: dry run)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing non-empty values with launcher defaults",
    )
    parser.add_argument(
        "--env-template-only",
        action="store_true",
        help="Only write the .env.template file, do not touch config.yaml",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
        help="Override the Hermes profiles directory (for testing/CI)",
    )
    args = parser.parse_args(argv)

    profiles_dir = args.profiles_dir or hermes_profiles_dir()

    launcher_path = LAUNCHER_PROFILES_DIR / f"{args.profile}.json"
    if not launcher_path.exists():
        print(f"ERROR: Launcher profile not found: {launcher_path}", file=sys.stderr)
        return 1

    launcher = load_json(launcher_path)
    validate_launcher_profile(launcher, launcher_path)

    hermes_profile_name = launcher["hermes_profile"]
    hermes_profile_dir = profiles_dir / hermes_profile_name
    hermes_config_path = hermes_profile_dir / "config.yaml"

    print(f"Launcher profile : {args.profile}")
    print(f"Launcher path     : {launcher_path}")
    print(f"PMOVES profile    : {launcher['pmoves_profile']}")
    print(f"Room              : {launcher['room']['room_id']}")
    print(f"Hermes profile    : {hermes_profile_name}")
    print(f"Hermes config     : {hermes_config_path}")

    hermes_profile_dir.mkdir(parents=True, exist_ok=True)
    current_config = load_yaml(hermes_config_path) if hermes_config_path.exists() else {}

    overrides = launcher.get("hermes_config_overrides", {})
    merged = deep_merge(current_config, overrides, force=args.force)

    # ─────────────────────────────────────────────────────────────────────
    # .env.template
    # ─────────────────────────────────────────────────────────────────────
    env_template_path = hermes_profile_dir / ".env.template"
    env_content = render_env_template(launcher.get("env_secrets", []))

    if args.env_template_only:
        if args.write:
            with open(env_template_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            print(f"Wrote .env template: {env_template_path}")
        else:
            print(f"\nDry run: would write .env template to {env_template_path}")
            print(env_content)
        return 0

    # ─────────────────────────────────────────────────────────────────────
    # Show diff preview
    # ─────────────────────────────────────────────────────────────────────
    if not args.write:
        print("\n--- Merged Hermes config preview ---")
        print(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=120))
        print("--- End preview ---")
        print(f"\nDry run: no files written. Use --write to apply to {hermes_config_path}")
        return 0

    # ─────────────────────────────────────────────────────────────────────
    # Write config.yaml
    # ─────────────────────────────────────────────────────────────────────
    if hermes_config_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = hermes_config_path.with_suffix(f".yaml.backup-{timestamp}")
        shutil.copy2(hermes_config_path, backup_path)
        print(f"Backup created    : {backup_path}")

    write_yaml(hermes_config_path, merged)
    print(f"Wrote Hermes config: {hermes_config_path}")

    with open(env_template_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    print(f"Wrote .env template: {env_template_path}")

    print("\nNext steps:")
    print(f"  1. Fill {hermes_profile_dir / '.env'} with the secrets from {env_template_path}")
    print(f"  2. Run 'hermes profile use {hermes_profile_name}' if not already active")
    print(f"  3. Verify with 'hermes profile show {hermes_profile_name}' or equivalent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
