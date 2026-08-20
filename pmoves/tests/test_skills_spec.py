"""Every skill in the repo must satisfy the Agent Skills spec.

<https://agentskills.io/specification>

This matters beyond tidiness. `name` and `description` are the only fields loaded
at startup for *every* skill — they are what an agent (and Archon, when minting a
new one) reads to decide whether a skill is relevant. A skill with no `SKILL.md`
is not a badly-described skill; it is an invisible one. All five skills under
`.minimax/skills/` were invisible for exactly that reason: they shipped as
"skill scaffolding" in #1484 with every other file present, and each of their
`docs/*` pages opened with "Start here only after reading `../SKILL.md`" —
pointing at a file that was never committed.

Scope note: `.claude/skills/` and `.agents/skills/` are *install targets* for the
`skills` package as well as homes for hand-authored skills. Both are checked,
because a skill that fails the spec is unusable regardless of how it arrived.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[2]

SKILL_ROOTS = (
    Path(".claude/skills"),
    Path(".minimax/skills"),
    Path(".agents/skills"),
)

# name: 1-64 chars, lowercase a-z0-9 and hyphens, no leading/trailing hyphen,
# no consecutive hyphens.
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_COMPATIBILITY = 500


def _skill_dirs() -> list[Path]:
    found: list[Path] = []
    for root in SKILL_ROOTS:
        abs_root = REPO_ROOT / root
        if not abs_root.is_dir():
            continue
        found.extend(d for d in sorted(abs_root.iterdir()) if d.is_dir())
    return found


def _frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise AssertionError(f"{skill_md}: no YAML frontmatter (must start with ---)")
    end = text.find("\n---", 3)
    if end == -1:
        raise AssertionError(f"{skill_md}: frontmatter is not terminated by ---")
    data = yaml.safe_load(text[3:end])
    if not isinstance(data, dict):
        raise AssertionError(f"{skill_md}: frontmatter is not a mapping")
    return data


def test_some_skills_are_discovered():
    """Guards against the whole suite passing vacuously."""
    dirs = _skill_dirs()
    assert len(dirs) >= 20, f"only {len(dirs)} skill dirs found — discovery is broken"


@pytest.mark.parametrize("skill_dir", _skill_dirs(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_skill_meets_spec(skill_dir: Path):
    rel = skill_dir.relative_to(REPO_ROOT).as_posix()

    skill_md = skill_dir / "SKILL.md"
    assert skill_md.is_file(), (
        f"{rel}: SKILL.md is required at the skill root. Without it the skill is "
        f"invisible to every agent and to the `skills` package — not merely "
        f"undocumented."
    )

    data = _frontmatter(skill_md)

    name = data.get("name")
    assert name, f"{rel}: `name` is required"
    assert isinstance(name, str), f"{rel}: `name` must be a string, got {type(name).__name__}"
    assert len(name) <= MAX_NAME, f"{rel}: `name` is {len(name)} chars, max {MAX_NAME}"
    assert NAME_RE.match(name), (
        f"{rel}: `name` {name!r} must be lowercase a-z0-9 and hyphens, with no "
        f"leading/trailing hyphen and no consecutive hyphens"
    )
    assert name == skill_dir.name, (
        f"{rel}: `name` is {name!r} but the parent directory is "
        f"{skill_dir.name!r} — the spec requires them to match"
    )

    description = data.get("description")
    assert description, f"{rel}: `description` is required and must be non-empty"
    assert isinstance(description, str), f"{rel}: `description` must be a string"
    assert len(description) <= MAX_DESCRIPTION, (
        f"{rel}: `description` is {len(description)} chars, max {MAX_DESCRIPTION}"
    )

    compatibility = data.get("compatibility")
    if compatibility is not None:
        assert isinstance(compatibility, str), f"{rel}: `compatibility` must be a string"
        assert len(compatibility) <= MAX_COMPATIBILITY, (
            f"{rel}: `compatibility` is {len(compatibility)} chars, max {MAX_COMPATIBILITY}"
        )

    metadata = data.get("metadata")
    if metadata is not None:
        assert isinstance(metadata, dict), f"{rel}: `metadata` must be a mapping"
        non_string = sorted(k for k, v in metadata.items() if not isinstance(v, str))
        assert not non_string, (
            f"{rel}: `metadata` must map string keys to string VALUES; these are "
            f"not strings: {non_string}. A list or number here is accepted by "
            f"yaml.safe_load but violates the spec."
        )
