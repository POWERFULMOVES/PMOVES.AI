import os
import json
import logging
import re
import asyncio
from contextlib import asynccontextmanager
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
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
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
    """Application lifespan management."""
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
                except Exception as e:
                    logger.exception("Failed to process geometry event")

        # Subscribe to geometry events
        await nc.subscribe("geometry.event.v1", cb=geometry_message_handler)
        await nc.subscribe("tokenism.geometry.event.v1", cb=geometry_message_handler)
        logger.info("Subscribed to geometry event subjects")

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

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    nats_status = "connected" if nc and nc.is_connected else "disconnected"
    supabase_status = "connected" if storage else "not_configured"
    hf_status = "configured" if HF_TOKEN else "missing"

    return {
        "status": "ok",
        "nats": nats_status,
        "supabase": supabase_status,
        "huggingface": hf_status,
    }


@app.get("/agentgym/stats")
async def get_stats():
    """Get system statistics."""
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
    """Publish dataset to HuggingFace.

    Args:
        dataset_name: Name for the dataset
        trajectory_ids: List of trajectory IDs to include
        session_id: Alternative: include all trajectories from a session
        private: Whether to create a private dataset
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
