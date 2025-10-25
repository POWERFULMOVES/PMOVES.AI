import os, requests
from typing import List

# Priority (local-first): ollama -> openai-compatible (LM Studio, vLLM, NVIDIA NIM) -> HuggingFace -> sentence-transformers

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

OA_BASE = os.environ.get("OPENAI_COMPAT_BASE_URL")  # e.g., http://localhost:1234/v1 for LM Studio; http://vllm:8000/v1
OA_KEY = os.environ.get("OPENAI_COMPAT_API_KEY", "")
OA_EMBED_MODEL = os.environ.get("OPENAI_COMPAT_EMBED_MODEL", "text-embedding-3-small")

HF_API_KEY = os.environ.get("HF_API_KEY", "")
HF_EMBED_MODEL = os.environ.get("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

ST_MODEL = os.environ.get("SENTENCE_MODEL", "all-MiniLM-L6-v2")

_st_model = None

def _embed_ollama(text: str):
    """Generates an embedding using a local Ollama instance.

    Args:
        text: The text to embed.

    Returns:
        The embedding vector as a list of floats, or None on failure.
    """
    try:
        r = requests.post(f"{OLLAMA_URL}/api/embeddings", json={"model": OLLAMA_EMBED_MODEL, "prompt": text}, timeout=15)
        if r.ok:
            v = r.json().get("embedding")
            if v: return v
    except Exception:
        pass
    return None

def _embed_openai_compat(text: str):
    """Generates an embedding using an OpenAI-compatible API.

    Args:
        text: The text to embed.

    Returns:
        The embedding vector as a list of floats, or None on failure.
    """
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
    """Generates an embedding using the Hugging Face Inference API.

    Args:
        text: The text to embed.

    Returns:
        The embedding vector as a list of floats, or None on failure.
    """
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
    """Generates an embedding using a local `sentence-transformers` model.

    Args:
        text: The text to embed.

    Returns:
        The embedding vector as a list of floats.
    """
    global _st_model
    from sentence_transformers import SentenceTransformer
    if _st_model is None:
        _st_model = SentenceTransformer(ST_MODEL)
    return _st_model.encode([text], normalize_embeddings=True).tolist()[0]

def embed_text(text: str) -> List[float]:
    """Generates an embedding for a given text by trying multiple providers.

    The function attempts to generate an embedding using the following providers
    in order, returning the result from the first successful one:
    1. Ollama (local)
    2. OpenAI-compatible API (e.g., LM Studio, vLLM)
    3. Hugging Face Inference API
    4. `sentence-transformers` (local)

    Args:
        text: The text to embed.

    Returns:
        The embedding vector as a list of floats.
    """
    return (
        _embed_ollama(text)
        or _embed_openai_compat(text)
        or _embed_hf(text)
        or _embed_sentence_transformers(text)
    )

