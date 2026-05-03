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
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
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
NATS_URL = os.environ["NATS_URL"]
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


_chit_encode_content = None
CHIT_ENCODE_HOOK_PATH = os.environ.get("CHIT_ENCODE_HOOK_PATH", "")


def _load_chit_encode_content():
    """
    Load and cache the `chit_encode_content` callable from a single pinned hook directory.
    
    If `CHIT_ENCODE_HOOK_PATH` is empty or unset, returns `None`. If the hook directory exists, attempts to load `chit_encode_hook.py` and retrieve the `chit_encode_content` attribute; if successful, caches and returns that callable. Subsequent calls return the cached callable.
    
    Returns:
        The `chit_encode_content` callable if available, or `None` when `CHIT_ENCODE_HOOK_PATH` is not set.
    
    Raises:
        ImportError: If `CHIT_ENCODE_HOOK_PATH` is set but `chit_encode_hook.py` is missing, the import spec cannot be created, or the module does not expose a `chit_encode_content` callable.
    """
    global _chit_encode_content
    if _chit_encode_content is not None:
        return _chit_encode_content
    if not CHIT_ENCODE_HOOK_PATH:
        return None
    hook_file = Path(CHIT_ENCODE_HOOK_PATH) / "chit_encode_hook.py"
    if not hook_file.is_file():
        raise ImportError(
            f"CHIT_ENCODE_HOOK_PATH set but {hook_file} does not exist"
        )
    spec = importlib.util.spec_from_file_location(
        "chit_encode_hook", hook_file
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create module spec for {hook_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "chit_encode_content"):
        _chit_encode_content = module.chit_encode_content
        return _chit_encode_content
    raise ImportError(
        f"{hook_file} exists but has no 'chit_encode_content' callable"
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the FastAPI application lifespan by starting the NATS resilience loop on startup and ensuring orderly shutdown of NATS-related background work.
    
    On startup (when NATS is enabled) this lifespan context starts a background resilience task that maintains the NATS connection. On shutdown it cancels and awaits the background task (suppressing exceptions), closes the NATS client if present (suppressing exceptions), and clears module-level NATS state.
    """
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
GATE_API_KEY = os.environ.get("GATE_API_KEY", "")
_bearer_scheme = HTTPBearer(auto_error=False)

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, lambda r, e: HTTPException(429, "Rate limit exceeded"))

_MAX_BODY_BYTES = 512 * 1024  # 512 KB


async def _require_api_key(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> None:
    """
    Validate the request's bearer token against the configured gateway API key or allow requests when no key is configured.
    
    If GATE_API_KEY is unset or empty, the function permits all requests. If a key is configured and the provided credentials are missing or do not match, the function raises an HTTPException with status code 401 and detail "Invalid or missing API key".
    
    Raises:
        HTTPException: status code 401 when the API key is required but missing or incorrect.
    """
    if not GATE_API_KEY:
        return  # no key configured = open (dev mode, protect with network policy)
    if credentials is None or credentials.credentials != GATE_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class PreviewRawRequest(BaseModel):
    text: str = Field(default="", max_length=10000)
    source_ref: Optional[str] = Field(default=None, max_length=500)
    content_type: Optional[str] = Field(default="text/plain", max_length=100)
    favorite_words: Optional[List[str]] = Field(default=None, max_length=100)
    aliases: Optional[List[str]] = Field(default=None, max_length=100)
    labels: Optional[List[str]] = Field(default=None, max_length=100)
    lane: Optional[str] = Field(default="text", max_length=50)
    content_id: Optional[str] = Field(default=None, max_length=200)
    model_config = {"extra": "ignore"}


class EvaluateRequest(BaseModel):
    content_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=10000)
    source_ref: Optional[str] = Field(default=None, max_length=500)
    shape_id: Optional[str] = Field(default=None, max_length=200)
    merkle_root: Optional[str] = Field(default=None, max_length=200)
    graphiti_mark: Optional[str] = Field(default=None, max_length=500)
    provenance_refs: Optional[List[str]] = Field(default=None, max_length=50)
    favorite_words: Optional[List[str]] = Field(default=None, max_length=100)
    anchor_terms: Optional[List[str]] = Field(default=None, max_length=100)
    semantic_weights: Optional[List[Dict[str, Any]]] = Field(default=None)
    noise_score: Optional[float] = Field(default=None)
    semantic_density: Optional[float] = Field(default=None)
    hyperbolic_coords: Optional[Dict[str, Any]] = Field(default=None)
    spectral_signature: Optional[List[Any]] = Field(default=None)
    dirichlet_weights: Optional[Dict[str, Any]] = Field(default=None)
    checksum: Optional[str] = Field(default=None, max_length=200)
    model_config = {"extra": "ignore"}


def _now_iso() -> str:
    """
    Return the current UTC time as an ISO 8601 string with a trailing 'Z'.
    
    Returns:
        iso_timestamp (str): Current UTC timestamp in ISO 8601 format, e.g. "2026-05-03T12:34:56.789012Z".
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_terms(values: Any) -> List[str]:
    """
    Normalize a list of term strings by trimming, lowercasing, removing non-strings and empties, and preserving first-occurrence order without duplicates.
    
    Parameters:
        values (Any): Input expected to be a list of items; non-list inputs produce an empty list.
    
    Returns:
        List[str]: A list of normalized terms (lowercased, trimmed) in their original first-seen order with duplicates removed.
    """
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
    """
    Extracts lowercase tokens from the input text using a specific token pattern.
    
    Parameters:
        text: Input string to tokenize; it is lowercased before token extraction.
    
    Returns:
        tokens: List of tokens matching the pattern: start with an ASCII letter followed by one or more ASCII letters, digits, underscore, or hyphen (minimum token length 2).
    """
    return re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", text.lower())


def _build_content_id(payload: Dict[str, Any]) -> str:
    """
    Build a deterministic content identifier for a payload.
    
    Parameters:
        payload (Dict[str, Any]): Input dictionary possibly containing `content_id`, `source_ref`, and `text`.
    
    Returns:
        str: The content identifier. If `payload["content_id"]` is a non-empty string, that trimmed value is returned.
             Otherwise returns `content-<hex>` where `<hex>` is the first 16 hex chars of SHA-256 over
             "<source_ref or 'inline'>::" + first 160 characters of `text`.
    """
    explicit = payload.get("content_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    seed = f"{payload.get('source_ref', 'inline')}::{payload.get('text', '')[:160]}"
    return f"content-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _build_shape_id(content_id: str, anchor_terms: List[str]) -> str:
    """
    Constructs a deterministic shape identifier from a content ID and anchor terms.
    
    Parameters:
        content_id (str): The canonical content identifier used as the primary seed.
        anchor_terms (List[str]): Anchor terms; up to the first four are incorporated into the seed.
    
    Returns:
        str: A shape identifier in the form `shape-<16hex>` derived from the SHA-256 digest of `content_id::anchor_seed`.
    """
    anchor_seed = ",".join(anchor_terms[:4]) or "empty"
    digest = hashlib.sha256(f"{content_id}::{anchor_seed}".encode("utf-8")).hexdigest()[:16]
    return f"shape-{digest}"


def _semantic_weights(text: str, favorite_words: List[str]) -> List[Dict[str, Any]]:
    """
    Compute a ranked list of semantic terms extracted from `text`, giving extra weight to `favorite_words`.
    
    Parameters:
        text (str): Input text to analyze; tokens are extracted and stopwords ignored.
        favorite_words (List[str]): Terms that receive a fixed weight bonus when present.
    
    Returns:
        List[Dict[str, Any]]: Up to `TOP_K_TERMS` entries sorted by decreasing weight. Each entry contains:
            - `term` (str): the token string,
            - `weight` (float): the computed weight (normalized frequency plus favorite and length components, rounded to 4 decimals),
            - `favorite` (bool): `true` if the term was in `favorite_words`, `false` otherwise.
    """
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
    """
    Estimate a noise score for a text based on token repetition, punctuation, short tokens, and semantic signal.
    
    Parameters:
        text (str): Original text being evaluated.
        tokens (List[str]): Tokenized, lowercased terms extracted from `text`.
        semantic_weights (List[Dict[str, Any]]): Ranked semantic term weights; empty list indicates no semantic signal.
    
    Returns:
        noise_score (float): A value between 0.0 and 1.0 where higher values indicate greater estimated noise; rounded to 4 decimals.
    """
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
    """
    Estimate the semantic density of tokenized content relative to provided anchor terms.
    
    Parameters:
        tokens (List[str]): Tokenized words from the content; stopwords will be excluded from the uniqueness measure.
        anchor_terms (List[str]): Anchor terms extracted from the content used to boost density.
    
    Returns:
        float: A value between 0.0 and 1.0 (rounded to four decimals) representing semantic density, where higher values indicate more unique, anchor-rich content.
    """
    if not tokens:
        return 0.0

    content_terms = [token for token in tokens if token not in STOPWORDS]
    unique_content_ratio = len(set(content_terms)) / max(1, len(tokens))
    anchor_ratio = len(anchor_terms) / max(1, TOP_K_TERMS)
    density = 0.65 * unique_content_ratio + 0.35 * anchor_ratio
    return round(min(1.0, max(0.0, density)), 4)


def shape_raw_content(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a lexicon-weighted "shaped" representation of raw content suitable for attestation and gating.
    
    Parameters:
        payload (dict): Input content envelope. Expected keys include `text` (raw content),
            optional `content_id`, `source_ref`, `content_type`, `favorite_words`, `aliases`,
            `labels`, and `lane`. Extra keys are ignored.
    
    Returns:
        dict: Shaped content containing:
            - content_id (str): Deterministic identifier for the content.
            - text (str): Trimmed input text.
            - source_ref (str): Source reference or generated inline reference.
            - content_type (str): Content MIME type (defaults to "text/plain").
            - shape_id (str): Deterministic identifier for this shaped view.
            - aliases (list[str]): Normalized alias terms.
            - favorite_words (list[str]): Normalized favorite terms.
            - anchor_terms (list[str]): Selected anchor terms used for shaping.
            - semantic_weights (list[dict]): Top-K terms with weights and favorite flags.
            - noise_score (float): Heuristic noise estimate in range [0.0, 1.0].
            - semantic_density (float): Heuristic semantic density in range [0.0, 1.0].
            - labels (list[str]): Normalized label terms.
            - meta (dict): Metadata about the shaping operation (worker, stage, node, lane, timestamps).
    """
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
    """
    Compute a deterministic Merkle root from a list of string leaves.
    
    Each non-empty leaf is SHA-256 hashed (hex). If no non-empty leaves are provided, the hash of the literal bytes b"empty" is used as the sole leaf. Hashes are then combined pairwise (duplicating the last hash when an odd count occurs) and re-hashed until a single root hash remains.
    
    Parameters:
        leaves (List[str]): Iterable of leaf strings; empty or falsy strings are ignored.
    
    Returns:
        str: The Merkle root as a hex digest prefixed with "0x".
    """
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
    """
    Generate an attested payload for a shaped content item by encoding content with the configured CHIT hook, computing a Merkle root over canonical leaves, and producing provenance fields.
    
    Parameters:
        payload (Dict[str, Any]): Shaped content dictionary. Required keys: `"content_id"`, `"shape_id"`, `"source_ref"`, and `"text"`. Optional keys that will be included if present: `"anchor_terms"`, `"favorite_words"`, `"aliases"`, `"labels"`, `"semantic_weights"`, `"noise_score"`, `"semantic_density"`.
    
    Returns:
        Dict[str, Any]: Attested content dictionary containing:
          - identifiers: `content_id`, `shape_id`, `source_ref`
          - attestation fields: `graphiti_mark`, `merkle_root`, `provenance_refs`, `checksum`, `attested_at`
          - carried lexicon and score fields: `anchor_terms`, `favorite_words`, `semantic_weights`, `noise_score`, `semantic_density`
          - encoded payload fields extracted from the CHIT result: `hyperbolic_coords`, `spectral_signature`, `dirichlet_weights`
          - `meta` block with worker/stage/node identity.
    
    Raises:
        RuntimeError: If the CHIT encode hook is not available (CHIT_ENCODE_HOOK_PATH unset or loader failed).
    """
    metadata = {
        "content_id": payload["content_id"],
        "shape_id": payload["shape_id"],
        "source_ref": payload["source_ref"],
        "anchor_terms": payload.get("anchor_terms", []),
        "favorite_words": payload.get("favorite_words", []),
        "aliases": payload.get("aliases", []),
        "labels": payload.get("labels", []),
    }
    chit_fn = _load_chit_encode_content()
    if chit_fn is None:
        raise RuntimeError(
            "CHIT encode hook not available — set CHIT_ENCODE_HOOK_PATH to enable attestation"
        )
    cgp = chit_fn(payload["text"], metadata=metadata)
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
    """
    Evaluate an attested content payload against configured thresholds and produce an accept-or-reject decision topic and payload.
    
    Checks the payload's noise score, semantic density, anchor term count, and presence of attestation fields, then builds a scorecard and a decision envelope describing the outcome.
    
    Parameters:
        payload (dict): Attested content dictionary. Expected keys include `content_id`, `text`, `source_ref` and may include `shape_id`, `merkle_root`, `graphiti_mark`, `provenance_refs`, `favorite_words`, `anchor_terms`, `semantic_weights`, `noise_score`, and `semantic_density`.
    
    Returns:
        tuple[str, dict]: A two-element tuple where the first element is the NATS subject topic (`ACCEPTED_SUBJECT` or `REJECTED_SUBJECT`) and the second is the decision payload. The decision payload always contains identifiers, carried term lists, a `scorecard`, and `meta` with evaluation timestamp; on rejection it includes `rejected_reason` and `rejected_reasons`, and on acceptance it includes `kb_namespace` and `accepted_reason`.
    """
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
    """
    Run the full preview pipeline for a raw content payload: shape the text, produce an attested record, and evaluate the gating decision.
    
    Parameters:
        payload (Dict[str, Any]): Raw input following the preview schema (e.g., fields from PreviewRawRequest such as `text`, optional `source_ref`, `favorite_words`, etc.).
    
    Returns:
        Dict[str, Any]: A dictionary with:
            - "shaped": The shaped content payload produced by shape_raw_content.
            - "attested": The attested content payload produced by attest_shaped_content.
            - "decision_subject": The NATS subject/topic chosen by evaluate_attested_content (accepted or rejected subject).
            - "decision": The decision payload returned by evaluate_attested_content (the gated/accepted or rejected message).
    """
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
    """
    Parse raw message bytes into an upstream envelope and a payload dictionary.
    
    Parameters:
        data (bytes): Raw UTF-8 JSON message body.
    
    Returns:
        tuple: (upstream, payload) where `upstream` is the decoded envelope dict when the top-level object contains a `payload` dict (otherwise `None`), and `payload` is the decoded payload dict to be processed.
    
    Raises:
        ValueError: if the body size exceeds the configured limit or if the decoded JSON is not an object.
    """
    if len(data) > _MAX_BODY_BYTES:
        raise ValueError(f"Request body exceeds {_MAX_BODY_BYTES // 1024} KB limit")
    decoded = json.loads(data.decode("utf-8"))
    if isinstance(decoded, dict) and isinstance(decoded.get("payload"), dict):
        return decoded, decoded["payload"]
    if isinstance(decoded, dict):
        return None, decoded
    raise ValueError("Expected JSON object payload")


async def _publish_next(topic: str, payload: Dict[str, Any], upstream: Optional[Dict[str, Any]]) -> None:
    """
    Publish a payload to a NATS subject, wrapping it in an envelope and recording the publish metric.
    
    If `upstream` is provided, `correlation_id` is taken from `upstream["correlation_id"]` or `upstream["id"]`, and `parent_id` is taken from `upstream["id"]`; these are included in the envelope along with the service source. The function publishes the JSON-encoded envelope to `topic` and increments the published-messages metric.
    
    Parameters:
        topic (str): NATS subject to publish to.
        payload (Dict[str, Any]): Message payload to include in the envelope.
        upstream (Optional[Dict[str, Any]]): Optional upstream envelope or metadata used to propagate `correlation_id` and `parent_id`.
    
    Raises:
        RuntimeError: If the NATS client is not connected.
    """
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
    """
    Handle an incoming raw NATS message by parsing the payload, shaping the raw content, and publishing the shaped result while recording metrics.
    
    Parameters:
        msg (Any): NATS message object whose `data` contains the JSON payload to process. On success this handler publishes the shaped payload to the shaped subject, increments the received/published metrics, and records processing duration. On failure it logs the exception, increments the failure metric for the raw stage, and records the processing duration.
    """
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
    """
    Process a received "shaped" NATS message by attesting its payload and publishing the resulting attested content.
    
    Parameters:
        msg (Any): NATS message-like object whose `data` attribute contains the serialized message body consumed by the service.
    
    Notes:
        - Publishes the attested payload to the configured `ATTESTED_SUBJECT`.
        - Updates Prometheus metrics for messages received, processing duration, and failures.
        - On exception, logs the error and increments the failure metric.
    """
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
    """
    Handle incoming attested-stage NATS messages by evaluating gating rules and publishing the resulting decision.
    
    Parses the incoming message body from msg.data, runs the gating evaluation on the attested payload, and publishes the returned decision to the appropriate subject. Updates Prometheus metrics for messages received, processing duration, and failures; on error, logs the exception and increments the attested-stage failure counter.
    
    Parameters:
        msg (Any): NATS message-like object whose `data` attribute contains the UTF-8 JSON payload to process.
    """
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
    """
    Register NATS subscriptions for the content pipeline subjects and log the registration.
    
    Subscribes to the raw, shaped, and attested subject channels using the configured queue group and associated message handlers; awaits each subscription call before returning and emits an info log listing the subscribed subjects.
    """
    await nc.subscribe(RAW_SUBJECT, cb=_handle_raw, queue=QUEUE_GROUP)
    await nc.subscribe(SHAPED_SUBJECT, cb=_handle_shaped, queue=QUEUE_GROUP)
    await nc.subscribe(ATTESTED_SUBJECT, cb=_handle_attested, queue=QUEUE_GROUP)
    logger.info(
        "Subscribed to provenance subjects: %s",
        ", ".join([RAW_SUBJECT, SHAPED_SUBJECT, ATTESTED_SUBJECT]),
    )


async def _nats_resilience_loop() -> None:
    """
    Maintain a resilient background NATS connection loop that connects, registers subscriptions, and reconnects on failures.
    
    This coroutine runs indefinitely: it attempts to connect to the configured NATS server, sets the module-level `_nc` client while connected, registers the service subscriptions, and waits for an internal disconnect event. On connection failures it backs off and retries; on unexpected disconnection it clears `_nc`, closes the client, and restarts the connect loop. If cancelled, it closes the active NATS client (if any) and re-raises the cancellation.
    """
    global _nc
    backoff = 1.0

    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        def _mark_connection_lost(reason: str) -> None:
            """
            Mark the current NATS connection as lost and signal a local disconnect.
            
            If the module-level `_nc` still refers to the client instance captured by the surrounding callback, clear `_nc`. Set the local `disconnect_event` (if not already set) and log a warning with `reason`.
            
            Parameters:
                reason (str): Human-readable explanation of why the connection was lost; included in the warning log.
            """
            global _nc
            if _nc is nc:
                _nc = None
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning("NATS connection lost: %s", reason)

        async def _disconnected_cb():
            """
            Callback invoked when the NATS client is disconnected to mark the service connection as lost.
            """
            _mark_connection_lost("disconnected")

        async def _closed_cb():
            """
            Callback invoked when the NATS client connection is closed to mark the connection as lost.
            
            Used as a lifecycle callback to signal the local connection state change so the resilience loop and subscription management can react.
            """
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
    """
    Return a service health and configuration summary.
    
    Returns:
        dict: Health information containing:
            - `ok` (bool): service health flag, `True` when service is running.
            - `service` (str): service name.
            - `node_name` (str): identity of this node instance.
            - `node_role` (str): role assigned to this node.
            - `nats_enabled` (bool): whether NATS integration is enabled by configuration.
            - `nats_connected` (bool): whether a NATS client is currently connected.
            - `thresholds` (dict): configured gating thresholds with keys:
                - `noise_max` (float): maximum allowed noise score.
                - `semantic_density_min` (float): minimum required semantic density.
                - `min_anchors` (int): minimum required number of anchor terms.
    """
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
async def metrics(_auth: None = Depends(_require_api_key)):
    """
    Serve current Prometheus metrics in the Prometheus text exposition format.
    
    Returns:
        Response: HTTP response whose body is the Prometheus-formatted metrics registry and whose Content-Type is "text/plain; version=0.0.4".
    """
    from fastapi.responses import Response
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/preview/raw")
@limiter.limit("10/minute")
async def preview_raw(
    request: Request,
    body: PreviewRawRequest,
    _auth: None = Depends(_require_api_key),
):
    """
    Process a preview raw request through the shaping, attestation, and gating pipeline.
    
    Parameters:
        request (Request): Incoming FastAPI request (unused by the pipeline but kept for route signature).
        body (PreviewRawRequest): Validated request payload containing the raw content and optional metadata.
    
    Returns:
        dict: Pipeline result with keys `shaped` (shaped payload), `attested` (attested payload), `decision_subject` (NATS subject for the gating decision), and `decision` (gating decision payload).
    """
    return preview_raw_pipeline(body.model_dump())


@app.post("/v1/evaluate")
@limiter.limit("10/minute")
async def evaluate(
    request: Request,
    body: EvaluateRequest,
    _auth: None = Depends(_require_api_key),
):
    """
    Handle an evaluate request by running gating on an attested content payload and returning the resulting topic and decision payload.
    
    Returns:
        dict: A mapping with keys:
            - "topic": the subject to publish the decision to (accepted or rejected subject string).
            - "payload": the decision payload dictionary produced by `evaluate_attested_content`.
    """
    topic, decision = evaluate_attested_content(body.model_dump())
    return {
        "topic": topic,
        "payload": decision,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=HEALTH_PORT)
