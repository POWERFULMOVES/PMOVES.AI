"""HTTP API routes for GPU Orchestrator."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/gpu", tags=["gpu"])


# Request/Response models
class LoadModelRequest(BaseModel):
    """Request to load a model."""

    model_id: str
    provider: str  # ollama, vllm, tts
    priority: int = 5
    session_id: Optional[str] = None


class LoadModelResponse(BaseModel):
    """Response for model load request."""

    request_id: str
    model_key: str
    already_loaded: bool
    message: str


class UnloadModelResponse(BaseModel):
    """Response for model unload request."""

    success: bool
    model_key: str
    message: str


class OptimizeResponse(BaseModel):
    """Response for GPU optimization."""

    unloaded: list[str]
    errors: list[str]
    message: str


# These will be set by main.py after app creation
_lifecycle_manager = None
_vram_tracker = None
_model_registry = None


def set_dependencies(lifecycle_manager, vram_tracker, model_registry):
    """Set service dependencies for routes."""
    global _lifecycle_manager, _vram_tracker, _model_registry
    _lifecycle_manager = lifecycle_manager
    _vram_tracker = vram_tracker
    _model_registry = model_registry


@router.get("/status")
async def get_gpu_status():
    """Get full GPU status with VRAM breakdown.

    Returns GPU metrics, running processes, and loaded models.
    """
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    status = await _lifecycle_manager.get_status()
    return status.to_dict()


@router.get("/metrics/summary")
async def get_metrics_summary():
    """Get summarized GPU metrics.

    Lighter weight than full status - just key metrics.
    """
    if not _vram_tracker:
        raise HTTPException(status_code=503, detail="Service not initialized")

    metrics = _vram_tracker.get_metrics()
    return {
        "total_vram_mb": metrics.total_vram_mb,
        "used_vram_mb": metrics.used_vram_mb,
        "free_vram_mb": metrics.free_vram_mb,
        "vram_usage_percent": metrics.vram_usage_percent,
        "temperature_c": metrics.temperature_c,
        "utilization_percent": metrics.utilization_percent,
    }


@router.get("/models")
async def list_models(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    include_unloaded: bool = Query(True, description="Include unloaded models from registry"),
):
    """List models and their memory requirements.

    Returns loaded models and optionally known models from registry.
    """
    if not _lifecycle_manager or not _model_registry:
        raise HTTPException(status_code=503, detail="Service not initialized")

    loaded = _lifecycle_manager.get_loaded_models()

    result = {
        "loaded": loaded,
        "loaded_count": len(loaded),
    }

    if include_unloaded:
        registry_models = _model_registry.list_models(provider)
        result["registry"] = [m.to_dict() for m in registry_models]
        result["registry_count"] = len(registry_models)

    return result


@router.get("/models/loaded")
async def list_loaded_models():
    """List only currently loaded models."""
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return {
        "models": _lifecycle_manager.get_loaded_models(),
    }


@router.post("/models/load", response_model=LoadModelResponse)
async def load_model(request: LoadModelRequest):
    """Load a model with priority queueing.

    If insufficient VRAM, idle models may be evicted automatically.
    """
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        request_id, already_loaded = await _lifecycle_manager.request_load(
            model_id=request.model_id,
            provider=request.provider,
            priority=request.priority,
            session_id=request.session_id,
        )

        model_key = f"{request.provider}/{request.model_id}"

        if already_loaded:
            return LoadModelResponse(
                request_id=request_id,
                model_key=model_key,
                already_loaded=True,
                message=f"Model {model_key} is already loaded",
            )
        else:
            return LoadModelResponse(
                request_id=request_id,
                model_key=model_key,
                already_loaded=False,
                message=f"Model {model_key} queued for loading",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/unload/{provider}/{model_id}", response_model=UnloadModelResponse)
async def unload_model(
    provider: str,
    model_id: str,
    force: bool = Query(False, description="Force unload even if in active session"),
):
    """Unload a specific model to free VRAM.

    Note: vLLM and TTS do not support dynamic unloading.
    """
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    model_key = f"{provider}/{model_id}"

    try:
        success = await _lifecycle_manager.unload_model(
            model_id=model_id,
            provider=provider,
            force=force,
        )

        if success:
            return UnloadModelResponse(
                success=True,
                model_key=model_key,
                message=f"Model {model_key} unloaded successfully",
            )
        else:
            return UnloadModelResponse(
                success=False,
                model_key=model_key,
                message=f"Failed to unload {model_key} - may be in active session or not loaded",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_gpu():
    """Auto-optimize GPU by unloading idle models.

    Frees VRAM by unloading models that have been idle past threshold.
    """
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        result = await _lifecycle_manager.optimize()
        return OptimizeResponse(
            unloaded=result["unloaded"],
            errors=result["errors"],
            message=f"Optimization complete: {len(result['unloaded'])} models unloaded",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue")
async def get_load_queue():
    """Get current load queue status."""
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return _lifecycle_manager.get_queue_status()


@router.get("/sessions")
async def list_sessions():
    """List active model sessions."""
    if not _lifecycle_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return {
        "sessions": _lifecycle_manager.session_manager.list_sessions(),
    }


@router.get("/registry")
async def get_registry():
    """Get full model registry configuration."""
    if not _model_registry:
        raise HTTPException(status_code=503, detail="Service not initialized")

    return _model_registry.to_dict()


@router.get("/processes")
async def get_gpu_processes():
    """Get list of processes using GPU."""
    if not _vram_tracker:
        raise HTTPException(status_code=503, detail="Service not initialized")

    processes = _vram_tracker.get_processes()
    return {
        "processes": [p.to_dict() for p in processes],
        "count": len(processes),
    }
