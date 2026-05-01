#!/usr/bin/env python3
"""
Content Provenance Gate for the z890 lane.

This service is the first concrete parity worker for the SPARK provenance plan:
it takes raw content, shapes it into a lexicon-weighted payload, attests that
payload with CHIT geometry + a Merkle root, and then gates what is allowed into
HiRAG.

Current shaping logic is intentionally heuristic and lightweight so PMOVES-SPARK
can later replace it with a richer semantic pass without changing the subjects.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)

try:
    from nats.aio.client import Client as NATS
except ImportError:
    NATS = Any  # type: ignore[assignment]

try:
    from pmoves.services.common.events import envelope
except ImportError:
    from services.common.events import envelope


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("content_provenance_gate")

SERVICE_NAME = os.environ.get("SERVICE_NAME", "content-provenance-gate")
NODE_NAME = os.environ.get("NODE_NAME", "z890")
NODE_ROLE = os.environ.get("NODE_ROLE", "z890")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8112"))
QUEUE_GROUP = os.environ.get("CONTENT_PROVENANCE_QUEUE", "content-provenance-gate")
HIRAG_NAMESPACE = os.environ.get("HIRAG_NAMESPACE", "hirag-provenance")

RAW_SUBJECT = "content.raw.v1"
SHAPED_SUBJECT = "content.lexicon.shaped.v1"
ATTESTED_SUBJECT = "content.provenance.attested.v1"
ACCEPTED_SUBJECT = "content.hirag.accepted.v1"
REJECTED_SUBJECT = "content.hirag.rejected.v1"

TOP_K_TERMS = int(os.environ.get("CONTENT_SHAPE_TOP_K", "8"))
NOISE_MAX = float(os.environ.get("CONTENT_NOISE_MAX", "0.58"))
SEMANTIC_DENSITY_MIN = float(os.environ.get("CONTENT_SEMANTIC_DENSITY_MIN", "0.18"))
MIN_ANCHORS = int(os.environ.get("CONTENT_MIN_ANCHORS", "2"))
DISABLE_NATS = os.environ.get("CONTENT_PROVENANCE_DISABLE_NATS", "").lower() in {
    "1",
    "true",
    "yes",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "then",
    "this",
    "to",
    "was",
    "we",
    "with",
}

messages_received = Counter(
    "content_provenance_gate_messages_received_total",
    "Messages received by provenance gate",
    ["subject"],
)
messages_published = Counter(
    "content_provenance_gate_messages_published_total",
    "Messages published by provenance gate",
    ["subject"],
)
messages_failed = Counter(
    "content_provenance_gate_messages_failed_total",
    "Messages that failed processing",
    ["stage", "error_type"],
)
processing_duration = Histogram(
    "content_provenance_gate_processing_duration_seconds",
    "Time spent processing provenance stages",
    ["stage"],
)

_nc: Optional[NATS] = None
_nats_loop_task: Optional[asyncio.Task] = None


def _load_chit_encode_content():
    candidates = [
        Path(__file__).resolve().parents[2] / "tools" / "chit_encode_hook.py",
        Path(__file__).resolve().parents[1] / "tools" / "chit_encode_hook.py",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("content_provenance_chit_encode", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, "chit_encode_content"):
            return module.chit_encode_content
    raise ImportError("Could not locate tools/chit_encode_hook.py for provenance attestation")


chit_encode_content = _load_chit_encode_content()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _nats_loop_task, _nc

    if not DISABLE_NATS and (_nats_loop_task is None or _nats_loop_task.done()):
        logger.info("Starting content provenance NATS loop")
        _nats_loop_task = asyncio.create_task(_nats_resilience_loop())

    yield

    if _nats_loop_task:
        _nats_loop_task.cancel()
        try:
            await _nats_loop_task
        except Exception:
            pass
        _nats_loop_task = None

    if _nc:
        try:
            await _nc.close()
        except Exception:
            pass
        _nc = None

    logger.info("Content provenance gate shut down")


app = FastAPI(title="Content Provenance Gate", version="0.1.0", lifespan=lifespan)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_terms(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    normalized: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = value.strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", text.lower())


def _build_content_id(payload: Dict[str, Any]) -> str:
    explicit = payload.get("content_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    seed = f"{payload.get('source_ref', 'inline')}::{payload.get('text', '')[:160]}"
    return f"content-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _build_shape_id(content_id: str, anchor_terms: List[str]) -> str:
    anchor_seed = ",".join(anchor_terms[:4]) or "empty"
    digest = hashlib.sha256(f"{content_id}::{anchor_seed}".encode("utf-8")).hexdigest()[:16]
    return f"shape-{digest}"


def _semantic_weights(text: str, favorite_words: List[str]) -> List[Dict[str, Any]]:
    tokens = _tokenize(text)
    if not tokens:
        return []

    counts: Dict[str, int] = {}
    for token in tokens:
        if token in STOPWORDS:
            continue
        counts[token] = counts.get(token, 0) + 1

    if not counts:
        return []

    favorite_set = set(favorite_words)
    total = max(1, sum(counts.values()))
    scored: List[Tuple[str, float, bool]] = []
    for term, count in counts.items():
        base = count / total
        bonus = 0.15 if term in favorite_set else 0.0
        richness = min(0.1, len(term) / 100.0)
        score = round(base + bonus + richness, 4)
        scored.append((term, score, term in favorite_set))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return [
        {"term": term, "weight": score, "favorite": favorite}
        for term, score, favorite in scored[:TOP_K_TERMS]
    ]


def _estimate_noise_score(text: str, tokens: List[str], semantic_weights: List[Dict[str, Any]]) -> float:
    if not text.strip():
        return 1.0

    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    repetition = 1.0 - unique_ratio
    dominant_term_ratio = 0.0
    if tokens:
        counts: Dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        dominant_term_ratio = max(counts.values()) / max(1, len(tokens))
    punctuation_ratio = len(re.findall(r"[^a-zA-Z0-9\s]", text)) / max(1, len(text))
    short_ratio = len([token for token in tokens if len(token) <= 2]) / max(1, len(tokens))
    no_signal_penalty = 0.25 if not semantic_weights else 0.0
    score = (
        0.45 * repetition
        + 0.2 * dominant_term_ratio
        + 0.25 * min(1.0, punctuation_ratio * 4.0)
        + 0.15 * short_ratio
        + 0.15 * no_signal_penalty
    )
    return round(min(1.0, max(0.0, score)), 4)


def _estimate_semantic_density(tokens: List[str], anchor_terms: List[str]) -> float:
    if not tokens:
        return 0.0

    content_terms = [token for token in tokens if token not in STOPWORDS]
    unique_content_ratio = len(set(content_terms)) / max(1, len(tokens))
    anchor_ratio = len(anchor_terms) / max(1, TOP_K_TERMS)
    density = 0.65 * unique_content_ratio + 0.35 * anchor_ratio
    return round(min(1.0, max(0.0, density)), 4)


def shape_raw_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    content_id = _build_content_id(payload)
    source_ref = str(payload.get("source_ref") or f"inline:{content_id}")
    favorite_words = _normalize_terms(payload.get("favorite_words"))
    aliases = _normalize_terms(payload.get("aliases"))
    labels = _normalize_terms(payload.get("labels"))
    tokens = _tokenize(text)
    semantic_weights = _semantic_weights(text, favorite_words)
    anchor_terms = [item["term"] for item in semantic_weights[: max(1, MIN_ANCHORS + 1)]]
    noise_score = _estimate_noise_score(text, tokens, semantic_weights)
    semantic_density = _estimate_semantic_density(tokens, anchor_terms)
    shape_id = _build_shape_id(content_id, anchor_terms)

    return {
        "content_id": content_id,
        "text": text,
        "source_ref": source_ref,
        "content_type": str(payload.get("content_type", "text/plain")),
        "shape_id": shape_id,
        "aliases": aliases,
        "favorite_words": favorite_words,
        "anchor_terms": anchor_terms,
        "semantic_weights": semantic_weights,
        "noise_score": noise_score,
        "semantic_density": semantic_density,
        "labels": labels,
        "meta": {
            "worker": SERVICE_NAME,
            "stage": "lexicon_shaped",
            "node_name": NODE_NAME,
            "node_role": NODE_ROLE,
            "lane": str(payload.get("lane", "text")),
            "created_at": _now_iso(),
            "placeholder_for": "pmoves-dgx-spark",
        },
    }


def _merkle_root(leaves: List[str]) -> str:
    level = [hashlib.sha256(leaf.encode("utf-8")).hexdigest() for leaf in leaves if leaf]
    if not level:
        level = [hashlib.sha256(b"empty").hexdigest()]

    while len(level) > 1:
        next_level: List[str] = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            next_level.append(hashlib.sha256(f"{left}{right}".encode("utf-8")).hexdigest())
        level = next_level

    return f"0x{level[0]}"


def attest_shaped_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    metadata = {
        "content_id": payload["content_id"],
        "shape_id": payload["shape_id"],
        "source_ref": payload["source_ref"],
        "anchor_terms": payload.get("anchor_terms", []),
        "favorite_words": payload.get("favorite_words", []),
        "aliases": payload.get("aliases", []),
        "labels": payload.get("labels", []),
    }
    cgp = chit_encode_content(payload["text"], metadata=metadata)
    leaf_inputs = [
        payload["content_id"],
        payload["shape_id"],
        payload["source_ref"],
        json.dumps(payload.get("anchor_terms", []), sort_keys=True),
        json.dumps(payload.get("semantic_weights", []), sort_keys=True),
        cgp.checksum,
    ]
    merkle_root = _merkle_root(leaf_inputs)
    graphiti_mark = f"graphiti:{payload['shape_id']}:{cgp.checksum[:12]}"

    return {
        "content_id": payload["content_id"],
        "text": payload["text"],
        "source_ref": payload["source_ref"],
        "shape_id": payload["shape_id"],
        "graphiti_mark": graphiti_mark,
        "merkle_root": merkle_root,
        "provenance_refs": [
            payload["source_ref"],
            f"shape:{payload['shape_id']}",
            f"checksum:{cgp.checksum}",
        ],
        "anchor_terms": payload.get("anchor_terms", []),
        "favorite_words": payload.get("favorite_words", []),
        "semantic_weights": payload.get("semantic_weights", []),
        "noise_score": payload.get("noise_score", 1.0),
        "semantic_density": payload.get("semantic_density", 0.0),
        "hyperbolic_coords": cgp.payload.get("hyperbolic_coords", {}),
        "spectral_signature": cgp.payload.get("spectral_signature", []),
        "dirichlet_weights": cgp.payload.get("dirichlet_weights", {}),
        "checksum": cgp.checksum,
        "attested_at": _now_iso(),
        "meta": {
            "worker": SERVICE_NAME,
            "stage": "provenance_attested",
            "node_name": NODE_NAME,
            "node_role": NODE_ROLE,
        },
    }


def evaluate_attested_content(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    reasons: List[str] = []
    noise_score = float(payload.get("noise_score", 1.0))
    semantic_density = float(payload.get("semantic_density", 0.0))
    anchor_terms = payload.get("anchor_terms", [])

    if noise_score > NOISE_MAX:
        reasons.append("noise_score_above_threshold")
    if semantic_density < SEMANTIC_DENSITY_MIN:
        reasons.append("semantic_density_below_threshold")
    if len(anchor_terms) < MIN_ANCHORS:
        reasons.append("insufficient_anchor_terms")
    if not payload.get("merkle_root"):
        reasons.append("missing_merkle_root")
    if not payload.get("graphiti_mark"):
        reasons.append("missing_graphiti_mark")

    scorecard = {
        "noise_score": round(noise_score, 4),
        "noise_max": NOISE_MAX,
        "semantic_density": round(semantic_density, 4),
        "semantic_density_min": SEMANTIC_DENSITY_MIN,
        "anchor_count": len(anchor_terms),
        "anchor_min": MIN_ANCHORS,
    }

    base_payload = {
        "content_id": payload["content_id"],
        "text": payload["text"],
        "source_ref": payload["source_ref"],
        "shape_id": payload.get("shape_id"),
        "merkle_root": payload.get("merkle_root"),
        "graphiti_mark": payload.get("graphiti_mark"),
        "provenance_refs": payload.get("provenance_refs", []),
        "favorite_words": payload.get("favorite_words", []),
        "anchor_terms": anchor_terms,
        "semantic_weights": payload.get("semantic_weights", []),
        "scorecard": scorecard,
        "meta": {
            "worker": SERVICE_NAME,
            "stage": "hirag_gate",
            "node_name": NODE_NAME,
            "node_role": NODE_ROLE,
            "evaluated_at": _now_iso(),
        },
    }

    if reasons:
        rejected = dict(base_payload)
        rejected["rejected_reason"] = reasons[0]
        rejected["rejected_reasons"] = reasons
        return REJECTED_SUBJECT, rejected

    accepted = dict(base_payload)
    accepted["kb_namespace"] = HIRAG_NAMESPACE
    accepted["accepted_reason"] = "provenance_gate_passed"
    return ACCEPTED_SUBJECT, accepted


def preview_raw_pipeline(payload: Dict[str, Any]) -> Dict[str, Any]:
    shaped = shape_raw_content(payload)
    attested = attest_shaped_content(shaped)
    decision_subject, decision_payload = evaluate_attested_content(attested)
    return {
        "shaped": shaped,
        "attested": attested,
        "decision_subject": decision_subject,
        "decision": decision_payload,
    }


def _parse_message_body(data: bytes) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    decoded = json.loads(data.decode("utf-8"))
    if isinstance(decoded, dict) and isinstance(decoded.get("payload"), dict):
        return decoded, decoded["payload"]
    if isinstance(decoded, dict):
        return None, decoded
    raise ValueError("Expected JSON object payload")


async def _publish_next(topic: str, payload: Dict[str, Any], upstream: Optional[Dict[str, Any]]) -> None:
    if _nc is None:
        raise RuntimeError("NATS client not connected")

    correlation_id = None
    parent_id = None
    if upstream:
        correlation_id = upstream.get("correlation_id") or upstream.get("id")
        parent_id = upstream.get("id")

    env = envelope(
        topic,
        payload,
        correlation_id=correlation_id,
        parent_id=parent_id,
        source=SERVICE_NAME,
    )
    await _nc.publish(topic, json.dumps(env).encode("utf-8"))
    messages_published.labels(topic).inc()


async def _handle_raw(msg: Any) -> None:
    messages_received.labels(RAW_SUBJECT).inc()
    start_time = time.time()
    try:
        upstream, payload = _parse_message_body(msg.data)
        shaped = shape_raw_content(payload)
        await _publish_next(SHAPED_SUBJECT, shaped, upstream)
        processing_duration.labels("raw").observe(time.time() - start_time)
    except Exception:
        logger.exception("Failed to shape raw content")
        messages_failed.labels("raw", "processing_error").inc()
        processing_duration.labels("raw").observe(time.time() - start_time)


async def _handle_shaped(msg: Any) -> None:
    messages_received.labels(SHAPED_SUBJECT).inc()
    start_time = time.time()
    try:
        upstream, payload = _parse_message_body(msg.data)
        attested = attest_shaped_content(payload)
        await _publish_next(ATTESTED_SUBJECT, attested, upstream)
        processing_duration.labels("shaped").observe(time.time() - start_time)
    except Exception:
        logger.exception("Failed to attest shaped content")
        messages_failed.labels("shaped", "processing_error").inc()
        processing_duration.labels("shaped").observe(time.time() - start_time)


async def _handle_attested(msg: Any) -> None:
    messages_received.labels(ATTESTED_SUBJECT).inc()
    start_time = time.time()
    try:
        upstream, payload = _parse_message_body(msg.data)
        topic, decision = evaluate_attested_content(payload)
        await _publish_next(topic, decision, upstream)
        processing_duration.labels("attested").observe(time.time() - start_time)
    except Exception:
        logger.exception("Failed to gate attested content")
        messages_failed.labels("attested", "processing_error").inc()
        processing_duration.labels("attested").observe(time.time() - start_time)


async def _register_nats_subscriptions(nc: NATS) -> None:
    await nc.subscribe(RAW_SUBJECT, cb=_handle_raw, queue=QUEUE_GROUP)
    await nc.subscribe(SHAPED_SUBJECT, cb=_handle_shaped, queue=QUEUE_GROUP)
    await nc.subscribe(ATTESTED_SUBJECT, cb=_handle_attested, queue=QUEUE_GROUP)
    logger.info(
        "Subscribed to provenance subjects: %s",
        ", ".join([RAW_SUBJECT, SHAPED_SUBJECT, ATTESTED_SUBJECT]),
    )


async def _nats_resilience_loop() -> None:
    global _nc
    backoff = 1.0

    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        def _mark_connection_lost(reason: str) -> None:
            global _nc
            if _nc is nc:
                _nc = None
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning("NATS connection lost: %s", reason)

        async def _disconnected_cb():
            _mark_connection_lost("disconnected")

        async def _closed_cb():
            _mark_connection_lost("closed")

        try:
            await nc.connect(
                servers=[NATS_URL],
                disconnected_cb=_disconnected_cb,
                closed_cb=_closed_cb,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("NATS connection failed: %s", exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue

        _nc = nc
        backoff = 1.0
        logger.info("Connected to NATS at %s", NATS_URL)
        await _register_nats_subscriptions(nc)

        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            try:
                await nc.close()
            except Exception:
                pass
            if _nc is nc:
                _nc = None
            raise

        try:
            await nc.close()
        except Exception:
            pass


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "node_name": NODE_NAME,
        "node_role": NODE_ROLE,
        "nats_enabled": not DISABLE_NATS,
        "nats_connected": _nc is not None,
        "thresholds": {
            "noise_max": NOISE_MAX,
            "semantic_density_min": SEMANTIC_DENSITY_MIN,
            "min_anchors": MIN_ANCHORS,
        },
    }


@app.get("/metrics")
async def metrics():
    from fastapi.responses import Response

    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/preview/raw")
async def preview_raw(payload: Dict[str, Any]):
    return preview_raw_pipeline(payload)


@app.post("/v1/evaluate")
async def evaluate(payload: Dict[str, Any]):
    topic, decision = evaluate_attested_content(payload)
    return {
        "topic": topic,
        "payload": decision,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=HEALTH_PORT)
