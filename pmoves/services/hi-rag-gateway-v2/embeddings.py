"""Embedding generation with multi-model support.

Supports two embedding backends:
  - SentenceTransformer (default, e.g. all-MiniLM-L6-v2)
  - BGEM3FlagModel (BAAI/bge-m3 — dense + sparse + ColBERT)

Model type is auto-detected from EMBEDDING_MODEL env var.
Hot-swap via swap_embedding_model() or POST /hirag/admin/embedding/model.
"""

import threading
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException

from config import (
    EMBEDDING_MODEL,
    EMBEDDING_MODEL_TYPE,
    EMBEDDING_DIMENSION,
    DEVICE,
    logger,
    _embed_via_providers,
)

# Lock for thread-safe model hot-swap
_embedder_lock = threading.Lock()


def _is_bge3(model_name: str) -> bool:
    """Return True if model_name should use BGEM3FlagModel."""
    return "bge-m3" in model_name.lower()


def _get_sentence_embedder(model_name: str):
    """Lazy-init a SentenceTransformer model."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name, device=DEVICE)


def _get_bge3_embedder(model_name: str):
    """Lazy-init a BGEM3FlagModel."""
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(model_name, use_fp16=(DEVICE == "cuda"))


def _get_embedder():
    """Return the current embedding model (lazy-init, thread-safe)."""
    import config as _cfg
    with _embedder_lock:
        if _cfg._embedder is not None and _cfg._embedding_model_loaded == _cfg.EMBEDDING_MODEL:
            return _cfg._embedder
        # Need to (re)load
        model_name = _cfg.EMBEDDING_MODEL
        if _is_bge3(model_name):
            logger.info("Loading BGEM3FlagModel: %s", model_name)
            _cfg._embedder = _get_bge3_embedder(model_name)
        else:
            logger.info("Loading SentenceTransformer: %s", model_name)
            _cfg._embedder = _get_sentence_embedder(model_name)
        _cfg._embedding_model_loaded = model_name
        return _cfg._embedder


def _encode_bge3(embedder, text: str) -> List[float]:
    """Encode text with BGEM3FlagModel, returning dense vector."""
    output = embedder.encode([text], return_dense=True, return_sparse=True, return_colbert_vecs=False)
    # output is a dict with 'dense_vecs', 'lexical_weights', 'colbert_vecs'
    dense = output.get("dense_vecs") if isinstance(output, dict) else None
    if dense is not None:
        if hasattr(dense, "tolist"):
            dense = dense.tolist()
        if isinstance(dense, list) and len(dense) > 0:
            vec = dense[0]
            if isinstance(vec, list):
                return vec
            if hasattr(vec, "tolist"):
                return vec.tolist()
    # Fallback: if encode returned array directly
    if hasattr(output, "tolist"):
        arr = output.tolist()
        if isinstance(arr, list) and arr:
            return arr[0] if isinstance(arr[0], list) else arr
    raise RuntimeError("bge-m3 encode returned unexpected format")


def _encode_sentence(embedder, text: str) -> List[float]:
    """Encode text with SentenceTransformer, returning normalized vector."""
    emb = embedder.encode([text], normalize_embeddings=True)
    if hasattr(emb, "tolist"):
        emb = emb.tolist()
    candidate = emb[0] if isinstance(emb, list) and emb else None
    if not candidate:
        raise RuntimeError("sentence-transformers returned empty vector")
    return candidate


def embed_query(text: str) -> List[float]:
    """Embed a query string, trying provider chain first then local fallback.

    Returns a dense float vector regardless of model backend.
    """
    # Try provider chain first
    vec = None
    if _embed_via_providers is None:
        logger.debug("No provider embedding available; using local fallback")
    else:
        try:
            vec = _embed_via_providers(text)
        except Exception:
            logger.exception("Provider embedding failed; will attempt fallback")
            vec = None

    vec = _coerce_vector(vec)
    if vec:
        return vec

    # Local model fallback
    import config as _cfg
    model_name = _cfg.EMBEDDING_MODEL
    logger.info("Embedding providers unavailable; falling back to %s", model_name)
    try:
        embedder = _get_embedder()
        if _is_bge3(model_name):
            candidate = _encode_bge3(embedder, text)
        else:
            candidate = _encode_sentence(embedder, text)
        candidate = _coerce_vector(candidate)
        if not candidate:
            raise RuntimeError("embedding model returned empty vector")
        return candidate
    except Exception as e:
        logger.exception("Embedding fallback failed")
        raise HTTPException(500, f"Embedding error: {e}") from e


def embed_query_multi(text: str) -> Dict[str, Any]:
    """Embed a query, returning all available representations.

    For bge-m3: returns dict with 'dense', 'sparse', 'colbert' keys.
    For SentenceTransformer: returns dict with 'dense' only.
    """
    import config as _cfg
    model_name = _cfg.EMBEDDING_MODEL
    embedder = _get_embedder()

    if _is_bge3(model_name):
        output = embedder.encode(
            [text],
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=True,
        )
        dense = output.get("dense_vecs") if isinstance(output, dict) else None
        sparse = output.get("lexical_weights") if isinstance(output, dict) else None
        colbert = output.get("colbert_vecs") if isinstance(output, dict) else None

        def _to_list(v):
            if v is None:
                return None
            if hasattr(v, "tolist"):
                return v.tolist()
            return v

        result = {"dense": _to_list(dense)}
        if sparse:
            result["sparse"] = _to_list(sparse)
        if colbert:
            result["colbert"] = _to_list(colbert)
        return result
    else:
        vec = _encode_sentence(embedder, text)
        return {"dense": vec}


def get_embedding_dimension() -> int:
    """Return the output dimension of the current embedding model."""
    import config as _cfg
    # Explicit override takes priority
    if _cfg.EMBEDDING_DIMENSION:
        try:
            return int(_cfg.EMBEDDING_DIMENSION)
        except (TypeError, ValueError):
            pass
    # Auto-detect from model
    model_name = _cfg.EMBEDDING_MODEL
    dim_map = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
        "BAAI/bge-m3": 1024,
        "BAAI/bge-large-en-v1.5": 1024,
        "BAAI/bge-base-en-v1.5": 768,
        "BAAI/bge-small-en-v1.5": 384,
    }
    if model_name in dim_map:
        return dim_map[model_name]
    # Try to detect from model object
    try:
        embedder = _get_embedder()
        if hasattr(embedder, "get_sentence_embedding_dimension"):
            return embedder.get_sentence_embedding_dimension()
        if hasattr(embedder, "encode"):
            test = embedder.encode(["test"])
            if hasattr(test, "shape"):
                return test.shape[-1]
            if isinstance(test, list) and test:
                vec = test[0]
                if isinstance(vec, list):
                    return len(vec)
                if hasattr(vec, "shape"):
                    return vec.shape[-1]
    except Exception:
        logger.warning("Could not auto-detect embedding dimension for %s", model_name)
    return 384  # safe default


def swap_embedding_model(model_name: str) -> Dict[str, Any]:
    """Hot-swap the embedding model at runtime.

    Returns dict with status and new model info.
    Thread-safe: acquires lock during swap.
    Validates the new model by encoding a test string before reporting success.
    """
    import config as _cfg
    with _embedder_lock:
        old_model = _cfg.EMBEDDING_MODEL
        old_type = _cfg.EMBEDDING_MODEL_TYPE
        # Unload current model to free GPU memory
        if _cfg._embedder is not None:
            try:
                if hasattr(_cfg._embedder, "model") and hasattr(_cfg._embedder.model, "to"):
                    _cfg._embedder.model.to("meta")  # free GPU memory
            except Exception as exc:
                logger.debug("embedder.model.to('meta') failed: %s", exc)
        _cfg._embedder = None
        _cfg._embedding_model_loaded = None
        # Update config atomically: model name and type together
        _cfg.EMBEDDING_MODEL = model_name
        _cfg.EMBEDDING_MODEL_TYPE = _detect_type(model_name)
        logger.info(
            "Embedding model hot-swap: %s (%s) -> %s (%s)",
            old_model, old_type, model_name, _cfg.EMBEDDING_MODEL_TYPE,
        )
        # Validate: actually load and try encoding a test string
        try:
            embedder = _get_embedder()
            if _is_bge3(model_name):
                test_vec = _encode_bge3(embedder, "validation test")
            else:
                test_vec = _encode_sentence(embedder, "validation test")
            if not test_vec:
                raise RuntimeError("model returned empty vector during validation")
        except Exception as exc:
            # Rollback on failure
            logger.error("Model validation failed for %s: %s", model_name, exc)
            _cfg.EMBEDDING_MODEL = old_model
            _cfg.EMBEDDING_MODEL_TYPE = old_type
            _cfg._embedder = None
            _cfg._embedding_model_loaded = None
            raise RuntimeError(f"Model validation failed for {model_name}: {exc}") from exc
    return {
        "ok": True,
        "previous_model": old_model,
        "current_model": model_name,
        "model_type": _cfg.EMBEDDING_MODEL_TYPE,
        "dimension": get_embedding_dimension(),
    }


def _detect_type(model_name: str) -> str:
    return "bge3" if _is_bge3(model_name) else "sentence"


def get_embedding_status() -> Dict[str, Any]:
    """Return current embedding model status."""
    import config as _cfg
    return {
        "model": _cfg.EMBEDDING_MODEL,
        "model_type": _cfg.EMBEDDING_MODEL_TYPE,
        "loaded": _cfg._embedder is not None,
        "model_loaded": _cfg._embedding_model_loaded,
        "dimension": get_embedding_dimension() if _cfg._embedder is not None else None,
        "device": DEVICE,
    }


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
