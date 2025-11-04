"""Utilities for interacting with OpenRouter from the DeepResearch worker."""

from __future__ import annotations

import json
from textwrap import shorten
from typing import Any, Dict, List


def _collect_text(value: Any, output: List[str]) -> None:
    """Recursively collect text-like content from OpenAI-style message payloads."""
    if not value:
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            output.append(text)
        return
    if isinstance(value, list):
        for item in value:
            _collect_text(item, output)
        return
    if isinstance(value, dict):
        # Prefer explicit text/value keys before falling back to nested content.
        for key in ("text", "value", "content"):
            if key in value:
                _collect_text(value[key], output)
                return
        # Some tool payloads wrap the actual data deeper in nested structures.
        for key in ("message", "data"):
            if key in value:
                _collect_text(value[key], output)
        return


def _extract_message_content(response: Dict[str, Any]) -> str:
    """Return the assistant message content from an OpenRouter chat-completions payload."""
    if not isinstance(response, dict):
        return ""

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    choice = choices[0] or {}
    if not isinstance(choice, dict):
        return ""

    message = choice.get("message")
    if not isinstance(message, dict):
        text_choice = choice.get("text")
        return text_choice.strip() if isinstance(text_choice, str) else ""

    fragments: List[str] = []
    _collect_text(message.get("content"), fragments)

    if not fragments:
        text_choice = choice.get("text")
        if isinstance(text_choice, str) and text_choice.strip():
            fragments.append(text_choice.strip())

    if fragments:
        return "\n".join(fragments)

    function_call = message.get("function_call")
    function_fragments: List[str] = []
    if isinstance(function_call, dict):
        name = function_call.get("name")
        arguments = function_call.get("arguments")
        parts = []
        if isinstance(name, str) and name.strip():
            parts.append(name.strip())
        if isinstance(arguments, str) and arguments.strip():
            parts.append(arguments.strip())
        if parts:
            function_fragments.append(" ".join(parts))

    tool_calls = message.get("tool_calls")
    if isinstance(tool_calls, list):
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            call_type = call.get("type")
            if call_type == "function":
                function = call.get("function") or {}
                name = function.get("name")
                arguments = function.get("arguments")
                name_text = name.strip() if isinstance(name, str) else ""
                args_text = arguments.strip() if isinstance(arguments, str) else ""
                if name_text and args_text:
                    function_fragments.append(f"{name_text}({args_text})")
                elif name_text:
                    function_fragments.append(name_text)
                elif args_text:
                    function_fragments.append(args_text)
            else:
                collected: List[str] = []
                _collect_text(call.get("output"), collected)
                if collected:
                    function_fragments.append("\n".join(collected))

    if function_fragments:
        return "\n".join(function_fragments)

    return ""


def _summarise_response(payload: Dict[str, Any]) -> str:
    """Return a compact string representation of an OpenRouter payload for error messages."""
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        raw = repr(payload)
    return shorten(raw, width=300, placeholder="…")


def _run_openrouter(response: Dict[str, Any]) -> str:
    """Return assistant content from an OpenRouter chat response, raising when missing."""
    content = _extract_message_content(response)
    if not content:
        summary = _summarise_response(response)
        raise ValueError(
            "OpenRouter response did not contain assistant content. "
            f"Payload preview: {summary}"
        )
    return content

