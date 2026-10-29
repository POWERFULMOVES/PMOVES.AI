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
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# In Docker, environment variables are injected via docker-compose.
# For local development, optionally load from env.shared via dotenv.
if not os.getenv("DOCKER_CONTAINER") and not os.getenv("DOCKER_ENV"):
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


def _dev_mode() -> bool:
    """Explicit developer signals only — absence of config proves nothing."""
    return (
        os.getenv('FLASK_ENV', '') == 'development'
        or os.getenv('TOKENISM_DEV', '') == '1'
    )


def _resolve_secret_key() -> str:
    """Resolve the Flask session key fail-closed, mode-aware.

    Fleet mode: SECRET_KEY is set (compose injects it from the secrets
    funnel; docker-compose.ui.yml gates it with ``${SECRET_KEY:?}``) — use
    it VERBATIM. No stripping: every byte of the value is part of the
    trust root, and silently altering it would invalidate live cookies.

    Dev mode: SECRET_KEY is absent AND an explicit dev signal is present
    (FLASK_ENV=development or TOKENISM_DEV=1) — mint an EPHEMERAL 64-hex
    key for this process. It is not persisted, so sessions and signed
    cookies do not survive a restart; that is loud by design.

    Anything else — production, or a bare ``docker run`` outside the
    compose gate — raises at config load rather than minting. Under
    multiple Gunicorn workers each worker would mint a DIFFERENT key and
    signed cookies would fail per-request; a restart would invalidate
    every cookie. The historical inline default was a public literal in
    this repository, which let anyone forge session cookies against any
    deployed instance, so there is no default and no silent fallback.
    """
    raw = os.getenv('SECRET_KEY')
    if raw is not None and raw.strip():
        return raw
    if _dev_mode():
        minted = secrets.token_hex(32)
        logger.warning(
            "SECRET_KEY not set: minted an EPHEMERAL session key "
            "(sessions/signed cookies will NOT survive restart). "
            "Set SECRET_KEY via the secrets funnel for fleet deployments."
        )
        return minted
    raise RuntimeError(
        "SECRET_KEY is not set and no dev-mode signal found "
        "(FLASK_ENV=development or TOKENISM_DEV=1). Refusing to mint an "
        "ephemeral session key outside dev mode: multi-worker deployments "
        "would diverge per worker and restarts would invalidate all "
        "sessions. Provide SECRET_KEY via the secrets funnel."
    )


@dataclass(frozen=True)
class NATSConfig:
    """NATS message bus configuration."""
    url: str = os.getenv('NATS_URL', 'nats://nats:4222')
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
    geometry_bus_url: str = os.getenv('GEOMETRY_BUS_URL', 'nats://nats:4222')
    cgp_version: str = os.getenv('CGP_VERSION', '1.0')


@dataclass(frozen=True)
class ServiceConfig:
    """Main service configuration."""
    host: str = os.getenv('TOKENISM_HOST', '0.0.0.0')
    port: int = int(os.getenv('TOKENISM_PORT', '8100'))
    debug: bool = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    secret_key: str = field(default_factory=_resolve_secret_key)

    # Sub-components
    nats: NATSConfig = NATSConfig()
    tensorzero: TensorZeroConfig = TensorZeroConfig()
    supabase: SupabaseConfig = SupabaseConfig()
    agentzero: AgentZeroConfig = AgentZeroConfig()
    chit: CHITConfig = CHITConfig()


# Global configuration instance
config = ServiceConfig()
