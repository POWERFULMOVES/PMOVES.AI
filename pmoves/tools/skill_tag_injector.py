#!/usr/bin/env python3
"""Inject PMOVES.AI-CONTEXT-TAGS into submodule CLAUDE.md files.

Reads the submodule-skill registry and appends (or updates) a machine-parseable
context-tag block at the bottom of each submodule's CLAUDE.md file.

Only modifies files that already exist in the parent repo's view.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "pmoves" / "configs" / "submodule_skill_registry.json"

TIER_LABELS = {
    1: "Always Load (Critical)",
    2: "On-Demand (Major Subsystem)",
    3: "Conditional (Integration)",
    4: "Explicit Only (Nested/Vendor)",
}

TAG_START = "<!-- PMOVES.AI-CONTEXT-TAGS -->"
TAG_END = "<!-- /PMOVES.AI-CONTEXT-TAGS -->"


def load_registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def build_tag_block(name: str, entry: dict) -> str:
    skills = entry.get("skills", [])
    context_files = entry.get("context_files", [])
    domain_tags = entry.get("domain_tags", [])
    tier = entry.get("context_tier", 4)
    tier_label = TIER_LABELS.get(tier, "Unknown")

    skills_str = ", ".join(f"`/{s.replace('/', ':')}`" for s in skills) if skills else "_none_"
    context_str = ", ".join(f"`{c}`" for c in context_files) if context_files else "_none_"
    domain_str = ", ".join(f"`{d}`" for d in domain_tags) if domain_tags else "_none_"

    return f"""{TAG_START}
## PMOVES.AI Skill Hints

**Primary Skills:** {skills_str}
**Context Files:** {context_str}
**Domain Tags:** {domain_str}
**Context Tier:** {tier} ({tier_label})
{TAG_END}"""


def find_claude_md(submodule_path: str) -> Path | None:
    """Find CLAUDE.md for a submodule, checking common locations."""
    candidates = [
        REPO_ROOT / submodule_path / "CLAUDE.md",
        REPO_ROOT / submodule_path / ".claude" / "CLAUDE.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def inject_tags(path: Path, block: str, *, dry_run: bool = False) -> bool:
    """Inject or update the tag block in a CLAUDE.md file. Returns True if modified."""
    content = path.read_text(encoding="utf-8")

    # Check if tags already exist — replace them
    pattern = re.compile(
        re.escape(TAG_START) + r".*?" + re.escape(TAG_END),
        re.DOTALL,
    )
    if pattern.search(content):
        new_content = pattern.sub(block, content)
    else:
        # Append with two newlines separator
        stripped = content.rstrip()
        new_content = stripped + "\n\n" + block + "\n"

    if new_content == content:
        return False

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    registry = load_registry()
    submodules = registry.get("submodules", {})

    injected = 0
    skipped = 0

    for name, entry in sorted(submodules.items()):
        # Skip alias/canonical entries — they reference another entry
        if entry.get("canonical"):
            continue

        claude_md = find_claude_md(name)
        if claude_md is None:
            skipped += 1
            continue

        block = build_tag_block(name, entry)
        rel = claude_md.relative_to(REPO_ROOT).as_posix()

        if inject_tags(claude_md, block, dry_run=dry_run):
            action = "would inject" if dry_run else "injected"
            print(f"  {action}: {rel}")
            injected += 1
        else:
            print(f"  up-to-date: {rel}")

    print(f"\nSummary: {injected} injected, {skipped} skipped (no CLAUDE.md)")
    if dry_run:
        print("(dry-run mode — no files modified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
