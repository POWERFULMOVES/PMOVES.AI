import os, requests
from typing import List

# Priority (local-first): ollama -> openai-compatible (LM Studio, vLLM, NVIDIA NIM) -> HuggingFace -> sentence-transformers

TENSORZERO_BASE = os.environ.get("TENSORZERO_BASE_URL", "")
TENSORZERO_API_KEY = os.environ.get("TENSORZERO_API_KEY", "")
TENSORZERO_EMBED_MODEL = os.environ.get(
    "TENSORZERO_EMBED_MODEL",
    "tensorzero::embedding_model_name::gemma_embed_local",
)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://pmoves-ollama:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "embeddinggemma:300m")

OA_BASE = os.environ.get("OPENAI_COMPAT_BASE_URL")  # e.g., http://localhost:1234/v1 for LM Studio; http://vllm:8000/v1
OA_KEY = os.environ.get("OPENAI_COMPAT_API_KEY", "")
OA_EMBED_MODEL = os.environ.get("OPENAI_COMPAT_EMBED_MODEL", "text-embedding-3-small")

HF_API_KEY = os.environ.get("HF_API_KEY", "")
HF_EMBED_MODEL = os.environ.get("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

ST_MODEL = os.environ.get("SENTENCE_MODEL", "all-MiniLM-L6-v2")

_st_model = None

def _tensorzero_openai_base() -> str:
    if not TENSORZERO_BASE:
        return ""
    base = TENSORZERO_BASE.rstrip("/")
    if base.endswith("/openai"):
        return base
    return f"{base}/openai"


def _embed_tensorzero(text: str):
    base = _tensorzero_openai_base()
    if not base:
        return None
    try:
        headers = {"Content-Type": "application/json"}
        if TENSORZERO_API_KEY:
            headers["Authorization"] = f"Bearer {TENSORZERO_API_KEY}"
        resp = requests.post(
            f"{base}/v1/embeddings",
            json={"model": TENSORZERO_EMBED_MODEL, "input": text},
            headers=headers,
            timeout=30,
        )
        if resp.ok:
            data = resp.json() or {}
            arr = (data.get("data") or [{}])[0].get("embedding")
            if arr:
                return arr
    except Exception:
        pass
    return None

def _embed_ollama(text: str):
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": OLLAMA_EMBED_MODEL, "prompt": text}, timeout=15)
        if r.ok:
            v = r.json().get("embedding")
            if v: return v
    except Exception:
        pass
    return None

def _embed_openai_compat(text: str):
    if not OA_BASE:
        return None
    try:
        r = requests.post(f"{OA_BASE.rstrip('/')}/v1/embeddings", json={"model": OA_EMBED_MODEL, "input": text}, headers={"Authorization": f"Bearer {OA_KEY}"} if OA_KEY else {}, timeout=20)
        if r.ok:
            data = r.json()
            arr = (data.get("data") or [{}])[0].get("embedding")
            if arr: return arr
    except Exception:
        pass
    return None

def _embed_hf(text: str):
    if not HF_API_KEY:
        return None
    try:
        r = requests.post(f"https://api-inference.huggingface.co/pipeline/feature-extraction/{HF_EMBED_MODEL}", headers={"Authorization": f"Bearer {HF_API_KEY}", "content-type":"application/json"}, json={"inputs": text}, timeout=20)
        if r.ok:
            vec = r.json()
            # flatten if nested (seq x dim)
            if isinstance(vec, list) and vec and isinstance(vec[0], list):
                # average pooling over tokens
                import numpy as np
                return (np.array(vec).mean(axis=0)).tolist()
            if isinstance(vec, list):
                return vec
    except Exception:
        pass
    return None

def _embed_sentence_transformers(text: str):
    global _st_model
    from sentence_transformers import SentenceTransformer
    if _st_model is None:
        _st_model = SentenceTransformer(ST_MODEL)
    return _st_model.encode([text], normalize_embeddings=True).tolist()[0]

def embed_text(text: str) -> List[float]:
    return (
        _embed_tensorzero(text)
        or _embed_ollama(text)
        or _embed_openai_compat(text)
        or _embed_hf(text)
        or _embed_sentence_transformers(text)
    )
