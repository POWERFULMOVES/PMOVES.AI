#!/usr/bin/env python3
"""Validate submodule-skill registry completeness against .gitmodules and skill files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from submodule_utils import parse_gitmodules_rows  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
GITMODULES = REPO_ROOT / ".gitmodules"
REGISTRY_PATH = REPO_ROOT / "pmoves" / "configs" / "submodule_skill_registry.json"
SKILLS_DIR = REPO_ROOT / ".claude" / "commands"
CONTEXT_DIR = REPO_ROOT / ".claude" / "context"
AGENTS_DIR = REPO_ROOT / "pmoves" / "docs" / "AGENTS"


def load_registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def validate() -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    # Load registry
    try:
        registry = load_registry()
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        errors.append(f"FAIL: Cannot load registry: {exc}")
        return errors

    submodules = registry.get("submodules", {})

    # Load .gitmodules
    modules = parse_gitmodules_rows(GITMODULES)
    gitmodule_paths = {mod["path"] for mod in modules}

    # 1. Every initialized submodule should have a registry entry
    for path in sorted(gitmodule_paths):
        if path not in submodules:
            errors.append(f"FAIL: Submodule '{path}' in .gitmodules has no registry entry")

    # 2. Every registry entry should correspond to a .gitmodules entry
    #    Skip entries that have a "canonical" field (alias/vendor dual-mount paths
    #    that reference another entry's .gitmodules path).
    for name in sorted(submodules):
        entry = submodules[name]
        if entry.get("canonical"):
            continue
        if name not in gitmodule_paths:
            errors.append(f"FAIL: Registry entry '{name}' not found in .gitmodules")

    # 3. Every skill referenced must exist as a .md file
    all_skills: set[str] = set()
    for name, entry in submodules.items():
        for skill in entry.get("skills", []):
            all_skills.add(skill)

    for skill in sorted(all_skills):
        skill_path = SKILLS_DIR / f"{skill}.md"
        if not skill_path.is_file():
            errors.append(f"FAIL: Skill '{skill}' referenced in registry but '{skill}.md' not found in .claude/commands/")

    # 4. Every context file referenced must exist
    all_context: set[str] = set()
    for name, entry in submodules.items():
        for cf in entry.get("context_files", []):
            all_context.add(cf)

    for cf in sorted(all_context):
        cf_path = CONTEXT_DIR / cf
        if not cf_path.is_file():
            errors.append(f"FAIL: Context file '{cf}' referenced in registry but not found in .claude/context/")

    # 5. Every AGENTS doc referenced must exist
    all_agents: set[str] = set()
    for name, entry in submodules.items():
        for ad in entry.get("agents_docs", []):
            all_agents.add(ad)

    for ad in sorted(all_agents):
        ad_path = AGENTS_DIR / ad
        if not ad_path.is_file():
            errors.append(f"FAIL: AGENTS doc '{ad}' referenced in registry but not found in pmoves/docs/AGENTS/")

    # 6. Dual-mount / canonical entries should reference an existing canonical entry
    for name, entry in submodules.items():
        canonical = entry.get("canonical")
        if canonical and canonical not in submodules:
            errors.append(f"FAIL: '{name}' references canonical '{canonical}' which has no registry entry")
        dual_mount = entry.get("dual_mount")
        if dual_mount and dual_mount not in submodules:
            warnings.append(f"WARN: '{name}' declares dual_mount '{dual_mount}' which has no separate registry entry (OK if vendor path)")

    # 7. Required fields check
    required_fields = ["context_tier", "domain_tags", "skills", "context_files", "agents_docs"]
    for name, entry in submodules.items():
        for field in required_fields:
            if field not in entry:
                errors.append(f"FAIL: Registry entry '{name}' missing required field '{field}'")

    # 8. context_tier must be 1-4
    for name, entry in submodules.items():
        tier = entry.get("context_tier")
        if tier is not None and tier not in (1, 2, 3, 4):
            errors.append(f"FAIL: Registry entry '{name}' has invalid context_tier={tier} (must be 1-4)")

    return errors + warnings


def main() -> int:
    issues = validate()
    if not issues:
        print(f"OK: Skill registry valid ({REGISTRY_PATH.relative_to(REPO_ROOT)})")
        return 0

    fails = [i for i in issues if i.startswith("FAIL")]
    warns = [i for i in issues if i.startswith("WARN")]

    for issue in issues:
        print(issue)

    print(f"\nSummary: {len(fails)} error(s), {len(warns)} warning(s)")

    if "--strict" in sys.argv:
        return 1

    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
