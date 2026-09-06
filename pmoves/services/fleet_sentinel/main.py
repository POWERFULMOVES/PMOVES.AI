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

Honesty contract (this fleet's dominant defect class is "reports success
throughout"): every capability this service advertises is probed, and when a
prerequisite is absent the service says so in /healthz and in the action
trail rather than emitting a doomed subprocess and recording a nonzero exit.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
HTTP_TIMEOUT = float(os.environ.get("SENTINEL_HTTP_TIMEOUT", "5"))
POLL_CONCURRENCY = int(os.environ.get("SENTINEL_POLL_CONCURRENCY", "16"))

# --- Untrusted-input boundary -------------------------------------------------
# A slug arrives from a NATS announcement. Anyone who can publish on
# services.announce.v1 controls it, so it is untrusted input that ends up in an
# argv position of a `make` invocation.
#
# ALLOWLIST, not denylist: this repo has been bitten by denylists that were
# bypassed by shapes nobody had listed. SLUG_RE states what is *permitted* —
# DNS-label-shaped names (lowercase alnum, internal hyphens, <=64 chars) —
# and everything else is refused. Note the anchors are ^...$ with no `re.M`
# and the class excludes newline, so a payload like "svc\nrm -rf /" cannot
# smuggle a second line past the match.
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# Optional second gate: when set, ONLY these slugs are eligible for self-heal.
# Unset means "any slug that satisfies SLUG_RE", which is the argv-safe
# boundary; set it on nodes that want an explicit named roster.
HEAL_ALLOWLIST = {
    s.strip() for s in os.environ.get("SENTINEL_HEAL_ALLOWLIST", "").split(",") if s.strip()
}


def resolve_make_dir() -> Optional[Path]:
    """Locate the pmoves Makefile directory inside the mounted checkout.

    Compose mounts the REPO ROOT at /srv/pmoves (`${PWD}/..:/srv/pmoves:ro`),
    and the Makefile lives one level down at <root>/pmoves/Makefile. Accept the
    directly-mounted-pmoves layout too. Returns None when neither is present,
    which is a hard "cannot self-heal" rather than a path to guess at.
    """
    for candidate in (PMOVES_DIR / "pmoves", PMOVES_DIR):
        if (candidate / "Makefile").is_file():
            return candidate
    return None


def self_heal_capability() -> Tuple[bool, str]:
    """Probe whether a Known-Road restart can actually run here.

    Returns (capable, reason); reason is "" when capable.

    The container is deliberately built without a Docker socket (a sentinel
    holding the socket is a fleet-wide privilege escalation), and
    python:3.12-slim ships neither `make` nor the Docker CLI. Rather than
    spawning a subprocess that is guaranteed to exit nonzero and logging that
    as an attempted heal, the service reports the missing prerequisite by name.
    """
    if not SELF_HEAL:
        return False, "self-heal disabled (SENTINEL_SELF_HEAL=0)"
    make_dir = resolve_make_dir()
    if make_dir is None:
        return False, (
            f"no pmoves checkout at {PMOVES_DIR} "
            f"(expected a Makefile at {PMOVES_DIR}/pmoves/Makefile)"
        )
    if not (make_dir / "scripts" / "with-env.sh").is_file():
        return False, f"{make_dir}/scripts/with-env.sh missing from the mounted checkout"
    if shutil.which("bash") is None:
        return False, "bash not on PATH"
    if shutil.which("make") is None:
        return False, "make not installed in this image"
    if shutil.which("docker") is None:
        return False, (
            "no Docker CLI on PATH — `make up-<svc>` cannot reach a daemon; "
            "a host-side runner or a constrained socket proxy must execute the "
            "Known Road (see services/fleet_sentinel/README.md)"
        )
    return True, ""


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
        self._raw_nc = None
        self.listener_mode = "none"  # none | common | raw
        self.listener_error: Optional[str] = None

    # -- listener state ------------------------------------------------------
    @property
    def listener_connected(self) -> bool:
        """True only when a NATS connection is actually up.

        Deliberately NOT ServiceAnnouncementListener.is_running: that property
        requires `self._task`, which `start()` never assigns (only the unused
        run_forever() does), so it reads False on a perfectly healthy listener.
        Reporting that as the health signal would be a false negative.
        """
        if self.listener is not None:
            return bool(getattr(self.listener, "is_connected", False))
        if self._raw_nc is not None:
            return bool(getattr(self._raw_nc, "is_connected", False))
        return False

    def _upsert(
        self,
        slug: str,
        name: str,
        url: str,
        health_check: str,
        tier: str,
        port: Optional[int],
        announce_interval_s: Optional[float],
    ) -> None:
        prev = self.registry.get(slug)
        self.registry[slug] = SentinelEntry(
            slug=slug,
            name=name,
            url=url,
            health_check=health_check,
            tier=tier,
            port=port,
            consecutive_failures=prev.consecutive_failures if prev else 0,
            restarts=prev.restarts if prev else 0,
            health=(prev.health if prev else "unknown"),
            last_restart=prev.last_restart if prev else 0.0,
            announce_interval_s=announce_interval_s,
        )

    async def start_listener(self) -> bool:
        try:
            from services.common.nats_service_listener import ServiceAnnouncementListener
        except ImportError as exc:
            # Standalone image layout (no services/common sibling): subscribe
            # directly on the announce subject with the same schema.
            logger.warning("services.common unavailable (%s) — using raw listener", exc)
            return await self._start_raw_listener()

        async def on_announce(info: Any) -> None:
            slug = str(info.slug)
            if not SLUG_RE.match(slug):
                logger.warning("rejected announcement with invalid slug: %r", info.slug)
                return
            tier = getattr(info, "tier", None)
            metadata = getattr(info, "metadata", None)
            self._upsert(
                slug=slug,
                name=info.name,
                url=getattr(info, "base_url", "") or "",
                health_check=info.health_check_url or "",
                # ServiceTier is a (str, Enum); str() on it renders
                # "ServiceTier.API", not the contract value "api".
                tier=(getattr(tier, "value", None) or str(tier)) if tier else "unknown",
                port=info.default_port,
                announce_interval_s=(
                    metadata.get("announce_interval_s") if isinstance(metadata, dict) else None
                ),
            )
            logger.info("registry upsert: %s (tier=%s)", slug, tier)

        # Constructor-arg callback (ServiceInfo), per nats_service_listener.py:77-92
        self.listener = ServiceAnnouncementListener(
            nats_url=NATS_URL, on_announcement=on_announce
        )
        # start() catches its own exceptions and returns False. Logging
        # "started" unconditionally would report success for a dead listener.
        ok = bool(await self.listener.start())
        if not ok:
            self.listener = None
            self.listener_error = f"ServiceAnnouncementListener.start() returned False ({NATS_URL})"
            logger.error("announce listener FAILED to start (%s)", NATS_URL)
            return False
        self.listener_mode = "common"
        self.listener_error = None
        logger.info("announce listener started (%s)", NATS_URL)
        return True

    async def _start_raw_listener(self) -> bool:
        """Minimal subscriber when services.common is unavailable in-image."""
        import nats as nats_lib

        async def cb(msg: Any) -> None:
            try:
                data = json.loads(msg.data.decode())
            except Exception:
                return
            slug = str(data.get("slug", ""))
            if not SLUG_RE.match(slug):
                logger.warning("rejected announcement with invalid slug: %r", data.get("slug"))
                return
            md = data.get("metadata") or {}
            self._upsert(
                slug=slug,
                name=data.get("name", slug),
                url=data.get("url", ""),
                health_check=data.get("health_check", ""),
                tier=str(data.get("tier", "unknown")),
                port=data.get("port"),
                announce_interval_s=md.get("announce_interval_s") if isinstance(md, dict) else None,
            )

        try:
            nc = await nats_lib.connect(NATS_URL)
            await nc.subscribe("services.announce.v1", cb=cb)
        except Exception as exc:
            self.listener_error = f"raw listener connect failed: {exc}"
            logger.error("raw announce listener FAILED (%s): %s", NATS_URL, exc)
            return False
        self._raw_nc = nc
        self.listener_mode = "raw"
        self.listener_error = None
        logger.info("raw announce listener started (%s)", NATS_URL)
        return True

    # -- health polling ------------------------------------------------------
    @staticmethod
    def _probe(url: str) -> bool:
        import urllib.request

        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def poll_once(self) -> None:
        now = time.time()
        due: list[SentinelEntry] = []
        for entry in list(self.registry.values()):
            if not entry.health_check:
                entry.health = "unknown"
                continue
            # Staleness is HEARTBEAT-GATED. Verified at this commit: the five
            # announce_service() callers (evo-controller, presign,
            # ffmpeg-whisper, flute-gateway, agent-zero) each publish ONCE at
            # startup and close the connection; no recurring announcer exists
            # in this repo. An unconditional announce-age test would therefore
            # mark every discovered service stale ~2min after boot and stop
            # polling it. So staleness applies only when the announcement
            # itself declares metadata.announce_interval_s.
            if (
                entry.announce_interval_s
                and now - entry.last_announce > ANNOUNCE_STALE_FACTOR * entry.announce_interval_s
            ):
                entry.health = "stale"
                continue
            due.append(entry)

        if not due:
            return

        # urlopen is blocking; running it inline in the event loop stalled the
        # listener callbacks and /healthz for up to HTTP_TIMEOUT per service.
        sem = asyncio.Semaphore(max(1, POLL_CONCURRENCY))

        async def check(entry: SentinelEntry) -> Tuple[SentinelEntry, bool]:
            async with sem:
                return entry, await asyncio.to_thread(self._probe, entry.health_check)

        for entry, ok in await asyncio.gather(*(check(e) for e in due)):
            if ok:
                entry.health = "healthy"
                entry.consecutive_failures = 0
                continue
            entry.consecutive_failures += 1
            entry.health = "failing"
            if (
                SELF_HEAL
                and entry.consecutive_failures >= FAILURE_THRESHOLD
                and time.time() - entry.last_restart > RESTART_COOLDOWN
            ):
                await self.known_road_restart(entry.slug)

    # -- recovery ------------------------------------------------------------
    def _record(self, action: Dict[str, Any]) -> None:
        self.actions.append(action)
        try:
            ACTION_TRAIL.parent.mkdir(parents=True, exist_ok=True)
            with ACTION_TRAIL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(action) + "\n")
        except OSError as exc:
            # The trail is the audit artifact; losing it must be visible.
            logger.error("could not append to action trail %s: %s", ACTION_TRAIL, exc)

    async def known_road_restart(self, slug: str) -> None:
        """The ONLY sanctioned recovery: make secrets-funnel && make up-<svc>.

        Raw `docker restart` is damage-control-blocked for good reason: it
        bypasses env re-projection. The Known Road re-funnels env first.
        """
        # Fail closed at the boundary. Callers today pass a registry key that
        # was already validated on ingest, but this function is the thing that
        # builds an argv, so it re-checks rather than trusting its caller.
        if not SLUG_RE.match(slug or ""):
            logger.error("refusing restart for non-conforming slug: %r", slug)
            self._record({
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "known_road_restart",
                "slug": slug,
                "status": "refused",
                "reason": "slug failed the allowlist pattern",
            })
            return
        if HEAL_ALLOWLIST and slug not in HEAL_ALLOWLIST:
            logger.warning("slug %s not in SENTINEL_HEAL_ALLOWLIST — refusing", slug)
            self._record({
                "ts": datetime.now(timezone.utc).isoformat(),
                "action": "known_road_restart",
                "slug": slug,
                "status": "refused",
                "reason": "slug not in SENTINEL_HEAL_ALLOWLIST",
            })
            return

        entry = self.registry[slug]
        entry.last_restart = time.time()
        action: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "known_road_restart",
            "slug": slug,
            "failures": entry.consecutive_failures,
        }

        capable, reason = self_heal_capability()
        if not capable:
            # Do NOT spawn a subprocess that cannot succeed, and do NOT clear
            # consecutive_failures — the service is still down and the registry
            # must keep saying so. The cooldown alone throttles this record.
            action["status"] = "deferred"
            action["reason"] = reason
            logger.error("self-heal DEFERRED for %s: %s", slug, reason)
            self._record(action)
            return

        entry.restarts += 1
        logger.warning("self-heal: %s after %d failures", slug, entry.consecutive_failures)
        make_dir = resolve_make_dir()
        if make_dir is None:  # unreachable via self_heal_capability(), belt-and-braces
            action["status"] = "deferred"
            action["reason"] = "checkout disappeared between probe and exec"
            self._record(action)
            return
        with_env = str(make_dir / "scripts" / "with-env.sh")
        steps = [
            ["bash", with_env, "make", "-C", str(make_dir), "secrets-funnel"],
            ["bash", with_env, "make", "-C", str(make_dir), f"up-{slug}"],
        ]
        action["status"] = "executed"
        action["steps"] = []
        try:
            for argv in steps:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                # communicate() FIRST: create_subprocess_exec returns before the
                # child exits, so proc.returncode is None until it is awaited.
                # Testing it beforehand made `None == 0` false and silently
                # skipped the `up-<slug>` step every single time.
                out, _ = await proc.communicate()
                action["steps"].append({
                    "target": argv[-1],
                    "exit": proc.returncode,
                    "tail": (out or b"").decode(errors="replace")[-500:],
                })
                if proc.returncode != 0:
                    break
            action["exit"] = action["steps"][-1]["exit"] if action["steps"] else None
        except Exception as exc:
            action["status"] = "error"
            action["error"] = str(exc)
        self._record(action)
        if action.get("exit") == 0:
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


async def _guarded(coro_fn, label: str) -> None:
    """Run a background coroutine so its failure is logged, not swallowed."""
    try:
        await coro_fn()
    except Exception:
        logger.exception("%s task failed", label)


@app.on_event("startup")
async def _startup() -> None:
    capable, reason = self_heal_capability()
    if not capable:
        logger.warning("self-heal is NOT operational: %s", reason)
    asyncio.create_task(_guarded(sentinel.start_listener, "listener"))
    asyncio.create_task(_guarded(_poll_loop, "poll"))


async def _poll_loop() -> None:
    while True:
        try:
            await sentinel.poll_once()
        except Exception:
            logger.exception("poll cycle failed")
        await asyncio.sleep(POLL_INTERVAL)


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    capable, reason = self_heal_capability()
    return {
        "status": "healthy",
        "listener_mode": sentinel.listener_mode,
        "listener_connected": sentinel.listener_connected,
        "listener_error": sentinel.listener_error,
        "services": len(sentinel.registry),
        "self_heal": "operational" if capable else "unavailable",
        "self_heal_reason": reason or None,
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
