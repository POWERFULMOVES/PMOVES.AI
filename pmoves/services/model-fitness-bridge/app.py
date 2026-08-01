"""Model Fitness Bridge — subscribes to benchmark/eval events, calls model-registry fitness API.

Closes the FATAL gap G1: POST /api/model-fitness exists but zero services call it.

This bridge listens to:
  - llama.benchmark.completed.v1 (from throughput-lab)
  - agentgym.train.completed.v1 (from agentgym-rl-coordinator)
  - agentgym.model.published.v1 (from agentgym-rl-coordinator)

And periodically scrapes TensorZero ClickHouse telemetry, then calls
POST /api/model-fitness with CHIT-signed normalized scores.

Run: python -m pmoves.services.model_fitness_bridge.app
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any

import httpx
from fastapi import FastAPI

logger = logging.getLogger("model-fitness-bridge")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# --- Config ---------------------------------------------------------------
MODEL_REGISTRY_URL = os.environ.get("MODEL_REGISTRY_URL", "http://model-registry:8110")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
CLICKHOUSE_URL = os.environ.get("TENSORZERO_CLICKHOUSE_URL", "http://tensorzero-clickhouse:8123")
CLICKHOUSE_USER = os.environ.get("TENSORZERO_CLICKHOUSE_USER", "tensorzero")
CLICKHOUSE_PASS = os.environ.get("TENSORZERO_CLICKHOUSE_PASSWORD", "tensorzero")
CLICKHOUSE_DB = os.environ.get("TENSORZERO_CLICKHOUSE_DB", "tensorzero")
SCRAPE_INTERVAL = int(os.environ.get("FITNESS_SCRAPE_INTERVAL", "300"))  # 5 min
BRIDGE_AGENT_ID = os.environ.get("FITNESS_BRIDGE_AGENT_ID", "model-fitness-bridge")
BRIDGE_PORT = int(os.environ.get("FITNESS_BRIDGE_PORT", "8080"))

SUBJECTS = [
    "llama.benchmark.completed.v1",
    "agentgym.train.completed.v1",
    "agentgym.model.published.v1",
]

app = FastAPI(title="PMOVES Model Fitness Bridge", version="0.1.0")

# --- Fitness API caller ---------------------------------------------------

async def call_model_fitness(
    model_id: str,
    source: str,
    lane: str,
    score: float,
    metrics: dict[str, Any],
    run_id: str | None = None,
    training_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST to model-registry /api/model-fitness with the fitness payload."""
    payload: dict[str, Any] = {
        "model_id": model_id,
        "source": source,
        "lane": lane,
        "score": max(0.0, min(1.0, score)),
        "metrics": metrics,
        "agent_id": BRIDGE_AGENT_ID,
    }
    if run_id:
        payload["run_id"] = run_id
    if training_metrics:
        payload["training_metrics"] = training_metrics

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{MODEL_REGISTRY_URL}/api/model-fitness",
                json=payload,
            )
            resp.raise_for_status()
            logger.info("fitness recorded: model=%s source=%s score=%.3f", model_id, source, score)
            return resp.json()
        except Exception as exc:
            logger.error("fitness API call failed for model=%s: %s", model_id, exc)
            return {}

async def call_model_candidates(
    hf_id: str,
    lane: str,
    trail_ref: str | None = None,
) -> dict[str, Any]:
    """POST to model-registry /api/model-candidates to register a new model."""
    payload: dict[str, Any] = {
        "hf_id": hf_id,
        "lane": lane,
        "intended_lane": lane,
        "agent_id": BRIDGE_AGENT_ID,
    }
    if trail_ref:
        payload["signed_trail_ref"] = trail_ref

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{MODEL_REGISTRY_URL}/api/model-candidates",
                json=payload,
            )
            if resp.status_code == 409:
                logger.info("candidate already exists: %s", hf_id)
                return {"status": "exists"}
            resp.raise_for_status()
            logger.info("candidate registered: %s", hf_id)
            return resp.json()
        except Exception as exc:
            logger.error("candidate API call failed for %s: %s", hf_id, exc)
            return {}

# --- Event handlers -------------------------------------------------------

async def on_benchmark_completed(data: dict[str, Any]) -> None:
    """Handle llama.benchmark.completed.v1 from throughput-lab."""
    model_id = data.get("model") or data.get("model_id") or "unknown"
    tps = float(data.get("tokens_per_second") or data.get("throughput_tps") or 0)
    latency_ms = float(data.get("latency_ms") or data.get("mean_latency_ms") or 0)
    errors = int(data.get("errors") or 0)
    total_requests = int(data.get("total_requests") or data.get("requests") or 1)

    # Normalize to 0-1: throughput-heavy scoring
    # 50+ tok/s = 1.0; 0 tok/s = 0.0; log-scaled between
    import math
    tps_score = min(1.0, math.log10(max(1, tps)) / math.log10(50)) if tps > 0 else 0.0
    success_rate = max(0.0, 1.0 - (errors / max(1, total_requests)))
    latency_score = max(0.0, 1.0 - (latency_ms / 10000)) if latency_ms > 0 else 0.5

    score = tps_score * 0.5 + success_rate * 0.3 + latency_score * 0.2

    await call_model_fitness(
        model_id=model_id,
        source="pinokio",
        lane=data.get("lane", "chat"),
        score=score,
        metrics={
            "throughput_tps": tps,
            "latency_ms": latency_ms,
            "errors": errors,
            "total_requests": total_requests,
        },
        run_id=data.get("run_id") or data.get("sweep_id"),
    )

async def on_agentgym_train_completed(data: dict[str, Any]) -> None:
    """Handle agentgym.train.completed.v1 from AgentGym RL coordinator."""
    model_id = data.get("model_id") or data.get("model") or "unknown"
    mean_reward = float(data.get("mean_reward") or data.get("final_reward") or 0)
    mean_reward_normalized = float(data.get("mean_reward_normalized") or mean_reward)

    score = max(0.0, min(1.0, mean_reward_normalized))

    await call_model_fitness(
        model_id=model_id,
        source="evoswarm",
        lane="agentgym",
        score=score,
        metrics={
            "mean_reward": mean_reward,
            "episodes": int(data.get("episodes") or 0),
            "training_steps": int(data.get("training_steps") or 0),
        },
        training_metrics=data.get("training_metrics"),
        run_id=data.get("run_id") or data.get("training_id"),
    )

async def on_agentgym_model_published(data: dict[str, Any]) -> None:
    """Handle agentgym.model.published.v1 — register as a model candidate."""
    hf_id = data.get("hf_id") or data.get("model_repo") or ""
    if not hf_id:
        logger.warning("agentgym.model.published with no hf_id: %s", data)
        return

    await call_model_candidates(
        hf_id=hf_id,
        lane="agentgym",
        trail_ref=data.get("trail_ref") or data.get("signed_trail_ref"),
    )

    # Also record initial fitness from training metrics if present
    if data.get("mean_reward_normalized"):
        await call_model_fitness(
            model_id=hf_id,
            source="evoswarm",
            lane="agentgym",
            score=float(data["mean_reward_normalized"]),
            metrics=data.get("training_metrics", {}),
            run_id=data.get("run_id"),
        )

HANDLERS: dict[str, Any] = {
    "llama.benchmark.completed.v1": on_benchmark_completed,
    "agentgym.train.completed.v1": on_agentgym_train_completed,
    "agentgym.model.published.v1": on_agentgym_model_published,
}

# --- NATS subscriber ------------------------------------------------------

async def nats_subscriber_loop() -> None:
    """Connect to NATS and subscribe to all fitness-relevant subjects."""
    try:
        import nats
    except ImportError:
        logger.warning("nats-py not installed — bridge running in scrape-only mode")
        return

    while True:
        try:
            nc = await nats.connect(NATS_URL, name="model-fitness-bridge", max_reconnect_attempts=-1)
            logger.info("NATS connected: %s", NATS_URL)

            async def message_handler(msg):
                subject = msg.subject
                handler = HANDLERS.get(subject)
                if not handler:
                    return
                try:
                    data = json.loads(msg.data)
                    logger.info("received %s: model=%s", subject, data.get("model_id") or data.get("model") or "?")
                    await handler(data)
                except Exception:
                    logger.exception("handler error for %s", subject)

            for subject in SUBJECTS:
                await nc.subscribe(subject, cb=message_handler)
                logger.info("subscribed: %s", subject)

            # Keep alive
            while True:
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("NATS connection error; retrying in 10s")
            await asyncio.sleep(10)

# --- ClickHouse telemetry scraper -----------------------------------------

TELEMETRY_QUERY = """
SELECT
    model_name,
    count() as total_requests,
    countIf(status = 'success') as successes,
    avg(duration_ms) as avg_latency_ms,
    sum(tokens_output) / (sum(duration_ms) / 1000) as avg_tps
FROM {db}.inference
WHERE timestamp > now() - INTERVAL {hours} HOUR
GROUP BY model_name
"""

async def scrape_clickhouse_telemetry() -> list[dict[str, Any]]:
    """Scrape TensorZero ClickHouse for per-model telemetry."""
    query = TELEMETRY_QUERY.format(db=CLICKHOUSE_DB, hours=1)
    params = {"user": CLICKHOUSE_USER, "password": CLICKHOUSE_PASS, "database": CLICKHOUSE_DB}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{CLICKHOUSE_URL}/",
                content=query,
                params=params,
            )
            resp.raise_for_status()
            lines = [l for l in resp.text.strip().split("\n") if l.strip()]
            results = []
            for line in lines:
                parts = line.split("\t")
                if len(parts) >= 5:
                    results.append({
                        "model_name": parts[0],
                        "total_requests": int(parts[1]),
                        "successes": int(parts[2]),
                        "avg_latency_ms": float(parts[3]) if parts[3] != "nan" else 0,
                        "avg_tps": float(parts[4]) if parts[4] != "nan" and parts[4] != "inf" else 0,
                    })
            return results
        except Exception as exc:
            logger.error("ClickHouse scrape failed: %s", exc)
            return []

async def telemetry_scrape_loop() -> None:
    """Periodically scrape ClickHouse and record fitness from live telemetry."""
    logger.info("telemetry scraper started (interval=%ds)", SCRAPE_INTERVAL)
    while True:
        try:
            await asyncio.sleep(SCRAPE_INTERVAL)
            results = await scrape_clickhouse_telemetry()
            if not results:
                continue
            logger.info("scraped %d models from ClickHouse", len(results))
            for row in results:
                import math
                model_name = row["model_name"]
                success_rate = row["successes"] / max(1, row["total_requests"])
                latency_score = max(0, 1.0 - (row["avg_latency_ms"] / 10000))
                tps_score = min(1.0, math.log10(max(1, row["avg_tps"])) / math.log10(50)) if row["avg_tps"] > 0 else 0
                score = tps_score * 0.5 + success_rate * 0.3 + latency_score * 0.2

                await call_model_fitness(
                    model_id=model_name,
                    source="tensorzero",
                    lane="chat",
                    score=score,
                    metrics={
                        "total_requests": row["total_requests"],
                        "success_rate": success_rate,
                        "avg_latency_ms": row["avg_latency_ms"],
                        "avg_tps": row["avg_tps"],
                    },
                    run_id=f"ch-scrape-{int(time.time())}",
                )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("telemetry scrape loop error")

# --- FastAPI app ----------------------------------------------------------

@app.get("/healthz")
async def healthz():
    return {"status": "healthy", "service": "model-fitness-bridge", "subjects": SUBJECTS}

@app.get("/metrics")
async def metrics():
    return {
        "subjects_subscribed": SUBJECTS,
        "model_registry_url": MODEL_REGISTRY_URL,
        "scrape_interval": SCRAPE_INTERVAL,
    }

@app.on_event("startup")
async def startup():
    asyncio.create_task(nats_subscriber_loop())
    asyncio.create_task(telemetry_scrape_loop())
    logger.info("model-fitness-bridge started — registry=%s nats=%s", MODEL_REGISTRY_URL, NATS_URL)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "pmoves.services.model_fitness_bridge.app:app",
        host="0.0.0.0",
        port=BRIDGE_PORT,
        log_level="info",
    )
