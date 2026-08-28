"""PMOVES.Notes extension — persist the agent's reasoning trace.

Runs at ``reasoning_stream_end`` (fired after the chat model call completes).
Reads the full reasoning stashed by the ``reasoning_stream`` capture hook,
persists it to Open Notebook in a background task, and clears the stash. Skips
ephemeral BACKGROUND contexts so internal background reasoning is not surfaced
as user-visible notes.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from agent import AgentContextType, LoopData
from helpers.defer import THREAD_BACKGROUND, DeferredTask
from helpers.extension import Extension
from helpers.print_style import PrintStyle

REASONING_DATA_KEY = "_pmoves_notes_reasoning"


def _enabled() -> bool:
    return os.getenv("PMOVES_NOTES_ENABLED", "true").lower() == "true"


def _min_length() -> int:
    try:
        return int(os.getenv("PMOVES_NOTES_MIN_REASONING_LENGTH", "100"))
    except (TypeError, ValueError):
        return 100


def _notebook_api_url() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_URL", "http://open-notebook:5055")


def _notebook_token() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_TOKEN", "")


def _build_headers(api_url: str, token: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        if api_url.lower().startswith("http://"):
            PrintStyle(font_color="yellow").print(
                "[PMOVES.Notes] WARNING: OPEN_NOTEBOOK_API_TOKEN is set but "
                "OPEN_NOTEBOOK_API_URL uses plaintext http:// — the bearer token "
                "will be sent unencrypted. Use https:// for non-internal endpoints."
            )
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _publish_nats_event(subject: str, data: dict[str, Any]) -> None:
    try:
        import nats  # lazy import: optional dependency

        nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222"))
        try:
            await nc.publish(subject, json.dumps(data).encode())
        finally:
            await nc.close()
    except Exception as exc:  # noqa: BLE001 — best-effort
        PrintStyle(font_color="yellow").print(
            f"[PMOVES.Notes] NATS publish to {subject} failed: {exc}"
        )


async def _save_reasoning_trace(agent_name: str, reasoning: str) -> None:
    stamp = datetime.now(timezone.utc)
    # Open Notebook POST /api/notes accepts {content, title, note_type} only.
    # Reasoning traces are machine-generated -> note_type "ai"; tags fold into body.
    note = {
        "title": f"Reasoning Trace — {agent_name} — {stamp.strftime('%Y-%m-%d %H:%M')}",
        "content": (
            f"# Agent Reasoning Trace\n\n"
            f"**Agent**: {agent_name}\n"
            f"**Timestamp**: {stamp.isoformat()}\n\n"
            f"## Reasoning\n\n{reasoning}\n\n"
            f"_tags: reasoning, trace, {agent_name.lower()}, memory_"
        ),
        "note_type": "ai",
    }

    api_url = _notebook_api_url()
    headers = _build_headers(api_url, _notebook_token())

    try:
        import aiohttp  # lazy import

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/api/notes",
                json=note,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    detail = await resp.text()
                    PrintStyle(font_color="yellow").print(
                        f"[PMOVES.Notes] reasoning-trace save failed: HTTP {resp.status} — {detail}"
                    )
                    return
                result = await resp.json()
    except Exception as exc:  # noqa: BLE001 — never disturb the agent loop
        PrintStyle(font_color="yellow").print(
            f"[PMOVES.Notes] reasoning-trace error: {exc}"
        )
        return

    note_id = result.get("id", "unknown") if isinstance(result, dict) else "unknown"
    await _publish_nats_event(
        "agent.notes.saved.v1",
        {
            "note_id": note_id,
            "title": note["title"],
            "tags": ["reasoning", "trace"],
            "timestamp": stamp.isoformat(),
        },
    )


class SaveReasoningTrace(Extension):
    """Persist the captured reasoning trace to Open Notebook after the stream ends."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs) -> None:
        if not self.agent or not _enabled():
            return
        # Skip ephemeral background contexts — do not surface internal reasoning.
        if self.agent.context.type == AgentContextType.BACKGROUND:
            return

        reasoning = self.agent.get_data(REASONING_DATA_KEY) or ""
        # Clear the stash regardless so traces never bleed across iterations.
        self.agent.set_data(REASONING_DATA_KEY, None)

        if not isinstance(reasoning, str) or len(reasoning) < _min_length():
            return

        agent_name = getattr(self.agent, "agent_name", "Agent")
        DeferredTask(thread_name=THREAD_BACKGROUND).start_task(
            _save_reasoning_trace, agent_name, reasoning
        )
