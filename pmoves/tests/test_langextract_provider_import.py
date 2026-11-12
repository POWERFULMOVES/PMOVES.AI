"""libs/langextract/__init__.py provider imports.

The module had two ``except Exception`` clauses on one ``try``. The second was
dead code, so:

* when ``providers.llm`` imported fine, ``CloudflareWorkersAIProvider`` was
  never bound and ``LANGEXTRACT_PROVIDER=cloudflare`` raised ``NameError``;
* when ``providers.llm`` failed to import, the first ``except`` body re-ran the
  same import and the whole package became unimportable.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PMOVES_DIR = Path(__file__).resolve().parents[1]
if str(PMOVES_DIR) not in sys.path:
    sys.path.insert(0, str(PMOVES_DIR))

langextract = importlib.import_module("libs.langextract")
RuleProvider = importlib.import_module("libs.langextract.providers.rule").RuleProvider


@pytest.fixture
def fresh(monkeypatch):
    def _reload():
        mod = importlib.reload(langextract)
        mod._provider = None
        return mod

    yield _reload
    monkeypatch.undo()
    importlib.reload(langextract)


def test_cloudflare_provider_is_bound_and_selectable(fresh, monkeypatch):
    pytest.importorskip("requests")
    monkeypatch.setenv("LANGEXTRACT_PROVIDER", "cloudflare")
    monkeypatch.setenv("CLOUDFLARE_API_BASE", "http://cf.invalid")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token-not-real")
    mod = fresh()
    assert mod.CloudflareWorkersAIProvider is not None
    provider = mod._get_provider()
    assert type(provider).__name__ == "CloudflareWorkersAIProvider"


def test_all_llm_providers_bound_when_llm_imports(fresh):
    pytest.importorskip("requests")
    mod = fresh()
    for name in ("OpenAIChatProvider", "GeminiProvider", "TensorZeroProvider", "CloudflareWorkersAIProvider"):
        assert getattr(mod, name) is not None, name


def test_package_imports_and_falls_back_to_rule_when_llm_unavailable(fresh, monkeypatch):
    monkeypatch.setitem(sys.modules, "libs.langextract.providers.llm", None)
    mod = fresh()
    for name in ("OpenAIChatProvider", "GeminiProvider", "TensorZeroProvider", "CloudflareWorkersAIProvider"):
        assert getattr(mod, name) is None, name
    for provider_name in ("cloudflare", "openai", "gemini", "tz", "rule"):
        monkeypatch.setenv("LANGEXTRACT_PROVIDER", provider_name)
        assert type(mod._get_provider()).__name__ == "RuleProvider"
