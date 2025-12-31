#!/usr/bin/env python3
"""
Session Context Worker - Transforms Claude Code session context to Hi-RAG knowledge base entries.

Subscribes to: claude.code.session.context.v1
Publishes to: kb.upsert.request.v1
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import nats
from fastapi import FastAPI
from contextlib import asynccontextmanager
from nats.aio.client import Client as NATS
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

# Prometheus metrics
messages_received = Counter(
    'session_context_worker_messages_received_total',
    'Total number of messages received',
    ['subject']
)
messages_processed = Counter(
    'session_context_worker_messages_processed_total',
    'Total number of messages successfully processed',
    ['context_type']
)
messages_failed = Counter(
    'session_context_worker_messages_failed_total',
    'Total number of messages that failed processing',
    ['error_type']
)
kb_upserts_published = Counter(
    'session_context_worker_kb_upserts_published_total',
    'Total number of KB upsert requests published',
    ['namespace']
)
processing_duration = Histogram(
    'session_context_worker_processing_duration_seconds',
    'Time spent processing session context messages',
    ['context_type']
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("session_context_worker")

# Environment variables
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8100"))
SESSION_CONTEXT_SUBJECT = "claude.code.session.context.v1"
KB_UPSERT_SUBJECT = "kb.upsert.request.v1"

# Global state
_nc: Optional[NATS] = None
_nats_loop_task: Optional[asyncio.Task] = None

# FastAPI app for health endpoint
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global _nats_loop_task, _nc
    # Startup
    """Start NATS connection loop on app startup."""

    if _nats_loop_task is None or _nats_loop_task.done():
        logger.info("Starting NATS resilience loop")
        _nats_loop_task = asyncio.create_task(_nats_resilience_loop())
    yield
    # Shutdown
    """Clean shutdown of NATS connection."""

    if _nats_loop_task:
        _nats_loop_task.cancel()
        try:
            await _nats_loop_task
        except Exception:
            pass
        _nats_loop_task = None

    if _nc:
        try:
            await _nc.close()
        except Exception:
            pass
        _nc = None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=HEALTH_PORT)

app = FastAPI(title="Session Context Worker", version="0.1.0", lifespan=lifespan)


def _extract_searchable_content(context: Dict[str, Any]) -> str:
    """
    Extract searchable text content from session context.

    Combines summary, task descriptions, decisions, and other relevant information
    into a single searchable text block.
    """
    parts = []

    # Add summary
    summary = context.get("summary")
    if summary:
        parts.append(f"Summary: {summary}")

    # Add repository and branch context
    repo = context.get("repository")
    branch = context.get("branch")
    if repo:
        parts.append(f"Repository: {repo}")
    if branch:
        parts.append(f"Branch: {branch}")

    # Add pending tasks
    pending_tasks = context.get("pending_tasks", [])
    if pending_tasks:
        task_texts = []
        for task in pending_tasks:
            content = task.get("content", "")
            status = task.get("status", "")
            if content:
                task_texts.append(f"[{status}] {content}")
        if task_texts:
            parts.append(f"Tasks:\n" + "\n".join(task_texts))

    # Add decisions
    decisions = context.get("decisions", [])
    if decisions:
        decision_texts = []
        for decision in decisions:
            question = decision.get("question", "")
            answer = decision.get("answer", "")
            if question and answer:
                decision_texts.append(f"Q: {question}\nA: {answer}")
        if decision_texts:
            parts.append(f"Decisions:\n" + "\n".join(decision_texts))

    # Add active files summary
    active_files = context.get("active_files", [])
    if active_files:
        file_paths = [f.get("path", "") for f in active_files if f.get("path")]
        if file_paths:
            parts.append(f"Active files: {', '.join(file_paths[:10])}")

    # Add tool executions summary
    tool_executions = context.get("tool_executions", [])
    if tool_executions:
        tool_summaries = []
        for execution in tool_executions:
            tool_name = execution.get("tool", "")
            summary = execution.get("summary", "")
            if tool_name and summary:
                tool_summaries.append(f"{tool_name}: {summary}")
        if tool_summaries:
            parts.append(f"Tool executions:\n" + "\n".join(tool_summaries[:5]))

    # Add agent spawns
    agent_spawns = context.get("agent_spawns", [])
    if agent_spawns:
        agent_texts = []
        for spawn in agent_spawns:
            agent_type = spawn.get("agent_type", "")
            task = spawn.get("task", "")
            status = spawn.get("status", "")
            if agent_type:
                agent_texts.append(f"{agent_type} [{status}]: {task}")
        if agent_texts:
            parts.append(f"Agent spawns:\n" + "\n".join(agent_texts))

    return "\n\n".join(parts)


def _build_metadata(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build metadata object for Hi-RAG knowledge base entry.

    Includes session tracking, repository info, and context type classification.
    """
    metadata = {
        "source": "claude-code",
        "session_id": context.get("session_id", ""),
        "context_type": context.get("context_type", "unknown"),
        "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat()),
    }

    # Add optional fields if present
    if context.get("worktree"):
        metadata["worktree"] = context["worktree"]

    if context.get("branch"):
        metadata["branch"] = context["branch"]

    if context.get("repository"):
        metadata["repository"] = context["repository"]

    if context.get("working_directory"):
        metadata["working_directory"] = context["working_directory"]

    if context.get("parent_session_id"):
        metadata["parent_session_id"] = context["parent_session_id"]

    # Add task count
    pending_tasks = context.get("pending_tasks", [])
    if pending_tasks:
        metadata["task_count"] = len(pending_tasks)
        completed_tasks = [t for t in pending_tasks if t.get("status") == "completed"]
        metadata["completed_task_count"] = len(completed_tasks)

    # Add file count
    active_files = context.get("active_files", [])
    if active_files:
        metadata["active_file_count"] = len(active_files)

    # Add decision count
    decisions = context.get("decisions", [])
    if decisions:
        metadata["decision_count"] = len(decisions)

    return metadata


def _transform_to_kb_upsert(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform session context to kb.upsert.request.v1 payload.

    Creates a knowledge base entry that can be searched and retrieved later.
    """
    session_id = context.get("session_id", "unknown")
    context_type = context.get("context_type", "unknown")
    timestamp = context.get("timestamp", datetime.now(timezone.utc).isoformat())

    # Generate unique ID for this KB entry
    kb_id = f"claude-session-{session_id}-{context_type}-{timestamp}"

    # Extract searchable content
    text = _extract_searchable_content(context)

    # Build metadata
    metadata = _build_metadata(context)

    # Create kb.upsert payload
    kb_upsert = {
        "items": [
            {
                "id": kb_id,
                "text": text,
                "metadata": metadata,
            }
        ],
        "namespace": "claude-code-sessions",
        "meta": {
            "worker": "session-context-worker",
            "version": "0.1.0",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    return kb_upsert


async def _handle_session_context(msg: NATS.Msg) -> None:
    """
    Handle incoming session context messages.

    Transforms the context and publishes to kb.upsert.request.v1.
    """
    messages_received.labels(SESSION_CONTEXT_SUBJECT).inc()
    start_time = time.time()
    context_type = "unknown"

    try:
        # Parse message
        data = json.loads(msg.data.decode("utf-8"))

        if not isinstance(data, dict):
            logger.warning(f"Invalid message format: expected dict, got {type(data)}")
            messages_failed.labels("invalid_format").inc()
            processing_duration.labels("unknown").observe(time.time() - start_time)
            return

        session_id = data.get("session_id", "unknown")
        context_type = data.get("context_type", "unknown")

        logger.info(
            f"Processing session context: session_id={session_id}, type={context_type}",
            extra={
                "session_id": session_id,
                "context_type": context_type,
            }
        )

        # Transform to kb.upsert format
        kb_upsert = _transform_to_kb_upsert(data)

        # Publish to kb.upsert.request.v1
        if _nc:
            await _nc.publish(
                KB_UPSERT_SUBJECT,
                json.dumps(kb_upsert).encode("utf-8")
            )
            kb_upserts_published.labels("claude-code-sessions").inc()
            logger.info(
                f"Published KB upsert for session {session_id}",
                extra={
                    "session_id": session_id,
                    "kb_id": kb_upsert["items"][0]["id"],
                    "text_length": len(kb_upsert["items"][0]["text"]),
                }
            )
        else:
            logger.warning("NATS client not connected, skipping publish")
            messages_failed.labels("nats_not_connected").inc()
            processing_duration.labels(context_type).observe(time.time() - start_time)
            return

        messages_processed.labels(context_type).inc()
        processing_duration.labels(context_type).observe(time.time() - start_time)

    except json.JSONDecodeError as e:
        logger.exception("Failed to decode JSON")
        messages_failed.labels("json_decode_error").inc()
        processing_duration.labels(context_type).observe(time.time() - start_time)
    except Exception as e:
        logger.error(f"Error processing session context: {e}", exc_info=True)
        messages_failed.labels("processing_error").inc()
        processing_duration.labels(context_type).observe(time.time() - start_time)


async def _register_nats_subscriptions(nc: NATS) -> None:
    """Register NATS subscriptions."""
    try:
        await nc.subscribe(SESSION_CONTEXT_SUBJECT, cb=_handle_session_context)
        logger.info(
            f"Subscribed to {SESSION_CONTEXT_SUBJECT}",
            extra={"subject": SESSION_CONTEXT_SUBJECT}
        )
    except Exception as exc:
        logger.error(
            f"Failed to subscribe to {SESSION_CONTEXT_SUBJECT}: {exc}",
            exc_info=True
        )


async def _nats_resilience_loop() -> None:
    """
    NATS connection resilience loop with automatic reconnection.

    Maintains persistent NATS connection with exponential backoff on failures.
    """
    global _nc
    backoff = 1.0

    while True:
        nc = NATS()
        disconnect_event = asyncio.Event()

        def _mark_connection_lost(reason: str) -> None:
            global _nc
            if _nc is nc:
                _nc = None
            if not disconnect_event.is_set():
                disconnect_event.set()
            logger.warning(
                f"NATS connection lost: {reason}",
                extra={"reason": reason, "servers": [NATS_URL]}
            )

        async def _disconnected_cb():
            _mark_connection_lost("disconnected")

        async def _closed_cb():
            _mark_connection_lost("closed")

        try:
            logger.info(
                f"Attempting NATS connection: {NATS_URL}",
                extra={"servers": [NATS_URL], "backoff": backoff}
            )
            await nc.connect(
                servers=[NATS_URL],
                disconnected_cb=_disconnected_cb,
                closed_cb=_closed_cb
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                f"NATS connection failed: {exc}",
                extra={"servers": [NATS_URL], "error": str(exc), "backoff": backoff}
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
            continue

        # Connection successful
        _nc = nc
        backoff = 1.0
        logger.info(f"NATS connected: {NATS_URL}", extra={"servers": [NATS_URL]})

        # Register subscriptions
        await _register_nats_subscriptions(nc)

        # Wait for disconnection
        try:
            await disconnect_event.wait()
        except asyncio.CancelledError:
            try:
                await nc.close()
            except Exception:
                pass
            if _nc is nc:
                _nc = None
            raise

        # Clean up connection
        try:
            await nc.close()
        except Exception:
            pass


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {
        "ok": True,
        "nats_connected": _nc is not None,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    from fastapi.responses import Response
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)



