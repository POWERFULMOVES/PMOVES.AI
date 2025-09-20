from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, HTTPException
from nats.aio.client import Client as NATS
from pydantic import BaseModel, Field, HttpUrl

from services.common.events import envelope
from .orchestrator import ArchonOrchestrator

logger = logging.getLogger("archon.main")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
PORT = int(os.environ.get("PORT", 8090))


class CrawlJob(BaseModel):
    url: HttpUrl
    task_id: Optional[str] = None
    depth: Optional[int] = Field(default=None, ge=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArchonService:
    def __init__(self, *, nats_url: str = NATS_URL) -> None:
        self._nats_url = nats_url
        self._nc: Optional[NATS] = None
        self._ready = asyncio.Event()
        self._logger = logging.getLogger("archon.service")
        self._subscriptions = (
            "archon.crawl.request",
            "archon.crawl.request.v1",
            "ingest.document.ready.v1",
            "ingest.file.added.v1",
            "ingest.transcript.ready.v1",
        )
        self.orchestrator = ArchonOrchestrator(self.publish_event, logger=logging.getLogger("archon.orchestrator"))

    @property
    def is_connected(self) -> bool:
        return self._ready.is_set()

    async def start(self) -> None:
        if self._nc is not None:
            return
        self._logger.info("Connecting to NATS at %s", self._nats_url)
        self._nc = NATS()
        await self._nc.connect(servers=[self._nats_url])
        for subject in self._subscriptions:
            await self._nc.subscribe(subject, cb=self._on_message)
        self._ready.set()
        self._logger.info("Archon service connected and subscriptions registered")

    async def stop(self) -> None:
        if self._nc is None:
            return
        self._logger.info("Draining NATS connection")
        await self.orchestrator.shutdown()
        try:
            await self._nc.drain()
        finally:
            await self._nc.close()
            self._nc = None
            self._ready.clear()
        self._logger.info("Archon service disconnected")

    async def publish_event(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "archon",
    ) -> Dict[str, Any]:
        await self._ready.wait()
        assert self._nc is not None
        env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
        await self._nc.publish(topic, json.dumps(env).encode("utf-8"))
        await self._nc.flush()
        return env

    async def handle_local_event(
        self,
        topic: str,
        payload: Dict[str, Any],
        *,
        correlation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        source: str = "archon",
    ) -> Any:
        env = envelope(topic, payload, correlation_id=correlation_id, parent_id=parent_id, source=source)
        return await self.orchestrator.dispatch(topic, env)

    async def _on_message(self, msg) -> None:
        data: Dict[str, Any]
        try:
            data = json.loads(msg.data.decode("utf-8"))
        except json.JSONDecodeError:
            self._logger.exception("Invalid JSON received on %s", msg.subject)
            return
        if not isinstance(data, dict):
            self._logger.warning("Dropping non-dict payload from %s", msg.subject)
            return
        data.setdefault("topic", msg.subject)
        await self.orchestrator.dispatch(msg.subject, data)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Archon service")
    service = ArchonService()
    await service.start()
    app.state.service = service
    try:
        yield
    finally:
        logger.info("Stopping Archon service")
        await service.stop()


app = FastAPI(title="Archon (PMOVES v5)", lifespan=lifespan)


def get_archon_service() -> ArchonService:
    service = getattr(app.state, "service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Archon service unavailable")
    return service


@app.get("/healthz")
async def healthz(service: ArchonService = Depends(get_archon_service)) -> Dict[str, Any]:
    status = "ok" if service.is_connected else "degraded"
    return {"status": status, "service": "archon", "nats": service.is_connected}


@app.post("/events/publish")
async def events_publish(
    body: Dict[str, Any] = Body(...),
    service: ArchonService = Depends(get_archon_service),
) -> Dict[str, Any]:
    topic = body.get("topic")
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")
    payload = body.get("payload") or {}
    env = await service.publish_event(topic, payload, source="archon.api")
    return {"published": topic, "id": env["id"]}


@app.post("/archon/crawl")
async def submit_crawl(
    job: CrawlJob,
    service: ArchonService = Depends(get_archon_service),
) -> Dict[str, Any]:
    payload = job.model_dump(exclude_none=True)
    task_id = payload.get("task_id") or str(uuid.uuid4())
    payload["task_id"] = task_id
    await service.publish_event("archon.crawl.request.v1", payload, source="archon.api")
    return {"task_id": task_id}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, service: ArchonService = Depends(get_archon_service)) -> Dict[str, Any]:
    snapshot = await service.orchestrator.snapshot_tasks()
    task = snapshot.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task_id": task_id, **task}


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=os.environ.get("ARCHON_LOG_LEVEL", "INFO"))
    uvicorn.run("services.archon.main:app", host="0.0.0.0", port=PORT, reload=False)
