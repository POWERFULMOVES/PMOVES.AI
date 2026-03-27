"""Lightweight HuggingFace API client for model metadata enrichment.

Uses httpx (already a dependency) — no huggingface_hub SDK needed.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

HF_API_BASE = "https://huggingface.co/api/models"
HF_TOKEN = os.environ.get("HF_TOKEN", "")
DEFAULT_TIMEOUT = 30.0


async def fetch_model_info(hf_id: str) -> Dict[str, Any]:
    """Fetch model card metadata from HuggingFace API.

    Args:
        hf_id: HuggingFace model identifier (e.g. "Qwen/Qwen3-Embedding-4B")

    Returns:
        Dict with model metadata (tags, downloads, license, etc.)
    """
    url = f"{HF_API_BASE}/{hf_id}"
    headers = _build_headers()

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


async def fetch_model_config(hf_id: str) -> Optional[Dict[str, Any]]:
    """Fetch model config.json from HuggingFace (contains dimensions, architecture).

    Args:
        hf_id: HuggingFace model identifier

    Returns:
        Dict with config data, or None if config.json doesn't exist.
    """
    url = f"https://huggingface.co/{hf_id}/resolve/main/config.json"
    headers = _build_headers()

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


def parse_embedding_dimensions(config: Dict[str, Any]) -> Optional[int]:
    """Extract embedding dimensions from a HuggingFace model config.

    Tries common config keys in order of specificity.
    """
    for key in ("embedding_dimension", "hidden_size", "d_model", "n_embd"):
        if key in config:
            val = config[key]
            if isinstance(val, int) and val > 0:
                return val
    return None


def parse_cuda_support(info: Dict[str, Any]) -> bool:
    """Determine CUDA/GPU support from model tags and library info."""
    tags = set(info.get("tags", []))
    cuda_indicators = {"pytorch", "cuda", "transformers", "safetensors"}
    return bool(tags & cuda_indicators)


def parse_model_summary(info: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a concise summary from HuggingFace model info.

    Returns a dict suitable for merging into Supabase metadata.
    """
    summary: Dict[str, Any] = {
        "hf_id": info.get("id", ""),
        "hf_last_modified": info.get("lastModified", ""),
        "hf_downloads": info.get("downloads", 0),
        "hf_likes": info.get("likes", 0),
        "hf_tags": info.get("tags", []),
        "hf_library_name": info.get("library_name", ""),
        "hf_pipeline_tag": info.get("pipeline_tag", ""),
        "hf_license": info.get("cardData", {}).get("license", ""),
        "cuda_supported": parse_cuda_support(info),
    }
    return summary


def _build_headers() -> Dict[str, str]:
    """Build request headers, optionally with auth token."""
    headers: Dict[str, str] = {"Accept": "application/json"}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"
    return headers
