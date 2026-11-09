"""MCP tool definitions and handlers for the PMOVES NATS bridge.

v0.2 (spec §7b): CORE-account `.creds` auth + CHIT-signed publish. The MCP is a
first-class two-layer-trust citizen — the NATS account (via `.creds`) is the
transport-trust gate; the CHIT signature (via the CANONICAL signer) is the
payload-provenance gate. It never reimplements CHIT crypto and never fakes a
signature: it signs only when the real signer succeeds, else marks the message
`X-CHIT-Signed: false` (unsigned-local) — no fake CHIT.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import nats
from mcp.types import TextContent, Tool

# Ensure the monorepo root is on sys.path so the CANONICAL signer resolves even
# when launched via `uv --directory ./pmoves-nats-mcp` — that puts this package
# dir on the path but NOT the repo root, so the import below would silently fall
# to None and every CHIT-aware publish would ship X-CHIT-Signed: false. Walk up
# to the dir that actually holds pmoves/tools/chit_security.py (never a fixed
# depth); no-op outside the monorepo, so the guarded import still degrades cleanly.
for _root in Path(__file__).resolve().parents:
    if (_root / "pmoves" / "tools" / "chit_security.py").exists():
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        break

# Name it, don't re-type it: use the CANONICAL CHIT signer. Optional import so
# the MCP still runs (raw publish) outside the monorepo context.
try:
    from pmoves.tools.chit_security import sign_cgp as _canonical_sign_cgp
except Exception:  # pragma: no cover - import guarded on purpose
    _canonical_sign_cgp = None

# Subjects whose payloads are CGP packets and should carry a CHIT signature.
CHIT_AWARE_PREFIXES = ("chit.", "tokenism.prosodic.", "geometry.")


def _nats_url() -> str:
    return os.environ.get("NATS_URL", "nats://nats:pmoves@127.0.0.1:4222")


def _nats_creds() -> str | None:
    """Path to a CORE user `.creds` file (nsc-minted). When set, the MCP binds to
    the CORE account instead of the legacy plaintext user/pass in NATS_URL.

    Returns None (legacy fallback) when unset, empty, or still an unresolved
    ``${...}`` placeholder. A bare mcp.json ``"${NATS_CREDS}"`` survives literally
    on nodes where the var is absent, and that string is truthy — passing it to
    nats-py would make it try to open a file literally named ``${NATS_CREDS}`` and
    fail every publish/subscribe instead of falling back to NATS_URL. Guarding here
    protects ALL launch paths, not just Claude Code's ${VAR} expansion."""
    val = (os.environ.get("NATS_CREDS") or "").strip()
    if not val or (val.startswith("${") and val.endswith("}")):
        return None
    return val


async def _connect(name: str):
    creds = _nats_creds()
    if creds:
        return await nats.connect(_nats_url(), user_credentials=creds, name=name)
    return await nats.connect(_nats_url(), name=name)


def _is_chit_aware(subject: str) -> bool:
    return any(subject.startswith(p) for p in CHIT_AWARE_PREFIXES)


def _maybe_sign(subject: str, payload: str, sign: bool) -> tuple[bytes, dict[str, str] | None, dict[str, Any]]:
    """Return (body_bytes, headers, meta). Signs iff the subject is CHIT-aware or
    sign=True. Honest: only claims `signed` when the canonical signer succeeds."""
    want = sign or _is_chit_aware(subject)
    if not want:
        return payload.encode("utf-8"), None, {"signed": False, "chit_aware": False}

    if _canonical_sign_cgp is None:
        return (
            payload.encode("utf-8"),
            {"X-CHIT-Signed": "false", "X-CHIT-Reason": "canonical-signer-unavailable"},
            {"signed": False, "reason": "pmoves.tools.chit_security not importable in this context"},
        )

    try:
        cgp = json.loads(payload)
        if not isinstance(cgp, dict):
            raise ValueError("payload is not a CGP object")
    except Exception as exc:
        return (
            payload.encode("utf-8"),
            {"X-CHIT-Signed": "false", "X-CHIT-Reason": "payload-not-cgp"},
            {"signed": False, "reason": f"payload not a CGP dict: {exc}"},
        )

    try:
        signed = _canonical_sign_cgp(cgp)  # canonical HMAC; raises without a signing key
        return (
            json.dumps(signed).encode("utf-8"),
            {"X-CHIT-Signed": "true"},
            {"signed": True},
        )
    except Exception as exc:
        # Signer present but no key / failed → publish unsigned-local, honestly.
        return (
            payload.encode("utf-8"),
            {"X-CHIT-Signed": "false", "X-CHIT-Reason": "unsigned-local"},
            {"signed": False, "reason": f"canonical sign_cgp failed (no passphrase?): {exc}"},
        )


async def _publish(
    subject: str,
    payload: str,
    headers: dict[str, str] | None = None,
    sign: bool = False,
) -> dict[str, Any]:
    """Publish one message. `headers`/`sign` keep defaults: this helper is called
    directly as `_publish(subject, payload)` by .claude/hooks/test/run_integration.sh,
    which would otherwise TypeError before ever opening a connection."""
    body, sig_headers, meta = _maybe_sign(subject, payload, sign)
    merged: dict[str, str] = dict(headers or {})
    if sig_headers:
        merged.update(sig_headers)
    nc = await _connect("pmoves-nats-mcp")
    try:
        await nc.publish(subject, body, headers=merged or None)
        await nc.flush(timeout=2)
        return {
            "published": True,
            "subject": subject,
            "bytes": len(body),
            "chit_signed": meta.get("signed", False),
            "account": "CORE" if _nats_creds() else "legacy",
            **({"chit_note": meta["reason"]} if meta.get("reason") else {}),
        }
    finally:
        await nc.close()


async def _subscribe(subject: str, timeout_seconds: int, max_messages: int) -> list[dict[str, Any]]:
    nc = await _connect("pmoves-nats-mcp-sub")
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
            msg_headers = msg.headers or {}
            # NATS headers are strings. Returning the raw header made the honest
            # "false" verdict read as signed downstream -- bool("false") is True in
            # Python and Boolean("false") is true in JS, so an agent auditing the bus
            # saw every unsigned message as signed. Normalise to a real bool so the
            # subscribe side reports the same type _publish does.
            captured.append({
                "subject": msg.subject,
                "data": msg.data.decode("utf-8", errors="replace"),
                "reply": msg.reply or None,
                "chit_signed": msg_headers.get("X-CHIT-Signed") == "true",
                **({"chit_note": msg_headers["X-CHIT-Reason"]}
                   if msg_headers.get("X-CHIT-Reason") else {}),
            })
        await sub.unsubscribe()
        return captured
    finally:
        await nc.close()


async def handle_publish(
    subject: str,
    payload: str,
    headers: dict[str, str] | None = None,
    sign: bool = False,
) -> list[TextContent]:
    if not subject or not isinstance(subject, str):
        return [TextContent(type="text", text=json.dumps({"error": "subject is required"}))]
    result = await _publish(subject, payload or "", headers, bool(sign))
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
            "CHIT-aware subjects (`chit.*`, `tokenism.prosodic.*`, `geometry.*`) — or sign=true — "
            "are CHIT-signed via the canonical signer before publish (never a fake signature: "
            "unsigned-local is marked X-CHIT-Signed:false). Binds to the CORE account when NATS_CREDS is set."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "NATS subject (e.g. archon.mint.agent.v1)"},
                "payload": {"type": "string", "description": "Message body (JSON-encoded string; a CGP object for CHIT-aware subjects)"},
                "headers": {
                    "type": "object",
                    "description": "Optional NATS headers",
                    "additionalProperties": {"type": "string"},
                },
                "sign": {
                    "type": "boolean",
                    "description": "Force CHIT-signing even for a non-CHIT-aware subject (payload must be a CGP JSON object)",
                    "default": False,
                },
            },
            "required": ["subject", "payload"],
        },
    ),
    Tool(
        name="nats_subscribe",
        description=(
            "Subscribe to a NATS subject (supports wildcards `*` and `>`), wait up to timeout_seconds, "
            "and return up to max_messages captured payloads (with their X-CHIT-Signed header). Useful for "
            "verifying mint flows, tailing CHIT signed events, or auditing live JetStream traffic."
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
