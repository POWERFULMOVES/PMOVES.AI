"""Mutation-kill harness: the mmx surface parity gate must BITE when the
rules it enforces are put back.

THE DEFECT
----------
``pmoves/docs/services/MMX_CLI_SURFACE.md`` described an ``mmx`` command
surface that the installed binary does not have. It promised ``mmx music
generate``, ``mmx speech list-voices``, ``mmx speech clone``, ``mmx config
get`` and ``mmx search news``; it omitted ``mmx agent setup``, ``mmx text
repl``, ``mmx config show``, ``mmx config export-schema``, ``mmx video task
get`` and ``mmx video download``; and it stated npm version ``v1.0.19``
against an installed ``1.0.25``.

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
The kill signal is NOT "pytest exited non-zero" -- a signal that a collection
error, a timeout or an unrelated environment failure also satisfies. The
harness reads pytest's own short test summary and requires the NAMED test to
be IN it. A harness may only claim a kill it can point at.

THE MUTATIONS
--------------
Each mutation removes or inverts ONE rule the gate depends on. The gate is
not allowed to become a gate that cannot fail.

  M1   the DOCUMENTED_MISSING command rule is removed
  M2   the DOCUMENTED_MISSING resource rule is removed
  M3   the UNDOCUMENTED rule is removed
  M4   the VERSION_DRIFT rule is removed
  M5   the PARSE_ERROR finding is swallowed
  M6   the INSTRUMENT_ERROR finding (missing snapshot) is swallowed
  M7   the snapshot ENTRY validation is removed
  M8   the global-flag comparison is removed
  M9   the exit code stops reflecting the findings
  M10  the command tree is no longer scraped
  M11  the command table is no longer scraped
  M12  ANSI colour codes are no longer stripped
  M13  the command rows are no longer validated, so the model legend leaks in
  M14  the probe stops failing closed on a missing binary

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_mmx_surface_parity_mutation_kill.py -v

Hermetic: no network, no API key, no model call. It mutates files in this
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
PARITY_TOOL = REPO_ROOT / "pmoves" / "tools" / "mmx_surface_parity.py"
PROBE_TOOL = REPO_ROOT / "pmoves" / "tools" / "mmx_surface_probe.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_mmx_surface_parity.py"

_PYTEST_TIMEOUT_SECONDS = 300.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-mmx-surface-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

    name: str
    target: Path
    old: str
    new: str
    target_test: str
    rationale: str


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1_documented_missing_command_rule_removed",
        target=PARITY_TOOL,
        old="""        for command in sorted(doc_resources[name] - set(snap_resources.get(name, []))):""",
        new="""        for command in sorted(set()):""",
        target_test="test_a_documented_command_the_cli_lacks_is_reported",
        rationale=(
            "Without the command half of the DOCUMENTED_MISSING rule, a doc "
            "that promises `mmx speech clone` passes the gate -- which is the "
            "drift this lane exists to end."
        ),
    ),
    Mutation(
        name="M2_documented_missing_resource_rule_removed",
        target=PARITY_TOOL,
        old="""        if name not in snap_resources:""",
        new="""        if False:""",
        target_test="test_a_documented_resource_the_cli_lacks_is_reported",
        rationale=(
            "Without the resource half, a doc that documents a whole resource "
            "the CLI never had (`music`) is no longer reported at the "
            "granularity it actually drifted at."
        ),
    ),
    Mutation(
        name="M3_undocumented_rule_removed",
        target=PARITY_TOOL,
        old="""        if name not in doc_resources:""",
        new="""        if False:""",
        target_test="test_a_snapshot_command_the_doc_never_mentions_is_reported",
        rationale=(
            "Without the UNDOCUMENTED rule the gate only ever polices what "
            "the doc says, never what the CLI gained -- so the next command "
            "the upstream adds would go undocumented without a word."
        ),
    ),
    Mutation(
        name="M4_version_drift_rule_removed",
        target=PARITY_TOOL,
        old="""    if doc_surface["mmx_version"] is not None and doc_surface["mmx_version"] != snap_version:""",
        new="""    if False:""",
        target_test="test_a_version_mismatch_is_reported",
        rationale=(
            "The version string is the claim most likely to rot: the doc said "
            "v1.0.19 while the binary was 1.0.25. Dropping the rule lets that "
            "happen again silently."
        ),
    ),
    Mutation(
        name="M5_parse_error_swallowed",
        target=PARITY_TOOL,
        old="""        except DocParseError as exc:
            findings.append(
                _finding("PARSE_ERROR", f"the doc could not be parsed: {exc}", scope="doc")
            )""",
        new="""        except DocParseError:
            pass""",
        target_test="test_a_doc_without_the_machine_readable_block_is_a_parse_error",
        rationale=(
            "An unparseable doc must fail closed. If the parse error stops "
            "producing a finding, a doc whose machine-readable block was "
            "deleted reads as merely 'nothing to compare'."
        ),
    ),
    Mutation(
        name="M6_instrument_error_swallowed",
        target=PARITY_TOOL,
        old="""    except SnapshotError as exc:
        findings.append(
            _finding("INSTRUMENT_ERROR", f"the snapshot could not be read: {exc}", scope="snapshot")
        )""",
        new="""    except SnapshotError:
        pass""",
        target_test="test_a_missing_snapshot_file_is_an_instrument_error",
        rationale=(
            "A gate that cannot read its instrument must not report success. "
            "A missing snapshot is the classic case: without the finding, the "
            "gate reports a clean doc it never measured."
        ),
    ),
    Mutation(
        name="M7_snapshot_entry_validation_removed",
        target=PARITY_TOOL,
        old="""        if not isinstance(commands, list) or any(
            not isinstance(command, str) or not command for command in commands
        ):
            raise SnapshotError(
                f"the snapshot file {path} has a malformed command list for resource {name!r}"
            )""",
        new="""        if False:
            raise SnapshotError(
                f"the snapshot file {path} has a malformed command list for resource {name!r}"
            )""",
        target_test="test_a_malformed_snapshot_entry_is_an_instrument_error",
        rationale=(
            "Entry granularity: a snapshot whose command list is not a list of "
            "names is a broken instrument. Validating only the file lets a "
            "corrupt entry through, and the gate then compares the doc "
            "against nonsense."
        ),
    ),
    Mutation(
        name="M8_global_flag_comparison_removed",
        target=PARITY_TOOL,
        old="""    for flag in sorted(snap_flags - doc_surface["global_flags"]):""",
        new="""    for flag in sorted(set()):""",
        target_test="test_a_global_flag_the_doc_omits_is_reported",
        rationale=(
            "The global flags are part of the surface. Without the comparison, "
            "a flag the CLI grows is never documented."
        ),
    ),
    Mutation(
        name="M9_exit_code_ignores_findings",
        target=PARITY_TOOL,
        old="""    return 0 if report["ok"] else 1""",
        new="""    return 0""",
        target_test="test_the_cli_exits_non_zero_when_findings_exist",
        rationale=(
            "The report can be perfect and the gate still useless if the exit "
            "code says zero. CI reads the exit code."
        ),
    ),
    Mutation(
        name="M10_command_tree_no_longer_scraped",
        target=PARITY_TOOL,
        old="""    for name, commands in extract_tree_surface(doc_text).items():""",
        new="""    for name, commands in {}.items():""",
        target_test="test_a_stale_command_tree_is_reported",
        rationale=(
            "The ASCII tree is the part of the doc a human reads first. If it "
            "is no longer scraped, a tree that rots away from the JSON block "
            "is invisible."
        ),
    ),
    Mutation(
        name="M11_command_table_no_longer_scraped",
        target=PARITY_TOOL,
        old="""    for name, commands in extract_table_claims(doc_text, known).items():""",
        new="""    for name, commands in {}.items():""",
        target_test="test_a_stale_command_table_is_reported",
        rationale=(
            "The command table is the part a sidecar author copies from. If "
            "it is no longer scraped, a stale example row is invisible."
        ),
    ),
    Mutation(
        name="M12_ansi_stripping_removed",
        target=PROBE_TOOL,
        old="""    return ANSI_RE.sub("", text)""",
        new="""    return text""",
        target_test="test_ansi_colour_codes_are_stripped",
        rationale=(
            "The CLI colourises its help when it believes it has a terminal. "
            "Without stripping, the colour codes end up inside resource names "
            "and the snapshot stops matching anything."
        ),
    ),
    Mutation(
        name="M13_command_rows_no_longer_validated",
        target=PROBE_TOOL,
        old="""        if not head or head[0] != resource:
            # Not a command row for this resource (e.g. the video model legend).
            continue
        words = _leading_command_words(head[1:])
        if words:
            commands.append(" ".join(words))""",
        new="""        commands.append(" ".join(head[1:]))""",
        target_test="test_the_video_model_legend_is_not_parsed_as_commands",
        rationale=(
            "The video resource's help carries a model legend (V2:, T2V:, "
            "I2V:, SEF:, S2V:) among its command rows. Without validating a "
            "row against the resource and taking only its leading command "
            "words, the legend leaks into the command list."
        ),
    ),
    Mutation(
        name="M14_probe_stops_failing_closed_on_a_missing_binary",
        target=PROBE_TOOL,
        old="""        raise ProbeError(
            f"--mmx-bin {explicit!r} is neither an existing file nor a command on PATH"
        )""",
        new="""        return explicit""",
        target_test="test_the_probe_fails_closed_when_the_binary_is_missing",
        rationale=(
            "A probe that cannot find the CLI must abort, not emit an empty "
            "snapshot. An empty snapshot is a lie the parity gate would "
            "happily compare against."
        ),
    ),
]


def _run_pytest(node_id: str, timeout: float = _PYTEST_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    # NOTE: no `--timeout` flag here. That flag belongs to the
    # `pytest-timeout` PLUGIN, which is not installed in every CI
    # environment -- and a flag the plugin does not know makes pytest exit
    # 4 with "unrecognized arguments", which would make the harness report
    # a mutation kill for the WRONG reason (a collection failure, not a
    # red test). The outer `subprocess.run(timeout=...)` is the real guard:
    # a hung inner pytest raises TimeoutExpired and the harness FAILS,
    # which is the behaviour we want.
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
            f"mutation {mutation.name}: anchor not found in {mutation.target.name}. "
            "The tool's source changed -- update the mutation.\n"
            f"--- expected ---\n{mutation.old}"
        )
    mutated = original.replace(mutation.old, mutation.new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def test_every_mutation_anchor_is_present():
    """A drifted anchor must be loud, not silently inert."""
    for mutation in MUTATIONS:
        original = mutation.target.read_text(encoding="utf-8")
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in {mutation.target.name} "
            "-- the tool source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name
        assert mutation.target_test in TEST_FILE.read_text(encoding="utf-8"), (
            f"mutation {mutation.name}: the named test {mutation.target_test} "
            "does not exist in the parity test file"
        )


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED -> GREEN, with a byte-exact restore."""
    node_id = f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"
    original = mutation.target.read_text(encoding="utf-8")

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH):
        # 1. GREEN BEFORE
        before = _run_pytest(node_id)
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        try:
            mutation.target.write_text(mutated, encoding="utf-8", newline="")

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
            mutation.target.write_text(original, encoding="utf-8", newline="")
            restored = mutation.target.read_text(encoding="utf-8")
            assert restored == original, f"{mutation.name}: the restore was not byte-exact"

        after_restore = _run_pytest(node_id)
        assert after_restore.returncode == 0, (
            f"{mutation.name}: the restored source does not pass "
            f"{mutation.target_test}\n{after_restore.stdout[-4000:]}"
        )


def test_the_tool_sources_are_intact_after_the_mutation_suite():
    """The last mutation must leave the tree exactly as it found it."""
    parity_source = PARITY_TOOL.read_text(encoding="utf-8")
    probe_source = PROBE_TOOL.read_text(encoding="utf-8")
    assert 'return 0 if report["ok"] else 1' in parity_source
    assert "for command in sorted(doc_resources[name]" in parity_source
    assert 'return ANSI_RE.sub("", text)' in probe_source
    assert "_leading_command_words(head[1:])" in probe_source
