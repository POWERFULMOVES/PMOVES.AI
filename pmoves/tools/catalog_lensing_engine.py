#!/usr/bin/env python3
"""PMOVES Catalog Lensing Engine -- 5-dimension ingestion pipeline.

Applies DARKXSIDE's 5 research dimensions as lenses to catalog items,
generating CHIT coordinates and media resonance mappings.

Usage:
    python catalog_lensing_engine.py --input catalog.json --output lensed.json
    python catalog_lensing_engine.py --input catalog.json --output lensed.json --dry-run
    python catalog_lensing_engine.py --input catalog.json --output lensed.json --embeddings-only

Author: PMOVES.AI / DARKXSIDE
Date: 2026-07-09
Version: 1.1
Reference: pmoves/docs/specs/CATALOG_325_INGESTION_PIPELINE.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import pickle
import re
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, cast

import numpy as np

try:
    from tqdm import tqdm

    HAS_TQDM = True
except Exception:
    HAS_TQDM = False

    def tqdm(iterable, *args, **kwargs):  # type: ignore[misc]
        return iterable


# ---------------------------------------------------------------------------
# Logging setup with secrets redaction
# ---------------------------------------------------------------------------

# Patterns that may indicate secrets/credentials in log output
_SECRET_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r'"token"\s*:\s*"[^"]+"', re.IGNORECASE), '"token": "***"'),
    (re.compile(r'"api_key"\s*:\s*"[^"]+"', re.IGNORECASE), '"api_key": "***"'),
    (re.compile(r'"password"\s*:\s*"[^"]+"', re.IGNORECASE), '"password": "***"'),
    (re.compile(r'"secret"\s*:\s*"[^"]+"', re.IGNORECASE), '"secret": "***"'),
    (re.compile(r'-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----', re.DOTALL), '***PEM-KEY-REDACTED***'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36,}', re.IGNORECASE), 'ghp_***REDACTED***'),
    (re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]+', re.IGNORECASE), 'Bearer ***REDACTED***'),
]


class SecretsRedactingFilter(logging.Filter):
    """Redacts potential secrets from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str):
            return True
        msg = record.msg
        for pattern, replacement in _SECRET_PATTERNS:
            msg = pattern.sub(replacement, msg)
        record.msg = msg
        # Also sanitize args if they are strings
        if record.args and isinstance(record.args, tuple):
            sanitized: Tuple[Any, ...] = tuple(
                self._sanitize_arg(arg) for arg in record.args
            )
            record.args = sanitized
        return True

    @staticmethod
    def _sanitize_arg(arg: Any) -> Any:
        if not isinstance(arg, str):
            return arg
        result = arg
        for pattern, replacement in _SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result


def _setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("catalog_lensing_engine")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    handler.addFilter(SecretsRedactingFilter())
    logger.addHandler(handler)
    # Prevent propagation to root logger to avoid duplicate output
    logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class LensingEngineError(Exception):
    """Base exception for lensing engine errors."""


class EmbeddingError(LensingEngineError):
    """Raised when embedding computation fails."""


class NormalizationError(LensingEngineError):
    """Raised when item normalization fails."""


class MediaResonanceError(LensingEngineError):
    """Raised when media resonance matching fails."""


class GroundingValidationError(LensingEngineError):
    """Raised when persona grounding validation fails."""


class CacheError(LensingEngineError):
    """Raised when embedding cache read/write fails."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class DimensionScores:
    """5-dimension lensing scores for a single catalog item.

    Attributes:
        multi_agent_orchestration: MAO dimension score [0.0, 1.0].
        ai_memory_systems: AIM dimension score [0.0, 1.0].
        consciousness_embodiment: C&E dimension score [0.0, 1.0].
        local_first_sovereignty: LFAS dimension score [0.0, 1.0].
        cultural_microbiome: CM dimension score [0.0, 1.0].
    """

    multi_agent_orchestration: float = 0.0
    ai_memory_systems: float = 0.0
    consciousness_embodiment: float = 0.0
    local_first_sovereignty: float = 0.0
    cultural_microbiome: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def values_list(self) -> List[float]:
        return [
            self.multi_agent_orchestration,
            self.ai_memory_systems,
            self.consciousness_embodiment,
            self.local_first_sovereignty,
            self.cultural_microbiome,
        ]

    def max_score(self) -> float:
        return max(self.values_list())

    def all_below(self, threshold: float) -> bool:
        return all(v < threshold for v in self.values_list())


@dataclass
class CHITSignature:
    """5D CHIT coordinate signature for a catalog item.

    Attributes:
        delta: Novelty -- KL divergence from DARKXSIDE prior [0.0, 1.0].
        Hz: Weighted cognitive frequency/tempo [40.0, 200.0].
        kappa: Coherence -- 1 - normalized entropy of dimension scores [0.0, 1.0].
        A: Amplitude -- overall significance/magnitude [0.0, 1.0].
        F: Dominant form archetype (e.g., "grounded", "orchestrator").
    """

    delta: float = 0.0
    Hz: float = 78.0
    kappa: float = 0.0
    A: float = 0.0
    F: str = "unclassified"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta": self.delta,
            "Hz": self.Hz,
            "kappa": self.kappa,
            "A": self.A,
            "F": self.F,
        }


@dataclass
class MediaResonance:
    """Media resonance matching results.

    Attributes:
        youtube_matches: Top-K matching YouTube video IDs.
        soundcloud_matches: Top-K matching SoundCloud track IDs.
        resonance_score: Aggregate resonance score [0.0, 1.0].
        match_details: Per-match similarity details.
    """

    youtube_matches: List[str] = field(default_factory=list)
    soundcloud_matches: List[str] = field(default_factory=list)
    resonance_score: float = 0.0
    match_details: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "youtube_matches": self.youtube_matches,
            "soundcloud_matches": self.soundcloud_matches,
            "resonance_score": round(self.resonance_score, 4),
            "match_details": self.match_details,
        }


@dataclass
class GroundingResult:
    """Persona grounding validation result.

    Attributes:
        grounded: Whether the item passes all grounding checks.
        confidence: Overall confidence score [0.0, 1.0].
        checks: Individual check results (above_typical, not_trivial, etc.).
    """

    grounded: bool = False
    confidence: float = 0.0
    checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "grounded": self.grounded,
            "confidence": round(self.confidence, 4),
            "checks": self.checks,
        }


@dataclass
class NormalizedItem:
    """Unified normalized item schema regardless of source type.

    Attributes:
        raw_id: Source-specific identifier.
        source_type: One of youtube|soundcloud|arxiv|web|document|github|twitter.
        url: Canonical URL for the item.
        title: Human-readable title.
        description: Short description or abstract.
        text_content: Cleaned normalized text for processing.
        metadata: Source-specific metadata dictionary.
        ingestion_timestamp: When the item was ingested.
        ingestion_version: Pipeline version string.
    """

    raw_id: str = ""
    source_type: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    text_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingestion_timestamp: str = ""
    ingestion_version: str = "1.1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LensedCatalogEntry:
    """Final lensed catalog entry with full CHIT signature and metadata.

    Attributes:
        id: Unique deterministic identifier.
        title: Human-readable title.
        source: Source type.
        url: Canonical URL.
        lenses: 5-dimension scores.
        chit_signature: Computed CHIT coordinate signature.
        media_resonance: Media resonance matching results.
        grounded: Persona grounding validation result.
        ingestion_metadata: Pipeline processing metadata.
    """

    id: str = ""
    title: str = ""
    source: str = ""
    url: str = ""
    lenses: DimensionScores = field(default_factory=DimensionScores)
    chit_signature: CHITSignature = field(default_factory=CHITSignature)
    media_resonance: MediaResonance = field(default_factory=MediaResonance)
    grounded: GroundingResult = field(default_factory=GroundingResult)
    ingestion_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "lenses": self.lenses.to_dict(),
            "chit_signature": self.chit_signature.to_dict(),
            "media_resonance": self.media_resonance.to_dict(),
            "grounded": self.grounded.to_dict(),
            "ingestion_metadata": self.ingestion_metadata,
        }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp *value* to the inclusive interval [*min_val*, *max_val*]."""
    return max(min_val, min(max_val, value))


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1-D arrays.

    Args:
        a: First vector.
        b: Second vector (must match *a* in length).

    Returns:
        Cosine similarity in [-1.0, 1.0], or 0.0 if either vector is zero.
    """
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return clamp(dot / (norm_a * norm_b), -1.0, 1.0)


def kl_divergence(p: List[float], q: List[float]) -> float:
    """Compute KL divergence D(p || q).

    Both *p* and *q* are treated as probability distributions and are
    clipped to a minimum of 1e-9 to avoid log(0).

    Returns:
        Non-negative KL divergence value.
    """
    kl = 0.0
    for pi, qi in zip(p, q):
        pi_c = max(pi, 1e-9)
        qi_c = max(qi, 1e-9)
        kl += pi_c * math.log(pi_c / qi_c)
    return max(kl, 0.0)


def generate_item_id(source_type: str, url: str, title: str) -> str:
    """Generate a deterministic unique ID for a catalog item.

    The ID is ``{source_type}-{hexdigest[:8]}`` where the hexdigest is
    derived from a SHA-256 hash of ``source_type:url:title``.
    """
    hasher = hashlib.sha256()
    hasher.update(f"{source_type}:{url}:{title}".encode("utf-8"))
    return f"{source_type}-{hasher.hexdigest()[:8]}"


def ensure_dir(path: Path) -> None:
    """Create parent directories for *path* if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Embedding Providers
# ---------------------------------------------------------------------------


class EmbeddingProvider(ABC):
    """Abstract base class for text embedding providers.

    Implementations must provide ``encode`` and ``encode_batch`` methods
    that return L2-normalized NumPy vectors.
    """

    @abstractmethod
    def encode(self, text: str) -> np.ndarray:
        """Encode a single text string into a dense embedding vector.

        Args:
            text: Input text.

        Returns:
            1-D NumPy array of the embedding.
        """
        ...

    @abstractmethod
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode a batch of texts into embedding vectors.

        Args:
            texts: List of input text strings.

        Returns:
            2-D NumPy array of shape ``(len(texts), embedding_dim)``.
        """
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Return the dimensionality of produced embeddings."""
        ...


class DummyEmbeddingProvider(EmbeddingProvider):
    """Deterministic TF-IDF-style embedding provider for testing / CPU-only fallback.

    Produces 384-dimensional vectors using a fixed random projection matrix
    seeded at ``VOCAB_HASH_SEED = 42``.  No external dependencies, no GPU,
    and fully deterministic given the same input text.
    """

    DIM: int = 384
    VOCAB_HASH_SEED: int = 42

    def __init__(self) -> None:
        rng = np.random.RandomState(self.VOCAB_HASH_SEED)
        self._projection = rng.randn(self.DIM, self.DIM).astype(np.float32)
        norms = np.linalg.norm(self._projection, axis=1, keepdims=True) + 1e-9
        self._projection = self._projection / norms
        self._dim = self.DIM

    def encode(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros(self.DIM, dtype=np.float32)
        words = text.lower().split()
        tf: Dict[str, int] = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1

        vec = np.zeros(self.DIM, dtype=np.float32)
        for word, count in tf.items():
            h = hashlib.md5(word.encode()).hexdigest()
            idx = int(h, 16) % self.DIM
            vec[idx] += count

        norm = np.linalg.norm(vec)
        if norm > 0.0:
            vec = vec / norm
        return self._projection.T @ vec

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        return np.array([self.encode(t) for t in texts], dtype=np.float32)

    @property
    def embedding_dim(self) -> int:
        return self._dim


class BGE3EmbeddingProvider(EmbeddingProvider):
    """BGE-M3 embedding provider via ``sentence-transformers``.

    Supports GPU acceleration when ``torch.cuda.is_available()`` and falls
    back to CPU otherwise.  The BAAI/bge-m3 model produces 1024-dimensional
    dense embeddings by default.

    Args:
        model_name: Hugging Face model identifier (default: ``BAAI/bge-m3``).
        device: Override device (``"cuda"``, ``"cpu"``, or ``None`` for auto).
        trust_remote_code: Whether to trust remote code in the model.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: Optional[str] = None,
        trust_remote_code: bool = True,
    ) -> None:
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "sentence-transformers and torch are required for BGE3EmbeddingProvider. "
                "Install: pip install sentence-transformers torch"
            ) from exc

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"

        self._device = device
        try:
            self.model = SentenceTransformer(
                model_name,
                device=device,
                trust_remote_code=trust_remote_code,
            )
        except Exception as exc:
            raise EmbeddingError(f"Failed to load BGE-M3 model '{model_name}': {exc}") from exc

        self.model_name = model_name
        # Infer dimension from the model
        test_vec = self.model.encode("test", normalize_embeddings=True, convert_to_numpy=True)
        self._dim = int(test_vec.shape[0])
        logger.info(
            "Loaded BGE-M3 embedding model: %s on %s (dim=%d)",
            model_name,
            device,
            self._dim,
        )

    def encode(self, text: str) -> np.ndarray:
        try:
            return self.model.encode(
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise EmbeddingError(f"BGE-M3 encoding failed: {exc}") from exc

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        try:
            return self.model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingError(f"BGE-M3 batch encoding failed: {exc}") from exc

    @property
    def embedding_dim(self) -> int:
        return self._dim


def resolve_embedding_provider(
    force_dummy: bool = False,
    model_name: str = "BAAI/bge-m3",
    device: Optional[str] = None,
) -> EmbeddingProvider:
    """Auto-detect the best available embedding provider.

    Resolution order:
        1. Dummy provider if *force_dummy* is ``True``.
        2. BGE3EmbeddingProvider if ``sentence-transformers`` + GPU/CPU.
        3. DummyEmbeddingProvider as ultimate fallback.

    Args:
        force_dummy: Always use the dummy provider.
        model_name: Model name for BGE3EmbeddingProvider.
        device: Override device selection.

    Returns:
        Configured :class:`EmbeddingProvider` instance.
    """
    if force_dummy:
        logger.info("Using DummyEmbeddingProvider (--use-dummy-embeddings)")
        return DummyEmbeddingProvider()

    try:
        provider = BGE3EmbeddingProvider(model_name=model_name, device=device)
        return provider
    except Exception as exc:
        logger.warning(
            "BGE-M3 provider unavailable (%s). Falling back to DummyEmbeddingProvider.",
            exc,
        )
        return DummyEmbeddingProvider()


# ---------------------------------------------------------------------------
# Embedding Cache
# ---------------------------------------------------------------------------


class EmbeddingCache:
    """Persistent cache for item embeddings stored as a pickle file.

    Cache path: ``pmoves/data/cache/catalog_embeddings.pkl`` (relative to
    the repository root or current working directory).

    The cache maps ``item_id -> np.ndarray`` (embedding vector) and is
    versioned so that changes to the embedding model invalidate old caches.

    Args:
        cache_path: Override default cache file path.
        version: Cache format version string.
    """

    DEFAULT_CACHE_PATH: str = "pmoves/data/cache/catalog_embeddings.pkl"

    def __init__(
        self,
        cache_path: Optional[str] = None,
        version: str = "1.1",
    ) -> None:
        self._cache_path = Path(cache_path or self.DEFAULT_CACHE_PATH)
        self._version = version
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self._cache_path.exists():
            logger.debug("No existing embedding cache at %s", self._cache_path)
            return
        try:
            with open(self._cache_path, "rb") as f:
                payload = pickle.load(f)
            if isinstance(payload, dict) and payload.get("_version") == self._version:
                self._data = payload.get("embeddings", {})
                logger.info(
                    "Loaded embedding cache: %d items from %s",
                    len(self._data),
                    self._cache_path,
                )
            else:
                logger.warning(
                    "Embedding cache version mismatch (expected %s). Starting fresh.",
                    self._version,
                )
                self._data = {}
        except Exception as exc:
            logger.warning("Failed to load embedding cache: %s", exc)
            self._data = {}

    def get(self, item_id: str) -> Optional[np.ndarray]:
        """Retrieve cached embedding for *item_id*, or ``None`` if absent."""
        entry = self._data.get(item_id)
        if entry is None:
            return None
        vec = entry.get("vector")
        if vec is None:
            return None
        return np.asarray(vec, dtype=np.float32)

    def put(self, item_id: str, embedding: np.ndarray) -> None:
        """Store *embedding* for *item_id* in the in-memory cache."""
        self._data[item_id] = {
            "vector": embedding.astype(np.float32),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def save(self) -> None:
        """Persist the in-memory cache to disk."""
        if not self._data:
            return
        try:
            ensure_dir(self._cache_path)
            payload = {
                "_version": self._version,
                "embeddings": self._data,
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            with open(self._cache_path, "wb") as f:
                pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(
                "Saved embedding cache: %d items to %s",
                len(self._data),
                self._cache_path,
            )
        except Exception as exc:
            raise CacheError(f"Failed to write embedding cache: {exc}") from exc

    def __len__(self) -> int:
        return len(self._data)


# ---------------------------------------------------------------------------
# Stage 1: Item Ingestion (Normalization)
# ---------------------------------------------------------------------------


class ItemNormalizer:
    """Normalize heterogeneous raw items to the unified :class:`NormalizedItem` schema.

    Handles JSON objects from YouTube, SoundCloud, arXiv, web, document,
    GitHub, and Twitter sources by extracting common fields and building a
    clean ``text_content`` string suitable for embedding.
    """

    _TEXT_FIELDS: Tuple[str, ...] = (
        "description",
        "content",
        "transcript",
        "text",
        "abstract",
        "body",
        "summary",
        "notes",
    )

    def normalize(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """Normalize a single raw item.

        Args:
            raw_item: Raw dictionary from the input catalog.

        Returns:
            Populated :class:`NormalizedItem`.

        Raises:
            NormalizationError: If the item cannot be normalized.
        """
        try:
            source_type = raw_item.get("source_type", "unknown")
            url = raw_item.get("url", "")
            title = raw_item.get("title", "")

            text_parts: List[str] = []
            for field_name in self._TEXT_FIELDS:
                val = raw_item.get(field_name)
                if val and isinstance(val, str) and val.strip():
                    text_parts.append(val.strip())

            if not text_parts and title:
                text_parts.append(title)

            text_content = "\n\n".join(text_parts)

            return NormalizedItem(
                raw_id=raw_item.get("id", raw_item.get("raw_id", "")),
                source_type=source_type,
                url=url,
                title=title,
                description=raw_item.get("description", ""),
                text_content=text_content,
                metadata=raw_item.get("metadata", {}),
                ingestion_timestamp=raw_item.get(
                    "ingestion_timestamp",
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                ),
                ingestion_version=raw_item.get("ingestion_version", "1.1"),
            )
        except Exception as exc:
            raise NormalizationError(f"Failed to normalize item: {exc}") from exc


# ---------------------------------------------------------------------------
# Stage 2: Dimension Scorer
# ---------------------------------------------------------------------------


class DimensionScorer:
    """Score catalog items across DARKXSIDE's 5 research dimensions.

    Each dimension score is computed as:

        score = 0.5 * embedding_sim + 0.3 * keyword_density + 0.2 * structural_signal

    Where:
        - **embedding_sim** is cosine similarity between the item embedding and
          a prototype embedding built from dimension keywords.
        - **keyword_density** is normalized keyword occurrences per 1000 words.
        - **structural_signal** is a source-type prior bonus.

    Args:
        embedding_provider: Provider used to compute text embeddings.
        cache: Optional :class:`EmbeddingCache` for item-level embeddings.
    """

    # 20-30 keywords per dimension
    KEYWORDS: Dict[str, List[str]] = {
        "multi_agent_orchestration": [
            "agent", "orchestration", "fleet", "swarm", "consensus", "delegate",
            "coordinate", "NATS", "JetStream", "distributed", "topology", "MOF",
            "mesh", "multi-agent", "orchestrate", "coordination", "quorum",
            "three-body", "governance", "ack protocol", "GRAPHITI", "agentic",
            "workflow", "pipeline", "dag", "task queue", "scheduler",
        ],
        "ai_memory_systems": [
            "memory", "context", "retrieval", "RAG", "vector", "embedding",
            "knowledge graph", "episodic", "semantic", "persistence", "HiRAG",
            "GraphRAG", "recall", "attention", "cache", "storage", "index",
            "retriever", "long-term", "short-term", "working memory",
            "context window", "token limit", "prompt compression", "summarization",
            "associative memory", "latent space", "nearest neighbor",
        ],
        "consciousness_embodiment": [
            "consciousness", "Unruh", "phase transition", "emergence", "holographic",
            "observer", "quantum", "critical point", "collapse", "world model",
            "embodiment", "phenomenology", "qualia", "superposition", "entanglement",
            "decoherence", "many-worlds", "CHR", "cymatic", "resonance",
            "Bose-Einstein", "criticality", "self-organization", "attractor",
            "bifurcation", "symmetry breaking", "collective behavior",
        ],
        "local_first_sovereignty": [
            "local-first", "edge", "self-hosted", "privacy", "sovereignty",
            "DIY", "homelab", "decentralize", "mesh", "open-source", "gatekeeping",
            "right-to-repair", "Gemma", "Jetson", "self-sovereign", "data ownership",
            "on-premise", "offline", "federated", "peer-to-peer", "tailscale",
            "headscale", "Nginx", "Docker", "Kubernetes", "single-board computer",
            "Raspberry Pi", "Orange Pi", "ARM64", "RISC-V", "confidential computing",
        ],
        "cultural_microbiome": [
            "cultural", "microbiome", "diversity", "multilingual", "community",
            "local expression", "Dream Create Share", "proliferation", "homogenization",
            "BRICS", "cooperative", "cultural vitality", "indigenous", "vernacular",
            "grassroots", "bottom-up", "participatory", "inclusive", "accessible",
            "Fordham Hill", "Bronx", "cultural preservation", "heritage",
            "creative economy", "cultural worker", "collective ownership",
            "platform cooperative", "commons", "shared infrastructure",
        ],
    }

    # Source-type structural priors per dimension
    STRUCTURAL_SIGNALS: Dict[str, Dict[str, float]] = {
        "github": {
            "multi_agent_orchestration": 0.30,
            "ai_memory_systems": 0.15,
            "consciousness_embodiment": 0.05,
            "local_first_sovereignty": 0.20,
            "cultural_microbiome": 0.05,
        },
        "arxiv": {
            "multi_agent_orchestration": 0.15,
            "ai_memory_systems": 0.25,
            "consciousness_embodiment": 0.25,
            "local_first_sovereignty": 0.05,
            "cultural_microbiome": 0.05,
        },
        "youtube": {
            "multi_agent_orchestration": 0.15,
            "ai_memory_systems": 0.10,
            "consciousness_embodiment": 0.20,
            "local_first_sovereignty": 0.20,
            "cultural_microbiome": 0.15,
        },
        "soundcloud": {
            "multi_agent_orchestration": 0.05,
            "ai_memory_systems": 0.05,
            "consciousness_embodiment": 0.25,
            "local_first_sovereignty": 0.10,
            "cultural_microbiome": 0.30,
        },
        "web": {
            "multi_agent_orchestration": 0.10,
            "ai_memory_systems": 0.15,
            "consciousness_embodiment": 0.15,
            "local_first_sovereignty": 0.15,
            "cultural_microbiome": 0.15,
        },
        "document": {
            "multi_agent_orchestration": 0.10,
            "ai_memory_systems": 0.15,
            "consciousness_embodiment": 0.15,
            "local_first_sovereignty": 0.15,
            "cultural_microbiome": 0.10,
        },
        "twitter": {
            "multi_agent_orchestration": 0.05,
            "ai_memory_systems": 0.10,
            "consciousness_embodiment": 0.10,
            "local_first_sovereignty": 0.10,
            "cultural_microbiome": 0.15,
        },
    }

    _DIM_ORDER: Tuple[str, ...] = (
        "multi_agent_orchestration",
        "ai_memory_systems",
        "consciousness_embodiment",
        "local_first_sovereignty",
        "cultural_microbiome",
    )

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        cache: Optional[EmbeddingCache] = None,
    ) -> None:
        self._embedder = embedding_provider
        self._cache = cache
        self._prototype_embeddings = self._build_prototype_embeddings()

    def _build_prototype_embeddings(self) -> Dict[str, np.ndarray]:
        prototypes: Dict[str, np.ndarray] = {}
        for dim, keywords in self.KEYWORDS.items():
            prototype_text = " ".join(keywords)
            prototypes[dim] = self._embedder.encode(prototype_text)
        return prototypes

    def _keyword_density(self, text: str, dimension: str) -> float:
        text_lower = text.lower()
        keywords = self.KEYWORDS[dimension]
        word_count = max(len(text.split()), 1)
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        # Normalize: expected max ~5 keywords per 1000 words for strong signal
        density = matches / (word_count / 1000.0 + 1e-6)
        return clamp(density / 5.0, 0.0, 1.0)

    def _structural_signal(self, item: NormalizedItem, dimension: str) -> float:
        signals = self.STRUCTURAL_SIGNALS.get(item.source_type, {})
        return signals.get(dimension, 0.0)

    def score(self, item: NormalizedItem) -> DimensionScores:
        """Compute 5-dimension scores for a normalized item.

        Args:
            item: Normalized catalog item.

        Returns:
            :class:`DimensionScores` with scores in [0.0, 1.0].

        Raises:
            EmbeddingError: If embedding computation fails.
        """
        text = item.text_content
        if not text:
            return DimensionScores()

        # Check cache first
        item_id = generate_item_id(item.source_type, item.url, item.title)
        embedding: Optional[np.ndarray] = None
        if self._cache is not None:
            embedding = self._cache.get(item_id)

        if embedding is None:
            embedding = self._embedder.encode(text)
            if self._cache is not None:
                self._cache.put(item_id, embedding)

        scores = DimensionScores()

        for dim in self._DIM_ORDER:
            embed_sim = cosine_similarity(embedding, self._prototype_embeddings[dim])
            # Map from [-1, 1] to [0, 1]
            embed_sim = (embed_sim + 1.0) / 2.0

            kw_density = self._keyword_density(text, dim)
            struct_sig = self._structural_signal(item, dim)

            score = clamp(
                0.5 * embed_sim + 0.3 * kw_density + 0.2 * struct_sig,
                0.0,
                1.0,
            )
            setattr(scores, dim, round(score, 2))

        return scores

    def score_batch(
        self,
        items: List[NormalizedItem],
    ) -> List[DimensionScores]:
        """Score a batch of items efficiently.

        Uses batch embedding computation when possible and respects the cache.

        Args:
            items: List of normalized items.

        Returns:
            List of :class:`DimensionScores` in the same order.
        """
        results: List[DimensionScores] = []

        # Determine which items need fresh embeddings
        to_encode: List[Tuple[int, NormalizedItem]] = []
        cached_embeddings: Dict[int, np.ndarray] = {}

        for idx, item in enumerate(items):
            item_id = generate_item_id(item.source_type, item.url, item.title)
            cached = self._cache.get(item_id) if self._cache else None
            if cached is not None:
                cached_embeddings[idx] = cached
            else:
                to_encode.append((idx, item))

        # Batch encode uncached items
        if to_encode:
            texts = [item.text_content for _, item in to_encode]
            batch_embeddings = self._embedder.encode_batch(texts)
            for (idx, item), emb in zip(to_encode, batch_embeddings):
                cached_embeddings[idx] = emb
                item_id = generate_item_id(item.source_type, item.url, item.title)
                if self._cache is not None:
                    self._cache.put(item_id, emb)

        # Score each item using its embedding
        for idx, item in enumerate(items):
            embedding = cached_embeddings[idx]
            text = item.text_content
            scores = DimensionScores()

            if text:
                for dim in self._DIM_ORDER:
                    embed_sim = cosine_similarity(
                        embedding, self._prototype_embeddings[dim]
                    )
                    embed_sim = (embed_sim + 1.0) / 2.0
                    kw_density = self._keyword_density(text, dim)
                    struct_sig = self._structural_signal(item, dim)
                    score = clamp(
                        0.5 * embed_sim + 0.3 * kw_density + 0.2 * struct_sig,
                        0.0,
                        1.0,
                    )
                    setattr(scores, dim, round(score, 2))

            results.append(scores)

        return results


# ---------------------------------------------------------------------------
# Stage 3: CHIT Coordinate Generator
# ---------------------------------------------------------------------------


class CHITCoordinateGenerator:
    """Compute 5D CHIT coordinate signature from dimension scores.

    The CHIT coordinates are:

    - **delta** (novelty): KL divergence from DARKXSIDE's typical dimension
      distribution, normalized to [0, 1].
    - **Hz** (tempo): Weighted cognitive frequency where each dimension has a
      characteristic frequency (MAO=85, AIM=72, C&E=65, LFAS=90, CM=78).
    - **kappa** (coherence): 1 - (2 * std_dev of dimension scores), clamped
      to [0, 1].  High coherence means dimensions reinforce each other.
    - **A** (amplitude): Mean of the 5 dimension scores.
    - **F** (form): Dominant archetype from a 16-type lookup table.
    """

    DARKXSIDE_PRIOR: np.ndarray = np.array(
        [0.35, 0.25, 0.20, 0.30, 0.15], dtype=np.float32
    )
    HZ_WEIGHTS: np.ndarray = np.array(
        [85.0, 72.0, 65.0, 90.0, 78.0], dtype=np.float32
    )

    # Form assignment rules (ordered: first match wins)
    FORM_RULES: List[Tuple[str, Callable[[DimensionScores], bool]]] = [
        ("grounded", lambda s: all(d > 0.3 for d in s.values_list())),
        ("pure_mao", lambda s: s.multi_agent_orchestration > 0.8),
        ("pure_aim", lambda s: s.ai_memory_systems > 0.8),
        ("pure_ce", lambda s: s.consciousness_embodiment > 0.8),
        ("pure_lfas", lambda s: s.local_first_sovereignty > 0.8),
        ("pure_cm", lambda s: s.cultural_microbiome > 0.8),
        (
            "orchestrator",
            lambda s: s.multi_agent_orchestration > 0.7
            and s.ai_memory_systems > 0.5,
        ),
        (
            "memory_weaver",
            lambda s: s.ai_memory_systems > 0.7
            and s.consciousness_embodiment > 0.4,
        ),
        (
            "phase_hunter",
            lambda s: s.consciousness_embodiment > 0.7
            and s.multi_agent_orchestration > 0.3,
        ),
        (
            "sovereign",
            lambda s: s.local_first_sovereignty > 0.7
            and s.cultural_microbiome > 0.3,
        ),
        (
            "culture_seed",
            lambda s: s.cultural_microbiome > 0.7
            and s.local_first_sovereignty > 0.3,
        ),
        (
            "architect",
            lambda s: s.multi_agent_orchestration > 0.5
            and s.ai_memory_systems > 0.5
            and s.consciousness_embodiment > 0.3,
        ),
        (
            "material_scientist",
            lambda s: s.consciousness_embodiment > 0.5
            and s.ai_memory_systems > 0.4
            and s.local_first_sovereignty > 0.3,
        ),
        (
            "dual_state",
            lambda s: (
                s.consciousness_embodiment > 0.5 and s.cultural_microbiome > 0.5
            )
            or abs(s.multi_agent_orchestration - s.local_first_sovereignty) < 0.1,
        ),
        ("hybrid", lambda s: s.max_score() < 0.5),
    ]

    def compute(self, scores: DimensionScores) -> CHITSignature:
        """Compute CHIT signature from dimension scores.

        Args:
            scores: 5-dimension scores.

        Returns:
            Populated :class:`CHITSignature`.
        """
        s = np.array(scores.values_list(), dtype=np.float32)
        s_sum = s.sum()
        if s_sum < 1e-6:
            return CHITSignature()

        s_norm = s / s_sum

        # delta: KL divergence from DARKXSIDE prior
        delta = kl_divergence(s_norm.tolist(), self.DARKXSIDE_PRIOR.tolist()) / 2.0
        delta = clamp(delta, 0.0, 1.0)

        # Hz: weighted cognitive frequency
        Hz = float(np.dot(self.HZ_WEIGHTS, s) / s_sum)
        Hz = clamp(Hz, 40.0, 200.0)

        # kappa: coherence = 1 - normalized std dev (scaled by 2)
        std_dev = float(np.std(s))
        kappa = clamp(1.0 - std_dev * 2.0, 0.0, 1.0)

        # A: amplitude = mean of scores
        A = clamp(s_sum / 5.0, 0.0, 1.0)

        # F: form archetype
        F = self._assign_form(scores)

        return CHITSignature(
            delta=round(delta, 4),
            Hz=round(Hz, 2),
            kappa=round(kappa, 4),
            A=round(A, 4),
            F=F,
        )

    def _assign_form(self, scores: DimensionScores) -> str:
        for form_name, rule_fn in self.FORM_RULES:
            try:
                if rule_fn(scores):
                    return form_name
            except Exception:
                continue
        return "unclassified"


# ---------------------------------------------------------------------------
# Stage 4: Media Resonance Matcher
# ---------------------------------------------------------------------------


class MediaResonanceMatcher:
    """Match catalog items to DARKXSIDE's media corpus by shape resonance.

    Computes embedding similarity between an item and pre-embedded media
    (YouTube videos and SoundCloud tracks), then returns top-K matches with
    resonance scores.

    Args:
        embedding_provider: Provider used for embedding computation.
        media_embeddings_path: Path to pre-computed media embeddings (.npy).
        media_catalog_path: Path to media catalog metadata (.json).
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        media_embeddings_path: Optional[str] = None,
        media_catalog_path: Optional[str] = None,
    ) -> None:
        self._embedder = embedding_provider
        self._media_embeddings: Optional[np.ndarray] = None
        self._media_catalog: List[Dict[str, Any]] = []
        self._dim = embedding_provider.embedding_dim

        # Initialize form-weight vectors (deterministic per form)
        self._form_weights: Dict[str, np.ndarray] = {}
        all_forms = [
            "orchestrator",
            "memory_weaver",
            "phase_hunter",
            "sovereign",
            "culture_seed",
            "architect",
            "material_scientist",
            "dual_state",
            "hybrid",
            "grounded",
            "pure_mao",
            "pure_aim",
            "pure_ce",
            "pure_lfas",
            "pure_cm",
            "unclassified",
        ]
        for form in all_forms:
            rng = np.random.RandomState(hash(form) % (2**31))
            w = rng.uniform(0.8, 1.2, size=self._dim).astype(np.float32)
            self._form_weights[form] = w / np.linalg.norm(w)

        # Load media embeddings and catalog if provided
        if media_embeddings_path and Path(media_embeddings_path).exists():
            self._load_media_embeddings(media_embeddings_path)

        if media_catalog_path and Path(media_catalog_path).exists():
            self._load_media_catalog(media_catalog_path)

    def _load_media_embeddings(self, path: str) -> None:
        try:
            self._media_embeddings = np.load(path).astype(np.float32)
            logger.info(
                "Loaded media embeddings: shape=%s from %s",
                self._media_embeddings.shape,
                path,
            )
        except Exception as exc:
            raise MediaResonanceError(
                f"Failed to load media embeddings from {path}: {exc}"
            ) from exc

    def _load_media_catalog(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._media_catalog = data
            elif isinstance(data, dict) and "items" in data:
                self._media_catalog = data["items"]
            else:
                self._media_catalog = [data]
            logger.info(
                "Loaded %d media catalog entries from %s",
                len(self._media_catalog),
                path,
            )
        except Exception as exc:
            raise MediaResonanceError(
                f"Failed to load media catalog from {path}: {exc}"
            ) from exc

    def match(
        self,
        item: NormalizedItem,
        chit_signature: CHITSignature,
        top_k: int = 5,
    ) -> MediaResonance:
        """Find top-K media items that resonate with the lensed item.

        Args:
            item: Normalized catalog item.
            chit_signature: Computed CHIT signature (determines form weights).
            top_k: Number of top matches to return per media type.

        Returns:
            :class:`MediaResonance` with matched video/track IDs.
        """
        if self._media_embeddings is None or len(self._media_catalog) == 0:
            logger.debug("No media embeddings or catalog available for resonance matching")
            return MediaResonance()

        try:
            embedding = self._embedder.encode(item.text_content)
            form_weights = self._form_weights.get(
                chit_signature.F,
                np.ones_like(embedding),
            )
            weighted_embedding = embedding * form_weights
            norm = np.linalg.norm(weighted_embedding)
            if norm > 0.0:
                weighted_embedding = weighted_embedding / norm

            # Compute similarities against all media
            similarities = self._media_embeddings @ weighted_embedding
            top_indices = np.argsort(similarities)[-top_k:][::-1]

            youtube_matches: List[str] = []
            soundcloud_matches: List[str] = []
            match_details: List[Dict[str, Any]] = []

            for idx in top_indices:
                if idx < 0 or idx >= len(self._media_catalog):
                    continue
                media = self._media_catalog[idx]
                media_id = media.get("id", f"media-{int(idx)}")
                sim = float(similarities[int(idx)])

                if media.get("type") == "youtube":
                    youtube_matches.append(media_id)
                elif media.get("type") == "soundcloud":
                    soundcloud_matches.append(media_id)
                else:
                    # Default classification
                    youtube_matches.append(media_id)

                match_details.append(
                    {
                        "media_id": media_id,
                        "type": media.get("type", "unknown"),
                        "similarity": round(sim, 4),
                        "title": media.get("title", ""),
                    }
                )

            resonance_score = (
                float(np.mean(similarities[top_indices]))
                if len(top_indices) > 0
                else 0.0
            )

            return MediaResonance(
                youtube_matches=youtube_matches,
                soundcloud_matches=soundcloud_matches,
                resonance_score=clamp(resonance_score, 0.0, 1.0),
                match_details=match_details,
            )
        except Exception as exc:
            logger.error("Media resonance matching failed: %s", exc)
            return MediaResonance()


# ---------------------------------------------------------------------------
# Stage 5: Persona Grounding Validator
# ---------------------------------------------------------------------------


class PersonaGroundingValidator:
    """Validate lensed items against the canonical DARKXSIDE persona.

    An item is **grounded** if it passes all four checks:

    1. *above_typical*: At least one dimension exceeds the persona-typical value.
    2. *not_trivial*: Not all dimensions are below 0.1.
    3. *resonance_ok*: Media resonance > 0.3 OR max dimension score > 0.5.
    4. *has_form*: CHIT form is not "unclassified".

    Items scoring < 0.3 on all dimensions are marked **unclassified** (excluded).
    Items with high coherence (> 0.7) and a specific form are marked **grounded**.
    """

    PERSONA_DIMENSIONS: Dict[str, Dict[str, float]] = {
        "multi_agent_orchestration": {"typical": 0.35},
        "ai_memory_systems": {"typical": 0.25},
        "consciousness_embodiment": {"typical": 0.20},
        "local_first_sovereignty": {"typical": 0.30},
        "cultural_microbiome": {"typical": 0.15},
    }

    def validate(self, entry: LensedCatalogEntry) -> GroundingResult:
        """Validate a lensed catalog entry against the DARKXSIDE persona.

        Args:
            entry: Lensed entry with dimension scores and CHIT signature.

        Returns:
            :class:`GroundingResult` with checks and confidence.
        """
        scores = entry.lenses
        s = scores.values_list()

        above_typical = any(
            getattr(scores, dim) > self.PERSONA_DIMENSIONS[dim]["typical"]
            for dim in self.PERSONA_DIMENSIONS
        )

        not_trivial = any(v > 0.1 for v in s)

        resonance_ok = (
            entry.media_resonance.resonance_score > 0.3 or max(s) > 0.5
        )

        has_form = entry.chit_signature.F != "unclassified"

        checks: Dict[str, bool] = {
            "above_typical": above_typical,
            "not_trivial": not_trivial,
            "resonance_ok": resonance_ok,
            "has_form": has_form,
        }

        grounded = all(checks.values())

        if grounded:
            confidence = (
                0.3 * (max(s) if s else 0.0)
                + 0.3 * entry.media_resonance.resonance_score
                + 0.2 * entry.chit_signature.kappa
                + 0.2 * (sum(1 for c in checks.values() if c) / len(checks))
            )
        else:
            confidence = sum(s) / len(s) * 0.5 if s else 0.0

        return GroundingResult(
            grounded=grounded,
            confidence=round(clamp(confidence, 0.0, 1.0), 4),
            checks=checks,
        )


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------


class CatalogLensingPipeline:
    """Orchestrates all 5 stages of the catalog lensing pipeline.

    Stage flow::

        Raw Item -> Stage 1: Normalize -> Stage 2: Dimension Score
            -> Stage 3: CHIT Coords -> Stage 4: Media Resonance
            -> Stage 5: Grounding Validation -> Lensed Entry

    Args:
        embedding_provider: Embedding provider (BGE-M3 or dummy).
        cache: Optional embedding cache.
        media_embeddings_path: Path to pre-computed media embeddings (.npy).
        media_catalog_path: Path to media catalog metadata (.json).
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        cache: Optional[EmbeddingCache] = None,
        media_embeddings_path: Optional[str] = None,
        media_catalog_path: Optional[str] = None,
    ) -> None:
        self._embedder = embedding_provider
        self._cache = cache
        self._normalizer = ItemNormalizer()
        self._scorer = DimensionScorer(embedding_provider, cache=cache)
        self._chit_generator = CHITCoordinateGenerator()
        self._media_matcher = MediaResonanceMatcher(
            embedding_provider,
            media_embeddings_path=media_embeddings_path,
            media_catalog_path=media_catalog_path,
        )
        self._validator = PersonaGroundingValidator()
        self._stage_times: Dict[str, float] = {}

    def process_item(self, raw_item: Dict[str, Any]) -> LensedCatalogEntry:
        """Process a single raw item through all 5 pipeline stages.

        Never crashes -- exceptions are caught and logged, returning a
        best-effort entry.

        Args:
            raw_item: Raw dictionary from the input catalog.

        Returns:
            Fully populated :class:`LensedCatalogEntry`.
        """
        # Stage 1: Normalize
        t0 = time.time()
        try:
            item = self._normalizer.normalize(raw_item)
        except Exception as exc:
            logger.error("Stage 1 (normalize) failed: %s", exc)
            return self._error_entry(raw_item, f"normalize: {exc}")
        self._stage_times["stage1_normalize"] = time.time() - t0

        # Stage 2: Dimension Scoring
        t0 = time.time()
        try:
            scores = self._scorer.score(item)
        except Exception as exc:
            logger.error("Stage 2 (score) failed for '%s': %s", item.title, exc)
            scores = DimensionScores()
        self._stage_times["stage2_lensing"] = time.time() - t0

        # Stage 3: CHIT Coordinates
        t0 = time.time()
        try:
            chit = self._chit_generator.compute(scores)
        except Exception as exc:
            logger.error("Stage 3 (CHIT) failed: %s", exc)
            chit = CHITSignature()
        self._stage_times["stage3_chit"] = time.time() - t0

        # Stage 4: Media Resonance
        t0 = time.time()
        try:
            media_res = self._media_matcher.match(item, chit)
        except Exception as exc:
            logger.error("Stage 4 (resonance) failed: %s", exc)
            media_res = MediaResonance()
        self._stage_times["stage4_resonance"] = time.time() - t0

        # Stage 5: Grounding Validation
        entry = LensedCatalogEntry(
            id=generate_item_id(item.source_type, item.url, item.title),
            title=item.title,
            source=item.source_type,
            url=item.url,
            lenses=scores,
            chit_signature=chit,
            media_resonance=media_res,
            ingestion_metadata={
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pipeline_version": "1.1",
                "processing_stage": "complete",
            },
        )

        t0 = time.time()
        try:
            entry.grounded = self._validator.validate(entry)
        except Exception as exc:
            logger.error("Stage 5 (grounding) failed: %s", exc)
            entry.grounded = GroundingResult(
                grounded=False, confidence=0.0, checks={}
            )
        self._stage_times["stage5_grounding"] = time.time() - t0

        return entry

    def process_batch(
        self,
        raw_items: List[Dict[str, Any]],
        max_items: Optional[int] = None,
        dry_run: bool = False,
    ) -> List[LensedCatalogEntry]:
        """Process a batch of raw items through the lensing pipeline.

        Args:
            raw_items: List of raw catalog dictionaries.
            max_items: If set, process at most this many items.
            dry_run: If ``True``, do not write output (just process and return).

        Returns:
            List of :class:`LensedCatalogEntry` objects.
        """
        if max_items is not None:
            raw_items = raw_items[:max_items]

        total = len(raw_items)
        results: List[LensedCatalogEntry] = []

        mode_str = " (DRY RUN)" if dry_run else ""
        logger.info(
            "Processing %d items through 5-stage lensing pipeline%s...",
            total,
            mode_str,
        )
        start_time = time.time()

        iterator = tqdm(raw_items, desc="Lensing", unit="item") if HAS_TQDM else raw_items

        for i, raw_item in enumerate(iterator):
            try:
                entry = self.process_item(raw_item)
                results.append(entry)

                if not HAS_TQDM and ((i + 1) % 10 == 0 or i == total - 1):
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    grounded_count = sum(
                        1 for e in results if e.grounded.grounded
                    )
                    logger.info(
                        "  Processed %d/%d items (%.1f items/sec) -- "
                        "grounded: %d/%d",
                        i + 1,
                        total,
                        rate,
                        grounded_count,
                        len(results),
                    )
            except Exception as exc:
                logger.error("Failed to process item %d: %s", i, exc)
                results.append(
                    LensedCatalogEntry(
                        id=f"failed-{i}",
                        title=raw_item.get("title", "unknown"),
                        source=raw_item.get("source_type", "unknown"),
                        url=raw_item.get("url", ""),
                    )
                )

        total_time = time.time() - start_time
        grounded_count = sum(1 for e in results if e.grounded.grounded)
        logger.info(
            "Batch complete: %d items in %.1fs (%d grounded, %d failed)",
            len(results),
            total_time,
            grounded_count,
            sum(1 for e in results if e.id.startswith("failed-")),
        )
        return results

    def precompute_embeddings(
        self,
        raw_items: List[Dict[str, Any]],
        max_items: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """Precompute and cache embeddings for all items without full scoring.

        Args:
            raw_items: List of raw catalog dictionaries.
            max_items: If set, process at most this many items.

        Returns:
            Dictionary mapping ``item_id -> embedding``.
        """
        if max_items is not None:
            raw_items = raw_items[:max_items]

        total = len(raw_items)
        logger.info("Precomputing embeddings for %d items...", total)

        embeddings: Dict[str, np.ndarray] = {}
        items_to_encode: List[Tuple[str, NormalizedItem]] = []

        # First pass: normalize and check cache
        for raw_item in raw_items:
            try:
                item = self._normalizer.normalize(raw_item)
                item_id = generate_item_id(
                    item.source_type, item.url, item.title
                )
                cached = self._cache.get(item_id) if self._cache else None
                if cached is not None:
                    embeddings[item_id] = cached
                else:
                    items_to_encode.append((item_id, item))
            except Exception as exc:
                logger.warning("Skipping item in precompute: %s", exc)

        # Batch encode uncached items
        batch_size = 32
        for batch_start in tqdm(
            range(0, len(items_to_encode), batch_size),
            desc="Encoding batches",
            unit="batch",
            disable=not HAS_TQDM,
        ):
            batch = items_to_encode[batch_start : batch_start + batch_size]
            item_ids = [tid for tid, _ in batch]
            texts = [item.text_content for _, item in batch]

            try:
                batch_embs = self._embedder.encode_batch(texts)
                for item_id, emb in zip(item_ids, batch_embs):
                    embeddings[item_id] = emb
                    if self._cache is not None:
                        self._cache.put(item_id, emb)
            except Exception as exc:
                logger.error("Batch encoding failed at offset %d: %s", batch_start, exc)
                # Fallback: encode individually
                for item_id, item in batch:
                    try:
                        emb = self._embedder.encode(item.text_content)
                        embeddings[item_id] = emb
                        if self._cache is not None:
                            self._cache.put(item_id, emb)
                    except Exception as inner_exc:
                        logger.error("Individual encoding failed for %s: %s", item_id, inner_exc)

        logger.info(
            "Precomputed %d embeddings (%d from cache, %d fresh)",
            len(embeddings),
            len(embeddings) - len(items_to_encode),
            len(items_to_encode),
        )

        if self._cache is not None:
            self._cache.save()

        return embeddings

    @staticmethod
    def _error_entry(raw_item: Dict[str, Any], error_msg: str) -> LensedCatalogEntry:
        return LensedCatalogEntry(
            id=f"error-{hash(str(raw_item)) & 0xFFFFFFFF:08x}",
            title=raw_item.get("title", "unknown"),
            source=raw_item.get("source_type", "unknown"),
            url=raw_item.get("url", ""),
            ingestion_metadata={
                "error": error_msg,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pipeline_version": "1.1",
            },
        )

    def get_stats(self, entries: List[LensedCatalogEntry]) -> Dict[str, Any]:
        """Compute aggregate statistics over a list of lensed entries.

        Args:
            entries: Processed lensed entries.

        Returns:
            Statistics dictionary with counts, dimension stats, form
            distribution, and resonance summary.
        """
        if not entries:
            return {}

        grounded_count = sum(1 for e in entries if e.grounded.grounded)
        total = len(entries)

        dim_stats: Dict[str, Dict[str, float]] = {}
        dims = [
            "multi_agent_orchestration",
            "ai_memory_systems",
            "consciousness_embodiment",
            "local_first_sovereignty",
            "cultural_microbiome",
        ]

        for dim in dims:
            vals = [getattr(e.lenses, dim) for e in entries]
            dim_stats[dim] = {
                "mean": round(float(np.mean(vals)), 4),
                "std": round(float(np.std(vals)), 4),
                "min": round(float(np.min(vals)), 4),
                "max": round(float(np.max(vals)), 4),
            }

        form_counts: Dict[str, int] = {}
        for e in entries:
            form = e.chit_signature.F
            form_counts[form] = form_counts.get(form, 0) + 1

        res_scores = [e.media_resonance.resonance_score for e in entries]

        return {
            "total_items": total,
            "grounded_items": grounded_count,
            "grounding_rate": round(grounded_count / total, 4) if total else 0.0,
            "dimension_stats": dim_stats,
            "form_distribution": form_counts,
            "resonance": {
                "mean": round(float(np.mean(res_scores)), 4),
                "median": round(float(np.median(res_scores)), 4),
            },
            "pipeline_version": "1.1",
            "processing_timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
        }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_catalog(path: str) -> List[Dict[str, Any]]:
    """Load catalog from JSON or JSONL file.

    Args:
        path: Path to the catalog file.

    Returns:
        List of raw catalog item dictionaries.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input catalog not found: {path}")

    if path.endswith(".jsonl"):
        items: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items
    elif path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if "items" in data:
                return cast(List[Dict[str, Any]], data["items"])
            return [data]
        else:
            raise ValueError(f"Unsupported JSON structure in {path}")
    else:
        raise ValueError(f"Unsupported file format: {path} (expected .json or .jsonl)")


def write_jsonl_output(
    entries: List[LensedCatalogEntry],
    path: str,
) -> None:
    """Write lensed entries as JSON Lines (one JSON object per line).

    Args:
        entries: Lensed catalog entries.
        path: Output file path.
    """
    ensure_dir(Path(path))
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def write_json_output(
    entries: List[LensedCatalogEntry],
    path: str,
) -> None:
    """Write lensed entries as a single pretty-printed JSON array.

    Args:
        entries: Lensed catalog entries.
        path: Output file path.
    """
    ensure_dir(Path(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in entries], f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "PMOVES Catalog Lensing Engine -- 5-dimension ingestion pipeline "
            "for cataloged items."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --input catalog.json --output lensed.json\n"
            "  %(prog)s --input catalog.json --output lensed.json --dry-run\n"
            "  %(prog)s --input catalog.json --embeddings-only\n"
            "  %(prog)s --input catalog.json --output lensed.json --max-items 5 --verbose\n"
        ),
    )
    parser.add_argument("--input", required=True, help="Input catalog JSON/JSONL file")
    parser.add_argument(
        "--output",
        default="lensed_catalog.json",
        help="Output lensed catalog path (default: lensed_catalog.json)",
    )
    parser.add_argument(
        "--media-embeddings",
        dest="media_embeddings",
        help="Path to pre-computed media embeddings (.npy)",
    )
    parser.add_argument(
        "--media-catalog",
        dest="media_catalog",
        help="Path to media catalog metadata (.json)",
    )
    parser.add_argument(
        "--cache-path",
        dest="cache_path",
        default=EmbeddingCache.DEFAULT_CACHE_PATH,
        help="Path for embedding cache (default: pmoves/data/cache/catalog_embeddings.pkl)",
    )
    parser.add_argument(
        "--model",
        default="BAAI/bge-m3",
        help="Embedding model name (default: BAAI/bge-m3)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help='Override device: "cuda", "cpu", or None for auto',
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=32,
        help="Batch size for embedding computation (default: 32)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Process but do not write output files",
    )
    parser.add_argument(
        "--embeddings-only",
        dest="embeddings_only",
        action="store_true",
        help="Only precompute and cache embeddings, skip full pipeline",
    )
    parser.add_argument(
        "--max-items",
        dest="max_items",
        type=int,
        default=None,
        help="Limit processing to N items (useful for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    parser.add_argument(
        "--use-dummy-embeddings",
        dest="use_dummy",
        action="store_true",
        help="Use dummy embeddings (no model download / GPU required)",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Write output as JSON Lines (default: pretty JSON)",
    )
    parser.add_argument(
        "--stats-output",
        dest="stats_output",
        help="Optional path to write aggregate statistics JSON",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    global logger
    logger = _setup_logging(verbose=args.verbose)

    # Load input catalog
    try:
        raw_items = load_catalog(args.input)
    except Exception as exc:
        logger.error("Failed to load input catalog: %s", exc)
        return 1

    logger.info("Loaded %d items from %s", len(raw_items), args.input)

    if args.max_items is not None:
        logger.info("Limiting to %d items (max-items)", args.max_items)

    # Resolve embedding provider
    try:
        embedder = resolve_embedding_provider(
            force_dummy=args.use_dummy,
            model_name=args.model,
            device=args.device,
        )
    except Exception as exc:
        logger.error("Failed to initialize embedding provider: %s", exc)
        return 1

    # Initialize embedding cache
    cache = EmbeddingCache(cache_path=args.cache_path)

    # Build pipeline
    pipeline = CatalogLensingPipeline(
        embedding_provider=embedder,
        cache=cache,
        media_embeddings_path=args.media_embeddings,
        media_catalog_path=args.media_catalog,
    )

    # Embeddings-only mode
    if args.embeddings_only:
        logger.info("=== EMBEDDINGS-ONLY MODE ===")
        embeddings = pipeline.precompute_embeddings(raw_items, max_items=args.max_items)
        if args.dry_run:
            logger.info("DRY RUN: Would have cached %d embeddings", len(embeddings))
        else:
            cache.save()
            logger.info("Cached %d embeddings to %s", len(embeddings), args.cache_path)
        return 0

    # Full pipeline
    results = pipeline.process_batch(
        raw_items,
        max_items=args.max_items,
        dry_run=args.dry_run,
    )

    # Save cache (embeddings accumulated during scoring)
    if not args.dry_run and cache:
        cache.save()

    # Write output
    if not args.dry_run:
        try:
            if args.jsonl:
                write_jsonl_output(results, args.output)
            else:
                write_json_output(results, args.output)
            logger.info("Wrote %d lensed entries to %s", len(results), args.output)
        except Exception as exc:
            logger.error("Failed to write output: %s", exc)
            return 1
    else:
        logger.info("DRY RUN: Skipped writing output to %s", args.output)

    # Compute and report statistics
    stats = pipeline.get_stats(results)
    logger.info(
        "Grounding rate: %.1f%% (%d/%d)",
        stats.get("grounding_rate", 0.0) * 100,
        stats.get("grounded_items", 0),
        stats.get("total_items", 0),
    )

    if args.stats_output and not args.dry_run:
        try:
            ensure_dir(Path(args.stats_output))
            with open(args.stats_output, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
                f.write("\n")
            logger.info("Wrote statistics to %s", args.stats_output)
        except Exception as exc:
            logger.error("Failed to write stats: %s", exc)

    # Console summary
    _print_summary(stats, args)

    return 0


def _print_summary(stats: Dict[str, Any], args: argparse.Namespace) -> None:
    print("\n" + "=" * 72)
    print("  CATALOG 325 -- Lensing Pipeline Complete")
    print("=" * 72)
    print(f"  Items processed:  {stats.get('total_items', 0)}")
    print(
        f"  Items grounded:   {stats.get('grounded_items', 0)} "
        f"({stats.get('grounding_rate', 0.0):.1%})"
    )
    print(f"  Mean resonance:   {stats.get('resonance', {}).get('mean', 0.0):.4f}")
    if not args.dry_run:
        print(f"  Output:           {args.output}")
    else:
        print(f"  Output:           (dry run -- not written)")
    print(f"  Embedding cache:  {args.cache_path}")

    dim_stats = stats.get("dimension_stats", {})
    if dim_stats:
        print("\n  Dimension means:")
        for dim, ds in dim_stats.items():
            print(f"    {dim:42s} {ds['mean']:.4f}")

    form_dist = stats.get("form_distribution", {})
    if form_dist:
        print("\n  Form distribution:")
        for form, count in sorted(form_dist.items(), key=lambda x: -x[1]):
            print(f"    {form:42s} {count:3d}")

    print("\n" + "=" * 72)
    print(
        "GRAPHITI_MARK: CATALOG325::LENSING-ENGINE::v1.1::"
        + time.strftime("%Y-%m-%d", time.gmtime())
    )
    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
