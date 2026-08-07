#!/usr/bin/env python3
"""PMOVES HF Research Agent — Model Evaluation Worker.

Subscribes to ``hf.model.discovered.v1`` from hf-agent, evaluates models
against configured benchmark criteria, and publishes evaluation results to
``hf.model.evaluated.v1``.

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
SERVER_PORT = int(os.environ.get("HF_RESEARCH_PORT", "8202"))

# Evaluation criteria (env-configurable)
MIN_DOWNLOADS = int(os.environ.get("HF_MIN_DOWNLOADS", "100"))
MIN_LIKES = int(os.environ.get("HF_MIN_LIKES", "10"))
MIN_SCORE = int(os.environ.get("HF_MIN_SCORE", "50"))
PREFERRED_TAGS_RAW = os.environ.get("HF_PREFERRED_TAGS", "")
PREFERRED_TAGS = {t.strip().lower() for t in PREFERRED_TAGS_RAW.split(",") if t.strip()}
AVOID_TAGS_RAW = os.environ.get("HF_AVOID_TAGS", "")
AVOID_TAGS = {t.strip().lower() for t in AVOID_TAGS_RAW.split(",") if t.strip()}

SUBSCRIBE_SUBJECT = "hf.model.discovered.v1"
PUBLISH_SUBJECT = "hf.model.evaluated.v1"


class HFResearchAgent:
    """Evaluates discovered HuggingFace models against benchmark criteria."""

    def __init__(self, nats_url: str) -> None:
        self.nats_url = nats_url
        self.nc: NATS | None = None
        self.sub = None
        self._shutdown = asyncio.Event()
        self._healthy = False
        self._evaluated_count = 0
        self._passed_count = 0
        self._last_evaluated: str = ""

    # ── Health ───────────────────────────────────────────────────────────────

    async def _healthz(self, request: web.Request) -> web.Response:
        """Health-check endpoint."""
        status = {
            "status": "healthy" if self._healthy else "starting",
            "service": "hf-research-agent",
            "evaluated_total": self._evaluated_count,
            "passed_total": self._passed_count,
            "last_evaluated": self._last_evaluated,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        code = 200 if self._healthy else 503
        return web.json_response(status, status=code)

    # ── Evaluation ───────────────────────────────────────────────────────────

    @staticmethod
    def _evaluate_model(model: dict[str, Any]) -> dict[str, Any]:
        """Evaluate a discovered model against configured benchmark criteria.

        Returns an evaluation envelope with pass/fail, score, and rationale.
        """
        tags = {str(t).lower() for t in model.get("tags", [])}
        downloads = model.get("downloads", 0)
        likes = model.get("likes", 0)
        model_id = model.get("model_id", "unknown")

        score = 0
        max_score = 100
        reasons: list[str] = []

        # Criterion 1: Downloads (0-40 points)
        if downloads >= 10000:
            score += 40
            reasons.append(f"high downloads ({downloads})")
        elif downloads >= 1000:
            score += 25
            reasons.append(f"moderate downloads ({downloads})")
        elif downloads >= MIN_DOWNLOADS:
            score += 10
            reasons.append(f"meets min downloads ({downloads})")
        else:
            reasons.append(f"low downloads ({downloads})")

        # Criterion 2: Community engagement (0-25 points)
        if likes >= 100:
            score += 25
            reasons.append(f"high engagement ({likes} likes)")
        elif likes >= MIN_LIKES:
            score += 15
            reasons.append(f"moderate engagement ({likes} likes)")
        else:
            reasons.append(f"low engagement ({likes} likes)")

        # Criterion 3: Preferred tags (0-20 points)
        matched_preferred = tags & PREFERRED_TAGS
        if matched_preferred:
            score += 20
            reasons.append(f"preferred tags: {sorted(matched_preferred)}")

        # Criterion 4: Pipeline tag presence (0-15 points)
        pipeline_tag = model.get("pipeline_tag", "")
        if pipeline_tag:
            score += 15
            reasons.append(f"pipeline_tag: {pipeline_tag}")

        # Criterion 5: Local-model compatibility (0-10 bonus)
        # Rewards GGUF/ARM64/quantized variants that can run on fleet nodes
        # without conversion. On SPARK (sm_121, ARM64, 128GB UMA) this is
        # the difference between a model that works immediately vs one that
        # needs a full recompile.
        compat_keywords = {"gguf", "arm64", "aarch64", "q4_k_m", "q4_k_s", "q5_k_m",
                           "q8_0", "q4_0", "exl2", "awq", "gptq", "mxfp4", "nvfp4"}
        model_id_lower = model_id.lower()
        matched_compat = {kw for kw in compat_keywords if kw in model_id_lower or kw in tags}
        if matched_compat:
            score += 10
            reasons.append(f"local-compat (+10): {sorted(matched_compat)}")

        # Penalty: Avoid tags (-10 points each)
        matched_avoid = tags & AVOID_TAGS
        if matched_avoid:
            penalty = 10 * len(matched_avoid)
            score = max(0, score - penalty)
            reasons.append(f"avoid tags match (-{penalty}): {sorted(matched_avoid)}")

        passed = score >= MIN_SCORE
        return {
            "model_id": model_id,
            "score": score,
            "max_score": max_score + 10,  # +10 from Criterion 5
            "passed": passed,
            "reasons": reasons,
            "tags": model.get("tags", []),
            "downloads": downloads,
            "likes": likes,
            "pipeline_tag": pipeline_tag,
            "hf_url": model.get("hf_url", f"https://huggingface.co/{model_id}"),
            "discovered_at": model.get("discovered_at", ""),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── NATS Handler ─────────────────────────────────────────────────────────

    async def _on_discovered(self, msg) -> None:
        """Handle incoming model discovery events."""
        try:
            model = json.loads(msg.data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[hf-research] dropping non-JSON message: {exc}", file=sys.stderr)
            return

        if not isinstance(model, dict):
            print("[hf-research] dropping non-object message", file=sys.stderr)
            return

        evaluation = self._evaluate_model(model)
        data = json.dumps(evaluation, default=str).encode("utf-8")
        await self.nc.publish(PUBLISH_SUBJECT, data)

        self._evaluated_count += 1
        if evaluation["passed"]:
            self._passed_count += 1

        self._last_evaluated = datetime.now(timezone.utc).isoformat()
        if not self._healthy:
            self._healthy = True

        status_icon = "PASS" if evaluation["passed"] else "SKIP"
        print(
            f"[hf-research] {status_icon} {evaluation['model_id']} "
            f"(score={evaluation['score']}/{evaluation['max_score']})"
        )

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def run(self) -> int:
        self.nc = await nats.connect(self.nats_url)
        self.sub = await self.nc.subscribe(SUBSCRIBE_SUBJECT, cb=self._on_discovered)
        print(f"[hf-research] connected to {_redact_url(self.nats_url)}")
        print(f"[hf-research] subscribed to {SUBSCRIBE_SUBJECT}")
        print(f"[hf-research] publishing to {PUBLISH_SUBJECT}")

        # Mark healthy after successful subscription (NATS connectivity proven)
        self._healthy = True

        # Start HTTP health server
        app = web.Application()
        app.router.add_get("/healthz", self._healthz)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", SERVER_PORT)
        await site.start()
        print(f"[hf-research] healthz on :{SERVER_PORT}/healthz")

        # Signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._shutdown.set)

        await self._shutdown.wait()

        # Cleanup
        await self.sub.unsubscribe()
        await runner.cleanup()
        await self.nc.drain()
        print("[hf-research] shutdown complete")
        return 0


async def main() -> int:
    agent = HFResearchAgent(NATS_URL)
    return await agent.run()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
