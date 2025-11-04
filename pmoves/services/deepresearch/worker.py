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

"""Deep Research worker utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


class InvalidResearchRequest(ValueError):
    """Raised when a research request payload cannot be decoded."""


@dataclass(slots=True)
class ResearchRequest:
    """Normalised representation of a deep research job."""

    query: str
    mode: str = "standard"
    max_steps: Optional[int] = None
    context: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    notebook_overrides: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)


def _normalise_context(raw: Any) -> List[Any]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray, dict)):
        return list(raw)
    if isinstance(raw, dict):
        return [raw]
    raise InvalidResearchRequest("context must be a string, mapping, or iterable of items")


def _normalise_metadata(name: str, raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    raise InvalidResearchRequest(f"{name} must be an object when provided")


def _ensure_query(data: Dict[str, Any]) -> str:
    for key in ("query", "prompt", "question", "topic"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise InvalidResearchRequest("request payload must include a non-empty 'query'/'prompt' field")


def _decode_request(payload: Dict[str, Any]) -> ResearchRequest:
    """Validate an incoming envelope and return a :class:`ResearchRequest`."""

    if not isinstance(payload, dict):
        raise InvalidResearchRequest("request envelope must be a dictionary")
    body = payload.get("payload")
    if not isinstance(body, dict):
        raise InvalidResearchRequest("envelope missing payload object")

    query = _ensure_query(body)

    mode = body.get("mode") or "standard"
    if not isinstance(mode, str):
        raise InvalidResearchRequest("mode must be a string")

    max_steps_raw = body.get("max_steps")
    max_steps: Optional[int]
    if max_steps_raw is None:
        max_steps = None
    else:
        if isinstance(max_steps_raw, bool):
            raise InvalidResearchRequest("max_steps must be an integer")
        try:
            max_steps = int(max_steps_raw)
        except (TypeError, ValueError) as exc:
            raise InvalidResearchRequest("max_steps must be an integer") from exc
        if max_steps < 0:
            raise InvalidResearchRequest("max_steps must be >= 0")

    context = _normalise_context(body.get("context"))
    metadata = _normalise_metadata("metadata", body.get("metadata"))
    notebook_overrides = _normalise_metadata("notebook", body.get("notebook"))

    extras = {
        key: value
        for key, value in body.items()
        if key
        not in {
            "query",
            "prompt",
            "question",
            "topic",
            "mode",
            "max_steps",
            "context",
            "metadata",
            "notebook",
        }
    }

    return ResearchRequest(
        query=query,
        mode=mode,
        max_steps=max_steps,
        context=context,
        metadata=metadata,
        notebook_overrides=notebook_overrides,
        extras=extras,
    )


def _handle_request(payload: Dict[str, Any]) -> Tuple[Optional[ResearchRequest], Dict[str, Any]]:
    """Decode the incoming payload, surfacing schema errors in metadata."""

    try:
        request = _decode_request(payload)
    except InvalidResearchRequest as exc:
        return None, {"error": str(exc)}
    return request, dict(request.metadata)
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

from services.common.events import envelope
from .parser import parse_model_output, prepare_result

LOGGER = logging.getLogger("pmoves.deepresearch")
logging.basicConfig(
    level=getattr(logging, os.getenv("DEEPRESEARCH_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

REQUEST_SUBJECT = "research.deepresearch.request.v1"
RESULT_SUBJECT = "research.deepresearch.result.v1"
DEFAULT_MODE = "openrouter"


@dataclass
class ResearchRequest:
    query: str
    mode: str
    max_steps: Optional[int]
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    notebook_overrides: Dict[str, Any]


@dataclass
class ResearchResult:
    query: str
    status: str
    summary: str
    notes: List[str]
    sources: List[Dict[str, Any]]
    mode: str
    metadata: Dict[str, Any]
    raw_log: Optional[str]
    error: Optional[str]
    iterations: Optional[List[Dict[str, Any]]]
    duration_ms: int
    notebook_entry_id: Optional[str] = None

    def as_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": self.query,
            "status": self.status,
            "mode": self.mode,
            "metadata": self.metadata,
            "duration_ms": self.duration_ms,
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.notes:
            payload["notes"] = self.notes
        if self.sources:
            payload["sources"] = self.sources
        if self.raw_log:
            payload["raw_log"] = self.raw_log
        if self.error:
            payload["error"] = self.error
        if self.iterations:
            payload["iterations"] = self.iterations
        if self.notebook_entry_id:
            payload["notebook_entry_id"] = self.notebook_entry_id
        return payload


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


class NotebookPublisher:
    """Mirror research summaries into Open Notebook."""

    def __init__(self) -> None:
        self.base_url = (os.getenv("OPEN_NOTEBOOK_API_URL") or "").rstrip("/")
        self.api_token = os.getenv("OPEN_NOTEBOOK_API_TOKEN") or ""
        self.notebook_id = os.getenv("DEEPRESEARCH_NOTEBOOK_ID") or ""
        self.title_prefix = os.getenv("DEEPRESEARCH_NOTEBOOK_TITLE_PREFIX") or ""
        self.embed = _env_bool("DEEPRESEARCH_NOTEBOOK_EMBED", True)
        self.async_processing = _env_bool("DEEPRESEARCH_NOTEBOOK_ASYNC", True)

    def _merge_overrides(self, overrides: Dict[str, Any]) -> Dict[str, Any]:
        if not overrides:
            overrides = {}
        notebook_id = str(overrides.get("notebook_id") or self.notebook_id or "").strip()
        title_prefix = overrides.get("title_prefix", self.title_prefix)
        embed = overrides.get("embed")
        async_processing = overrides.get("async_processing")
        return {
            "enabled": bool(self.base_url and self.api_token and notebook_id),
            "base_url": self.base_url,
            "token": self.api_token,
            "notebook_id": notebook_id,
            "title_prefix": title_prefix or "",
            "embed": self.embed if embed is None else bool(embed),
            "async_processing": self.async_processing if async_processing is None else bool(async_processing),
        }

    async def publish(self, result: ResearchResult, overrides: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        config = self._merge_overrides(overrides)
        if not config["enabled"]:
            return None, None

        if not result.summary and not result.notes:
            LOGGER.info("Skipping Notebook publish; nothing to persist for query '%s'", result.query)
            return None, None

        title = result.summary.split("\n", 1)[0][:160] if result.summary else result.query[:160]
        if config["title_prefix"]:
            title = f"{config['title_prefix']} · {title}"

        sections: List[str] = []
        if result.summary:
            sections.append(f"## Summary\n{result.summary.strip()}")
        if result.notes:
            notes_block = "\n".join(f"- {note}" for note in result.notes if note)
            if notes_block:
                sections.append(f"## Notes\n{notes_block}")
        if result.sources:
            lines = []
            for src in result.sources:
                title_text = src.get("title") or src.get("url") or "Source"
                snippet = src.get("snippet")
                url = src.get("url")
                if url:
                    line = f"- [{title_text}]({url})"
                else:
                    line = f"- {title_text}"
                if snippet:
                    line += f" — {snippet}"
                lines.append(line)
            if lines:
                sections.append("## Sources\n" + "\n".join(lines))
        if result.raw_log and len(result.raw_log) < 64000:
            sections.append(f"## Raw Output\n````\n{result.raw_log}\n````")

        body = "\n\n".join(section for section in sections if section)

        headers = {
            "Authorization": f"Bearer {config['token']}",
            "Accept": "application/json",
        }
        payload = {
            "type": "text",
            "title": title,
            "notebooks": [config["notebook_id"]],
            "content": body,
            "embed": config["embed"],
            "async_processing": config["async_processing"],
        }
        try:
            async with httpx.AsyncClient(base_url=config["base_url"], headers=headers, timeout=30.0) as client:
                response = await client.post("/api/sources/json", json=payload)
                response.raise_for_status()
                data = response.json()
                entry_id = data.get("id") if isinstance(data, dict) else None
                return entry_id, None
        except httpx.HTTPStatusError as exc:
            LOGGER.error("Notebook publish failed (%s): %s", exc.response.status_code, exc.response.text)
            return None, f"HTTP {exc.response.status_code}"
        except httpx.HTTPError as exc:  # broad but we log above
            LOGGER.error("Notebook publish error: %s", exc)
            return None, str(exc)


class DeepResearchRunner:
    def __init__(self) -> None:
        self.mode = (os.getenv("DEEPRESEARCH_MODE") or DEFAULT_MODE).lower()
        self.timeout = float(os.getenv("DEEPRESEARCH_TIMEOUT", "600"))
        self.openrouter_model = os.getenv("DEEPRESEARCH_OPENROUTER_MODEL", "tongyi-deepresearch")
        self.openrouter_base = (os.getenv("DEEPRESEARCH_OPENROUTER_API_BASE") or os.getenv("OPENROUTER_API_BASE") or "https://openrouter.ai/api").rstrip("/")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY") or ""
        self.openrouter_title = os.getenv("DEEPRESEARCH_OPENROUTER_TITLE", "PMOVES DeepResearch bridge")
        self.openrouter_site = os.getenv("DEEPRESEARCH_OPENROUTER_SITE", "https://pmoves.ai")
        self.api_base = (os.getenv("DEEPRESEARCH_API_BASE") or "http://deepresearch:8080").rstrip("/")
        self.planning_endpoint = os.getenv("DEEPRESEARCH_PLANNING_ENDPOINT", "/api/research")

    async def run(self, request: ResearchRequest) -> ResearchResult:
        start = time.perf_counter()
        mode = (request.mode or self.mode or DEFAULT_MODE).lower()
        metadata = dict(request.metadata or {})
        metadata.setdefault("mode", mode)
        try:
            if mode == "openrouter":
                summary, notes, sources, iterations, raw_log = await self._run_openrouter(request)
                status = "success"
                error = None
            else:
                summary, notes, sources, iterations, raw_log = await self._run_local(request)
                status = "success"
                error = None
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("DeepResearch run failed for query '%s'", request.query)
            duration = int((time.perf_counter() - start) * 1000)
            metadata["error"] = str(exc)
            return ResearchResult(
                query=request.query,
                status="error",
                summary="",
                notes=[],
                sources=[],
                mode=mode,
                metadata=metadata,
                raw_log=None,
                error=str(exc),
                iterations=None,
                duration_ms=duration,
            )

        duration = int((time.perf_counter() - start) * 1000)
        return ResearchResult(
            query=request.query,
            status=status,
            summary=summary,
            notes=notes,
            sources=sources,
            mode=mode,
            metadata=metadata,
            raw_log=raw_log,
            error=error,
            iterations=iterations,
            duration_ms=duration,
        )

    async def _run_openrouter(
        self, request: ResearchRequest
    ) -> Tuple[str, List[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[str]]:
        if not self.openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for openrouter mode")

        system_prompt = (
            "You are Tongyi DeepResearch operating inside the PMOVES agent mesh. "
            "Return a compact JSON object with keys summary (string), notes (array of strings), "
            "sources (array of {title,url,snippet,confidence}), and steps (array describing each iteration). "
            "Focus on actionable findings, keep citations concise, and include confidence between 0 and 1."
        )
        user_payload = {
            "query": request.query,
            "context": request.context,
            "max_steps": request.max_steps,
        }
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": self.openrouter_site,
            "X-Title": self.openrouter_title,
            "Accept": "application/json",
        }
        json_payload = {
            "model": self.openrouter_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, self.timeout))
        async with httpx.AsyncClient(base_url=self.openrouter_base, headers=headers, timeout=timeout) as client:
            response = await client.post("/v1/chat/completions", json=json_payload)
            response.raise_for_status()
            data = response.json()

        content = _extract_message_content(data)
        parsed = parse_model_output(content)
        return prepare_result(parsed)

    async def _run_local(
        self, request: ResearchRequest
    ) -> Tuple[str, List[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[str]]:
        if not self.api_base:
            raise RuntimeError("Set DEEPRESEARCH_API_BASE for local mode")
        payload = {
            "query": request.query,
            "context": request.context,
            "max_steps": request.max_steps,
        }
        timeout = httpx.Timeout(self.timeout, connect=min(10.0, self.timeout))
        async with httpx.AsyncClient(base_url=self.api_base, timeout=timeout) as client:
            response = await client.post(self.planning_endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
        parsed = parse_model_output(json.dumps(data)) if isinstance(data, dict) else parse_model_output(str(data))
        return prepare_result(parsed)


async def _handle_request(msg: Msg, runner: DeepResearchRunner, publisher: NotebookPublisher, nc: NATS) -> None:
    try:
        data = json.loads(msg.data.decode("utf-8"))
        request = _decode_request(data)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.exception("Invalid DeepResearch request: %s", exc)
        return

    result = await runner.run(request)
    entry_id, publish_error = await publisher.publish(result, request.notebook_overrides)
    if entry_id:
        result.notebook_entry_id = entry_id
        result.metadata["notebook"] = {"entry_id": entry_id}
    elif publish_error:
        result.metadata["notebook"] = {"error": publish_error}

    env = envelope(
        RESULT_SUBJECT,
        result.as_payload(),
        correlation_id=data.get("correlation_id"),
        parent_id=data.get("id"),
        source="deepresearch",
    )
    await nc.publish(RESULT_SUBJECT, json.dumps(env).encode("utf-8"))


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    runner = DeepResearchRunner()
    publisher = NotebookPublisher()
    nc = NATS()
    await nc.connect(servers=[nats_url])
    LOGGER.info("DeepResearch worker connected to NATS at %s", nats_url)

    async def cb(msg: Msg) -> None:
        await _handle_request(msg, runner, publisher, nc)

    await nc.subscribe(REQUEST_SUBJECT, cb=cb)
    LOGGER.info("Listening for %s", REQUEST_SUBJECT)

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        LOGGER.info("DeepResearch worker shutting down")
    finally:
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
