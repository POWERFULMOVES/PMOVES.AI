"""Fleet Sentinel — the registry consumer that connects the autonetwork primitives.

Design: docs/services/IDE_PINOKIO_FLEET_CONSOLE_PLAN.md (PR #2916)
Lane claim: AGNOTE4482PHI.t1 2026-09-04T16:51:00Z (HERMES-AGENT)

The pieces existed but were disconnected: services announce on
services.announce.v1 (nats_service_listener), a registry with 4-level fallback
exists (service_registry), healthz is fleet-standard, and channel-monitor
demonstrates the poll pattern. This service closes the loop:

  announce → registry row → /registry.json (Pinokio/CLI/A2UI consume)
           → health poll → 3× failure → Known-Road restart (rate-limited)

Reuses ServiceAnnouncementListener verbatim (queue group dedupes multi-
sentinel). The Known-Road recovery path is the ONLY restart mechanism —
never raw `docker restart`, per AGENTS.md damage-control doctrine.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger("fleet_sentinel")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
POLL_INTERVAL = float(os.environ.get("SENTINEL_POLL_INTERVAL", "30"))
FAILURE_THRESHOLD = int(os.environ.get("SENTINEL_FAILURE_THRESHOLD", "3"))
RESTART_COOLDOWN = float(os.environ.get("SENTINEL_RESTART_COOLDOWN", "600"))
ANNOUNCE_STALE_FACTOR = float(os.environ.get("SENTINEL_STALE_FACTOR", "2.0"))
PMOVES_DIR = Path(os.environ.get("SENTINEL_PMOVES_DIR", "/srv/pmoves"))
ACTION_TRAIL = Path(os.environ.get("SENTINEL_ACTION_TRAIL", "/data/fleet-sentinel/actions.jsonl"))
SELF_HEAL = os.environ.get("SENTINEL_SELF_HEAL", "1") == "1"
# Slug allowlist: announcements are untrusted input. A slug that fails this
# pattern can never reach a shell command (RCE via metacharacters, review P1).
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
HTTP_TIMEOUT = float(os.environ.get("SENTINEL_HTTP_TIMEOUT", "5"))


@dataclass
class SentinelEntry:
    slug: str
    name: str
    url: str
    health_check: str
    tier: str
    port: Optional[int] = None
    last_announce: float = field(default_factory=time.time)
    health: str = "unknown"  # unknown | healthy | failing | stale
    consecutive_failures: int = 0
    last_restart: float = 0.0
    restarts: int = 0
    announce_interval_s: Optional[float] = None  # None = one-shot startup announce

    def to_public(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "url": self.url,
            "health_check": self.health_check,
            "tier": self.tier,
            "port": self.port,
            "health": self.health,
            "last_announce_age_s": round(time.time() - self.last_announce, 1),
            "restarts": self.restarts,
        }


class FleetSentinel:
    def __init__(self) -> None:
        self.registry: Dict[str, SentinelEntry] = {}
        self.actions: list[Dict[str, Any]] = []
        self.listener = None

    async def start_listener(self) -> None:
        try:
            from services.common.nats_service_listener import ServiceAnnouncementListener
        except ImportError:
            # Standalone image layout (no services/common sibling): subscribe
            # directly on the announce subject with the same schema.
            return await self._start_raw_listener()

        async def on_announce(info: Any) -> None:
            slug = str(info.slug)
            if not SLUG_RE.match(slug):
                logger.warning("rejected announcement with invalid slug: %r", info.slug)
                return
            prev = self.registry.get(slug)
            self.registry[slug] = SentinelEntry(
                slug=slug,
                name=info.name,
                url=getattr(info, "base_url", "") or "",
                health_check=info.health_check_url or "",
                tier=(getattr(info, "tier", None).value if getattr(info, "tier", None) else "unknown"),
                port=info.default_port,
                consecutive_failures=prev.consecutive_failures if prev else 0,
                restarts=prev.restarts if prev else 0,
                health=(prev.health if prev else "unknown"),
                announce_interval_s=getattr(info, "metadata", {}).get("announce_interval_s")
                if isinstance(getattr(info, "metadata", None), dict) else None,
            )
            logger.info("registry upsert: %s (tier=%s)", slug, getattr(info, "tier", "?"))

        # Constructor-arg callback (ServiceInfo), per nats_service_listener.py:77-92
        self.listener = ServiceAnnouncementListener(
            nats_url=NATS_URL, on_announcement=on_announce
        )
        await self.listener.start()
        logger.info("announce listener started (%s)", NATS_URL)

    async def poll_once(self) -> None:
        import urllib.request

        now = time.time()
        for slug, entry in list(self.registry.items()):
            if not entry.health_check:
                entry.health = "unknown"
                continue
            # NOTE: existing publishers announce ONCE at startup (announce_service
            # closes its connection); there is no heartbeat yet. Until producers
            # adopt the BackgroundAnnouncer, announce-age staleness would mark
            # every service stale after ~2min — so staleness is HEARTBEAT-GATED:
            # only applies when the announcement payload declares an interval.
            if entry.announce_interval_s and now - entry.last_announce > ANNOUNCE_STALE_FACTOR * entry.announce_interval_s:
                entry.health = "stale"
                continue
            try:
                with urllib.request.urlopen(entry.health_check, timeout=HTTP_TIMEOUT) as resp:
                    ok = resp.status == 200
            except Exception:
                ok = False
            if ok:
                entry.health = "healthy"
                entry.consecutive_failures = 0
            else:
                entry.consecutive_failures += 1
                entry.health = "failing"
                if (
                    SELF_HEAL
                    and entry.consecutive_failures >= FAILURE_THRESHOLD
                    and now - entry.last_restart > RESTART_COOLDOWN
                ):
                    await self.known_road_restart(slug)

    async def known_road_restart(self, slug: str) -> None:
        """The ONLY sanctioned recovery: make secrets-funnel && make up-<svc>.

        Raw `docker restart` is damage-control-blocked for good reason: it
        bypasses env re-projection. The Known Road re-funnels env first.
        """
        entry = self.registry[slug]
        entry.last_restart = time.time()
        entry.restarts += 1
        action = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "known_road_restart",
            "slug": slug,
            "failures": entry.consecutive_failures,
        }
        logger.warning("self-heal: %s after %d failures", slug, entry.consecutive_failures)
        # Fixed argv (no shell, no interpolation beyond the validated slug),
        # correct checkout layout: repo root mounted at /srv/pmoves -> the
        # pmoves Makefile lives at /srv/pmoves/pmoves.
        make_dir = PMOVES_DIR / "pmoves" if (PMOVES_DIR / "pmoves" / "Makefile").exists() else PMOVES_DIR
        try:
            proc = await asyncio.create_subprocess_exec(
                "bash", str(make_dir / "scripts" / "with-env.sh"), "make", "-C", str(make_dir),
                "secrets-funnel",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            if proc.returncode == 0:
                proc = await asyncio.create_subprocess_exec(
                    "bash", str(make_dir / "scripts" / "with-env.sh"), "make", "-C", str(make_dir),
                    f"up-{slug}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
            out, _ = await proc.communicate()
            action["exit"] = proc.returncode
            action["tail"] = (out or b"").decode(errors="replace")[-500:]
        except Exception as exc:
            action["error"] = str(exc)
        self.actions.append(action)
        ACTION_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        with ACTION_TRAIL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(action) + "\n")
        entry.consecutive_failures = 0  # give the restart a fresh window

    def registry_json(self) -> Dict[str, Any]:
        return {
            "generated": datetime.now(timezone.utc).isoformat(),
            "poll_interval_s": POLL_INTERVAL,
            "services": sorted(
                (e.to_public() for e in self.registry.values()),
                key=lambda s: (s["tier"], s["slug"]),
            ),
        }


sentinel = FleetSentinel()
app = FastAPI(title="PMOVES Fleet Sentinel", version="1.0.0")


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(sentinel.start_listener())
    asyncio.create_task(_poll_loop())


async def _poll_loop() -> None:
    while True:
        try:
            await sentinel.poll_once()
        except Exception:
            logger.exception("poll cycle failed")
        await asyncio.sleep(POLL_INTERVAL)


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "listener": sentinel.listener.is_running if sentinel.listener else False,
        "services": len(sentinel.registry),
        "self_heal": SELF_HEAL,
    }


@app.get("/registry.json")
async def registry_json() -> JSONResponse:
    return JSONResponse(sentinel.registry_json())


@app.get("/actions")
async def actions() -> Dict[str, Any]:
    return {"actions": sentinel.actions[-100:]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("SENTINEL_PORT", "8116")))


    async def _start_raw_listener(self) -> None:
        """Minimal subscriber when services.common is unavailable in-image."""
        import nats as nats_lib
        import urllib.parse

        nc = await nats_lib.connect(NATS_URL)
        self._raw_nc = nc

        async def cb(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
            except Exception:
                return
            slug = str(data.get("slug", ""))
            if not SLUG_RE.match(slug):
                return
            prev = self.registry.get(slug)
            md = data.get("metadata") or {}
            self.registry[slug] = SentinelEntry(
                slug=slug,
                name=data.get("name", slug),
                url=data.get("url", ""),
                health_check=data.get("health_check", ""),
                tier=str(data.get("tier", "unknown")),
                port=data.get("port"),
                consecutive_failures=prev.consecutive_failures if prev else 0,
                restarts=prev.restarts if prev else 0,
                health=(prev.health if prev else "unknown"),
                announce_interval_s=md.get("announce_interval_s") if isinstance(md, dict) else None,
            )

        await nc.subscribe("services.announce.v1", cb=cb)
        logger.info("raw announce listener started (%s)", NATS_URL)
