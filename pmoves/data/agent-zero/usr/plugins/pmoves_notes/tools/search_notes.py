"""PMOVES.Notes tool — search notes in Open Notebook.

Conforms to the Agent Zero tool API: subclass ``helpers.tool.Tool`` and
implement ``async def execute(...) -> Response``. Discovered by file name
(``tools/search_notes.py`` -> tool name ``search_notes``).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from helpers.print_style import PrintStyle
from helpers.tool import Response, Tool


def _notebook_api_url() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_URL", "http://open-notebook:5055")


def _notebook_token() -> str:
    return os.getenv("OPEN_NOTEBOOK_API_TOKEN", "")


def _build_headers(api_url: str, token: str) -> dict[str, str]:
    """Build request headers, warning if a token would be sent over plaintext HTTP."""
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


async def publish_nats_event(subject: str, data: dict[str, Any]) -> None:
    """Best-effort NATS publish; never raises into the caller."""
    try:
        import nats  # lazy import: optional dependency

        nc = await nats.connect(os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222"))
        try:
            await nc.publish(subject, json.dumps(data).encode())
        finally:
            await nc.close()
    except Exception as exc:  # noqa: BLE001 — event publishing is best-effort
        PrintStyle(font_color="yellow").print(
            f"[PMOVES.Notes] NATS publish to {subject} failed: {exc}"
        )


class SearchNotes(Tool):
    """Search PMOVES.AI Open Notebook (persistent knowledge base) for notes."""

    async def execute(
        self,
        query: str = "",
        limit: int = 10,
        **kwargs,
    ) -> Response:
        if query is None:
            query = ""
        query = query if isinstance(query, str) else str(query)
        query = query.strip()
        if not query:
            return Response(
                message="search_notes error: 'query' is required.", break_loop=False
            )

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10

        # Open Notebook search is POST /api/search (SearchRequest), not a notes
        # sub-route. Scope to notes (not sources) and request text search.
        payload = {
            "query": query,
            "type": "text",
            "limit": min(max(limit, 1), 50),
            "search_sources": False,
            "search_notes": True,
        }

        api_url = _notebook_api_url()
        headers = _build_headers(api_url, _notebook_token())

        try:
            import aiohttp  # lazy import: keeps import errors out of tool discovery

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{api_url}/api/search",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        detail = await resp.text()
                        return Response(
                            message=f"search_notes failed: HTTP {resp.status} — {detail}",
                            break_loop=False,
                        )
                    results = await resp.json()
        except Exception as exc:  # noqa: BLE001 — surface as tool message, never crash loop
            return Response(message=f"search_notes error: {exc}", break_loop=False)

        raw_notes = results.get("results", []) if isinstance(results, dict) else []
        if not isinstance(raw_notes, list):
            raw_notes = []

        summary = []
        for n in raw_notes:
            if not isinstance(n, dict):
                continue
            content = n.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            summary.append(
                {
                    "id": n.get("id"),
                    "title": n.get("title"),
                    "snippet": (content[:200] + "...") if len(content) > 200 else content,
                    "note_type": n.get("note_type"),
                }
            )

        await publish_nats_event(
            "agent.notes.searched.v1",
            {
                "query": query,
                "results_count": len(summary),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        body = json.dumps({"query": query, "count": len(summary), "results": summary}, indent=2)
        return Response(message=f"search_notes results:\n{body}", break_loop=False)
