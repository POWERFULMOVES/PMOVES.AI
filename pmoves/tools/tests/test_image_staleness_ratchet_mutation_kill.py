"""Mutation-kill harness: the image-staleness ratchet's COPY-SOURCE probe
must BITE when the rules it enforces are put back.

THE DEFECT
----------
The ratchet asked one question about a matrix entry: does the Dockerfile
FILE exist? It never asked whether that Dockerfile could be BUILT from the
context the workflow hands the builder. A Dockerfile's ``COPY`` sources are
relative to the BUILD CONTEXT, so a repository that writes its Dockerfile
for its own subdirectory -- PMOVES-DoX's ``backend/Dockerfile`` does
``COPY requirements.txt ./`` -- produced an image the gate called VERIFIED
and the build could not produce. MEASURED on the live matrix: four entries
were in exactly that state (``pmoves-botz-gateway``, ``pmoves-gpu-orchestrator``,
``pmoves-tokenism-ui`` and ``pmoves-ultimate-tts-studio``), and the fourth of
those pointed at a Dockerfile for a DIFFERENT SERVICE than its name claimed.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the same three phases, in this order:

  1. GREEN BEFORE -- the pristine source must pass the selected test.
  2. RED AFTER    -- the mutated source must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored source must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed
run cannot leave the tree mutated, and the restore is asserted.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero" -- a collection error, a
timeout or an unrelated environment failure also satisfies that. The
harness reads pytest's own short test summary and requires the NAMED test
to be IN it. A harness may only claim a kill it can point at.

THE MUTATIONS
--------------
Each mutation removes or inverts ONE rule the probe depends on. The probe
is not allowed to become a probe that cannot fail.

  M1   an unresolvable COPY source is no longer reported
  M2   the ``--from=`` stage-copy rule is removed
  M3   a glob COPY source that matches nothing is no longer reported
  M4   ``build_context`` no longer moves the build context
  M5   the dead-``build_context`` rule is removed

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tools/tests/test_image_staleness_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no gh, no registry API. It mutates files in
this repo and restores them.
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
RATCHET = REPO_ROOT / "pmoves" / "tools" / "image_staleness_ratchet.py"
TEST_FILE = REPO_ROOT / "pmoves" / "tools" / "tests" / "test_image_staleness_ratchet.py"

_PYTEST_TIMEOUT_SECONDS = 300.0

_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-image-staleness-mutation.lock"


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
        name="M1_unresolvable_copy_source_is_no_longer_reported",
        target=RATCHET,
        old="""            if not _source_resolves(source, context_dir):
                unresolved.append(source)""",
        new="""            if False:
                unresolved.append(source)""",
        target_test="test_a_copy_source_the_context_does_not_hold_is_drifted",
        rationale=(
            "Without the resolution check every COPY source 'resolves', and "
            "the probe reports a build that cannot succeed as VERIFIED -- the "
            "exact defect this probe was added for."
        ),
    ),
    Mutation(
        name="M2_stage_copy_rule_removed",
        target=RATCHET,
        old="""        if any(flag.startswith("--from=") for flag in flags):
            continue""",
        new="""        if False:
            continue""",
        target_test="test_a_stage_copy_is_not_a_build_context_source",
        rationale=(
            "`COPY --from=build ./dist /out` copies from another build stage, "
            "not from the context. Without the rule the probe looks for "
            "`./dist` in the context and reports a perfectly good "
            "multi-stage Dockerfile as unbuildable."
        ),
    ),
    Mutation(
        name="M3_glob_copy_source_with_no_match_is_no_longer_reported",
        target=RATCHET,
        old="""        except OSError:
            return False
        return False""",
        new="""        except OSError:
            return True
        return True""",
        target_test="test_a_glob_copy_source_with_no_match_is_drifted",
        rationale=(
            "`COPY package*.json ./` fails when the context holds no "
            "package.json. A glob that matches nothing must be an "
            "unresolved source, not a resolved one."
        ),
    ),
    Mutation(
        name="M4_build_context_no_longer_moves_the_build_context",
        target=RATCHET,
        old="""        context_dir = base / build_context_rel if build_context_rel else base""",
        new="""        context_dir = base""",
        target_test="test_a_build_context_resolves_the_dockerfile_inside_it",
        rationale=(
            "`build_context` is the only way a matrix entry can say 'the "
            "context is this subdirectory'. Without it, every entry resolves "
            "against the repo root -- which is the pre-fix behaviour that "
            "produced four unbuildable images, and it is the "
            "`build_inputs` claim that observes it: the Dockerfile inside the "
            "subdirectory is no longer the file the build would open."
        ),
    ),
    Mutation(
        name="M5_dead_build_context_rule_removed",
        target=RATCHET,
        old="""        if build_context_rel:
            # `build_context` is read INSIDE the workflow's `matrix.repo &&`
            # branch, so for an entry with no `repo:` it is never read.
            return DRIFTED, (""",
        new="""        if False:
            # `build_context` is read INSIDE the workflow's `matrix.repo &&`
            # branch, so for an entry with no `repo:` it is never read.
            return DRIFTED, (""",
        target_test="test_a_dead_build_context_on_an_in_tree_entry_is_drifted",
        rationale=(
            "Dead build input is where a silently changed behaviour hides: "
            "the matrix says one thing and the build does another. The rule "
            "that catches it must not be removable."
        ),
    ),
    Mutation(
        name="M6_remote_add_url_treated_as_a_context_source",
        target=RATCHET,
        old="""        if verb == "ADD":
            sources = [
                word
                for word in sources
                if not _URL_RE.match(word) and not _CHECKSUM_RE.match(word)
            ]""",
        new="""        if False:
            sources = [
                word
                for word in sources
                if not _URL_RE.match(word) and not _CHECKSUM_RE.match(word)
            ]""",
        target_test="test_a_remote_add_url_is_not_a_build_context_source",
        rationale=(
            "`ADD <url>` FETCHES the url over the network -- docker's `ADD` "
            "supports remote urls precisely because it can download them, so "
            "the build context never has to contain them. MEASURED 2026-11-01: "
            "without this rule the probe reported DRIFTED for "
            "`pmoves-remote-view`, whose Dockerfile adds the s6-overlay "
            "tarballs by url -- and that Dockerfile BUILDS."
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
            "does not exist in the ratchet test file"
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


def test_the_tool_source_is_intact_after_the_mutation_suite():
    """The last mutation must leave the tree exactly as it found it."""
    source = RATCHET.read_text(encoding="utf-8")
    assert "if not _source_resolves(source, context_dir):" in source
    assert 'if any(flag.startswith("--from=") for flag in flags):' in source
    assert "context_dir = base / build_context_rel if build_context_rel else base" in source
    assert '"copy_sources": probe_copy_sources,' in source
