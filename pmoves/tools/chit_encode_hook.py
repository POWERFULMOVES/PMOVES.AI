#!/usr/bin/env python3
"""
CHIT Encoding Hook for Ingestion Pipeline

Pre-indexing CHIT transform: content → Dirichlet weights + hyperbolic coords → CGP packet.
Designed to be wired into Extract Worker (port 8083) before Qdrant/Meilisearch indexing.

Thread 3.3: CHIT Encoding in Ingestion Pipeline

Usage:
    # As a standalone tool
    python pmoves/tools/chit_encode_hook.py --input content.json

    # As a library
    from pmoves.tools.chit_encode_hook import chit_encode_content
    cgp = chit_encode_content(text, metadata)

    # As a pre-index hook (called by extract-worker)
    POST http://localhost:8083/hooks/chit-encode
    {"content": "...", "metadata": {...}}
"""

import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# Riemann zeta zeros used for spectral signature verification
ZETA_ZEROS = [14.134725, 21.022040, 25.010858, 30.424876, 32.935062, 37.586178]


@dataclass
class HyperbolicCoords:
    """Poincare disk model coordinates."""

    x: float
    y: float
    curvature: float = -1.0
    radius: float = 0.0  # distance from origin in Poincare disk


@dataclass
class DirichletWeightVector:
    """Dirichlet weight distribution for content attribution."""

    alphas: List[float]
    categories: List[str]
    total_alpha: float = 0.0


@dataclass
class CGPPacket:
    """CHIT Geometry Packet v2."""

    version: str = "cgp.v2"
    timestamp: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    source: str = "chit_encode_hook"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_spectral_signature(text: str) -> List[float]:
    """Compute spectral signature using Riemann zeta zero positions.

    Maps text hash to spectral coefficients anchored at known zeta zeros.
    This provides a compact, verifiable fingerprint of the content.
    """
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hash_int = int(text_hash[:16], 16)

    signature = []
    for i, zero in enumerate(ZETA_ZEROS):
        # Modulate each zeta zero by content hash
        phase = (hash_int >> (i * 8)) & 0xFF
        amplitude = zero * (1.0 + (phase / 255.0) * 0.1)
        signature.append(round(amplitude, 6))

    return signature


def compute_hyperbolic_coords(
    text: str,
    depth: float = 0.5,
    semantic_angle: Optional[float] = None,
) -> HyperbolicCoords:
    """Map content to Poincare disk coordinates.

    Hierarchical depth maps to radial distance (deeper = closer to boundary).
    Semantic angle determined by content hash for consistent positioning.
    """
    # Hash-based angle if not provided
    if semantic_angle is None:
        text_hash = hashlib.md5(text[:200].encode("utf-8")).hexdigest()
        semantic_angle = (int(text_hash[:8], 16) / 0xFFFFFFFF) * 2 * math.pi

    # Depth [0, 1] maps to Poincare radius [0, 0.95]
    # Items deeper in hierarchy sit closer to the disk boundary
    radius = min(0.95, depth * 0.95)

    x = radius * math.cos(semantic_angle)
    y = radius * math.sin(semantic_angle)

    return HyperbolicCoords(
        x=round(x, 6),
        y=round(y, 6),
        curvature=-1.0,
        radius=round(radius, 6),
    )


def compute_dirichlet_weights(
    text: str,
    categories: Optional[List[str]] = None,
) -> DirichletWeightVector:
    """Compute Dirichlet-distributed attribution weights for content.

    Default categories reflect CHIT content dimensions:
    - factual: factual information density
    - conceptual: abstract concept density
    - procedural: how-to/process content
    - contextual: situational/environmental context
    - relational: entity relationships
    """
    if categories is None:
        categories = ["factual", "conceptual", "procedural", "contextual", "relational"]

    # Simple heuristic-based alpha estimation
    text_lower = text.lower()
    word_count = len(text.split())

    alphas = []
    for cat in categories:
        base_alpha = 0.1  # smoothing

        if cat == "factual":
            # Numbers, dates, proper nouns suggest factual content
            numbers = len([w for w in text.split() if any(c.isdigit() for c in w)])
            base_alpha += (numbers / max(1, word_count)) * 10
        elif cat == "conceptual":
            # Abstract words, definitions
            concept_words = sum(1 for w in text_lower.split() if w in {
                "concept", "theory", "model", "framework", "paradigm",
                "abstraction", "principle", "architecture", "pattern",
            })
            base_alpha += (concept_words / max(1, word_count)) * 15
        elif cat == "procedural":
            # Steps, instructions
            proc_words = sum(1 for w in text_lower.split() if w in {
                "step", "install", "run", "execute", "configure", "setup",
                "first", "then", "next", "finally", "build", "deploy",
            })
            base_alpha += (proc_words / max(1, word_count)) * 15
        elif cat == "contextual":
            # Environment, conditions
            ctx_words = sum(1 for w in text_lower.split() if w in {
                "when", "where", "environment", "context", "condition",
                "scenario", "case", "situation", "platform", "system",
            })
            base_alpha += (ctx_words / max(1, word_count)) * 12
        elif cat == "relational":
            # Relationships, connections
            rel_words = sum(1 for w in text_lower.split() if w in {
                "connects", "relates", "depends", "requires", "integrates",
                "communicates", "references", "imports", "extends", "inherits",
            })
            base_alpha += (rel_words / max(1, word_count)) * 12

        alphas.append(round(max(0.1, base_alpha), 4))

    total = sum(alphas)
    return DirichletWeightVector(
        alphas=alphas,
        categories=categories,
        total_alpha=round(total, 4),
    )


def compute_holographic_boundary(text: str) -> str:
    """Compute holographic boundary representation.

    Returns a compact encoding that represents the content's
    information at the boundary of the Poincare disk.
    """
    import base64

    # SHA-512 as boundary hash
    boundary_hash = hashlib.sha512(text.encode("utf-8")).digest()
    return base64.b64encode(boundary_hash[:32]).decode("ascii")


def chit_encode_content(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    depth: float = 0.5,
) -> CGPPacket:
    """Encode content as a CHIT Geometry Packet (CGP v2).

    This is the main entry point for the encoding hook.

    Args:
        text: Content to encode
        metadata: Optional metadata (source, tags, etc.)
        depth: Hierarchical depth [0, 1] for Poincare disk positioning

    Returns:
        CGPPacket with full CHIT encoding
    """
    metadata = metadata or {}
    now = datetime.now(timezone.utc).isoformat()

    # Compute all CHIT components
    spectral = compute_spectral_signature(text)
    coords = compute_hyperbolic_coords(text, depth=depth)
    weights = compute_dirichlet_weights(text)
    boundary = compute_holographic_boundary(text)

    # Build CGP payload
    payload = {
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "content_length": len(text),
        "word_count": len(text.split()),
        "hyperbolic_coords": asdict(coords),
        "spectral_signature": spectral,
        "dirichlet_weights": {
            "alphas": weights.alphas,
            "categories": weights.categories,
            "total_alpha": weights.total_alpha,
        },
        "holographic_boundary": boundary,
        "metadata": metadata,
    }

    # Checksum over payload
    payload_json = json.dumps(payload, sort_keys=True)
    checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    return CGPPacket(
        version="cgp.v2",
        timestamp=now,
        payload=payload,
        checksum=checksum,
        source="chit_encode_hook",
    )


def main() -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CHIT Encoding Hook")
    parser.add_argument("--input", "-i", help="Input JSON file with content")
    parser.add_argument("--text", "-t", help="Direct text input")
    parser.add_argument("--depth", type=float, default=0.5, help="Hierarchical depth [0,1]")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    args = parser.parse_args()

    if args.text:
        text = args.text
        metadata = {}
    elif args.input:
        with open(args.input) as f:
            data = json.load(f)
        text = data.get("content", data.get("text", ""))
        metadata = {k: v for k, v in data.items() if k not in ("content", "text")}
    else:
        # Read from stdin
        text = sys.stdin.read().strip()
        metadata = {}

    if not text:
        print("No content to encode", file=sys.stderr)
        return 1

    packet = chit_encode_content(text, metadata, depth=args.depth)
    indent = 2 if args.pretty else None
    print(json.dumps(packet.to_dict(), indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
