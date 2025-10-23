import os
from typing import Dict, Any

from .providers.rule import RuleProvider
try:
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

def extract_text(document: str, namespace: str = "pmoves", doc_id: str = "doc") -> Dict[str, Any]:
    return _provider_singleton().extract_text(document, namespace, doc_id)

def extract_xml(xml: str, namespace: str = "pmoves", doc_id: str = "doc") -> Dict[str, Any]:
    return _provider_singleton().extract_xml(xml, namespace, doc_id)
