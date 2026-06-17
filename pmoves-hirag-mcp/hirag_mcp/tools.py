"""MCP tool definitions and handlers for the PMOVES Hi-RAG bridge.

Three tools, all thin HTTP passthroughs to existing PMOVES services
(per `.claude/CATALOG.md` — leverage, don't duplicate):

- ``hirag_query``     → Hi-RAG Gateway v2 ``POST /hirag/query`` (:8086 CPU / :8087 GPU)
- ``notebook_search`` → Open Notebook API (``$OPEN_NOTEBOOK_API_URL`` + token)
- ``service_health``  → catalog health endpoints (``/healthz``; Cipher is ``/health``)
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.types import TextContent, Tool

DEFAULT_TIMEOUT = 30.0

# Catalog health endpoints — source of truth: .claude/CATALOG.md + service routes.
# NOTE: Cipher exposes /health (not /healthz); Hi-RAG v2 has NO /healthz — its liveness
# route is "/" (root), verified in pmoves/services/hi-rag-gateway-v2/routes/health.py
# (probing /healthz 404s; the repo smoke test treats that 404 as "not running").
HEALTH_CATALOG: dict[str, str] = {
    "agent-zero": "http://localhost:8080/healthz",
    "archon": "http://localhost:8091/healthz",
    "hirag-cpu": "http://localhost:8086/",
    "hirag-gpu": "http://localhost:8087/",
    "cipher": "http://localhost:8105/health",
    "supaserch": "http://localhost:8099/healthz",
    "deepresearch": "http://localhost:8098/healthz",
    "flute-gateway": "http://localhost:8055/healthz",
    "pmoves-yt": "http://localhost:8077/healthz",
    "extract-worker": "http://localhost:8083/healthz",
    "presign": "http://localhost:8088/healthz",
}


def _hirag_url(gpu: bool = False) -> str:
    """Resolve the Hi-RAG v2 base URL (CPU :8086 default, GPU :8087 via flag)."""
    if gpu:
        return os.environ.get("HIRAG_GPU_URL", "http://localhost:8087")
    return os.environ.get("HIRAG_URL", "http://localhost:8086")


def _notebook_config() -> tuple[str, str]:
    """Resolve Open Notebook API URL + token from the environment."""
    return (
        os.environ.get("OPEN_NOTEBOOK_API_URL", ""),
        os.environ.get("OPEN_NOTEBOOK_API_TOKEN", ""),
    )


def _text(payload: Any) -> list[TextContent]:
    """Wrap a JSON-serializable payload as a single MCP TextContent item."""
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))]


async def handle_hirag_query(
    query: str,
    top_k: int = 10,
    rerank: bool = True,
    gpu: bool = False,
) -> list[TextContent]:
    """Query Hi-RAG v2 hybrid retrieval (Qdrant + Neo4j + Meilisearch, cross-encoder rerank)."""
    if not query or not isinstance(query, str):
        return _text({"error": "query is required"})
    top_k = max(1, min(int(top_k), 50))
    base = _hirag_url(gpu=bool(gpu))
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(
            f"{base}/hirag/query",
            json={"query": query, "top_k": top_k, "rerank": bool(rerank)},
        )
        resp.raise_for_status()
        return _text(resp.json())


async def handle_notebook_search(q: str, limit: int = 10) -> list[TextContent]:
    """Search Open Notebook (SurrealDB) via its HTTP API; requires env URL + token."""
    if not q or not isinstance(q, str):
        return _text({"error": "q is required"})
    url, token = _notebook_config()
    if not url:
        return _text({"error": "OPEN_NOTEBOOK_API_URL not set — see pmoves/env.tier-* + secrets-funnel"})
    limit = max(1, min(int(limit), 50))
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(
            f"{url.rstrip('/')}/api/search",
            params={"q": q, "limit": limit},
            headers=headers,
        )
        resp.raise_for_status()
        return _text(resp.json())


async def handle_service_health(name: str = "") -> list[TextContent]:
    """Probe one named catalog service, or all of them when name is empty."""
    targets = (
        {name: HEALTH_CATALOG[name]} if name and name in HEALTH_CATALOG
        else HEALTH_CATALOG if not name
        else None
    )
    if targets is None:
        return _text({"error": f"unknown service '{name}'", "known": sorted(HEALTH_CATALOG)})
    results: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for svc, url in targets.items():
            try:
                resp = await client.get(url)
                results[svc] = {"status": resp.status_code, "ok": resp.status_code == 200}
            except Exception as exc:
                results[svc] = {"status": None, "ok": False, "error": str(exc)}
    return _text(results)


TOOLS: list[Tool] = [
    Tool(
        name="hirag_query",
        description=(
            "Hybrid knowledge retrieval over the PMOVES corpus via Hi-RAG Gateway v2 "
            "(Qdrant vectors + Neo4j graph + Meilisearch full-text, cross-encoder rerank). "
            "Use for any 'search our docs/knowledge/transcripts' request — the self-hosted "
            "Notion/Confluence-search analog."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language query"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
                "rerank": {"type": "boolean", "default": True},
                "gpu": {"type": "boolean", "default": False, "description": "Use GPU gateway :8087"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="notebook_search",
        description=(
            "Search Open Notebook (SurrealDB research notebook). Requires "
            "OPEN_NOTEBOOK_API_URL (+ optional token) in env. DeepResearch and "
            "Notebook Sync publish results here."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["q"],
        },
    ),
    Tool(
        name="service_health",
        description=(
            "Probe PMOVES service health endpoints from .claude/CATALOG.md. "
            "Pass a service name (e.g. 'hirag-cpu', 'agent-zero', 'cipher') or "
            "omit to sweep all. Check health before using a service (BOOTSTRAP rule 5)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Catalog service name; empty = all"},
            },
        },
    ),
]


TOOL_HANDLERS = {
    "hirag_query": handle_hirag_query,
    "notebook_search": handle_notebook_search,
    "service_health": handle_service_health,
}
