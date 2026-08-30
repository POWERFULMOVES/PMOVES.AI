#!/usr/bin/env python3
"""Provision the Qdrant collection Cipher Memory writes into (`pmoves_cipher_memory`).

WHY THIS EXISTS
---------------
`Pmoves-cipher/src/pmoves/embedding.ts::ensureCollection()` *does* create the
collection on demand — but it is only ever called from `storeVector()`,
`search()` and `deleteVector()`, and all three are gated behind a successful
`sidecar.embed()`:

    const embedding = await sidecar.embed(content)      # memory-routes.ts:36
    if (embedding) {
      await sidecar.storeVector(...)                    # <- only path to ensureCollection()
    }

So on any node where TensorZero/Ollama is unreachable, `embed()` returns null,
`ensureCollection()` never runs, and the collection is never created. Cipher
still answers 201/200 because `POST /api/memory` falls back to ByteRover's
lexical store and `GET /api/memory/search` falls back to `lexicalFallback()`.
The vector path is dead and nothing says so. Provisioning eagerly, from the
repo, removes that dependency on a lucky first write.

The sibling script `provision_qdrant_pmoves_chunks_qwen3.py` is the pattern this
follows — including its exit-code contract. Note that script has no Make target
and no init container, which is why nothing ever runs it. This one is wired to
both (`make -C pmoves qdrant-provision-cipher`, and the `qdrant-init` compose
one-shot).

SCHEMA
------
Mirrors exactly what `embedding.ts` writes and queries. Do not drift from it:

    vectors:        { "dense": { size: EMBEDDING_DIM, distance: "Cosine" } }
    sparse_vectors: { "bm25":  { modifier: "idf" } }

`storeVector` upserts `{dense: <vector>, bm25: {text, model: "qdrant/bm25"}}`
and `search` runs a dense prefetch + a BM25 prefetch fused with `{fusion:
"rrf"}`. Qdrant >= 1.14 tokenizes `qdrant/bm25` documents server-side, so no
external inference service is required for the sparse half.

IDEMPOTENCY
-----------
Re-running is safe. If the collection already matches, this is a no-op and
exits 0 without mutating anything. If it exists but disagrees with the schema
above it exits 2 and leaves the data alone — Qdrant cannot add a sparse-vector
field to a live collection, so reconciling means a recreate, and that is the
operator's call, not this script's.

USAGE
-----
Known Road (preferred):

    make -C pmoves qdrant-provision-cipher
    make -C pmoves qdrant-verify-cipher      # provision, then --self-test

SELF-TEST (`--self-test`)
-------------------------
After provisioning, round-trips a probe point through the collection using the
exact request bodies `embedding.ts` sends — the named-vector upsert from
`storeVector()` and the dense-prefetch + BM25-prefetch + `{fusion: "rrf"}` query
from `search()` — then deletes the probe by payload filter the way
`deleteVector()` does.

The dense half uses a synthetic unit vector, not a real embedding: this checks
that the COLLECTION can serve what the code asks of it, which is answerable on a
node whose embedding backend is down. It is deliberately not a substitute for
`make -C pmoves cipher-memory-smoke`, which exercises Cipher's own HTTP surface
and fails when the embedding backend is unreachable.

From the host, if Qdrant publishes a port on this node:

    cd pmoves && . ./scripts/with-env.sh
    python3 scripts/provision_qdrant_cipher_memory.py

From inside any container on a Qdrant-reachable network:

    docker exec pmoves-cipher-api-1 python3 /scripts/provision_qdrant_cipher_memory.py

Environment:
    QDRANT_URL                       default http://qdrant:6333
    QDRANT_API_KEY / QDRANT__API_KEY required when Qdrant enforces auth
    QDRANT_CIPHER_COLLECTION         default pmoves_cipher_memory
    EMBEDDING_DIM                    default 2560 (qwen3-embedding:4b)
    QDRANT_WAIT_SECONDS              default 0 (how long to wait for Qdrant to come up)
    QDRANT_RECREATE_ON_MISMATCH      default false — set 1/true/yes to DROP AND
                                     RECREATE on schema mismatch (DATA LOSS)

Exit codes (same contract as provision_qdrant_pmoves_chunks_qwen3.py):
    0 — collection matches the expected schema, or was just created
        (and, with --self-test, the round trip succeeded)
    1 — auth or network error (Qdrant unreachable, or auth rejected),
        or the --self-test round trip failed
    2 — schema mismatch on an existing collection (operator decides)
    3 — unexpected exception
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

# Must match Pmoves-cipher/src/pmoves/embedding.ts: DENSE_FIELD / BM25_FIELD.
DENSE_FIELD = "dense"
BM25_FIELD = "bm25"
DISTANCE = "Cosine"
SPARSE_MODIFIER = "idf"

_TRUTHY = ("1", "true", "yes", "on")


def _env_flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in _TRUTHY


def _request(method, url, api_key, payload=None, timeout=15.0):
    """Return (status, parsed_body). Raises URLError/OSError on transport failure.

    Qdrant accepts either an `api-key` header or `Authorization: Bearer`.
    embedding.ts sends Bearer; this sends `api-key`. Both are accepted by
    Qdrant 1.16 — verified on B850 — so the two agree in practice.
    """
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url=url, method=method, data=body)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("api-key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


def _wait_for_qdrant(url, api_key, wait_seconds):
    """Poll /collections until Qdrant answers, or the budget runs out.

    A 200 or a 401/403 both prove Qdrant is *up* — auth is judged separately so
    that a wrong key reports as an auth error rather than as a timeout.
    """
    deadline = time.monotonic() + max(wait_seconds, 0)
    attempt = 0
    while True:
        attempt += 1
        try:
            status, _ = _request("GET", url + "/collections", api_key, timeout=5.0)
            if status < 500:
                return True
            print("[provision] Qdrant returned %s (attempt %d) — retrying." % (status, attempt), file=sys.stderr)
        except (urllib.error.URLError, OSError) as exc:
            print("[provision] Qdrant not reachable yet (attempt %d): %s" % (attempt, exc), file=sys.stderr)
        if time.monotonic() >= deadline:
            return False
        time.sleep(2.0)


def _describe(config):
    """Pull (dense_size, dense_distance, sparse_map) out of a collection config.

    Returns dense_size None when there is no vector named `dense` — which also
    covers the single-unnamed-vector layout, where `params.vectors` is a flat
    `{"size": N, "distance": D}` rather than a name->params map. That layout is
    a genuine mismatch for Cipher: `storeVector` upserts named vectors.
    """
    params = config.get("params") or {}
    vectors = params.get("vectors") or {}
    sparse = params.get("sparse_vectors") or {}
    dense = vectors.get(DENSE_FIELD) if isinstance(vectors, dict) else None
    if not isinstance(dense, dict):
        return None, None, sparse
    return dense.get("size"), dense.get("distance"), sparse


def _schema(dim):
    return {
        "vectors": {DENSE_FIELD: {"size": dim, "distance": DISTANCE}},
        "sparse_vectors": {BM25_FIELD: {"modifier": SPARSE_MODIFIER}},
    }


PROBE_POINT_ID = "00000000-0000-4000-8000-0000cafe0001"
PROBE_MEMORY_ID = "__provision_self_test__"
PROBE_AGENT_ID = "__provision__"
PROBE_TEXT = "pmoves cipher provisioning self test hybrid retrieval probe"


def _delete_probe(url, api_key, collection):
    """Delete the probe by payload filter — the same shape deleteVector() uses."""
    try:
        _request(
            "POST",
            "%s/collections/%s/points/delete?wait=true" % (url, collection),
            api_key,
            {"filter": {"must": [{"key": "memoryId", "match": {"value": PROBE_MEMORY_ID}}]}},
            timeout=30.0,
        )
    except (urllib.error.URLError, OSError) as exc:
        print("[self-test] WARN — could not clean up the probe point: %s" % exc, file=sys.stderr)


def _self_test(url, api_key, collection, dim):
    """Round-trip a probe using embedding.ts's exact upsert and query bodies.

    Returns 0 on success, 1 on any failure. Always removes the probe point,
    including on the failure paths — a leftover probe would pollute real
    searches.
    """
    print("[self-test] Round-tripping a probe point through '%s'." % collection)

    # Leftovers from an interrupted earlier run would make the assertions lie.
    _delete_probe(url, api_key, collection)

    # Synthetic unit vector. A real embedding is not required to prove the
    # collection accepts the shape, and no 2560d backend may be reachable.
    dense = [0.0] * dim
    dense[0] = 1.0

    # Mirrors embedding.ts::storeVector — named dense vector plus a bm25
    # document that Qdrant tokenizes server-side.
    upsert = {
        "points": [
            {
                "id": PROBE_POINT_ID,
                "vector": {
                    DENSE_FIELD: dense,
                    BM25_FIELD: {"text": PROBE_TEXT, "model": "qdrant/bm25"},
                },
                "payload": {
                    "memoryId": PROBE_MEMORY_ID,
                    "category": "provisioning",
                    "tags": ["provisioning"],
                    "content": PROBE_TEXT,
                    "agentId": PROBE_AGENT_ID,
                },
            }
        ]
    }
    try:
        status, body = _request(
            "PUT", "%s/collections/%s/points?wait=true" % (url, collection), api_key, upsert, timeout=30.0
        )
    except (urllib.error.URLError, OSError) as exc:
        print("[self-test] FAILED — network error on upsert: %s" % exc, file=sys.stderr)
        return 1
    if status != 200:
        print("[self-test] FAILED — upsert returned %s: %s" % (status, body), file=sys.stderr)
        print(
            "  This is the shape storeVector() sends. A 4xx here means every Cipher\n"
            "  vector write is being rejected and swallowed (embedding.ts only logs it).",
            file=sys.stderr,
        )
        _delete_probe(url, api_key, collection)
        return 1
    print("[self-test]   upsert OK (dense %dd + bm25 document, %d chars)" % (dim, len(PROBE_TEXT)))

    # Mirrors embedding.ts::search — dense prefetch + BM25 prefetch, RRF-fused,
    # scoped by the same payload filter the agentId path builds.
    query = {
        "prefetch": [
            {"query": dense, "using": DENSE_FIELD, "limit": 10,
             "filter": {"must": [{"key": "agentId", "match": {"value": PROBE_AGENT_ID}}]}},
            {"query": {"text": "hybrid retrieval probe", "model": "qdrant/bm25"}, "using": BM25_FIELD, "limit": 10,
             "filter": {"must": [{"key": "agentId", "match": {"value": PROBE_AGENT_ID}}]}},
        ],
        "query": {"fusion": "rrf"},
        "limit": 5,
        "with_payload": True,
    }
    try:
        status, body = _request(
            "POST", "%s/collections/%s/points/query" % (url, collection), api_key, query, timeout=30.0
        )
    except (urllib.error.URLError, OSError) as exc:
        print("[self-test] FAILED — network error on query: %s" % exc, file=sys.stderr)
        _delete_probe(url, api_key, collection)
        return 1
    if status != 200:
        print("[self-test] FAILED — RRF query returned %s: %s" % (status, body), file=sys.stderr)
        _delete_probe(url, api_key, collection)
        return 1

    points = (((body or {}).get("result") or {}).get("points")) or []
    hit = next((pt for pt in points if (pt.get("payload") or {}).get("memoryId") == PROBE_MEMORY_ID), None)
    _delete_probe(url, api_key, collection)

    if hit is None:
        print(
            "[self-test] FAILED — the RRF query did not return the probe. Points: %s" % points,
            file=sys.stderr,
        )
        return 1

    print("[self-test]   hybrid RRF query OK (score=%s)" % hit.get("score"))
    print("[self-test] OK — dense + BM25 + RRF fusion all serve the shape embedding.ts sends.")
    return 0


def main():
    self_test = "--self-test" in sys.argv[1:]
    unknown = [a for a in sys.argv[1:] if a != "--self-test"]
    if unknown:
        print("[provision] Unknown argument(s): %s (only --self-test is accepted)" % unknown, file=sys.stderr)
        return 3

    url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
    api_key = os.environ.get("QDRANT_API_KEY") or os.environ.get("QDRANT__API_KEY") or None
    collection = os.environ.get("QDRANT_CIPHER_COLLECTION", "pmoves_cipher_memory")

    raw_dim = os.environ.get("EMBEDDING_DIM", "2560")
    try:
        dim = int(raw_dim)
    except ValueError:
        print("[provision] EMBEDDING_DIM is not an integer: %r" % raw_dim, file=sys.stderr)
        return 3
    if dim <= 0:
        print("[provision] EMBEDDING_DIM must be positive, got %d" % dim, file=sys.stderr)
        return 3

    try:
        wait_seconds = int(os.environ.get("QDRANT_WAIT_SECONDS", "0"))
    except ValueError:
        wait_seconds = 0

    print(
        "[provision] Target: %s/collections/%s (dense=%s %dd %s, sparse=%s modifier=%s)"
        % (url, collection, DENSE_FIELD, dim, DISTANCE, BM25_FIELD, SPARSE_MODIFIER)
    )

    if not _wait_for_qdrant(url, api_key, wait_seconds):
        print("[provision] Qdrant at %s did not become reachable within %ds." % (url, wait_seconds), file=sys.stderr)
        return 1

    try:
        status, body = _request("GET", "%s/collections/%s" % (url, collection), api_key)
    except (urllib.error.URLError, OSError) as exc:
        print("[provision] Network error probing collection: %s" % exc, file=sys.stderr)
        return 1

    if status in (401, 403):
        print(
            "[provision] Qdrant rejected the credentials (%s). Set QDRANT_API_KEY "
            "(or QDRANT__API_KEY) from env.tier-data." % status,
            file=sys.stderr,
        )
        return 1

    if status == 200:
        config = ((body or {}).get("result") or {}).get("config") or {}
        size, distance, sparse = _describe(config)
        sparse_entry = sparse.get(BM25_FIELD) if isinstance(sparse, dict) else None

        problems = []
        if size is None:
            found = sorted((config.get("params") or {}).get("vectors") or {})
            problems.append("no named dense vector %r (found: %s)" % (DENSE_FIELD, found))
        elif int(size) != dim:
            problems.append("dense size is %s, expected %d" % (size, dim))
        if distance is not None and str(distance).lower() != DISTANCE.lower():
            problems.append("dense distance is %r, expected %r" % (distance, DISTANCE))
        if sparse_entry is None:
            problems.append("no sparse vector %r — hybrid_search cannot work without it" % BM25_FIELD)
        elif str((sparse_entry or {}).get("modifier", "")).lower() != SPARSE_MODIFIER:
            problems.append(
                "sparse %r modifier is %r, expected %r"
                % (BM25_FIELD, (sparse_entry or {}).get("modifier"), SPARSE_MODIFIER)
            )

        if not problems:
            print(
                "[provision] OK — '%s' already matches (dense %sd %s, sparse %s/%s). No-op."
                % (collection, size, distance, BM25_FIELD, SPARSE_MODIFIER)
            )
            if self_test:
                return _self_test(url, api_key, collection, dim)
            return 0

        print("[provision] MISMATCH — '%s' exists but disagrees with embedding.ts:" % collection, file=sys.stderr)
        for problem in problems:
            print("    - %s" % problem, file=sys.stderr)
        print(
            "  Qdrant cannot add a sparse-vector field to a live collection, so reconciling\n"
            "  means dropping it. Operator options:\n"
            "    A) Recreate (DATA LOSS): set QDRANT_RECREATE_ON_MISMATCH=1 and re-run.\n"
            "    B) Point Cipher at a new name: set QDRANT_COLLECTION=<new-name> on cipher-api.\n"
            "    C) Investigate: does EMBEDDING_DIM match the model the embedding backend\n"
            "       actually serves? qwen3-embedding:4b is 2560d; nomic-embed-text is 768d.",
            file=sys.stderr,
        )
        if not _env_flag("QDRANT_RECREATE_ON_MISMATCH"):
            return 2

        print("[provision] QDRANT_RECREATE_ON_MISMATCH set — dropping '%s' (DATA LOSS)." % collection, file=sys.stderr)
        try:
            del_status, del_body = _request("DELETE", "%s/collections/%s" % (url, collection), api_key, timeout=30.0)
        except (urllib.error.URLError, OSError) as exc:
            print("[provision] Network error deleting collection: %s" % exc, file=sys.stderr)
            return 1
        if del_status != 200:
            print("[provision] Delete failed (%s): %s" % (del_status, del_body), file=sys.stderr)
            return 1

    elif status != 404:
        print("[provision] Unexpected status %s probing collection: %s" % (status, body), file=sys.stderr)
        return 1

    # 404, or we just deleted a mismatched collection — create fresh.
    print("[provision] Creating '%s'." % collection)
    try:
        create_status, create_body = _request(
            "PUT", "%s/collections/%s" % (url, collection), api_key, _schema(dim), timeout=30.0
        )
    except (urllib.error.URLError, OSError) as exc:
        print("[provision] Network error creating collection: %s" % exc, file=sys.stderr)
        return 1

    # A racing provisioner (two nodes, or init container + Make target) can win
    # between our 404 and this PUT. Qdrant answers 409 for that; treat it as a
    # no-op rather than a failure and let the verify below judge the result.
    if create_status == 409:
        print("[provision] '%s' was created concurrently — verifying." % collection)
    elif create_status != 200:
        print("[provision] Create failed (%s): %s" % (create_status, create_body), file=sys.stderr)
        return 1

    # Verify rather than trust the 200 — a create that silently drops the sparse
    # field would otherwise report success and fail later, at query time.
    try:
        status, body = _request("GET", "%s/collections/%s" % (url, collection), api_key)
    except (urllib.error.URLError, OSError) as exc:
        print("[provision] Network error verifying collection: %s" % exc, file=sys.stderr)
        return 1
    if status != 200:
        print("[provision] Verification read failed (%s): %s" % (status, body), file=sys.stderr)
        return 1

    size, distance, sparse = _describe(((body or {}).get("result") or {}).get("config") or {})
    if size != dim or BM25_FIELD not in (sparse or {}):
        print(
            "[provision] Verification FAILED — created collection reports dense=%s, sparse=%s. "
            "Expected dense=%d, sparse=['%s']." % (size, sorted(sparse or {}), dim, BM25_FIELD),
            file=sys.stderr,
        )
        return 1

    print(
        "[provision] OK — created '%s' (dense %sd %s + sparse %s/%s)."
        % (collection, size, distance, BM25_FIELD, SPARSE_MODIFIER)
    )
    if self_test:
        return _self_test(url, api_key, collection, dim)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — top-level guard, reports before exiting
        print("[provision] Unexpected exception: %s" % exc, file=sys.stderr)
        raise SystemExit(3) from exc
