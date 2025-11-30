"""Surfaced missing DeepResearch-related credentials during env setup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable


def _load_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            values[key] = value
    return values


def _placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return lowered in {"changeme", "change-me", "todo", "set-me"}


def _report_missing(keys: Iterable[str]) -> int:
    missing = list(keys)
    if not missing:
        return 0
    print("⚠ Missing DeepResearch credentials:")
    for item in missing:
        print(f"   - {item}")
    print(
        "  Populate these in pmoves/env.shared to enable OpenRouter queries and Notebook mirroring."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check DeepResearch required secrets")
    parser.add_argument(
        "--file",
        default="env.shared",
        help="env.shared path to inspect (default: env.shared)",
    )
    args = parser.parse_args(argv)

    env_path = Path(args.file)
    env_values = _load_env(env_path)

    missing: list[str] = []

    openrouter_key = env_values.get("OPENROUTER_API_KEY", "")
    if _placeholder(openrouter_key):
        missing.append("OPENROUTER_API_KEY")

    notebook_token = env_values.get("OPEN_NOTEBOOK_API_TOKEN", "")
    if _placeholder(notebook_token):
        missing.append("OPEN_NOTEBOOK_API_TOKEN")

    notebook_password = env_values.get("OPEN_NOTEBOOK_PASSWORD", "")
    if _placeholder(notebook_password):
        missing.append("OPEN_NOTEBOOK_PASSWORD (replace 'changeme')")

    notebook_id = env_values.get("DEEPRESEARCH_NOTEBOOK_ID", "")
    if _placeholder(notebook_id):
        missing.append("DEEPRESEARCH_NOTEBOOK_ID")

    _report_missing(missing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
