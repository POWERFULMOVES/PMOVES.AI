import os
from typing import Dict, Any, Optional

from .providers.rule import RuleProvider
try:
    from .providers.llm import OpenAIChatProvider, GeminiProvider, TensorZeroProvider
except Exception:
    OpenAIChatProvider = None
    GeminiProvider = None
    TensorZeroProvider = None
    from .providers.llm import (
        OpenAIChatProvider,
        GeminiProvider,
        CloudflareWorkersAIProvider,
    )
except Exception:
    OpenAIChatProvider = None
    GeminiProvider = None
    CloudflareWorkersAIProvider = None

def _get_provider():
    name = os.environ.get("LANGEXTRACT_PROVIDER", "rule").lower()
    if name in ("openai", "openrouter", "groq") and OpenAIChatProvider:
        return OpenAIChatProvider()
    if name in ("gemini",) and GeminiProvider:
        return GeminiProvider()
    if name in ("tensorzero","tz") and TensorZeroProvider:
        return TensorZeroProvider()
    if name in ("cloudflare", "workers", "workers-ai") and CloudflareWorkersAIProvider:
        return CloudflareWorkersAIProvider()
    # default local, rule-based
    return RuleProvider()

_provider = None

def _provider_singleton():
    global _provider
    if _provider is None:
        _provider = _get_provider()
    return _provider

_ENV_METADATA_KEYS = {
    "request_id": ("LANGEXTRACT_REQUEST_ID", "TENSORZERO_REQUEST_ID"),
    "feedback_url": ("LANGEXTRACT_FEEDBACK_URL", "TENSORZERO_FEEDBACK_URL"),
    "feedback_token": ("LANGEXTRACT_FEEDBACK_TOKEN", "TENSORZERO_FEEDBACK_TOKEN"),
    "feedback_metric": ("LANGEXTRACT_FEEDBACK_METRIC", "TENSORZERO_FEEDBACK_METRIC"),
}


def _merge_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    merged: Dict[str, Any] = {}
    if isinstance(metadata, dict):
        merged.update(metadata)
    for key, env_keys in _ENV_METADATA_KEYS.items():
        for env_key in env_keys:
            value = os.environ.get(env_key)
            if value:
                merged.setdefault(key, value)
                break
    return merged or None


def extract_text(
    document: str,
    namespace: str = "pmoves",
    doc_id: str = "doc",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = _merge_metadata(metadata)
    return _provider_singleton().extract_text(document, namespace, doc_id, merged)

def extract_xml(
    xml: str,
    namespace: str = "pmoves",
    doc_id: str = "doc",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    merged = _merge_metadata(metadata)
    return _provider_singleton().extract_xml(xml, namespace, doc_id, merged)
