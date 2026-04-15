"""Hybrid scoring, TensorZero reranking, and FlagReranker initialization."""

from typing import Any, Dict, List, Optional

import requests

from config import (
    ALPHA,
    RERANK_ENABLE,
    RERANK_MODEL_RESOLVED,
    RERANK_PROVIDER,
    DEVICE,
    _RERANK_FP16_EFFECTIVE,
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
                "tensorzero rerank request failed status=%s body=%s", resp.status_code, resp.text[:200]
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
    import config as _cfg
    if _cfg._reranker is not None:
        return _cfg._reranker
    if not RERANK_ENABLE:
        return None
    try:
        use_fp16 = _RERANK_FP16_EFFECTIVE
        _cfg._reranker = FlagReranker(RERANK_MODEL_RESOLVED, use_fp16=use_fp16)
        if DEVICE == "cuda" and hasattr(_cfg._reranker, "model"):
            _cfg._reranker.model = _cfg._reranker.model.to("cuda")  # type: ignore[attr-defined]
        return _cfg._reranker
    except Exception as e:
        logger.exception("Reranker init failed")
        return None
