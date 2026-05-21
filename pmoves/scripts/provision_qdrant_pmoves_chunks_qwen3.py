#!/usr/bin/env python3
"""Provision the Qdrant collection `pmoves_chunks_qwen3` (2560d, Cosine) — L9.

This closes the `p7.nats.embedding-quality` TAC node in
`pmoves/configs/tac_trees/pinokio-p7.tac.yaml`. The stack standardized on
TensorZero / Qwen3-embedding:4b (PR #1082) which produces **2560-dimensional**
vectors (NOT 3072 — common mistake; see
`pmoves/services/extract-worker/CLAUDE.md`).

Idempotent: if the collection already exists at 2560d Cosine, exits 0 with no
mutation. If it exists at a different dimension, prints a guarded warning and
exits 2 (operator decides recreate-with-data-loss vs use a different name).

Auth: reads `QDRANT_URL` + `QDRANT_API_KEY` from environment. Operator runs
via:

    cd pmoves
    . ./scripts/with-env.sh                       # loads env.shared + env.tier-data
    python3 scripts/provision_qdrant_pmoves_chunks_qwen3.py

…or runs from inside a container that already has the env loaded:

    docker exec -e QDRANT_RECREATE_ON_DIM_MISMATCH=false pmoves-extract-worker-1 \\
        python /app/scripts/provision_qdrant_pmoves_chunks_qwen3.py

Exit codes:
    0 — collection exists at the right dim/distance OR was just created
    1 — auth or network error (QDRANT_URL unreachable, or auth rejected)
    2 — dim mismatch detected (existing collection has wrong dim — operator decides)
    3 — unexpected exception

Reference pattern: `pmoves/services/extract-worker/worker.py::_ensure_qdrant`
"""
from __future__ import annotations

import os
import sys


COLLECTION = "pmoves_chunks_qwen3"
DIM = 2560
DISTANCE = "Cosine"


def main() -> int:
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http.exceptions import UnexpectedResponse
        from qdrant_client.http.models import Distance, VectorParams
    except ImportError:
        print("[provision] qdrant-client not installed. Install via:", file=sys.stderr)
        print("    pip install qdrant-client", file=sys.stderr)
        return 3

    url = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    api_key = os.environ.get("QDRANT_API_KEY", "") or None

    print(f"[provision] Target: {url}/collections/{COLLECTION} (dim={DIM}, distance={DISTANCE})")

    try:
        client = QdrantClient(url=url, api_key=api_key, timeout=30.0)
    except Exception as exc:
        print(f"[provision] Failed to construct QdrantClient: {exc}", file=sys.stderr)
        return 1

    # Probe — does the collection already exist?
    existing_dim = None
    existing_distance = None
    try:
        info = client.get_collection(COLLECTION)
        params = getattr(getattr(info, "config", None), "params", None)
        if isinstance(params, dict):
            vectors = params.get("vectors") or {}
            existing_dim = vectors.get("size") if isinstance(vectors, dict) else None
            existing_distance = vectors.get("distance") if isinstance(vectors, dict) else None
        else:
            vectors = getattr(params, "vectors", None)
            existing_dim = getattr(vectors, "size", None)
            existing_distance = getattr(vectors, "distance", None)
    except UnexpectedResponse as exc:
        if getattr(exc, "status_code", None) == 404:
            existing_dim = None  # collection doesn't exist — fall through to create
        else:
            print(f"[provision] Qdrant API error during probe: {exc}", file=sys.stderr)
            return 1
    except Exception as exc:
        # qdrant-client surfaces 404 in different ways across versions; treat unknown errors as not-found
        # only if the error string contains the canonical 404 phrasing.
        msg = str(exc)
        msg_lower = msg.lower()
        if "404" in msg or "Not found" in msg or "doesn't exist" in msg:
            existing_dim = None
        elif any(p in msg_lower for p in (
            "connection refused", "connection reset", "connection aborted",
            "timeout", "timed out", "unreachable", "could not resolve",
            "name or service not known", "dns", "network is unreachable",
            "no route to host", "transport", "ssl", "tls",
        )):
            # Classify network/transport failures as exit code 1 per documented
            # exit-code contract — operators retry/escalate on 1, debug on 3.
            print(f"[provision] Qdrant network/transport error during probe: {exc}", file=sys.stderr)
            return 1
        else:
            print(f"[provision] Unexpected exception during probe: {exc}", file=sys.stderr)
            return 3

    # Branch on existing state
    if existing_dim is None:
        print(f"[provision] Collection '{COLLECTION}' not found — creating fresh.")
        try:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
            )
        except Exception as exc:
            print(f"[provision] create_collection failed: {exc}", file=sys.stderr)
            return 1
        print(f"[provision] OK — created {COLLECTION} (dim={DIM}, distance={DISTANCE}).")
        return 0

    existing_dim_int = int(existing_dim) if existing_dim is not None else None
    existing_distance_str = str(existing_distance) if existing_distance else "unknown"

    if existing_dim_int == DIM:
        # Dim matches; check distance metric
        if existing_distance_str.lower().endswith("cosine"):
            print(
                f"[provision] OK — collection '{COLLECTION}' already exists at "
                f"dim={existing_dim_int}, distance={existing_distance_str}. No-op."
            )
            return 0
        else:
            print(
                f"[provision] WARN — collection '{COLLECTION}' exists at dim={existing_dim_int} "
                f"but distance is '{existing_distance_str}' (expected Cosine). Operator: "
                "recreate with correct distance OR accept the existing metric.",
                file=sys.stderr,
            )
            return 2

    # Dim mismatch
    print(
        f"[provision] MISMATCH — collection '{COLLECTION}' exists at dim={existing_dim_int}, "
        f"but the expected dim is {DIM}. This is the 3072-vs-2560 trap; see "
        "pmoves/services/extract-worker/CLAUDE.md.",
        file=sys.stderr,
    )
    print(
        "  Operator options:\n"
        "    A) Recreate (DATA LOSS): set QDRANT_RECREATE_ON_DIM_MISMATCH=1 and re-run.\n"
        "    B) Use a separate collection name: set QDRANT_COLLECTION=<new-name> downstream.\n"
        "    C) Investigate: are extract-worker and hi-rag-gateway-v2 actually pinned to "
        "qwen3_embedding_4b_local (2560d) per the standard?",
        file=sys.stderr,
    )

    allow_recreate = os.environ.get("QDRANT_RECREATE_ON_DIM_MISMATCH", "false").lower() in ("1", "true", "yes")
    if allow_recreate:
        print(
            f"[provision] QDRANT_RECREATE_ON_DIM_MISMATCH=true — recreating "
            f"{COLLECTION} at dim={DIM} (DATA LOSS).",
            file=sys.stderr,
        )
        try:
            client.recreate_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
            )
        except Exception as exc:
            print(f"[provision] recreate_collection failed: {exc}", file=sys.stderr)
            return 1
        print(f"[provision] OK — recreated {COLLECTION} at dim={DIM}.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
