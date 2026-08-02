"""PMOVES.Notes tool — save a note to Open Notebook.

Conforms to the Agent Zero tool API: subclass ``helpers.tool.Tool`` and
implement ``async def execute(...) -> Response``. Agent Zero discovers this
tool by file name (``tools/save_note.py`` -> tool name ``save_note``) and loads
the first class in the file that subclasses ``Tool``.
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


class SaveNote(Tool):
    """Save a note to PMOVES.AI Open Notebook (persistent knowledge base)."""

    async def execute(
        self,
        content: str = "",
        title: str = "",
        tags: list[str] | None = None,
        **kwargs,
    ) -> Response:
        if content is None:
            content = ""
        content = content if isinstance(content, str) else str(content)
        if not content.strip():
            return Response(
                message="save_note error: 'content' is required.", break_loop=False
            )

        tags = list(tags) if isinstance(tags, (list, tuple)) else []

        if not title:
            lines = content.splitlines()
            first_line = lines[0] if lines else content
            title = (first_line[:60] + "...") if len(first_line) > 60 else first_line

        # Open Notebook's POST /api/notes accepts {content, title, note_type,
        # notebook_id} only — there is no tags/metadata field. Fold tags into the
        # note body so the categorization survives.
        all_tags = tags + ["agent-created"]
        body = content + "\n\n_tags: " + ", ".join(all_tags) + "_"
        note = {
            "content": body,
            "title": title,
            "note_type": "human",
        }

        api_url = _notebook_api_url()
        headers = _build_headers(api_url, _notebook_token())

        try:
            import aiohttp  # lazy import: keeps import errors out of tool discovery

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{api_url}/api/notes",
                    json=note,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        detail = await resp.text()
                        return Response(
                            message=f"save_note failed: HTTP {resp.status} — {detail}",
                            break_loop=False,
                        )
                    result = await resp.json()
        except Exception as exc:  # noqa: BLE001 — surface as tool message, never crash loop
            return Response(message=f"save_note error: {exc}", break_loop=False)

        if not isinstance(result, dict):
            return Response(
                message="save_note failed: unexpected response shape (expected JSON object).",
                break_loop=False,
            )

        note_id = result.get("id", "unknown")
        await publish_nats_event(
            "agent.notes.saved.v1",
            {
                "note_id": note_id,
                "title": title,
                "tags": tags,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        return Response(
            message=f"Note saved to Open Notebook (id={note_id}, title={title!r}).",
            break_loop=False,
        )
