"""
Standard Event Subjects for PMOVES.AI Agent Coordination

Based on PMOVES-ToKenism-Multi event naming conventions.
All subjects follow the pattern: `pmoves.{service}.{event}.{version}`

Usage:
    from pmoves.services.agent_zero.python.events.subjects import AGENT_STARTED, ALL_AGENT_EVENTS

    # Publish
    await bus.publish(AGENT_STARTED, "AGENT_STARTED", data={"agent_id": "agent-zero"})

    # Subscribe to all agent events
    await bus.subscribe(ALL_AGENT_EVENTS, handler)
"""

# =============================================================================
# Agent Lifecycle Events
# =============================================================================

"""Agent process started successfully"""
AGENT_STARTED = "pmoves.agent.started.v1"

"""Agent process stopped/shutdown"""
AGENT_STOPPED = "pmoves.agent.stopped.v1"

"""Agent encountered error"""
AGENT_ERROR = "pmoves.agent.error.v1"

# =============================================================================
# Task/Work Events
# =============================================================================

"""New task created for execution"""
TASK_CREATED = "pmoves.work.task.created.v1"

"""Task assigned to specific agent/worker"""
TASK_ASSIGNED = "pmoves.work.task.assigned.v1"

"""Task completed successfully"""
TASK_COMPLETED = "pmoves.work.task.completed.v1"

"""Task failed (includes error details)"""
TASK_FAILED = "pmoves.work.task.failed.v1"

# =============================================================================
# Tool Execution Events
# =============================================================================

"""Tool/invocation started"""
TOOL_STARTED = "pmoves.agent.tool.started.v1"

"""Tool/invocation completed successfully"""
TOOL_COMPLETED = "pmoves.agent.tool.completed.v1"

"""Tool/invocation failed"""
TOOL_FAILED = "pmoves.agent.tool.failed.v1"

# =============================================================================
# A2A (Agent-to-Agent) Coordination Events
# =============================================================================

"""Task submitted via A2A protocol"""
A2A_TASK_SUBMITTED = "pmoves.a2a.task.submitted.v1"

"""A2A task received by target agent"""
A2A_TASK_RECEIVED = "pmoves.a2a.task.received.v1"

"""A2A artifact ready (output produced)"""
A2A_ARTIFACT_READY = "pmoves.a2a.artifact.ready.v1"

# =============================================================================
# CHIT Geometry Events (future)
# =============================================================================

"""Geometry published to GEOMETRY BUS"""
GEOMETRY_PUBLISHED = "pmoves.geometry.published.v1"

"""CGP (Compressed Geometric Primitive) ready for transmission"""
CGP_READY = "pmoves.geometry.cgp.ready.v1"

# =============================================================================
# Wildcard Subjects (for catching all events in a category)
# =============================================================================

"""All PMOVES events (catch-all)"""
ALL_PMOVES_EVENTS = "pmoves.>"

"""All agent lifecycle events"""
ALL_AGENT_EVENTS = "pmoves.agent.>"

"""All work/task events"""
ALL_WORK_EVENTS = "pmoves.work.>"

"""All A2A coordination events"""
ALL_A2A_EVENTS = "pmoves.a2a.>"

"""All geometry/CHIT events"""
ALL_GEOMETRY_EVENTS = "pmoves.geometry.>"

# =============================================================================
# Subject Catalog (for documentation and validation)
# =============================================================================

EVENT_SUBJECTS = {
    "AGENT_STARTED": AGENT_STARTED,
    "AGENT_STOPPED": AGENT_STOPPED,
    "AGENT_ERROR": AGENT_ERROR,
    "TASK_CREATED": TASK_CREATED,
    "TASK_ASSIGNED": TASK_ASSIGNED,
    "TASK_COMPLETED": TASK_COMPLETED,
    "TASK_FAILED": TASK_FAILED,
    "TOOL_STARTED": TOOL_STARTED,
    "TOOL_COMPLETED": TOOL_COMPLETED,
    "TOOL_FAILED": TOOL_FAILED,
    "A2A_TASK_SUBMITTED": A2A_TASK_SUBMITTED,
    "A2A_TASK_RECEIVED": A2A_TASK_RECEIVED,
    "A2A_ARTIFACT_READY": A2A_ARTIFACT_READY,
    "GEOMETRY_PUBLISHED": GEOMETRY_PUBLISHED,
    "CGP_READY": CGP_READY,
}

WILDCARD_SUBJECTS = {
    "ALL_PMOVES_EVENTS": ALL_PMOVES_EVENTS,
    "ALL_AGENT_EVENTS": ALL_AGENT_EVENTS,
    "ALL_WORK_EVENTS": ALL_WORK_EVENTS,
    "ALL_A2A_EVENTS": ALL_A2A_EVENTS,
    "ALL_GEOMETRY_EVENTS": ALL_GEOMETRY_EVENTS,
}


def validate_subject(subject: str) -> bool:
    """
    Validate subject format.

    Args:
        subject: NATS subject to validate

    Returns:
        True if valid, False otherwise
    """
    # Basic validation: must contain at least 3 parts separated by dots
    parts = subject.split(".")
    if len(parts) < 3:
        return False

    # Must start with "pmoves"
    if parts[0] != "pmoves":
        return False

    # Version must be present and start with "v"
    version = parts[-1]
    if not version.startswith("v"):
        return False

    return True


def get_event_category(subject: str) -> str:
    """
    Extract event category from subject.

    Args:
        subject: NATS subject

    Returns:
        Category name (e.g., "agent", "work", "a2a", "geometry")
    """
    parts = subject.split(".")
    if len(parts) >= 2:
        return parts[1]
    return "unknown"
