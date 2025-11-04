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
