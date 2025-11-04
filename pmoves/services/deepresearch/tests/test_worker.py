"""Tests for the DeepResearch OpenRouter helpers."""

from __future__ import annotations

import sys
"""Tests for the deep research worker helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from pmoves.services.deepresearch.worker import _extract_message_content, _run_openrouter


def test_extract_message_content_returns_plain_text() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The capital of France is Paris.",
                }
            }
        ]
    }

    assert (
        _extract_message_content(response)
        == "The capital of France is Paris."
    )


def test_extract_message_content_handles_tool_call_arguments() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "search",
                                "arguments": '{"query": "openrouter"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    assert (
        _extract_message_content(response)
        == 'search({"query": "openrouter"})'
    )


def test_run_openrouter_raises_when_content_missing() -> None:
    response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                }
            }
        ]
    }

    with pytest.raises(ValueError) as exc:
        _run_openrouter(response)

    assert "did not contain assistant content" in str(exc.value)
from pmoves.services.deepresearch.worker import (
    InvalidResearchRequest,
    ResearchRequest,
    _decode_request,
    _handle_request,
)

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "contracts" / "samples" / "research"


def test_decode_request_minimal_envelope():
    request = _decode_request({"payload": {"query": "Map PMOVES research milestones"}})
    assert isinstance(request, ResearchRequest)
    assert request.query == "Map PMOVES research milestones"
    assert request.mode == "standard"
    assert request.max_steps is None
    assert request.context == []
    assert request.metadata == {}
    assert request.notebook_overrides == {}
    assert request.extras == {}


def test_decode_request_casts_max_steps_and_context_string():
    request = _decode_request(
        {
            "payload": {
                "query": "Explain PMOVES research agenda",
                "max_steps": "5",
                "context": "Use published docs",
                "metadata": {"priority": "high"},
            }
        }
    )
    assert request.max_steps == 5
    assert request.context == ["Use published docs"]
    assert request.metadata == {"priority": "high"}


@pytest.mark.parametrize("sample_path", sorted(SAMPLES_DIR.glob("*.json")))
def test_decode_request_from_samples(sample_path: Path):
    envelope = json.loads(sample_path.read_text())
    request = _decode_request(envelope)
    assert isinstance(request, ResearchRequest)
    assert request.query
    assert isinstance(request.notebook_overrides, dict)
    assert "notebook" not in request.extras
    if "max_steps" in envelope.get("payload", {}):
        assert isinstance(request.max_steps, int)
    if "deliverable" in envelope.get("payload", {}):
        assert request.extras.get("deliverable") == envelope["payload"]["deliverable"]


def test_decode_request_rejects_bad_metadata():
    with pytest.raises(InvalidResearchRequest):
        _decode_request({"payload": {"query": "Test", "metadata": []}})


def test_handle_request_reports_error():
    request, metadata = _handle_request({"payload": {}})
    assert request is None
    assert metadata["error"].startswith("request payload")


def test_handle_request_returns_metadata_copy():
    envelope = {"payload": {"query": "What is PMOVES?", "metadata": {"ticket": "R-42"}}}
    request, metadata = _handle_request(envelope)
    assert isinstance(request, ResearchRequest)
    assert metadata == {"ticket": "R-42"}
    assert metadata is not request.metadata
