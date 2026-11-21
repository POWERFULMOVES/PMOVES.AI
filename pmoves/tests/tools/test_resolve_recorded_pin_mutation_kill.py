"""Mutation-kill harness: the recorded-pin gates must BITE when the defect is
put back.

THE DEFECT CLASS
----------------
`integrations-ghcr.yml` resolved a fork-backed entry's build context by
cloning a MOVING BRANCH (`git clone --depth=1 --branch "$cfg_ref"`), while
PMOVES.AI records an exact gitlink for the same fork. The image the lane
publishes was therefore not reproducible from the repository state.

The fix has two links -- a RESOLVER that turns a fork URL into the recorded
commit, and a WORKFLOW that checks that commit out instead of the branch. This
harness mutates BOTH, because a harness that could only ever rewrite one of
them could not prove that the other is load-bearing.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
The house budget model charges a mutation-kill harness by its WALL CLOCK: a
file that costs more than ``FALLBACK_FILE_TIMEOUT`` (60s) is killed when the
ratchet isolates it, and a healthy-but-slow file is then reported as a broken
one (see ``pmoves/configs/pytest_ratchet/_slow_files.yaml``). Every phase
here spawns a full ``python -m pytest`` child, and one child startup is ~1.6s
on this host -- irreducible.

So the GREEN phases run ONCE for the whole session, over every target test,
instead of once per mutation:

  * GREEN BEFORE runs once, before any mutation, over ALL the target tests;
  * RED AFTER runs per mutation, over the ONE named test (this is the only
    phase that has to be per-mutation: the source under test differs);
  * GREEN AFTER runs once, after every mutation has been restored.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it. A harness may
only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below rewrites the CALL the production path makes, or removes a
rule the production path relies on. None of them re-types the fix's own
expression: each one is a defect a reviewer could plausibly introduce, and
each is killed by a test that exercises the production path.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_resolve_recorded_pin_mutation_kill.py -v

Hermetic: no network, no docker, no gh, no credentials. It mutates one tool
and one workflow file in this repo and restores them.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from pmoves.tests import mutation_backup

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "resolve_recorded_pin.py"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "integrations-ghcr.yml"
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_resolve_recorded_pin.py"

_PYTEST_TIMEOUT_SECONDS = 600.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-recorded-pin-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    old: str
    new: str
    target_test: str
    rationale: str
    target_file: Path


MUTATIONS: list[Mutation] = [
    # ------------------------------------------------------------------
    # the resolver
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_nested_submodule_preferred_over_the_top_level_one",
        old="""    top_level = {p: s for p, s in resolved.items() if "/" not in p}
    if len(top_level) == 1:
        chosen_path, chosen_sha = next(iter(top_level.items()))""",
        new="""    top_level = {p: s for p, s in resolved.items() if "/" in p}
    if len(top_level) == 1:
        chosen_path, chosen_sha = next(iter(top_level.items()))""",
        target_test="test_the_tool_prefers_the_top_level_submodule",
        rationale=(
            "PMOVES-Archon is tracked by TWO submodules that pin DIFFERENT "
            "commits: `PMOVES-Archon` (490d74bc) and "
            "`pmoves/integrations/archon` (8d135dab). The top-level one is the "
            "answer, because `build-images.yml` builds "
            "`github.workspace/<repo>`. Preferring the nested one would make "
            "the two publishers disagree about what they are building."
        ),
        target_file=TOOL,
    ),
    Mutation(
        name="M2_the_tree_read_without_recursion",
        old="""    rc, out = _git(repo_root, "ls-tree", "-r", "HEAD")""",
        new="""    rc, out = _git(repo_root, "ls-tree", "HEAD")""",
        target_test="test_the_tool_resolves_a_nested_submodule",
        rationale=(
            "PMOVES.AI nests submodules INSIDE directories -- "
            "`pmoves/integrations/archon` is one -- and a non-recursive "
            "`git ls-tree HEAD` lists only the top level. The nested "
            "submodule would then read as declared-but-unrecorded, and the "
            "resolver would refuse a fork it can in fact resolve."
        ),
        target_file=TOOL,
    ),
    Mutation(
        name="M3_an_ambiguous_fork_reported_as_not_tracked",
        old="""    raise ResolutionError(
        EXIT_AMBIGUOUS,""",
        new="""    raise ResolutionError(
        EXIT_NOT_TRACKED,""",
        target_test="test_the_tool_refuses_an_ambiguous_fork",
        rationale=(
            "Exit 3 means 'this fork is not tracked, so a branch is the only "
            "source'. Exit 4 means 'this fork IS tracked and the answer is not "
            "knowable'. Collapsing them tells the caller to build a moving "
            "branch for a fork the repository says it pins -- the exact defect "
            "this resolver exists to remove."
        ),
        target_file=TOOL,
    ),
    # ------------------------------------------------------------------
    # the workflow
    # ------------------------------------------------------------------
    Mutation(
        name="M4_the_prepare_step_no_longer_checks_out_the_recorded_commit",
        old="""              git -C integration-src fetch --depth=1 origin "$cfg_pin"
              git -C integration-src checkout --detach "$cfg_pin"
              echo "✔ pinned to the recorded commit $cfg_pin\"""",
        new="""              git -C integration-src fetch --depth=1 origin "$cfg_pin"
              echo "✔ fetched the recorded commit $cfg_pin\"""",
        target_test="test_the_prepare_step_checks_out_the_recorded_commit",
        rationale=(
            "Fetching the recorded commit without checking it out leaves the "
            "working tree on the BRANCH. The build would then be from the "
            "moving ref again, while the log claimed the opposite."
        ),
        target_file=WORKFLOW_FILE,
    ),
    Mutation(
        name="M5_the_pin_step_falls_back_to_the_branch_when_the_resolver_fails",
        old="""            *)
              echo "::error::could not resolve the recorded commit for ${cfg_url} (exit ${status})"
              exit 1
              ;;""",
        new="""            *)
              echo "::warning::could not resolve the recorded commit for ${cfg_url} (exit ${status}); falling back to the branch ref"
              pin=""
              ;;""",
        target_test=(
            "test_the_workflow_step_fails_closed_on_a_resolver_failure"
        ),
        rationale=(
            "An ambiguous fork, a declared-but-unrecorded submodule, an "
            "unreadable tree: all three mean the recorded commit is not "
            "knowable. Falling back to the branch would rebuild the defect "
            "quietly, and a warning in a log nobody reads is not a guard."
        ),
        target_file=WORKFLOW_FILE,
    ),
    # ------------------------------------------------------------------
    # the review round: four defects the bots found
    # ------------------------------------------------------------------
    Mutation(
        name="M6_a_missing_sibling_declaration_falls_back_to_the_recorded_one",
        old="""    if missing:
        # ANY declared-but-unrecorded submodule makes the repository state
        # INCONSISTENT -- even when a SIBLING declaration IS recorded.
        #
        # Falling back to the sibling would publish a commit the tree does not
        # record for the PREFERRED candidate, and `build-images.yml` -- which
        # builds the top-level path -- would then disagree with this lane
        # about what is being built. The documented contract says exit 5 for a
        # declared-but-unrecorded submodule, and the contract does not carry a
        # "unless another one happens to be there" clause.
        raise ResolutionError(
            EXIT_INCONSISTENT,
            f"{url} is declared as a submodule ({', '.join(sorted(missing))}) but "
            f"the tree records no gitlink for it; the repository state is "
            f"inconsistent",
        )""",
        new="""    if missing and not resolved:
        raise ResolutionError(
            EXIT_INCONSISTENT,
            f"{url} is declared as a submodule ({', '.join(sorted(missing))}) but "
            f"the tree records no gitlink for it; the repository state is "
            f"inconsistent",
        )""",
        target_test=(
            "test_the_tool_fails_closed_when_a_sibling_declaration_has_no_gitlink"
        ),
        rationale=(
            "This is the EXACT pre-fix defect the review found: a fork whose "
            "TOP-LEVEL declaration is unrecorded but whose NESTED sibling IS "
            "recorded resolved to the sibling with exit 0, even though the "
            "documented contract says a declared-but-unrecorded submodule is "
            "INCONSISTENT (5) and must fail. The top-level path is the one "
            "`build-images.yml` builds, so the fallback would make the two "
            "publishers disagree about what they are building."
        ),
        target_file=TOOL,
    ),
    Mutation(
        name="M7_the_scp_style_url_no_longer_reduced",
        old="""    scp = _SCP_LIKE.match(cleaned)
    if scp:
        cleaned = scp.group("path")""",
        new="""    scp = None
    if scp:
        cleaned = scp.group("path")""",
        target_test="test_the_tool_normalises_the_scp_style_url",
        rationale=(
            "`git@host:org/repo.git` is the spelling git itself prints for an "
            "SSH remote, so a fork's `.gitmodules` entry can carry it. With "
            "the rule removed the url cannot be reduced to `<org>/<repo>`, "
            "the fork reads as NOT TRACKED, and exit 3 tells the caller to "
            "build the MOVING BRANCH -- the exact defect this tool exists to "
            "kill, reached through a url spelling."
        ),
        target_file=TOOL,
    ),
    Mutation(
        name="M8_the_broad_lookuperror_catch_is_back",
        old="""    except NotTrackedError:""",
        new="""    except LookupError:""",
        target_test=(
            "test_the_tool_does_not_report_an_unrelated_lookup_error_as_not_tracked"
        ),
        rationale=(
            "`KeyError` and `IndexError` are `LookupError` subclasses, so the "
            "broad catch turns any subscript mistake inside the resolution "
            "into exit 3 -- 'not tracked, build the branch'. The dedicated "
            "exception is what keeps the one failure the caller may paper "
            "over from sharing a door with the ones it may not."
        ),
        target_file=TOOL,
    ),
    Mutation(
        name="M9_a_pin_input_dropped_from_the_workflow_path_filter",
        old="""      - 'Pmoves-Health-wger'
""",
        new="""      - 'Pmoves-Health-wger-REMOVED'
""",
        target_test="test_the_workflow_runs_when_a_recorded_pin_can_change",
        rationale=(
            "The pin is STATIC now: advancing it does not change what the "
            "next run builds, so the pin's own inputs -- the submodule paths, "
            ".gitmodules, the resolver -- must trigger the workflow. Drop one "
            "and advancing that pin leaves the published image on the "
            "PREVIOUS commit, with nothing red."
        ),
        target_file=WORKFLOW_FILE,
    ),
]


def _run_pytest(
    node_ids: list[str], timeout: float = _PYTEST_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *node_ids,
            "-q",
            "-p",
            "no:warnings",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def _node_id(mutation: Mutation) -> str:
    return f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"


_GREEN_BEFORE: list[subprocess.CompletedProcess] = []


def _green_before() -> list[subprocess.CompletedProcess]:
    """GREEN BEFORE, once for the whole session: the pristine source must pass
    EVERY target test."""
    if not _GREEN_BEFORE:
        node_ids = [_node_id(mutation) for mutation in MUTATIONS]
        _GREEN_BEFORE.append(_run_pytest(node_ids))
    return _GREEN_BEFORE


def _named_test_failed(proc: subprocess.CompletedProcess, test_name: str) -> bool:
    """True only if pytest's own short summary names THIS test as failed.

    A collection error, a timeout, or an unrelated failure also makes pytest
    exit non-zero; none of those is a kill.
    """
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
            if line.startswith("FAILED ") and test_name in line:
                return True
    return False


@contextlib.contextmanager
def _file_lock(path: Path):
    """Cross-process lock so two harnesses cannot mutate the tree at once."""
    handle = path.open("a+", encoding="utf-8")
    acquired = False
    try:
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                time.sleep(0.2)
        if not acquired:
            raise TimeoutError(f"could not acquire {path}")
        yield
    finally:
        if acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover - POSIX hosts
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


def _apply_mutation(mutation: Mutation, original: str) -> str:
    """Return the mutated source, or raise if the anchor does not match.

    A mutation whose anchor has drifted must FAIL LOUDLY. Silently mutating
    nothing would produce a green harness that proves nothing.
    """
    if mutation.old not in original:
        raise AssertionError(
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.target_file.name}. The source changed -- update the "
            f"mutation.\n--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def _read_source(path: Path) -> tuple[str, bool]:
    """(text, uses_crlf) for a source file.

    The text is normalised to ``\\n`` so a mutation anchor is line-ending
    independent; the flag records the file's OWN convention so the restore can
    put it back exactly as it was.
    """
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def _write_source(path: Path, text: str, crlf: bool) -> None:
    """Write a source file back in its own line-ending convention."""
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def test_every_mutation_anchor_is_present() -> None:
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original, _crlf = _read_source(mutation.target_file)
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.target_file.name} -- the source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED, with a byte-exact restore. GREEN is batched (see the
    module docstring): it runs once before any mutation and once after the
    last restore, over every target test."""
    node_id = _node_id(mutation)
    target = mutation.target_file
    original, crlf = _read_source(target)
    original_bytes = target.read_bytes()

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH), mutation_backup.file_lock(
        mutation_backup.lock_path(REPO_ROOT, target)
    ):
        # 1. GREEN BEFORE (batched over every target test)
        before = _green_before()[0]
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        # The pristine bytes go on disk BEFORE the mutation, so a process that
        # is KILLED mid-mutation cannot leave the tree dirty for the next
        # session to inherit. See pmoves/tests/mutation_backup.py.
        mutation_backup.write_backup(REPO_ROOT, target, original_bytes)
        try:
            _write_source(target, mutated, crlf)

            # 2. RED AFTER -- the NAMED test must die
            after = _run_pytest([node_id])
            assert after.returncode != 0, (
                f"{mutation.name}: the mutation SURVIVED -- "
                f"{mutation.target_test} still passed\n{after.stdout[-4000:]}"
            )
            assert _named_test_failed(after, mutation.target_test), (
                f"{mutation.name}: pytest failed, but NOT the named test "
                f"{mutation.target_test}\n{after.stdout[-4000:]}\n{after.stderr[-2000:]}"
            )
        finally:
            # 3. restore -- byte-exact, line endings included
            _write_source(target, original, crlf)
            restored = target.read_bytes()
            assert restored == original_bytes, (
                f"{mutation.name}: the restore was not byte-exact"
            )
            # The backup is dropped only AFTER a byte-exact restore. If the
            # assert above fails, the backup is the only good copy of the
            # pristine source, and the next session must still be able to
            # restore it -- so it stays on disk.
            mutation_backup.clear_backup(REPO_ROOT, target)


def test_the_sources_are_intact_after_the_mutation_suite() -> None:
    """GREEN AFTER: after every mutation has been restored, every target test
    must pass again -- and the sources must be byte-identical to the
    originals."""
    tool = TOOL.read_text(encoding="utf-8")
    assert 'rc, out = _git(repo_root, "ls-tree", "-r", "HEAD")' in tool
    assert 'top_level = {p: s for p, s in resolved.items() if "/" not in p}' in tool
    assert "EXIT_AMBIGUOUS," in tool

    workflow = WORKFLOW_FILE.read_text(encoding="utf-8")
    assert 'git -C integration-src checkout --detach "$cfg_pin"' in workflow
    assert (
        'echo "::error::could not resolve the recorded commit for ${cfg_url} '
        '(exit ${status})"' in workflow
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
