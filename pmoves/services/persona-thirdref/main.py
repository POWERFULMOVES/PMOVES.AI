"""persona-thirdref service — consumption joiner + shape-trace emitter.

Environment:
  NATS_URL              default nats://nats:pmoves@nats:4222
  SUPABASE_URL          PostgREST base (e.g. http://supabase-kong:8000)
  SUPABASE_ANON_KEY     anon key for PostgREST reads
  PERSONA_THIRDREF_TOKEN  shared secret for the HTTP record endpoint
                          ("" disables HTTP entirely — NATS-only mode)
  PERSONA_THIRDREF_PROFILE_THRESHOLD  events before profile update (default 10)

Subjects:
  subscribes  persona.consumption.recorded.v1
  publishes   shape.trace.recorded.v1
              shape.profile.updated.v1   (at threshold)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

import jsonschema
from fastapi import FastAPI, HTTPException, Request

LOGGER = logging.getLogger("persona-thirdref")
_CANDIDATE_SCHEMA_DIRS = [
    # repo layout: services/persona-thirdref/main.py -> pmoves/contracts/...
    Path(__file__).resolve().parents[2] / "contracts" / "schemas",
    # container layout: schema shipped at /app/contracts (root build context)
    Path("/app/contracts/schemas"),
]
SCHEMA_DIR = next(d for d in _CANDIDATE_SCHEMA_DIRS
                  if (d / "persona" / "consumption.recorded.v1.schema.json").exists())
CONSUMPTION_SCHEMA = json.loads(
    (SCHEMA_DIR / "persona" / "consumption.recorded.v1.schema.json").read_text()
)
TRACE_REQUIRED = ["user_id", "agent_id", "timestamp", "interaction_type"]

SUB_CONSUMPTION = "persona.consumption.recorded.v1"
PUB_TRACE = "shape.trace.recorded.v1"
PUB_PROFILE = "shape.profile.updated.v1"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


class Joiner:
    """Resolve an item's resonance domains from Supabase enrichment.

    Kept synchronous-and-injectable so tests pass a stubbed fetch without
    network. httpx is imported lazily: the join path degrades to
    caller-provided domains when the client is unavailable.
    """

    def __init__(self, base_url: str, anon_key: str, http_fetch=None):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self._fetch = http_fetch  # callable(method, url, headers) -> (status, body)

    def youtube_video(self, video_id: str) -> dict[str, Any]:
        """Return {resonance_domain, resonance_secondary, persona_signal,
        curriculum_track} for a video id, or {} when unresolvable."""
        if not self.base_url or not self.anon_key:
            return {}
        url = (
            f"{self.base_url}/rest/v1/youtube_videos"
            f"?video_id=eq.{video_id}"
            "&select=resonance_domain,resonance_secondary,persona_signal,curriculum_track"
        )
        headers = {"apikey": self.anon_key, "Authorization": f"Bearer {self.anon_key}"}
        try:
            if self._fetch is not None:
                status, body = self._fetch("GET", url, headers)
            else:
                import httpx

                with httpx.Client(timeout=10) as client:
                    resp = client.get(url, headers=headers)
                    status, body = resp.status_code, resp.text
            if status != 200:
                LOGGER.warning("youtube_videos join failed: %s %s", status, body[:120])
                return {}
            rows = json.loads(body) if body else []
            return rows[0] if rows else {}
        except Exception as exc:  # noqa: BLE001 — degrade, never drop the event
            LOGGER.warning("join transport error: %s", exc)
            return {}


def join_domains(event: dict[str, Any], joiner: Joiner | None) -> list[str]:
    """Merge caller-provided domains with enrichment-joined domains."""
    domains: list[str] = []
    provided = list(event.get("resonance_domains") or [])
    if event.get("item_kind") == "youtube_video" and joiner is not None:
        row = joiner.youtube_video(event["item_id"])
        primary = row.get("resonance_domain")
        if primary:
            domains.append(primary)
        domains.extend(row.get("resonance_secondary") or [])
    domains.extend(provided)
    seen: set[str] = set()
    ordered: list[str] = []
    for domain in domains:
        if domain and domain not in seen:
            seen.add(domain)
            ordered.append(domain)
    return ordered


def build_trace(event: dict[str, Any], domains: list[str]) -> dict[str, Any]:
    """shape.trace.recorded.v1 payload for a consumption event."""
    trace: dict[str, Any] = {
        "interaction_type": "media",
        "agent_id": event.get("agent_id", ""),
        "user_id": event.get("user_id", ""),
        "timestamp": event["timestamp"],
        "resonance_domains": domains,
        "media_modality": "audio" if event.get("item_kind") == "beat" else "video",
    }
    if event.get("session_id"):
        trace["session_id"] = event["session_id"]
    if event.get("item_kind") == "youtube_video":
        trace["tool_ids"] = [f"youtube:{event['item_id']}"]
    return trace


def validate_consumption(event: dict[str, Any]) -> None:
    jsonschema.validate(event, CONSUMPTION_SCHEMA)
    kind = event["consumer_kind"]
    if kind == "human" and not event.get("user_id"):
        raise jsonschema.ValidationError("consumer_kind=human requires user_id")
    if kind == "agent" and not event.get("agent_id"):
        raise jsonschema.ValidationError("consumer_kind=agent requires agent_id")


class Accumulator:
    """In-memory domain histogram per identity; emits profile updates at
    threshold. Persisted state is deliberately out of scope for v1: the
    emitted shape traces are the durable record; this only decides WHEN
    the enrichment moment fires."""

    def __init__(self, threshold: int = 10):
        self.threshold = max(1, threshold)
        self.counts: dict[str, Counter] = {}
        self.events: dict[str, int] = {}

    def identity(self, event: dict[str, Any]) -> str:
        return (
            f"agent:{event['agent_id']}"
            if event["consumer_kind"] == "agent"
            else f"user:{event.get('user_id', 'unknown')}"
        )

    def record(self, event: dict[str, Any], domains: list[str]) -> dict[str, Any] | None:
        key = self.identity(event)
        bucket = self.counts.setdefault(key, Counter())
        bucket.update(domains or ["unclassified"])
        self.events[key] = self.events.get(key, 0) + 1
        if self.events[key] % self.threshold == 0:
            total = sum(bucket.values())
            return {
                "identity": key,
                "total_traces": total,
                "resonance_weights": {
                    domain: round(count / total, 4)
                    for domain, count in bucket.most_common()
                },
                "timestamp": event["timestamp"],
            }
        return None


class Service:
    """Wiring: validate -> join -> trace emit -> maybe profile emit."""

    def __init__(self, joiner: Joiner | None = None, accumulator: Accumulator | None = None,
                 publisher=None):
        self.joiner = joiner
        self.accumulator = accumulator or Accumulator(
            int(_env("PERSONA_THIRDREF_PROFILE_THRESHOLD", "10"))
        )
        # publisher(subject, payload) — async callable; None drops to log-only.
        self.publisher = publisher
        self.processed = 0
        self.emitted_traces = 0
        self.emitted_profiles = 0

    async def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        validate_consumption(event)
        domains = join_domains(event, self.joiner)
        trace = build_trace(event, domains)
        profile = self.accumulator.record(event, domains)
        self.processed += 1
        self.emitted_traces += 1
        if self.publisher is not None:
            await self.publisher(PUB_TRACE, trace)
            if profile is not None:
                self.emitted_profiles += 1
                await self.publisher(PUB_PROFILE, profile)
        else:
            LOGGER.info("trace: %s", json.dumps(trace)[:200])
            if profile is not None:
                LOGGER.info("profile: %s", json.dumps(profile)[:200])
        return {"trace": trace, "profile": profile}



def create_app(joiner: Joiner | None = None, service: Service | None = None) -> FastAPI:
    app = FastAPI(title="persona-thirdref", version="0.1.0")
    svc = service or Service(joiner=joiner)
    token = _env("PERSONA_THIRDREF_TOKEN")
    started = time.time()
    app.state.service = svc
    app.state.nats_task = None

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover — transport wiring
        # Wiring runs as a BACKGROUND task: nats-py's reconnect loop can hang
        # indefinitely on an unresolvable host, and startup must never block
        # on transport — healthz has to answer even when the bus is gone.
        asyncio.create_task(_wire_bus(svc))

    async def _wire_bus(svc: Service) -> None:
        if _env("PERSONA_THIRDREF_DISABLE_NATS"):
            return
        url = _env("NATS_URL", "nats://nats:pmoves@nats:4222")
        try:
            import nats.aio.client as nats_client

            async def bridge(msg) -> None:
                try:
                    await svc.handle(json.loads(msg.data.decode()))
                except jsonschema.ValidationError as exc:
                    LOGGER.warning("invalid consumption event: %s", exc.message)
                except Exception:  # noqa: BLE001
                    LOGGER.exception("handler error")

            nc = nats_client.Client()
            await nc.connect(url, connect_timeout=5, max_reconnect_attempts=0)
            await nc.subscribe(SUB_CONSUMPTION, cb=bridge)

            async def publish(subject: str, payload: dict[str, Any]) -> None:
                await nc.publish(subject, json.dumps(payload).encode())

            svc.publisher = publish
            LOGGER.info("bus wired: sub %s", SUB_CONSUMPTION)
        except Exception as exc:  # noqa: BLE001 — degrade, never die
            LOGGER.warning("bus wiring offline (%s); HTTP + log-only mode", exc)

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {
            "status": "ok",
            "processed": svc.processed,
            "traces": svc.emitted_traces,
            "profiles": svc.emitted_profiles,
            "uptime_s": round(time.time() - started, 1),
        }

    @app.post("/v1/record")
    async def record(request: Request) -> dict[str, Any]:
        if not token:
            raise HTTPException(503, "HTTP record endpoint disabled (no token configured)")
        supplied = request.headers.get("X-Thirdref-Token", "")
        if supplied != token:
            raise HTTPException(401, "bad token")
        event = await request.json()
        try:
            result = await svc.handle(event)
        except jsonschema.ValidationError as exc:
            raise HTTPException(422, f"invalid event: {exc.message}") from exc
        return {
            "ok": True,
            "domains": result["trace"]["resonance_domains"],
            "profile_updated": result["profile"] is not None,
        }

    return app


app = create_app()


def main() -> None:  # pragma: no cover — container entrypoint
    logging.basicConfig(level=logging.INFO)
    import uvicorn

    uvicorn.run(
        "persona_thirdref.main:app" if __package__ else "main:app",
        host="0.0.0.0",
        port=int(_env("PERSONA_THIRDREF_PORT", "8099")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
