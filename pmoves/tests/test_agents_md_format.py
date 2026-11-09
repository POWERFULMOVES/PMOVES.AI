"""
Regression tests: PMOVES.AI's root AGENTS.md follows the
agents.md open format.

The 3 canonical section names (per the open format spec at
PMOVES-agents.md/):

  - ## Dev environment tips
  - ## Testing instructions
  - ## PR instructions

Plus the PMOVES extension convention: PMOVES-specific
sections get a <!-- PMOVES-EXT: <name> --> marker immediately
above the section heading. The marker is grep-discoverable
(`grep -rn 'PMOVES-EXT:' AGENTS.md`) and machine-checkable
(these tests fail if a future PR adds a PMOVES section
without the marker).

The PRs that landed the convention (this slice):

  - commit 1: rename 'Build & Development Commands' → 'Dev
    environment tips' (so the open format's canonical name
    is present)
  - commit 2: promote the format reference to a top-of-file
    note (so a cold-start agent sees the spec at the top)
  - commit 3: document the PMOVES extension convention (the
    `<!-- PMOVES-EXT: <name> -->` marker)

These tests pin all three. A future edit that drops a
canonical section, renames it away from the open format
name, or adds a new PMOVES section without a marker fails
here at PR time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_MD = REPO_ROOT / "AGENTS.md"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def agents_md_text() -> str:
    """The root AGENTS.md as a string."""
    if not AGENTS_MD.exists():
        pytest.skip(f"AGENTS.md not present at {AGENTS_MD}")
    return AGENTS_MD.read_text(encoding="utf-8")


# ============================================================================
# Open format: 3 canonical section names
# ============================================================================


CANONICAL_SECTIONS = (
    "Dev environment tips",
    "Testing instructions",
    "PR instructions",
)


def test_agents_md_has_canonical_dev_environment_tips(agents_md_text: str) -> None:
    """AGENTS.md has the open format's '## Dev environment tips' section."""
    assert "\n## Dev environment tips\n" in agents_md_text or agents_md_text.startswith("## Dev environment tips\n"), (
        "AGENTS.md must have '## Dev environment tips' as a section heading; "
        "this is the agents.md open format canonical section name "
        "(per PMOVES-agents.md/ submodule, fork of agentsmd/agents.md)"
    )


def test_agents_md_has_canonical_testing_instructions(agents_md_text: str) -> None:
    """AGENTS.md has the open format's '## Testing instructions' section."""
    assert "\n## Testing instructions\n" in agents_md_text or agents_md_text.startswith("## Testing instructions\n"), (
        "AGENTS.md must have '## Testing instructions' as a section heading"
    )


def test_agents_md_has_canonical_pr_instructions(agents_md_text: str) -> None:
    """AGENTS.md has the open format's '## PR instructions' section."""
    assert "\n## PR instructions\n" in agents_md_text or agents_md_text.startswith("## PR instructions\n"), (
        "AGENTS.md must have '## PR instructions' as a section heading"
    )


def test_agents_md_canonical_sections_are_unique(agents_md_text: str) -> None:
    """No canonical section name appears twice (typo guard)."""
    for name in CANONICAL_SECTIONS:
        count = len(re.findall(rf"^##\s+{re.escape(name)}\s*$", agents_md_text, re.MULTILINE))
        assert count == 1, (
            f"AGENTS.md has {count} sections named '## {name}'; "
            f"canonical section names must appear exactly once"
        )


# ============================================================================
# Open format: the format reference is at the top
# ============================================================================


def test_agents_md_format_reference_is_at_top(agents_md_text: str) -> None:
    """The agents.md format reference is in the first 30 lines.

    A cold-start agent that knows the open format looks for
    the spec reference early in the file (where the README
    and license live). A future edit that moves it back to
    line 200+ gets caught here.
    """
    # First 30 lines: enough to cover the title + the format
    # note + the first section heading.
    head = "\n".join(agents_md_text.splitlines()[:30])
    assert "agents.md" in head.lower() and "format" in head.lower(), (
        "AGENTS.md must have the agents.md format reference in the "
        "first 30 lines (where cold-start agents look for the spec); "
        f"head was: {head!r}"
    )


# ============================================================================
# PMOVES extension convention: every non-canonical section is marked
# ============================================================================


# The 5 PMOVES extensions marked in the slice's commit 3. Future PRs
# that add a new section must add the marker + update this tuple.
PMOVES_EXT_MARKERS = (
    "project_structure",
    "non_obvious_rules",
    "submodule_workflow",
    "deployment",
    "security",
)


def test_agents_md_has_pmovesext_markers(agents_md_text: str) -> None:
    """AGENTS.md has at least one <!-- PMOVES-EXT: name --> marker.

    This is the convention doc'd in commit 3. A file that
    drops the marker convention (or never had it) fails this
    test, so the next person who reads the convention can't
    silently lose it.
    """
    assert "<!-- PMOVES-EXT:" in agents_md_text, (
        "AGENTS.md must use the <!-- PMOVES-EXT: name --> marker "
        "convention for PMOVES-specific sections; the marker is "
        "grep-discoverable and machine-checkable (see the next test)"
    )


def test_agents_md_pmovesext_markers_present(agents_md_text: str) -> None:
    """The 5 PMOVES extensions from commit 3 are still marked.

    A future PR that removes a marker (or a section) without
    updating this test fails here. The tuple above + the
    assertion below are the contract.
    """
    for name in PMOVES_EXT_MARKERS:
        marker = f"<!-- PMOVES-EXT: {name} -->"
        assert marker in agents_md_text, (
            f"AGENTS.md is missing the {marker!r} marker; the section "
            f"'{name.replace('_', ' ').title()}' may have lost its "
            f"extension boundary. Re-add the marker, or if the section "
            f"is genuinely removed, update PMOVES_EXT_MARKERS in "
            f"pmoves/tests/test_agents_md_format.py"
        )


def test_agents_md_no_unmarked_pmovesspecific_sections(agents_md_text: str) -> None:
    """Every ## heading has a PMOVES-EXT marker or matches a canonical name.

    This is the inverse check: the marker is REQUIRED for any
    section that isn't one of the 3 canonical names. A new
    PMOVES section without a marker fails this test, so the
    convention is enforced at PR time.
    """
    # Find all ## section headings (not the file's # title).
    headings = re.findall(r"^##\s+(.+?)\s*$", agents_md_text, re.MULTILINE)
    # Normalize: a heading like "Dev environment tips" matches the
    # canonical name. A heading like "Project Structure" doesn't
    # and must be marked.
    canonical_set = set(CANONICAL_SECTIONS)
    unmarked = [h for h in headings if h not in canonical_set]

    # Each unmarked heading must be preceded by a PMOVES-EXT marker.
    # We check by looking at the lines immediately above each heading.
    lines = agents_md_text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if not m:
            continue
        heading = m.group(1)
        if heading in canonical_set:
            continue
        # The line(s) immediately above must contain a PMOVES-EXT
        # marker. Allow up to 3 lines above (in case the marker is
        # separated by a blank line).
        preceding = "\n".join(lines[max(0, i - 3):i])
        assert "<!-- PMOVES-EXT:" in preceding, (
            f"Section '## {heading}' is not in the agents.md open "
            f"format's canonical set and has no <!-- PMOVES-EXT: "
            f"name --> marker immediately above it. Either add a "
            f"marker (if the section is PMOVES-specific) or rename "
            f"it to one of the 3 canonical names (if it's a format "
            f"section). Canonical names: {sorted(canonical_set)}"
        )
