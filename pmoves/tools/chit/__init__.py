"""
CHIT (Cymatic-Holographic Information Transfer) Tools

This package provides decoder utilities for CHIT Geometry Packets (CGP):
- chit_decoder: Basic text decoder (exact + geometry modes)
- chit_decoder_mm: Multi-modal decoder for images/audio
- Security utilities available in pmoves.tools.chit_security

Usage:
    from pmoves.tools.chit import decode_cgp, decode_images
    results = decode_cgp("path/to/cgp.json", corpus_path="path/to/corpus.jsonl")

Reference: pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "PMOVES.AI"

# Convenience functions that wrap the CLI tools

def decode_cgp(
    cgp_path: str,
    corpus_path: str | None = None,
    mode: str = "auto",
    per_constellation: int = 50,
) -> list[dict]:
    """
    Decode a CHIT Geometry Packet to content.

    Args:
        cgp_path: Path to CGP JSON file
        corpus_path: Path to corpus (JSONL/CSV/TXT) for geometry mode
        mode: "auto", "exact", or "geometry"
        per_constellation: Target items per constellation

    Returns:
        List of decoded records with text/content

    Example:
        >>> results = decode_cgp("cgp.json", corpus_path="corpus.jsonl")
        >>> for r in results[:5]:
        ...     print(f"{r['constellation_id']}: {r['text'][:100]}")
    """
    import sys
    from pathlib import Path

    # Import decoder module
    from pmoves.tools.chit import chit_decoder

    # Load CGP
    cgp = chit_decoder.load_cgp(cgp_path)

    # Determine mode
    has_text = any(
        "points" in const
        and any(
            isinstance(p.get("text", ""), str) and p.get("text", "").strip()
            for p in const.get("points", [])
        )
        for s in cgp.get("super_nodes", [])
        for const in s.get("constellations", [])
    )

    if mode == "auto":
        mode = "exact" if has_text else "geometry"

    # Decode based on mode
    if mode == "exact":
        return chit_decoder.exact_decode(cgp)
    elif mode == "geometry":
        if not corpus_path:
            raise ValueError("Geometry mode requires corpus_path")
        texts = chit_decoder.load_corpus(corpus_path)
        backend = cgp.get("meta", {}).get("backend", "sentence-transformers/all-MiniLM-L6-v2")
        vecs = chit_decoder.embed_texts(texts, backend)
        return chit_decoder.geometry_only_decode(
            cgp, texts, vecs, per_constellation=per_constellation
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")


def decode_images(
    cgp_path: str,
    image_dir: str,
    model_name: str = "clip-ViT-B-32",
    per_constellation: int = 24,
) -> list[dict]:
    """
    Decode a CHIT Geometry Packet to images using CLIP.

    Args:
        cgp_path: Path to CGP JSON file (must use CLIP backend)
        image_dir: Directory containing images
        model_name: CLIP model name
        per_constellation: Target images per constellation

    Returns:
        List of decoded image records with path and score

    Example:
        >>> results = decode_images("cgp_clip.json", image_dir="./images")
        >>> for r in results[:5]:
        ...     print(f"{r['path']}: {r['proj_est']:.4f}")
    """
    from pmoves.tools.chit import chit_decoder_mm

    cgp = chit_decoder_mm.load_cgp(cgp_path)
    return chit_decoder_mm.decode_images(
        cgp,
        image_dir,
        model_name=model_name,
        per_constellation=per_constellation,
    )


__all__ = [
    "decode_cgp",
    "decode_images",
]
