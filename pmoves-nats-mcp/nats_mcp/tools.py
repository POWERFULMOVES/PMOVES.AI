"""MCP tool definitions and handlers for the PMOVES NATS bridge."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import nats
from mcp.types import TextContent, Tool


def _nats_url() -> str:
    return os.environ.get("NATS_URL", "nats://nats:pmoves@127.0.0.1:4222")


async def _publish(subject: str, payload: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    nc = await nats.connect(_nats_url(), name="pmoves-nats-mcp")
    try:
        await nc.publish(subject, payload.encode("utf-8"), headers=headers)
        await nc.flush(timeout=2)
        return {"published": True, "subject": subject, "bytes": len(payload)}
    finally:
        await nc.close()


async def _subscribe(subject: str, timeout_seconds: int, max_messages: int) -> list[dict[str, Any]]:
    nc = await nats.connect(_nats_url(), name="pmoves-nats-mcp-sub")
    captured: list[dict[str, Any]] = []
    try:
        sub = await nc.subscribe(subject)
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while len(captured) < max_messages:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                break
            try:
                msg = await asyncio.wait_for(sub.next_msg(timeout=remaining), timeout=remaining)
            except (asyncio.TimeoutError, nats.errors.TimeoutError):
                break
            captured.append({
                "subject": msg.subject,
                "data": msg.data.decode("utf-8", errors="replace"),
                "reply": msg.reply or None,
            })
        await sub.unsubscribe()
        return captured
    finally:
        await nc.close()


async def handle_publish(subject: str, payload: str, headers: dict[str, str] | None = None) -> list[TextContent]:
    if not subject or not isinstance(subject, str):
        return [TextContent(type="text", text=json.dumps({"error": "subject is required"}))]
    result = await _publish(subject, payload or "", headers)
    return [TextContent(type="text", text=json.dumps(result))]


async def handle_subscribe(
    subject: str,
    timeout_seconds: int = 5,
    max_messages: int = 10,
) -> list[TextContent]:
    if not subject or not isinstance(subject, str):
        return [TextContent(type="text", text=json.dumps({"error": "subject is required"}))]
    timeout_seconds = max(1, min(int(timeout_seconds), 60))
    max_messages = max(1, min(int(max_messages), 100))
    messages = await _subscribe(subject, timeout_seconds, max_messages)
    return [TextContent(
        type="text",
        text=json.dumps({"subject": subject, "received": len(messages), "messages": messages}),
    )]


TOOLS: list[Tool] = [
    Tool(
        name="nats_publish",
        description=(
            "Publish a message to a NATS subject on the PMOVES event bus. "
            "Subjects follow `<domain>.<entity>.<event>.v<n>` (e.g. `archon.mint.agent.v1`). "
            "Use for fire-and-forget events; for request/reply use a subscribe loop with a reply subject."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "NATS subject (e.g. archon.mint.agent.v1)"},
                "payload": {"type": "string", "description": "Message body (JSON-encoded string recommended)"},
                "headers": {
                    "type": "object",
                    "description": "Optional NATS headers",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["subject", "payload"],
        },
    ),
    Tool(
        name="nats_subscribe",
        description=(
            "Subscribe to a NATS subject (supports wildcards `*` and `>`), wait up to timeout_seconds, "
            "and return up to max_messages captured payloads. Useful for verifying mint flows, "
            "tailing CHIT signed events, or auditing live JetStream traffic."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject or wildcard pattern"},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 60, "default": 5},
                "max_messages": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
            },
            "required": ["subject"],
        },
    ),
]


TOOL_HANDLERS = {
    "nats_publish": handle_publish,
    "nats_subscribe": handle_subscribe,
}
