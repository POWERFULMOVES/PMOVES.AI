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

import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, Field
import uvicorn

from hf_client import (
    fetch_model_info,
    fetch_model_config,
    parse_embedding_dimensions,
    parse_model_summary,
)

_HERE = Path(__file__).resolve()
for _path in _HERE.parents:
    if not (_path / "pmoves").is_dir():
        continue
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
    break

from pmoves.services.common.events import validate_payload  # noqa: E402
from pmoves.services.common.model_fitness import (  # noqa: E402
    build_model_fitness_event,
    require_trusted_agent_identity,
)

try:
    from nats.aio.client import Client as NATS
    from nats.aio.errors import ErrConnectionClosed, ErrTimeout
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False

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
    global nats_client

    # Startup
    logger.info("PMOVES Model Registry starting up...")
    logger.info(f"Supabase URL: {SUPABASE_URL}")
    logger.info(f"NATS URL: {NATS_URL}")

    # Connect to NATS for GPU event sync + catalog change publishing
    nats_client = RegistryNatsClient(NATS_URL, supabase)
    connected = await nats_client.connect()
    if not connected:
        logger.warning("Running without NATS — deployment sync disabled")

    yield

    # Shutdown
    logger.info("PMOVES Model Registry shutting down...")
    if nats_client:
        await nats_client.disconnect()


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


class ModelCandidateRecord(BaseModel):
    """HuggingFace/autoresearch candidate waiting for validation."""

    id: Optional[str] = None
    model_id: str
    hf_id: str
    task: Optional[str] = None
    license: Optional[str] = None
    params: Optional[int] = None
    context_length: Optional[int] = None
    capabilities: List[str] = Field(default_factory=list)
    backend_fit: List[str] = Field(default_factory=list)
    vram_mb_estimate: Optional[int] = None
    quantization_support: List[str] = Field(default_factory=list)
    intended_lane: str = "agent_mesh"
    validation_status: str = Field(default="candidate", pattern=r'^(candidate|validated|rejected|activated)$')
    source: str = "huggingface"
    agent_id: str = "codex"
    signed_trail_ref: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelFitnessRequest(BaseModel):
    """Input for normalized model-fitness recording."""

    model_id: str
    source: str = Field(pattern=r'^(tensorzero|pinokio|unsloth|hf-autoresearch|evoswarm|manual)$')
    lane: str
    tensorzero_metrics: Dict[str, Any] = Field(default_factory=dict)
    training_metrics: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = None
    agent_id: str


class ModelFitnessRecord(BaseModel):
    """Persisted model-fitness scorecard event."""

    model_id: str
    source: str
    lane: str
    score: float = Field(ge=0, le=1)
    metrics: Dict[str, Any]
    run_id: str
    timestamp: str
    agent_id: str
    signature: Dict[str, Any]


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

    async def create_model_candidate(self, candidate: ModelCandidateRecord) -> Dict:
        """Persist or merge a model candidate record."""
        data = candidate.model_dump(exclude_unset=True, exclude={"id"})
        headers = {
            **self.headers,
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        url = f"{self.url}/rest/v1/model_candidates?on_conflict=hf_id,intended_lane"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=data)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

    async def create_model_fitness_record(self, record: ModelFitnessRecord) -> Dict:
        """Persist a normalized model-fitness event."""
        data = {
            "model_id": record.model_id,
            "source": record.source,
            "lane": record.lane,
            "score": record.score,
            "metrics": record.metrics,
            "run_id": record.run_id,
            "agent_id": record.agent_id,
            "signature": record.signature,
            "recorded_at": record.timestamp,
        }
        return await self._request("POST", "model_fitness_records", data=data)


# Global Supabase client
supabase = SupabaseClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ============================================================================
# NATS Integration
# ============================================================================

class RegistryNatsClient:
    """NATS client for model registry — subscribes to GPU events, publishes catalog changes."""

    # Subjects we subscribe to (from gpu-orchestrator + pipeline sources)
    SUB_MODEL_LOADED = "mesh.gpu.model.loaded.v1"
    SUB_MODEL_UNLOADED = "mesh.gpu.model.unloaded.v1"
    SUB_HF_EVALUATED = "hf.model.evaluated.v1"          # G4: from hf-research-agent
    SUB_AGENTGYM_PUBLISHED = "agentgym.model.published.v1"  # G5: from agentgym-rl-coordinator

    # Subject we publish on catalog mutations
    PUB_REGISTRY_UPDATED = "model.registry.updated.v1"
    PUB_MODEL_FITNESS_RECORDED = "model.fitness.recorded.v1"

    def __init__(self, nats_url: str, supabase_client: SupabaseClient):
        self.nats_url = nats_url
        self.supabase = supabase_client
        self._nc: Optional[NATS] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to NATS and set up subscriptions."""
        if not NATS_AVAILABLE:
            logger.warning("NATS library not available — running without NATS")
            return False
        try:
            self._nc = NATS()
            await self._nc.connect(
                servers=[self.nats_url],
                reconnect_time_wait=2,
                max_reconnect_attempts=-1,
            )
            self._connected = True
            logger.info(f"Model Registry connected to NATS at {self.nats_url}")

            # Subscribe to GPU orchestrator events
            await self._nc.subscribe(self.SUB_MODEL_LOADED, cb=self._on_model_loaded)
            await self._nc.subscribe(self.SUB_MODEL_UNLOADED, cb=self._on_model_unloaded)
            logger.info("Subscribed to mesh.gpu.model.{loaded,unloaded}.v1")

            # G4: Subscribe to HF research evaluations (auto-register high-scoring candidates)
            await self._nc.subscribe(self.SUB_HF_EVALUATED, cb=self._on_hf_evaluated)
            logger.info("Subscribed to hf.model.evaluated.v1 (G4 pipeline link)")

            # G5: Subscribe to AgentGym model publications (register RL-trained models)
            await self._nc.subscribe(self.SUB_AGENTGYM_PUBLISHED, cb=self._on_agentgym_published)
            logger.info("Subscribed to agentgym.model.published.v1 (G5 pipeline link)")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Gracefully disconnect from NATS."""
        if self._nc and self._connected:
            try:
                await self._nc.drain()
            except Exception as e:
                logger.warning(f"Error draining NATS connection: {e}")
        self._connected = False
        logger.info("Model Registry disconnected from NATS")

    async def publish_catalog_change(
        self, action: str, resource_type: str, resource_id: str
    ) -> None:
        """Publish a catalog change event to NATS."""
        if not self._nc or not self._connected:
            logger.warning(
                f"NATS disconnected — catalog change notification dropped: "
                f"{action} {resource_type}/{resource_id}"
            )
            return
        try:
            payload = json.dumps({
                "type": self.PUB_REGISTRY_UPDATED,
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }).encode()
            await self._nc.publish(self.PUB_REGISTRY_UPDATED, payload)
        except Exception as e:
            logger.error(f"Error publishing catalog change: {e}")

    async def publish_model_fitness(self, event: Dict[str, Any]) -> None:
        """Publish a signed model.fitness.recorded.v1 payload."""
        if not self._nc or not self._connected:
            logger.warning(
                "NATS disconnected — model fitness notification dropped: "
                f"{event.get('model_id')}/{event.get('run_id')}"
            )
            return
        try:
            await self._nc.publish(
                self.PUB_MODEL_FITNESS_RECORDED,
                json.dumps(event).encode(),
            )
        except Exception as e:
            logger.error(f"Error publishing model fitness: {e}")

    async def _on_model_loaded(self, msg) -> None:
        """Handle mesh.gpu.model.loaded.v1 — upsert deployment as loaded."""
        try:
            data = json.loads(msg.data.decode())
            model_key = data.get("model_key", "")
            vram_mb = data.get("vram_mb", 0)

            # model_key format: "provider/model_id"
            parts = model_key.split("/", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid model_key format: {model_key}")
                return

            provider, model_id = parts
            deployment = ModelDeployment(
                model_id=model_id,
                node_id="gpu-orchestrator",
                provider_type=provider,
                status="loaded",
                vram_allocated_mb=vram_mb,
            )
            await self.supabase.upsert_deployment(deployment)
            logger.info(f"Deployment synced: {model_key} -> loaded ({vram_mb}MB)")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Malformed NATS message on {self.SUB_MODEL_LOADED}: {e}")
        except Exception as e:
            logger.error(f"Error handling model loaded event: {e}", exc_info=True)

    async def _on_model_unloaded(self, msg) -> None:
        """Handle mesh.gpu.model.unloaded.v1 — update deployment to unloaded."""
        try:
            data = json.loads(msg.data.decode())
            model_key = data.get("model_key", "")

            parts = model_key.split("/", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid model_key format: {model_key}")
                return

            provider, model_id = parts
            deployment = ModelDeployment(
                model_id=model_id,
                node_id="gpu-orchestrator",
                provider_type=provider,
                status="unloaded",
                vram_allocated_mb=0,
            )
            await self.supabase.upsert_deployment(deployment)
            logger.info(f"Deployment synced: {model_key} -> unloaded")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Malformed NATS message on {self.SUB_MODEL_UNLOADED}: {e}")
        except Exception as e:
            logger.error(f"Error handling model unloaded event: {e}", exc_info=True)

    async def _on_hf_evaluated(self, msg) -> None:
        """Handle hf.model.evaluated.v1 — G4: auto-register high-scoring candidates.

        The hf-research-agent scores models by downloads/likes/tags.
        If score exceeds threshold, register as a candidate.
        """
        try:
            data = json.loads(msg.data.decode())
            model_id = data.get("model_id") or data.get("id") or ""
            score = float(data.get("score") or 0)

            if not model_id or score < 50:
                return

            lane = data.get("lane", "chat")
            logger.info(f"G4: registering candidate {model_id} (score={score})")

            await self.supabase.create_model_candidate(ModelCandidateRecord(
                hf_id=model_id,
                model_id=model_id,
                source="hf-autoresearch",
                lane=lane,
                intended_lane=lane,
                pipeline_tag="text-generation",
                validation_status="candidate",
                metadata={
                    "hf_score": score,
                    "downloads": data.get("downloads"),
                    "likes": data.get("likes"),
                    "tags": data.get("tags"),
                    "reasons": data.get("reasons"),
                },
            ))
            await self.publish_catalog_change("create", "model_candidate", model_id)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Malformed NATS message on {self.SUB_HF_EVALUATED}: {e}")
        except Exception as e:
            logger.error(f"Error handling hf.model.evaluated event: {e}", exc_info=True)

    async def _on_agentgym_published(self, msg) -> None:
        """Handle agentgym.model.published.v1 — G5: register RL-trained models.

        The agentgym-rl-coordinator publishes models to HF Hub after RL training.
        Register them as candidates and record initial training fitness.
        """
        try:
            data = json.loads(msg.data.decode())
            # Codex P1: AgentGym publishes model_id, dataset_id, repo_url
            # (not hf_id or model_repo)
            hf_id = data.get("hf_id") or data.get("repo_url") or ""
            model_id = data.get("model_id") or ""
            if not hf_id and model_id:
                hf_id = model_id
            if not hf_id:
                return

            logger.info(f"G5: registering RL-trained candidate {hf_id}")

            await self.supabase.upsert_model_candidate(
                hf_id=hf_id,
                lane="agentgym",
                source="evoswarm",
                status="candidate",
                metadata={
                    "training_id": data.get("training_id") or data.get("run_id"),
                    "mean_reward": data.get("mean_reward"),
                    "mean_reward_normalized": data.get("mean_reward_normalized"),
                    "episodes": data.get("episodes"),
                    "training_metrics": data.get("training_metrics"),
                },
            )
            await self.publish_catalog_change("create", "model_candidate", hf_id)

            # Record initial fitness from training if present
            if data.get("mean_reward_normalized"):
                score = max(0.0, min(1.0, float(data["mean_reward_normalized"])))
                await self.supabase.create_model_fitness_record({
                    "model_id": hf_id,
                    "source": "evoswarm",
                    "lane": "agentgym",
                    "score": score,
                    "run_id": data.get("training_id") or data.get("run_id"),
                })
                logger.info(f"G5: initial fitness for {hf_id}: score={score:.3f}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Malformed NATS message on {self.SUB_AGENTGYM_PUBLISHED}: {e}")
        except Exception as e:
            logger.error(f"Error handling agentgym.model.published event: {e}", exc_info=True)


# Global NATS client
nats_client: Optional[RegistryNatsClient] = None


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
                    'weight = 1.0',
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
            "models/{id}/enrich-hf": "Enrich model from HuggingFace metadata",
            "models/enrich-hf-bulk": "Batch-enrich all models with hf_id",
            "model-candidates": "Register signed HF/autoresearch model candidates",
            "model-fitness": "Record normalized TensorZero/Pinokio/Unsloth fitness",
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
    result = await supabase.upsert_deployment(deployment)
    if nats_client:
        await nats_client.publish_catalog_change(
            "updated", "deployment", deployment.model_id
        )
    return result


@app.post("/api/model-candidates")
async def register_model_candidate(candidate: ModelCandidateRecord):
    """Register a signed model candidate from HF/autoresearch."""
    try:
        identity = require_trusted_agent_identity(candidate.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not candidate.signed_trail_ref:
        raise HTTPException(
            status_code=400,
            detail="signed_trail_ref is required before candidate persistence",
        )
    result = await supabase.create_model_candidate(candidate)
    if nats_client:
        await nats_client.publish_catalog_change(
            "candidate_registered",
            "model_candidate",
            candidate.hf_id,
        )
    return {"identity": identity.to_dict(), "items": result}


@app.post("/api/model-fitness", response_model=ModelFitnessRecord)
async def record_model_fitness(request: ModelFitnessRequest):
    """Record a signed model fitness scorecard."""
    try:
        require_trusted_agent_identity(request.agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    event = build_model_fitness_event(
        model_id=request.model_id,
        source=request.source,
        lane=request.lane,
        tensorzero_metrics=request.tensorzero_metrics,
        training_metrics=request.training_metrics,
        run_id=request.run_id,
        agent_id=request.agent_id,
    )
    try:
        validate_payload("model.fitness.recorded.v1", event)
    except JsonSchemaValidationError as exc:
        logger.warning("model.fitness.recorded.v1 validation failed: %s", exc)
        raise HTTPException(status_code=422, detail=f"Invalid model fitness event: {exc}") from exc
    record = ModelFitnessRecord(**event)
    await supabase.create_model_fitness_record(record)
    if nats_client:
        await nats_client.publish_model_fitness(event)
    return record


# ============================================================================
# HuggingFace Enrichment Endpoints
# ============================================================================

@app.post("/api/models/{model_id}/enrich-hf")
async def enrich_from_huggingface(model_id: str):
    """Fetch model card metadata from HuggingFace and update registry.

    Looks up the model in Supabase, resolves its hf_id from metadata,
    fetches HF API data, and merges enrichment back into the record.
    """
    # 1. Get model from Supabase
    model = await supabase.get_model_by_id(model_id)
    metadata = model.get("metadata") or {}
    hf_id = metadata.get("hf_id")

    if not hf_id:
        raise HTTPException(
            status_code=400,
            detail=f"Model {model_id} has no hf_id in metadata. Set metadata.hf_id first.",
        )

    # 2. Fetch from HuggingFace
    try:
        hf_info = await fetch_model_info(hf_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"HuggingFace API error for {hf_id}: {e.response.status_code}",
        )

    enrichment = parse_model_summary(hf_info)

    # 3. Try to get config.json for dimensions
    hf_config = await fetch_model_config(hf_id)
    if hf_config:
        dims = parse_embedding_dimensions(hf_config)
        if dims:
            enrichment["dimensions"] = dims

    # 4. Merge into existing metadata and update Supabase
    merged = {**enrichment, **metadata}
    await supabase._request(
        "PUT",
        f"models?id=eq.{model_id}",
        data={"metadata": merged},
    )

    # 5. Publish catalog change
    if nats_client:
        await nats_client.publish_catalog_change("enriched", "model", model_id)

    logger.info(f"Enriched model {model_id} from HuggingFace ({hf_id})")
    return {
        "model_id": model_id,
        "hf_id": hf_id,
        "enrichment": enrichment,
    }


@app.post("/api/models/enrich-hf-bulk")
async def enrich_all_from_huggingface(
    model_type: Optional[str] = Query(default="embedding", description="Filter by model type"),
):
    """Batch-enrich all models that have hf_id in metadata."""
    models = await supabase.get_active_models()

    if model_type:
        models = [m for m in models if m.get("model_type") == model_type]

    results = {"enriched": [], "skipped": [], "failed": []}

    for model in models:
        model_id = model.get("id")
        metadata = model.get("metadata") or {}
        hf_id = metadata.get("hf_id")

        if not hf_id:
            results["skipped"].append({"id": model_id, "name": model.get("name"), "reason": "no hf_id"})
            continue

        try:
            hf_info = await fetch_model_info(hf_id)
            enrichment = parse_model_summary(hf_info)

            hf_config = await fetch_model_config(hf_id)
            if hf_config:
                dims = parse_embedding_dimensions(hf_config)
                if dims:
                    enrichment["dimensions"] = dims

            merged = {**enrichment, **metadata}
            await supabase._request(
                "PUT",
                f"models?id=eq.{model_id}",
                data={"metadata": merged},
            )

            results["enriched"].append({"id": model_id, "hf_id": hf_id, "dimensions": enrichment.get("dimensions")})
            logger.info(f"Enriched {model.get('name')} from HF ({hf_id})")
        except Exception as e:
            results["failed"].append({"id": model_id, "hf_id": hf_id, "error": str(e)})
            logger.warning(f"Failed to enrich {model.get('name')}: {e}")

    if nats_client and results["enriched"]:
        await nats_client.publish_catalog_change("bulk_enriched", "models", str(len(results["enriched"])))

    return results


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT)
