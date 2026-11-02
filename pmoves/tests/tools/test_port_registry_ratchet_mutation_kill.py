"""Mutation-kill harness: the port registry ratchet's fixes must BITE when the
defect is put back.

This is the PROVENANCE HARNESS for the code-review fixes to the port registry
ratchet (``pmoves/tools/port_registry_ratchet.py``) on PR #3445. The sibling
ratchets in this repo already carry one; this file closes the gap.

THE DEFECTS
-----------
Six defects, all of them the same species -- the tool's SELF-DOCUMENTATION and
its ENFORCEMENT disagreeing, or the tool skipping an input it cannot measure:

  F6  ``--write-collisions`` baselined EVERY published host port, not only
      the ports two or more services claim. The writer therefore manufactured
      its own failure: on the next ``--check`` every single-claimant entry
      hit the STALE branch and the gate exited 1. A smoke detector that
      burns the house down when you press the test button.
  F7  The writer emitted the placeholder reason while the header it wrote
      claimed "the ratchet accepts it" -- and the gate rejected that very
      placeholder as UNREVIEWED. The documented auto-baseline flow could
      never produce a passing file.
  F8  A compose port entry that is not a string -- the LONG-SYNTAX mapping
      form (``published:``/``target:``) -- was silently skipped, and so was a
      ``ports:`` that is not a list. This is a gate whose stated religion is
      FAIL CLOSED, and it shrugged at the one compose syntax it cannot
      measure.
  F23 ``check_python_registries``'s docstring promised a rule the code did
      not enforce: the docstring said the host port counted only for a
      service with no container port recorded, and the code accepted the host
      port unconditionally.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted. The source is
read and written with ``newline=""`` so the tool's LF line endings survive
the harness untouched.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
Every phase spawns a full ``python -m pytest`` child, and one child startup
is ~1.6s on this host -- irreducible. So:

  * GREEN BEFORE runs once, before any mutation, over ALL the target tests;
  * RED AFTER runs per mutation, over the ONE named test (the only phase
    that has to be per-mutation: the source under test differs);
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
Each mutation below restores the PRE-FIX behaviour of the exact branch the
named test guards:

  M1  the writer's multi-claimant filter is removed -- every published port
      is baselined again, and the next check calls them STALE;
  M2  the writer's header is restored to the text that claims the ratchet
      accepts the placeholder;
  M3  the gate stops rejecting the placeholder the writer emits -- the
      behaviour the pre-fix header CLAIMED, and the documented writer flow
      cannot survive;
  M4  a non-string compose port entry is skipped again instead of reported;
  M5  a ``ports:`` that is not a list is skipped again instead of reported;
  M6  ``check_python_registries``'s docstring is restored to the text that
      promises a rule the code does not enforce.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_port_registry_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh. It mutates one file in this
repo and restores it.
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
TOOL = REPO_ROOT / "pmoves" / "tools" / "port_registry_ratchet.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tests" / "tools" / "test_port_registry_ratchet.py"

_PYTEST_TIMEOUT_SECONDS = 600.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-port-registry-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite, and the test that MUST die from it."""

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
        name="M1_writer_baselines_every_published_port",
        old="""        shared = {
            port: info for port, info in collisions.items() if info["count"] > 1
        }""",
        new="""        shared = {
            port: info for port, info in collisions.items()
        }""",
        target_test="test_the_collision_writer_baselines_only_multi_claimant_ports",
        rationale=(
            "The baseline records the host ports TWO OR MORE services claim. "
            "Without the filter the writer records every published port, and "
            "the next --check calls each single-claimant entry STALE -- the "
            "documented writer flow manufacturing the failure it exists to "
            "prevent."
        ),
    ),
    Mutation(
        name="M2_writer_header_claims_the_ratchet_accepts_the_placeholder",
        old="""            "# Every entry needs a real reason. The writer emits the\\n"
            "# PLACEHOLDER reason\\n"
            "#\\n"
            "#     REVIEW THIS -- a pre-existing duplicate host port\\n"
            "#\\n"
            "# and the gate reports EVERY entry that still carries it as\\n"
            "# UNREVIEWED. So a freshly written baseline FAILS the gate until\\n"
            "# a human replaces each reason with why these two services may\\n"
            "# share the port. The placeholder is a to-do, NOT a review: the\\n"
            "# ratchet does not accept it.\\n\"""",
        new="""            "# Every entry needs a real reason. 'REVIEW THIS' is a placeholder and\\n"
            "# the ratchet accepts it, but a reason that says nothing is a claim\\n"
            "# nobody checked.\\n\"""",
        target_test="test_the_collision_writer_header_says_the_gate_rejects_the_placeholder_reason",
        rationale=(
            "The header the writer writes must describe the gate that reads "
            "it. The pre-fix header claimed the ratchet ACCEPTS the "
            "placeholder while the same file's gate rejected it -- so the "
            "written file and the code told opposite stories."
        ),
    ),
    Mutation(
        name="M3_gate_stops_rejecting_the_placeholder",
        old="""        reason = str(entry.get("reason") or "").strip()
        if not reason or reason.upper().startswith(REVIEW_PLACEHOLDER_PREFIX):
            unreviewed_collisions.append(port)""",
        new="""        reason = str(entry.get("reason") or "").strip()
        if not reason:
            unreviewed_collisions.append(port)""",
        target_test="test_a_freshly_written_collision_baseline_fails_the_gate_as_unreviewed_and_not_as_stale",
        rationale=(
            "The behaviour the pre-fix header CLAIMED: the ratchet accepts "
            "the placeholder. With that in force the freshly written "
            "baseline passes the gate, and a baseline nobody ever reviewed "
            "becomes the gate's own pass -- the reason the writer's "
            "placeholder exists."
        ),
    ),
    Mutation(
        name="M4_non_string_port_entry_skipped_again",
        old="""            for entry in entries:
                if not isinstance(entry, str):
                    # FAIL CLOSED at ENTRY granularity. The compose
                    # LONG-SYNTAX mapping form (`published:`/`target:`) is a
                    # legitimate Docker Compose feature -- it is NOT malformed
                    # -- but this instrument measures only the short string
                    # form, so the entry is REPORTED as unmeasured rather than
                    # silently skipped.
                    errors.append(
                        {
                            "file": rel,
                            "error": (
                                f"service {svc}: port entry is not a string "
                                f"(got {type(entry).__name__}) -- this instrument "
                                "measures only the short string form of a compose "
                                "port entry; the compose LONG-SYNTAX mapping form "
                                "(`published:`/`target:`) is a legitimate Docker "
                                "Compose feature that this instrument does not yet "
                                "measure, so the entry is REPORTED rather than "
                                "skipped"
                            ),
                        }
                    )
                    continue""",
        new="""            for entry in entries:
                if not isinstance(entry, str):
                    continue""",
        target_test="test_a_compose_long_syntax_port_entry_is_reported_not_skipped",
        rationale=(
            "A compose port entry this instrument cannot read is reported, "
            "not walked past. Without the report the long-syntax mapping "
            "form -- a bare published host port the gate never measures -- "
            "is invisible to the very gate that exists to catch it."
        ),
    ),
    Mutation(
        name="M5_non_list_ports_skipped_again",
        old="""            raw_entries = spec.get("ports")
            if raw_entries is None:
                entries: list = []
            elif isinstance(raw_entries, list):
                entries = raw_entries
            else:
                # FAIL CLOSED at ENTRY granularity: a `ports:` this
                # instrument cannot read is reported, not walked past.
                errors.append(
                    {
                        "file": rel,
                        "error": (
                            f"service {svc}: `ports` is not a list "
                            f"(got {type(raw_entries).__name__}) -- this instrument "
                            "cannot measure it"
                        ),
                    }
                )
                continue""",
        new="""            entries = spec.get("ports") or []
            if not isinstance(entries, list):
                continue""",
        target_test="test_a_compose_service_whose_ports_is_not_a_list_is_reported_not_skipped",
        rationale=(
            "The same fail-closed rule at the OTHER entry granularity: a "
            "`ports:` that is not a list cannot be enumerated, so it must be "
            "reported rather than skipped."
        ),
    ),
    Mutation(
        name="M6_python_registry_docstring_promises_an_unenforced_rule",
        old='''def check_python_registries(registry: dict, py: dict) -> list[dict]:
    """Each Python registry's port must exist as a slot in the canonical registry.

    THE SEMANTIC DISTINCTION, MEASURED: the two Python registries record the
    port a client uses to reach the service. For most services that is the
    CONTAINER port, but it is NOT always: compose publishes a HOST port,
    which is a different number for most services (``pmoves-ui`` listens on
    3000 and is published on 4482; ``supabase-db`` listens on 5432 and is
    published on 54322), and a service the canonical registry records with
    BOTH a container port and a host port is sometimes listed in a Python
    registry under its published HOST port.

    ENFORCED RULE: a Python registry port matches when it equals the
    CONTAINER port or the HOST port of any slot of that service. A drift is
    reported only when it matches NEITHER.

    WHY NOT THE STRICTER RULE: an earlier version of this docstring promised
    that the host port counted only for a service whose slots record no
    container port. MEASURED against the committed tree, the two Python
    registries do not satisfy that rule -- the host-port arm is load-bearing,
    and the strict rule turns the committed tree RED for a shape the
    registries legitimately have. The looser rule above is therefore the
    enforced one, and the measurement lives in the tree rather than in this
    paragraph: `test_the_python_registry_host_port_fallback_is_load_bearing`
    computes it.
    """''',
        new='''def check_python_registries(registry: dict, py: dict) -> list[dict]:
    """Each Python registry's port must exist as a slot in the canonical registry.

    THE SEMANTIC DISTINCTION, MEASURED: the two Python registries record the
    port the service LISTENS ON -- the CONTAINER port. Compose publishes a
    HOST port, which is a different number for most services: ``pmoves-ui``
    listens on 3000 and is published on 4482; ``supabase-db`` listens on 5432
    and is published on 54322. Comparing a Python registry against the
    registry's HOST port therefore reports four false drifts, which is what
    the first version of this rule did. The comparison is against the
    CONTAINER port, falling back to the host port only when no container port
    is recorded.
    """''',
        target_test="test_the_python_registry_docstring_states_the_rule_the_gate_enforces",
        rationale=(
            "A docstring that promises a rule the code does not enforce is "
            "worse than no docstring: a reader takes the promise as the "
            "contract. The pre-fix text promised the host-port fallback was "
            "conditional; the code accepts the host port unconditionally."
        ),
    ),
]


def _read_source(path: Path) -> str:
    """Read the source WITHOUT newline translation.

    The tool uses LF endings; a translating read plus a translating write
    would silently rewrite the file to CRLF and the restore would not be
    byte-exact.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _write_source(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _run_pytest(
    node_ids: list[str], timeout: float = _PYTEST_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess:
    # NOTE: no `--timeout` flag. That flag belongs to the `pytest-timeout`
    # PLUGIN, which is not installed in every CI environment -- and a flag
    # the plugin does not know makes pytest exit 4 with "unrecognized
    # arguments", which would make this harness report a kill for the WRONG
    # reason (a collection failure, not a red test). The outer
    # `subprocess.run(timeout=...)` is the real guard.
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


def _node_id(target_test: str) -> str:
    return f"{TEST_FILE.relative_to(REPO_ROOT).as_posix()}::{target_test}"


_GREEN_BEFORE: list[subprocess.CompletedProcess] = []


def _green_before() -> list[subprocess.CompletedProcess]:
    """GREEN BEFORE, once for the whole session: the pristine source must pass
    EVERY target test."""
    if not _GREEN_BEFORE:
        node_ids = [_node_id(mutation.target_test) for mutation in MUTATIONS]
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
        original = _read_source(mutation.path)
        assert mutation.old in original, (
            f"mutation {mutation.name}: anchor not found in "
            f"{mutation.path.name} -- the source drifted"
        )
        assert mutation.old != mutation.new, mutation.name
        assert mutation.target_test, mutation.name


@pytest.mark.parametrize("mutation", MUTATIONS, ids=lambda m: m.name)
def test_the_mutation_kills_the_named_test(mutation: Mutation) -> None:
    """GREEN -> RED, with a byte-exact restore. GREEN is batched (see the
    module docstring): it runs once before any mutation and once after the
    last restore, over every target test."""
    node_id = _node_id(mutation.target_test)
    target = mutation.path
    original = _read_source(target)

    with _MUTATION_LOCK, _file_lock(_LOCK_PATH):
        # 1. GREEN BEFORE (batched over every target test)
        before = _green_before()[0]
        assert before.returncode == 0, (
            f"{mutation.name}: the pristine source does not pass "
            f"{mutation.target_test}\n{before.stdout[-4000:]}"
        )

        mutated = _apply_mutation(mutation, original)
        try:
            _write_source(target, mutated)

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
            # The evidence, printed: WHICH named test died, under WHICH
            # mutation. A harness may only claim a kill it can point at.
            print(f"KILL {mutation.name}: {mutation.target_test}", flush=True)
        finally:
            # 3. restore -- byte-exact
            _write_source(target, original)
            restored = _read_source(target)
            assert restored == original, f"{mutation.name}: the restore was not byte-exact"


def test_the_tool_source_is_intact_after_the_mutation_suite():
    """GREEN AFTER: after every mutation has been restored, every target test
    must pass again -- and the source must be byte-identical to the
    original."""
    original = _read_source(TOOL)
    assert 'if info["count"] > 1' in original
    assert "# UNREVIEWED. So a freshly written baseline FAILS the gate until" in original
    assert "reason.upper().startswith(REVIEW_PLACEHOLDER_PREFIX)" in original
    assert "port entry is not a string" in original
    assert "`ports` is not a list" in original
    assert "ENFORCED RULE" in original

    node_ids = [_node_id(mutation.target_test) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored source does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
