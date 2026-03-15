"""
Cipher MCP NATS Event Publisher

Fire-and-forget event publishing for memory operations.
Follows the pmoves_announcer pattern: connect → publish → flush → close.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SUBJECT_STORED = "cipher.memory.stored.v1"
SUBJECT_SEARCHED = "cipher.memory.searched.v1"
SUBJECT_REASONING_STORED = "cipher.reasoning.stored.v1"


def _get_nats_url() -> str:
    """Get NATS URL from environment or registry."""
    try:
        from pmoves_registry import get_nats_url
        return get_nats_url()
    except ImportError:
        return os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")


async def publish_event(subject: str, payload: dict) -> bool:
    """Fire-and-forget NATS publish. Logs to stderr on failure, never raises."""
    try:
        from nats.aio.client import Client as NATS

        nc = NATS()
        await nc.connect(_get_nats_url(), connect_timeout=5)
        await nc.publish(subject, json.dumps(payload).encode())
        await nc.flush()
        await nc.close()
        return True
    except Exception as e:
        print(f"NATS publish failed ({subject}): {e}", file=sys.stderr)
        return False


async def emit_memory_stored(
    memory_id: str, category: str, tags: List[str]
) -> bool:
    """Emit event when a memory is stored."""
    return await publish_event(SUBJECT_STORED, {
        "memory_id": memory_id,
        "category": category,
        "tags": tags,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def emit_memory_searched(
    query: str, result_count: int, category: Optional[str] = None
) -> bool:
    """Emit event when memories are searched."""
    return await publish_event(SUBJECT_SEARCHED, {
        "query": query,
        "result_count": result_count,
        "category": category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def emit_reasoning_stored(
    reasoning_id: str, question: str
) -> bool:
    """Emit event when a reasoning trace is stored."""
    return await publish_event(SUBJECT_REASONING_STORED, {
        "reasoning_id": reasoning_id,
        "question": question[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
