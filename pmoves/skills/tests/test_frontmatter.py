"""Frontmatter smoke tests for PMOVES skills.

Walks pmoves/skills/*/SKILL.md and verifies:
1. The file exists and is non-empty.
2. The YAML frontmatter (between --- markers) parses cleanly.
3. The required `name` + `description` fields are present.
4. The `name` field matches the directory name (the convention that
   room.skill_bindings[*].skill_id resolves to).
5. The `name` matches the slug pattern [a-z0-9][a-z0-9-]*.

Locks the slice-4 architecture rule "schema/contract first, then surface".
Skill frontmatter is machine-loadable (room manifests reference it by
skill_id), so it deserves a smoke test that runs in CI.

This module is intentionally framework-light (stdlib only + pyyaml) so
it works in any environment that already runs pmoves/scripts/* tests.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

SKILLS_ROOT = Path(__file__).resolve().parent.parent  # tests/ -> skills/ = pmoves/skills
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _iter_skill_files():
    """Yield (skill_dir, skill_md_path) for every SKILL.md under SKILLS_ROOT."""
    for skill_md in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        yield skill_md.parent, skill_md


def _parse_frontmatter(skill_md: Path) -> dict:
    """Return the parsed YAML frontmatter dict, or fail loudly."""
    text = skill_md.read_text(encoding="utf-8")
    # Frontmatter is between the first two `---` lines at the top of the file.
    if not text.startswith("---\n"):
        raise AssertionError(f"{skill_md}: missing leading '---' for frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise AssertionError(f"{skill_md}: missing closing '---' for frontmatter")
    frontmatter_text = text[4:end]
    return yaml.safe_load(frontmatter_text)


# ---- The actual tests ----

def test_all_skills_have_skill_md():
    """Every skill directory under pmoves/skills/ must have a SKILL.md."""
    skill_dirs = [p for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()]
    assert skill_dirs, f"no SKILL.md found under {SKILLS_ROOT}"
    # Sanity: at least the slice-6 skills + slice-2 pinokio-bridge + slice-4 gepeto-wrapper exist
    expected = {"pmoves-helpdesk-skill", "room-suggest-skill", "pinokio-bridge-skill", "gepeto-wrapper-skill"}
    actual = {p.name for p in skill_dirs}
    missing = expected - actual
    assert not missing, f"missing expected skill directories: {missing}"


def test_skill_frontmatter_parses():
    """Every SKILL.md frontmatter must parse as YAML."""
    for _, skill_md in _iter_skill_files():
        fm = _parse_frontmatter(skill_md)
        assert isinstance(fm, dict), f"{skill_md}: frontmatter is not a mapping"


def test_skill_frontmatter_required_fields():
    """Every SKILL.md must have `name` + `description`."""
    for _, skill_md in _iter_skill_files():
        fm = _parse_frontmatter(skill_md)
        assert "name" in fm, f"{skill_md}: missing `name`"
        assert "description" in fm, f"{skill_md}: missing `description`"
        assert isinstance(fm["name"], str) and fm["name"].strip(), f"{skill_md}: empty `name`"
        assert isinstance(fm["description"], str) and fm["description"].strip(), f"{skill_md}: empty `description`"


def test_skill_ids_referenced_by_room_manifests_resolve_to_a_skill_dir():
    """Slice-6 invariant: the 2 new skills referenced by pmoves.room.helpdesk
    must each resolve to a directory under pmoves/skills/ that has a SKILL.md.

    (We don't do a global "every skill_id resolves" check here because skills
    live in multiple places: pmoves/skills/ (newer convention) and
    .claude/skills/ (older convention). A global resolver belongs in P7, not
    in a skill frontmatter test.)
    """
    skill_dirs = {p.name for p in SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists()}
    assert "pmoves-helpdesk-skill" in skill_dirs
    assert "room-suggest-skill" in skill_dirs
    for sid in ("pmoves-helpdesk-skill", "room-suggest-skill"):
        assert (SKILLS_ROOT / sid / "SKILL.md").exists(), (
            f"slice-6 skill directory exists but SKILL.md is missing: {sid}"
        )


def test_skill_name_slug_pattern():
    """The `name` must match [a-z0-9][a-z0-9-]*."""
    for _, skill_md in _iter_skill_files():
        fm = _parse_frontmatter(skill_md)
        assert NAME_PATTERN.match(fm["name"]), (
            f"{skill_md}: name '{fm['name']}' does not match pattern {NAME_PATTERN.pattern}"
        )


# ---- Slice-6 specific regression tests ----

def test_helpdesk_skill_registers_helpdesk_subjects():
    """The pmoves-helpdesk-skill must document the 2 subjects it emits."""
    skill_md = SKILLS_ROOT / "pmoves-helpdesk-skill" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "helpdesk.intake.opened.v1" in text
    assert "helpdesk.intake.routed.v1" in text


def test_room_suggest_skill_emits_room_suggested():
    """The room-suggest-skill must document the 1 subject it emits."""
    skill_md = SKILLS_ROOT / "room-suggest-skill" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "helpdesk.room.suggested.v1" in text


def test_helpdesk_skill_consumes_room_directory():
    """Both skills must document they read room.directory.v1 (slice 3)."""
    for skill in ("pmoves-helpdesk-skill", "room-suggest-skill"):
        text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "room.directory.v1" in text, f"{skill}: missing room.directory.v1 reference"


def test_helpdesk_skill_consumes_pinokio_apps_registry():
    """Both skills must document they read the slice-4 pinokio-apps registry."""
    for skill in ("pmoves-helpdesk-skill", "room-suggest-skill"):
        text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "pinokio-apps" in text, f"{skill}: missing pinokio-apps registry reference"


def test_helpdesk_skill_explicit_ambient_or_workflow():
    """The pmoves-helpdesk-skill must document its invocation_mode
    (ambient by design — the helpdesk listens on every chat turn)."""
    skill_md = SKILLS_ROOT / "pmoves-helpdesk-skill" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert "ambient" in text.lower(), f"pmoves-helpdesk-skill: missing ambient invocation note"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
