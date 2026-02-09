"""
PMOVES-BoTZ VL Sentinel - Vision-Language Monitoring

Vision-language processing agent for monitoring and diagnostics.
Supports Ollama (local) and vLLM backends with models from the HF catalog.

Model Options (from HF catalog):
- qwen2-vl:7b (Ollama) - 7B parameters, single GPU
- qwen3-vl:8b (vLLM) - 8B parameters, next generation
- llava-v1.6-7b (vLLM) - LLaVA architecture

Environment Variables:
- VL_PROVIDER: ollama (default) or vllm
- VL_MODEL: Model name (default: qwen2-vl:7b for ollama)
- OLLAMA_BASE_URL: Ollama API URL (default: http://pmoves-ollama:11434)
- VLLM_VL_URL: vLLM VL API URL (default: http://vllm-vl-8b:8000/v1)
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
import requests
import base64

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# OpenAI API key format validation (sk- followed by alphanumeric)
OPENAI_KEY_PATTERN = re.compile(r"^sk-[a-zA-Z0-9]{32,}$")

# Maximum URL length to prevent DoS (8KB)
MAX_URL_LENGTH = 8192

# Maximum image size (25MB) to prevent memory exhaustion
MAX_IMAGE_SIZE = 25 * 1024 * 1024

# =============================================================================
# Configuration
# =============================================================================

PROVIDER = os.environ.get("VL_PROVIDER", "ollama").lower()

# Model catalog mapping
VL_MODELS = {
    # Ollama models
    "qwen2-vl:7b": {
        "provider": "ollama",
        "hf_id": "Qwen/Qwen2-VL-7B-Instruct",
        "params": "7B",
        "context": "32768",
        "tier": "medium",
    },
    "qwen2-vl:14b": {
        "provider": "ollama",
        "hf_id": "Qwen/Qwen2-VL-14B-Instruct",
        "params": "14B",
        "context": "32768",
        "tier": "medium",
    },
    # vLLM models (by endpoint)
    "qwen3-vl-8b-vllm": {
        "provider": "vllm",
        "hf_id": "Qwen/Qwen3-VL-8B-Instruct",
        "params": "8B",
        "context": "32768",
        "tier": "medium",
    },
    "llava-v1.6-7b-vllm": {
        "provider": "vllm",
        "hf_id": "llava-hf/llava-v1.6-vicuna-7b-hf",
        "params": "7B",
        "context": "4096",
        "tier": "medium",
    },
}

# Default models by provider
DEFAULT_MODELS = {
    "ollama": "qwen2-vl:7b",
    "vllm": "qwen3-vl-8b-vllm",
}

# Configuration from environment
_env_model = os.environ.get("VL_MODEL")
MODEL = _env_model or DEFAULT_MODELS.get(PROVIDER, "qwen2-vl:7b")

OLLAMA_BASE_URL = os.environ.get(
    "OLLAMA_BASE_URL",
    "http://pmoves-ollama:11434"  # Docker network
)
# Fallback for standalone mode
if OLLAMA_BASE_URL == "http://pmoves-ollama:11434":
    if not os.path.exists("/.dockerenv"):
        OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

VLLM_VL_URL = os.environ.get(
    "VLLM_VL_URL",
    "http://vllm-vl-8b:8000/v1"
)

OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

app = FastAPI(title="PMOVES VL Sentinel", version="2.0.0")

# =============================================================================
# Data Models
# =============================================================================

class ImageInput(BaseModel):
    """Image input for VL processing.

    Attributes:
        url: Optional remote URL to fetch image from
        b64: Optional base64-encoded image data

    Note:
        Exactly one of url or b64 should be provided.
        URLs are validated for length to prevent DoS.
    """
    url: Optional[str] = None
    b64: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_url_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL length to prevent DoS attacks."""
        if v and len(v) > MAX_URL_LENGTH:
            raise ValueError(f"URL exceeds maximum length of {MAX_URL_LENGTH}")
        return v


class GuideRequest(BaseModel):
    """Request for VL guidance.

    Attributes:
        task: Description of the task or problem to diagnose
        images: Optional list of images to analyze
        logs: Optional list of log lines for context
        metrics: Optional dictionary of metrics for context
    """
    task: str
    images: Optional[List[ImageInput]] = None
    logs: Optional[List[str]] = None
    metrics: Optional[Dict[str, Any]] = None


class ModelInfo(BaseModel):
    """Model information from the catalog.

    Attributes:
        name: Model identifier (e.g., 'qwen2-vl:7b')
        provider: Backend provider ('ollama' or 'vllm')
        hf_id: Hugging Face model ID
        params: Model parameter count
        context: Context window size
        tier: Hardware tier classification
    """
    name: str
    provider: str
    hf_id: Optional[str] = None
    params: Optional[str] = None
    context: Optional[str] = None
    tier: Optional[str] = None

# =============================================================================
# Helper Functions
# =============================================================================

def get_model_info(model_name: str) -> Optional[ModelInfo]:
    """Get model information from the VL model catalog.

    Args:
        model_name: Model identifier to look up

    Returns:
        ModelInfo object if found in catalog, None otherwise

    Note:
        Catalog contains models from HF catalog with metadata
        including Hugging Face ID, parameters, and context length.
    """
    if model_name in VL_MODELS:
        info = VL_MODELS[model_name]
        return ModelInfo(
            name=model_name,
            provider=info["provider"],
            hf_id=info.get("hf_id"),
            params=info.get("params"),
            context=info.get("context"),
            tier=info.get("tier"),
        )
    return None


def fetch_b64(img: ImageInput) -> Optional[str]:
    """Fetch and convert image to base64 encoding.

    Args:
        img: ImageInput with either url or b64 data

    Returns:
        Base64-encoded image string, or None if no valid input

    Raises:
        HTTPException: If URL fetch fails or image exceeds size limit

    Note:
        Validates image size to prevent memory exhaustion.
        Returns pre-encoded b64 data directly if provided.
    """
    if img.b64:
        return img.b64
    if img.url:
        try:
            r = requests.get(img.url, timeout=15, stream=True)
            r.raise_for_status()

            # Check content length before downloading
            content_length = int(r.headers.get("content-length", 0))
            if content_length > MAX_IMAGE_SIZE:
                logger.warning(f"Image from {img.url} exceeds size limit: {content_length} bytes")
                raise HTTPException(
                    status_code=413,
                    detail=f"Image size ({content_length} bytes) exceeds maximum ({MAX_IMAGE_SIZE})"
                )

            # Download with size limit
            content = r.content
            if len(content) > MAX_IMAGE_SIZE:
                logger.warning(f"Image from {img.url} exceeds size limit after download: {len(content)} bytes")
                raise HTTPException(
                    status_code=413,
                    detail=f"Image size exceeds maximum of {MAX_IMAGE_SIZE} bytes"
                )

            return base64.b64encode(content).decode("utf-8")
        except requests.Timeout as e:
            logger.error(f"Timeout fetching image from {img.url}: {e}")
            raise HTTPException(status_code=408, detail=f"Image fetch timeout: {e}")
        except requests.ConnectionError as e:
            logger.error(f"Connection error fetching image from {img.url}: {e}")
            raise HTTPException(status_code=503, detail=f"Failed to connect to image server: {e}")
        except requests.HTTPError as e:
            logger.error(f"HTTP error fetching image from {img.url}: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Image server returned error: {e}")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch image from {img.url}: {e}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch image: {e}")
    return None


def ask_ollama(prompt: str, images_b64: List[str]) -> str:
    """Query Ollama vision-language model.

    Args:
        prompt: Text prompt for the model
        images_b64: List of base64-encoded images

    Returns:
        Model response text

    Raises:
        HTTPException: If Ollama request fails

    Note:
        Uses Ollama /api/generate endpoint with images array.
        120-second timeout for large image processing.
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "images": images_b64,
        "stream": False
    }
    r = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=120)
    if not r.ok:
        raise HTTPException(status_code=503, detail=f"Ollama error: {r.text[-500:]}")
    data = r.json()
    return data.get("response", "")


def ask_vllm(prompt: str, images_b64: List[str]) -> str:
    """Query vLLM vision-language model (OpenAI-compatible API).

    Args:
        prompt: Text prompt for the model
        images_b64: List of base64-encoded images

    Returns:
        Model response text

    Raises:
        HTTPException: If vLLM request fails

    Note:
        Uses OpenAI-compatible /chat/completions endpoint.
        Images are embedded as data URLs in the message content.
    """
    messages = [{
        "role": "user",
        "content": [{"type": "text", "text": prompt}]
    }]

    for b64 in images_b64:
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    payload = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 2048,
    }

    r = requests.post(f"{VLLM_VL_URL}/chat/completions", json=payload, timeout=120)
    if not r.ok:
        raise HTTPException(status_code=503, detail=f"vLLM error: {r.text[-500:]}")

    data = r.json()
    return data["choices"][0]["message"]["content"]


def ask_openai(prompt: str, images_b64: List[str]) -> str:
    """Query OpenAI vision-language API.

    Args:
        prompt: Text prompt for the model
        images_b64: List of base64-encoded images

    Returns:
        Model response text

    Raises:
        HTTPException: If API key is invalid or request fails

    Note:
        Requires OPENAI_API_KEY environment variable.
        API key format is validated (sk- prefix with 32+ alphanumeric chars).
    """
    if not OPENAI_KEY:
        raise HTTPException(status_code=401, detail="OPENAI_API_KEY not configured")

    # Validate API key format
    if not OPENAI_KEY_PATTERN.match(OPENAI_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid OPENAI_API_KEY format. Expected: sk- followed by 32+ alphanumeric characters"
        )

    headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
    messages = [{
        "role": "user",
        "content": [{"type": "text", "text": prompt}]
    }]

    for b64 in images_b64:
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        json={"model": MODEL, "messages": messages},
        headers=headers,
        timeout=120
    )

    if not r.ok:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {r.text[-500:]}")

    data = r.json()
    return data["choices"][0]["message"]["content"]

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/healthz")
def health_check():
    """Health check endpoint following PMOVES.AI conventions.

    Returns:
        Dictionary with service status, provider, and current model info

    Note:
        Uses /healthz path to match PMOVES.AI service standards.
    """
    model_info = get_model_info(MODEL)
    return {
        "status": "healthy",
        "provider": PROVIDER,
        "model": MODEL,
        "model_info": model_info.dict() if model_info else None,
    }


# Legacy health endpoint for backward compatibility
@app.get("/health")
def health_check_legacy():
    """Legacy health check endpoint (deprecated - use /healthz).

    Note:
        Maintained for backward compatibility.
        New clients should use /healthz instead.
    """
    return health_check()

@app.get("/models")
def list_models():
    """List available VL models."""
    return {
        "models": [
            {
                "name": name,
                "provider": info["provider"],
                "hf_id": info.get("hf_id"),
                "params": info.get("params"),
            }
            for name, info in VL_MODELS.items()
        ],
        "current": MODEL,
    }

@app.post("/vl/guide")
def vl_guide(body: GuideRequest):
    """
    Generate VL guidance for monitoring/diagnostics.

    Args:
        body: GuideRequest with task, images, logs, metrics

    Returns:
        Guidance response with analysis and recommendations
    """
    # Fetch images without calling fetch_b64 twice
    img_b64s = []
    for i in (body.images or []):
        b64 = fetch_b64(i)
        if b64:
            img_b64s.append(b64)

    sys_prompt = (
        "You are a vision-language monitoring agent. "
        "Given task context, images, and logs, diagnose problems and propose next actions. "
        "Answer in bullet points with short steps."
    )

    prompt = (
        f"{sys_prompt}\n"
        f"Task: {body.task}\n"
        f"Logs: {body.logs or []}\n"
        f"Metrics: {body.metrics or {}}"
    )

    try:
        if PROVIDER == "ollama":
            answer = ask_ollama(prompt, img_b64s)
        elif PROVIDER == "vllm":
            answer = ask_vllm(prompt, img_b64s)
        else:
            answer = ask_openai(prompt, img_b64s)

        return {
            "ok": True,
            "guidance": answer,
            "model": MODEL,
            "provider": PROVIDER,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "7072"))
    uvicorn.run(app, host="0.0.0.0", port=port)
