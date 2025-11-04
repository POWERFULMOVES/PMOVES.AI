from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def parse_model_output(raw_text: str | None) -> Dict[str, Any]:
    if raw_text is None:
        return {}
    cleaned = raw_text.strip()
    if not cleaned:
        return {}
    if cleaned.startswith("```"):
        cleaned = _strip_code_fence(cleaned)
    parsed = _try_json_parse(cleaned)
    if parsed is not None:
        return parsed
    inner = _extract_json_fragment(cleaned)
    if inner:
        parsed = _try_json_parse(inner)
        if parsed is not None:
            return parsed
    return {"summary": cleaned, "notes": [], "sources": []}


def prepare_result(parsed: Dict[str, Any]) -> Tuple[str, List[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[str]]:
    summary = str(parsed.get("summary") or parsed.get("conclusion") or "").strip()
    notes_raw = parsed.get("notes") or parsed.get("findings") or []
    if isinstance(notes_raw, str):
        notes = [notes_raw.strip()] if notes_raw.strip() else []
    else:
        notes = [str(item).strip() for item in notes_raw if str(item).strip()]

    sources_raw = parsed.get("sources") or parsed.get("citations") or []
    sources: List[Dict[str, Any]] = []
    if isinstance(sources_raw, dict):
        sources_raw = [sources_raw]
    for entry in sources_raw:
        if isinstance(entry, str):
            title = entry.strip()
            if title:
                sources.append({"title": title})
            continue
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or entry.get("name") or entry.get("url") or "").strip()
        url = entry.get("url")
        snippet = entry.get("snippet") or entry.get("summary")
        confidence = entry.get("confidence")
        normalized: Dict[str, Any] = {}
        if title:
            normalized["title"] = title
        if isinstance(url, str) and url.strip():
            normalized["url"] = url.strip()
        if isinstance(snippet, str) and snippet.strip():
            normalized["snippet"] = snippet.strip()
        if isinstance(confidence, (int, float)):
            normalized["confidence"] = max(0.0, min(1.0, float(confidence)))
        if normalized:
            sources.append(normalized)
        elif title:
            sources.append({"title": title})

    iterations = None
    steps_raw = parsed.get("steps") or parsed.get("iterations")
    if isinstance(steps_raw, list):
        iterations = []
        for step in steps_raw:
            if isinstance(step, dict):
                iterations.append(step)
            else:
                iterations.append({"detail": str(step)})

    raw_log = parsed.get("raw") or parsed.get("log")
    if isinstance(raw_log, (dict, list)):
        raw_log = json.dumps(raw_log, ensure_ascii=False)
    elif not isinstance(raw_log, str):
        raw_log = None

    return summary, notes, sources, iterations, raw_log


def _strip_code_fence(block: str) -> str:
    parts = block.split("```")
    if len(parts) >= 3:
        return "```".join(parts[1:-1]).strip()
    return block.strip("`")


def _try_json_parse(payload: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _extract_json_fragment(text: str) -> Optional[str]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]
