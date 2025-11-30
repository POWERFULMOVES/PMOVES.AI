"""Utilities for parsing the deep research model output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_blob(text: str) -> str:
    """Return the JSON blob embedded in ``text``.

    The model frequently returns markdown fenced blocks or wraps the JSON payload in
    additional commentary. The helper searches for fenced blocks first and falls back
    to locating the first well-formed object in the string.
    """

    fenced = _JSON_FENCE_RE.search(text)
    if fenced:
        candidate = fenced.group(1).strip()
        if candidate:
            return candidate

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    brace_match = _JSON_OBJECT_RE.search(stripped)
    if brace_match:
        return brace_match.group(0)

    raise ValueError("Unable to locate JSON payload in model output")


def parse_model_output(raw_output: str) -> Dict[str, Any]:
    """Parse the model output into a dictionary.

    The function extracts the first JSON blob that appears in ``raw_output`` and
    returns the decoded dictionary. A :class:`ValueError` is raised when the text does
    not contain a valid JSON structure.
    """

    blob = _extract_json_blob(raw_output)
    return json.loads(blob)


def _normalise_source(source: Any) -> Dict[str, Any]:
    """Normalise an individual source entry."""

    if isinstance(source, dict):
        score = source.get("score")
        if score is None:
            score = source.get("relevance")
        try:
            score_value = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_value = 0.0
        return {
            "title": str(source.get("title", "")),
            "url": str(source.get("url", "")),
            "score": score_value,
            "excerpt": str(source.get("excerpt") or source.get("snippet") or ""),
        }

    if isinstance(source, str):
        return {"title": "", "url": source, "score": 0.0, "excerpt": ""}

    raise TypeError(f"Unsupported source entry type: {type(source)!r}")


def prepare_result(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare the final result payload consumed by downstream services."""

    summary = (
        parsed.get("summary")
        or parsed.get("answer")
        or parsed.get("result")
        or ""
    )

    sources: Iterable[Any] = parsed.get("sources") or []
    normalised_sources: List[Dict[str, Any]] = [_normalise_source(item) for item in sources]
    normalised_sources.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    result: Dict[str, Any] = {
        "summary": summary,
        "sources": normalised_sources,
    }

    if "query" in parsed:
        result["query"] = parsed["query"]
    if "reasoning" in parsed:
        result["reasoning"] = parsed["reasoning"]

    return result
