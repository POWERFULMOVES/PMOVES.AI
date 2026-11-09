"""Hybrid scoring, TensorZero reranking, and multi-model reranker support.

Supports two reranker backends:
  - FlagReranker (default, e.g. bge-reranker-base, bge-reranker-v2-m3)
  - FlagLLMReranker (e.g. bge-reranker-v2-gemma)

Model type is auto-detected from RERANK_MODEL env var.
Hot-swap via swap_reranker_model() or POST /hirag/admin/reranker/model.
"""

import threading
from typing import Any, Dict, List, Optional

import requests

from config import (
    ALPHA,
    RERANK_ENABLE,
    RERANK_PROVIDER,
    DEVICE,
    TENSORZERO_BASE_URL,
    TENSORZERO_RERANK_FUNCTION,
    TENSORZERO_RERANK_TIMEOUT,
    TENSORZERO_API_KEY,
    logger,
)

try:
    from FlagEmbedding import FlagReranker
except ImportError:
    FlagReranker = None  # type: ignore

try:
    from FlagEmbedding import FlagLLMReranker
except ImportError:
    FlagLLMReranker = None  # type: ignore

# Lock for thread-safe model hot-swap
_reranker_lock = threading.Lock()


def _is_llm_reranker(model_name: str) -> bool:
    """Return True if model_name should use FlagLLMReranker."""
    name_lower = model_name.lower()
    # Gemma-based models and models with 'llm' in the short name use FlagLLMReranker
    if "gemma" in name_lower:
        return True
    short_name = name_lower.split("/")[-1]
    if "llm" in short_name:
        return True
    return False


def _detect_reranker_type(model_name: str) -> str:
    """Return 'llm' for FlagLLMReranker, 'flag' for FlagReranker."""
    return "llm" if _is_llm_reranker(model_name) else "flag"


def hybrid_score(vec_score: float, lex_score: float, alpha: float = ALPHA) -> float:
    return alpha * vec_score + (1.0 - alpha) * lex_score


def _tensorzero_rerank(query: str, pool: List[Dict[str, Any]]) -> Optional[List[float]]:
    base = TENSORZERO_BASE_URL.rstrip("/")
    if not base or not pool:
        return None
    url = f"{base}/functions/{TENSORZERO_RERANK_FUNCTION}/invoke"
    payload = {
        "query": query,
        "documents": [p.get("text", "") for p in pool],
    }
    headers = {"Content-Type": "application/json"}
    if TENSORZERO_API_KEY:
        headers["Authorization"] = f"Bearer {TENSORZERO_API_KEY}"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=TENSORZERO_RERANK_TIMEOUT)
        if not resp.ok:
            logger.warning(
                "Rerank error: status=%s", resp.status_code,
            )
            return None
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        scores = data.get("scores") or data.get("data")
        if isinstance(scores, list):
            try:
                return [float(s) for s in scores]
            except (TypeError, ValueError):
                return None
    except Exception:
        logger.exception("tensorzero rerank invocation error")
    return None


def _get_reranker():
    """Return the current reranker model (lazy-init, thread-safe).

    Auto-detects whether to use FlagReranker or FlagLLMReranker based on
    the model name stored in config.RERANK_MODEL_RESOLVED.
    """
    import config as _cfg
    with _reranker_lock:
        model_name = _cfg.RERANK_MODEL_RESOLVED
        # Check if already loaded with the same model
        if _cfg._reranker is not None and _cfg._reranker_model_loaded == model_name:
            return _cfg._reranker

        if not RERANK_ENABLE:
            return None

        try:
            use_fp16 = _cfg._RERANK_FP16_EFFECTIVE
            configured_model_name = _cfg.RERANK_MODEL or model_name
            reranker_type = _cfg.RERANKER_TYPE or _detect_reranker_type(configured_model_name)

            if reranker_type == "llm":
                if FlagLLMReranker is None:
                    raise ImportError(
                        "FlagLLMReranker not available; install FlagEmbedding>=1.2.5"
                    )
                logger.info("Loading FlagLLMReranker: %s (fp16=%s)", model_name, use_fp16)
                _cfg._reranker = FlagLLMReranker(
                    model_name,
                    use_fp16=use_fp16,
                    devices=[f"{DEVICE}:0"] if DEVICE == "cuda" else None,
                )
            else:
                if FlagReranker is None:
                    raise ImportError(
                        "FlagReranker not available; install FlagEmbedding>=1.2.0"
                    )
                logger.info("Loading FlagReranker: %s (fp16=%s)", model_name, use_fp16)
                _cfg._reranker = FlagReranker(model_name, use_fp16=use_fp16)
                if DEVICE == "cuda" and hasattr(_cfg._reranker, "model"):
                    _cfg._reranker.model = _cfg._reranker.model.to("cuda")

            _cfg._reranker_model_loaded = model_name
            _cfg.RERANKER_TYPE = reranker_type
            return _cfg._reranker

        except Exception:
            logger.exception("Reranker init failed")
            return None


def compute_rerank_scores(query: str, pool: List[Dict[str, Any]]) -> Optional[List[float]]:
    """Compute rerank scores for a query against a pool of documents.

    Uses TensorZero if configured, otherwise the local reranker.
    Returns a list of float scores or None.
    """
    if not pool:
        return None

    # Try TensorZero provider first
    if RERANK_PROVIDER in {"tensorzero", "tz", "tzero"}:
        scores = _tensorzero_rerank(query, pool)
        if scores is not None:
            return scores

    # Local reranker
    reranker = _get_reranker()
    if reranker is None:
        return None

    try:
        pairs = [[query, p.get("text", "")] for p in pool]
        scores = reranker.compute_score(pairs)
        # Normalize to list of floats
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        if isinstance(scores, list):
            return [float(s) for s in scores]
        # Single score (only 1 document)
        return [float(scores)] if scores is not None else None
    except Exception:
        logger.exception("Reranker compute_score failed")
        return None


def swap_reranker_model(model_name: str) -> Dict[str, Any]:
    """Hot-swap the reranker model at runtime.

    Returns dict with status and new model info.
    Thread-safe: acquires lock during swap.
    """
    import config as _cfg
    with _reranker_lock:
        old_model = _cfg.RERANK_MODEL
        old_type = _cfg.RERANKER_TYPE
        # Unload current model to free GPU memory
        if _cfg._reranker is not None:
            try:
                if hasattr(_cfg._reranker, "model") and hasattr(_cfg._reranker.model, "to"):
                    _cfg._reranker.model.to("meta")
            except Exception:
                pass
        _cfg._reranker = None
        _cfg._reranker_model_loaded = None
        # Update config
        _cfg.RERANK_MODEL = model_name
        new_type = _detect_reranker_type(model_name)
        _cfg.RERANKER_TYPE = new_type
        # Update resolved path (no path override in hot-swap)
        _cfg.RERANK_MODEL_RESOLVED = model_name
        logger.info(
            "Reranker model hot-swap: %s (%s) -> %s (%s)",
            old_model, old_type, model_name, new_type,
        )
    return {
        "ok": True,
        "previous_model": old_model,
        "current_model": model_name,
        "reranker_type": new_type,
        "device": DEVICE,
    }


def get_reranker_status() -> Dict[str, Any]:
    """Return current reranker model status."""
    import config as _cfg
    return {
        "model": _cfg.RERANK_MODEL,
        "model_resolved": _cfg.RERANK_MODEL_RESOLVED,
        "reranker_type": _cfg.RERANKER_TYPE,
        "loaded": _cfg._reranker is not None,
        "model_loaded": _cfg._reranker_model_loaded,
        "enabled": RERANK_ENABLE,
        "provider": RERANK_PROVIDER,
        "device": DEVICE,
    }
