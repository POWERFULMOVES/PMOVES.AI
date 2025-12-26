"""
Service catalog for PMOVES.AI testing framework.

Provides single source of truth for all service definitions,
health check patterns, and metadata.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class HealthCheckType(Enum):
    """Types of health checks supported by services."""

    STANDARD = "/healthz"          # Most FastAPI/Flask services
    GRADIO = "/gradio_api/info"     # Gradio-based UI services
    QDRANT = "/readyz"              # Qdrant vector database
    MEILISEARCH = "/health"         # Meilisearch search engine
    POSTGRES = "pg_isready"         # PostgreSQL (subprocess check)
    NATS = "ping"                   # NATS monitoring endpoint
    NEO4J = "cypher-shell"          # Neo4j HTTP UI
    CONNECTION = "socket"           # Raw TCP socket check


@dataclass
class ServiceDefinition:
    """Definition of a PMOVES.AI service for testing."""

    name: str                       # Service name
    port: int                       # HTTP/TCP port
    health_path: str = "/healthz"   # HTTP path or check type
    health_type: HealthCheckType = HealthCheckType.STANDARD
    expected_fields: List[str] = field(default_factory=list)  # Expected JSON fields
    expected_status: int = 200      # Expected HTTP status
    timeout: float = 5.0            # Per-test timeout (seconds)
    profile: Optional[str] = None   # Docker compose profile
    dependencies: List[str] = field(default_factory=list)  # Dependent services
    gpu_required: bool = False      # Requires GPU
    description: str = ""           # Human-readable description


# ============================================================================
# AGENT COORDINATION & ORCHESTRATION
# ============================================================================

AGENT_ZERO = ServiceDefinition(
    name="agent-zero",
    port=8080,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "version", "timestamp"],
    profile="agents",
    dependencies=["postgres", "nats"],
    description="Agent orchestration service with embedded runtime",
)

ARCHON = ServiceDefinition(
    name="archon",
    port=8091,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "supabase_connected"],
    profile="agents",
    dependencies=["postgres", "agent-zero"],
    description="Supabase-driven agent service with prompt management",
)

MESH_AGENT = ServiceDefinition(
    name="mesh-agent",
    port=0,  # No HTTP interface
    health_type=HealthCheckType.CONNECTION,
    profile="agents",
    dependencies=["nats"],
    description="Distributed node announcer for multi-host orchestration",
)

DEEPRESEARCH = ServiceDefinition(
    name="deepresearch",
    port=8098,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    profile="orchestration",
    dependencies=["nats", "tensorzero-gateway"],
    description="LLM-based research planner (Alibaba Tongji)",
)

SUPASERCH = ServiceDefinition(
    name="supaserch",
    port=8099,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "metrics"],
    profile="orchestration",
    dependencies=["tensorzero-gateway", "deepresearch"],
    description="Multimodal holographic deep research orchestrator",
)

CONSCIOUSNESS_SERVICE = ServiceDefinition(
    name="consciousness-service",
    port=0,  # NATS worker only
    health_type=HealthCheckType.CONNECTION,
    profile="workers",
    dependencies=["nats"],
    description="Agent consciousness state management worker",
)

# ============================================================================
# LLM GATEWAY & OBSERVABILITY
# ============================================================================

TENSORZERO_GATEWAY = ServiceDefinition(
    name="tensorzero-gateway",
    port=3030,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "clickhouse_connected"],
    profile="orchestration",
    dependencies=["clickhouse"],
    description="Centralized LLM gateway for all model providers",
)

TENSORZERO_CLICKHOUSE = ServiceDefinition(
    name="tensorzero-clickhouse",
    port=8123,
    health_path="/ping",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["ok"],
    profile="orchestration",
    description="Observability metrics storage for TensorZero",
)

TENSORZERO_UI = ServiceDefinition(
    name="tensorzero-ui",
    port=4000,
    health_path="/",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="ui",
    dependencies=["tensorzero-gateway", "tensorzero-clickhouse"],
    description="TensorZero metrics dashboard and admin interface",
)

# ============================================================================
# RETRIEVAL & KNOWLEDGE SERVICES
# ============================================================================

HIRAG_V2 = ServiceDefinition(
    name="hi-rag-gateway-v2",
    port=8086,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "qdrant_connected", "neo4j_connected", "meilisearch_connected"],
    profile="orchestration",
    dependencies=["qdrant", "neo4j", "meilisearch", "tensorzero-gateway"],
    description="Next-gen hybrid RAG with cross-encoder reranking",
)

HIRAG_V2_GPU = ServiceDefinition(
    name="hi-rag-gateway-v2-gpu",
    port=8087,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="gpu",
    dependencies=["qdrant", "neo4j", "meilisearch"],
    gpu_required=True,
    description="GPU-accelerated Hi-RAG v2",
)

HIRAG_V1 = ServiceDefinition(
    name="hi-rag-gateway",
    port=8089,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="orchestration",
    dependencies=["qdrant", "neo4j", "meilisearch"],
    description="Legacy hybrid RAG implementation (v1)",
)

HIRAG_V1_GPU = ServiceDefinition(
    name="hi-rag-gateway-gpu",
    port=8110,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="gpu",
    dependencies=["qdrant", "neo4j", "meilisearch"],
    gpu_required=True,
    description="GPU-accelerated Hi-RAG v1",
)

# ============================================================================
# VOICE & SPEECH SERVICES
# ============================================================================

FLUTE_GATEWAY = ServiceDefinition(
    name="flute-gateway",
    port=8055,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "engines_available"],
    profile="tts",
    dependencies=["tensorzero-gateway"],
    description="Multimodal voice communication with Pipecat integration",
)

ULTIMATE_TTS_STUDIO = ServiceDefinition(
    name="ultimate-tts-studio",
    port=7861,
    health_path="/gradio_api/info",
    health_type=HealthCheckType.GRADIO,
    expected_fields=["version", "mode"],
    profile="gpu,tts",
    gpu_required=True,
    description="Multi-engine TTS with 7 engines (Kokoro, F5-TTS, etc.)",
)

GPU_ORCHESTRATOR = ServiceDefinition(
    name="gpu-orchestrator",
    port=0,  # No HTTP interface
    health_type=HealthCheckType.CONNECTION,
    profile="gpu",
    gpu_required=True,
    description="GPU model loading and orchestration service",
)

# ============================================================================
# MEDIA INGESTION & PROCESSING
# ============================================================================

PMOVES_YT = ServiceDefinition(
    name="pmoves-yt",
    port=8077,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="yt",
    dependencies=["minio", "nats"],
    description="YouTube ingestion service",
)

FFMPEG_WHISPER = ServiceDefinition(
    name="ffmpeg-whisper",
    port=8078,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "model_loaded"],
    profile="workers",
    dependencies=["minio"],
    gpu_required=True,
    description="Media transcription (OpenAI Whisper with GPU)",
)

MEDIA_VIDEO = ServiceDefinition(
    name="media-video",
    port=8079,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["minio", "supabase"],
    gpu_required=True,
    description="Object/frame analysis with YOLOv8",
)

MEDIA_AUDIO = ServiceDefinition(
    name="media-audio",
    port=8082,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["minio"],
    description="Audio analysis (emotion/speaker detection)",
)

EXTRACT_WORKER = ServiceDefinition(
    name="extract-worker",
    port=8083,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "qdrant_connected", "meilisearch_connected"],
    profile="workers",
    dependencies=["qdrant", "meilisearch", "tensorzero-gateway"],
    description="Text embedding & indexing service",
)

PDF_INGEST = ServiceDefinition(
    name="pdf-ingest",
    port=8092,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["minio", "extract-worker"],
    description="Document ingestion orchestrator",
)

LANGEXTRACT = ServiceDefinition(
    name="langextract",
    port=8084,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    description="Language detection and NLP preprocessing",
)

NOTEBOOK_SYNC = ServiceDefinition(
    name="notebook-sync",
    port=8095,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status", "surrealdb_connected"],
    profile="workers",
    dependencies=["extract-worker", "langextract"],
    description="SurrealDB Open Notebook synchronizer",
)

SESSION_CONTEXT_WORKER = ServiceDefinition(
    name="session-context-worker",
    port=0,  # NATS worker only
    health_type=HealthCheckType.CONNECTION,
    profile="workers",
    dependencies=["nats"],
    description="Session context management worker",
)

CHAT_RELAY = ServiceDefinition(
    name="chat-relay",
    port=0,  # NATS worker only
    health_type=HealthCheckType.CONNECTION,
    profile="workers",
    dependencies=["nats"],
    description="Chat message relay worker",
)

# ============================================================================
# UTILITY & INTEGRATION SERVICES
# ============================================================================

PRESIGN = ServiceDefinition(
    name="presign",
    port=8088,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["minio"],
    description="MinIO URL presigner for short-lived download URLs",
)

RENDER_WEBHOOK = ServiceDefinition(
    name="render-webhook",
    port=8085,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["supabase", "minio"],
    description="ComfyUI render callback handler",
)

PUBLISHER_DISCORD = ServiceDefinition(
    name="publisher-discord",
    port=8094,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["nats"],
    description="Discord notification bot",
)

JELLYFIN_BRIDGE = ServiceDefinition(
    name="jellyfin-bridge",
    port=8093,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="workers",
    dependencies=["supabase"],
    description="Jellyfin metadata webhook & helper",
)

CHANNEL_MONITOR = ServiceDefinition(
    name="channel-monitor",
    port=8097,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_fields=["status"],
    profile="yt",
    dependencies=["pmoves-yt", "nats"],
    description="External content watcher (YouTube channels, etc.)",
)

# ============================================================================
# DATA STORAGE
# ============================================================================

POSTGRES = ServiceDefinition(
    name="postgres",
    port=5432,
    health_path="pg_isready",
    health_type=HealthCheckType.POSTGRES,
    profile="data",
    description="PostgreSQL with pgvector extension",
)

POSTGREST = ServiceDefinition(
    name="postgrest",
    port=3010,
    health_path="/",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="data",
    dependencies=["postgres"],
    description="PostgREST API for Supabase",
)

QDRANT = ServiceDefinition(
    name="qdrant",
    port=6333,
    health_path="/readyz",
    health_type=HealthCheckType.QDRANT,
    expected_status=200,
    profile="data",
    description="Vector embeddings for semantic search",
)

NEO4J = ServiceDefinition(
    name="neo4j",
    port=7474,
    health_path="/",
    health_type=HealthCheckType.NEO4J,
    expected_status=200,
    profile="data",
    description="Knowledge graph storage",
)

MEILISEARCH = ServiceDefinition(
    name="meilisearch",
    port=7700,
    health_path="/health",
    health_type=HealthCheckType.MEILISEARCH,
    expected_status=200,
    profile="data",
    description="Full-text keyword search",
)

MINIO = ServiceDefinition(
    name="minio",
    port=9000,
    health_path="/minio/health/live",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="data",
    description="S3-compatible object storage",
)

NATS = ServiceDefinition(
    name="nats",
    port=4222,
    health_path="ping",
    health_type=HealthCheckType.NATS,
    profile="data",
    description="JetStream-enabled event broker",
)

# ============================================================================
# MONITORING STACK
# ============================================================================

PROMETHEUS = ServiceDefinition(
    name="prometheus",
    port=9090,
    health_path="/-/healthy",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="monitoring",
    description="Metrics scraping from all services",
)

GRAFANA = ServiceDefinition(
    name="grafana",
    port=3000,
    health_path="/api/health",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="monitoring",
    dependencies=["prometheus"],
    description="Dashboard visualization",
)

LOKI = ServiceDefinition(
    name="loki",
    port=3100,
    health_path="/readyz",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="monitoring",
    description="Centralized log aggregation",
)

CADVISOR = ServiceDefinition(
    name="cadvisor",
    port=8080,
    health_path="/healthz",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="monitoring",
    description="Container metrics for Prometheus",
)

# ============================================================================
# USER INTERFACE
# ============================================================================

PMOVES_UI = ServiceDefinition(
    name="pmoves-ui",
    port=3000,
    health_path="/",
    health_type=HealthCheckType.STANDARD,
    expected_status=200,
    profile="ui",
    dependencies=["agent-zero", "tensorzero-gateway", "hirag-v2"],
    description="PMOVES.AI web UI",
)

# ============================================================================
# SERVICE COLLECTIONS
# ============================================================================

# All services with HTTP/TCP endpoints
SERVICES = [
    AGENT_ZERO,
    ARCHON,
    DEEPRESEARCH,
    SUPASERCH,
    TENSORZERO_GATEWAY,
    TENSORZERO_CLICKHOUSE,
    TENSORZERO_UI,
    HIRAG_V2,
    HIRAG_V2_GPU,
    HIRAG_V1,
    HIRAG_V1_GPU,
    FLUTE_GATEWAY,
    ULTIMATE_TTS_STUDIO,
    PMOVES_YT,
    FFMPEG_WHISPER,
    MEDIA_VIDEO,
    MEDIA_AUDIO,
    EXTRACT_WORKER,
    PDF_INGEST,
    LANGEXTRACT,
    NOTEBOOK_SYNC,
    PRESIGN,
    RENDER_WEBHOOK,
    PUBLISHER_DISCORD,
    JELLYFIN_BRIDGE,
    CHANNEL_MONITOR,
    POSTGRES,
    POSTGREST,
    QDRANT,
    NEO4J,
    MEILISEARCH,
    MINIO,
    NATS,
    PROMETHEUS,
    GRAFANA,
    LOKI,
    CADVISOR,
    PMOVES_UI,
]

# Services without HTTP endpoints (NATS workers, internal services)
INTERNAL_SERVICES = [
    MESH_AGENT,
    CONSCIOUSNESS_SERVICE,
    GPU_ORCHESTRATOR,
    SESSION_CONTEXT_WORKER,
    CHAT_RELAY,
]

# GPU-required services
GPU_SERVICES = [s for s in SERVICES if s.gpu_required]

# Critical path services (dependency chain)
CRITICAL_PATH = [
    POSTGRES,
    POSTGREST,
    NATS,
    TENSORZERO_GATEWAY,
    AGENT_ZERO,
    HIRAG_V2,
]

# Services by profile
def get_services_by_profile(profile: str) -> List[ServiceDefinition]:
    """Get all services for a specific Docker Compose profile."""
    return [s for s in SERVICES if s.profile and profile in s.profile.split(",")]


def get_service_by_name(name: str) -> Optional[ServiceDefinition]:
    """Get service definition by name."""
    all_services = SERVICES + INTERNAL_SERVICES
    for service in all_services:
        if service.name == name:
            return service
    return None
