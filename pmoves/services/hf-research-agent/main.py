#!/usr/bin/env python3
"""PMOVES HF Research Agent — Model Evaluation Worker.

Subscribes to ``hf.model.discovered.v1`` from hf-agent, evaluates models
against configured benchmark criteria, and publishes evaluation results to
``hf.model.evaluated.v1``.

Follows the spark-shape-worker pattern: asyncio + nats-py + _load_secret.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import nats
from nats.aio.client import Client as NATS

from card_evidence import eval_job_recipe, is_hub_model_id, load_card_evidence
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
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
SERVER_PORT = int(os.environ.get("HF_RESEARCH_PORT", "8202"))

# Evaluation criteria (env-configurable)
MIN_DOWNLOADS = int(os.environ.get("HF_MIN_DOWNLOADS", "100"))
MIN_LIKES = int(os.environ.get("HF_MIN_LIKES", "10"))
MIN_SCORE = int(os.environ.get("HF_MIN_SCORE", "50"))

# Scoring scale. Criteria 1-4 award up to BASE_MAX_SCORE (40 + 25 + 20 + 15);
# Criterion 5 adds COMPAT_BONUS_POINTS, criteria 6-7 (model-card evidence,
# 2026-10-11) add EVAL_EVIDENCE_POINTS + LICENSE_POINTS, so the attainable
# maximum is 130, not 100. MIN_SCORE is an absolute threshold, not a
# percentage of MAX_SCORE.
BASE_MAX_SCORE = 100
COMPAT_BONUS_POINTS = 10
EVAL_EVIDENCE_POINTS = 15
LICENSE_POINTS = 5
MAX_SCORE = BASE_MAX_SCORE + COMPAT_BONUS_POINTS + EVAL_EVIDENCE_POINTS + LICENSE_POINTS

# Model-card evidence (card_evidence.py): the card's model-index results,
# licence, base model, library and gated state. Fetched off the event loop on
# a BOUNDED pool: nats-py gives every message its own handler task, so a burst
# of slow or gated models must not stack an unbounded number of Hub reads
# (kilo review on #3354). The timeout is passed down to the Hub client as the
# request timeout, so it bounds the work and not only the wait; the pool caps
# how many reads are in flight at once. HF_CARD_EVIDENCE=0 turns it off and
# criteria 6-7 score 0.
HF_TOKEN = _load_secret("HF_TOKEN")
HF_CARD_EVIDENCE = os.environ.get("HF_CARD_EVIDENCE", "1").strip().lower() not in {"0", "false", "no", "off", ""}
HF_CARD_EVIDENCE_TIMEOUT = float(os.environ.get("HF_CARD_EVIDENCE_TIMEOUT", "20"))
HF_CARD_EVIDENCE_WORKERS = max(1, int(os.environ.get("HF_CARD_EVIDENCE_WORKERS", "4")))
# The eval-job RECIPE attached to a passing model (text only; nothing is
# submitted here). Flavors/tasks follow the hugging-face-jobs skill.
HF_EVAL_FLAVOR = os.environ.get("HF_EVAL_FLAVOR", "cpu-basic")
HF_EVAL_TASK = os.environ.get("HF_EVAL_TASK", "mmlu")
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
        self._evidence_pool = ThreadPoolExecutor(
            max_workers=HF_CARD_EVIDENCE_WORKERS, thread_name_prefix="card-evidence"
        )

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
    def _evaluate_model(model: dict[str, Any], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        """Evaluate a discovered model against configured benchmark criteria.

        ``evidence`` is the model-card envelope from ``load_card_evidence``;
        ``None`` (fetch off or failed) scores criteria 6-7 as zero and says so.
        Returns an evaluation envelope with pass/fail, score, and rationale.
        """
        tags = {str(t).lower() for t in model.get("tags", [])}
        downloads = model.get("downloads", 0)
        likes = model.get("likes", 0)
        model_id = model.get("model_id", "unknown")

        score = 0
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
            score += COMPAT_BONUS_POINTS
            reasons.append(
                f"local-compat (+{COMPAT_BONUS_POINTS}): {sorted(matched_compat)}"
            )

        # Criterion 6: reported evaluations on the model card (0-15).
        # model-index results are the model's own benchmark claims; their
        # presence is evidence someone measured it, the values ride along so
        # a consumer can judge them. (hugging-face-evaluation skill surface.)
        evidence = evidence or {}
        eval_results = evidence.get("eval_results") or []
        errors = evidence.get("errors") or []
        if eval_results:
            score += EVAL_EVIDENCE_POINTS
            reasons.append(f"model-index evals (+{EVAL_EVIDENCE_POINTS}): {len(eval_results)} result(s)")
        elif errors:
            # A card that was never read has no absence to report; the
            # receipts ride in card_evidence.errors (kilo review on #3354).
            reasons.append(f"card evidence incomplete ({len(errors)} Hub read(s) failed; see card_evidence.errors)")
        elif evidence.get("available"):
            reasons.append("no model-index evals on card")
        else:
            reasons.append("card evidence unavailable")

        # Criterion 7: a declared licence (0-5). Gated/base-model are recorded
        # below, never scored: whether a fleet node may pull the weights is an
        # operator judgement, not a number.
        license_id = evidence.get("license")
        if license_id:
            score += LICENSE_POINTS
            reasons.append(f"license declared (+{LICENSE_POINTS}): {license_id}")

        # Penalty: Avoid tags (-10 points each)
        matched_avoid = tags & AVOID_TAGS
        if matched_avoid:
            penalty = 10 * len(matched_avoid)
            score = max(0, score - penalty)
            reasons.append(f"avoid tags match (-{penalty}): {sorted(matched_avoid)}")

        passed = score >= MIN_SCORE
        # The recipe is shell text an operator pastes; a bus-supplied id that
        # is not a Hub id never reaches it (eval_job_recipe returns None).
        recipe = eval_job_recipe(model_id, task=HF_EVAL_TASK, flavor=HF_EVAL_FLAVOR) if passed else None
        if passed and recipe is None:
            reasons.append("model id is not a Hub id; no eval-job recipe")
        return {
            "model_id": model_id,
            "score": score,
            "max_score": MAX_SCORE,
            "passed": passed,
            "reasons": reasons,
            "card_evidence": {
                "available": bool(evidence.get("available", False)),
                "license": evidence.get("license"),
                "base_model": evidence.get("base_model") or [],
                "library_name": evidence.get("library_name"),
                "gated": evidence.get("gated"),
                "errors": evidence.get("errors") or [],
            },
            "eval_results": eval_results,
            "eval_job_recipe": recipe,
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

        evidence: dict[str, Any] | None = None
        if HF_CARD_EVIDENCE and is_hub_model_id(model.get("model_id")):
            try:
                loop = asyncio.get_running_loop()
                evidence = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._evidence_pool,
                        functools.partial(load_card_evidence, model["model_id"], HF_TOKEN, HF_CARD_EVIDENCE_TIMEOUT),
                    ),
                    timeout=HF_CARD_EVIDENCE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                evidence = {"available": False, "errors": [f"card evidence timed out after {HF_CARD_EVIDENCE_TIMEOUT:g}s"], "eval_results": []}
            except Exception as exc:  # the loader itself never raises; belt and braces
                evidence = {"available": False, "errors": [f"card evidence: {exc}"], "eval_results": []}

        evaluation = self._evaluate_model(model, evidence)
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
        self._evidence_pool.shutdown(wait=False, cancel_futures=True)
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
