#!/usr/bin/env python3
"""PMOVES HF Agent — Autonomous HuggingFace Model Patrol.

Polls HuggingFace for new models matching configured criteria and publishes
discovery events to NATS subject ``hf.model.discovered.v1``.

Follows the spark-shape-worker pattern: asyncio + nats-py + _load_secret.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone
from typing import Any

import nats
from nats.aio.client import Client as NATS
from aiohttp import web

try:  # huggingface_hub >= 1.0 removed ModelFilter; list_models takes kwargs directly
    from huggingface_hub import HfApi
    _HAS_MODEL_FILTER = False
except ImportError:  # pragma: no cover
    HfApi = None  # type: ignore[misc,assignment]
    _HAS_MODEL_FILTER = False

try:
    from huggingface_hub import ModelFilter  # type: ignore[import-not-found]
    _HAS_MODEL_FILTER = True
except ImportError:
    ModelFilter = None  # type: ignore[assignment,misc]


def _load_secret(key: str, default: str = "") -> str:
    """Read *key* from env, falling back to the ``{key}_FILE`` Docker secret mount."""
    val = os.environ.get(key)
    if val:
        return val
    file_path = os.environ.get(f"{key}_FILE")
    if file_path and os.path.exists(file_path):
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    return default


def _redact_url(url: str) -> str:
    """Strip credentials from a NATS URL for safe logging."""
    if "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return url


# ── Configuration ────────────────────────────────────────────────────────────
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
HF_TOKEN = _load_secret("HF_TOKEN")
SERVER_PORT = int(os.environ.get("HF_AGENT_PORT", "8201"))

# Polling configuration
POLL_INTERVAL = int(os.environ.get("HF_POLL_INTERVAL", "300"))  # seconds
HF_TASK_FILTER = os.environ.get("HF_TASK_FILTER", "")  # e.g. "text-generation"
HF_TAGS = [t.strip() for t in os.environ.get("HF_TAGS", "").split(",") if t.strip()]
HF_AUTHOR = os.environ.get("HF_AUTHOR", "")
HF_SORT = os.environ.get("HF_SORT", "lastModified")
HF_DIRECTION = int(os.environ.get("HF_DIRECTION", "-1"))
HF_LIMIT = int(os.environ.get("HF_LIMIT", "50"))

PUBLISH_SUBJECT = "hf.model.discovered.v1"


class HFAgent:
    """Autonomous HuggingFace model patrol agent."""

    def __init__(self, nats_url: str, hf_token: str, poll_interval: int) -> None:
        self.nats_url = nats_url
        self.hf_token = hf_token
        self.poll_interval = poll_interval
        self.nc: NATS | None = None
        self._shutdown = asyncio.Event()
        self._seen: set[str] = set()
        self._poll_task: asyncio.Task | None = None
        self._healthy = False
        self._last_poll: str = ""
        self._discovered_count = 0
        self._api: HfApi | None = None

    def _init_hf_api(self) -> HfApi:
        """Initialize the HuggingFace Hub API client."""
        return HfApi(token=self.hf_token or None)

    # ── Health ───────────────────────────────────────────────────────────────

    async def _healthz(self, request: web.Request) -> web.Response:
        """Health-check endpoint."""
        status = {
            "status": "healthy" if self._healthy else "starting",
            "service": "hf-agent",
            "last_poll": self._last_poll,
            "discovered_total": self._discovered_count,
            "seen_models": len(self._seen),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        code = 200 if self._healthy else 503
        return web.json_response(status, status=code)

    # ── Discovery ────────────────────────────────────────────────────────────

    def _build_list_models_kwargs(self) -> dict[str, Any]:
        """Construct kwargs for HfApi.list_models across huggingface_hub versions.

        huggingface_hub <1.0 used a ``ModelFilter`` object; >=1.0 takes the
        filter parameters as direct keyword arguments. This shim normalises
        both so the poll loop survives library upgrades.
        """
        task = HF_TASK_FILTER or None
        tags = HF_TAGS or None
        author = HF_AUTHOR or None

        if _HAS_MODEL_FILTER:
            mf = ModelFilter(task=task, tags=tags, author=author)
            return {"filter": mf}

        # huggingface_hub >= 1.0: task → pipeline_tag, tags → filter list
        kwargs: dict[str, Any] = {}
        if task:
            kwargs["pipeline_tag"] = task
        if tags:
            kwargs["filter"] = tags
        if author:
            kwargs["author"] = author
        return kwargs

    def _discover_models(self) -> list[dict[str, Any]]:
        """Query HuggingFace for models matching configured criteria.

        Returns only models not yet seen (deduplicated by ``model_id``).
        """
        models: list[dict[str, Any]] = []
        try:
            list_kwargs = self._build_list_models_kwargs()
            # ``direction`` is only accepted by the legacy API; the new API
            # derives sort order from the ``sort`` argument.
            if _HAS_MODEL_FILTER:
                list_kwargs["direction"] = HF_DIRECTION
            results = self._api.list_models(
                sort=HF_SORT,
                limit=HF_LIMIT,
                **list_kwargs,
            )
            for model_info in results:
                model_id = getattr(model_info, "id", str(model_info))
                if model_id in self._seen:
                    continue

                tags = getattr(model_info, "tags", []) or []
                downloads = getattr(model_info, "downloads", 0) or 0
                likes = getattr(model_info, "likes", 0) or 0
                last_modified = getattr(model_info, "lastModified", "")
                pipeline_tag = getattr(model_info, "pipeline_tag", "") or ""

                entry: dict[str, Any] = {
                    "model_id": model_id,
                    "tags": tags,
                    "downloads": downloads,
                    "likes": likes,
                    "last_modified": str(last_modified) if last_modified else "",
                    "pipeline_tag": pipeline_tag,
                    "author": getattr(model_info, "author", "") or "",
                    "hf_url": f"https://huggingface.co/{model_id}",
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                }
                models.append(entry)
                self._seen.add(model_id)
        except Exception as exc:
            print(f"[hf-agent] discovery error: {exc}", file=sys.stderr)
        return models

    async def _poll_loop(self) -> None:
        """Periodic polling loop — fetches new models and publishes to NATS."""
        while not self._shutdown.is_set():
            try:
                discovered = await asyncio.get_running_loop().run_in_executor(
                    None, self._discover_models
                )
                for model in discovered:
                    data = json.dumps(model, default=str).encode("utf-8")
                    await self.nc.publish(PUBLISH_SUBJECT, data)
                    self._discovered_count += 1
                    print(
                        f"[hf-agent] discovered {model['model_id']} "
                        f"-> {PUBLISH_SUBJECT}"
                    )

                self._last_poll = datetime.now(timezone.utc).isoformat()
                if not self._healthy:
                    self._healthy = True
                    print("[hf-agent] first poll complete, marking healthy")

                if discovered:
                    print(
                        f"[hf-agent] poll cycle: {len(discovered)} new models "
                        f"(total seen: {len(self._seen)})"
                    )
            except Exception as exc:
                print(f"[hf-agent] poll error: {exc}", file=sys.stderr)

            # Wait for next cycle or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(), timeout=self.poll_interval
                )
            except asyncio.TimeoutError:
                pass

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def run(self) -> int:
        # Connect NATS
        self.nc = await nats.connect(self.nats_url)
        print(f"[hf-agent] connected to {_redact_url(self.nats_url)}")
        print(f"[hf-agent] publishing to {PUBLISH_SUBJECT}")

        # Initialize HF API
        self._api = self._init_hf_api()
        print(f"[hf-agent] HF API initialized (token={'yes' if self.hf_token else 'no'})")

        # Start HTTP health server
        app = web.Application()
        app.router.add_get("/healthz", self._healthz)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", SERVER_PORT)
        await site.start()
        print(f"[hf-agent] healthz on :{SERVER_PORT}/healthz")

        # Start polling
        self._poll_task = asyncio.create_task(self._poll_loop())

        # Signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown.set)

        await self._shutdown.wait()

        # Cleanup
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        await runner.cleanup()
        await self.nc.drain()
        print("[hf-agent] shutdown complete")
        return 0


async def main() -> int:
    agent = HFAgent(NATS_URL, HF_TOKEN, POLL_INTERVAL)
    return await agent.run()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
