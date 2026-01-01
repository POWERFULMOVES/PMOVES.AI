#!/usr/bin/env python3
"""
Session Context Worker - Transforms Claude Code session context to Hi-RAG knowledge base entries.

This module provides a NATS-based worker service that subscribes to Claude Code session
context events, transforms them into searchable knowledge base entries, and publishes
them to the Hi-RAG knowledge base for retrieval and analysis.

NATS Subjects:
    - Subscribes to: claude.code.session.context.v1
    - Publishes to: kb.upsert.request.v1

Environment Variables:
    NATS_URL: NATS server connection URL (default: "nats://nats:4222")
    HEALTH_PORT: Port for health check endpoint (default: 8100)

Prometheus Metrics:
    - session_context_worker_messages_received_total: Messages received by subject
    - session_context_worker_messages_processed_total: Successfully processed messages
    - session_context_worker_messages_failed_total: Failed message processing
    - session_context_worker_kb_upserts_published_total: KB upsert requests published
    - session_context_worker_processing_duration_seconds: Processing time histogram

Example:
    To run this service::

        NATS_URL=nats://localhost:4222 python main.py

    This will start the FastAPI server with health and metrics endpoints,
    connect to NATS, and begin processing session context messages.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
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
    """Manage application lifespan with NATS connection lifecycle.

    This async context manager handles the startup and shutdown of the NATS
    connection resilience loop. On startup, it creates the NATS connection task.
    On shutdown, it gracefully cancels the task and closes the connection.

    Args:
        app (FastAPI): The FastAPI application instance. This parameter is required
            by FastAPI's lifespan interface but is not used directly.

    Yields:
        None: This context manager yields control back to FastAPI during the
            application's lifetime.

    Notes:
        - The NATS resilience loop runs in a background task and handles automatic
          reconnection with exponential backoff.
        - On shutdown, the task is cancelled and the NATS connection is closed
          gracefully.
        - Exceptions during shutdown are silently caught to ensure clean exit.
    """
    global _nats_loop_task, _nc
    # Startup: Start NATS connection loop
    if _nats_loop_task is None or _nats_loop_task.done():
        logger.info("Starting NATS resilience loop")
        _nats_loop_task = asyncio.create_task(_nats_resilience_loop())
    yield
    # Shutdown: Clean shutdown of NATS connection
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


app = FastAPI(title="Session Context Worker", version="0.1.0", lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=HEALTH_PORT)


def _extract_searchable_content(context: Dict[str, Any]) -> str:
    """Extract searchable text content from session context.

    This function combines summary, task descriptions, decisions, and other relevant
    information from a Claude Code session context into a single searchable text block
    suitable for indexing in the Hi-RAG knowledge base.

    Args:
        context (Dict[str, Any]): The session context dictionary containing:
            - summary (str, optional): Overall session summary.
            - repository (str, optional): Git repository name.
            - branch (str, optional): Git branch name.
            - pending_tasks (List[Dict], optional): List of pending/completed tasks.
            - decisions (List[Dict], optional): List of Q&A decisions.
            - active_files (List[Dict], optional): List of active file contexts.
            - tool_executions (List[Dict], optional): List of tool execution records.
            - agent_spawns (List[Dict], optional): List of agent spawn events.

    Returns:
        str: A formatted string containing all searchable content sections
            separated by double newlines. Sections include summary, repository/branch,
            tasks, decisions, active files, tool executions, and agent spawns.

    Notes:
        - Task descriptions are prefixed with their status (e.g., "[completed]").
        - Only the first 10 active files are included to avoid excessive length.
        - Only the first 5 tool executions are included to avoid excessive length.
        - Empty sections are omitted from the output.
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
    """Build metadata object for Hi-RAG knowledge base entry.

    Constructs a metadata dictionary for the knowledge base entry including session
    tracking information, repository details, and context type classification.
    This metadata enables efficient filtering and retrieval of session contexts.

    Args:
        context (Dict[str, Any]): The session context dictionary containing:
            - session_id (str, optional): Unique session identifier.
            - context_type (str, optional): Type of context (e.g., "completion").
            - timestamp (str, optional): ISO format timestamp of the context.
            - worktree (str, optional): Git worktree path.
            - branch (str, optional): Git branch name.
            - repository (str, optional): Git repository identifier.
            - working_directory (str, optional): Current working directory path.
            - parent_session_id (str, optional): Parent session ID if applicable.
            - pending_tasks (List[Dict], optional): List of tasks for count metadata.
            - active_files (List[Dict], optional): List of files for count metadata.
            - decisions (List[Dict], optional): List of decisions for count metadata.

    Returns:
        Dict[str, Any]: A metadata dictionary containing:
            - source (str): Always "claude-code".
            - session_id (str): Session identifier.
            - context_type (str): Context type classification.
            - timestamp (str): ISO format timestamp.
            - worktree (str, optional): Git worktree path if present.
            - branch (str, optional): Git branch name if present.
            - repository (str, optional): Git repository identifier if present.
            - working_directory (str, optional): Working directory path if present.
            - parent_session_id (str, optional): Parent session ID if present.
            - task_count (int, optional): Total number of tasks.
            - completed_task_count (int, optional): Number of completed tasks.
            - active_file_count (int, optional): Number of active files.
            - decision_count (int, optional): Number of decisions made.

    Notes:
        - Optional fields are only included if present in the input context.
        - Count fields are only included if the corresponding lists are non-empty.
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
    """Transform session context to kb.upsert.request.v1 payload.

    Creates a knowledge base upsert request that transforms a Claude Code session
    context into a format suitable for the Hi-RAG knowledge base. The resulting
    entry can be searched and retrieved for future reference.

    Args:
        context (Dict[str, Any]): The session context dictionary containing all
            session information including summary, tasks, decisions, files, etc.

    Returns:
        Dict[str, Any]: A kb.upsert.request.v1 compatible payload with the structure:
            - items (List[Dict]): List containing a single knowledge base item:
                - id (str): Unique identifier generated from session_id, context_type,
                    and timestamp.
                - text (str): Searchable text content extracted from the context.
                - metadata (Dict[str, Any]): Metadata fields for filtering.
            - namespace (str): Always "claude-code-sessions".
            - meta (Dict[str, Any]): Processing metadata including:
                - worker (str): Always "session-context-worker".
                - version (str): Worker version string.
                - processed_at (str): ISO format timestamp of processing.

    Notes:
        - The KB entry ID is deterministic: "claude-session-{session_id}-{context_type}-{timestamp}".
        - All entries are stored in the "claude-code-sessions" namespace.
        - The processed_at timestamp reflects when the transformation occurred, not
          the original session timestamp.
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


async def _handle_session_context(msg: nats.aio.msg.Msg) -> None:
    """Handle incoming session context messages from NATS.

    This is the message handler for the claude.code.session.context.v1 subject.
    It parses the incoming session context, transforms it into a knowledge base
    upsert request, and publishes it to the kb.upsert.request.v1 subject.

    Args:
        msg (nats.aio.msg.Msg): The NATS message object containing:
            - data (bytes): JSON-encoded session context data.
            - subject (str): The NATS subject the message was published to.
            - reply (str, optional): Optional reply subject for responses.

    Returns:
        None: This function publishes results to NATS and updates Prometheus
            metrics but does not return a value.

    Raises:
        json.JSONDecodeError: If the message data cannot be decoded as JSON.
        Exception: For any other processing errors (logged but not raised).

    Notes:
        - Updates Prometheus metrics for messages received, processed, and failed.
        - Tracks processing duration as a histogram metric.
        - Logs warnings for invalid message formats and skips processing.
        - Logs errors and continues processing other messages if transformation fails.
        - Requires the global NATS client (_nc) to be connected for publishing.
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
    """Register NATS subscriptions for the session context worker.

    Subscribes to the claude.code.session.context.v1 subject to receive
    session context events for processing and transformation into knowledge
    base entries.

    Args:
        nc (NATS): The connected NATS client instance to register subscriptions on.

    Returns:
        None: This function registers subscriptions directly on the NATS client.

    Raises:
        Exception: If subscription registration fails. Errors are logged with
            details about the subject and exception.

    Notes:
        - Only one subscription is registered: claude.code.session.context.v1.
        - The message handler (_handle_session_context) is called for each message.
        - Subscription failures are logged but do not crash the worker.
    """
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
    """NATS connection resilience loop with automatic reconnection.

    This function runs in a background task and maintains a persistent connection
    to the NATS server. It implements exponential backoff reconnection logic to
    handle network failures and server restarts gracefully.

    Returns:
        None: This function runs indefinitely until cancelled or raises
            asyncio.CancelledError.

    Raises:
        asyncio.CancelledError: When the task is cancelled during shutdown.

    Notes:
        - Implements exponential backoff starting at 1 second, maxing out at 30 seconds.
        - Backoff resets to 1 second after a successful connection.
        - Registers subscriptions after each successful connection.
        - Waits indefinitely on a disconnect event for the lifetime of the connection.
        - Cleanly closes the connection on shutdown.
        - Updates the global _nc variable with the active connection.
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
    """Health check endpoint for monitoring service status.

    Provides a simple health check that indicates whether the service is running
    and if the NATS connection is currently active.

    Returns:
        Dict[str, Any]: A health status dictionary containing:
            - ok (bool): Always True, indicating the service is running.
            - nats_connected (bool): True if NATS client is connected, False otherwise.

    Notes:
        - This endpoint is typically used by orchestrators (Kubernetes, Docker Compose)
          for health checks.
        - The NATS connection status reflects the current state and may change
          as the resilience loop reconnects.
    """
    return {
        "ok": True,
        "nats_connected": _nc is not None and not getattr(_nc, "_is_closed", True)
    }


@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint for observability.

    Exposes Prometheus metrics in the standard text format for scraping by
    Prometheus or compatible monitoring systems.

    Returns:
        Response: A FastAPI Response object containing:
            - body (bytes): Prometheus metrics in text exposition format.
            - media_type (str): CONTENT_TYPE_LATEST (text/plain; version=0.0.4).

    Notes:
        - Metrics include counters for messages received/processed/failed and KB upserts.
        - Processing duration histogram with context_type label.
        - Typically scraped by Prometheus at /metrics every 15-60 seconds.
        - The REGISTRY contains all prometheus_client metrics defined at module level.
    """
    from fastapi.responses import Response
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)



