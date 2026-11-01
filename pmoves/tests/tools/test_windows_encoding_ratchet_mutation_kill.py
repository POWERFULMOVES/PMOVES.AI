"""Mutation-kill harness: the Windows-encoding fix must BITE when the defect
is put back.

This is the PROVENANCE HARNESS for commit 1 of the carry-over closure lane
(the item the operator named "the 25 pre-existing Windows-only compose-smoke
failures plus the validate_service_tools_packaging.py cp1252 defect").

THE DEFECT
----------
Python's ``open()``/``Path.read_text()`` default to the LOCALE encoding when
``encoding`` is omitted. On the operator's Windows host (cp1252) reading a
UTF-8 file raises ``UnicodeDecodeError``. MEASURED 2026-11-01: 25 tests in
``pmoves/tests/smoke/test_compose_structure.py`` and
``pmoves/tests/smoke/test_port_conflicts.py`` failed that way, and ALL 27
passed with ``PYTHONUTF8=1`` -- proving the failures were decoding, not logic.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

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
rule the production path relies on:

  M1  ``Path.open``'s mode is read from the wrong SLOT -- the builtin slot
      instead of the path slot. A binary ``Path.open("rb")`` is then judged
      text and flagged.
  M2  builtin ``open``'s mode is read from the wrong SLOT -- the path slot
      instead of the builtin slot. A binary ``open(path, "rb")`` is then
      judged text and flagged.
  M3  the NON-PATH carve-out is removed -- ``os.open``/``Image.open`` are then
      judged as text-mode path opens.
  M4  the ``encoding=`` keyword detection is removed -- every file read is
      then flagged.
  M5  the STALE half of the baseline contract is removed -- a fixed file no
      longer turns the gate red, so the baseline can outlive its defect.
  M6  the NEW-GAP half of the baseline contract is removed -- a new gap in an
      unbaselined file no longer turns the gate red.
  M7  the FAIL-CLOSED half of the exit code is removed -- an unparseable file
      stops failing the gate.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_windows_encoding_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh. It mutates files in this
repo and restores them.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL = REPO_ROOT / "pmoves" / "tools" / "windows_encoding_ratchet.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_windows_encoding_ratchet.py"

_PYTEST_TIMEOUT_SECONDS = 300.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-windows-encoding-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    old: str
    new: str
    target_test: str
    rationale: str


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_path_open_mode_slot",
        old="""    if path_open:
        mode = node.args[0] if node.args else None""",
        new="""    if path_open:
        mode = node.args[1] if len(node.args) >= 2 else None""",
        target_test="test_a_binary_path_open_is_not_flagged",
        rationale=(
            "Path.open(mode, ...) takes the mode FIRST. Reading the builtin slot "
            "instead makes a binary Path.open look like a text-mode read and "
            "flags it -- a false positive on every binary handle in the fleet."
        ),
    ),
    Mutation(
        name="M2_builtin_open_mode_slot",
        old="""    else:
        mode = node.args[1] if len(node.args) >= 2 else None""",
        new="""    else:
        mode = node.args[0] if node.args else None""",
        target_test="test_a_binary_builtin_open_is_not_flagged",
        rationale=(
            "builtin open(file, mode, ...) takes the mode SECOND. Reading the "
            "path slot instead sees the FILENAME, misses the binary mode, and "
            "flags every binary read in the fleet."
        ),
    ),
    Mutation(
        name="M3_non_path_carve_out_removed",
        old="""    if isinstance(recv, ast.Name):
        return recv.id in NON_PATH_OPENERS
    return False""",
        new="""    return False""",
        target_test="test_a_non_path_opener_is_not_judged",
        rationale=(
            "os.open / Image.open / wave.open open BINARY handles where an "
            "encoding argument is meaningless. Without the carve-out the "
            "ratchet demands an encoding on them -- a false positive."
        ),
    ),
    Mutation(
        name="M4_encoding_keyword_detection_removed",
        old="""def _has_encoding_keyword(node: ast.Call) -> bool:
    return any(kw.arg == "encoding" for kw in node.keywords)""",
        new="""def _has_encoding_keyword(node: ast.Call) -> bool:
    return False""",
        target_test="test_a_read_text_with_encoding_is_not_flagged",
        rationale=(
            "If the encoding keyword is not recognised, EVERY file read in the "
            "fleet is flagged -- the ratchet stops measuring the defect and "
            "starts measuring noise."
        ),
    ),
    Mutation(
        name="M5_stale_baseline_half_removed",
        old="""        elif count < baseline[name]:
            stale.append(""",
        new="""        elif count < baseline[name] and False:
            stale.append(""",
        target_test="test_a_count_that_fell_is_stale",
        rationale=(
            "Without the stale half, fixing a file leaves its baseline entry "
            "in place -- so the defect can be re-introduced silently and the "
            "baseline outlives what it recorded."
        ),
    ),
    Mutation(
        name="M6_new_gap_half_removed",
        old="""        if name not in baseline:
            new_gaps.append({"file": name, "count": count, "reason": "not in baseline"})""",
        new="""        if name not in baseline:
            pass""",
        target_test="test_a_file_absent_from_the_baseline_is_a_new_gap",
        rationale=(
            "Without the new-gap half, a fresh undecoded read in a file that "
            "is not in the baseline passes the gate -- the ratchet would only "
            "ever police the population it already knows about."
        ),
    ),
    Mutation(
        name="M7_fail_closed_exit_code_removed",
        old="""            or payload["orphan_gaps"]
            or payload["problems"]""",
        new="""            or payload["orphan_gaps"]""",
        target_test="test_the_cli_fails_closed_when_a_file_cannot_be_parsed",
        rationale=(
            "An unparseable file must fail the gate. If instrument errors do "
            "not affect the exit code, a file the ratchet cannot read is "
            "silently skipped and the gate reports success on a population it "
            "never measured."
        ),
    ),
]


def _run_pytest(node_id: str, timeout: float = _PYTEST_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "-p", "no:warnings", "--timeout=120"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def _named_test_failed(proc: subprocess.CompletedProcess, test_name: str) -> bool:
    """True only if pytest's own short summary names THIS test as failed.

    A collection error, a timeout, or an unrelated failure also makes pytest
    exit non-zero; none of those is a kill.
    """
    for line in proc.stdout.splitlines():
        if line.startswith("FAILED ") and test_name in line:
            return True
    for line in proc.stderr.splitlines():
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
            f"mutation {mutation.name}: anchor not found in {TOOL.name}. "
            "The tool's source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    original = TOOL.read_text(encoding="utf-8")
    for mutation in MUTATIONS:
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found -- the tool source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED -> GREEN, with a byte-exact restore."""
    node_id = f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"
    original = TOOL.read_text(encoding="utf-8")

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH):
        # 1. GREEN BEFORE
        before = _run_pytest(node_id)
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        try:
            TOOL.write_text(mutated, encoding="utf-8")

            # 2. RED AFTER -- the NAMED test must die
            after = _run_pytest(node_id)
            assert after.returncode != 0, (
                f"{mutation.name}: the mutation SURVIVED -- "
                f"{mutation.target_test} still passed\n{after.stdout[-4000:]}"
            )
            assert _named_test_failed(after, mutation.target_test), (
                f"{mutation.name}: pytest failed, but NOT the named test "
                f"{mutation.target_test}\n{after.stdout[-4000:]}\n{after.stderr[-2000:]}"
            )
        finally:
            # 3. GREEN AFTER -- byte-exact restore
            TOOL.write_text(original, encoding="utf-8")
            restored = TOOL.read_text(encoding="utf-8")
            assert restored == original, f"{mutation.name}: the restore was not byte-exact"

        after_restore = _run_pytest(node_id)
        assert after_restore.returncode == 0, (
            f"{mutation.name}: the restored source does not pass "
            f"{mutation.target_test}\n{after_restore.stdout[-4000:]}"
        )


def test_the_tool_source_is_intact_after_the_mutation_suite():
    """The last mutation must leave the tree exactly as it found it."""
    original = TOOL.read_text(encoding="utf-8")
    assert "mode = node.args[0] if node.args else None" in original
    assert "return recv.id in NON_PATH_OPENERS" in original
    assert 'or payload["problems"]' in original
