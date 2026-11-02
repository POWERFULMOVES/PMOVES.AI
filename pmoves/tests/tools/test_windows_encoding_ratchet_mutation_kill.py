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
  M8  a PEP 695 type-parameter list is reintroduced into the measured tree --
      the file becomes a SyntaxError on the project's declared floor.
  M9  `io` is re-exempted -- `io.open` IS `builtins.open`, so re-exempting it
      re-opens the exact defect class the gate exists to catch.
  M10 `codecs` is re-exempted -- `codecs.open(path)` opens in TEXT mode with
      the LOCALE encoding, so it is the same defect class.
  M11 the mode of `io.open`/`codecs.open` is read from the PATH slot instead
      of the BUILTIN slot -- every binary `io.open(path, "rb")` is then judged
      text and flagged.
  M12 an undecodable file is silently skipped instead of REPORTED -- the gate
      reports success over a population it never measured.
  M13 the measured gap breakdown is dropped -- the tool stops publishing what
      it measured, and the live-tree claim rides on it.
  M14 `codecs.open`'s `encoding` slot is read as the builtin slot -- the tool
      then reports a site that DID pass the encoding positionally as one with
      no encoding at all.
  M15 `io.open`'s `encoding` slot is read as the codecs slot -- three
      positional arguments cannot have carried the encoding, so the report
      mislabels the site.

BYTE-EXACT RESTORE
------------------
The restore is byte-exact: the file's exact bytes are captured before the
mutation and written back afterwards, and the check compares BYTES. A
decoded-text comparison cannot certify bytes -- `read_text` translates CRLF
back to LF, so it certifies byte-exactness through a lens that blurs the very
bytes it certifies. The mutation is written with the file's OWN newline
convention, so a CRLF file stays CRLF for the duration of the mutation.

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
    """One mutation: the rewrite, and the test that MUST die from it.

    ``target_file`` is the file the rewrite is applied to. It defaults to the
    ratchet TOOL. A mutation that lives in the TREE -- a module using syntax
    newer than the project's declared floor -- names its own file, because a
    harness that could only ever rewrite the tool could not prove that the
    tree-level invariant is load-bearing.
    """

    name: str
    old: str
    new: str
    target_test: str
    rationale: str
    target_file: Path | None = None

    @property
    def path(self) -> Path:
        return self.target_file or TOOL


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
    Mutation(
        name="M8_pep_695_type_parameters_reintroduced",
        old="""    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:""",
        new="""    async def call[
        T
    ](
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:""",
        target_test=(
            "test_no_module_in_the_measured_surface_uses_syntax_newer_than_"
            "the_declared_minimum_python"
        ),
        rationale=(
            "PEP 695 type parameter lists are Python 3.12+. The project "
            "declares `requires-python = \">=3.11\"` and the ratchet job runs "
            "on 3.11, so this file becomes a SyntaxError there and the "
            "ratchet cannot PARSE it to measure it. MEASURED 2026-11-01: this "
            "was the one PEP 695 site in 1400 files, and it broke the "
            "windows-encoding-ratchet CI job."
        ),
        target_file=(
            REPO_ROOT / "pmoves" / "services" / "semantic-cache"
            / "chit_invalidation.py"
        ),
    ),
    Mutation(
        name="M9_io_re_exempted",
        old="""    "bz2",
    "dbm",""",
        new="""    "bz2",
    "dbm",
    "io",""",
        target_test="test_io_open_without_encoding_is_flagged",
        rationale=(
            "`io.open` IS `builtins.open` (verified: `io.open is builtins.open` "
            "-> True), so it opens in TEXT mode with the LOCALE encoding -- "
            "the defect class this gate exists to catch. Exempting it again "
            "is a permanent blind spot, not a false-positive fix."
        ),
    ),
    Mutation(
        name="M10_codecs_re_exempted",
        old="""    "dbm",
    "fitz",""",
        new="""    "codecs",
    "dbm",
    "fitz",""",
        target_test="test_codecs_open_without_encoding_is_flagged",
        rationale=(
            "`codecs.open(filename, mode, encoding, ...)` with `encoding=None` "
            "falls through to `builtins.open(filename, mode, buffering)` -- a "
            "TEXT-mode read with the LOCALE encoding. Same defect class, so it "
            "is judged, never exempted."
        ),
    ),
    Mutation(
        name="M11_builtin_signature_mode_slot_reverted",
        old="""                path_open = False
                builtin_signature = True""",
        new="""                path_open = True
                builtin_signature = True""",
        target_test="test_a_binary_io_open_is_not_flagged",
        rationale=(
            "`io.open`/`codecs.open` take the mode in the BUILTIN slot (second "
            "positional), not the Path slot (first). Reading the Path slot "
            "sees the FILENAME, misses the binary mode, and flags every binary "
            "`io.open(path, \"rb\")` in the fleet -- a false positive."
        ),
    ),
    Mutation(
        name="M12_undecodable_file_silently_skipped",
        old="""            errors.append({"file": rel, "error": f"unreadable: {exc}"})""",
        new="""            pass  # MUTATION: the undecodable file is silently skipped""",
        target_test="test_an_unreadable_file_is_reported_not_skipped",
        rationale=(
            "A file that cannot be decoded as UTF-8 must be an instrument "
            "error. Silently skipping it reports success over a population "
            "the gate never measured -- the exact failure the decode path "
            "exists to prevent."
        ),
    ),
    Mutation(
        name="M14_codecs_encoding_slot_reverted",
        old="""    "codecs": 2,""",
        new="""    "codecs": 3,""",
        target_test="test_a_codecs_open_with_a_positional_encoding_is_reported_as_positional",
        rationale=(
            "`codecs.open(filename, mode, encoding, ...)` takes `encoding` "
            "THIRD. Reading the builtin slot (fourth) instead makes the tool "
            "report a site that DID pass the encoding positionally as one "
            "with no encoding at all -- a wrong report about a real site."
        ),
    ),
    Mutation(
        name="M15_io_encoding_slot_reverted",
        old="""    "io": OPEN_ENCODING_POSITIONAL_INDEX,""",
        new="""    "io": 2,""",
        target_test="test_an_io_open_with_three_positional_args_reports_no_encoding",
        rationale=(
            "`io.open` IS `builtins.open`, whose `encoding` is the FOURTH "
            "parameter. Three positional arguments cannot have carried it, so "
            "reading the codecs slot (third) mislabels the site as 'encoding "
            "may be positional'."
        ),
    ),
    Mutation(
        name="M13_gap_breakdown_removed",
        old="""        "gaps_by_call": dict(sorted(gaps_by_call.items())),""",
        new="""        "gaps_by_call": {},""",
        target_test="test_the_live_tree_has_no_io_or_codecs_open_gap",
        rationale=(
            "The breakdown is what the tool PUBLISHES about what it measured. "
            "Dropping it leaves the live-tree claim riding on a number "
            "nothing computes."
        ),
    ),
]


def _read_source(path: Path) -> tuple[bytes, str]:
    """The file's exact bytes, plus its text with newlines normalised to LF.

    The mutation anchors are written with LF and the ratchet tool is CRLF in
    this worktree, so the anchor match runs against the normalised text. The
    BYTES are what the restore must reproduce EXACTLY: a decoded-text
    comparison cannot tell LF from CRLF, because `read_text` translates them
    away -- it certifies byte-exactness through a lens that blurs the very
    bytes it certifies.
    """
    raw = path.read_bytes()
    return raw, raw.decode("utf-8").replace("\r\n", "\n")


def _write_source(path: Path, text: str, newline: str) -> None:
    """Write LF-normalised `text` using the file's OWN newline convention."""
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def _run_pytest(node_id: str, timeout: float = _PYTEST_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    # NOTE: no `--timeout` flag here. That flag belongs to the
    # `pytest-timeout` PLUGIN, which is not installed in every CI
    # environment -- and a flag the plugin does not know makes pytest exit
    # 4 with "unrecognized arguments", which would make the harness report
    # a mutation kill for the WRONG reason (a collection failure, not a
    # red test). The outer `subprocess.run(timeout=...)` is the real guard.
    return subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "-p", "no:warnings"],
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
            f"mutation {mutation.name}: anchor not found in {mutation.path.name}. "
            "The source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original = mutation.path.read_text(encoding="utf-8")
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.path.name} -- the source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED -> GREEN, with a byte-exact restore."""
    node_id = f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"
    target = mutation.path
    original_bytes, original = _read_source(target)
    newline = "\r\n" if b"\r\n" in original_bytes else "\n"

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH):
        # 1. GREEN BEFORE
        before = _run_pytest(node_id)
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        try:
            # The mutation is written with the file's OWN newline convention,
            # so a CRLF file stays CRLF: the mutation changes what it says and
            # nothing else.
            _write_source(target, mutated, newline)

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
            # 3. GREEN AFTER -- byte-exact restore. The file's exact bytes go
            # back, and the check compares BYTES: `read_text` would translate
            # CRLF away and could not tell the difference.
            target.write_bytes(original_bytes)
            restored = target.read_bytes()
            assert restored == original_bytes, (
                f"{mutation.name}: the restore was not byte-exact"
            )

        after_restore = _run_pytest(node_id)
        assert after_restore.returncode == 0, (
            f"{mutation.name}: the restored source does not pass "
            f"{mutation.target_test}\n{after_restore.stdout[-4000:]}"
        )


def test_the_mutation_write_preserves_the_files_line_endings(tmp_path):
    """A CRLF file must still be CRLF after a mutation -- and after a restore.

    The harness used to write with `write_text(..., encoding="utf-8")` and NO
    `newline=""`, so on Windows the LF text it wrote was translated to CRLF on
    disk, and the `read_text` comparison that "certified" the restore
    translated it straight back. The bytes it claimed to certify were never
    compared.
    """
    target = tmp_path / "tool.py"
    target.write_bytes(b"line one\r\nline two\r\n")
    raw, text = _read_source(target)
    assert raw == b"line one\r\nline two\r\n"
    assert text == "line one\nline two\n"

    _write_source(target, text.replace("line one", "line ONE"), "\r\n")
    written = target.read_bytes()
    assert written == b"line ONE\r\nline two\r\n"
    # no lone LF crept in
    assert b"\n" not in written.replace(b"\r\n", b"")


def test_the_restore_reproduces_the_original_bytes(tmp_path):
    """The restore is byte-exact -- including the bytes `read_text` blurs."""
    target = tmp_path / "tool.py"
    original_bytes = b"x = 1\r\ny = 2\r\n"
    target.write_bytes(original_bytes)
    raw, text = _read_source(target)

    _write_source(target, text.replace("x = 1", "x = 9"), "\r\n")
    assert target.read_bytes() != original_bytes

    target.write_bytes(raw)
    assert target.read_bytes() == original_bytes


def test_the_tool_source_is_intact_after_the_mutation_suite():
    """The last mutation must leave the tree exactly as it found it."""
    original = TOOL.read_text(encoding="utf-8")
    assert "mode = node.args[0] if node.args else None" in original
    assert "return recv.id in NON_PATH_OPENERS" in original
    assert 'or payload["problems"]' in original
    assert 'BUILTIN_SIGNATURE_OPENERS = {"codecs", "io"}' in original
    assert '"gaps_by_call": dict(sorted(gaps_by_call.items()))' in original
