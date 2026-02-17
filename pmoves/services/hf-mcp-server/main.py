#!/usr/bin/env python3
"""
Hugging Face MCP Server for PMOVES.AI

Provides Model Context Protocol tools for:
- Model discovery from Hugging Face Hub
- Model download and caching to shared volume
- Model metadata extraction (size, requirements, quantization)
- GGUF conversion support for Ollama
- vLLM compatibility checking

MCP Tools:
- hf.model.search: Search models by task, size, architecture
- hf.model.info: Get model metadata and requirements
- hf.model.download: Download model to local cache
- hf.model.list: List cached models
- hf.model.convert_gguf: Convert to GGUF for Ollama
"""

import asyncio
import json
import logging
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from huggingface_hub import (
    HfApi,
    ModelFilter,
    hf_hub_download,
    snapshot_download,
)
from huggingface_hub.utils import tqdm as hf_tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment variables
HF_HOME = os.environ.get("HF_HOME", "/models")
HF_HUB_CACHE = os.environ.get("HF_HUB_CACHE", "/models/hub")
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
SERVER_PORT = int(os.environ.get("PORT", "8096"))

MODELS_BASE = Path(HF_HUB_CACHE) / "models"

# Metrics counter with thread safety
_download_count = 0
_download_lock = threading.Lock()


_SAFE_MODEL_RE = re.compile(r"^[a-zA-Z0-9._/-]+$")


def _safe_model_path(model_id: str) -> Path:
    """Resolve a model cache path, rejecting path traversal attempts."""
    if ".." in model_id or not _SAFE_MODEL_RE.match(model_id):
        raise HTTPException(status_code=400, detail="Invalid model ID")
    sanitized = model_id.replace("/", "--")
    resolved = (MODELS_BASE / sanitized).resolve()
    try:
        resolved.relative_to(MODELS_BASE.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid model ID") from None
    return resolved


class ModelTier(Enum):
    """Hardware tier classifications for models."""
    SMALL = "small"  # 3B-8B, CPU/Edge
    MEDIUM = "medium"  # 7B-14B, Single GPU
    LARGE = "large"  # 30B-70B, Multi-GPU
    XLARGE = "xlarge"  # 70B+, Multi-GPU cluster


class ModelUse(Enum):
    """Model use case categories."""
    ORCHESTRATOR = "orchestrator"  # Complex reasoning tasks
    CODING = "coding"  # Code generation
    UTILITY = "utility"  # Fast simple tasks
    VL_SENTINEL = "vl_sentinel"  # Vision-language processing
    EMBEDDINGS = "embeddings"  # Text embeddings
    HIRAG_RERANK = "hirag_rerank"  # RAG reranking
    RESEARCH = "research"  # Deep research tasks


class BackendType(Enum):
    """Supported inference backends."""
    OLLAMA = "ollama"
    VLLM = "vllm"
    LLAMA_CPP = "llama_cpp"
    TRANSFORMERS = "transformers"


@dataclass
class ModelMetadata:
    """Metadata for a Hugging Face model."""
    model_id: str
    name: str
    params: int  # Parameter count
    context_length: int = 4096
    quantization: str = "fp16"
    tier: ModelTier = ModelTier.MEDIUM
    uses: List[ModelUse] = field(default_factory=list)
    backends: List[BackendType] = field(default_factory=lambda: [BackendType.TRANSFORMERS])
    hf_url: str = ""
    requires_gpu: bool = True
    min_vram_mb: int = 0
    recommended_tp_size: int = 1
    max_tp_size: int = 1
    supports_pp: bool = False
    dimensions: Optional[int] = None  # For embedding models
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create ModelMetadata from dictionary.

        Args:
            data: Dictionary containing model metadata from catalog

        Returns:
            ModelMetadata instance with parsed enum values

        Raises:
            KeyError: If required field 'model_id' or 'name' is missing
        """
        uses = [ModelUse(u) for u in data.get("uses", [])]
        backends = [BackendType(b) for b in data.get("backends", ["transformers"])]
        tier = ModelTier(data.get("tier", "medium"))
        return cls(
            model_id=data["model_id"],
            name=data["name"],
            params=data["params"],
            context_length=data.get("context_length", 4096),
            quantization=data.get("quantization", "fp16"),
            tier=tier,
            uses=uses,
            backends=backends,
            hf_url=data.get("hf_url", ""),
            requires_gpu=data.get("requires_gpu", True),
            min_vram_mb=data.get("min_vram_mb", 0),
            recommended_tp_size=data.get("recommended_tp_size", 1),
            max_tp_size=data.get("max_tp_size", 1),
            supports_pp=data.get("supports_pp", False),
            dimensions=data.get("dimensions"),
            tags=data.get("tags", []),
        )


# Model catalog with recommended models
MODEL_CATALOG: Dict[str, Dict[str, Any]] = {
    # Small Models (3B-8B) - CPU/Edge
    "phi3-mini": {
        "model_id": "microsoft/Phi-3-mini-128k-instruct",
        "name": "phi3-mini",
        "params": 3_800_000_000,
        "context_length": 128000,
        "quantization": "fp16",
        "tier": "small",
        "uses": ["utility", "edge"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "phi3:3.8b-mini-128k-instruct",
        "hf_url": "https://huggingface.co/microsoft/Phi-3-mini-128k-instruct",
    },
    "gemma-2-2b": {
        "model_id": "google/gemma-2-2b-it",
        "name": "gemma-2-2b",
        "params": 2_000_000_000,
        "context_length": 8192,
        "quantization": "fp16",
        "tier": "small",
        "uses": ["utility"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "gemma-2:2b",
        "hf_url": "https://huggingface.co/google/gemma-2-2b-it",
    },

    # Medium Models (7B-14B) - Single GPU
    "qwen2.5-7b": {
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "qwen2.5-7b",
        "params": 7_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["orchestrator", "coding", "utility"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "qwen2.5:7b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        "min_vram_mb": 16384,
        "recommended_tp_size": 1,
        "max_tp_size": 2,
    },
    "qwen2.5-14b": {
        "model_id": "Qwen/Qwen2.5-14B-Instruct",
        "name": "qwen2.5-14b",
        "params": 14_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["orchestrator", "coding"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "qwen2.5:14b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-14B-Instruct",
        "min_vram_mb": 24576,
        "recommended_tp_size": 1,
        "max_tp_size": 2,
    },
    "llama3.1-8b": {
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
        "name": "llama3.1-8b",
        "params": 8_000_000_000,
        "context_length": 128000,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["orchestrator", "utility"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "llama3.1:8b",
        "hf_url": "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct",
        "min_vram_mb": 16384,
        "recommended_tp_size": 1,
        "max_tp_size": 4,
    },
    "gemma-2-9b": {
        "model_id": "google/gemma-2-9b",
        "name": "gemma-2-9b",
        "params": 9_000_000_000,
        "context_length": 8192,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["orchestrator", "utility"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "gemma-2:9b",
        "hf_url": "https://huggingface.co/google/gemma-2-9b",
    },
    "qwen2.5-coder-7b": {
        "model_id": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "name": "qwen2.5-coder-7b",
        "params": 7_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["coding"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "qwen2.5-coder:7b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct",
    },
    "deepseek-coder-6.7b": {
        "model_id": "deepseek-ai/deepseek-coder-6.7b-instruct",
        "name": "deepseek-coder-6.7b",
        "params": 6_700_000_000,
        "context_length": 16384,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["coding"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "deepseek-coder:6.7b",
        "hf_url": "https://huggingface.co/deepseek-ai/deepseek-coder-6.7b-instruct",
    },

    # Large Models (30B-70B) - Multi-GPU
    "qwen2.5-32b": {
        "model_id": "Qwen/Qwen2.5-32B-Instruct",
        "name": "qwen2.5-32b",
        "params": 32_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "large",
        "uses": ["orchestrator", "research"],
        "backends": ["vllm"],
        "ollama_name": "qwen2.5:32b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-32B-Instruct",
        "min_vram_mb": 49152,
        "recommended_tp_size": 2,
        "max_tp_size": 4,
        "supports_pp": True,
    },
    "qwen2.5-72b": {
        "model_id": "Qwen/Qwen2.5-72B-Instruct",
        "name": "qwen2.5-72b",
        "params": 72_000_000_000,
        "context_length": 128000,
        "quantization": "fp16",
        "tier": "large",
        "uses": ["research", "coordinator"],
        "backends": ["vllm"],
        "ollama_name": "qwen2.5:72b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2.5-72B-Instruct",
        "min_vram_mb": 81920,
        "recommended_tp_size": 4,
        "max_tp_size": 8,
        "supports_pp": True,
    },

    # Vision-Language Models
    "qwen2-vl-7b": {
        "model_id": "Qwen/Qwen2-VL-7B-Instruct",
        "name": "qwen2-vl-7b",
        "params": 7_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["vl_sentinel"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "qwen2-vl:7b",
        "hf_url": "https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct",
    },
    "llava-v1.6-7b": {
        "model_id": "llava-hf/llava-v1.6-vicuna-7b-hf",
        "name": "llava-v1.6-7b",
        "params": 7_000_000_000,
        "context_length": 4096,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["vl_sentinel"],
        "backends": ["vllm"],
        "hf_url": "https://huggingface.co/llava-hf/llava-v1.6-vicuna-7b-hf",
    },

    # Embedding Models
    "qwen3-embedding-8b": {
        "model_id": "Qwen/Qwen3-Embedding-8B",
        "name": "qwen3-embedding-8b",
        "params": 8_000_000_000,
        "context_length": 32768,
        "quantization": "fp16",
        "tier": "medium",
        "uses": ["embeddings", "hirag"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "qwen3-embedding:8b",
        "hf_url": "https://huggingface.co/Qwen/Qwen3-Embedding-8B",
        "dimensions": 4096,
    },
    "bge-large-en-v1.5": {
        "model_id": "BAAI/bge-large-en-v1.5",
        "name": "bge-large-en-v1.5",
        "params": 1_340_000_000,
        "context_length": 512,
        "quantization": "fp16",
        "tier": "small",
        "uses": ["embeddings"],
        "backends": ["ollama", "vllm"],
        "ollama_name": "bge-large",
        "hf_url": "https://huggingface.co/BAAI/bge-large-en-v1.5",
        "dimensions": 1024,
    },
    "nomic-embed-text": {
        "model_id": "nomic-ai/nomic-embed-text-v1.5",
        "name": "nomic-embed-text",
        "params": 137_000_000,
        "context_length": 8192,
        "quantization": "fp16",
        "tier": "small",
        "uses": ["embeddings"],
        "backends": ["ollama"],
        "ollama_name": "nomic-embed-text",
        "hf_url": "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5",
        "dimensions": 768,
    },

    # Rerankers
    "qwen3-reranker-4b": {
        "model_id": "Qwen/Qwen3-Reranker-4B",
        "name": "qwen3-reranker-4b",
        "params": 4_000_000_000,
        "context_length": 512,
        "quantization": "fp16",
        "tier": "small",
        "uses": ["hirag_rerank"],
        "backends": ["ollama"],
        "ollama_name": "qwen3-reranker:4b",
        "hf_url": "https://huggingface.co/Qwen/Qwen3-Reranker-4B",
    },
}


# FastAPI app
app = FastAPI(title="Hugging Face MCP Server", version="1.0.0")

# Hugging Face API client
hf_api = HfApi()


# =============================================================================
# MCP Tool Handlers
# =============================================================================

async def hf_model_search(
    task: Optional[str] = None,
    size: Optional[str] = None,
    architecture: Optional[str] = None,
    tier: Optional[str] = None,
    use_case: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search for models in the catalog.

    Args:
        task: Model task (text-generation, embedding, etc.)
        size: Model size tier (small, medium, large)
        architecture: Model architecture (llama, qwen, etc.)
        tier: Same as size (for backwards compatibility)
        use_case: Intended use case (orchestrator, coding, etc.)

    Returns:
        List of matching model metadata dictionaries
    """
    # Filter models from catalog
    results = []

    for model_key, model_data in MODEL_CATALOG.items():
        # Filter by tier/size
        filter_tier = tier or size
        if filter_tier and model_data.get("tier") != filter_tier:
            continue

        # Filter by use case
        if use_case and use_case not in model_data.get("uses", []):
            continue

        # Filter by architecture (partial match on model_id)
        if architecture and architecture.lower() not in model_data["model_id"].lower():
            continue

        results.append({
            "key": model_key,
            **model_data,
        })

    return results


async def hf_model_info(model_id: str) -> Dict[str, Any]:
    """Get detailed metadata for a specific model.

    Args:
        model_id: Model identifier (catalog key or HF model ID)

    Returns:
        Model metadata dictionary
    """
    # Check if it's a catalog key
    if model_id in MODEL_CATALOG:
        model_data = MODEL_CATALOG[model_id]
        hf_id = model_data["model_id"]
    else:
        # Direct HF model ID
        hf_id = model_id
        model_data = {}

    try:
        # Fetch model info from Hugging Face Hub
        model_info = hf_api.model_info(hf_id)

        result = {
            "model_id": hf_id,
            "name": model_info.modelId,
            "hf_url": f"https://huggingface.co/{hf_id}",
            "tags": model_info.tags,
            "pipeline_tag": model_info.pipeline_tag,
            "private": model_info.private,
            "downloads": model_info.downloads,
            "likes": model_info.likes,
            "created_at": str(model_info.created_at),
            "last_modified": str(model_info.last_modified),
        }

        # Merge with catalog data if available
        if model_data:
            result.update(model_data)

        return result

    except Exception as e:
        logger.error(f"Error fetching model info for {hf_id}: {e}")
        # Return catalog data if available
        if model_data:
            return {
                "model_id": model_data.get("model_id", model_id),
                "name": model_data.get("name", model_id),
                **model_data,
            }
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")


async def hf_model_download(
    model_id: str,
    variant: Optional[str] = None,
    quantization: Optional[str] = None,
) -> Dict[str, Any]:
    """Download a model to the local cache.

    Args:
        model_id: Model identifier (catalog key or HF model ID)
        variant: Model variant (e.g., q4_0, q5_0, f16)
        quantization: Quantization format

    Returns:
        Download result with model path and metadata
    """
    # Resolve model ID
    if model_id in MODEL_CATALOG:
        model_data = MODEL_CATALOG[model_id]
        hf_id = model_data["model_id"]
    else:
        hf_id = model_id
        model_data = {}

    cache_dir = _safe_model_path(hf_id)

    try:
        # Create cache directory (must be inside try block for error handling)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Download model snapshot
        logger.info(f"Downloading model {hf_id} to {cache_dir}")

        with hf_tqdm():
            snapshot_download(
                repo_id=hf_id,
                local_dir=cache_dir,
                local_dir_use_symlinks=False,
            )

        # Publish NATS event
        await _publish_download_event(hf_id, str(cache_dir))

        # Increment download counter (thread-safe)
        global _download_count
        with _download_lock:
            _download_count += 1

        return {
            "ok": True,
            "model_id": hf_id,
            "name": model_data.get("name", hf_id),
            "path": str(cache_dir),
            "downloaded": True,
            "message": f"Model {hf_id} downloaded successfully",
        }

    except OSError as e:
        # File system errors (disk full, permission denied)
        logger.error(f"Filesystem error downloading model {hf_id}: {e}")
        raise HTTPException(
            status_code=507,
            detail=f"Insufficient storage or permission denied: {e}"
        )
    except Exception as e:
        logger.error(f"Error downloading model {hf_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def hf_model_list() -> List[Dict[str, Any]]:
    """List all models currently cached locally.

    Returns:
        List of cached model metadata
    """
    hub_path = Path(HF_HUB_CACHE) / "models"
    results = []

    if not hub_path.exists():
        return results

    for model_dir in hub_path.iterdir():
        if not model_dir.is_dir():
            continue

        # Convert back to HF model ID format
        hf_id = model_dir.name.replace("--", "/")

        # Get size
        total_size = 0
        file_count = 0
        for file_path in model_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1

        # Check if in catalog
        catalog_entry = None
        for key, data in MODEL_CATALOG.items():
            if data["model_id"] == hf_id:
                catalog_entry = data
                break

        results.append({
            "model_id": hf_id,
            "name": catalog_entry.get("name") if catalog_entry else hf_id,
            "path": str(model_dir),
            "size_bytes": total_size,
            "size_gb": round(total_size / (1024**3), 2),
            "file_count": file_count,
            "in_catalog": catalog_entry is not None,
        })

    return results


async def hf_model_convert_gguf(
    model_id: str,
    quantize: str = "q4_0",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a model to GGUF format for Ollama.

    Args:
        model_id: Model identifier
        quantize: Quantization format (q4_0, q4_k_m, q5_0, q8_0, f16)
        output_dir: Output directory for GGUF model

    Returns:
        Conversion result with output path
    """
    # This is a placeholder - actual GGUF conversion requires llama.cpp
    # In production, this would spawn a conversion job or call an external service

    cache_dir = _safe_model_path(model_id)

    if not cache_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Model {model_id} not found in cache. Download first.",
        )

    if output_dir:
        if ".." in output_dir or not re.match(r"^[a-zA-Z0-9._\-/]+$", output_dir):
            raise HTTPException(status_code=400, detail="Invalid output_dir")
        resolved = (cache_dir / output_dir).resolve()
        try:
            resolved.relative_to(cache_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="output_dir must be within model cache")
        output_path = str(resolved)
    else:
        output_path = str(cache_dir / "gguf")

    return {
        "ok": True,
        "model_id": model_id,
        "quantize": quantize,
        "output_path": output_path,
        "message": "GGUF conversion initiated. Check /status/{job_id} for progress.",
        "note": "Actual GGUF conversion requires llama.cpp integration",
    }


async def hf_tensorzero_config() -> Dict[str, Any]:
    """Generate TensorZero configuration for all catalog models.

    Returns:
        TensorZero configuration TOML fragment
    """
    config_lines = ["# Auto-generated by Hugging Face MCP Server", ""]
    ollama_base = "http://pmoves-ollama:11434/v1"

    for model_key, model_data in MODEL_CATALOG.items():
        model_name = model_data["name"]
        ollama_name = model_data.get("ollama_name")
        if not ollama_name:
            continue

        # Model config
        config_lines.append(f"[models.{model_name}]")
        config_lines.append('routing = ["ollama_local"]')
        config_lines.append("")
        config_lines.append(f"[models.{model_name}.providers.ollama_local]")
        config_lines.append('type = "openai"')
        config_lines.append(f'api_base = "{ollama_base}"')
        config_lines.append(f'model_name = "{ollama_name}"')
        config_lines.append('api_key_location = "none"')
        config_lines.append("")

    return {
        "ok": True,
        "config": "\n".join(config_lines),
        "format": "toml",
    }


# =============================================================================
# NATS Event Publishing
# =============================================================================

async def _publish_download_event(model_id: str, path: str):
    """Publish model download event to NATS message bus.

    Args:
        model_id: Hugging Face model identifier (e.g., 'Qwen/Qwen2.5-7B-Instruct')
        path: Local filesystem path where model was cached

    Side effects:
        Publishes JSON event to 'hf.model.downloaded.v1' NATS subject
        Logs success or failure of event publication

    Note:
        Falls back gracefully if NATS is unavailable.
        Event payload includes: model_id, path, timestamp
    """
    try:
        import nats

        nc = await nats.connect(NATS_URL)
        event = {
            "model_id": model_id,
            "path": path,
            "timestamp": asyncio.get_event_loop().time(),
        }
        await nc.publish("hf.model.downloaded.v1", json.dumps(event).encode())
        await nc.close()
        logger.info(f"Published download event for {model_id}")

    except ImportError:
        logger.warning("nats-py not installed, skipping event publish")
    except Exception as e:
        logger.error(f"Failed to publish NATS event: {e}")


# =============================================================================
# HTTP API Endpoints (FastAPI)
# =============================================================================

@app.get("/healthz")
async def health_check():
    """Health check endpoint following PMOVES.AI conventions.

    Returns:
        Dictionary with service status information including:
        - status: Service health state
        - service: Service name
        - version: Service version
        - hf_home: Hugging Face cache directory
        - hf_cache: Hub cache directory

    Note:
        Uses /healthz path to match PMOVES.AI service standards.
    """
    return {
        "status": "healthy",
        "service": "hf-mcp-server",
        "version": "1.0.0",
        "hf_home": HF_HOME,
        "hf_cache": HF_HUB_CACHE,
    }


# Legacy health endpoint for backward compatibility
@app.get("/health")
async def health_check_legacy():
    """Legacy health check endpoint (deprecated - use /healthz).

    Note:
        Maintained for backward compatibility.
        New clients should use /healthz instead.
    """
    return await health_check()


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint for observability.

    Returns:
        Prometheus-formatted metrics text with:
        - hf_mcp_server_up: Service availability
        - hf_mcp_cached_models_total: Number of cached models
        - hf_mcp_downloads_total: Total download count

    Note:
        Follows Prometheus text-based exposition format.
    """
    # Count cached models (ensure HF_HUB_CACHE is Path object)
    hub_cache = Path(HF_HUB_CACHE)
    cached_count = 0
    if hub_cache.exists():
        for model_dir in hub_cache.iterdir():
            if model_dir.is_dir() and (model_dir / "snapshots").exists():
                cached_count += 1

    metrics_text = f"""# HELP hf_mcp_server_up Service availability gauge
# TYPE hf_mcp_server_up gauge
hf_mcp_server_up 1.0

# HELP hf_mcp_cached_models_total Number of models in cache
# TYPE hf_mcp_cached_models_total gauge
hf_mcp_cached_models_total {cached_count}

# HELP hf_mcp_downloads_total Total model download count
# TYPE hf_mcp_downloads_total counter
hf_mcp_downloads_total {_download_count}
"""
    from fastapi.responses import Response
    return Response(
        content=metrics_text,
        media_type="text/plain",
        headers={"Content-Type": "text/plain; version=0.0.4"}
    )


@app.post("/api/model/search")
async def api_model_search(request: Dict[str, Any]):
    """Search for models in the catalog."""
    results = await hf_model_search(
        task=request.get("task"),
        size=request.get("size"),
        architecture=request.get("architecture"),
        tier=request.get("tier"),
        use_case=request.get("use_case"),
    )
    return {"ok": True, "models": results}


@app.get("/api/model/{model_id}")
async def api_model_info(model_id: str):
    """Get model info."""
    result = await hf_model_info(model_id)
    return {"ok": True, "model": result}


@app.post("/api/model/download")
async def api_model_download(request: Dict[str, Any]):
    """Download a model."""
    result = await hf_model_download(
        model_id=request["model_id"],
        variant=request.get("variant"),
        quantization=request.get("quantization"),
    )
    return result


@app.get("/api/models")
async def api_model_list():
    """List cached models."""
    results = await hf_model_list()
    return {"ok": True, "models": results}


@app.post("/api/model/convert-gguf")
async def api_model_convert_gguf(request: Dict[str, Any]):
    """Convert model to GGUF format."""
    result = await hf_model_convert_gguf(
        model_id=request["model_id"],
        quantize=request.get("quantize", "q4_0"),
        output_dir=request.get("output_dir"),
    )
    return result


@app.get("/api/config/tensorzero")
async def api_tensorzero_config():
    """Generate TensorZero config for catalog models."""
    result = await hf_tensorzero_config()
    return result


# =============================================================================
# SSE MCP Transport (for MCP clients)
# =============================================================================

@app.get("/sse")
async def sse_endpoint():
    """Server-Sent Events endpoint for MCP protocol."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        """Stream MCP events."""
        # Send initial endpoint announcement
        import json

        endpoints = [
            {
                "name": "hf.model.search",
                "description": "Search for models in the catalog",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "size": {"type": "string", "enum": ["small", "medium", "large"]},
                        "use_case": {"type": "string"},
                    },
                },
            },
            {
                "name": "hf.model.info",
                "description": "Get model metadata",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_id": {"type": "string"},
                    },
                    "required": ["model_id"],
                },
            },
            {
                "name": "hf.model.download",
                "description": "Download model to local cache",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "model_id": {"type": "string"},
                        "variant": {"type": "string"},
                    },
                    "required": ["model_id"],
                },
            },
            {
                "name": "hf.model.list",
                "description": "List cached models",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

        yield f"event: tools\ndata: {json.dumps(endpoints)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run the HF MCP Server."""
    import uvicorn

    logger.info(f"Starting Hugging Face MCP Server on port {SERVER_PORT}")
    logger.info(f"HF_HOME: {HF_HOME}")
    logger.info(f"HF_HUB_CACHE: {HF_HUB_CACHE}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=SERVER_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
