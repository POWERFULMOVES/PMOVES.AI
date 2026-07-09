#!/usr/bin/env python3
"""
CATALOG 325 — Lensing Engine
==============================

Processes cataloged items through DARKXSIDE's 5 research dimension lenses,
assigns CHIT coordinate signatures, performs media resonance matching, and
validates against the canonical DARKXSIDE persona.

Usage:
    python pmoves/tools/catalog_lensing_engine.py --input catalog.json --output lensed.json
    make catalog-lens INPUT=catalog.json OUTPUT=lensed.json

Author: PMOVES.AI / DARKXSIDE
Date: 2026-07-09
Version: 1.0
Reference: pmoves/docs/specs/CATALOG_325_INGESTION_PIPELINE.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("catalog_lensing_engine")

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class DimensionScores:
    """5-dimension lensing scores for a single item."""

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


@dataclass
class CHITSignature:
    """5D CHIT coordinate signature."""

    delta: float = 0.0       # novelty
    Hz: float = 78.0         # tempo/cognitive frequency
    kappa: float = 0.0       # coherence
    A: float = 0.0           # amplitude
    F: str = "unclassified"  # form

    def to_dict(self) -> Dict[str, Any]:
        return {"delta": self.delta, "Hz": self.Hz, "kappa": self.kappa, "A": self.A, "F": self.F}


@dataclass
class MediaResonance:
    """Media resonance matching results."""

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
    """Persona grounding validation result."""

    grounded: bool = False
    confidence: float = 0.0
    checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"grounded": self.grounded, "confidence": round(self.confidence, 4), "checks": self.checks}


@dataclass
class NormalizedItem:
    """Unified normalized item schema."""

    raw_id: str = ""
    source_type: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    text_content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingestion_timestamp: str = ""
    ingestion_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LensedCatalogEntry:
    """Final lensed catalog entry."""

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
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return clamp(dot / (norm_a * norm_b), -1.0, 1.0)


def kl_divergence(p: List[float], q: List[float]) -> float:
    """Compute KL divergence D(p || q)."""
    kl = 0.0
    for pi, qi in zip(p, q):
        if pi > 1e-9 and qi > 1e-9:
            kl += pi * math.log(pi / qi)
    return max(kl, 0.0)


def generate_item_id(source_type: str, url: str, title: str) -> str:
    """Generate deterministic unique ID for a catalog item."""
    hasher = hashlib.sha256()
    hasher.update(f"{source_type}:{url}:{title}".encode("utf-8"))
    return f"{source_type}-{hasher.hexdigest()[:8]}"


# ---------------------------------------------------------------------------
# Stage 1: Item Ingestion (Normalization)
# ---------------------------------------------------------------------------


class ItemNormalizer:
    """Normalize heterogeneous raw items to unified schema."""

    def normalize(self, raw_item: Dict[str, Any]) -> NormalizedItem:
        """Normalize a single raw item."""
        source_type = raw_item.get("source_type", "unknown")
        url = raw_item.get("url", "")
        title = raw_item.get("title", "")

        # Build text content from available fields
        text_parts = []
        for field_name in ["description", "content", "transcript", "text", "abstract", "body"]:
            if field_name in raw_item and raw_item[field_name]:
                text_parts.append(str(raw_item[field_name]))
        if not text_parts and title:
            text_parts.append(title)

        text_content = "\n\n".join(text_parts)

        return NormalizedItem(
            raw_id=raw_item.get("id", ""),
            source_type=source_type,
            url=url,
            title=title,
            description=raw_item.get("description", ""),
            text_content=text_content,
            metadata=raw_item.get("metadata", {}),
            ingestion_timestamp=raw_item.get("ingestion_timestamp", ""),
            ingestion_version=raw_item.get("ingestion_version", "1.0"),
        )


# ---------------------------------------------------------------------------
# Embedding Interface (pluggable for BGE-M3)
# ---------------------------------------------------------------------------


class EmbeddingProvider:
    """Abstract embedding provider interface."""

    def encode(self, text: str) -> np.ndarray:
        raise NotImplementedError

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        raise NotImplementedError


class DummyEmbeddingProvider(EmbeddingProvider):
    """
    Fallback embedding provider using TF-IDF-style weighted random projections.
    Produces deterministic 384-d vectors for testing without GPU.
    """

    DIM = 384
    VOCAB_HASH_SEED = 42

    def __init__(self):
        rng = np.random.RandomState(self.VOCAB_HASH_SEED)
        self.projection = rng.randn(self.DIM, self.DIM).astype(np.float32)
        self.projection = self.projection / (np.linalg.norm(self.projection, axis=1, keepdims=True) + 1e-9)

    def encode(self, text: str) -> np.ndarray:
        words = text.lower().split()
        if not words:
            return np.zeros(self.DIM, dtype=np.float32)

        tf: Dict[str, int] = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1

        vec = np.zeros(self.DIM, dtype=np.float32)
        for word, count in tf.items():
            h = hashlib.md5(word.encode()).hexdigest()
            idx = int(h, 16) % self.DIM
            vec[idx] += count

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return self.projection.T @ vec

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        return np.array([self.encode(t) for t in texts], dtype=np.float32)


class BGEM3Provider(EmbeddingProvider):
    """BGE-M3 embedding provider (requires sentence-transformers)."""

    def __init__(self, model_name: str = "BAAI/bge-m3"):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        logger.info(f"Loaded embedding model: {model_name}")

    def encode(self, text: str) -> np.ndarray:
        return self.model.encode(text, normalize_embeddings=True, convert_to_numpy=True)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        return self.model.encode(
            texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True
        )


# ---------------------------------------------------------------------------
# Stage 2: Lensing Engine
# ---------------------------------------------------------------------------


class LensingEngine:
    """
    Apply 5 research dimension lenses to normalized items.

    Scoring formula per dimension:
        score = 0.5 * embedding_similarity + 0.3 * keyword_density + 0.2 * structural_signal
    """

    KEYWORDS: Dict[str, List[str]] = {
        "multi_agent_orchestration": [
            "agent", "orchestration", "fleet", "swarm", "consensus", "delegate",
            "coordinate", "NATS", "JetStream", "distributed", "topology", "MOF",
            "mesh", "multi-agent", "orchestrate", "coordination", "quorum",
            "three-body", "governance", "ack protocol", "GRAPHITI",
        ],
        "ai_memory_systems": [
            "memory", "context", "retrieval", "RAG", "vector", "embedding",
            "knowledge graph", "episodic", "semantic", "persistence", "HiRAG",
            "GraphRAG", "recall", "attention", "cache", "storage", "index",
            "retriever", "long-term", "short-term", "working memory",
        ],
        "consciousness_embodiment": [
            "consciousness", "Unruh", "phase transition", "emergence", "holographic",
            "observer", "quantum", "critical point", "collapse", "world model",
            "embodiment", "phenomenology", "qualia", "superposition", "entanglement",
            "decoherence", "many-worlds", "CHR", "cymatic", "resonance",
        ],
        "local_first_sovereignty": [
            "local-first", "edge", "self-hosted", "privacy", "sovereignty",
            "DIY", "homelab", "decentralize", "mesh", "open-source", "gatekeeping",
            "right-to-repair", "Gemma", "Jetson", "self-sovereign", "data ownership",
            "on-premise", "offline", "federated", "peer-to-peer", "tailscale",
        ],
        "cultural_microbiome": [
            "cultural", "microbiome", "diversity", "multilingual", "community",
            "local expression", "Dream Create Share", "proliferation", "homogenization",
            "BRICS", "cooperative", "cultural vitality", "indigenous", "vernacular",
            "grassroots", "bottom-up", "participatory", "inclusive", "accessible",
            "Fordham Hill", "Bronx", "cultural preservation",
        ],
    }

    STRUCTURAL_SIGNALS: Dict[str, Dict[str, float]] = {
        "github": {
            "multi_agent_orchestration": 0.3,
            "ai_memory_systems": 0.15,
            "consciousness_embodiment": 0.05,
            "local_first_sovereignty": 0.2,
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

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedder = embedding_provider
        self.prototype_embeddings = self._build_prototype_embeddings()

    def _build_prototype_embeddings(self) -> Dict[str, np.ndarray]:
        prototypes: Dict[str, np.ndarray] = {}
        for dim, keywords in self.KEYWORDS.items():
            prototype_text = " ".join(keywords)
            prototypes[dim] = self.embedder.encode(prototype_text)
        return prototypes

    def _keyword_density(self, text: str, dimension: str) -> float:
        text_lower = text.lower()
        keywords = self.KEYWORDS[dimension]
        word_count = max(len(text.split()), 1)
        matches = sum(1 for kw in keywords if kw.lower() in text_lower)
        density = matches / (word_count / 1000 + 1e-6)
        return clamp(density / 5.0, 0.0, 1.0)

    def _structural_signal(self, item: NormalizedItem, dimension: str) -> float:
        signals = self.STRUCTURAL_SIGNALS.get(item.source_type, {})
        return signals.get(dimension, 0.0)

    def score(self, item: NormalizedItem) -> DimensionScores:
        text = item.text_content
        if not text:
            return DimensionScores()

        embedding = self.embedder.encode(text)
        scores = DimensionScores()
        dims = [
            "multi_agent_orchestration",
            "ai_memory_systems",
            "consciousness_embodiment",
            "local_first_sovereignty",
            "cultural_microbiome",
        ]

        for dim in dims:
            embed_sim = cosine_similarity(embedding, self.prototype_embeddings[dim])
            embed_sim = (embed_sim + 1.0) / 2.0
            kw_density = self._keyword_density(text, dim)
            struct_sig = self._structural_signal(item, dim)
            score = clamp(
                0.5 * embed_sim + 0.3 * kw_density + 0.2 * struct_sig,
                0.0, 1.0,
            )
            setattr(scores, dim, round(score, 2))

        return scores


# ---------------------------------------------------------------------------
# Stage 3: CHIT Coordinate Assignment
# ---------------------------------------------------------------------------


class CHITCoordinateAssignment:
    """Compute 5D CHIT signature from dimension scores."""

    DARKXSIDE_PRIOR = np.array([0.35, 0.25, 0.20, 0.30, 0.15], dtype=np.float32)
    HZ_WEIGHTS = np.array([85.0, 72.0, 65.0, 90.0, 78.0], dtype=np.float32)

    FORM_RULES: List[Tuple[str, callable]] = [
        ("grounded", lambda s: all(d > 0.3 for d in s.values_list())),
        ("pure_mao", lambda s: s.multi_agent_orchestration > 0.8),
        ("pure_aim", lambda s: s.ai_memory_systems > 0.8),
        ("pure_ce", lambda s: s.consciousness_embodiment > 0.8),
        ("pure_lfas", lambda s: s.local_first_sovereignty > 0.8),
        ("pure_cm", lambda s: s.cultural_microbiome > 0.8),
        ("orchestrator", lambda s: s.multi_agent_orchestration > 0.7 and s.ai_memory_systems > 0.5),
        ("memory_weaver", lambda s: s.ai_memory_systems > 0.7 and s.consciousness_embodiment > 0.4),
        ("phase_hunter", lambda s: s.consciousness_embodiment > 0.7 and s.multi_agent_orchestration > 0.3),
        ("sovereign", lambda s: s.local_first_sovereignty > 0.7 and s.cultural_microbiome > 0.3),
        ("culture_seed", lambda s: s.cultural_microbiome > 0.7 and s.local_first_sovereignty > 0.3),
        ("architect", lambda s: s.multi_agent_orchestration > 0.5 and s.ai_memory_systems > 0.5 and s.consciousness_embodiment > 0.3),
        ("material_scientist", lambda s: s.consciousness_embodiment > 0.5 and s.ai_memory_systems > 0.4 and s.local_first_sovereignty > 0.3),
        ("dual_state", lambda s: (s.consciousness_embodiment > 0.5 and s.cultural_microbiome > 0.5) or abs(s.multi_agent_orchestration - s.local_first_sovereignty) < 0.1),
        ("hybrid", lambda s: s.max_score() < 0.5),
    ]

    def compute(self, scores: DimensionScores) -> CHITSignature:
        s = np.array(scores.values_list(), dtype=np.float32)
        s_sum = s.sum()
        if s_sum < 1e-6:
            return CHITSignature()

        s_norm = s / s_sum

        delta = kl_divergence(s_norm.tolist(), self.DARKXSIDE_PRIOR.tolist()) / 2.0
        delta = clamp(delta, 0.0, 1.0)

        Hz = float(np.dot(self.HZ_WEIGHTS, s) / s_sum)
        Hz = clamp(Hz, 40.0, 200.0)

        std_dev = float(np.std(s))
        kappa = clamp(1.0 - std_dev * 2.0, 0.0, 1.0)

        A = clamp(s_sum / 5.0, 0.0, 1.0)
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
# Stage 4: Media Resonance Matching
# ---------------------------------------------------------------------------


class MediaResonanceMatcher:
    """Match items to DARKXSIDE's media corpus by shape resonance."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        media_embeddings: Optional[np.ndarray] = None,
        media_catalog: Optional[List[Dict[str, Any]]] = None,
    ):
        self.embedder = embedding_provider
        self.media_embeddings = media_embeddings
        self.media_catalog = media_catalog or []

        dim = 384
        self.form_weights: Dict[str, np.ndarray] = {}
        for form in [
            "orchestrator", "memory_weaver", "phase_hunter", "sovereign",
            "culture_seed", "architect", "material_scientist", "dual_state",
            "hybrid", "grounded", "pure_mao", "pure_aim", "pure_ce",
            "pure_lfas", "pure_cm", "unclassified",
        ]:
            rng = np.random.RandomState(hash(form) % (2**31))
            w = rng.uniform(0.8, 1.2, size=dim).astype(np.float32)
            self.form_weights[form] = w / np.linalg.norm(w)

    def match(
        self,
        item: NormalizedItem,
        chit_signature: CHITSignature,
        top_k: int = 5,
    ) -> MediaResonance:
        if self.media_embeddings is None or len(self.media_catalog) == 0:
            logger.debug("No media embeddings available for resonance matching")
            return MediaResonance()

        embedding = self.embedder.encode(item.text_content)
        form_weights = self.form_weights.get(chit_signature.F, np.ones_like(embedding))
        weighted_embedding = embedding * form_weights
        weighted_embedding = weighted_embedding / (np.linalg.norm(weighted_embedding) + 1e-9)

        similarities = self.media_embeddings @ weighted_embedding
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        youtube_matches = []
        soundcloud_matches = []
        match_details = []

        for idx in top_indices:
            media = self.media_catalog[idx]
            media_id = media.get("id", f"media-{idx}")
            sim = float(similarities[idx])

            if media.get("type") == "youtube":
                youtube_matches.append(media_id)
            else:
                soundcloud_matches.append(media_id)

            match_details.append({
                "media_id": media_id,
                "type": media.get("type", "unknown"),
                "similarity": round(sim, 4),
                "title": media.get("title", ""),
            })

        resonance_score = float(np.mean(similarities[top_indices])) if len(top_indices) > 0 else 0.0

        return MediaResonance(
            youtube_matches=youtube_matches,
            soundcloud_matches=soundcloud_matches,
            resonance_score=clamp(resonance_score, 0.0, 1.0),
            match_details=match_details,
        )


# ---------------------------------------------------------------------------
# Stage 5: Persona Grounding Validator
# ---------------------------------------------------------------------------


class PersonaGroundingValidator:
    """Validate lensed items against canonical DARKXSIDE persona."""

    PERSONA_DIMENSIONS = {
        "multi_agent_orchestration": {"typical": 0.35},
        "ai_memory_systems": {"typical": 0.25},
        "consciousness_embodiment": {"typical": 0.20},
        "local_first_sovereignty": {"typical": 0.30},
        "cultural_microbiome": {"typical": 0.15},
    }

    def validate(self, entry: LensedCatalogEntry) -> GroundingResult:
        scores = entry.lenses
        s = scores.values_list()

        above_typical = any(
            getattr(scores, dim) > self.PERSONA_DIMENSIONS[dim]["typical"]
            for dim in self.PERSONA_DIMENSIONS
        )

        not_trivial = any(v > 0.1 for v in s)

        resonance_ok = (
            entry.media_resonance.resonance_score > 0.3 or
            max(s) > 0.5
        )

        has_form = entry.chit_signature.F != "unclassified"

        checks = {
            "above_typical": above_typical,
            "not_trivial": not_trivial,
            "resonance_ok": resonance_ok,
            "has_form": has_form,
        }

        grounded = all(checks.values())

        confidence = 0.0
        if grounded:
            confidence = (
                0.3 * (max(s) if s else 0.0) +
                0.3 * entry.media_resonance.resonance_score +
                0.2 * entry.chit_signature.kappa +
                0.2 * (sum(1 for c in checks.values() if c) / len(checks))
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
    """Orchestrates all 5 pipeline stages."""

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        media_embeddings: Optional[np.ndarray] = None,
        media_catalog: Optional[List[Dict[str, Any]]] = None,
    ):
        self.embedder = embedding_provider or DummyEmbeddingProvider()
        self.normalizer = ItemNormalizer()
        self.lensing_engine = LensingEngine(self.embedder)
        self.chit_assigner = CHITCoordinateAssignment()
        self.media_matcher = MediaResonanceMatcher(
            self.embedder, media_embeddings, media_catalog
        )
        self.validator = PersonaGroundingValidator()

        self.stage_times: Dict[str, float] = {}

    def process_item(self, raw_item: Dict[str, Any]) -> LensedCatalogEntry:
        t0 = time.time()
        item = self.normalizer.normalize(raw_item)
        self.stage_times["stage1_normalize"] = time.time() - t0

        t0 = time.time()
        scores = self.lensing_engine.score(item)
        self.stage_times["stage2_lensing"] = time.time() - t0

        t0 = time.time()
        chit = self.chit_assigner.compute(scores)
        self.stage_times["stage3_chit"] = time.time() - t0

        t0 = time.time()
        media_res = self.media_matcher.match(item, chit)
        self.stage_times["stage4_resonance"] = time.time() - t0

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
                "pipeline_version": "1.0",
                "processing_stage": "complete",
            },
        )

        t0 = time.time()
        entry.grounded = self.validator.validate(entry)
        self.stage_times["stage5_grounding"] = time.time() - t0

        return entry

    def process_batch(
        self, raw_items: List[Dict[str, Any]]
    ) -> List[LensedCatalogEntry]:
        results: List[LensedCatalogEntry] = []
        total = len(raw_items)

        logger.info(f"Processing {total} items through 5-stage lensing pipeline...")
        start_time = time.time()

        for i, raw_item in enumerate(raw_items):
            try:
                entry = self.process_item(raw_item)
                results.append(entry)
                if (i + 1) % 10 == 0 or i == total - 1:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"  Processed {i + 1}/{total} items "
                        f"({rate:.1f} items/sec) — "
                        f"grounded: {sum(1 for e in results if e.grounded.grounded)}/{len(results)}"
                    )
            except Exception as e:
                logger.error(f"Failed to process item {i}: {e}")
                results.append(LensedCatalogEntry(
                    id=f"failed-{i}",
                    title=raw_item.get("title", "unknown"),
                    source=raw_item.get("source_type", "unknown"),
                    url=raw_item.get("url", ""),
                ))

        total_time = time.time() - start_time
        logger.info(f"Batch complete: {len(results)} items in {total_time:.1f}s")
        return results

    def get_stats(self, entries: List[LensedCatalogEntry]) -> Dict[str, Any]:
        if not entries:
            return {}

        grounded_count = sum(1 for e in entries if e.grounded.grounded)
        total = len(entries)

        dim_stats: Dict[str, Dict[str, float]] = {}
        dims = ["multi_agent_orchestration", "ai_memory_systems",
                "consciousness_embodiment", "local_first_sovereignty",
                "cultural_microbiome"]

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
            "grounding_rate": round(grounded_count / total, 4),
            "dimension_stats": dim_stats,
            "form_distribution": form_counts,
            "resonance": {
                "mean": round(float(np.mean(res_scores)), 4),
                "median": round(float(np.median(res_scores)), 4),
            },
            "pipeline_version": "1.0",
            "processing_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(
        description="CATALOG 325 — Lensed Ingestion Pipeline for PMOVES.AI"
    )
    ap.add_argument("--input", required=True, help="Input catalog JSON/JSONL file")
    ap.add_argument("--output", default="lensed_catalog.json", help="Output lensed catalog")
    ap.add_argument("--media-embeddings", help="Pre-computed media embeddings (.npy)")
    ap.add_argument("--media-catalog", help="Media catalog JSON")
    ap.add_argument("--model", default="BAAI/bge-m3", help="Embedding model name")
    ap.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding")
    ap.add_argument("--stage", choices=["1", "2", "3", "4", "5", "all"], default="all",
                    help="Run specific stage only")
    ap.add_argument("--stats-output", help="Output statistics JSON file")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    ap.add_argument("--use-dummy-embeddings", action="store_true",
                    help="Use dummy embeddings (no GPU/model download required)")

    args = ap.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    raw_items: List[Dict[str, Any]] = []
    if args.input.endswith(".jsonl"):
        with open(args.input, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    raw_items.append(json.loads(line))
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                raw_items = data
            elif isinstance(data, dict) and "items" in data:
                raw_items = data["items"]
            else:
                raw_items = [data]

    logger.info(f"Loaded {len(raw_items)} items from {args.input}")

    if args.use_dummy_embeddings:
        logger.info("Using dummy embeddings (no model download)")
        embedder: EmbeddingProvider = DummyEmbeddingProvider()
    else:
        try:
            embedder = BGEM3Provider(args.model)
        except Exception as e:
            logger.warning(f"Failed to load BGE-M3, falling back to dummy: {e}")
            embedder = DummyEmbeddingProvider()

    media_embeddings = None
    media_catalog: List[Dict[str, Any]] = []

    if args.media_embeddings:
        media_embeddings = np.load(args.media_embeddings)
        logger.info(f"Loaded media embeddings: {media_embeddings.shape}")

    if args.media_catalog:
        with open(args.media_catalog, "r", encoding="utf-8") as f:
            media_catalog = json.load(f)
        logger.info(f"Loaded {len(media_catalog)} media catalog entries")

    pipeline = CatalogLensingPipeline(
        embedding_provider=embedder,
        media_embeddings=media_embeddings,
        media_catalog=media_catalog,
    )

    results = pipeline.process_batch(raw_items)

    output_data = [entry.to_dict() for entry in results]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote {len(output_data)} lensed entries to {args.output}")

    stats = pipeline.get_stats(results)
    logger.info(f"Grounding rate: {stats['grounding_rate']:.1%} "
                f"({stats['grounded_items']}/{stats['total_items']})")

    if args.stats_output:
        with open(args.stats_output, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        logger.info(f"Wrote statistics to {args.stats_output}")

    print("\n" + "=" * 60)
    print("CATALOG 325 — Lensing Pipeline Complete")
    print("=" * 60)
    print(f"  Items processed:  {stats['total_items']}")
    print(f"  Items grounded:   {stats['grounded_items']} ({stats['grounding_rate']:.1%})")
    print(f"  Mean resonance:   {stats['resonance']['mean']:.4f}")
    print(f"  Output:           {args.output}")
    print("\n  Dimension means:")
    for dim, ds in stats['dimension_stats'].items():
        print(f"    {dim:40s} {ds['mean']:.4f}")
    print("\n  Form distribution:")
    for form, count in sorted(stats['form_distribution'].items(), key=lambda x: -x[1]):
        print(f"    {form:40s} {count:3d}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
