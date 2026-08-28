"""Ensure the Qdrant collections used by the gate-measure library exist.

Two collections power dual gate-junction measurement:

* ``gate_semantic_memory`` — historical-success vectors per
  ``(junction_id, layer)``. Read by ``measure_junction()`` to compute the
  semantic score.
* ``gate_drift_dynamo`` — drift capture surface. Written when
  ``syntactic_pass=True`` and ``semantic_score < drift_threshold``. Mineable
  retrospectively to separate errors from innovations.

Vector dimension defaults to 2560d (Qwen3-Embedding-4B). Override with
``GATE_MEASURE_VECTOR_DIM`` if a different embedding model is in use.

Run in idempotent fashion — collections that already exist with the right
dimension are left alone; mismatched dimensions are reported but not
auto-recreated (avoids accidental data loss; mirrors the Hi-RAG v2
``QDRANT_RECREATE_ON_DIM_MISMATCH=false`` invariant).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

import httpx

logger = logging.getLogger("bootstrap_drift_dynamo")

DEFAULT_QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
DEFAULT_VECTOR_DIM = int(os.environ.get("GATE_MEASURE_VECTOR_DIM", "2560"))

GATE_SEMANTIC_MEMORY = "gate_semantic_memory"
GATE_DRIFT_DYNAMO = "gate_drift_dynamo"

PAYLOAD_INDEXES = [
    ("junction_id", "keyword"),
    ("layer", "keyword"),
    ("upstream_intent_id", "keyword"),
    ("phrase_id", "keyword"),
]


def _collection_url(base: str, name: str) -> str:
    return f"{base.rstrip('/')}/collections/{name}"


def _ensure_collection(client: httpx.Client, base: str, name: str, dim: int) -> str:
    url = _collection_url(base, name)
    resp = client.get(url)
    if resp.status_code == 200:
        cfg = resp.json().get("result", {})
        existing_dim = (
            cfg.get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size")
        )
        if existing_dim == dim:
            return "exists"
        return f"dim_mismatch (existing={existing_dim}, requested={dim})"

    body: dict[str, Any] = {
        "vectors": {"size": dim, "distance": "Cosine"},
        "optimizers_config": {"default_segment_number": 2},
    }
    resp = client.put(url, json=body)
    resp.raise_for_status()
    return "created"


def _ensure_payload_indexes(client: httpx.Client, base: str, name: str) -> list[str]:
    """Create payload indexes for filterable fields. Idempotent."""
    statuses: list[str] = []
    for field, schema in PAYLOAD_INDEXES:
        url = f"{_collection_url(base, name)}/index"
        resp = client.put(url, json={"field_name": field, "field_schema": schema})
        if resp.status_code == 200:
            statuses.append(f"{field}=ok")
        elif resp.status_code in (400, 409):
            statuses.append(f"{field}=already_exists")
        else:
            statuses.append(f"{field}=err({resp.status_code})")
    return statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    parser.add_argument("--dim", type=int, default=DEFAULT_VECTOR_DIM)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on dimension mismatch instead of warning",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    out: dict[str, Any] = {"qdrant_url": args.qdrant_url, "dim": args.dim, "collections": {}}
    exit_code = 0

    with httpx.Client(timeout=10.0) as client:
        for collection in (GATE_SEMANTIC_MEMORY, GATE_DRIFT_DYNAMO):
            try:
                status = _ensure_collection(client, args.qdrant_url, collection, args.dim)
            except httpx.HTTPError as exc:
                status = f"error: {exc}"
                exit_code = 1
            indexes: list[str] = []
            if status in ("exists", "created"):
                try:
                    indexes = _ensure_payload_indexes(client, args.qdrant_url, collection)
                except httpx.HTTPError as exc:
                    indexes = [f"error: {exc}"]
                    exit_code = 1
            if status.startswith("dim_mismatch") and args.strict:
                exit_code = 2
            out["collections"][collection] = {"status": status, "indexes": indexes}
            logger.info("%s -> %s (%s)", collection, status, ", ".join(indexes) or "no-indexes")

    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
