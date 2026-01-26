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
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Resolve env.shared path relative to this config file
# Config file is at: .../tokenism-simulator/config/__init__.py
# env.shared is at: pmoves/env.shared (3 levels up from config file)
_env_path = Path(__file__).resolve().parents[3] / "env.shared"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    logger.warning(f"Environment file not found: {_env_path}, using system environment")


@dataclass(frozen=True)
class NATSConfig:
    """NATS message bus configuration."""
    url: str = os.getenv('NATS_URL', 'nats://localhost:4222')
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
    url: str = os.getenv('TENSORZERO_URL', 'http://tensorzero-gateway:3030')
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
    geometry_bus_url: str = os.getenv('GEOMETRY_BUS_URL', 'nats://localhost:4222')
    cgp_version: str = os.getenv('CGP_VERSION', '0.2')


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
