"""PMOVES.Notes extension — auto-save conversation summaries.

Runs at ``message_loop_end``. Conforms to the Agent Zero extension API:
subclass ``helpers.extension.Extension`` and implement
``async def execute(self, loop_data=LoopData(), **kwargs)``. Discovered because
it lives under ``extensions/python/message_loop_end/`` and subclasses
``Extension``. The persist call runs in a background task so it never blocks the
agent's message loop.
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


def _enabled() -> bool:
    return os.getenv("PMOVES_NOTES_ENABLED", "true").lower() == "true"


def _notebook_api_url() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_URL", "http://open-notebook:5055")


def _notebook_token() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_TOKEN", "")


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


async def _save_conversation(agent_name: str, content: str) -> None:
    """Persist a conversation summary to Open Notebook (runs in background task)."""
    if not content.strip():
        return

    first_line = content.splitlines()[0] if content.splitlines() else content
    title = f"Conversation with {agent_name}: " + (
        (first_line[:50] + "...") if len(first_line) > 50 else first_line
    )
    # Open Notebook POST /api/notes accepts {content, title, note_type} only.
    # These summaries are machine-generated -> note_type "ai". Tags are folded
    # into the body since the notes API has no tags field.
    body = content + "\n\n_tags: conversation, auto-saved, " + agent_name.lower() + "_"
    note = {
        "content": body,
        "title": title,
        "note_type": "ai",
    }

    api_url = _notebook_api_url()
    token = _notebook_token()
    headers = {"Content-Type": "application/json"}
    if token:
        if api_url.lower().startswith("http://"):
            PrintStyle(font_color="yellow").print(
                "[PMOVES.Notes] WARNING: OPEN_NOTEBOOK_API_TOKEN is set but "
                "OPEN_NOTEBOOK_API_URL uses plaintext http:// — the bearer token "
                "will be sent unencrypted. Use https:// for non-internal endpoints."
            )
        headers["Authorization"] = f"Bearer {token}"

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
                        f"[PMOVES.Notes] auto-save failed: HTTP {resp.status} — {detail}"
                    )
                    return
                result = await resp.json()
    except Exception as exc:  # noqa: BLE001 — never disturb the agent loop
        PrintStyle(font_color="yellow").print(f"[PMOVES.Notes] auto-save error: {exc}")
        return

    await _publish_nats_event(
        "agent.notes.saved.v1",
        {
            "note_id": result.get("id", "unknown"),
            "title": title,
            "tags": ["conversation", "auto-saved"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


class AutoSaveConversation(Extension):
    """Auto-save the conversation summary after each message loop."""

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs) -> None:
        if not self.agent or not _enabled():
            return
        # Skip ephemeral background contexts.
        if self.agent.context.type == AgentContextType.BACKGROUND:
            return

        try:
            content = self.agent.history.output_text()
        except Exception as exc:  # noqa: BLE001
            PrintStyle(font_color="yellow").print(
                f"[PMOVES.Notes] could not read history: {exc}"
            )
            return

        agent_name = getattr(self.agent, "agent_name", "Agent")
        # Fire-and-forget so note persistence never blocks the message loop.
        DeferredTask(thread_name=THREAD_BACKGROUND).start_task(
            _save_conversation, agent_name, content
        )
