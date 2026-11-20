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

So this harness puts the defects back, ten ways, and requires the NAMED test
to die each time.

THE CROSS-LANE CLASS
--------------------
Two of those ten are not a defect in this section at all -- they are the
REVERT of a correction another lane forced. The nats-note lane moved the
`_NATS_CREDS_NOTE` prose out of `pmoves-nats-fleet`'s `env` block -- the
field the roster gate expands -- so the malformed `${...}` that prose quoted
stopped being a finding on every launch. That change invalidated a row THIS
section published, and the row had to go.

The lesson is that a lane's fix can invalidate an ALREADY-MERGED lane's
published table, and the gate that catches it is the ratchet of the merged
lane -- not the ratchet of the lane that changed the roster. M9 and M10 keep
that correction load-bearing: M9 pins the footnote's row count to the table's
real row count, and M10 puts the removed row back and requires the roster
test to die.

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
short test summary and requires the NAMED test to be in it, as a ``FAILED``
line whose node id ENDS at that test's name. A harness may only claim a kill
it can point at.

WHY THE NODE-ID FORM, AND NOT JUST THE NAME
--------------------------------------------
A pytest COLLECTION ERROR prints ``ERROR <node id>``, and that line names
the target test just as loudly as a failure does: when a future refactor
renames an in-module helper the ratchet subprocess imports, the summary
carries ``ERROR .../test_bootstrap_windows_host_quirks_ratchet.py::
test_the_roster_table_matches_the_live_roster_and_the_live_gate``. A gate
that failed to collect ANY test is not a gate that bit.

The predicate therefore requires all three of:
  * the line starts with ``FAILED `` -- pytest's own prefix for a failed
    test, and NOT the ``ERROR `` prefix a collection error carries;
  * the line carries the node-id form ``::<test name>`` -- so the name is
    the test's own name and not a word that happens to appear in another
    test's name or in a failure message;
  * the node id ENDS at that name -- ``test_x_extra`` is a DIFFERENT test
    from ``test_x``.

``test_a_collection_error_naming_the_target_is_not_a_kill`` pins all three,
and the copy-based kill below proves the predicate is load-bearing.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below changes the SECTION -- the document the gate reads -- and
never re-types the gate's own expression. A mutation that edited the gate
would prove nothing about the document it claims to check.

TWO KILLS MUTATE A COPY OF THE GATE INSTEAD
--------------------------------------------
Two of the defects this harness covers live in the GATE, not in the
document: the kill predicate above, and the brace-set extractor in the
ratchet. A section mutation cannot prove either of them, so those two kills
apply their mutation to a COPY of the gate file, run the COPY's OWN test
function against the mutated copy, and require the copy's test to fail with
the specific expected message. The tracked original is never written to, and
its bytes are asserted afterwards.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_bootstrap_windows_host_quirks_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
``.claude/BOOTSTRAP.md`` in this repo and restores it.
"""

from __future__ import annotations

import contextlib
import os
import re
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

CLAUDE_DOC = REPO_ROOT / ".claude" / "CLAUDE.md"

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
    replace_all: bool = False


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
    # ------------------------------------------------------------------
    # The gate described as fail-closed when it is fail-OPEN
    # ------------------------------------------------------------------
    Mutation(
        name="M5_the_section_calls_a_degraded_header_dropped",
        old=(
            "| normalizer RAN | the server is KEPT and DEGRADED, and the "
            "literal `${...}` is left in the header | YES |"
        ),
        new=(
            "| normalizer RAN | the server is DROPPED, and the literal "
            "`${...}` is left in the header | YES |"
        ),
        target_test="test_the_fail_closed_claim_matches_the_live_gate",
        rationale=(
            "The retracted claim was that the gate stops a literal `${...}` "
            "from leaking into an MCP header. It does not: with the "
            "normalizer running and the credential unset, the live "
            "normalizer KEEPS the server, records it DEGRADED, and leaves "
            "the literal in the header -- so the placeholder reaches the "
            "wire and the session starts. The ratchet derives the verdict "
            "by CALLING the normalizer, so a section that says DROPPED dies."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A roster server the section stopped covering
    # ------------------------------------------------------------------
    Mutation(
        name="M6_the_section_drops_a_roster_server_from_the_footnote",
        old=(
            "(`cloudflare`, `tailscale`, `huggingface`, `pmoves-cipher-local`, "
            "`pmoves-minimax-mcp`, `composio-local`, `hostinger-mcp`)"
        ),
        new=(
            "(`cloudflare`, `huggingface`, `pmoves-cipher-local`, "
            "`pmoves-minimax-mcp`, `composio-local`, `hostinger-mcp`)"
        ),
        target_test=(
            "test_every_required_roster_var_of_every_roster_server_is_covered"
        ),
        rationale=(
            "`tailscale` requires TAILSCALE_API_KEY and TAILSCALE_TAILNET in "
            "the live roster. The old gate only swept the servers the TABLE "
            "names, so this server -- named in the footnote, outside the "
            "table -- sat outside the gate entirely, and a bare reference "
            "added to its entry would land in the same blind spot. The "
            "ratchet now sweeps the FULL roster: every server that yields "
            "findings must be in the table or in the footnote."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A citation whose rule is not in the file it cites
    # ------------------------------------------------------------------
    Mutation(
        name="M7_the_section_cites_a_remedy_the_cited_file_does_not_have",
        old=(
            "`make -C pmoves fleet-status` is the hostname-only way to read "
            "the fleet"
        ),
        new=(
            "`make -C pmoves fleet-listing` is the hostname-only way to read "
            "the fleet"
        ),
        target_test=(
            "test_every_rule_the_section_cites_is_still_in_the_file_it_cites"
        ),
        rationale=(
            "Fix path 1 sends the operator to "
            "`.claude/hooks/damage-control/patterns.yaml` for the rule that "
            "blocks Tailscale IPs, and to `make -C pmoves fleet-status` as "
            "the hostname-only way to read the fleet. Proving the FILE "
            "exists is not enough: rename the file, or delete the rule "
            "inside it, and the always-loaded doc keeps sending operators to "
            "a justification the tree no longer has. The ratchet "
            "content-checks the citation."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A size budget the always-loaded file does not meet
    # ------------------------------------------------------------------
    Mutation(
        name="M8_the_documented_size_budget_is_below_the_file",
        old="≤18k chars",
        new="≤8k chars",
        target_test="test_the_bootstrap_stays_within_its_documented_budget",
        rationale=(
            "`.claude/CLAUDE.md` publishes the character budget for the "
            "always-loaded `.claude/BOOTSTRAP.md`, and the ratchet reads "
            "that budget FROM that doc so the published number and the gate "
            "cannot drift apart. A budget the file does not meet must fail "
            "the gate, not be ignored -- otherwise the number is fiction "
            "again, which is exactly what it was before this lane."
        ),
        target_file=CLAUDE_DOC,
        test_file=RATCHET,
        replace_all=True,
    ),
    # ------------------------------------------------------------------
    # A footnote whose row count no longer matches the table
    # ------------------------------------------------------------------
    Mutation(
        name="M9_the_footnote_row_count_drifts_from_the_table",
        old="than these 8 rows",
        new="than these 9 rows",
        target_test="test_the_footnote_states_how_many_rows_it_is_a_superset_of",
        rationale=(
            "The footnote claims the table is a superset of N rows. That is a "
            "claim ABOUT the table, in an always-loaded doc, and the count has "
            "to move whenever a row moves. The nats-note lane REMOVED a row "
            "(`pmoves-nats-fleet` / `NATS_CREDS`, no longer a finding once the "
            "note moved out of `env`), so the count went from 9 to 8 -- and a "
            "count left at 9 would claim a row the table no longer has, which "
            "is the same class of lie the section was landed to remove. The "
            "count is parsed out of the footnote and compared with the table's "
            "real row count."
        ),
        target_file=BOOTSTRAP,
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # A finding the live gate no longer produces, published again
    # ------------------------------------------------------------------
    Mutation(
        name="M10_the_section_publishes_a_finding_the_gate_no_longer_produces",
        old="| `pmoves-nats-fleet` | `NATS_URL` | `env` | DEGRADED |",
        new=(
            "| `pmoves-nats-fleet` | `NATS_URL` | `env` | DEGRADED |\n"
            "| `pmoves-nats-fleet` | `NATS_CREDS` | `env` | DEGRADED |"
        ),
        target_test="test_the_roster_table_matches_the_live_roster_and_the_live_gate",
        rationale=(
            "This is the REVERT of the cross-lane reconciliation: the row the "
            "nats-note lane invalidated, put back. MEASURED against the LIVE "
            "normalizer, `NATS_CREDS` is now CLEAN -- its binding is the "
            "DEFAULTED `${NATS_CREDS:-}`, and the `_NATS_CREDS_NOTE` prose "
            "that used to make it a finding now lives at server level, OUTSIDE "
            "the fields the gate expands. Re-publishing the row tells the "
            "operator to set a variable that fixes nothing, and the WARN "
            "never comes back -- the exact failure the roster table exists to "
            "prevent. The ratchet derives the verdict by CALLING the "
            "normalizer, so a row the gate no longer produces dies."
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
    """True only if pytest's own short summary names THIS test as FAILED.

    A collection error, a timeout, or an unrelated failure also makes pytest
    exit non-zero; none of those is a kill.

    The line must carry the node-id form and END at the test's name:

      * ``FAILED `` -- pytest's prefix for a failed test. A collection error
        prints ``ERROR <node id>`` and names the target test just as
        loudly, and a gate that collected nothing did not bite;
      * ``::<test name>`` -- so the name is the test's own name in the
        summary, not a word that happens to appear in another test's name
        or in a failure message;
      * nothing name-like after it -- ``test_x_extra`` is a DIFFERENT test
        from ``test_x``.
    """
    pattern = re.compile(
        r"^FAILED\s+.*?::" + re.escape(test_name) + r"(?![0-9A-Za-z_])"
    )
    for stream in (proc.stdout, proc.stderr):
        for line in stream.splitlines():
            if pattern.search(line):
                return True
    return False


def _fake_proc(text: str) -> subprocess.CompletedProcess:
    """A CompletedProcess carrying pytest-shaped output, for the predicate."""
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=1, stdout=text, stderr=""
    )


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
    if mutation.replace_all:
        mutated = original.replace(mutation.old, mutation.new)
    else:
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


# ---------------------------------------------------------------------------
# The kill signal itself
# ---------------------------------------------------------------------------
#: A pytest COLLECTION ERROR that names the target test. This is the shape a
#: future refactor produces when it renames an in-module helper the ratchet
#: subprocess imports: the summary carries the node id, and the harness would
#: read the name out of it.
_COLLECTION_ERROR_LINE = (
    "ERROR pmoves/tests/tools/test_bootstrap_windows_host_quirks_ratchet.py"
    "::test_the_roster_table_matches_the_live_roster_and_the_live_gate "
    "- ImportError: cannot import name '_live_verdict'"
)


def test_a_collection_error_naming_the_target_is_not_a_kill() -> None:
    """A collection ERROR naming the target test is NOT a kill.

    Codex review finding 4630983480. pytest exits non-zero on a collection
    error and prints the target test's node id in its summary, so a harness
    that only asks "does the name appear?" records a kill that proves
    nothing: a gate that collected NO test did not bite.

    The kill signal has to be the `FAILED` prefix AND the node-id form AND
    the node id must END at the test's name.
    """
    target = "test_the_roster_table_matches_the_live_roster_and_the_live_gate"

    error = _fake_proc(
        "=========================== short test summary info ============================\n"
        + _COLLECTION_ERROR_LINE
        + "\n"
    )
    assert not _named_test_failed(error, target), (
        "a collection ERROR naming the target test was counted as a kill -- "
        "a gate that collected nothing did not bite"
    )

    failed = _fake_proc(
        "=========================== short test summary info ============================\n"
        "FAILED pmoves/tests/tools/test_bootstrap_windows_host_quirks_ratchet.py"
        "::"
        + target
        + " - AssertionError: the section says one thing\n"
    )
    assert _named_test_failed(failed, target), (
        "a real FAILED line for the target test was not counted as a kill"
    )

    longer = _fake_proc(
        "FAILED pmoves/tests/tools/other.py::" + target + "_extra - AssertionError\n"
    )
    assert not _named_test_failed(longer, target), (
        "a FAILED line for a DIFFERENT test whose name merely CONTAINS the "
        "target's name was counted as a kill"
    )


# ---------------------------------------------------------------------------
# Copy-based kills: the defects that live in the GATE, not in the document
# ---------------------------------------------------------------------------
def _copy_of(source: Path, tag: str) -> Path:
    """A byte-identical copy of *source*, beside itself.

    Beside itself because the copy's own ``Path(__file__).resolve().parents[3]``
    must still resolve to the repository root, and because pytest can run
    the copy exactly as it runs the original.

    The name starts with an UNDERSCORE on purpose. ``python_files`` is
    ``test_*.py``, so a ``test_``-named copy would be picked up by the NEXT
    session's directory scan -- and it carries a MUTATION, so it would fail
    tests that have nothing to do with it. A leading underscore is invisible
    to a directory scan and still collectable when the path is passed
    explicitly, which is exactly how it is run here.
    """
    return source.with_name(f"_mutant_{source.stem}__{tag}.py")


def _run_copy_test(copy: Path, test_name: str) -> subprocess.CompletedProcess:
    """Run ONE test function out of a copy of a gate file."""
    node_id = f"{copy.relative_to(REPO_ROOT).as_posix()}::{test_name}"
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            node_id,
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
        timeout=_PYTEST_TIMEOUT_SECONDS,
        cwd=str(REPO_ROOT),
    )


def test_the_kill_signal_rejects_a_collection_error() -> None:
    """The kill predicate must be load-bearing, and this is the proof.

    The mutation is applied to a COPY of this file: the predicate is
    weakened to the loose form -- "any summary line that contains the test
    name" -- which is the form that counts a collection ERROR as a kill. The
    COPY's own ``test_a_collection_error_naming_the_target_is_not_a_kill``
    must then FAIL, with the specific message. The tracked original is
    never written to, and its bytes are asserted afterwards.
    """
    source = Path(__file__).resolve()
    original_bytes = source.read_bytes()
    copy = _copy_of(source, "predicate")
    strict = "            if pattern.search(line):\n"
    loose = "            if test_name in line:\n"
    try:
        text = original_bytes.decode("utf-8")
        assert strict in text, (
            "the kill predicate is not in the shape this kill mutates -- "
            "update the mutation"
        )
        copy.write_bytes(text.replace(strict, loose, 1).encode("utf-8"))
        try:
            proc = _run_copy_test(
                copy, "test_a_collection_error_naming_the_target_is_not_a_kill"
            )
            assert proc.returncode != 0, (
                "the weakened kill predicate did NOT die -- the copy's own "
                "test passed against a predicate that counts a collection "
                "ERROR as a kill\n" + proc.stdout[-4000:]
            )
            assert (
                "a collection ERROR naming the target test was counted as a kill"
                in proc.stdout
            ), (
                "the weakened predicate died, but not with the expected "
                "message\n" + proc.stdout[-4000:]
            )
        finally:
            copy.unlink(missing_ok=True)
    finally:
        assert source.read_bytes() == original_bytes, (
            "the tracked harness file was not restored byte-exactly"
        )


def test_the_brace_extraction_tolerates_both_spellings() -> None:
    """The ratchet's brace-set extractor must be load-bearing, and this is
    the proof.

    The mutation is applied to a COPY of the ratchet: the brace-set pattern
    is tightened back to the single spelling ``{sh,ps1,cmd}``, so the
    equally valid ``{sh, ps1, cmd}`` extracts NOTHING. The COPY's own
    ``test_the_launcher_extraction_tolerates_both_brace_spellings`` must
    then FAIL, with the specific message. The tracked original is never
    written to, and its bytes are asserted afterwards.
    """
    source = RATCHET
    original_bytes = source.read_bytes()
    copy = _copy_of(source, "brace")
    tolerant = (
        r'_LAUNCHER_SET = re.compile(r"([A-Za-z0-9\-]+)\.\{[ \t]*sh[ \t]*,'
        r'[ \t]*ps1[ \t]*,[ \t]*cmd[ \t]*\}")'
    )
    intolerant = (
        r'_LAUNCHER_SET = re.compile(r"([A-Za-z0-9\-]+)\.\{sh,ps1,cmd\}")'
    )
    try:
        text = original_bytes.decode("utf-8")
        assert tolerant in text, (
            "the brace-set extractor is not in the shape this kill mutates -- "
            "update the mutation"
        )
        copy.write_bytes(text.replace(tolerant, intolerant, 1).encode("utf-8"))
        try:
            proc = _run_copy_test(
                copy, "test_the_launcher_extraction_tolerates_both_brace_spellings"
            )
            assert proc.returncode != 0, (
                "the tightened brace extractor did NOT die -- the copy's own "
                "test passed against an extractor that reads only one "
                "spelling\n" + proc.stdout[-4000:]
            )
            assert (
                "the spacey brace spelling extracts differently from the tight one"
                in proc.stdout
            ), (
                "the tightened extractor died, but not with the expected "
                "message\n" + proc.stdout[-4000:]
            )
        finally:
            copy.unlink(missing_ok=True)
    finally:
        assert source.read_bytes() == original_bytes, (
            "the tracked ratchet file was not restored byte-exactly"
        )


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
    must pass again -- and every mutated source must be byte-identical to the
    original."""
    for mutation in MUTATIONS:
        text = mutation.target_file.read_text(encoding="utf-8")
        assert mutation.old in text, (
            f"{mutation.name}: the anchor is not intact in "
            f"{mutation.target_file.name} after the mutation suite"
        )
        if mutation.new not in mutation.old:
            assert mutation.new not in text, (
                f"{mutation.name}: the mutated text is still in "
                f"{mutation.target_file.name} after the mutation suite"
            )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored section does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
