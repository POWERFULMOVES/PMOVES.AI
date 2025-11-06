from __future__ import annotations

from typing import Dict

import pytest

from pmoves.services.deepresearch import (
    DeepResearchRunner,
    ResearchRequest,
    ResearchResources,
    clear_cache,
    load_cookbooks,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_cache()
    yield
    clear_cache()


def test_load_cookbooks_caches_fetcher_calls():
    calls: Dict[str, int] = {}

    def fake_fetch(path: str) -> str:
        calls[path] = calls.get(path, 0) + 1
        return f"content:{path}"

    result1 = load_cookbooks(["guide.md"], fetcher=fake_fetch)
    result2 = load_cookbooks(["guide.md"], fetcher=fake_fetch)

    assert result1 == {"guide.md": "content:guide.md"}
    assert result2 == result1
    assert calls == {"guide.md": 1}


def test_openrouter_run_enriches_context_with_cookbooks():
    captured = {}

    def fake_client(payload):
        captured["payload"] = payload
        return {"status": "ok"}

    def fake_loader(paths):
        return {path: f"details for {path}" for path in paths}

    request = ResearchRequest(
        prompt="Summarise multimodal tips",
        context=["baseline"],
        resources=ResearchResources(cookbooks=["vision/tips.md"]),
    )

    runner = DeepResearchRunner(openrouter_client=fake_client, cookbook_loader=fake_loader)
    result = runner._run_openrouter(request)

    assert result == {"status": "ok"}
    payload = captured["payload"]
    assert payload["context"][0] == "baseline"
    assert any("details for vision/tips.md" in entry for entry in payload["context"][1:])
    attachments = payload["notebook"]["attachments"]
    assert attachments[0]["path"] == "vision/tips.md"
    assert attachments[0]["type"] == "cookbook"
    assert attachments[0]["excerpt"].startswith("details for vision/tips.md")
    assert payload["resources"]["cookbooks"] == ["vision/tips.md"]


def test_local_run_enriches_context_with_cookbooks_when_no_client():
    def fake_loader(paths):
        return {"audio.md": "audio notes"}

    request = ResearchRequest(
        prompt="Audio guidance",
        context=[],
        resources=ResearchResources(cookbooks=["audio.md"]),
    )

    runner = DeepResearchRunner(cookbook_loader=fake_loader)
    result = runner._run_local(request)

    assert result["provider"] == "local"
    payload = result["payload"]
    assert payload["context"][-1].startswith("# Cookbook: audio.md")
    assert payload["notebook"]["attachments"][0]["excerpt"].startswith("audio notes")
