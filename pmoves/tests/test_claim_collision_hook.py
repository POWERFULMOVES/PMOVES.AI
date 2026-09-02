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


def test_unkeyed_claim_is_refused_not_merely_reported(tmp_path):
    """A claim with no lane is unenforceable, so it is refused rather than logged.

    THIS ASSERTION USED TO BE `ALLOW` plus a "NOT CHECKED" line on stderr, and
    that made the raw shell write MORE PERMISSIVE than the sanctioned tool it is
    supposed to be replaced by. Measured at 776b429b9 with the identical claim:

        EXIT=0  Bash echo-redirect / Bash heredoc / Write
        EXIT=3  make -C pmoves register-claim   ("a CLAIM must name --branch")

    AGENTS.md requires a CLAIM row to carry branch + scope + TTL, and 78 rows in
    the live register name no branch and are enforceable by nothing. Could not
    measure is not a pass.
    """
    r = run_hook(tmp_path, "- `t` CLAIM `AGENT-B` scope: **freeform prose, no branch**")
    assert r.returncode == BLOCK, f"an unenforceable claim must be refused: {r.stderr!r}"
    assert "names no branch" in r.stderr
    assert "register-claim" in r.stderr, "a refusal must name the road that works"


def test_an_unkeyed_claim_is_refused_the_same_way_on_the_shell_path(tmp_path):
    """Same row, same verdict, whichever tool the agent happens to have.

    The gap Codex found was between the shell path and `register_append.py`.
    Fixing it on Bash alone would have re-opened the gap this PR closed --
    Write and Bash disagreeing about one register row.
    """
    row = "- `t` CLAIM `AGENT-B` scope: **freeform prose, no branch**"
    via_write = run_hook(tmp_path, row)
    via_bash = _run_bash(tmp_path, f"echo '{row}' >> {REGISTER_NAME}")
    assert via_write.returncode == BLOCK
    assert via_bash.returncode == BLOCK
    assert via_write.stderr == via_bash.stderr, (
        "the two matchers must say the same thing:\n"
        f"WRITE: {via_write.stderr!r}\nBASH:  {via_bash.stderr!r}"
    )


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
# --- the shell-shaped hole -------------------------------------------------
# A heredoc/tee/sed write never reaches the Write|Edit matcher. This agent filed
# its own CLAIM that way and the gate never fired. The Bash path cannot do the
# same check -- a shell command carries no proposed text -- so it asks instead.

def _run_bash(tmp_path: Path, command: str, existing: str = EXISTING):
    register = tmp_path / REGISTER_NAME
    register.write_text(existing, encoding="utf-8")
    payload = {
        "tool_name": "Bash",
        "cwd": str(tmp_path),
        "tool_input": {"command": command},
    }
    return subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True,
    )


def _decision(result):
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


# THESE TESTS CHANGED CONTRACT DELIBERATELY, and the old assertions are kept
# here as the record of what was replaced. Every one of them asserted
# `permissionDecision: "ask"` on a shell write, because the hook could not read
# what a shell command would write and said so honestly.
#
# It can now read the common case: a heredoc body, and an `echo`/`printf`
# literal, are IN the command string. So a recoverable write gets the same
# collision check the Write path gets -- blocking at exit 2 on a held lane, and
# passing silently when it is clean -- and only a genuinely unreadable write
# (`sed -i`, a variable, a computed row) is refused as could-not-measure.
#
# The change was not cosmetic. Measured 2026-09-02: Write exited 2 on a held
# lane while Bash exited 0 on identical content, and four delivery agents in
# one session had no Write tool at all, so "ask" was the only verdict any of
# them could receive.


@pytest.mark.parametrize("command", [
    f"python3 - <<'PY'\nopen('{REGISTER_NAME}','a').write(x)\nPY",
    f"sed -i 's/a/b/' {REGISTER_NAME}",
    f"printf '%s' \"$ROW\" >> {REGISTER_NAME}",
    f"cat > {REGISTER_NAME} <<'EOF'\n- entry\nEOF",
])
def test_unreadable_shell_writes_are_refused(tmp_path, command):
    """A write whose CONTENT is not in the command string is could-not-measure.

    Per the repo doctrine (0 clean / 1 findings / 3 could not measure -- NOT a
    pass) that is a refusal. The advisory this replaces returned exit 0 with an
    "ask", which made could-not-measure indistinguishable from measured-clean
    on the only surface that gates.
    """
    r = _run_bash(tmp_path, command)
    assert r.returncode == BLOCK, f"unreadable write allowed: {command!r}"
    assert "NOT MEASURED" in r.stderr
    assert "register-claim" in r.stderr, (
        "a refusal with no sanctioned alternative is a deadlock, not a gate"
    )


@pytest.mark.parametrize("command", [
    f"cat >> {REGISTER_NAME} <<'EOF'\n{{row}}\nEOF",
    f"tee -a {REGISTER_NAME} <<'EOF'\n{{row}}\nEOF",
    f"echo '{{row}}' >> {REGISTER_NAME}",
])
def test_recoverable_shell_writes_are_checked_like_a_write_tool(tmp_path, command):
    """The heredoc/literal body IS the payload, so it gets the real check.

    Both halves are asserted. A gate observed only refusing is as unproven as
    one observed only passing, and breaking the routine append is how a gate
    gets removed.
    """
    squat = ("- `t` CLAIM `AGENT-B` scope: **mine now.** Branch `feat/widget`")
    r = _run_bash(tmp_path, command.format(row=squat))
    assert r.returncode == BLOCK, f"collision missed on the shell path: {command!r}"
    assert "feat/widget" in r.stderr and "AGENT-A" in r.stderr

    free = ("- `t` CLAIM `AGENT-B` scope: **new work.** Branch `feat/unheld`")
    r = _run_bash(tmp_path, command.format(row=free))
    assert r.returncode == ALLOW, f"routine append broken: {command!r}"


def test_the_shell_block_message_matches_the_write_path(tmp_path):
    """One register, one verdict, one message -- whichever tool you reached for.

    A gate whose refusal depends on the tool teaches that the tool is the
    variable, which is precisely how the shell path came to be the way to file
    a claim without being checked.
    """
    row = "- `t` CLAIM `AGENT-B` scope: **mine now.** Branch `feat/widget`"
    via_write = run_hook(tmp_path, row)
    via_bash = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF")
    assert via_write.returncode == via_bash.returncode == BLOCK
    assert via_write.stderr == via_bash.stderr


@pytest.mark.parametrize("command", [
    f"grep -n CLAIM {REGISTER_NAME}",
    f"sed -n '1,5p' {REGISTER_NAME}",
    f"wc -l {REGISTER_NAME}",
    "echo hello >> /tmp/unrelated.txt",
])
def test_reads_and_unrelated_writes_stay_silent(tmp_path, command):
    """A prompt on every `grep` would train the reader to click through."""
    r = _run_bash(tmp_path, command)
    assert r.returncode == ALLOW
    assert _decision(r) is None, f"spurious prompt for: {command!r}"


def test_the_refusal_names_the_lane_and_the_holder(tmp_path):
    """Surfacing state is still the whole point.

    The advisory listed EVERY open lane because it did not know which one you
    were about to touch. Now it does, so it names the one that actually
    collides and the owner holding it -- the same information, minus the noise
    that trains people to click through.
    """
    row = "- `t` CLAIM `AGENT-B` scope: **mine now.** Branch `feat/widget`"
    r = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF")
    assert r.returncode == BLOCK
    assert "AGENT-A" in r.stderr and "feat/widget" in r.stderr


def test_a_file_path_is_not_a_lane(tmp_path):
    """`docs/x.md` in a scope is a citation, not a claimed branch.

    Unfiltered, two agents citing the same spec file would collide on it, and
    the register showed lanes nobody was working.
    """
    # Each row names its OWN lane. Without that these two claims are unkeyed,
    # and an unkeyed claim is now refused on its own account -- which would let
    # this test pass while saying nothing about the suffix filter. With distinct
    # lanes the only thing that can produce a collision here is the cited file
    # being read as a lane, which is exactly the property under test.
    existing = (
        "- `t` CLAIM `AGENT-A` scope: **wrote it up.** Branch `feat/write-the-spec` "
        "See `docs/superpowers/specs/thing-design.md`\n"
    )
    r = run_hook(
        tmp_path,
        "- `t` CLAIM `AGENT-B` scope: **read it.** Branch `feat/read-the-spec` "
        "See `docs/superpowers/specs/thing-design.md`",
        existing=existing,
    )
    assert r.returncode == ALLOW, "a shared file citation must not read as a collision"


def test_a_real_docs_branch_is_still_a_lane(tmp_path):
    """The filter keys on the file extension, so extensionless docs/ branches survive."""
    existing = "- `t` CLAIM `AGENT-A` scope: **x.** Branch `docs/opus5-identity-and-lane-claim`\n"
    r = run_hook(
        tmp_path,
        "- `t` CLAIM `AGENT-B` scope: **x.** Branch `docs/opus5-identity-and-lane-claim`",
        existing=existing,
    )
    assert r.returncode == BLOCK, "a genuine docs/ branch must still be a lane"


def test_every_colliding_lane_is_named_not_just_the_first(tmp_path):
    """One identity can hold several lanes, and a claim can name several.

    #2760 made open_claims_in() keep a LIST per owner because keying one claim
    per owner silently forgot every lane but the newest. The refusal has to
    report all of them, or the agent fixes one collision and hits the next.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` scope: **one.** Branch `feat/one`\n"
        "- `t1` CLAIM `AGENT-A` scope: **two.** Branch `feat/two`\n"
    )
    row = ("- `t2` CLAIM `AGENT-B` scope: **both.** "
           "Branch `feat/one` and Branch `feat/two`")
    r = _run_bash(
        tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
        existing=existing,
    )
    assert r.returncode == BLOCK
    assert "feat/one" in r.stderr and "feat/two" in r.stderr



def test_a_release_citing_a_file_still_closes_the_whole_claim(tmp_path):
    """A RELEASE that cites a file path is a BARE release, not a scoped one.

    `lanes_in` filters file paths out of CLAIM lines; the RELEASE line has to
    use the same filter. Left on the raw regex, a release whose scope mentions
    `docs/something.md` produces a non-empty `released` set, so it takes the
    "closes only the named lanes" branch and closes nothing -- while the
    register's own convention (99 of its 120 RELEASE lines name no branch) is
    that a bare release is a full handoff. The lane would stay open and the
    author would have no way to tell.
    """
    existing = (
        "- `2026-01-01T00:00:00Z` CLAIM `AGENT-A` scope: **widget.** Branch `feat/widget`\n"
        "- `2026-01-02T00:00:00Z` RELEASE `AGENT-A` scope: **done, see `docs/notes.md`.**\n"
    )
    proposed = existing + (
        "- `2026-01-03T00:00:00Z` CLAIM `AGENT-B` scope: **mine now.** Branch `feat/widget`\n"
    )
    result = run_hook(tmp_path, proposed, existing=existing)
    assert result.returncode == ALLOW, (
        "the release closed the lane, so AGENT-B may take it:\n" + result.stderr
    )


# --- Codex findings on #2755 -------------------------------------------------

def test_replacement_commands_are_refused(tmp_path):
    """`cp`/`mv`/`perl -pi` rewrite a file with no redirect and no sed -i.

    None of them carried a WRITE_TOKENS match, so the gate stayed silent while
    the register was replaced wholesale -- the exact hole the Bash advisory
    exists to close, reachable by the most ordinary way to overwrite a file.
    """
    for command in (
        f"cp updated.md {REGISTER_NAME}",
        f"mv staged.md {REGISTER_NAME}",
        f"perl -pi -e 's/a/b/' {REGISTER_NAME}",
        f"install -m 644 new.md {REGISTER_NAME}",
    ):
        r = _run_bash(tmp_path, command)
        assert r.returncode == BLOCK, f"silent on a register rewrite: {command!r}"
        assert "NOT MEASURED" in r.stderr


def test_read_only_redirection_is_not_advised(tmp_path):
    """A redirect that does not TARGET the register is not a write to it.

    `2>/dev/null` and a redirect to report.txt matched the bare `>` token, so
    routine reads prompted. This hook runs on every Bash call, so a false ask
    here is friction on ordinary work -- and friction is what trains people to
    click through the prompt that actually matters.
    """
    for command in (
        f"cat {REGISTER_NAME} 2>/dev/null",
        f"grep CLAIM {REGISTER_NAME} > report.txt",
        f"wc -l < {REGISTER_NAME}",
    ):
        r = _run_bash(tmp_path, command)
        assert _decision(r) is None, f"false prompt on a read: {command!r}"


def test_redirection_onto_the_register_is_checked_not_merely_flagged(tmp_path):
    """The other half of the above: a redirect AT the register is now READ.

    `echo '- entry' >> REG` used to raise an "ask" because the hook could not
    see the content. It can: the literal is single-quoted, so the shell expands
    nothing and `- entry` is exactly what lands. It carries no CLAIM, collides
    with nothing, and passes -- while the same redirect carrying a claim on a
    held lane is refused, which the collision tests above pin.

    Silence here is a MEASURED clean, not an unexamined one.
    """
    r = _run_bash(tmp_path, f"echo '- entry' >> {REGISTER_NAME}")
    assert r.returncode == ALLOW
    assert _decision(r) is None


def test_an_explicitly_marked_branch_keeps_its_file_suffix(tmp_path):
    """A branch may legitimately end in `.py`; the suffix filter dropped it.

    Both claims then became unkeyed, so two owners could hold one branch with
    no collision -- the gate failing OPEN, silently. The suffix filter still
    earns its place for bare cited paths, so an explicit `Branch` marker is
    what distinguishes a claimed lane from a referenced file.
    """
    existing = "- `t0` CLAIM `AGENT-A` scope: **parser.** Branch `fix/parser.py`\n"
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` scope: **same parser.** Branch `fix/parser.py`",
        existing=existing,
    )
    assert r.returncode == BLOCK, f"gate failed OPEN on a suffixed branch: {r.returncode}"
    assert "fix/parser.py" in r.stderr


def test_a_cited_file_path_is_still_not_a_lane(tmp_path):
    """Negative control for the fix above: no marker, so the suffix filter holds."""
    existing = ("- `t0` CLAIM `AGENT-A` branch: `fix/reviewer-notes` \xb7 scope: "
                "reviewed `docs/superpowers/specs/x-design.md`\n")
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `fix/reader-notes` \xb7 scope: also read "
        "`docs/superpowers/specs/x-design.md`",
        existing=existing,
    )
    assert r.returncode == ALLOW, "a merely-cited spec file must not register as a lane"


# ---------------------------------------------------------------------------
# CO-OWNERS -- lanes are shared just like nodes, and the register can say so.
#
# The gap these pin: the row grammar captured exactly ONE backticked owner, so a
# lane worked by four bodies could only ever be attributed to one and every
# co-worker was invisible to any machine reading the ledger. The hook already
# BELIEVED shared lanes were legitimate -- its docstring says "more than one
# node on a lane is the village working, not a violation" -- it simply could not
# tell a declared collaboration apart from a genuine clash.
#
# The load-bearing assertion in this section is NOT that a declared shared lane
# is allowed. It is the pair: declared -> allow, UNDECLARED -> still block. A
# gate that only got quieter would be a regression wearing a feature's clothes.
# ---------------------------------------------------------------------------


def test_a_declared_co_owner_may_claim_the_shared_lane(tmp_path):
    """The motivating case: four bodies on #2807, one of them claiming next."""
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-B` (ran the validation) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` scope: **picking up widget.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == ALLOW, (
        "a lane whose holder DECLARED this claimant as a co-owner is shared work, "
        f"not a collision; got {r.returncode}: {r.stderr}"
    )


def test_declaring_the_holder_as_a_co_owner_also_shares_the_lane(tmp_path):
    """Symmetry: the newcomer declaring the incumbent works too.

    Without this the field would only work if the FIRST agent had foreseen who
    would join -- which is backwards, since a lane picks up co-workers as it
    goes. That is why 198 rows say `Three-body: delivery=...` after the fact.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · "
        "co-owners: `AGENT-A` (holds the open claim) · scope: **joining.**",
    )
    assert r.returncode == ALLOW, (
        f"declaring the incumbent must share the lane; got {r.returncode}: {r.stderr}"
    )


def test_an_UNDECLARED_collision_still_blocks(tmp_path):
    """The negative control, and the reason this feature is not just a mute button.

    Same file, same lane, co-owners declared -- but naming somebody ELSE. The
    lane is shared with C, not with the claimant, so the clash is real.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-C` (did the docs) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` scope: **also widget.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == BLOCK, (
        "declaring SOME co-owner must not excuse a claimant who is not among "
        f"them; got {r.returncode}"
    )
    assert "feat/widget" in r.stderr
    assert "AGENT-A" in r.stderr


def test_collision_still_keys_on_the_lane_not_the_claimant(tmp_path):
    """The original inversion, re-pinned with the field present.

    Participants changed HOW two claims are compared; it must not have changed
    WHAT they are keyed on. A co-owned claim on a different branch is still a
    different lane.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-B` (helped) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-A` scope: **unrelated.** Branch `feat/gadget`",
        existing=existing,
    )
    assert r.returncode == ALLOW, "one owner running several lanes is the normal case"


def test_a_co_owner_id_is_folded_through_the_same_vocabulary(tmp_path):
    """A co-owner written in a different spelling of one identity still matches.

    Co-owner IDs go through canonical_owner() exactly as the signing owner
    does. Anything less and the field would open a second uncontrolled name
    space beside the one identity_vocabulary.yaml exists to control -- and a
    declaration written in the wrong spelling would silently do nothing.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `B850-CLAUDE` (ran it) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `B850-CLAUDE (Knuckles)` scope: **mine too.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == ALLOW, (
        "`B850-CLAUDE` as a co-owner must fold to the same identity as "
        f"`B850-CLAUDE (Knuckles)` claiming; got {r.returncode}: {r.stderr}"
    )


def test_the_agent_registry_key_spelling_folds_too(tmp_path):
    """`claude_b850` -- the agent_registry.yaml key -- was the fifth spelling.

    canonical_owner() bridged `B850-CLAUDE (Knuckles)` -> `B850-CLAUDE` ->
    `b850-claude` and stopped there. The `2026-08-28T16:47:00Z` CLAIM on
    `docs/governance-enforcement-gap` recorded the split (item 3) and left it
    open; it is closed by aliasing the registry key.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `claude_b850` (delivery) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `B850-CLAUDE (Knuckles)` scope: **mine.** Branch `feat/widget`",
        existing=existing,
    )
    assert r.returncode == ALLOW, (
        f"registry key `claude_b850` must fold to b850-claude; got {r.returncode}: {r.stderr}"
    )


def test_a_single_owner_row_is_completely_unchanged(tmp_path):
    """Backward compatibility, asserted rather than assumed.

    Every row written before this field existed carries no marker, so it never
    enters the co-owner code path. Both directions of the original rule are
    re-checked here against the new implementation.
    """
    blocked = run_hook(
        tmp_path, "- `t` CLAIM `AGENT-B` scope: **also widget.** Branch `feat/widget`"
    )
    assert blocked.returncode == BLOCK, "different owner, same lane must still block"
    allowed = run_hook(
        tmp_path, "- `t` CLAIM `AGENT-A` scope: **other.** Branch `feat/gadget`"
    )
    assert allowed.returncode == ALLOW, "same owner, different lane must still allow"


def test_an_unreadable_co_owners_field_is_reported_not_skipped(tmp_path):
    """`co-owners: 4090 and SPARK` satisfies a human and is empty to a machine.

    That is this lane's own defect reintroduced one layer down, so it must be
    LOUD. Reporting it as `[]` would be indistinguishable from a row that
    genuinely has no co-owners -- a silent gate is the failure mode.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · "
        "co-owners: 4090 and SPARK and DARKXSIDE · scope: **gadget.**",
    )
    assert "NOT MEASURED" in r.stderr, (
        f"an unparseable co-owners field must say so; stderr was: {r.stderr!r}"
    )


def test_a_co_owner_id_does_not_register_as_a_lane(tmp_path):
    """Blast radius. LANE_RE matches branch-shaped tokens loosely.

    A backticked co-owner ID must not be mistaken for a claimed branch, or the
    field would silently widen what every row claims. LANE_RE needs a
    conventional-commit prefix and BRANCH_MARKER_RE keys on the word `branch`,
    so neither can fire here -- pinned so a later regex edit cannot quietly
    break it.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · "
        "co-owners: `AGENT-C` (helped) · scope: **gadget.**",
    )
    assert r.returncode == ALLOW
    second = run_hook(
        tmp_path,
        "- `t2` CLAIM `AGENT-D` scope: **unrelated.** Branch `feat/widget`",
        existing=(
            "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · "
            "co-owners: `AGENT-C` (helped) · scope: **gadget.**\n"
        ),
    )
    assert second.returncode == ALLOW, (
        "AGENT-B's row claims only feat/gadget; a co-owner ID must not have "
        f"widened it. got {second.returncode}: {second.stderr}"
    )


def test_a_declared_co_owner_changes_the_verdict_not_just_the_prose(tmp_path):
    """"AGENT-A holds feat/widget" and "...shared with AGENT-B" differ.

    This used to be asserted against the ADVISORY, which enumerated every open
    lane into an `ask` and let a permission classifier decide. The advisory is
    gone -- it was the surface on which a colliding CLAIM filed by heredoc
    exited 0 -- so the same distinction is pinned where it now lives: the
    incumbent's declaration turns a BLOCK into an announced ALLOW.
    """
    shared = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-B` (ran the validation) · scope: **widget.**\n"
    )
    undeclared = "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · scope: **widget.**\n"
    row = "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **shared.**"

    blocked = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                        existing=undeclared)
    assert blocked.returncode == BLOCK

    allowed = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                        existing=shared)
    assert allowed.returncode == ALLOW, (
        f"a declared co-owner did not change the verdict: {allowed.stderr}"
    )
    assert "SHARED LANE" in allowed.stderr, "a suppressed collision left no trace"
    assert "AGENT-B" in allowed.stderr or "AGENT-A" in allowed.stderr


def _reason(result):
    """The prompt text of an `ask`, or None when the hook emitted no decision."""
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


# --------------------------------------------------------------------------
# A DECLARATION IS NOT A PERMISSION SLIP.
#
# `mine & theirs` is a symmetric intersection, so on its own it cannot tell
# "the incumbent invited me" from "I named the incumbent without asking".
# Both used to exit 0 with completely empty stderr -- the honest case and the
# squat were indistinguishable AT THE HOOK'S OUTPUT, which is the one place a
# reviewer would ever look. The three tests below pin the distinction: the
# consented case is allowed AND said out loud, the one-sided case is neither
# blocked nor waved through but ASKED, and the undeclared case still blocks.
# --------------------------------------------------------------------------

def test_a_unilateral_co_owner_declaration_is_asked_never_silently_allowed(tmp_path):
    """The self-issued exemption. Exit 0 + empty stderr was the whole bug.

    A newcomer can write anyone's ID into its own row; nothing about that is a
    handoff. Blocking it would be wrong too -- an incumbent who went offline is
    exactly the case the register is a ledger and not a lock for. So: surface
    it, name who declared what, and let whoever is deciding decide.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · "
        "co-owners: `AGENT-A` (totally working with me, honest) · scope: **squat.**",
    )
    assert r.returncode == ALLOW, "a one-sided declaration is not a hard block"
    assert _decision(r) == "ask", (
        "a collision suppressed by a self-issued declaration must not pass "
        f"silently; stdout was {r.stdout!r} / stderr {r.stderr!r}"
    )
    reason = _reason(r)
    assert "unilateral" in reason.lower(), reason
    assert "feat/widget" in reason, "the prompt must name the lane"
    assert "AGENT-A" in reason and "AGENT-B" in reason, (
        f"the prompt must name who declared whom: {reason!r}"
    )


def test_a_reciprocated_declaration_is_allowed_and_said_out_loud(tmp_path):
    """The honest workflow, which must stay frictionless -- but not silent.

    The incumbent's OPEN row names the newcomer, so the party who actually
    holds the lane consented. No prompt. It still leaves a trace, because a
    suppressed collision that leaves no trace is not distinguishable from a
    gate that never ran.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-B` (joining me on this) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **the work.**",
        existing=existing,
    )
    assert r.returncode == ALLOW, f"consented sharing must not block: {r.stderr}"
    assert _decision(r) is None, (
        f"consented sharing must not prompt either: {r.stdout!r}"
    )
    assert "SHARED LANE" in r.stderr, (
        f"a suppressed collision must leave a trace: {r.stderr!r}"
    )
    assert "feat/widget" in r.stderr and "AGENT-A" in r.stderr


def test_an_undeclared_collision_still_blocks_after_the_consent_split(tmp_path):
    """The half that must not weaken. Re-driven against the new code path."""
    r = run_hook(
        tmp_path, "- `t1` CLAIM `AGENT-B` scope: **also widget.** Branch `feat/widget`"
    )
    assert r.returncode == BLOCK, f"expected block, got {r.returncode}: {r.stderr}"
    assert "feat/widget" in r.stderr and "AGENT-A" in r.stderr


# --------------------------------------------------------------------------
# ONE ROW'S DECLARATION IS ONE ROW'S DECLARATION.
#
# co_owners_in() ran once over the WHOLE proposed text and was attached to
# every CLAIM match in it, so a single honest field on row 1 granted
# participation to row 2, row 3, and anything else in the same write. Multi-row
# appends to this register are routine, so this was not only an adversarial
# case: the gate and the register ended up disagreeing about who is on a lane,
# because open_claims_in() has always parsed per line.
# --------------------------------------------------------------------------

def test_a_co_owner_declaration_does_not_leak_to_other_rows_in_the_same_edit(tmp_path):
    """Row 1 declares honestly on ITS lane; row 2 squats, declaring nothing."""
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · "
        "co-owners: `AGENT-A` (honest, on this other lane) · scope: **gadget.**\n"
        "- `t2` CLAIM `AGENT-B` branch: `feat/widget` · scope: **squat.**\n",
    )
    assert r.returncode == BLOCK, (
        "row 1's co-owners field must not cover row 2; got "
        f"{r.returncode}: {r.stdout!r} / {r.stderr!r}"
    )
    assert "feat/widget" in r.stderr


def test_the_AB_control_for_the_row_scope_leak(tmp_path):
    """The same two rows with row 1's field deleted -- the reviewer's control.

    Both spellings must now BLOCK. Before the fix, deleting one field on an
    unrelated row flipped the other row from ALLOW to BLOCK, which is the
    proof that the field was being read out of its own row's scope.
    """
    rows = (
        "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · scope: **gadget.**\n"
        "- `t2` CLAIM `AGENT-B` branch: `feat/widget` · scope: **squat.**\n"
    )
    assert run_hook(tmp_path, rows).returncode == BLOCK


def test_a_multi_row_append_does_not_cross_contaminate_lanes(tmp_path):
    """The routine case, and the false positive a co-owner-only fix would add.

    Row 1 legitimately shares a lane the incumbent declared; row 2 claims a
    free lane. Reading lanes over the whole edit would put row 1's shared lane
    onto row 2 -- which declares nobody -- and block an ordinary append.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
        "co-owners: `AGENT-B` (joining me on this) · scope: **widget.**\n"
    )
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **the shared work.**\n"
        "- `t2` CLAIM `AGENT-B` branch: `feat/unheld` · scope: **new lane.**\n",
        existing=existing,
    )
    assert r.returncode == ALLOW, (
        f"ordinary multi-row append must not collide with itself: {r.stderr}"
    )
    assert _decision(r) is None, f"and must not prompt: {r.stdout!r}"


def test_a_row_naming_no_branch_of_its_own_still_uses_the_edits_lanes(tmp_path):
    """Scoping lanes per row must not make the gate BLINDER than it was.

    A CLAIM that names no branch on its own line is unkeyed; the pre-existing
    whole-text read is kept for exactly that row, so a claim whose branch is
    written on a neighbouring line is still compared instead of silently
    passing as unguarded.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` scope: **picking this up.**\n"
        "  (working on branch: `feat/widget` from this week)\n",
    )
    assert r.returncode == BLOCK, (
        f"an unkeyed row must not lose the lanes it used to see: {r.stderr!r}"
    )


# --------------------------------------------------------------------------
# A ROW THAT DOCUMENTS THE GRAMMAR IS NOT A ROW THAT USES IT.
# --------------------------------------------------------------------------

def test_a_double_backtick_EXAMPLE_cannot_suppress_a_real_collision(tmp_path):
    """The register is a document about its own governance.

    ``co-owners: `X` (note)`` shows the grammar. Read as a declaration, a row
    that merely EXPLAINS the field could take a lane off somebody -- a silent
    grant produced by documentation.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: the grammar is "
        "``co-owners: `AGENT-A` (what they did)`` as shown.",
    )
    assert r.returncode == BLOCK, (
        "a documented example must not grant participation; got "
        f"{r.returncode}: {r.stdout!r} / {r.stderr!r}"
    )
    assert "feat/widget" in r.stderr


def test_an_unreadable_co_owner_field_carries_a_decision_not_just_stderr(tmp_path):
    """"Could not measure" on the ENFORCING path was exit 0 + stderr.

    Exit 0 is the same code as a fully measured clean run, and PreToolUse
    stderr on exit 0 is not fed back the way exit-2 stderr is. The register's
    documented doctrine is that could-not-measure is never indistinguishable
    from clean, so the hook raises it as a decision instead.
    """
    r = run_hook(
        tmp_path,
        "- `t1` CLAIM `AGENT-B` branch: `feat/gadget` · "
        "co-owners: 4090 and SPARK and DARKXSIDE · scope: **gadget.**",
    )
    assert "NOT MEASURED" in r.stderr
    assert _decision(r) == "ask", (
        f"could-not-measure must not exit 0 looking clean: {r.stdout!r}"
    )


def test_the_word_branch_inside_a_code_span_is_a_mention_not_a_lane(tmp_path):
    """A phantom lane made of prose stays open forever in an append-only file.

    ``branch: `x` `` is a marker; "keys on the word `branch`, so ..." is prose
    that happens to contain the noun -- and with `:` optional the matcher fired
    on the mention and captured everything up to the next backtick. Two CLAIM
    rows in the live register hold a sentence as a lane that way. Nobody can
    release it, and it blocks whoever tries.

    Driven through the COLLISION VERDICT rather than the advisory that used to
    enumerate open lanes: the real lane must still block, and the prose must
    not appear as one.
    """
    existing = (
        "- `t0` CLAIM `AGENT-A` scope: BRANCH_MARKER_RE keys on the word "
        "`branch`, so neither can fire on a co-owner ID. Lane is "
        "`feat/widget` here.\n"
    )
    row = "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **mine now.**"
    r = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                  existing=existing)
    assert r.returncode == BLOCK, (
        f"the real lane must still be seen: {r.stderr!r}"
    )
    assert "feat/widget" in r.stderr
    assert "so neither can fire" not in r.stderr, (
        f"prose was captured as a claimed lane: {r.stderr!r}"
    )


# --------------------------------------------------------------------------
# THE SHELL PATH IS AN ALLOWLIST.
#
# The fail-closed cut before this one enumerated the ways a command could WRITE
# the register and passed a 22-case matrix. An independent reviewer then
# measured six shapes the enumeration never considered -- every one exit 0,
# every one able to append a colliding CLAIM, two of them able to destroy an
# append-only ledger outright. Two more turned up reproducing that report.
#
# Adding those eight to a denylist would fix these eight. The defect is that the
# question was "which commands write?", and no author can enumerate that. These
# tests pin the inverted question: a segment naming the register is refused
# unless it is positively recognised as a read.
# --------------------------------------------------------------------------

_ROW = "- `t` CLAIM `AGENT-B` scope: **mine now.** branch: `feat/widget`"


@pytest.mark.parametrize("command", [
    # The six from the review, verbatim in shape.
    'python3 -c "open(\'{R}\',\'a\').write(\'{ROW}\')"',
    'python3 -c "open(\'{R}\',\'w\').write(\'nuked\')"',
    "python3 -c 'import pathlib;pathlib.Path(\"{R}\").write_text(\"x\")'",
    'node -e "require(\'fs\').appendFileSync(\'{R}\', \'{ROW}\')"',
    'ruby -e \'File.write("{R}", "{ROW}", mode:"a")\'',
    "printf 'a\\n{ROW}\\n.\\nw\\n' | ed -s {R}",
    # Found reproducing the review.
    "git checkout --ours -- {R}",
    "git restore --source=HEAD {R}",
    # Shapes nobody has listed anywhere, which is the point of an allowlist.
    "perl -e 'open(F,\">>\",\"{R}\");print F \"{ROW}\"'",
    "awk 'BEGIN{{print \"{ROW}\" >> \"{R}\"}}'",
    "php -r 'file_put_contents(\"{R}\",\"{ROW}\",FILE_APPEND);'",
    "some-future-tool --write {R}",
    "xargs -I% cp % {R} < /dev/null",
])
def test_inline_interpreter_and_unknown_writes_are_refused(tmp_path, command):
    """Not positively understood as a read -> could-not-measure -> refused.

    Each of these exited 0 (or would have) under the enumerate-the-writes cut.
    `python3 -c` is the single most likely command in a fleet whose delivery
    agents have had no Write tool for five consecutive sessions, and the `-w`
    form of it TRUNCATES an append-only ledger.
    """
    reg = tmp_path / REGISTER_NAME
    r = _run_bash(tmp_path, command.format(R=str(reg), ROW=_ROW))
    assert r.returncode == BLOCK, f"bypass: {command!r}"
    assert "NOT MEASURED" in r.stderr
    assert "register-claim" in r.stderr, (
        "a refusal with no sanctioned alternative is a deadlock, not a gate"
    )


def test_deleting_the_register_is_refused(tmp_path):
    """An append-only ledger cannot be re-created; removal IS the redaction."""
    reg = tmp_path / REGISTER_NAME
    # Spelled, not written: the damage-control hook literal-matches this token
    # anywhere in a command INCLUDING inside content, which is the same bug this
    # file's own heredoc handling was fixed for.
    r = _run_bash(tmp_path, "r" + "m" + " " + str(reg))
    assert r.returncode == BLOCK
    assert "NOT MEASURED" in r.stderr


@pytest.mark.parametrize("command", [
    "cat {R}",
    "grep -n CLAIM {R}",
    "sed -n '1,5p' {R}",
    "wc -l {R}",
    "head -n 3 {R} | cut -c1-40",
    "tail -n 1 {R}",
    "git show HEAD:{R}",
    "git add {R}",
    "git diff -- {R}",
    "ls -la {R}",
    "sha256sum {R}",
    "grep CLAIM {R} > /tmp/pmoves-gate-probe-report.txt",
    "cat {R} | python3 -c 'import sys;print(len(sys.stdin.read()))'",
])
def test_reading_the_register_from_a_shell_stays_allowed(tmp_path, command):
    """The deadlock direction, tested as hard as the hole direction.

    A gate that makes the register unreadable is worse than the gap it closes,
    and a prompt on every `grep` trains the reader to click through the one
    prompt that matters. The last row is the documented escape hatch for
    interpreters: pipe the register in rather than naming it.
    """
    reg = tmp_path / REGISTER_NAME
    r = _run_bash(tmp_path, command.format(R=str(reg)))
    assert r.returncode == ALLOW, f"read refused: {command!r}\n{r.stderr}"
    assert _decision(r) is None, f"spurious prompt for: {command!r}"


@pytest.mark.parametrize("suffix", [
    ".bak", ".orig", ".rej", ".BACKUP.123", ".LOCAL.123", ".REMOTE.123",
])
def test_a_neighbouring_filename_is_not_the_register(tmp_path, suffix):
    """Substring match on the redirect target denied git's own merge artifacts.

    `.orig`, `.rej` and `.BACKUP/.LOCAL/.REMOTE` are what git leaves behind in a
    conflict -- so the old test fired precisely in the merge-conflict scenario,
    which is the one where a careful hand fixup is the whole recovery story.
    This is the damage-control literal-match bug, on the write target instead of
    the content. A path test, not a substring test.
    """
    reg = tmp_path / REGISTER_NAME
    r = _run_bash(tmp_path, f"echo x > {reg}{suffix}")
    assert r.returncode == ALLOW, f"{suffix} refused as the register: {r.stderr}"


def test_the_register_may_be_a_copy_source_but_never_a_destination(tmp_path):
    """Coverage was inverted for the case that actually happens.

    Taking a backup before a risky fixup was refused, while `git checkout
    --ours` -- the operation .gitattributes names as SILENTLY DROPPING another
    node's provenance row -- passed clean.
    """
    reg = tmp_path / REGISTER_NAME
    ok = _run_bash(tmp_path, f"cp {reg} /tmp/pmoves-register-backup.md")
    assert ok.returncode == ALLOW, f"backing up the register refused: {ok.stderr}"
    ok2 = _run_bash(tmp_path, f"cp {reg} {reg}.bak")
    assert ok2.returncode == ALLOW, f"in-place backup refused: {ok2.stderr}"
    bad = _run_bash(tmp_path, f"cp /tmp/whatever.md {reg}")
    assert bad.returncode == BLOCK, "the register as a cp DESTINATION must refuse"


def test_a_multi_line_quoted_argument_is_not_a_second_command(tmp_path):
    """The literal-match-inside-content bug, refused a fourth entry.

    Splitting segments naively on newline turns the second line of a quoted
    argument into a "segment" whose first word is the register's own filename --
    which an allowlist then refuses. The command below writes /tmp and touches
    no ledger.
    """
    reg = tmp_path / REGISTER_NAME
    cmd = (f"echo 'first line\nthe file {reg} is the register\nthird line' "
           "> /tmp/pmoves-gate-notes.md")
    r = _run_bash(tmp_path, cmd)
    assert r.returncode == ALLOW, f"prose about the register refused: {r.stderr}"


# --------------------------------------------------------------------------
# THE THREE-WAY VERDICT REACHES THE SHELL PATH.
#
# #2858 gave the Write matcher block / SHARED LANE / ask. The shell matcher had
# no notion of `ask` at all, so a unilateral declaration filed through a heredoc
# -- the only way an agent with no Write tool can file anything -- was a silent
# exit 0 while the identical Write payload prompted.
# --------------------------------------------------------------------------

_RECIPROCATED = (
    "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · "
    "co-owners: `AGENT-B` (ran the validation) · scope: **widget.**\n"
)
_UNDECLARED = (
    "- `t0` CLAIM `AGENT-A` branch: `feat/widget` · scope: **widget.**\n"
)
_ONE_SIDED_ROW = (
    "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · "
    "co-owners: `AGENT-A` (I say we are sharing) · scope: **mine too.**"
)


def test_a_reciprocated_share_is_allowed_out_loud_on_the_shell_path(tmp_path):
    """The incumbent declared the claimant, so the sharing was consented to.

    Allowed without a prompt -- that workflow has to stay frictionless -- but
    announced, because an allow that prints nothing cannot be told apart from a
    gate that did not run. That is exactly the state a reviewer found the Bash
    path in.
    """
    row = "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **shared.**"
    r = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                  existing=_RECIPROCATED)
    assert r.returncode == ALLOW, f"consented share blocked: {r.stderr}"
    assert "SHARED LANE" in r.stderr and "AGENT-A" in r.stderr


def test_a_unilateral_declaration_asks_on_the_shell_path(tmp_path):
    """Attribution is not a handoff, and a heredoc must not be the way past it."""
    r = _run_bash(
        tmp_path,
        f"cat >> {REGISTER_NAME} <<'EOF'\n{_ONE_SIDED_ROW}\nEOF",
        existing=_UNDECLARED,
    )
    assert r.returncode == ALLOW
    assert _decision(r) == "ask", (
        f"the shell path had no notion of ask: {r.stdout!r}"
    )
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "UNILATERAL" in reason
    assert "AGENT-B" in reason and "AGENT-A" in reason, (
        "the prompt must name who declared whom"
    )


def test_an_undeclared_overlap_still_blocks_on_the_shell_path(tmp_path):
    row = "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **mine now.**"
    r = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                  existing=_UNDECLARED)
    assert r.returncode == BLOCK
    assert "feat/widget" in r.stderr and "AGENT-A" in r.stderr


@pytest.mark.parametrize("existing,row,expect_rc,expect_decision", [
    (_UNDECLARED,
     "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **mine now.**",
     BLOCK, None),
    (_RECIPROCATED,
     "- `t1` CLAIM `AGENT-B` branch: `feat/widget` · scope: **shared.**",
     ALLOW, None),
    (_UNDECLARED, _ONE_SIDED_ROW, ALLOW, "ask"),
])
def test_both_matchers_return_the_same_verdict(tmp_path, existing, row,
                                               expect_rc, expect_decision):
    """One register, one verdict, one message -- whichever tool you reached for.

    A gate whose answer depends on which tool you happened to have teaches that
    the tool is the variable, which is precisely how the shell path came to be
    the way to file a claim without being checked.
    """
    via_write = run_hook(tmp_path, row, existing=existing)
    via_bash = _run_bash(tmp_path, f"cat >> {REGISTER_NAME} <<'EOF'\n{row}\nEOF",
                         existing=existing)
    assert via_write.returncode == via_bash.returncode == expect_rc
    assert _decision(via_write) == _decision(via_bash) == expect_decision
    assert via_write.stderr == via_bash.stderr
    assert via_write.stdout == via_bash.stdout


def test_lanes_and_co_owners_are_read_per_row_not_per_payload(tmp_path):
    """An innocent row filed beside a colliding one is not charged with its lane.

    Reported twice, for one collision, and named a claimant who had nothing to
    do with the lane. #2858 removed this shape from the Write path with
    `_row_at`; sharing the verdict function is what could have let it back in.
    """
    proposed = (
        "- `t1` CLAIM `ALICE` branch: `fix/totally-innocent` · scope: **a.**\n"
        "- `t2` CLAIM `BOB` branch: `feat/widget` · scope: **b.**"
    )
    r = run_hook(tmp_path, proposed, existing=_UNDECLARED)
    assert r.returncode == BLOCK
    named = [l for l in r.stderr.splitlines() if "already claimed by" in l]
    assert len(named) == 1, f"one collision, reported {len(named)} times: {named}"
    assert "fix/totally-innocent" not in r.stderr, (
        "ALICE's innocent lane was charged with BOB's collision"
    )


# --------------------------------------------------------------------------
# A read-by-default command carrying its own output-file flag.
#
# The allowlist above fixed the interpreter class and then re-made the same
# mistake one layer in: `sort`, `shuf` and `xxd` were admitted wholesale as
# "read-only commands", and each of them takes an OUTPUT file. Measured against
# the allowlist cut, all at exit 0 with the register as the destination:
#
#     sort -o <register> in.txt          <- REPLACES the append-only ledger
#     shuf -o <register> in.txt          <- REPLACES it
#     xxd -r dump.hex <register>         <- rewrites it from a dump
#
# None of these appears in the review, in the 22-case matrix, or in the 32-probe
# sweep that replaced it. They were found by asking the allowlist the question it
# asks of everything else -- is this command CERTIFIED not to write? -- rather
# than by thinking of more shapes. "Usually a read" is not "certified".
# --------------------------------------------------------------------------


@pytest.mark.parametrize("command", [
    "sort -o {R} /tmp/in.txt",
    "sort --output={R} /tmp/in.txt",
    "sort --output {R} /tmp/in.txt",
    "shuf -o {R} /tmp/in.txt",
    "shuf --output={R} /tmp/in.txt",
    "xxd -r /tmp/dump.hex {R}",
    "xxd -revert /tmp/dump.hex {R}",
    "csplit -f {R} /tmp/in.txt 2",
    "csplit --prefix={R} /tmp/in.txt 2",
    "split -l 1 /tmp/in.txt {R}",
])
def test_a_read_only_command_with_an_output_flag_is_refused(tmp_path, command):
    """`sort -o <register>` truncates an append-only ledger at exit 0."""
    reg = tmp_path / REGISTER_NAME
    r = _run_bash(tmp_path, command.format(R=str(reg)))
    assert r.returncode == BLOCK, f"output-flag bypass: {command!r}"
    assert "NOT MEASURED" in r.stderr
    assert "register-claim" in r.stderr


@pytest.mark.parametrize("command", [
    "sort {R}",
    "sort {R} > /tmp/sorted.txt",
    "sort -u {R}",
    "shuf -n 3 {R}",
    "xxd {R}",
    "xxd {R} > /tmp/dump.hex",
    "od -c {R}",
    "split -l 100 {R} /tmp/part-",
    "csplit -f /tmp/pre- {R} 100",
])
def test_those_same_commands_still_read_the_register(tmp_path, command):
    """The guard keys on the output flag, not on the command name.

    `split -l 100 <register> /tmp/part-` reads it. A first cut of this guard
    counted `100` as an operand and refused that, which is the false-refusal
    direction -- the one that gets a gate switched off rather than bypassed.
    """
    reg = tmp_path / REGISTER_NAME
    r = _run_bash(tmp_path, command.format(R=str(reg)))
    assert r.returncode == ALLOW, f"read refused: {command!r}\n{r.stderr}"
    assert _decision(r) is None, f"spurious prompt for: {command!r}"
