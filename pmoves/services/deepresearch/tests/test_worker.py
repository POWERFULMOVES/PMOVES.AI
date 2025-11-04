"""Tests for the DeepResearch OpenRouter helpers."""

from __future__ import annotations

import sys
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
