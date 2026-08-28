"""Guard the Cipher Memory Qdrant collection against the "provisioner with no road" defect.

The defect
----------
Cipher's embedding sidecar (`Pmoves-cipher/src/pmoves/embedding.ts`) creates its
Qdrant collection lazily, in `ensureCollection()`. That is only ever reached
from `storeVector()`, `search()` and `deleteVector()`, and `memory-routes.ts`
gates all of them behind a successful `sidecar.embed()`::

    const embedding = await sidecar.embed(content)
    if (embedding) { await sidecar.storeVector(...) }   // only path to ensureCollection()

So on a node where no embedding backend is reachable, `embed()` returns null,
the create never fires, and `pmoves_cipher_memory` never exists — while
`POST /api/memory` keeps answering 201 off ByteRover's lexical store. Measured
on B850 (2026-08-27): collection absent, `embedding_id: null` on every write.

The repo already had this exact shape once. `scripts/provision_qdrant_pmoves_chunks_qwen3.py`
is a correct, idempotent provisioner that no Make target and no compose service
references, so nothing ever runs it — and `pmoves_chunks_qwen3` drifted to the
384d demo width that `seed_local.py` recreates it at. A provisioner reachable
only by hand exists on one machine and dies with the next volume reset.

What is asserted
----------------
1. `provision_qdrant_cipher_memory.py` exists and declares the schema
   `embedding.ts` actually uses — named `dense` vector, Cosine, and a `bm25`
   sparse vector with `modifier: idf`. Drift here silently breaks RRF fusion.
2. That script is reachable through a Known Road (`qdrant-provision-cipher`),
   and that road actually invokes it.
3. The bring-up roads for Cipher (`up-cipher`, `up-cipher-full`) run the
   provisioner, so a fresh node gets the collection without a manual step.
4. `cipher-memory-smoke` asserts on `embedding_id` and `score` rather than on
   curl's exit status alone — otherwise it passes with the vector path dead.
5. Non-vacuity: `embedding.ts` still gates `storeVector` behind `embed()`, and
   still writes the named vectors this provisioner creates. If the sidecar is
   ever changed to provision eagerly, assertions 1-3 stop guarding anything and
   this test should be revisited rather than silently kept green.

Deliberately static: no `docker`, no Qdrant, no tier env files, so this runs in
CI. The live behaviour it stands in for was verified on B850 — collection
created at 2560d Cosine + bm25/idf, re-run is a no-op, `EMBEDDING_DIM=768`
reports MISMATCH and exits 2 without mutating, and a probe point round-trips
through the dense + BM25 + RRF query shape.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PMOVES = REPO_ROOT / "pmoves"
MAKEFILE = PMOVES / "Makefile"
PROVISIONER = PMOVES / "scripts" / "provision_qdrant_cipher_memory.py"
EMBEDDING_TS = REPO_ROOT / "Pmoves-cipher" / "src" / "pmoves" / "embedding.ts"

PROVISION_TARGET = "qdrant-provision-cipher"
SCRIPT_BASENAME = "provision_qdrant_cipher_memory.py"


def _recipe(target: str) -> str:
    """Return the recipe lines for `target` from the Makefile.

    A recipe runs from the target line until the first line that is neither
    indented with a tab nor blank.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^%s\s*:(?!=)[^\n]*\n" % re.escape(target), text, re.MULTILINE)
    assert match, "Makefile has no target %r" % target
    lines = []
    for line in text[match.end():].splitlines():
        if line.startswith("\t"):
            lines.append(line)
        elif line.strip() == "":
            continue
        else:
            break
    return "\n".join(lines)


def test_provisioner_declares_the_schema_embedding_ts_uses():
    assert PROVISIONER.is_file(), "missing %s" % PROVISIONER
    src = PROVISIONER.read_text(encoding="utf-8")
    assert 'DENSE_FIELD = "dense"' in src
    assert 'BM25_FIELD = "bm25"' in src
    assert 'DISTANCE = "Cosine"' in src
    assert 'SPARSE_MODIFIER = "idf"' in src, (
        "BM25 sparse vectors need modifier 'idf'; without it RRF fusion scores are wrong"
    )


def test_provisioner_is_reachable_through_a_known_road():
    recipe = _recipe(PROVISION_TARGET)
    assert SCRIPT_BASENAME in recipe, (
        "%s does not invoke %s — the provisioner would be unreachable, which is the "
        "exact defect that left provision_qdrant_pmoves_chunks_qwen3.py dead"
        % (PROVISION_TARGET, SCRIPT_BASENAME)
    )


def test_provisioner_runs_from_a_container_on_the_qdrant_network():
    # Qdrant is not guaranteed to publish a host port (it does not on B850), so a
    # host-side invocation cannot reach it. The road must run in-network.
    recipe = _recipe(PROVISION_TARGET)
    assert "--network pmoves_data" in recipe, (
        "%s must run on pmoves_data; Qdrant may publish no host port" % PROVISION_TARGET
    )


def test_cipher_bringup_roads_provision_the_collection():
    for target in ("up-cipher", "up-cipher-full"):
        recipe = _recipe(target)
        assert PROVISION_TARGET in recipe, (
            "%s does not run %s — a fresh node would start Cipher with no collection"
            % (target, PROVISION_TARGET)
        )


def test_smoke_fails_when_the_vector_path_is_dead():
    recipe = _recipe("cipher-memory-smoke")
    # Both endpoints answer 2xx off the lexical fallback with Qdrant absent, so
    # exit-status-only assertions pass on a dead pipeline.
    assert "embedding_id" in recipe, (
        "cipher-memory-smoke must assert POST returned a non-null embedding_id"
    )
    assert '"score"' in recipe, (
        "cipher-memory-smoke must assert search results carry a score (vector hits) "
        "rather than lexical-fallback rows"
    )
    # memory-routes.ts rejects a body without agentId with a 400, and `curl -sf`
    # hides the reason. The payload must carry one or the target fails blind.
    assert "agentId" in recipe, "cipher-memory-smoke POST body must include agentId"


def test_non_vacuity_sidecar_still_gates_creation_behind_embedding():
    """If this fails, the sidecar may provision eagerly and this guard is moot.

    Skips rather than fails when the submodule is not checked out — CI clones
    without submodules should not red-flag on a missing working tree.
    """
    import pytest

    if not EMBEDDING_TS.is_file():
        pytest.skip("Pmoves-cipher submodule not checked out")
    src = EMBEDDING_TS.read_text(encoding="utf-8")
    assert "ensureCollection" in src
    # storeVector's first act is the ensureCollection guard — creation is a
    # side effect of a write, never a startup step.
    assert "if (!(await this.ensureCollection())) return" in src, (
        "embedding.ts no longer gates writes on ensureCollection() — re-check whether "
        "eager provisioning is still needed"
    )
    assert "const DENSE_FIELD = 'dense'" in src
    assert "const BM25_FIELD = 'bm25'" in src
    assert "modifier: 'idf'" in src
