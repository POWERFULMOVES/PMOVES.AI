"""Dual gate-junction measurement library.

Every gate junction in the PMOVES data plane emits two complementary measures:

1. Syntactic — JSON schema / NATS subject / RLS / JWT-claim validation.
   Cheap, deterministic, fail-fast.
2. Semantic — cosine similarity of the payload embedding against the
   historical-success cluster for (junction_id, layer) in Qdrant.
   Probabilistic, fail-soft.

Drift is the offset between the two: when syntactic_pass=True but
semantic_score < threshold, the payload is well-formed but its meaning
has diverged from the cluster of past successful traffic at this
junction. Drift is captured (not just alerted) into Qdrant collection
``gate_drift_dynamo`` so retrospective analysis can mine errors and
innovations apart — both look identical at the moment they happen.

Sampling: semantic measurement adds an embedding call per measurement,
so callers can pass ``sample_rate`` for hot paths. Drift events always
escape sampling (full sample on detected drift).

Returns ``JunctionMeasurement`` with the v2 signature fields populated;
callers fold this into their CHIT signature emit.
"""

from __future__ import annotations

import logging
import os
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from jsonschema import Draft202012Validator, ValidationError

logger = logging.getLogger(__name__)

DEFAULT_DRIFT_THRESHOLD = 0.3
DEFAULT_SAMPLE_RATE_HOT = 0.10
DEFAULT_SAMPLE_RATE_COLD = 1.0
DRIFT_DYNAMO_COLLECTION = "gate_drift_dynamo"
GATE_SEMANTIC_MEMORY_COLLECTION = "gate_semantic_memory"
TENSORZERO_BASE = os.environ.get("TENSORZERO_BASE_URL", "http://localhost:3030")
QDRANT_BASE = os.environ.get("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = os.environ.get(
    "GATE_MEASURE_EMBEDDING_MODEL",
    "tensorzero::embedding_model_name::qwen3_embedding_4b_local",
)
DRIFT_NATS_SUBJECT = "gate.drift.detected.v1"


@dataclass(frozen=True)
class JunctionMeasurement:
    """Result of measuring one inbound payload at a gate junction."""

    junction_id: str
    layer: str
    syntactic_pass: bool
    semantic_score: float
    drift_flag: bool
    upstream_intent_id: str | None
    phrase_anchor: list[str]
    measurement_id: str
    timestamp: str
    syntactic_errors: list[str] = field(default_factory=list)
    sampled: bool = True

    def to_signature_fields(self) -> dict[str, Any]:
        """Project onto the agent-graphiti signature.v2 field set."""
        return {
            "junction_id": self.junction_id,
            "layer": self.layer,
            "syntactic_pass": self.syntactic_pass,
            "semantic_score": self.semantic_score,
            "drift_flag": self.drift_flag,
            "upstream_intent_id": self.upstream_intent_id,
            "phrase_anchor": list(self.phrase_anchor),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_syntactic(payload: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, list[str]]:
    validator = Draft202012Validator(schema)
    errors: list[ValidationError] = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    if not errors:
        return True, []
    return False, [f"{'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}" for err in errors]


def _embed(text: str, *, client: httpx.Client | None = None, timeout: float = 5.0) -> list[float] | None:
    """Embed text via TensorZero. Returns None on failure (semantic measure is fail-soft)."""
    body = {"model": EMBEDDING_MODEL, "input": text}
    url = f"{TENSORZERO_BASE.rstrip('/')}/openai/v1/embeddings"
    try:
        if client is None:
            with httpx.Client(timeout=timeout) as c:
                resp = c.post(url, json=body)
        else:
            resp = client.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.warning("gate_measure embedding call failed: %s", exc)
        return None


def _qdrant_search(
    collection: str,
    vector: list[float],
    junction_id: str,
    layer: str,
    *,
    top_k: int = 5,
    client: httpx.Client | None = None,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Search Qdrant for nearest historical-success vectors at this junction+layer."""
    url = f"{QDRANT_BASE.rstrip('/')}/collections/{collection}/points/search"
    body = {
        "vector": vector,
        "limit": top_k,
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "junction_id", "match": {"value": junction_id}},
                {"key": "layer", "match": {"value": layer}},
            ]
        },
    }
    try:
        if client is None:
            with httpx.Client(timeout=timeout) as c:
                resp = c.post(url, json=body)
        else:
            resp = client.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("result", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("gate_measure Qdrant search failed: %s", exc)
        return []


def _qdrant_upsert_drift(
    measurement: JunctionMeasurement,
    payload: dict[str, Any],
    vector: list[float],
    *,
    client: httpx.Client | None = None,
    timeout: float = 5.0,
) -> None:
    """Capture drift into the gate_drift_dynamo collection. Fail-soft."""
    url = f"{QDRANT_BASE.rstrip('/')}/collections/{DRIFT_DYNAMO_COLLECTION}/points"
    body = {
        "points": [
            {
                "id": measurement.measurement_id,
                "vector": vector,
                "payload": {
                    "junction_id": measurement.junction_id,
                    "layer": measurement.layer,
                    "syntactic_pass": measurement.syntactic_pass,
                    "semantic_score": measurement.semantic_score,
                    "upstream_intent_id": measurement.upstream_intent_id,
                    "timestamp": measurement.timestamp,
                    "payload_summary": _summarize_payload(payload),
                },
            }
        ]
    }
    try:
        if client is None:
            with httpx.Client(timeout=timeout) as c:
                resp = c.put(url, json=body)
        else:
            resp = client.put(url, json=body, timeout=timeout)
        resp.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("gate_measure drift-dynamo upsert failed: %s", exc)


def _summarize_payload(payload: dict[str, Any], *, max_chars: int = 512) -> str:
    """Best-effort string summary suitable for embedding and Qdrant payload."""
    parts: list[str] = []
    for key in ("subject", "summary", "intent", "command", "action", "type", "event"):
        if key in payload and isinstance(payload[key], str):
            parts.append(f"{key}={payload[key]}")
    if not parts:
        text = str(payload)
    else:
        text = " | ".join(parts)
    return text[:max_chars]


def _resolve_phrase_anchors(neighbors: Iterable[dict[str, Any]], min_score: float) -> list[str]:
    """Extract phrase_id values from canonical phrase neighbors above ``min_score``."""
    out: list[str] = []
    for n in neighbors:
        if (n.get("score") or 0.0) < min_score:
            continue
        payload = n.get("payload") or {}
        phrase_id = payload.get("phrase_id")
        if phrase_id and phrase_id not in out:
            out.append(phrase_id)
    return out


def measure_junction(
    *,
    junction_id: str,
    layer: str,
    payload: dict[str, Any],
    schema: dict[str, Any] | None = None,
    upstream_intent_id: str | None = None,
    sample_rate: float | None = None,
    drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    phrase_match_threshold: float = 0.7,
    capture_drift: bool = True,
    http_client: httpx.Client | None = None,
) -> JunctionMeasurement:
    """Measure one payload at a gate junction.

    Parameters
    ----------
    junction_id, layer
        Identify the junction in the polarity taxonomy. layer is one of
        ``intent`` / ``execution`` / ``arbiter`` / ``observation``.
    payload
        The inbound message payload (NATS message, HTTP body, etc.).
    schema
        Optional JSON schema for syntactic validation. If omitted, the
        syntactic measure passes by default (caller is asserting upstream
        validation has already happened).
    upstream_intent_id
        For execution/observation layers, the UUID of the authorizing
        archon.command.issue.v1. Polarity arbiter rejects when missing.
    sample_rate
        Probability of running the (costly) semantic measure. ``None``
        defaults to 100% in cold paths and 10% in hot paths — caller
        decides via env or service config.
    drift_threshold
        semantic_score below this triggers ``drift_flag=True`` and
        gate.drift.detected.v1 emission.
    phrase_match_threshold
        Cosine score above which a phrase neighbor counts as an anchor.
    capture_drift
        If True (default), drift events are upserted to ``gate_drift_dynamo``
        even when sampling skipped the routine measurement.
    """

    measurement_id = str(uuid.uuid4())
    ts = _now_iso()

    if schema is not None:
        syntactic_pass, syntactic_errors = _validate_syntactic(payload, schema)
    else:
        syntactic_pass, syntactic_errors = True, []

    rate = DEFAULT_SAMPLE_RATE_COLD if sample_rate is None else sample_rate
    sampled = random.random() < rate

    semantic_score = 0.0
    phrase_anchors: list[str] = []
    vector: list[float] | None = None

    if sampled:
        text = _summarize_payload(payload)
        vector = _embed(text, client=http_client)
        if vector is not None:
            neighbors = _qdrant_search(
                GATE_SEMANTIC_MEMORY_COLLECTION,
                vector,
                junction_id,
                layer,
                client=http_client,
            )
            if neighbors:
                semantic_score = max((n.get("score") or 0.0) for n in neighbors)
            phrase_anchors = _resolve_phrase_anchors(neighbors, phrase_match_threshold)

    drift_flag = bool(syntactic_pass and sampled and vector is not None and semantic_score < drift_threshold)

    measurement = JunctionMeasurement(
        junction_id=junction_id,
        layer=layer,
        syntactic_pass=syntactic_pass,
        semantic_score=semantic_score,
        drift_flag=drift_flag,
        upstream_intent_id=upstream_intent_id,
        phrase_anchor=phrase_anchors,
        measurement_id=measurement_id,
        timestamp=ts,
        syntactic_errors=syntactic_errors,
        sampled=sampled,
    )

    if drift_flag and capture_drift and vector is not None:
        _qdrant_upsert_drift(measurement, payload, vector, client=http_client)

    return measurement


def measurement_to_drift_event(measurement: JunctionMeasurement, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a NATS message body for ``gate.drift.detected.v1``."""
    body = asdict(measurement)
    body["payload_summary"] = _summarize_payload(payload)
    return body


__all__ = [
    "DEFAULT_DRIFT_THRESHOLD",
    "DEFAULT_SAMPLE_RATE_COLD",
    "DEFAULT_SAMPLE_RATE_HOT",
    "DRIFT_DYNAMO_COLLECTION",
    "DRIFT_NATS_SUBJECT",
    "GATE_SEMANTIC_MEMORY_COLLECTION",
    "JunctionMeasurement",
    "measure_junction",
    "measurement_to_drift_event",
]
