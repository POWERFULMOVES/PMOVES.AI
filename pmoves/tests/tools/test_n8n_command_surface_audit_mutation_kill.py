"""Mutation-kill harness: the n8n command-surface ratchet must BITE when the
defect it exists for is put back.

THE DEFECT CLASS
----------------
``.claude/commands/n8n/*.md`` are slash commands an agent executes. Each of
them carried a second, dead path -- a ``docker exec`` into a container named
``pmoves-n8n-agent-1`` running a python payload that imported
``app_n8n_agent``. That path could not work, for TWO independent reasons:

  1. NO COMPOSE FILE CREATES THAT CONTAINER. No compose file in this
     repository defines an ``n8n-agent`` service; the live n8n containers are
     ``pmoves-n8n`` (pmoves/docker-compose.n8n.yml:21), ``pmoves-n8n-runners``
     (same file:71) and ``pmoves-n8n-db``
     (pmoves/docker-compose.n8n.postgres.yml:4).
  2. THE MODULE IS NOT IN THE IMAGE. The n8n image is built from
     ``PMOVES-n8n/compose/n8n/Dockerfile``, whose entire content is
     ``FROM n8nio/n8n:2.1.0`` -- a stock image with no PMOVES python module.
     Repointing the container name at ``pmoves-n8n`` would move the failure to
     ``ModuleNotFoundError: No module named 'app_n8n_agent'``.

The registry entry ``pmoves/config/mcp/n8n-agent.yaml`` carried the same dead
wiring: ``command: docker`` with ``args: [exec, -i,
docker-compose-n8n-agent-1, python, app_n8n_agent.py]``, naming a container no
compose file creates and a module the image does not carry.

A gate that only reads those files can only be load-bearing if a plausible
edit puts the defect back. So this harness puts it back, three ways, and
requires the NAMED test to die each time.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine tree must pass the selected test.
  2. RED AFTER    -- the mutated tree must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored tree must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted. The pristine bytes
are also written to a backup (pmoves/tests/mutation_backup.py) BEFORE the
mutation, so a KILLED process -- which runs no ``finally`` -- cannot leave the
tree dirty for the next session to inherit.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
Every phase here spawns a full ``python -m pytest`` child, and one child
startup is ~1.7s on this host -- irreducible. So the GREEN phases run ONCE for
the whole session, over every target test, and only the RED phase runs
per-mutation (it is the only phase whose source differs).

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero" -- a signal that a collection
error, a timeout or an unrelated environment failure also satisfies. The
harness reads pytest's own short test summary and requires the NAMED test to
be IN it. A harness may only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below changes the DOCUMENT the gate reads -- a slash command
file or the MCP registry entry -- and never re-types the gate's own
expression. A mutation that edited the gate would prove nothing about the
document it claims to check.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_n8n_command_surface_audit_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
files in this repository and restores them.
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

RATCHET = (
    REPO_ROOT
    / "pmoves"
    / "tests"
    / "tools"
    / "test_n8n_command_surface_audit.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

#: The SAME house-wide lock the other harnesses use. Two harnesses that mutate
#: files in this repo must not hold the tree at once -- a mutation harness
#: leaves the tree MUTATED by design, so anything that reads the tree during
#: that window reads the mutation.
_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-n8n-command-mutation.lock"


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
    # M1 -- the retired CONTAINER name, back in a slash command
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_retired_container_name_is_back_in_a_slash_command",
        old="# 1. Resolve name -> workflow ID",
        new=(
            "# Or via n8n MCP tool\n"
            "docker exec pmoves-n8n-agent-1 python3 -c \"print('ok')\"\n"
            "\n"
            "# 1. Resolve name -> workflow ID"
        ),
        target_test="test_no_docker_exec_target_outside_the_compose_container_set",
        rationale=(
            "This is the EXACT defect that was found: the command file named "
            "a container that no compose file creates. `pmoves-n8n-agent-1` "
            "is not a declared `container_name:` anywhere, and `n8n-agent` is "
            "not a service key in any compose file, so it is in neither the "
            "declared set nor the compose-default set. The payload is kept "
            "import-free on purpose: M1 must kill the CONTAINER assertion "
            "alone, so that M2 can kill the IMPORT assertion alone."
        ),
        target_file=REPO_ROOT / ".claude" / "commands" / "n8n" / "execute.md",
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # M2 -- the retired MODULE import, back in a slash command
    # ------------------------------------------------------------------
    Mutation(
        name="M2_the_retired_module_import_is_back_in_a_slash_command",
        old="# List all workflows",
        new=(
            "# Or via n8n MCP tool\n"
            "python3 -c \"\n"
            "from app_n8n_agent import N8nClient\n"
            "\"\n"
            "\n"
            "# List all workflows"
        ),
        target_test="test_no_command_file_imports_a_module_absent_from_the_n8n_image",
        rationale=(
            "The mirror of M1, and the reason a rename-only fix would have "
            "shipped a still-broken command: the n8n image is "
            "`FROM n8nio/n8n:2.1.0` with no COPY, so `app_n8n_agent` is in "
            "neither the standard library nor the image's module set. "
            "Repointing the container would have moved this failure from "
            "'no such container' to ModuleNotFoundError. No `docker exec` is "
            "used here, so this mutation kills the IMPORT assertion alone."
        ),
        target_file=REPO_ROOT / ".claude" / "commands" / "n8n" / "workflows.md",
        test_file=RATCHET,
    ),
    # ------------------------------------------------------------------
    # M3 -- the dead stdio server, re-activated in the MCP registry entry
    # ------------------------------------------------------------------
    Mutation(
        name="M3_the_dead_stdio_server_is_reactivated_in_the_registry_entry",
        old=(
            "# transport: stdio\n"
            "# command: docker\n"
            "# args:\n"
            "#   - exec\n"
            "#   - -i\n"
            "#   - <the re-enabled agent container name>\n"
            "#   - python\n"
            "#   - app_n8n_agent.py\n"
        ),
        new=(
            "transport: stdio\n"
            "command: docker\n"
            "args:\n"
            "  - exec\n"
            "  - -i\n"
            "  - docker-compose-n8n-agent-1\n"
            "  - python\n"
            "  - app_n8n_agent.py\n"
        ),
        target_test=(
            "test_the_n8n_agent_registry_entry_keeps_its_id_and_declares_no_dead_stdio_server"
        ),
        rationale=(
            "The registry entry is where the dead wiring was last written "
            "down: `docker-compose-n8n-agent-1` is a container no compose "
            "file creates, and `app_n8n_agent.py` is a module the n8n image "
            "does not carry. The loader "
            "(pmoves/tools/mcp_utils.py:load_mcp_tools) does not read "
            "`command`/`args`, so re-activating them would not change the "
            "roster -- it would just put a false claim back into a live "
            "config file, which is exactly the state this lane reconciled."
        ),
        target_file=REPO_ROOT / "pmoves" / "config" / "mcp" / "n8n-agent.yaml",
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
    """GREEN BEFORE, once for the whole session: the pristine tree must pass
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
            f"{mutation.name}: the pristine tree does not pass "
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
    must pass again -- and the tree must be byte-identical to the original."""
    retired = ("pmoves-n8n-agent-1", "docker-compose-n8n-agent-1")

    for path in (REPO_ROOT / ".claude" / "commands" / "n8n" / "execute.md",
                 REPO_ROOT / ".claude" / "commands" / "n8n" / "workflows.md"):
        text = path.read_text(encoding="utf-8")
        for name in retired:
            assert name not in text, (
                f"{path.name} still names the retired container {name}"
            )

    # The registry entry keeps the retired names in its EXPLANATION, which is
    # the point of the explanation -- but never in an ACTIVE line. An active
    # line is one that is not a comment.
    registry = REPO_ROOT / "pmoves" / "config" / "mcp" / "n8n-agent.yaml"
    for line in registry.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for name in retired:
            assert name not in stripped, (
                f"the registry entry names the retired container {name} on an "
                f"active line: {stripped}"
            )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored tree does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
