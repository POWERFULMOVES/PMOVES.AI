#!/usr/bin/env python3
"""
Update Open Notebook credentials across env files so the UI/API bearer stays in sync.

This helper rewrites the shared env files we mount into the Open Notebook container:
- pmoves/env.shared
- pmoves/.env
- pmoves/.env.local (if present)

Usage:
    python pmoves/scripts/set_open_notebook_password.py --password newpass
    python pmoves/scripts/set_open_notebook_password.py --password newpass --token newtoken

If --token is omitted the password value is mirrored into OPEN_NOTEBOOK_API_TOKEN.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Tuple


ROOT = Path(__file__).resolve().parent.parent
TARGET_FILES = [
    ROOT / "env.shared",
    ROOT / ".env",
    ROOT / ".env.local",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update Open Notebook password/token in env files.")
    parser.add_argument(
        "--password",
        required=True,
        help="New password to set for OPEN_NOTEBOOK_PASSWORD.",
    )
    parser.add_argument(
        "--token",
        help="Optional token value for OPEN_NOTEBOOK_API_TOKEN (defaults to password).",
    )
    parser.add_argument("--notebook-id", help="Optional notebook id to write into env files.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing files.")
    return parser.parse_args()


def update_env_lines(lines: Iterable[str], updates: Tuple[Tuple[str, str], ...]) -> Tuple[list[str], bool]:
    """Return updated lines and whether any change was applied."""
    new_lines = []
    changed = False
    remaining_keys = {k for k, _ in updates}

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue

        key, _, current_value = line.partition("=")
        key = key.strip()
        if key in remaining_keys:
            _, new_value = next(item for item in updates if item[0] == key)
            if current_value.rstrip("\n") != new_value:
                new_lines.append(f"{key}={new_value}\n")
                changed = True
            else:
                new_lines.append(line)
            remaining_keys.remove(key)
        else:
            new_lines.append(line)

    for key in remaining_keys:
        _, new_value = next(item for item in updates if item[0] == key)
        new_lines.append(f"{key}={new_value}\n")
        changed = True

    return new_lines, changed


def apply_updates(path: Path, updates: Tuple[Tuple[str, str], ...], dry_run: bool) -> bool:
    if not path.exists():
        return False

    original = path.read_text().splitlines(keepends=True)
    updated_lines, changed = update_env_lines(original, updates)
    if changed and not dry_run:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text("".join(updated_lines))
        tmp_path.replace(path)
    return changed


def main() -> int:
    args = parse_args()
    password = args.password.strip()
    token = (args.token or password).strip()

    if not password:
        sys.stderr.write("ERROR: password must be non-empty.\n")
        return 2
    if not token:
        sys.stderr.write("ERROR: token must be non-empty.\n")
        return 2

    updates_list = [
        ("OPEN_NOTEBOOK_PASSWORD", password),
        ("OPEN_NOTEBOOK_API_TOKEN", token),
    ]
    if args.notebook_id:
        notebook_id = args.notebook_id.strip()
        if notebook_id:
            updates_list.extend(
                [
                    ("MINDMAP_NOTEBOOK_ID", notebook_id),
                    ("YOUTUBE_NOTEBOOK_ID", notebook_id),
                    ("OPEN_NOTEBOOK_NOTEBOOK_ID", notebook_id),
                ]
            )

    updates = tuple(updates_list)

    any_changed = False
    for target in TARGET_FILES:
        changed = apply_updates(target, updates, args.dry_run)
        if changed:
            any_changed = True
            action = "Would update" if args.dry_run else "Updated"
            print(f"{action} {target}")

    if not any_changed:
        print("No changes needed; files already up to date.")

    if args.dry_run:
        print("Dry-run complete. Re-run without --dry-run to apply changes.")
        return 0

    print("Done. Restart Open Notebook to apply the new credentials:")
    print("  make -C pmoves down-open-notebook && make -C pmoves up-open-notebook")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
