"""Mutation-kill harness: the integration-reconciliation ratchet must BITE.

THE DEFECT CLASS
----------------
A documentation index drifts from the executable configs it claims to
describe. This lane was opened by five MEASURED instances of that drift in
``docs/PMOVES.AI Services and Integrations.md`` and the two registries it
contradicts:

* **F1** -- the doc declared Archon's path as ``pmoves/services/archon``,
  which does not exist on disk.
* **F2** -- three files named three different Dockerfiles for the ONE
  published ``pmoves-yt`` image. The live matrix
  (``.github/workflows/integrations-ghcr.matrix.json``) declares
  ``dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile``; the doc and the
  orphan registry both named ``pmoves/services/pmoves-yt/Dockerfile`` as the
  published source.
* **F3** -- the three published ``pmoves-jellyfin-ai-*`` images were named
  nowhere in the doc.
* **F4** -- ``pmoves-docker-gateway-sse`` was named nowhere in the doc.
* **F5** -- ``pmoves/integrations/README.md`` listed four of the eight
  directories that are actually on disk.

A gate that reads the document can only be load-bearing if a plausible edit
to the document makes it fail. So this harness puts each defect back, in the
live tree, and requires the NAMED test to die each time. Every ratchet test
in the companion module has exactly one kill here.

THE KILL CONTRACT: GREEN, RED, GREEN
------------------------------------
Every mutation case runs the SAME three phases, in this order:

  1. GREEN BEFORE -- the pristine tree must pass the selected test.
  2. RED AFTER    -- the mutated tree must fail the NAMED test.
  3. GREEN AFTER  -- the byte-exact restored tree must pass again.

The restore is byte-exact and happens in a ``finally`` block, so a failed run
cannot leave the tree mutated, and the restore is asserted.

THE GREEN PHASES ARE BATCHED, THE RED PHASES ARE NOT
-----------------------------------------------------
Every phase here spawns a full ``python -m pytest`` child, and one child
startup is ~1.7s on this host -- irreducible. So the GREEN phases run ONCE
for the whole session, over EVERY target test; only the RED phase is
per-mutation, because the source under test differs.

THE KILL SIGNAL IS A TEST NAME, NOT A MOOD
-------------------------------------------
The kill signal is NOT "pytest exited non-zero and the word 'failed' appeared
somewhere in the output" -- a signal that a collection error, a timeout or an
unrelated environment failure also satisfies. The harness reads pytest's own
short test summary and requires the NAMED test to be IN it. A harness may
only claim a kill it can point at.

A MUTATION MUST REVERT THE WIRING
----------------------------------
Each mutation below changes the DOCUMENT or the REGISTRY the gate reads --
never the gate's own expression. A mutation that edited the gate would prove
nothing about the document it claims to check.

Run it directly to see the mutation kills in action:

    python -m pytest pmoves/tests/tools/test_integration_reconciliation_ratchet_mutation_kill.py -v

Hermetic: no network, no docker, no NATS, no gh, no credentials. It mutates
this lane's documents in this repo and restores them.
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

DOC = REPO_ROOT / "docs" / "PMOVES.AI Services and Integrations.md"
ORPHANS_YAML = REPO_ROOT / "pmoves" / "configs" / "dockerfiles" / "_known_orphans.yaml"
INTEGRATIONS_README = REPO_ROOT / "pmoves" / "integrations" / "README.md"

#: The compose overlay the `up-yt-published` path runs. Small on purpose: it
#: is the file M7 wires the orphan Dockerfile into.
COMPOSE_INTEGRATIONS_IMAGES = REPO_ROOT / "pmoves" / "docker-compose.integrations.images.yml"

RATCHET = (
    REPO_ROOT
    / "pmoves"
    / "tests"
    / "tools"
    / "test_integration_reconciliation_ratchet.py"
)

_PYTEST_TIMEOUT_SECONDS = 600.0

# The SAME house-wide lock the other mutation harnesses use. Two harnesses
# that mutate files in this repo must not hold the tree at once -- a mutation
# harness leaves the tree MUTATED by design, so anything that reads the tree
# during that window reads the mutation.
_MUTATION_LOCK = threading.Lock()
_LOCK_PATH = Path(tempfile.gettempdir()) / "pmoves-house-ci-mutation.lock"


@dataclass(frozen=True)
class Mutation:
    """One mutation: the rewrite(s), and the test that MUST die from it."""

    name: str
    edits: tuple[tuple[str, str], ...]
    target_test: str
    rationale: str
    target_file: Path


MUTATIONS: list[Mutation] = [
    # ------------------------------------------------------------------
    # F1 -- the non-existent pmoves/services/archon path
    # ------------------------------------------------------------------
    Mutation(
        name="M1_the_nonexistent_services_archon_path_put_back",
        edits=(
            (
                "there is no in-tree `pmoves/services/` wrapper directory for Archon",
                "`pmoves/services/archon` is Archon's path in this monorepo",
            ),
        ),
        target_test="test_every_services_path_the_doc_claims_exists_on_disk",
        rationale=(
            "This is the EXACT defect that was found: the doc declared "
            "Archon's path as `pmoves/services/archon`, and there is no such "
            "directory -- `pmoves/services/` holds 101 sibling directories "
            "and none of them is `archon`. A reader who followed that path "
            "found nothing. The mutation puts the path back exactly as it "
            "was."
        ),
        target_file=DOC,
    ),
    # ------------------------------------------------------------------
    # F2 -- the doc names the ORPHAN as the CI-published Dockerfile
    # ------------------------------------------------------------------
    Mutation(
        name="M2_the_doc_names_the_orphan_as_the_ci_published_dockerfile",
        edits=(
            (
                "`dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile`",
                "`dockerfile: pmoves/services/pmoves-yt/Dockerfile`",
            ),
        ),
        target_test="test_the_docs_pmoves_yt_published_dockerfile_is_the_one_ci_builds",
        rationale=(
            "The three-way contradiction, half one. The matrix says the CI "
            "image workflow builds `PMOVES.YT/pmoves_yt_service/Dockerfile`; "
            "the doc said the CI builds the orphan "
            "`pmoves/services/pmoves-yt/Dockerfile`, which installs stock "
            "yt-dlp from PyPI instead of the fork. The mutation makes the "
            "doc name the orphan again -- the two disagree, and the matrix "
            "is the truth."
        ),
        target_file=DOC,
    ),
    # ------------------------------------------------------------------
    # F2 -- the orphan registry names the ORPHAN as the published source
    # ------------------------------------------------------------------
    Mutation(
        name="M3_the_orphan_registry_names_the_orphan_as_the_published_source",
        edits=(
            (
                "and `dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile` -- and THAT image",
                "and `dockerfile: pmoves/services/pmoves-yt/Dockerfile` -- and THAT image",
            ),
        ),
        target_test=(
            "test_the_known_orphans_pmoves_yt_reason_names_the_ci_published_dockerfile"
        ),
        rationale=(
            "The three-way contradiction, half two. The registry's reason "
            "line claimed that integrations-ghcr.yml builds and PUSHES the "
            "orphan file and that docker-compose.integrations.images.yml "
            "consumes it on the up-yt-published path. It does not: CI builds "
            "the fork's Dockerfile. The mutation restores that claim."
        ),
        target_file=ORPHANS_YAML,
    ),
    # ------------------------------------------------------------------
    # F3 -- a published jellyfin-ai image is unnamed in the doc
    # ------------------------------------------------------------------
    Mutation(
        name="M4_a_published_jellyfin_ai_image_is_unnamed_in_the_doc",
        edits=(
            (
                "| `pmoves-jellyfin-ai-api-gateway` | `ghcr.io/powerfulmoves/pmoves-jellyfin-ai-api-gateway` | submodule `Pmoves-Jellyfin-AI-Media-Stack` | `Pmoves-Jellyfin-AI-Media-Stack/Cataclysm_Provisioning_Bundle/provisioning_bundle/docker-stacks/jellyfin-ai/api-gateway/Dockerfile` |\n",
                "",
            ),
            (
                "`pmoves-jellyfin-ai-api-gateway`, `pmoves-jellyfin-ai-dashboard`",
                "`pmoves-jellyfin-ai-dashboard`",
            ),
        ),
        target_test="test_every_published_image_name_is_named_in_the_services_doc",
        rationale=(
            "The defect that was found: `pmoves/images.yaml` publishes three "
            "jellyfin-ai images and the doc named NONE of them, so it "
            "described the Jellyfin-AI stack without naming a single image "
            "it actually publishes. The mutation removes one of the three "
            "names from BOTH places the doc carries it (the inventory table "
            "and the stack's own paragraph), which is the pre-fix state."
        ),
        target_file=DOC,
    ),
    # ------------------------------------------------------------------
    # F4 -- pmoves-docker-gateway-sse is unnamed in the doc
    # ------------------------------------------------------------------
    Mutation(
        name="M5_the_docker_gateway_sse_mcp_server_is_unnamed_in_the_doc",
        edits=(
            (
                "**pmoves-docker-gateway-sse** – *Docker MCP Toolkit gateway, SSE surface.*",
                "*Docker MCP Toolkit gateway, SSE surface.*",
            ),
        ),
        target_test="test_every_pmoves_hosted_mcp_server_is_named_in_the_services_doc",
        rationale=(
            "The defect that was found: `pmoves-docker-gateway-sse` is in "
            "`pmoves/config/mcp_inventory.json` and in `kilo.json` and two "
            "bootstrap scripts, and appeared ZERO times in the doc. It is an "
            "MCP server entry, NOT a published image, so the doc has to name "
            "it for what it is. The mutation un-names it."
        ),
        target_file=DOC,
    ),
    # ------------------------------------------------------------------
    # F5 -- an on-disk integration directory is unlisted
    # ------------------------------------------------------------------
    Mutation(
        name="M6_an_on_disk_integration_directory_is_unlisted",
        edits=(
            (
                "- `github-runners/` – GitHub runner lane policy "
                "(`compose/lane_hosts.json`, `compose/runner_phase_policy.json`)\n",
                "",
            ),
        ),
        target_test="test_every_integration_directory_is_named_in_the_integrations_readme",
        rationale=(
            "The defect that was found: `pmoves/integrations/` holds EIGHT "
            "directories and the README listed FOUR. `agent0-plugins/`, "
            "`github-runners/` and `tools/` were unlisted, and `_template/` "
            "was described only in prose. The mutation drops one of the "
            "three unlisted directories."
        ),
        target_file=INTEGRATIONS_README,
    ),
    # ------------------------------------------------------------------
    # F2 -- the orphan gets wired into a compose build stanza
    # ------------------------------------------------------------------
    Mutation(
        name="M7_the_orphan_pmoves_yt_dockerfile_is_wired_into_a_compose_build",
        edits=(
            (
                "    image: ${PMOVES_YT_IMAGE:-ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest}\n",
                "    image: ${PMOVES_YT_IMAGE:-ghcr.io/powerfulmoves/pmoves-yt:pmoves-latest}\n"
                "    build:\n"
                "      context: ../pmoves\n"
                "      dockerfile: services/pmoves-yt/Dockerfile\n",
            ),
        ),
        target_test="test_the_orphan_pmoves_yt_dockerfile_is_named_by_no_compose_build",
        rationale=(
            "The doc calls the orphan a NON-DEPLOYED copy, and says so "
            "because no compose `build:` stanza names it. That is a claim "
            "about the runtime, so the ratchet checks it against the "
            "compose tree instead of trusting the prose. The mutation "
            "wires the orphan into a compose build stanza -- the real-world "
            "event that would make the doc's description false -- and the "
            "gate must notice."
        ),
        target_file=COMPOSE_INTEGRATIONS_IMAGES,
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
    return f"{RATCHET.relative_to(REPO_ROOT).as_posix()}::{mutation.target_test}"


_GREEN_BEFORE: list[subprocess.CompletedProcess] = []


def _green_before() -> list[subprocess.CompletedProcess]:
    """GREEN BEFORE, once for the whole session: the pristine tree must
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
    """Return the mutated source, or raise if an anchor does not match.

    A mutation whose anchor has drifted must FAIL LOUDLY. Silently mutating
    nothing would produce a green harness that proves nothing.
    """
    mutated = original
    for old, new in mutation.edits:
        if old not in mutated:
            raise AssertionError(
                f"mutation {mutation.name}: anchor not found in "
                f"{mutation.target_file.name}. The source changed -- update "
                f"the mutation.\n--- expected ---\n{old}"
            )
        mutated = mutated.replace(old, new, 1)
    if mutated == original:
        raise AssertionError(f"mutation {mutation.name}: the rewrite was a no-op")
    return mutated


def _read_source(path: Path) -> tuple[str, bool]:
    """(text, uses_crlf) for a source file.

    The text is normalised to ``\\n`` so a mutation anchor is line-ending
    independent; the flag records the file's OWN convention so the restore
    can put it back exactly as it was.
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
        for old, new in mutation.edits:
            assert old in original, (
                f"mutation {mutation.name}: anchor not found in "
                f"{mutation.target_file.name} -- the source drifted"
            )
            assert old != new, mutation.name
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
    must pass again -- and the mutated documents must be byte-identical to
    the originals."""
    doc = DOC.read_text(encoding="utf-8")
    assert "pmoves/services/archon" not in doc, (
        "the non-existent pmoves/services/archon path is back in the doc"
    )
    assert (
        "`dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile`" in doc
    ), "the doc's CI-published pmoves-yt Dockerfile is not intact"
    assert (
        "`dockerfile: pmoves/services/pmoves-yt/Dockerfile`" not in doc
    ), "the doc names the orphan pmoves-yt Dockerfile as the published source again"
    assert "pmoves-jellyfin-ai-api-gateway" in doc, (
        "the published jellyfin-ai api-gateway image is not intact in the doc"
    )
    assert "pmoves-docker-gateway-sse" in doc, (
        "the pmoves-docker-gateway-sse MCP server is not intact in the doc"
    )

    orphans = ORPHANS_YAML.read_text(encoding="utf-8")
    assert (
        "and `dockerfile: PMOVES.YT/pmoves_yt_service/Dockerfile` -- and THAT image"
        in orphans
    ), "the orphan registry's pmoves-yt reason line is not intact"

    readme = INTEGRATIONS_README.read_text(encoding="utf-8")
    assert "`github-runners/`" in readme, (
        "the github-runners integration directory is not listed in the README"
    )

    compose = COMPOSE_INTEGRATIONS_IMAGES.read_text(encoding="utf-8")
    assert "dockerfile:" not in compose, (
        "a compose build stanza still names the pmoves-yt orphan Dockerfile"
    )

    node_ids = [_node_id(mutation) for mutation in MUTATIONS]
    after = _run_pytest(node_ids)
    assert after.returncode == 0, (
        "the restored tree does not pass every target test again\n"
        f"{after.stdout[-4000:]}"
    )
