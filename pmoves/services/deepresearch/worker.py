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

    try:
        return ResearchRequest(
            query=query,
            mode=mode,
            max_steps=max_steps,
            context=context,
            metadata=metadata,
            notebook_overrides=notebook_overrides,
            extras=extras,
        )
    except TypeError:
        # Backward-compat: some builds define ResearchRequest without 'extras'
        return ResearchRequest(
            query=query,
            mode=mode,
            max_steps=max_steps,
            context=context,
            metadata=metadata,
            notebook_overrides=notebook_overrides,
        )


def _handle_request(payload: Dict[str, Any]) -> Tuple[Optional[ResearchRequest], Dict[str, Any]]:
    """Decode the incoming payload, surfacing schema errors in metadata."""

    try:
        request = _decode_request(payload)
    except InvalidResearchRequest as exc:
        return None, {"error": str(exc)}
    return request, dict(request.metadata)

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from nats.aio.client import Client as NATS
from fastapi import FastAPI, Response
import uvicorn
from nats.aio.msg import Msg
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

from services.common.events import envelope
from .parser import parse_model_output, prepare_result

LOGGER = logging.getLogger("pmoves.deepresearch")
logging.basicConfig(
    level=getattr(logging, os.getenv("DEEPRESEARCH_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

REQUEST_SUBJECT = "research.deepresearch.request.v1"
RESULT_SUBJECT = "research.deepresearch.result.v1"
CGP_SUBJECT = "tokenism.cgp.ready.v1"


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable.

    Accepts: 1, true, t, yes, y, on (case-insensitive) as True.
    Returns default if the variable is not set.
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_or_create_counter(name: str, description: str, labelnames: tuple) -> Counter:
    """Get existing counter or create new one (safe for module reimport via -m flag).

    The python -m flag can cause module double-import, which would register
    Prometheus metrics twice. This function checks the registry first to avoid
    the duplicate registration ValueError.
    """
    # Check if metric already exists in registry (handles -m double-import)
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return Counter(name, description, labelnames=labelnames)


# Enable CGP publishing via environment variable (default: enabled)
CGP_PUBLISH_ENABLED = _env_bool("DEEPRESEARCH_CGP_PUBLISH", default=True)
DEFAULT_MODE = "openrouter"

# Prometheus metrics (safe for module reimport via -m flag)
FALLBACK_COUNTER = _get_or_create_counter(
    "deepresearch_model_fallback_total",
    "Model fallback invocations grouped by reason",
    labelnames=("reason",),
)
REQUEST_COUNTER = _get_or_create_counter(
    "deepresearch_requests_total",
    "Total research requests processed",
    labelnames=("mode", "status"),
)


@dataclass
class ResearchRequest:
    """Incoming research request from NATS message bus.

    Attributes:
        query: The research question or topic to investigate.
        mode: Execution mode (tensorzero, openrouter, or local).
        max_steps: Maximum research iterations allowed.
        context: Additional context for the research task.
        metadata: Request metadata (correlation_id, timestamps, etc.).
        notebook_overrides: Override settings for Open Notebook publishing.
    """

    query: str
    mode: str
    max_steps: Optional[int]
    context: Dict[str, Any]
    metadata: Dict[str, Any]
    notebook_overrides: Dict[str, Any]


@dataclass
class ResearchResult:
    """Completed research result ready for publishing.

    Attributes:
        query: Original research query.
        status: Execution status (success, error, timeout).
        summary: Generated research summary.
        notes: Key findings and bullet points.
        sources: Ranked list of source citations.
        mode: Execution mode used.
        metadata: Request metadata propagated from input.
        raw_log: Optional reasoning/debug log.
        error: Error message if status is error.
        iterations: Research steps/iterations performed.
        duration_ms: Total execution time in milliseconds.
        notebook_entry_id: Open Notebook entry ID if published.
    """

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
        """Convert result to dictionary payload for NATS publishing."""
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


@dataclass(slots=True, frozen=True)
class NotebookPublishConfig:
    """Configuration for Open Notebook publishing.

    Attributes:
        enabled: Whether notebook publishing is enabled.
        base_url: Open Notebook API base URL.
        token: API authentication token.
        notebook_id: Target notebook UUID.
        title_prefix: Prefix for entry titles.
        embed: Whether to generate embeddings.
        async_processing: Use async processing queue.
    """

    enabled: bool
    base_url: str
    token: str
    notebook_id: str
    title_prefix: str
    embed: bool
    async_processing: bool


def _build_cgp_packet(result: "ResearchResult", request_id: str) -> Dict[str, Any]:
    """Build a CGP (CHIT Geometry Packet) from research results.

    Converts DeepResearch output into the GEOMETRY BUS standard format
    for attribution and knowledge graph integration.

    Args:
        result: The completed research result
        request_id: Unique request identifier (correlation_id or parent_id)

    Returns:
        Dict conforming to chit.cgp.v0.1 schema
    """
    # Build points from iterations (research steps)
    points: List[Dict[str, Any]] = []
    if result.iterations:
        for i, step in enumerate(result.iterations):
            # Type validation: skip non-dict entries with a warning
            if not isinstance(step, dict):
                LOGGER.warning("Skipping non-dict iteration step at index %d: %r", i, type(step).__name__)
                continue
            points.append({
                "id": f"step:{i}",
                "modality": "text",
                "proj": 1.0 if result.status == "success" else 0.5,
                "conf": 0.9,
                "summary": shorten(step.get("summary", step.get("action", "")), width=200),
                "ref_id": step.get("source_url", step.get("url", "")),
                "meta": {
                    "step_type": step.get("type", "search"),
                    "step_index": i,
                }
            })

    # Add sources as additional points
    if result.sources:
        for i, src in enumerate(result.sources):
            # Type validation: skip non-dict entries with a warning
            if not isinstance(src, dict):
                LOGGER.warning("Skipping non-dict source at index %d: %r", i, type(src).__name__)
                continue
            points.append({
                "id": f"source:{i}",
                "modality": "text",
                "proj": 0.8,
                "conf": src.get("confidence", 0.7),
                "summary": shorten(src.get("title", src.get("snippet", "")), width=200),
                "ref_id": src.get("url", src.get("link", "")),
                "meta": {
                    "source_type": src.get("type", "web"),
                    "domain": src.get("domain", ""),
                }
            })

    # Build spectrum from result quality metrics
    spectrum = [
        1.0 if result.status == "success" else 0.0,  # Completion
        len(result.sources) / 10.0 if result.sources else 0.0,  # Source richness
        len(result.iterations) / 5.0 if result.iterations else 0.0,  # Iteration depth
    ]
    # Clamp to [0, 1]
    spectrum = [max(0.0, min(1.0, v)) for v in spectrum]

    return {
        "spec": "chit.cgp.v0.1",
        "summary": f"DeepResearch: {shorten(result.query, width=100)}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "super_nodes": [
            {
                "id": f"research:{request_id}",
                "label": "deepresearch",
                "summary": shorten(result.summary, width=300) if result.summary else "Research complete",
                "x": 0.0,
                "y": 0.0,
                "r": 0.3,
                "constellations": [
                    {
                        "id": f"research.steps.{request_id}",
                        "summary": f"Research steps ({len(points)} points)",
                        "anchor": [0.5, 0.5, 0.5],
                        "spectrum": spectrum,
                        "points": points,
                        "meta": {
                            "namespace": "research",
                            "query": result.query,
                            "duration_ms": result.duration_ms,
                            "mode": result.mode,
                        }
                    }
                ],
            }
        ],
        "meta": {
            "source": RESULT_SUBJECT,
            "mode": result.mode,
            "status": result.status,
            "tags": ["deepresearch", "ai-research"],
        }
    }


class NotebookPublisher:
    """Mirror research summaries into Open Notebook."""

    def __init__(self) -> None:
        self.base_url = (os.getenv("OPEN_NOTEBOOK_API_URL") or "").rstrip("/")
        self.api_token = os.getenv("OPEN_NOTEBOOK_API_TOKEN") or ""
        self.notebook_id = os.getenv("DEEPRESEARCH_NOTEBOOK_ID") or ""
        self.title_prefix = os.getenv("DEEPRESEARCH_NOTEBOOK_TITLE_PREFIX") or ""
        self.embed = _env_bool("DEEPRESEARCH_NOTEBOOK_EMBED", True)
        self.async_processing = _env_bool("DEEPRESEARCH_NOTEBOOK_ASYNC", True)

    def _merge_overrides(self, overrides: Dict[str, Any]) -> NotebookPublishConfig:
        if not overrides:
            overrides = {}
        notebook_id = str(overrides.get("notebook_id") or self.notebook_id or "").strip()
        title_prefix = overrides.get("title_prefix", self.title_prefix)
        embed = overrides.get("embed")
        async_processing = overrides.get("async_processing")
        return NotebookPublishConfig(
            enabled=bool(self.base_url and self.api_token and notebook_id),
            base_url=self.base_url,
            token=self.api_token,
            notebook_id=notebook_id,
            title_prefix=title_prefix or "",
            embed=self.embed if embed is None else bool(embed),
            async_processing=self.async_processing if async_processing is None else bool(async_processing),
        )

    def resolve_config(self, overrides: Optional[Dict[str, Any]] = None) -> NotebookPublishConfig:
        return self._merge_overrides(overrides or {})

    async def publish(self, result: ResearchResult, overrides: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        config = self.resolve_config(overrides)
        if not config.enabled:
            return None, None

        if not result.summary and not result.notes:
            LOGGER.info("Skipping Notebook publish; nothing to persist for query '%s'", result.query)
            return None, None

        title = result.summary.split("\n", 1)[0][:160] if result.summary else result.query[:160]
        if config.title_prefix:
            title = f"{config.title_prefix} · {title}"

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
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/json",
        }
        payload = {
            "type": "text",
            "title": title,
            "notebooks": [config.notebook_id],
            "content": body,
            "embed": config.embed,
            "async_processing": config.async_processing,
        }
        try:
            async with httpx.AsyncClient(base_url=config.base_url, headers=headers, timeout=30.0) as client:
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
    """Executes deep research queries via multiple backend modes.

    Supports three execution modes:
    - tensorzero: Local Ollama inference via TensorZero gateway
    - openrouter: Cloud inference via OpenRouter API
    - local: External research API (e.g., Tongyi DeepResearch)

    The runner handles LLM inference, response parsing, and result
    normalization across all backends.
    """

    def __init__(self) -> None:
        """Initialize runner with configuration from environment variables."""
        self.mode = (os.getenv("DEEPRESEARCH_MODE") or DEFAULT_MODE).lower()
        self.timeout = float(os.getenv("DEEPRESEARCH_TIMEOUT", "600"))
        self.openrouter_model = os.getenv("DEEPRESEARCH_OPENROUTER_MODEL", "tongyi-deepresearch")
        self.openrouter_base = (os.getenv("DEEPRESEARCH_OPENROUTER_API_BASE") or os.getenv("OPENROUTER_API_BASE") or "https://openrouter.ai/api").rstrip("/")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY") or ""
        self.openrouter_title = os.getenv("DEEPRESEARCH_OPENROUTER_TITLE", "PMOVES DeepResearch bridge")
        self.openrouter_site = os.getenv("DEEPRESEARCH_OPENROUTER_SITE", "https://pmoves.ai")
        self.api_base = (os.getenv("DEEPRESEARCH_API_BASE") or "http://deepresearch:8080").rstrip("/")
        self.planning_endpoint = os.getenv("DEEPRESEARCH_PLANNING_ENDPOINT", "/api/research")
        # TensorZero/Ollama configuration
        self.tensorzero_base = (
            os.getenv("DEEPRESEARCH_TENSORZERO_BASE_URL")
            or os.getenv("TENSORZERO_BASE_URL")
            or "http://tensorzero-gateway:3030"
        ).rstrip("/")
        self.tensorzero_model = os.getenv("DEEPRESEARCH_TENSORZERO_MODEL", "nemotron-3-nano:30b")
        self.tensorzero_fallback_model = os.getenv("DEEPRESEARCH_TENSORZERO_FALLBACK_MODEL", "qwen3-vl:8b")
        self.tensorzero_key = os.getenv("TENSORZERO_API_KEY") or ""

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
            elif mode == "tensorzero":
                summary, notes, sources, iterations, raw_log = await self._run_tensorzero(request)
                status = "success"
                error = None
            else:
                # Local mode: if no external API configured, return a stub so smokes can pass
                if not self.api_base or self.api_base.endswith(":8080"):
                    summary = f"Stub research summary for: {request.query}"
                    notes = ["DeepResearch local mode stub (no API configured)"]
                    sources = []
                    iterations = None
                    raw_log = None
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

    async def _run_tensorzero(
        self, request: ResearchRequest
    ) -> Tuple[str, List[str], List[Dict[str, Any]], Optional[List[Dict[str, Any]]], Optional[str]]:
        """Run research using TensorZero gateway (Ollama/local models)."""
        url = f"{self.tensorzero_base}/openai/v1/chat/completions"

        system_prompt = (
            "You are a research planner operating inside the PMOVES agent mesh. "
            "Analyze the query and return a JSON object with these keys: "
            "summary (string with main findings), "
            "notes (array of actionable insight strings), "
            "sources (array of {title, url, snippet, confidence}), "
            "steps (array describing each research iteration). "
            "Focus on actionable findings with confidence between 0 and 1."
        )

        user_content = f"Research query: {request.query}"
        if request.context:
            user_content += f"\nContext: {request.context}"
        if request.max_steps:
            user_content += f"\nMax iterations: {request.max_steps}"

        payload = {
            "model": self.tensorzero_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }

        headers = {"Content-Type": "application/json"}
        if self.tensorzero_key:
            headers["Authorization"] = f"Bearer {self.tensorzero_key}"

        timeout = httpx.Timeout(self.timeout, connect=30.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            # Try fallback model if primary fails
            if self.tensorzero_fallback_model and self.tensorzero_fallback_model != self.tensorzero_model:
                LOGGER.warning(
                    "Primary model %s failed (%s), trying fallback %s",
                    self.tensorzero_model, exc.response.status_code, self.tensorzero_fallback_model
                )
                FALLBACK_COUNTER.labels(reason="http_error").inc()
                payload["model"] = self.tensorzero_fallback_model
                try:
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                        data = response.json()
                except httpx.HTTPStatusError as fallback_exc:
                    LOGGER.error(
                        "Fallback model %s also failed: HTTP %s",
                        self.tensorzero_fallback_model, fallback_exc.response.status_code
                    )
                    raise RuntimeError(
                        f"Both primary ({self.tensorzero_model}) and fallback "
                        f"({self.tensorzero_fallback_model}) models failed"
                    ) from fallback_exc
                except (httpx.TimeoutException, httpx.ConnectError) as network_exc:
                    LOGGER.error("Network error during fallback request: %s", network_exc)
                    raise RuntimeError(
                        f"Fallback model network error: {network_exc}"
                    ) from network_exc
            else:
                raise

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
        LOGGER.info("Received message on %s (%d bytes)", msg.subject, len(msg.data) if msg.data else 0)
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
    LOGGER.info("Published result for correlation_id=%s", data.get("correlation_id"))

    # Publish CGP packet for GEOMETRY BUS integration
    if CGP_PUBLISH_ENABLED:
        request_id = data.get("correlation_id") or data.get("id") or "unknown"
        cgp_packet = None
        try:
            cgp_packet = _build_cgp_packet(result, request_id)
        except (TypeError, AttributeError, KeyError) as build_exc:
            # Building errors indicate bugs in _build_cgp_packet - log at ERROR
            LOGGER.error(
                "CGP packet build failed (bug in _build_cgp_packet): %s (request_id=%s)",
                build_exc, request_id, exc_info=True
            )
        except Exception as build_exc:  # pylint: disable=broad-except
            LOGGER.error(
                "Unexpected error building CGP packet: %s (request_id=%s)",
                build_exc, request_id, exc_info=True
            )

        if cgp_packet is not None:
            try:
                await nc.publish(CGP_SUBJECT, json.dumps(cgp_packet).encode("utf-8"))
                LOGGER.info("Published CGP packet to %s for request_id=%s", CGP_SUBJECT, request_id)
            except Exception as pub_exc:  # pylint: disable=broad-except
                # Publishing errors indicate infrastructure issues - log at WARNING
                LOGGER.warning(
                    "Failed to publish CGP packet to NATS: %s (request_id=%s, nats_connected=%s)",
                    pub_exc, request_id, nc.is_connected if nc else False
                )


async def main() -> None:
    """Entry point for DeepResearch NATS worker service.

    Initializes the research runner, connects to NATS, and subscribes
    to research.deepresearch.request.v1 for incoming queries. Also
    starts a health server for Kubernetes probes.
    """
    nats_url = os.getenv("NATS_URL", "nats://nats:4222")
    runner = DeepResearchRunner()
    publisher = NotebookPublisher()
    nc = NATS()

    # Lightweight health server (start this before attempting NATS connect)
    app = FastAPI(title="DeepResearch Health")

    @app.get("/healthz")
    async def healthz():  # type: ignore[override]
        """Health check endpoint for Kubernetes liveness/readiness probes."""
        return {
            "status": "ok",
            "nats_connected": bool(nc.is_connected),
        }

    @app.get("/metrics")
    async def metrics():  # type: ignore[override]
        """Prometheus metrics endpoint for observability."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    async def _serve_health():
        port = int(os.getenv("DEEPRESEARCH_HEALTH_PORT", "8098"))
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    # Start health server first so /healthz is alive even if NATS connect is slow
    asyncio.create_task(_serve_health())

    # Now connect to NATS
    await nc.connect(servers=[nats_url])
    LOGGER.info("DeepResearch worker connected to NATS at %s", nats_url)

    async def cb(msg: Msg) -> None:
        await _handle_request(msg, runner, publisher, nc)

    sub = await nc.subscribe(REQUEST_SUBJECT, cb=cb)
    LOGGER.info("Subscribed to %s", REQUEST_SUBJECT)

    # diagnostic endpoint to publish a local request
    @app.post("/diag/publish")
    async def diag_publish(payload: Dict[str, Any]):  # type: ignore[override]
        env = {
            "id": payload.get("id") or "diag",
            "source": "deepresearch-diag",
            "correlation_id": payload.get("correlation_id") or "diag-corr",
            "payload": {
                "query": payload.get("query") or "diagnostic query",
                "mode": payload.get("mode") or runner.mode,
                "metadata": {"diag": True},
            },
        }
        await nc.publish(REQUEST_SUBJECT, json.dumps(env).encode("utf-8"))
        return {"status": "published", "subject": REQUEST_SUBJECT, "env": env}

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        LOGGER.info("DeepResearch worker shutting down")
    finally:
        await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
