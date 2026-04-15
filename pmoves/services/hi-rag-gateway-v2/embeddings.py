"""Embedding generation with provider fallback to local SentenceTransformer."""

from typing import Any, List, Optional

from fastapi import HTTPException

from config import MODEL, DEVICE, logger, _embed_via_providers, _embedder


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(MODEL, device=DEVICE)
    return _embedder


def embed_query(text: str):
    # Try provider chain first; fall back to local SentenceTransformer when unavailable
    vec = None
    try:
        vec = _embed_via_providers(text)
    except Exception:
        logger.exception("Provider embedding failed; will attempt fallback")
        vec = None

    vec = _coerce_vector(vec)
    if vec:
        return vec

    logger.info("Embedding providers unavailable; falling back to %s", MODEL)
    try:
        emb = _get_embedder().encode([text], normalize_embeddings=True)
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
        candidate = emb[0] if isinstance(emb, list) and emb else None
        candidate = _coerce_vector(candidate)
        if not candidate:
            raise RuntimeError("sentence-transformers returned empty vector")
        return candidate
    except Exception as e:
        logger.exception("Embedding fallback failed")
        raise HTTPException(500, f"Embedding error: {e}")


def _coerce_vector(vec: Any) -> Optional[List[float]]:
    if vec is None:
        return None
    if hasattr(vec, "tolist"):
        try:
            vec = vec.tolist()
        except Exception:
            return None
    if not isinstance(vec, (list, tuple)):
        return None
    out: List[float] = []
    try:
        for item in vec:
            out.append(float(item))
    except (TypeError, ValueError):
        return None
    return out if out else None
