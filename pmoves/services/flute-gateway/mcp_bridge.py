"""MCP SSE transport bridge for Flute-Gateway TTS engine access.

Exposes 14 TTS engines as MCP tools via Server-Sent Events transport.
No external MCP SDK dependency — implements the protocol directly using
FastAPI's StreamingResponse.

MCP Protocol (SSE transport):
    GET  /sse      → SSE stream, first event: endpoint URL for messages
    POST /messages → JSON-RPC messages (initialize, tools/list, tools/call)

Tools exposed:
    tts_list_engines   — List all 14 engines with VRAM, latency, categories
    tts_list_intents   — List 9 expressive synthesis intents
    tts_synthesize     — Synthesize speech with engine + intent selection
    tts_engine_status  — Per-engine loaded/unloaded status
    tts_load_engine    — Load specific engine into VRAM
    tts_unload_engine  — Unload specific engine to free VRAM

Cross-refs:
    pmoves/configs/tts-engine-capabilities.yaml  (engine specs)
    pmoves/configs/tts-engine-expressions.yaml   (intent→engine mapping)
    pmoves/docs/AGENTS/AGNOTE4482.BEATS.md       (BPM↔boundary architecture)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config paths — resolve relative to repo root
# ---------------------------------------------------------------------------
# Dev: pmoves/services/flute-gateway → repo root.  Docker: /app/mcp_bridge.py (flat).
_REPO_ROOT = Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path("/app")
_CAPABILITIES_PATH = Path(os.environ.get(
    "TTS_CAPABILITIES_YAML",
    _REPO_ROOT / "pmoves" / "configs" / "tts-engine-capabilities.yaml",
))
_EXPRESSIONS_PATH = Path(os.environ.get(
    "TTS_EXPRESSIONS_YAML",
    _REPO_ROOT / "pmoves" / "configs" / "tts-engine-expressions.yaml",
))

# Engine endpoints — same as gpu-orchestrator/services/tts_client.py
ENGINE_ENDPOINTS: dict[str, tuple[str, str]] = {
    "kitten_tts": ("/handle_load_kitten", "/handle_unload_kitten"),
    "kokoro": ("/handle_load_kokoro", "/handle_unload_kokoro"),
    "f5_tts": ("/handle_f5_load", "/handle_f5_unload"),
    "indextts": ("/handle_load_indextts", "/handle_unload_indextts"),
    "indextts2": ("/handle_load_indextts2", "/handle_unload_indextts2"),
    "fish": ("/handle_load_fish", "/handle_unload_fish"),
    "fish_s2": ("/handle_load_fish_s2", "/handle_unload_fish_s2"),
    "chatterbox": ("/handle_load_chatterbox", "/handle_unload_chatterbox"),
    "chatterbox_turbo": ("/handle_load_chatterbox_turbo", "/handle_unload_chatterbox_turbo"),
    "chatterbox_multilingual": ("/handle_load_chatterbox_multilingual", "/handle_unload_chatterbox_multilingual"),
    "voxcpm": ("/handle_load_voxcpm", "/handle_unload_voxcpm"),
    "higgs": ("/handle_load_higgs", "/handle_unload_higgs"),
    "qwen": ("/handle_load_qwen", "/handle_unload_qwen"),
    "vibevoice": ("/handle_vibevoice_load", "/handle_vibevoice_unload"),
}

# BPM ↔ Boundary mapping (from AGNOTE4482.BEATS.md)
BOUNDARY_BPM: dict[str, dict[str, Any]] = {
    "SENTENCE": {"bpm": 60, "pause_ms": 350, "root_note": "C4", "root_hz": 262},
    "CLAUSE": {"bpm": 90, "pause_ms": 180, "root_note": "E4", "root_hz": 330},
    "PHRASE": {"bpm": 120, "pause_ms": 100, "root_note": "G4", "root_hz": 392},
    "BREATH": {"bpm": 80, "pause_ms": 130, "root_note": "D4", "root_hz": 294},
    "NONE": {"bpm": 150, "pause_ms": 0, "root_note": "C5", "root_hz": 523},
}


# ---------------------------------------------------------------------------
# YAML config loaders (lazy, cached)
# ---------------------------------------------------------------------------
_capabilities_cache: dict | None = None
_expressions_cache: dict | None = None


def _load_capabilities() -> dict:
    """Load engine capabilities YAML, cached after first read."""
    global _capabilities_cache
    if _capabilities_cache is None:
        if _CAPABILITIES_PATH.exists():
            with open(_CAPABILITIES_PATH) as f:
                _capabilities_cache = yaml.safe_load(f) or {}
        else:
            logger.warning("Engine capabilities not found: %s", _CAPABILITIES_PATH)
            _capabilities_cache = {}
    return _capabilities_cache


def _load_expressions() -> dict:
    """Load intent expressions YAML, cached after first read."""
    global _expressions_cache
    if _expressions_cache is None:
        if _EXPRESSIONS_PATH.exists():
            with open(_EXPRESSIONS_PATH) as f:
                _expressions_cache = yaml.safe_load(f) or {}
        else:
            logger.warning("Engine expressions not found: %s", _EXPRESSIONS_PATH)
            _expressions_cache = {}
    return _expressions_cache


# ---------------------------------------------------------------------------
# MCP Tool definitions (JSON Schema for each tool)
# ---------------------------------------------------------------------------
MCP_TOOLS = [
    {
        "name": "tts_list_engines",
        "description": "List all 14 TTS engines with VRAM requirements, latency tier, category, and supported features.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "tts_list_intents",
        "description": "List 9 expressive synthesis intents (narrate, emote, dramatic, clone, multilingual, podcast, persona, agent, bpm_sync) with primary/fallback engines and available modifiers.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "tts_synthesize",
        "description": "Synthesize speech using a specific engine or intent. Returns audio as base64 WAV.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to synthesize"},
                "engine": {"type": "string", "description": "Engine ID (e.g., kitten_tts, kokoro, f5_tts). If omitted, uses intent to select."},
                "intent": {"type": "string", "description": "Expressive intent (narrate, emote, dramatic, clone, multilingual, podcast, persona, agent, bpm_sync). Used if engine not specified."},
                "modifier": {"type": "string", "description": "Intent modifier (e.g., happy, fast, theatrical). Overlays params on the intent defaults."},
                "voice": {"type": "string", "description": "Voice preset name (engine-specific)."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "tts_engine_status",
        "description": "Check which TTS engines are available and their load status via the Gradio API.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "tts_load_engine",
        "description": "Load a specific TTS engine into GPU VRAM. Only one heavy engine should be loaded at a time.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {"type": "string", "description": "Engine ID to load (e.g., kitten_tts, kokoro, indextts2)"},
            },
            "required": ["engine"],
        },
    },
    {
        "name": "tts_unload_engine",
        "description": "Unload a TTS engine from GPU VRAM (del model + gc.collect + torch.cuda.empty_cache).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "engine": {"type": "string", "description": "Engine ID to unload"},
            },
            "required": ["engine"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _tool_list_engines(
    _args: dict,
    provider: Any,
) -> dict:
    """Return engine registry from capabilities YAML."""
    caps = _load_capabilities()
    engines = caps.get("engines", {})
    summary = {}
    for eid, spec in engines.items():
        summary[eid] = {
            "name": spec.get("name", eid),
            "category": spec.get("category", "unknown"),
            "vram_mb": spec.get("vram_estimate_mb", 0),
            "latency": spec.get("latency_tier", "unknown"),
            "voice_cloning": spec.get("voice_cloning", False),
            "languages": spec.get("languages", []),
        }
    return {"engines": summary, "total": len(summary)}


async def _tool_list_intents(
    _args: dict,
    provider: Any,
) -> dict:
    """Return intent→engine mapping from expressions YAML."""
    expr = _load_expressions()
    intents = expr.get("intents", {})
    summary = {}
    for iid, spec in intents.items():
        summary[iid] = {
            "description": spec.get("description", ""),
            "primary_engine": spec.get("primary", ""),
            "fallback_engine": spec.get("fallback", ""),
            "modifiers": list(spec.get("modifiers", {}).keys()),
            "requires": spec.get("requires", []),
            "gradio_endpoint": spec.get("gradio_endpoint", "/generate_unified_tts"),
        }
    return {
        "intents": summary,
        "total": len(summary),
        "boundary_bpm_mapping": BOUNDARY_BPM,
    }


async def _tool_synthesize(
    args: dict,
    provider: Any,
) -> dict:
    """Synthesize speech via UltimateTTSProvider."""
    text = args.get("text", "")
    if not text:
        return {"error": "text is required"}

    engine = args.get("engine")
    intent = args.get("intent")
    modifier = args.get("modifier")
    voice = args.get("voice")

    # Resolve engine from intent if not specified
    if not engine and intent:
        expr = _load_expressions()
        intent_spec = expr.get("intents", {}).get(intent)
        if intent_spec:
            engine = intent_spec.get("primary")
        else:
            return {"error": f"Unknown intent: {intent}"}

    engine = engine or "kitten_tts"

    if engine not in ENGINE_ENDPOINTS:
        return {"error": f"Unknown engine: {engine}", "available": list(ENGINE_ENDPOINTS.keys())}

    if provider is None:
        return {"error": "UltimateTTSProvider not available (TTS Studio offline?)"}

    import base64
    try:
        audio_bytes = await provider.synthesize(
            text=text,
            voice=voice,
            engine=engine,
        )
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {
            "engine": engine,
            "intent": intent,
            "modifier": modifier,
            "text_length": len(text),
            "audio_bytes": len(audio_bytes),
            "audio_base64": audio_b64,
            "format": "wav",
            "status": "ok",
        }
    except Exception as e:
        logger.exception("tts_synthesize failed for engine=%s", engine)
        return {"error": str(e), "engine": engine}


async def _tool_engine_status(
    _args: dict,
    provider: Any,
) -> dict:
    """Check engine availability via Gradio API."""
    if provider is None:
        return {"error": "UltimateTTSProvider not available"}

    try:
        engines = await provider.get_engines()
        return {"engines": engines, "provider_healthy": True}
    except Exception as e:
        logger.exception("tts_engine_status failed")
        return {"error": str(e), "provider_healthy": False}


async def _tool_load_engine(
    args: dict,
    provider: Any,
) -> dict:
    """Load a TTS engine into VRAM."""
    engine = args.get("engine", "")
    if engine not in ENGINE_ENDPOINTS:
        return {"error": f"Unknown engine: {engine}", "available": list(ENGINE_ENDPOINTS.keys())}

    if provider is None:
        return {"error": "UltimateTTSProvider not available"}

    load_ep, _ = ENGINE_ENDPOINTS[engine]
    try:
        import httpx
        # The old synchronous /api/ predict endpoint is a 404 on current
        # Ultimate-TTS builds — go through the provider's event-based
        # /gradio_api/call flow instead.
        async with httpx.AsyncClient(timeout=120.0) as client:
            result = await provider._call_gradio(client, load_ep, [], timeout=120.0)
        return {"engine": engine, "endpoint": load_ep, "result": result, "status": "loaded"}
    except Exception as e:
        logger.exception("tts_load_engine failed for engine=%s", engine)
        return {"error": str(e), "engine": engine}


async def _tool_unload_engine(
    args: dict,
    provider: Any,
) -> dict:
    """Unload a TTS engine from VRAM."""
    engine = args.get("engine", "")
    if engine not in ENGINE_ENDPOINTS:
        return {"error": f"Unknown engine: {engine}", "available": list(ENGINE_ENDPOINTS.keys())}

    if provider is None:
        return {"error": "UltimateTTSProvider not available"}

    _, unload_ep = ENGINE_ENDPOINTS[engine]
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            result = await provider._call_gradio(client, unload_ep, [], timeout=60.0)
        return {"engine": engine, "endpoint": unload_ep, "result": result, "status": "unloaded"}
    except Exception as e:
        logger.exception("tts_unload_engine failed for engine=%s", engine)
        return {"error": str(e), "engine": engine}


# Tool dispatch table
_TOOL_HANDLERS = {
    "tts_list_engines": _tool_list_engines,
    "tts_list_intents": _tool_list_intents,
    "tts_synthesize": _tool_synthesize,
    "tts_engine_status": _tool_engine_status,
    "tts_load_engine": _tool_load_engine,
    "tts_unload_engine": _tool_unload_engine,
}


# ---------------------------------------------------------------------------
# MCP SSE Transport
# ---------------------------------------------------------------------------

class MCPSession:
    """Tracks a single MCP client session with its SSE queue."""

    def __init__(self, session_id: str, provider: Any, nats_client: Any = None):
        self.session_id = session_id
        self.provider = provider
        self.nats_client = nats_client
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.initialized = False

    async def handle_message(self, message: dict) -> None:
        """Process a JSON-RPC message and enqueue the response."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "pmoves-flute-gateway",
                        "version": "1.0.0",
                    },
                },
            }
            self.initialized = True

        elif method == "notifications/initialized":
            # Client acknowledgement — no response needed
            return

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": MCP_TOOLS},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            handler = _TOOL_HANDLERS.get(tool_name)

            if handler is None:
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
            else:
                try:
                    result = await handler(tool_args, self.provider)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                        },
                    }
                    # Publish NATS event for synthesis calls
                    if tool_name == "tts_synthesize" and self.nats_client and "error" not in result:
                        await self._publish_tts_event(tool_name, tool_args, result)
                except Exception as e:
                    logger.exception("Tool %s failed", tool_name)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(e)},
                    }

        elif method == "ping":
            response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        else:
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        await self.queue.put(json.dumps(response))

    async def _publish_tts_event(self, tool: str, args: dict, result: dict) -> None:
        """Publish TTS synthesis event to NATS."""
        try:
            payload = {
                "tool": tool,
                "engine": result.get("engine", ""),
                "text_length": result.get("text_length", 0),
                "audio_bytes": result.get("audio_bytes", 0),
                "intent": args.get("intent", ""),
                "status": result.get("status", ""),
            }
            await self.nats_client.publish(
                "tts.synthesis.result.v1",
                json.dumps(payload).encode("utf-8"),
            )
        except Exception as e:
            logger.warning("Failed to publish TTS NATS event: %s", e)


# Active sessions
_sessions: dict[str, MCPSession] = {}


def create_mcp_router(
    get_provider: Any,
    get_nats_client: Any,
) -> APIRouter:
    """Create FastAPI router with MCP SSE endpoints.

    Args:
        get_provider: Callable returning the UltimateTTSProvider instance (or None).
        get_nats_client: Callable returning the NATS client instance (or None).

    Returns:
        APIRouter with /sse and /messages endpoints mounted.
    """
    router = APIRouter()

    @router.get("/sse")
    async def sse_endpoint(request: Request):
        """SSE stream endpoint — MCP clients connect here."""
        session_id = str(uuid.uuid4())
        provider = get_provider()
        nats = get_nats_client()
        session = MCPSession(session_id, provider, nats)
        _sessions[session_id] = session

        logger.info("MCP session started: %s", session_id)

        async def event_stream():
            # First event: tell client where to send messages
            yield f"event: endpoint\ndata: /messages?session_id={session_id}\n\n"

            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(session.queue.get(), timeout=30.0)
                        yield f"event: message\ndata: {msg}\n\n"
                    except asyncio.TimeoutError:
                        # Send keepalive comment
                        yield ": keepalive\n\n"
            finally:
                _sessions.pop(session_id, None)
                logger.info("MCP session ended: %s", session_id)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post("/messages")
    async def messages_endpoint(request: Request, session_id: str):
        """Receive JSON-RPC messages from MCP clients."""
        session = _sessions.get(session_id)
        if session is None:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=404,
                content={"error": f"Session not found: {session_id}"},
            )

        body = await request.json()
        await session.handle_message(body)
        return {"ok": True}

    return router
