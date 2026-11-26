"""Mutation-kill harness: the LEARNINGS' own table SHAPE gate must BITE when the
shape defect is put back.

THE DEFECT CLASS
----------------
This lane's LEARNINGS file carries two kinds of claim: the COUNTS in its
tables, and the SHAPE of those tables. The lane ships a gate that recomputes
the counts by AST -- and that gate was green while the table's header declared
FOUR columns over THREE-column rows.

MEASURED 2026-11-05: merging this lane's two LEARNINGS files rebuilt the
"What shipped" table with a four-column header over three-column rows. Every
count in the table was still CORRECT, so all of the measurement gates passed
and the lane did not notice. The defect was caught by a REVIEWER reading the
rendered table -- and it had ALREADY been fixed once in this lane, for exactly
the same reason, by that same review round.

That is what makes it a defect rather than a typo: a fault that survives every
gate AND survives its own fix has no gate. The numbers were measured; the
shape was not. So the shape is measured now, and this harness is what proves
that measurement is load-bearing: it puts the defect back and requires the
NAMED test to die.

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
Each mutation below puts the SHAPE defect back into the LEARNINGS file in a
way a reviewer or a merge script could plausibly introduce. None of them
re-types the gate's own expression: each one changes the DOCUMENT, and the
gate must notice.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_house_ci_defect_closure_learnings_taxonomy_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
the lane's LEARNINGS file in this repo and restores it.
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

LEARNINGS = (
    REPO_ROOT / "pmoves" / "docs" / "AGENTS" / "house_ci_defect_closure_LEARNINGS.md"
)

TAXONOMY_GATE = (
    REPO_ROOT / "pmoves" / "tests" / "tools" / "test_house_ci_defect_closure_learnings_taxonomy.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-house-ci-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    old: str
    new: str
    target_test: str
    rationale: str
    target_file: Path
    test_file: Path


MUTATIONS: list[Mutation] = [
    # ------------------------------------------------------------------
    # house_ci_defect_closure_LEARNINGS.md -- the "What shipped" table
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_four_column_header_put_back_over_three_column_rows",
        old="""| # | Fix | Files |
|---|-----|-------|""",
        new="""| # | Fix | Measured | Files |
|---|-----|----------|-------|""",
        target_test=(
            "test_the_shipped_table_header_and_rows_agree_on_the_column_count"
        ),
        rationale=(
            "This is the EXACT defect that was found: the merge of this lane's "
            "two LEARNINGS files rebuilt the table with a four-column header "
            "over three-column rows. Every count stayed correct, so all of the "
            "measurement gates passed and the lane did not notice -- a reviewer "
            "reading the rendered table did. The same defect had already been "
            "fixed once in this lane for the same reason, which is the part "
            "that says the missing thing was a GATE and not more care."
        ),
        target_file=LEARNINGS,
        test_file=TAXONOMY_GATE,
    ),
    Mutation(
        name="M2_a_row_that_carries_one_cell_too_many",
        old="""| F1 | The approval guard normalises the verdict spelling before comparing, and the raw value still names the failure — 6 behavioural tests + 6 mutation kills | `pmoves/tests/tools/test_app_pr_approve_guard.py`, `pmoves/tests/tools/test_app_pr_approve_guard_mutation_kill.py` |""",
        new="""| F1 | The approval guard normalises the verdict spelling before comparing, and the raw value still names the failure — 6 behavioural tests + 6 mutation kills | `pmoves/tests/tools/test_app_pr_approve_guard.py`, `pmoves/tests/tools/test_app_pr_approve_guard_mutation_kill.py` | extra |""",
        target_test=(
            "test_the_shipped_table_header_and_rows_agree_on_the_column_count"
        ),
        rationale=(
            "The MIRROR of M1: the rows are too wide rather than the header "
            "being too tall. A gate that only checked 'is the header the shape "
            "I remember' would pass this, so the gate compares every row "
            "against the header's declared column count instead."
        ),
        target_file=LEARNINGS,
        test_file=TAXONOMY_GATE,
    ),
    Mutation(
        name="M3_the_separator_row_replaced_by_a_content_row",
        old="""| # | Fix | Files |
|---|-----|-------|""",
        new="""| # | Fix | Files |
| fix | description | files |""",
        target_test=(
            "test_the_shipped_table_header_and_rows_agree_on_the_column_count"
        ),
        rationale=(
            "A table whose separator row is a CONTENT row is not a table -- "
            "markdown renders it as plain text, and the counts inside it read "
            "as prose. The gate checks the separator's SHAPE, not just the "
            "header's, because a document can be malformed in more than one "
            "way and each way needs its own check."
        ),
        target_file=LEARNINGS,
        test_file=TAXONOMY_GATE,
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
    return f"{mutation.test_file.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"


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
    must pass again -- and the source must be byte-identical to the
    original."""
    learn = LEARNINGS.read_text(encoding="utf-8")
    assert "| # | Fix | Files |\n|---|-----|-------|" in learn, (
        "the 'What shipped' table's three-column header is not intact after "
        "the mutation suite"
    )
    assert "| # | Fix | Measured | Files |" not in learn, (
        "the four-column header defect is still in the LEARNINGS file"
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
