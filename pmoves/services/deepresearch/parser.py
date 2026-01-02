"""Utilities for parsing the deep research model output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def prepare_result(
    parsed: Dict[str, Any]
) -> Tuple[str, List[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[str]]:
    """Prepare the final result payload consumed by downstream services.

    Args:
        parsed: Dictionary from parse_model_output containing raw LLM response data.

    Returns:
        A tuple containing:
        - summary (str): Main research finding from 'summary', 'answer', or 'result' keys.
        - notes (List[str]): Actionable findings from 'notes' or 'findings' keys.
        - sources (List[Dict]): Normalized source dicts with keys: title, url, score, excerpt.
        - iterations (Optional[List[Dict]]): Research step dicts from 'iterations'/'steps', or None.
        - raw_log (Optional[str]): Debug/reasoning log from 'raw_log'/'reasoning', or None.

    Raises:
        TypeError: If parsed is not a dictionary (from parse_model_output failure).
    """
    if not isinstance(parsed, dict):
        raise TypeError(f"Expected dict from parse_model_output, got {type(parsed).__name__}")

    summary = str(
        parsed.get("summary")
        or parsed.get("answer")
        or parsed.get("result")
        or ""
    )

    # Extract notes from parsed data
    notes_raw = parsed.get("notes") or parsed.get("findings") or []
    notes: List[str] = [str(n) for n in notes_raw] if isinstance(notes_raw, list) else []

    # Normalise sources
    sources_raw: Iterable[Any] = parsed.get("sources") or []
    normalised_sources: List[Dict[str, Any]] = [_normalise_source(item) for item in sources_raw]
    normalised_sources.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    # Extract iterations/steps if present
    iterations_raw = parsed.get("iterations") or parsed.get("steps") or None
    iterations: Optional[List[Dict[str, Any]]] = None
    if isinstance(iterations_raw, list):
        iterations = [dict(step) if isinstance(step, dict) else {"step": str(step)} for step in iterations_raw]

    # Raw log for debugging
    raw_log: Optional[str] = parsed.get("raw_log") or parsed.get("reasoning") or None

    return (summary, notes, normalised_sources, iterations, raw_log)
