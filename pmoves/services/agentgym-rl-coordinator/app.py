import os
import json
import logging
import re
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException
import nats
from nats.errors import ConnectionClosedError, TimeoutError, NoServersError

# Import coordinator modules
from coordinator import (
    TrajectoryAccumulator,
    PPOTrainingOrchestrator,
    HuggingFacePublisher,
    SupabaseStorage,
)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentgym-coordinator")

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://supabase_kong_PMOVES.AI:8000")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN")
HF_ORG = os.getenv("HF_ORG", "pmoves")
PORT = int(os.getenv("PORT", 8114))

# Validation constants
VALID_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}
DATASET_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

# Global state
nc = None
trajectory_accumulator: Optional[TrajectoryAccumulator] = None
training_orchestrator: Optional[PPOTrainingOrchestrator] = None
hf_publisher: Optional[HuggingFacePublisher] = None
storage: Optional[SupabaseStorage] = None



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown: initialize storage and coordinator components, connect to NATS, and register message handlers for geometry, HuggingFace model downloads, and training completion.
    
    On startup, conditionally instantiates Supabase-backed storage and coordinators (trajectory accumulator, training orchestrator, HuggingFace publisher) when a Supabase key is available, establishes a NATS connection, and subscribes to:
    - geometry.event.v1 and tokenism.geometry.event.v1 to accumulate trajectories,
    - hf.model.downloaded.v1 to record downloaded HF models,
    - agentgym.train.completed.v1 to optionally auto-publish training runs to HuggingFace, emit model-published and benchmark pipeline events, and record completion events.
    
    On shutdown, closes the NATS connection and gracefully closes any initialized coordinators and storage.
    """
    global nc, trajectory_accumulator, training_orchestrator, hf_publisher, storage

    # Initialize storage and coordinators
    if SUPABASE_KEY:
        storage = SupabaseStorage(SUPABASE_URL, SUPABASE_KEY)
        trajectory_accumulator = TrajectoryAccumulator(SUPABASE_URL, SUPABASE_KEY)
        training_orchestrator = PPOTrainingOrchestrator(SUPABASE_URL, SUPABASE_KEY)
        hf_publisher = HuggingFacePublisher(SUPABASE_URL, SUPABASE_KEY, HF_TOKEN, HF_ORG)
        logger.info("Storage and coordinators initialized")
    else:
        logger.warning("SUPABASE_SERVICE_ROLE_KEY not set, using limited functionality")

    # Connect to NATS
    try:
        logger.info("Connecting to NATS at %s...", NATS_URL)
        nc = await nats.connect(NATS_URL)
        logger.info("Connected to NATS")

        # Subscribe to Geometry Bus events
        async def geometry_message_handler(msg):
            """Handle geometry events and accumulate trajectory data."""
            subject = msg.subject
            data = msg.data

            if trajectory_accumulator:
                try:
                    result = await trajectory_accumulator.process_geometry_event(
                        subject=subject,
                        data=data,
                    )
                    if result:
                        logger.debug(
                            "Processed geometry event: trajectory_id=%s",
                            result.get("trajectory_id"),
                        )
                except json.JSONDecodeError as e:
                    logger.exception("Invalid JSON in geometry event")
                except (KeyError, TypeError) as e:
                    logger.exception("Invalid geometry event structure")
                except Exception as e:
                    logger.exception("Unexpected error processing geometry event")

        # Subscribe to geometry events
        await nc.subscribe("geometry.event.v1", cb=geometry_message_handler)
        await nc.subscribe("tokenism.geometry.event.v1", cb=geometry_message_handler)
        logger.info("Subscribed to geometry event subjects")

        # Subscribe to HuggingFace model download events
        async def hf_model_handler(msg):
            """Handle HF model download notifications for training pipeline."""
            try:
                data = json.loads(msg.data)
                model_id = data.get("model_id")
                model_path = data.get("path")
                if model_id and model_path:
                    logger.info(
                        "HF model downloaded: %s at %s — recording for training pipeline",
                        model_id, model_path,
                    )
                    if storage:
                        await storage.record_event(
                            event_type="hf_model_downloaded",
                            payload={"model_id": model_id, "path": model_path},
                        )
                else:
                    logger.warning(
                        "hf.model.downloaded event missing model_id or path: %s",
                        data,
                    )
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON in hf.model.downloaded event: %s",
                    msg.data[:200] if msg.data else b"<empty>",
                )
            except Exception:
                logger.exception(
                    "Error processing HF model download event, payload=%s",
                    msg.data[:500] if msg.data else b"<empty>",
                )

        await nc.subscribe("hf.model.downloaded.v1", cb=hf_model_handler)
        logger.info("Subscribed to hf.model.downloaded.v1")

        # Subscribe to training completion events from EvoSwarm
        async def training_completed_handler(msg):
            """
            Handle a training completion event by optionally publishing associated trajectories to HuggingFace, emitting related NATS events, and recording the completion in storage.

            Parameters:
                msg: NATS message whose `data` is a JSON-encoded payload containing at minimum a `training_run_id` and optionally `trajectory_ids` and `model_id`.
            """
            try:
                data = json.loads(msg.data)
                training_run_id = data.get("training_run_id")
                trajectory_ids = data.get("trajectory_ids", [])
                model_id = data.get("model_id", "unknown")

                if not training_run_id:
                    logger.warning("agentgym.train.completed.v1 missing training_run_id")
                    return

                if not DATASET_NAME_PATTERN.match(training_run_id):
                    logger.warning("Invalid training_run_id format: %s", training_run_id[:100])
                    return

                logger.info(
                    "Training completed: run=%s, trajectories=%d, model=%s",
                    training_run_id, len(trajectory_ids), model_id,
                )

                # Validate trajectory IDs as UUIDs before publishing
                valid_trajectory_ids = []
                for tid in trajectory_ids:
                    try:
                        UUID(tid)
                        valid_trajectory_ids.append(tid)
                    except (ValueError, AttributeError):
                        logger.warning("Skipping invalid trajectory_id: %s", str(tid)[:100])
                trajectory_ids = valid_trajectory_ids

                # Auto-publish to HuggingFace if publisher is available
                if hf_publisher and trajectory_ids:
                    dataset_name = f"agentgym-{training_run_id}"
                    try:
                        result = await hf_publisher.publish_to_huggingface(
                            dataset_name=dataset_name,
                            trajectory_ids=trajectory_ids,
                            private=False,
                        )
                        logger.info(
                            "Auto-published to HuggingFace: %s",
                            result.get("repo_url"),
                        )

                        # Publish model published event
                        if nc and nc.is_connected:
                            published_event = json.dumps({
                                "training_run_id": training_run_id,
                                "model_id": model_id,
                                "dataset_id": result.get("dataset_id"),
                                "repo_url": result.get("repo_url"),
                                "trajectory_count": len(trajectory_ids),
                                "source": "agentgym-rl-coordinator",
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            })
                            await nc.publish(
                                "agentgym.model.published.v1",
                                published_event.encode(),
                            )
                            logger.info("Published agentgym.model.published.v1")

                            # Trigger benchmark visualization pipeline
                            pipeline_event = json.dumps({
                                "training_run_id": training_run_id,
                                "model_id": model_id,
                                "repo_url": result.get("repo_url"),
                                "source": "agentgym-rl-coordinator",
                            })
                            await nc.publish(
                                "skills.pipeline.model-benchmark-viz.v1",
                                pipeline_event.encode(),
                            )
                            logger.info("Triggered model-benchmark-viz pipeline")

                    except Exception:
                        logger.exception(
                            "Failed to auto-publish training run %s to HuggingFace",
                            training_run_id,
                        )
                elif not hf_publisher:
                    logger.warning(
                        "HF publisher not available, skipping auto-publish for run %s",
                        training_run_id,
                    )

                # Record completion event
                if storage:
                    await storage.record_event(
                        event_type="training_completed",
                        payload=data,
                    )

            except json.JSONDecodeError:
                logger.warning("Invalid JSON in agentgym.train.completed.v1")
            except Exception:
                logger.exception("Error handling training completion event")

        await nc.subscribe("agentgym.train.completed.v1", cb=training_completed_handler)
        logger.info("Subscribed to agentgym.train.completed.v1")

    except Exception as e:
        logger.exception("Failed to connect to NATS")

    yield

    # Shutdown
    if nc:
        try:
            await nc.close()
        except Exception as e:
            logger.warning("Error closing NATS connection: %s", e)

    if trajectory_accumulator:
        await trajectory_accumulator.close()
    if training_orchestrator:
        await training_orchestrator.close()
    if hf_publisher:
        await hf_publisher.close()
    if storage:
        await storage.close()


app = FastAPI(
    title="AgentGym RL Coordinator",
    description="PPO training orchestration and trajectory accumulation",
    version="0.1.0",
    lifespan=lifespan
)


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/healthz")
async def health_check():
    """
    Report current connectivity/configuration status for core services (NATS, Supabase, HuggingFace).
    
    Returns:
        dict: A mapping with the following keys:
            - "status": overall service status, set to "ok".
            - "nats": "connected" if the NATS client is connected, "disconnected" otherwise.
            - "supabase": "connected" if Supabase storage is configured, "not_configured" otherwise.
            - "huggingface": "configured" if a HuggingFace token is present, "missing" otherwise.
    """
    nats_status = "connected" if nc and nc.is_connected else "disconnected"
    supabase_status = "connected" if storage else "not_configured"
    hf_status = "configured" if HF_TOKEN else "missing"

    return {
        "status": "ok",
        "nats": nats_status,
        "supabase": supabase_status,
        "huggingface": hf_status,
    }


@app.get("/metrics")
async def metrics():
    """
    Expose Prometheus-formatted service and dependency status metrics.
    
    Returns:
        PlainTextResponse: Prometheus text exposition containing the following gauges with value `1` (connected/configured) or `0` (not):
            - `agentgym_up`: overall service health (always `1` while running)
            - `agentgym_nats_connected`: NATS connection status
            - `agentgym_supabase_connected`: Supabase storage availability
            - `agentgym_hf_configured`: HuggingFace token configuration status
    """
    nats_connected = 1 if nc and nc.is_connected else 0
    supabase_connected = 1 if storage else 0
    hf_configured = 1 if HF_TOKEN else 0

    lines = [
        "# HELP agentgym_up Service health status",
        "# TYPE agentgym_up gauge",
        "agentgym_up 1",
        "# HELP agentgym_nats_connected NATS connection status",
        "# TYPE agentgym_nats_connected gauge",
        f"agentgym_nats_connected {nats_connected}",
        "# HELP agentgym_supabase_connected Supabase connection status",
        "# TYPE agentgym_supabase_connected gauge",
        f"agentgym_supabase_connected {supabase_connected}",
        "# HELP agentgym_hf_configured HuggingFace token configured",
        "# TYPE agentgym_hf_configured gauge",
        f"agentgym_hf_configured {hf_configured}",
    ]

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")


@app.get("/agentgym/stats")
async def get_stats():
    """
    Assembles current connectivity and component statistics for the coordinator service.
    
    Returns:
        stats (dict): Dictionary containing:
            - `nats_connected` (bool): whether the NATS client is connected.
            - `supabase_connected` (bool): whether Supabase storage is configured.
            - trajectory-related statistics merged at the top level when available (from the trajectory accumulator).
            - `storage` (dict, optional): storage-specific statistics when available.
    """
    stats = {
        "nats_connected": nc is not None and nc.is_connected,
        "supabase_connected": storage is not None,
    }

    if trajectory_accumulator:
        traj_stats = await trajectory_accumulator.get_trajectory_stats()
        stats.update(traj_stats)

    if storage:
        storage_stats = await storage.get_stats()
        stats["storage"] = storage_stats

    return stats


# ============================================================================
# Trajectory Endpoints
# ============================================================================

@app.get("/agentgym/trajectories")
async def list_trajectories(
    session_id: Optional[str] = None,
    unpublished_only: bool = False,
    limit: int = 100,
):
    """List accumulated trajectories.

    Args:
        session_id: Filter by session ID
        unpublished_only: Only return unpublished trajectories
        limit: Max results
    """
    if not trajectory_accumulator:
        raise HTTPException(status_code=503, detail="Trajectory accumulator not available")

    trajectories = await trajectory_accumulator.list_trajectories(
        session_id=session_id,
        unpublished_only=unpublished_only,
        limit=limit,
    )

    return {"trajectories": trajectories, "count": len(trajectories)}


@app.get("/agentgym/trajectories/stats")
async def get_trajectory_stats():
    """Get trajectory accumulation statistics."""
    if not trajectory_accumulator:
        raise HTTPException(status_code=503, detail="Trajectory accumulator not available")

    return await trajectory_accumulator.get_trajectory_stats()


@app.get("/agentgym/trajectories/{trajectory_id}")
async def get_trajectory(trajectory_id: str):
    """Get a specific trajectory by ID."""
    # Validate trajectory_id is a UUID
    try:
        UUID(trajectory_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid trajectory_id format. Must be a valid UUID."
        )

    if not trajectory_accumulator:
        raise HTTPException(status_code=503, detail="Trajectory accumulator not available")

    trajectory = await trajectory_accumulator.get_trajectory(trajectory_id)
    if not trajectory:
        raise HTTPException(status_code=404, detail="Trajectory not found")

    return trajectory


# ============================================================================
# Training Endpoints
# ============================================================================

@app.post("/agentgym/train/start")
async def start_training(
    run_id: str,
    config: Optional[dict] = None,
):
    """Start PPO training for a run.

    Args:
        run_id: Unique training run identifier
        config: Optional PPO configuration override
    """
    if not training_orchestrator:
        raise HTTPException(status_code=503, detail="Training orchestrator not available")

    result = await training_orchestrator.start_training(run_id, config)
    return result


@app.get("/agentgym/train/status/{run_id}")
async def get_training_status(run_id: str):
    """Get training run status.

    Args:
        run_id: Training run ID
    """
    if not training_orchestrator:
        raise HTTPException(status_code=503, detail="Training orchestrator not available")

    status = await training_orchestrator.get_training_status(run_id)
    if not status:
        raise HTTPException(status_code=404, detail="Training run not found")

    return status


@app.get("/agentgym/train/jobs")
async def list_training_jobs(
    status: Optional[str] = None,
    limit: int = 50,
):
    """List training runs.

    Args:
        status: Filter by status (pending, running, completed, failed, cancelled)
        limit: Max results
    """
    # Validate status parameter
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    if not training_orchestrator:
        raise HTTPException(status_code=503, detail="Training orchestrator not available")

    jobs = await training_orchestrator.list_training_runs(status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@app.post("/agentgym/train/cancel/{run_id}")
async def cancel_training(run_id: str):
    """Cancel a running training job.

    Args:
        run_id: Training run ID
    """
    if not training_orchestrator:
        raise HTTPException(status_code=503, detail="Training orchestrator not available")

    cancelled = await training_orchestrator.cancel_training(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Training run not found or not running")

    return {"run_id": run_id, "status": "cancelled"}


# ============================================================================
# Dataset Publishing Endpoints
# ============================================================================

@app.post("/agentgym/dataset/publish")
async def publish_dataset(
    dataset_name: str,
    trajectory_ids: Optional[list[str]] = None,
    session_id: Optional[str] = None,
    private: bool = False,
):
    """
    Publish trajectories as a dataset to HuggingFace.
    
    Validates the dataset name and optional trajectory IDs, requires the HuggingFace publisher to be configured, and delegates publishing to the configured publisher.
    
    Parameters:
        dataset_name (str): Desired dataset name; must match allowed pattern (alphanumeric, dash, underscore) and be at most 100 characters.
        trajectory_ids (Optional[list[str]]): Optional list of trajectory UUID strings to include in the dataset.
        session_id (Optional[str]): Optional session identifier; when provided, trajectories from this session may be included.
        private (bool): If True, create the dataset as private.
    
    Returns:
        dict: The publisher's result containing publication metadata (e.g., dataset/repository information).
    
    Raises:
        HTTPException: 400 for invalid dataset_name or trajectory_id format, 503 if the HuggingFace publisher is unavailable, 500 for other publication failures.
    """
    # Validate dataset_name (HuggingFace naming conventions)
    if not DATASET_NAME_PATTERN.match(dataset_name):
        raise HTTPException(
            status_code=400,
            detail="Invalid dataset_name. Use alphanumeric, dash, underscore only (max 100 chars)"
        )
    if len(dataset_name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Dataset name too long (maximum 100 characters)"
        )

    # Validate trajectory_ids if provided
    if trajectory_ids:
        for tid in trajectory_ids:
            try:
                UUID(tid)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid trajectory_id format: {tid}. Must be a valid UUID.",
                ) from e

    if not hf_publisher:
        raise HTTPException(status_code=503, detail="HuggingFace publisher not available")

    try:
        result = await hf_publisher.publish_to_huggingface(
            dataset_name=dataset_name,
            trajectory_ids=trajectory_ids,
            session_id=session_id,
            private=private,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish dataset: {e!s}") from e


@app.get("/agentgym/datasets")
async def list_published_datasets():
    """List published HuggingFace datasets."""
    if not hf_publisher:
        raise HTTPException(status_code=503, detail="HuggingFace publisher not available")

    datasets = await hf_publisher.list_published_datasets()
    return {"datasets": datasets, "count": len(datasets)}
