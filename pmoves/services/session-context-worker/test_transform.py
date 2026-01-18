#!/usr/bin/env python3
"""
Test script for session context transformation.
Demonstrates the transformation from session.context.v1 to kb.upsert.request.v1.
"""

import json
import sys
from datetime import datetime

# Sample session context event
SAMPLE_SESSION_CONTEXT = {
    "session_id": "test-session-abc123",
    "context_type": "autocompact",
    "timestamp": "2025-12-07T23:00:00Z",
    "repository": "PMOVES.AI",
    "branch": "main",
    "working_directory": "/home/pmoves/PMOVES.AI",
    "summary": "Working on Phase 3 of Claude Awareness infrastructure - implementing session-context-worker service",
    "pending_tasks": [
        {
            "content": "Create session-context-worker service",
            "status": "in_progress",
            "priority": 1
        },
        {
            "content": "Add service to docker-compose.yml",
            "status": "pending",
            "priority": 2
        },
        {
            "content": "Test NATS integration",
            "status": "pending",
            "priority": 3
        }
    ],
    "active_files": [
        {
            "path": "pmoves/services/session-context-worker/main.py",
            "action": "create",
            "timestamp": "2025-12-07T22:30:00Z"
        },
        {
            "path": "pmoves/docker-compose.yml",
            "action": "edit",
            "timestamp": "2025-12-07T22:45:00Z"
        }
    ],
    "decisions": [
        {
            "question": "Which port should session-context-worker use?",
            "answer": "8100 for health endpoint",
            "timestamp": "2025-12-07T22:20:00Z"
        }
    ],
    "tool_executions": [
        {
            "tool": "Write",
            "summary": "Created main.py with NATS subscriber implementation",
            "success": True,
            "timestamp": "2025-12-07T22:30:00Z"
        },
        {
            "tool": "Edit",
            "summary": "Added service definition to docker-compose.yml",
            "success": True,
            "timestamp": "2025-12-07T22:45:00Z"
        }
    ]
}


def extract_searchable_content(context):
    """Extract searchable content from session context."""
    parts = []

    if context.get("summary"):
        parts.append(f"Summary: {context['summary']}")

    if context.get("repository"):
        parts.append(f"Repository: {context['repository']}")
    if context.get("branch"):
        parts.append(f"Branch: {context['branch']}")

    pending_tasks = context.get("pending_tasks", [])
    if pending_tasks:
        task_texts = [f"[{t['status']}] {t['content']}" for t in pending_tasks]
        parts.append(f"Tasks:\n" + "\n".join(task_texts))

    decisions = context.get("decisions", [])
    if decisions:
        decision_texts = [f"Q: {d['question']}\nA: {d['answer']}" for d in decisions]
        parts.append(f"Decisions:\n" + "\n".join(decision_texts))

    active_files = context.get("active_files", [])
    if active_files:
        file_paths = [f.get("path", "") for f in active_files]
        parts.append(f"Active files: {', '.join(file_paths)}")

    tool_executions = context.get("tool_executions", [])
    if tool_executions:
        tool_summaries = [f"{t['tool']}: {t['summary']}" for t in tool_executions]
        parts.append(f"Tool executions:\n" + "\n".join(tool_summaries))

    return "\n\n".join(parts)


def build_metadata(context):
    """Build metadata for KB entry."""
    metadata = {
        "source": "claude-code",
        "session_id": context.get("session_id", ""),
        "context_type": context.get("context_type", "unknown"),
        "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat()),
    }

    for field in ["worktree", "branch", "repository", "working_directory", "parent_session_id"]:
        if context.get(field):
            metadata[field] = context[field]

    if context.get("pending_tasks"):
        metadata["task_count"] = len(context["pending_tasks"])
        completed = [t for t in context["pending_tasks"] if t.get("status") == "completed"]
        metadata["completed_task_count"] = len(completed)

    if context.get("active_files"):
        metadata["active_file_count"] = len(context["active_files"])

    if context.get("decisions"):
        metadata["decision_count"] = len(context["decisions"])

    return metadata


def transform_to_kb_upsert(context):
    """Transform session context to kb.upsert.request.v1."""
    session_id = context.get("session_id", "unknown")
    context_type = context.get("context_type", "unknown")
    timestamp = context.get("timestamp", datetime.now(timezone.utc).isoformat())

    kb_id = f"claude-session-{session_id}-{context_type}-{timestamp}"
    text = extract_searchable_content(context)
    metadata = build_metadata(context)

    return {
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


if __name__ == "__main__":
    print("=" * 80)
    print("Session Context Transformation Test")
    print("=" * 80)
    print()

    print("INPUT (session.context.v1):")
    print("-" * 80)
    print(json.dumps(SAMPLE_SESSION_CONTEXT, indent=2))
    print()

    kb_upsert = transform_to_kb_upsert(SAMPLE_SESSION_CONTEXT)

    print("OUTPUT (kb.upsert.request.v1):")
    print("-" * 80)
    print(json.dumps(kb_upsert, indent=2))
    print()

    print("EXTRACTED TEXT:")
    print("-" * 80)
    print(kb_upsert["items"][0]["text"])
    print()

    print("METADATA:")
    print("-" * 80)
    print(json.dumps(kb_upsert["items"][0]["metadata"], indent=2))
    print()

    print("=" * 80)
    print("✓ Transformation successful!")
    print("=" * 80)
