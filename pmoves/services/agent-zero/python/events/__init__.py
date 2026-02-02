"""
Event Bus Package for Agent Zero

This package provides event-driven coordination for PMOVES.AI agents
via NATS message bus integration.

Based on PMOVES-ToKenism-Multi event bus patterns.
"""

from .bus import EventBus, Event, get_event_bus
from .subjects import (
    AGENT_STARTED,
    AGENT_STOPPED,
    AGENT_ERROR,
    TASK_CREATED,
    TASK_ASSIGNED,
    TASK_COMPLETED,
    TASK_FAILED,
    TOOL_STARTED,
    TOOL_COMPLETED,
    TOOL_FAILED,
    A2A_TASK_SUBMITTED,
    A2A_TASK_RECEIVED,
    A2A_ARTIFACT_READY,
    GEOMETRY_PUBLISHED,
    CGP_READY,
    ALL_PMOVES_EVENTS,
    ALL_AGENT_EVENTS,
    ALL_WORK_EVENTS,
)
from .schema import SchemaValidator

__all__ = [
    # Core classes
    "EventBus",
    "Event",
    "get_event_bus",
    "SchemaValidator",
    # Event subjects
    "AGENT_STARTED",
    "AGENT_STOPPED",
    "AGENT_ERROR",
    "TASK_CREATED",
    "TASK_ASSIGNED",
    "TASK_COMPLETED",
    "TASK_FAILED",
    "TOOL_STARTED",
    "TOOL_COMPLETED",
    "TOOL_FAILED",
    "A2A_TASK_SUBMITTED",
    "A2A_TASK_RECEIVED",
    "A2A_ARTIFACT_READY",
    "GEOMETRY_PUBLISHED",
    "CGP_READY",
    "Wildcard subjects",
    "ALL_PMOVES_EVENTS",
    "ALL_AGENT_EVENTS",
    "ALL_WORK_EVENTS",
]

__version__ = "1.0.0"
