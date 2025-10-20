"""EvoSwarm controller service.

This FastAPI worker periodically fetches recent geometry packets, evaluates fitness
metrics, and publishes updated parameter packs for CGP builders and decoders.
The concrete evolutionary logic will be filled in subsequent iterations; for now
we scaffold configuration, health endpoints, and background scheduling hooks.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI

logger = logging.getLogger("evo-controller")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(title="PMOVES Evo Controller", version="0.1.0")


@dataclass
class EvoConfig:
    """Runtime configuration for the controller loop."""

    rest_url: Optional[str] = field(default_factory=lambda: os.getenv("SUPA_REST_URL") or os.getenv("SUPABASE_REST_URL"))
    service_key: Optional[str] = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    poll_seconds: float = float(os.getenv("EVOSWARM_POLL_SECONDS", "300"))
    sample_limit: int = int(os.getenv("EVOSWARM_SAMPLE_LIMIT", "25"))
    namespace: Optional[str] = os.getenv("EVOSWARM_NAMESPACE")


class EvoSwarmController:
    """Background task coordinator for the evolutionary loop."""

    def __init__(self, config: EvoConfig) -> None:
        self.config = config
        self._stop = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        if self._task is None:
            logger.info("starting EvoSwarm controller loop")
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
            self._task = asyncio.create_task(self._run())

    async def shutdown(self) -> None:
        if self._task:
            logger.info("stopping EvoSwarm controller loop")
            self._stop.set()
            await self._task
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            start = time.perf_counter()
            try:
                await self._tick()
            except Exception:  # pragma: no cover - logged for observability
                logger.exception("evoswarm tick failed")
            elapsed = time.perf_counter() - start
            sleep_for = max(5.0, self.config.poll_seconds - elapsed)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                continue

    async def _tick(self) -> None:
        """Single polling iteration: fetch recent CGPs and publish a heartbeat pack.

        This is a minimal implementation that demonstrates end-to-end wiring by
        upserting a draft cg_builder parameter pack and publishing a
        geometry.swarm.meta.v1 event via Agent Zero. Real fitness logic will
        replace this placeholder.
        """

        if not self.config.rest_url:
            logger.warning("Supabase REST URL not configured; skipping tick")
            return
        # Fetch recent CGPs (for future fitness computation)
        payload = await self._fetch_recent_cgps()
        logger.debug("fetched %s CGPs for evaluation", len(payload))

        # Upsert a minimal parameter pack (namespace inferred from first CGP)
        namespace = self.config.namespace or (payload[0].get("namespace") if payload and isinstance(payload[0], dict) else "pmoves")
        pack = {
            "namespace": namespace,
            "modality": "video",
            "version": time.strftime("v%Y%m%d-%H%M%S"),
            "status": "draft",
            "pack_type": "cg_builder",
            "params": {"K": 8, "bins": 32, "tau": 0.2, "beta": 0.7},
            "energy": {"note": "placeholder"},
        }
        ok = await self._upsert_pack(pack)
        if ok:
            await self._publish_swarm_meta(pack)

    async def _fetch_recent_cgps(self) -> list[Dict[str, Any]]:
        """Stub for pulling recent CGPs from Supabase/PostgREST."""

        if not self._client or not self.config.rest_url:
            return []
        base_url = self.config.rest_url.rstrip("/")
        url = f"{base_url}/geometry_cgp_v1"
        headers = {"Accept": "application/json"}
        if self.config.service_key:
            headers.update({"apikey": self.config.service_key, "Authorization": f"Bearer {self.config.service_key}"})
        params = {
            "select": "payload,created_at",
            "order": "created_at.desc",
            "limit": str(self.config.sample_limit),
        }
        if self.config.namespace:
            params["payload->>namespace"] = f"eq.{self.config.namespace}"
        try:
            resp = await self._client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            rows = resp.json()
        except httpx.HTTPStatusError as exc:  # pragma: no cover - network failure
            logger.error("Supabase fetch failed: %s", exc)
            return []
        except Exception:
            logger.exception("unexpected error pulling CGPs")
            return []
        return [row.get("payload") for row in rows if isinstance(row, dict)]

    async def _upsert_pack(self, pack: Dict[str, Any]) -> bool:
        if not self._client or not self.config.rest_url:
            return False
        base_url = self.config.rest_url.rstrip("/")
        url = f"{base_url}/geometry_parameter_packs"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Prefer": "return=representation,resolution=merge-duplicates",
        }
        if self.config.service_key:
            headers.update({"apikey": self.config.service_key, "Authorization": f"Bearer {self.config.service_key}"})
        try:
            resp = await self._client.post(url, headers=headers, json=[pack])
            resp.raise_for_status()
            record: Optional[Dict[str, Any]] = None
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            if isinstance(payload, list) and payload:
                maybe_record = payload[0]
                record = maybe_record if isinstance(maybe_record, dict) else None
            elif isinstance(payload, dict):
                record = payload
            if record:
                pack.update(record)
            return True
        except httpx.HTTPStatusError as exc:  # pragma: no cover
            logger.error("pack upsert failed: %s", exc)
            return False
        except Exception:
            logger.exception("unexpected error upserting pack")
            return False

    async def _publish_swarm_meta(self, pack: Dict[str, Any]) -> None:
        base = os.getenv("AGENT_ZERO_BASE_URL") or os.getenv("AGENTZERO_BASE_URL") or "http://agent-zero:8080"
        url = base.rstrip("/") + "/events/publish"
        body = {
            "topic": "geometry.swarm.meta.v1",
            "source": "evo-controller",
            "payload": {
                "namespace": pack.get("namespace"),
                "modality": pack.get("modality"),
                "pack_id": pack.get("id") or "",
                "status": pack.get("status"),
                "version": pack.get("version"),
                "population_id": pack.get("population_id"),
                "best_fitness": pack.get("fitness"),
                "metrics": pack.get("energy"),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                r = await client.post(url, json=body)
                r.raise_for_status()
        except Exception:  # pragma: no cover
            logger.warning("failed to publish geometry.swarm.meta.v1 (agent-zero not reachable?)")


_controller = EvoSwarmController(EvoConfig())


@app.on_event("startup")
async def _startup() -> None:
    await _controller.start()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await _controller.shutdown()


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Liveness check."""

    return {"ok": True, "loop_running": _controller._task is not None}


@app.get("/config")
async def config() -> Dict[str, Any]:
    """Expose current controller configuration for observability."""

    cfg = _controller.config
    return {
        "poll_seconds": cfg.poll_seconds,
        "sample_limit": cfg.sample_limit,
        "namespace": cfg.namespace,
        "rest_url_configured": bool(cfg.rest_url),
    }
