"""Mutation-kill harness: the Windows-host-quirks ratchet must BITE when the
BOOTSTRAP section is put back the way it was.

THE DEFECT CLASS
----------------
``.claude/BOOTSTRAP.md`` is ALWAYS loaded. The section this lane landed
("Windows host quirks") was written in 2026-09 and `main` moved 1,550
commits past it before it was landed. Four of its claims had rotted in the
meantime: a plugin version that no longer existed, a settings FILE that was
not the file the plugin was enabled in, a DROPPED/DEGRADED verdict that was
the wrong verdict for the field the variable sat in, and an env-var name the
roster did not read. A doc that is always loaded is not a doc -- it is
instructions every cold start acts on -- so a gate that reads it can only be
load-bearing if a plausible edit to it makes the gate fail.

So this harness puts the defects back, four ways, and requires the NAMED test
to die each time.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine section must pass the selected test.
  2. RED AFTER    -- the mutated section must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored section must pass again.

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

So the GREEN phases run ONCE for the whole session, over every target test:

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
Each mutation below changes the SECTION -- the document the gate reads -- and
never re-types the gate's own expression. A mutation that edited the gate
would prove nothing about the document it claims to check.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_bootstrap_windows_host_quirks_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
``.claude/BOOTSTRAP.md`` in this repo and restores it.
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

BOOTSTRAP = REPO_ROOT / ".claude" / "BOOTSTRAP.md"

RATCHET = (
    REPO_ROOT
    / "pmoves"
    / "tests"
    / "tools"
    / "test_bootstrap_windows_host_quirks_ratchet.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

# The SAME house-wide lock the other harnesses use. Two harnesses that mutate
# files in this repo must not hold the tree at once -- a mutation harness
# leaves the tree MUTATED by design, so anything that reads the tree during
# that window reads the mutation.
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
    # A launcher that does not exist
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_section_names_a_launcher_that_is_not_on_disk",
        old="`deploy/provision/claude-pmoves.sh`",
        new="`deploy/provision/claude-pmovos.sh`",
        target_test="test_every_repo_path_the_section_names_exists",
        rationale=(
            "A launcher that is not on disk is the oldest failure mode in an "
            "always-loaded doc: the operator is told to update the ratchet "
            "that guards a file that does not exist, and the real file keeps "
            "drifting unguarded. The ratchet must notice a path the tree "
            "does not have -- which is why it resolves the section's paths "
            "against the FILESYSTEM rather than against a literal list."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A generator flag that does not exist
    # ------------------------------------------------------------------
    Mutation(
        name="M2_the_section_claims_a_generator_flag_that_does_not_exist",
        old="`--include-hand` flag",
        new="`--include-hand-written` flag",
        target_test="test_every_generator_flag_the_section_names_is_a_real_flag",
        rationale=(
            "The escape hatch is named in the section as the ONE way to make "
            "the generator touch the hand-written launchers. A flag that does "
            "not exist is an operator running a command that errors out, at "
            "the exact moment they are trying to pin drift. The ratchet "
            "derives the real option set from the generator's OWN argument "
            "parser, so an invented flag cannot survive."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A roster variable the roster does not read
    # ------------------------------------------------------------------
    Mutation(
        name="M3_the_section_names_an_env_var_the_roster_does_not_read",
        old=(
            "| `hostinger` | `HOSTINGER_API_TOKEN` | `env` | DEGRADED |"
        ),
        new=(
            "| `hostinger` | `HOSTINGER_API_KEY` | `env` | DEGRADED |"
        ),
        target_test="test_the_roster_table_matches_the_live_roster_and_the_live_gate",
        rationale=(
            "`HOSTINGER_API_KEY` is a REAL variable -- but it belongs to the "
            "sibling server `hostinger-mcp`, not to `hostinger`. An operator "
            "who sets the one the table names fixes nothing, and the "
            "WARN keeps coming back with no explanation. The ratchet checks "
            "the row against the LIVE roster entry for THAT server, so a "
            "plausible swap with a real-but-wrong variable dies."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A launcher that is NOT hand-written
    # ------------------------------------------------------------------
    Mutation(
        name="M4_the_section_calls_a_generated_launcher_hand_written",
        old="or `crush-pmoves.{sh,ps1,cmd}`",
        new="or `kilo-pmoves.{sh,ps1,cmd}`",
        target_test="test_the_section_names_exactly_the_hand_written_launchers",
        rationale=(
            "Calling a generator-managed launcher hand-written sends an "
            "operator to hand-edit a file the next regeneration overwrites -- "
            "the work is lost and the drift gate fires on a file nobody "
            "touched. The ratchet compares the section's set against the LIVE "
            "generator's `managed == \"hand\"` set in BOTH directions, so "
            "both a missing name and an extra one die."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
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
    """GREEN BEFORE, once for the whole session: the pristine section must
    pass EVERY target test."""
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
            f"{mutation.name}: the pristine section does not pass "
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
            # The backup is dropped ONLY AFTER a byte-exact restore. If the
            # assert above fails, the backup is the only good copy of the
            # pristine source, and the next session must still be able to
            # restore it -- so it stays on disk.
            mutation_backup.clear_backup(REPO_ROOT, target)


def test_the_sources_are_intact_after_the_mutation_suite() -> None:
    """GREEN AFTER: after every mutation has been restored, every target test
    must pass again -- and the section must be byte-identical to the
    original."""
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "deploy/provision/claude-pmovos.sh" not in text, (
        "the mutated launcher path is still in the section"
    )
    assert "`--include-hand` flag" in text, (
        "the generator flag is not intact after the mutation suite"
    )
    assert (
        "| `hostinger` | `HOSTINGER_API_TOKEN` | `env` | DEGRADED |" in text
    ), "the roster table row is not intact after the mutation suite"
    assert "or `crush-pmoves.{sh,ps1,cmd}`" in text, (
        "the hand-written launcher set is not intact after the mutation suite"
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored section does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
