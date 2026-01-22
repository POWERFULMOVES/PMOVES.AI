#!/usr/bin/env python3
"""
PMOVES Model Registry Service - Dynamic Model Configuration

This service provides a Supabase-backed model registry for PMOVES.AI:
- Manages model providers (OpenAI, Anthropic, Ollama, vLLM, etc.)
- Tracks individual models with capabilities and resource requirements
- Generates TensorZero TOML configuration from database
- Syncs with GPU Orchestrator for deployment tracking
- Publishes model availability announcements via NATS

Architecture:
    Model Registry (8110)
        ├── Supabase (3010) - Model metadata storage
        ├── GPU Orchestrator (8200) - Deployment tracking
        ├── NATS (4222) - Model announcements
        └── TensorZero (3030) - Dynamic configuration
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://host.docker.internal:54321")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
PORT = int(os.environ.get("PORT", "8110"))
MODEL_REGISTRY_API_KEY = os.environ.get("MODEL_REGISTRY_API_KEY", "")

# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan.

    Yields control after startup, performs cleanup on shutdown.
    """
    # Startup
    logger.info("PMOVES Model Registry starting up...")
    logger.info(f"Supabase URL: {SUPABASE_URL}")
    logger.info(f"NATS URL: {NATS_URL}")
    yield
    # Shutdown
    logger.info("PMOVES Model Registry shutting down...")


app = FastAPI(
    title="PMOVES Model Registry",
    description="Dynamic model configuration service with Supabase backing",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    services: Dict[str, str]


class ModelProvider(BaseModel):
    """Model provider configuration."""
    id: Optional[str] = None
    name: str
    type: str = Field(pattern=r'^(openai_compatible|anthropic|ollama|vllm|custom)$')
    api_base: Optional[str] = None
    api_key_env_var: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class Model(BaseModel):
    """AI model definition."""
    id: Optional[str] = None
    provider_id: str
    name: str
    model_id: str
    model_type: str = Field(pattern=r'^(chat|embedding|reranker|vl|tts|audio|image)$')
    capabilities: List[str] = Field(default_factory=list)
    vram_mb: int = 0
    context_length: Optional[int] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True


class ModelAlias(BaseModel):
    """Model alias for UI-friendly naming."""
    model_id: str
    alias: str
    context: Optional[str] = None


class ServiceModelMapping(BaseModel):
    """Service-to-model mapping."""
    id: Optional[str] = None
    service_name: str
    function_name: str
    model_id: str
    variant_name: str
    priority: int = 5
    weight: float = 1.0
    fallback_model_id: Optional[str] = None


class ModelDeployment(BaseModel):
    """Model deployment on GPU node."""
    id: Optional[str] = None
    model_id: str
    node_id: str
    provider_type: str = Field(pattern=r'^(ollama|vllm|tts|custom)$')
    status: str = Field(pattern=r'^(loading|loaded|unloaded|error)$')
    vram_allocated_mb: Optional[int] = None
    error_message: Optional[str] = None


# ============================================================================
# Supabase Client
# ============================================================================

class SupabaseClient:
    """Simple Supabase client for model registry operations."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, table: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make a request to Supabase REST API."""
        url = f"{self.url}/rest/v1/{table}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, headers=self.headers, params=params)
            elif method == "POST":
                response = await client.post(url, headers=self.headers, json=data)
            elif method == "PUT":
                response = await client.put(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = await client.delete(url, headers=self.headers, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")

        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_detail = response.json().get("message", error_detail)
            except:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_detail)

        return response.json()

    async def get_active_models(self) -> List[Dict]:
        """Get all active models with provider details."""
        return await self._request("GET", "v_active_models")

    async def get_service_models(self, service: str, function: str = None) -> List[Dict]:
        """Get models mapped to a service."""
        params = {"service_name": service}
        if function:
            params["function_name"] = function
        return await self._request("GET", "v_service_models", params=params)

    async def get_model_by_id(self, model_id: str) -> Dict:
        """Get a single model by ID."""
        results = await self._request("GET", "models", params={"id": f"eq.{model_id}"})
        if results:
            return results[0]
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    async def create_provider(self, provider: ModelProvider) -> Dict:
        """Create a new model provider."""
        data = provider.model_dump(exclude_unset=True, exclude={"id"})
        return await self._request("POST", "model_providers", data=data)

    async def create_model(self, model: Model) -> Dict:
        """Create a new model."""
        data = model.model_dump(exclude_unset=True, exclude={"id"})
        return await self._request("POST", "models", data=data)

    async def create_alias(self, alias: ModelAlias) -> Dict:
        """Create a model alias."""
        data = alias.model_dump(exclude_unset=True)
        return await self._request("POST", "model_aliases", data=data)

    async def create_mapping(self, mapping: ServiceModelMapping) -> Dict:
        """Create a service-to-model mapping."""
        data = mapping.model_dump(exclude_unset=True, exclude={"id"})
        return await self._request("POST", "service_model_mappings", data=data)

    async def upsert_deployment(self, deployment: ModelDeployment) -> Dict:
        """Create or update a model deployment."""
        data = deployment.model_dump(exclude_unset=True, exclude={"id"})
        # Check if deployment exists
        try:
            existing = await self._request("GET", "model_deployments", params={
                "model_id": f"eq.{deployment.model_id}",
                "node_id": f"eq.{deployment.node_id}"
            })
            if existing:
                # Update existing
                return await self._request("PUT", f"model_deployments?id=eq.{existing[0]['id']}", data=data)
        except HTTPException:
            pass
        return await self._request("POST", "model_deployments", data=data)


# Global Supabase client
supabase = SupabaseClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ============================================================================
# TensorZero TOML Builder
# ============================================================================

class TensorZeroConfigBuilder:
    """Generate TensorZero TOML configuration from Supabase registry."""

    def __init__(self, supabase_client: SupabaseClient):
        self.supabase = supabase_client

    async def build_config(self) -> str:
        """Generate complete tensorzero.toml from Supabase."""
        lines = ["# Auto-generated from PMOVES Model Registry", ""]

        # Gateway section
        lines.extend([
            "[gateway]",
            "",
            "  [gateway.observability]",
            "  clickHouse_url = \"http://clickhouse:8123\"",
            "  clickHouse_table = \"tensorzero\"",
            "  clickHouse_username = \"tensorzero\"",
            "  clickHouse_password = \"tensorzero\"",
            ""
        ])

        # Fetch models from Supabase
        models = await self.supabase.get_active_models()

        # Group models by type
        chat_models = [m for m in models if m.get('model_type') == 'chat']
        embedding_models = [m for m in models if m.get('model_type') == 'embedding']

        # Generate chat model sections
        for model in chat_models:
            lines.extend(self._build_chat_model_section(model))

        # Generate embedding model sections
        for model in embedding_models:
            lines.extend(self._build_embedding_model_section(model))

        # Generate function sections from service mappings
        lines.extend(await self._build_function_sections())

        return "\n".join(lines)

    def _build_chat_model_section(self, model: Dict) -> List[str]:
        """Build TensorZero chat model section."""
        model_name = model['model_id'].replace(':', '_').replace('-', '_')
        provider_name = model['provider_type']
        api_base = model.get('api_base', '')
        model_id = model['model_id']

        lines = [
            f"[models.{model_name}]",
            'routing = ["' + provider_name + '"]',
            "",
            f"[models.{model_name}.providers.{provider_name}]",
        ]

        if provider_name == "ollama":
            lines.extend([
                'type = "openai"',
                f'api_base = "{api_base or "http://pmoves-ollama:11434"}"',
                f'model_name = "{model_id}"',
                'api_key_location = "none"',
            ])
        elif provider_name == "openai_compatible":
            lines.extend([
                'type = "openai"',
                f'api_base = "{api_base}"',
                f'model_name = "{model_id}"',
            ])
        elif provider_name == "anthropic":
            lines.extend([
                'type = "anthropic"',
                f'model_name = "{model_id}"',
            ])

        lines.extend(["", ""])
        return lines

    def _build_embedding_model_section(self, model: Dict) -> List[str]:
        """Build TensorZero embedding model section."""
        model_name = model['model_id'].replace(':', '_').replace('-', '_')
        provider_name = model['provider_type']
        api_base = model.get('api_base', '')
        model_id = model['model_id']

        lines = [
            f"[models.{model_name}]",
            'routing = ["' + provider_name + '"]',
            "",
            f"[models.{model_name}.providers.{provider_name}]",
        ]

        if provider_name == "ollama":
            lines.extend([
                'type = "openai"',
                f'api_base = "{api_base or "http://pmoves-ollama:11434"}"',
                f'model_name = "{model_id}"',
                'api_key_location = "none"',
            ])
        elif provider_name == "openai_compatible":
            lines.extend([
                'type = "openai"',
                f'api_base = "{api_base}"',
                f'model_name = "{model_id}"',
            ])

        lines.extend(["", ""])
        return lines

    async def _build_function_sections(self) -> List[str]:
        """Build TensorZero function sections from service mappings."""
        lines = []

        # Common function configurations for PMOVES
        functions = {
            "agent_zero": {
                "description": "Agent Zero orchestration - multi-agent coordination",
                "variants": ["fast", "balanced", "accurate"]
            },
            "deepresearch": {
                "description": "DeepResearch - complex research planning",
                "variants": ["local", "cloud"]
            },
            "coding": {
                "description": "Code generation and analysis",
                "variants": ["fast", "accurate"]
            },
            "embeddings": {
                "description": "Text embedding generation",
                "variants": ["default"]
            }
        }

        for function_name, config in functions.items():
            lines.extend([
                f"[functions.{function_name}]",
                f'description = "{config["description"]}"',
                "",
            ])

            # Add variants (will be populated from service mappings)
            for variant in config["variants"]:
                variant_key = f"{function_name}_{variant}" if variant != "default" else function_name
                lines.extend([
                    f"[functions.{function_name}.variants.{variant}]",
                    f'type = "chat:{variant_key}"',
                    f'weight = 1.0',
                    ""
                ])

            lines.append("")

        return lines


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        services={
            "supabase": SUPABASE_URL,
            "nats": NATS_URL
        }
    )


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "PMOVES Model Registry",
        "version": "1.0.0",
        "endpoints": {
            "healthz": "Health check",
            "models": "List all active models",
            "models/{id}": "Get model details",
            "services/{service}/models": "Get models for a service",
            "tensorzero/config": "Export TensorZero TOML configuration",
            "deployments": "List active GPU deployments"
        }
    }


@app.get("/api/models")
async def list_models(
    model_type: Optional[str] = None,
    provider: Optional[str] = None
):
    """List all active models with optional filtering."""
    models = await supabase.get_active_models()

    # Apply filters
    if model_type:
        models = [m for m in models if m.get('model_type') == model_type]
    if provider:
        models = [m for m in models if m.get('provider_type') == provider]

    return {"items": models, "count": len(models)}


@app.get("/api/models/{model_id}")
async def get_model(model_id: str):
    """Get a single model by ID."""
    return await supabase.get_model_by_id(model_id)


@app.get("/api/services/{service}/models")
async def get_service_models(service: str, function: Optional[str] = None):
    """Get models mapped to a service."""
    return await supabase.get_service_models(service, function)


@app.get("/api/tensorzero/config")
async def get_tensorzero_config():
    """Generate TensorZero TOML configuration from Supabase."""
    from fastapi.responses import Response

    builder = TensorZeroConfigBuilder(supabase)
    config = await builder.build_config()

    return Response(
        content=config,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=tensorzero.toml"}
    )


@app.get("/api/deployments")
async def list_deployments(
    node_id: Optional[str] = None,
    status: Optional[str] = None
):
    """List model deployments with optional filtering."""
    # Query active deployments view
    deployments = await supabase._request("GET", "v_active_deployments")

    # Apply filters
    if node_id:
        deployments = [d for d in deployments if node_id in d.get('node_id', '')]
    if status:
        deployments = [d for d in deployments if d.get('status') == status]

    return {"items": deployments, "count": len(deployments)}


@app.post("/api/deployments")
async def register_deployment(deployment: ModelDeployment):
    """Register or update a model deployment (called by GPU Orchestrator)."""
    return await supabase.upsert_deployment(deployment)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
