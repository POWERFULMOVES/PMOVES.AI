"""Regression tests for .claude/hooks/governance/claim-collision-pre.py.

The hook shipped keyed on the CLAIMANT rather than the CLAIMED LANE, which
inverted the Village Rule it enforces: two owners could claim one branch with
no complaint, while a single owner was blocked from a second unrelated branch.
Both directions are pinned here, because the failure mode of a governance gate
is silence -- it goes on exiting 0 and looks exactly like a gate that works.

Invoked as a subprocess against the real entrypoint, not by importing
open_claims_in(), so the payload shape and the exit codes are covered too: a
PreToolUse hook only blocks on exit 2, so an exception-swallowed 0 is the bug
class that matters.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / ".claude" / "hooks" / "governance" / "claim-collision-pre.py"

# The hook only engages on files with the register's name.
REGISTER_NAME = "AGNOTE4482PHI.t1.md"
EXISTING = "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` scope: **widget.** Branch `feat/widget`\n"

ALLOW, BLOCK = 0, 2


def run_hook(tmp_path: Path, proposed: str, existing: str = EXISTING):
    register = tmp_path / REGISTER_NAME
    register.write_text(existing, encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(register), "content": proposed},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_hook_exists():
    assert HOOK.is_file(), f"governance hook missing: {HOOK}"


def test_different_owner_same_lane_is_blocked(tmp_path):
    """The event the register exists to prevent. Keyed on owner, this returned 0."""
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-B` scope: **also widget.** Branch `feat/widget`")
    assert r.returncode == BLOCK, f"expected block, got {r.returncode}: {r.stderr}"
    assert "feat/widget" in r.stderr
    assert "AGENT-A" in r.stderr, "block message must name who holds the lane"


def test_same_owner_different_lane_is_allowed(tmp_path):
    """A node running several lanes at once is the normal case here, not a collision."""
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-A` scope: **docs.** Branch `docs/typo`")
    assert r.returncode == ALLOW, f"false positive: {r.stderr}"


def test_same_owner_same_lane_is_allowed(tmp_path):
    """Re-naming your own open lane is not a collision with yourself."""
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-A` scope: **more widget.** Branch `feat/widget`")
    assert r.returncode == ALLOW, f"false positive: {r.stderr}"


def test_different_owner_different_lane_is_allowed(tmp_path):
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-B` scope: **docs.** Branch `docs/typo`")
    assert r.returncode == ALLOW, f"false positive: {r.stderr}"


def test_released_lane_is_free(tmp_path):
    """A RELEASE pairs by owner, and must free the lane for someone else."""
    existing = EXISTING + "- `2026-01-02T00:00:00Z` RELEASE `AGENT-A` scope: **done.**\n"
    r = run_hook(
        tmp_path,
        "- `t` CLAIM `AGENT-B` scope: **taking it over.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == ALLOW, f"released lane still blocked: {r.stderr}"


def test_release_must_match_the_claim_key_exactly(tmp_path):
    """Closing is an exact-string pop; a near-miss key must NOT free the lane.

    This is why a stale-keyed claim has to be released under its stale key.
    """
    existing = EXISTING + "- `2026-01-02T00:00:00Z` RELEASE `AGENT-A (v2)` scope: **done.**\n"
    r = run_hook(
        tmp_path,
        "- `t` CLAIM `AGENT-B` scope: **taking it over.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == BLOCK, "a mismatched RELEASE key must not close the lane"


def test_unkeyed_claim_reports_that_it_was_not_checked(tmp_path):
    """Partial coverage must be audible. Silence would read as 'verified'."""
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-B` scope: **freeform prose, no branch**")
    assert r.returncode == ALLOW
    assert "NOT CHECKED" in r.stderr, "unkeyed claims must not pass silently"


def test_non_register_file_is_ignored(tmp_path):
    other = tmp_path / "NOTES.md"
    other.write_text("hello", encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(other), "content": "CLAIM `AGENT-B` Branch `feat/widget`"},
    }
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )
    assert r.returncode == ALLOW


@pytest.mark.parametrize("tool", ["Read", "Bash", "Grep"])
def test_non_write_tools_are_ignored(tmp_path, tool):
    register = tmp_path / REGISTER_NAME
    register.write_text(EXISTING, encoding="utf-8")
    payload = {
        "tool_name": tool,
        "tool_input": {"file_path": str(register), "content": "CLAIM `AGENT-B` Branch `feat/widget`"},
    }
    r = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True
    )
    assert r.returncode == ALLOW


def test_line_numbers_resolve_the_way_an_editor_counts(tmp_path):
    """splitlines() also breaks on form feed; grep, sed, and editors do not.

    A block message points the reader at a line number, so a number that does
    not resolve in their editor sends them hunting.
    """
    existing = "filler\n\x0c\nfiller\n" + EXISTING
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-B` scope: **x.** Branch `feat/widget`", existing=existing)
    assert r.returncode == BLOCK
    reported = int(r.stderr.split("line ")[1].split(")")[0].strip())
    actual = existing.split("\n").index(EXISTING.rstrip("\n")) + 1
    assert reported == actual, f"hook said line {reported}, editors say {actual}"


# ---------------------------------------------------------------------------
# Spelling drift. The register carries 49 author strings for ~13 identities;
# B850 alone writes four. String equality made a release under one spelling
# fail to close a claim opened under another, and left a lane open for a week
# (2026-08-25). Both directions of that are pinned here.
# ---------------------------------------------------------------------------

B850_A = "B850-CLAUDE (Knuckles)"
B850_B = "B850-CLAUDE (Claude Opus 5)"


def test_a_release_closes_a_claim_written_under_another_spelling(tmp_path):
    """The lane-stays-open bug. `(Knuckles)` claims, `(Claude Opus 5)` releases."""
    existing = (
        f"- `2026-01-01T00:00:00Z` CLAIM `{B850_A}` scope: **x.** Branch `feat/widget`\n"
        f"- `2026-01-02T00:00:00Z` RELEASE `{B850_B}` scope: done.\n"
    )
    proposed = (
        "- `2026-01-03T00:00:00Z` CLAIM `AGENT-C` scope: **x.** Branch `feat/widget`\n"
    )
    result = run_hook(tmp_path, proposed, existing)
    assert result.returncode == ALLOW, (
        "the lane was released, under a different spelling of the same "
        f"identity; blocking it keeps the lane open forever.\n{result.stderr}"
    )


def test_an_identity_does_not_collide_with_itself_across_spellings(tmp_path):
    """The mirror-image false positive: re-claiming your own lane after your
    parenthetical changes (a new model, a new alter) is not a collision."""
    existing = (
        f"- `2026-01-01T00:00:00Z` CLAIM `{B850_A}` scope: **x.** Branch `feat/widget`\n"
    )
    proposed = (
        f"- `2026-01-03T00:00:00Z` CLAIM `{B850_B}` scope: **x.** Branch `feat/widget`\n"
    )
    result = run_hook(tmp_path, proposed, existing)
    assert result.returncode == ALLOW, (
        f"an identity blocked itself across two of its own spellings\n{result.stderr}"
    )


def test_a_genuine_collision_still_blocks_across_spellings(tmp_path):
    """Folding must not become a way to take someone else's lane.

    The whole risk of canonicalising is over-folding, so this pins the
    negative: two DIFFERENT identities on one lane still blocks.
    """
    existing = (
        f"- `2026-01-01T00:00:00Z` CLAIM `{B850_A}` scope: **x.** Branch `feat/widget`\n"
    )
    proposed = (
        "- `2026-01-03T00:00:00Z` CLAIM `4090-CLAUDE (field)` scope: **x.** "
        "Branch `feat/widget`\n"
    )
    result = run_hook(tmp_path, proposed, existing)
    assert result.returncode == BLOCK, (
        f"a real cross-identity collision stopped blocking\n{result.stdout}"
    )
    assert B850_A in result.stderr, (
        "the message must name the AS-WRITTEN owner so the reader can find the "
        f"entry; got: {result.stderr}"
    )


def test_the_hook_still_guards_when_the_vocabulary_is_missing(tmp_path, monkeypatch):
    """Fail-safe, not fail-open.

    With no vocabulary the hook must fall back to exact comparison -- its
    previous behaviour -- and still block a genuine collision. A guard that
    silently stops guarding when a config goes missing is the failure mode
    this whole change exists to remove.
    """
    proposed = (
        "- `2026-01-03T00:00:00Z` CLAIM `AGENT-B` scope: **x.** Branch `feat/widget`\n"
    )
    monkeypatch.setenv("PMOVES_IDENTITY_VOCABULARY", str(tmp_path / "nope.yaml"))
    result = run_hook(tmp_path, proposed)
    assert result.returncode == BLOCK, result.stdout
    assert "vocabulary unavailable" in result.stderr, (
        "the fallback must be audible -- a guard that quietly degrades is "
        f"indistinguishable from one that works. stderr was: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Dependency declaration.
#
# The hook is invoked as a bare `uv run` from a directory with no
# pyproject.toml. With no PEP 723 block uv supplies an interpreter that has no
# PyYAML, the identity vocabulary fails to import, and the hook falls back to
# comparing owner strings exactly -- reintroducing the collision-with-self this
# file exists to prevent, while still exiting 0 and printing nothing.
#
# This cannot be caught by running the hook here: %APPDATA%\Python\Python3xx\
# site-packages is on sys.path for EVERY interpreter on a developer box, so
# PyYAML is present locally however cleanly you invoke it. Reproduced with
# `PYTHONNOUSERSITE=1 uv run --no-project`, which is the state of a fresh node.
# So the assertion is structural: the declaration must be in the source.
# ---------------------------------------------------------------------------

SETTINGS = REPO_ROOT / ".claude" / "settings.json"

# Import name -> distribution name. Explicit, so an unrecognised third-party
# import fails the test rather than passing for lack of a mapping.
DISTRIBUTION = {"yaml": "pyyaml", "jsonschema": "jsonschema", "requests": "requests"}


def _uv_run_hook_scripts() -> list[Path]:
    """Every hook script settings.json launches with `uv run`."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    found: list[Path] = []
    for event in settings.get("hooks", {}).values():
        for matcher in event:
            for hook in matcher.get("hooks", []):
                command = hook.get("command", "")
                if "uv run" not in command:
                    continue
                m = re.search(r'\$CLAUDE_PROJECT_DIR/([^"\']+\.py)', command)
                if m:
                    found.append(REPO_ROOT / m.group(1))
    return found


def _pep723_dependencies(source: str) -> list[str] | None:
    """Parse the inline script block. None means no block at all."""
    m = re.search(r"^# /// script\n(.*?)^# ///$", source, re.M | re.S)
    if not m:
        return None
    body = "".join(line.lstrip("#").strip() for line in m.group(1).splitlines())
    deps = re.search(r"dependencies\s*=\s*\[(.*?)\]", body, re.S)
    if not deps:
        return []
    return re.findall(r'"([^"]+)"', deps.group(1))


def _third_party_imports(path: Path, seen: set[Path] | None = None) -> set[str]:
    """Top-level third-party modules reachable from `path`.

    Follows spec_from_file_location loads, because the hook's PyYAML need is
    inherited from identity_lineage.py rather than written in the hook itself.
    """
    seen = seen if seen is not None else set()
    if path in seen or not path.exists():
        return set()
    seen.add(path)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.update({node.module.split(".")[0]})
    third_party: set[str] = set()
    for module in modules:
        if module in sys.stdlib_module_names:
            continue
        sibling = path.parent / f"{module}.py"
        if sibling.exists():
            # A local sibling, not a distribution. Its own imports still count:
            # the hook inherits every dependency it reaches, however indirectly.
            third_party |= _third_party_imports(sibling, seen)
        else:
            third_party.add(module)
    # Follow modules loaded by explicit path, e.g. `root / "pmoves" / "tools" / "x.py"`.
    for _, filename in re.findall(
        r'"([A-Za-z0-9_-]+)"\s*/\s*"([A-Za-z0-9_.-]+\.py)"', source
    ):
        for candidate in REPO_ROOT.rglob(filename):
            third_party |= _third_party_imports(candidate, seen)
    return third_party


@pytest.mark.skipif(
    not hasattr(sys, "stdlib_module_names"), reason="needs Python 3.10+"
)
def test_uv_run_hooks_declare_the_dependencies_they_import():
    scripts = _uv_run_hook_scripts()
    assert scripts, (
        "no `uv run` hooks found in settings.json -- either the command shape "
        "changed or this test stopped looking at the right place. It must not "
        "pass by finding nothing to check."
    )
    undeclared: list[str] = []
    for script in scripts:
        needed = _third_party_imports(script)
        if not needed:
            continue
        declared = _pep723_dependencies(script.read_text(encoding="utf-8"))
        have = {d.lower() for d in (declared or [])}
        for module in sorted(needed):
            dist = DISTRIBUTION.get(module)
            assert dist, (
                f"{script.name} imports third-party module {module!r} with no "
                f"entry in DISTRIBUTION -- add one rather than letting this "
                f"test pass by not recognising it."
            )
            if dist.lower() not in have:
                undeclared.append(f"{script.name} needs {dist} (imports {module})")
    assert not undeclared, (
        "hook scripts run by bare `uv run` must declare their dependencies in a "
        "PEP 723 block, or uv hands them an interpreter without those packages "
        "on a clean node:\n  " + "\n  ".join(undeclared)
    )


def test_the_collision_hook_specifically_declares_pyyaml():
    """Pinned by name: this is the one whose absence degrades silently."""
    declared = _pep723_dependencies(HOOK.read_text(encoding="utf-8"))
    assert declared is not None, "claim-collision-pre.py has no PEP 723 block"
    assert any(d.lower() == "pyyaml" for d in declared), (
        f"pyyaml missing from {declared!r}: without it _load_folder() catches "
        "ImportError and the hook reverts to exact-string owner comparison, "
        "which is the defect it was changed to remove."
    )
