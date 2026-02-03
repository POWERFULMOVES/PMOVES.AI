"""HTTP endpoints for interacting with the gateway event bus."""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...event_bus import EventBus

router = APIRouter(prefix="/events", tags=["Events"])

_bus_ref: EventBus | None = None
_local_recent: Deque[Dict[str, Any]] = deque(maxlen=50)


def _get_bus(request: Request) -> EventBus | None:
    bus = getattr(request.app.state, "event_bus", None)
    return bus if isinstance(bus, EventBus) else None


class PublishRequest(BaseModel):
    topic: str
    payload: Dict[str, Any]
    correlation_id: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)
    source: str = Field(default="gateway")


@router.get("/recent")
def recent_events(request: Request, limit: int = Query(20, ge=1, le=200)) -> Dict[str, Any]:
    bus = _get_bus(request)
    if bus is not None:
        return {"events": bus.recent(limit)}
    return {"events": list(_local_recent)[:limit]}


@router.get("/topics")
def list_topics(request: Request) -> Dict[str, Any]:
    bus = _get_bus(request)
    return {"topics": bus.topics if bus is not None else []}


@router.post("/publish")
async def publish_event(req: PublishRequest, request: Request) -> Dict[str, Any]:
    bus = _get_bus(request)
    if bus is None:
        raise HTTPException(status_code=503, detail="Event bus unavailable")
    envelope = await bus.publish(
        req.topic,
        req.payload,
        correlation_id=req.correlation_id,
        parent_id=req.parent_id,
        source=req.source,
    )
    return {"ok": True, "envelope": envelope}


def set_event_bus(bus: EventBus | None) -> None:
    global _bus_ref
    _bus_ref = bus


def emit_event(event: Dict[str, Any]) -> Dict[str, Any] | None:
    topic = str(event.get("topic") or event.get("type") or "gateway.event")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {
        k: v for k, v in event.items() if k != "topic"
    }
    if _bus_ref is not None:
        return _bus_ref.record_local(topic, payload)
    envelope = {"topic": topic, "payload": payload}
    _local_recent.appendleft(envelope)
    return envelope
