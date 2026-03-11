"""
PMOVES Tokenism Simulator Configuration

Implements PMOVES.AI integration patterns:
- NATS message bus for event coordination
- TensorZero for LLM-based analysis
- Supabase for data persistence
- Prometheus metrics for observability
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# In Docker, environment variables are injected via docker-compose.
# For local development, optionally load from env.shared via dotenv.
if not os.getenv("DOCKER_CONTAINER"):
    try:
        from dotenv import load_dotenv
        # Walk up from config/__init__.py looking for env.shared
        _config_dir = Path(__file__).resolve().parent
        for _ancestor in _config_dir.parents:
            _env_path = _ancestor / "env.shared"
            if _env_path.exists():
                load_dotenv(_env_path)
                logger.info("Loaded environment from %s", _env_path)
                break
        else:
            logger.debug("No env.shared found in parent directories, using system environment")
    except ImportError:
        logger.debug("python-dotenv not installed, using system environment")


@dataclass(frozen=True)
class NATSConfig:
    """NATS message bus configuration."""
    url: str = os.getenv('NATS_URL', 'nats://nats:pmoves@nats:4222')
    client_name: str = os.getenv('NATS_CLIENT_NAME', 'tokenism-simulator')
    jetstream_enabled: bool = os.getenv('NATS_JETSTREAM', 'true').lower() == 'true'

    # Subjects we publish to
    simulation_result_subject: str = 'tokenism.simulation.result.v1'
    calibration_result_subject: str = 'tokenism.calibration.result.v1'
    cgp_ready_subject: str = 'tokenism.cgp.ready.v1'

    # Subjects we subscribe to
    deepresearch_request: str = 'research.deepresearch.request.v1'
    supaserch_request: str = 'supaserch.request.v1'
    agentzero_task: str = 'agentzero.task.v1'


@dataclass(frozen=True)
class TensorZeroConfig:
    """TensorZero LLM gateway configuration."""
    url: str = os.getenv('TENSORZERO_URL', 'http://tensorzero-gateway:3000')
    model: str = os.getenv('TENSORZERO_MODEL', 'claude-sonnet-4-5')
    timeout: int = int(os.getenv('TENSORZERO_TIMEOUT', '30'))


@dataclass(frozen=True)
class SupabaseConfig:
    """Supabase configuration for data persistence."""
    url: str = os.getenv('SUPABASE_URL', 'http://supabase_kong_PMOVES.AI:8000')
    key: str = os.getenv('SUPABASE_ANON_KEY', '')
    jwt_secret: str = os.getenv('SUPABASE_JWT_SECRET', '')
    pool_size: int = int(os.getenv('SUPABASE_POOL_SIZE', '10'))


@dataclass(frozen=True)
class AgentZeroConfig:
    """Agent Zero MCP integration configuration."""
    url: str = os.getenv('AGENTZERO_URL', 'http://agent-zero:8080')
    mcp_enabled: bool = os.getenv('AGENTZERO_MCP_ENABLED', 'true').lower() == 'true'
    mcp_token: str = os.getenv('AGENTZERO_MCP_TOKEN', '')


@dataclass(frozen=True)
class CHITConfig:
    """CHIT/Geometry Bus configuration."""
    enabled: bool = os.getenv('CHIT_ENABLED', 'true').lower() == 'true'
    geometry_bus_url: str = os.getenv('GEOMETRY_BUS_URL', 'nats://nats:pmoves@nats:4222')
    cgp_version: str = os.getenv('CGP_VERSION', '1.0')


@dataclass(frozen=True)
class ServiceConfig:
    """Main service configuration."""
    host: str = os.getenv('TOKENISM_HOST', '0.0.0.0')
    port: int = int(os.getenv('TOKENISM_PORT', '8100'))
    debug: bool = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    secret_key: str = os.getenv('SECRET_KEY', 'pmoves-tokenism-secret')

    # Sub-components
    nats: NATSConfig = NATSConfig()
    tensorzero: TensorZeroConfig = TensorZeroConfig()
    supabase: SupabaseConfig = SupabaseConfig()
    agentzero: AgentZeroConfig = AgentZeroConfig()
    chit: CHITConfig = CHITConfig()


# Global configuration instance
config = ServiceConfig()
