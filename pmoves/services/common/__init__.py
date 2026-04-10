"""
Shared utilities for PMOVES services.

The directory historically lacked an ``__init__`` making it a namespace package,
but explicit packaging helps downstream tooling and CI imports such as
``services.common.telemetry`` work reliably.

CHIT/Geometry modules:
    - geometry_models: Pydantic models for CGP v0.1/v0.2 structures
    - geometry_decoder: Unified CGP decoder with security features
    - shape_store: In-memory LRU cache for geometry packets
    - cgp_mappers: Health/finance data to CGP mappers
"""

from .telemetry import *  # noqa: F401,F403
from .model_nexus import (  # noqa: F401
    NexusConfigError,
    get_nexus_lane,
    get_nexus_provider,
    load_model_nexus,
    model_nexus_path,
    provider_allowed_for_lane,
    provider_requires_nexus_adapter,
)

# Ensure __all__ exists before extending (telemetry may not define it)
if '__all__' not in globals():
    __all__ = []

__all__ += [
    "NexusConfigError",
    "get_nexus_lane",
    "get_nexus_provider",
    "load_model_nexus",
    "model_nexus_path",
    "provider_allowed_for_lane",
    "provider_requires_nexus_adapter",
]

# CHIT Geometry exports (optional - graceful import)
try:
    from .geometry_models import (  # noqa: F401
        CGP_VERSION_V01,
        CGP_VERSION_V02,
        Point,
        Constellation,
        SuperNode,
        CGP,
        GeometryData,
        ValidationResult,
        TextFragment,
        DecodedGeometry,
        detect_cgp_version,
        cgp_dict_to_model,
    )
    from .geometry_decoder import (  # noqa: F401
        GeometryDecoder,
        decode_cgp,
        extract_text_from_cgp,
        validate_cgp,
        sign_cgp,
        verify_cgp,
        encrypt_anchor,
        decrypt_anchor,
        encrypt_anchors,
        decrypt_anchors,
    )
    __all__ += [
        "CGP_VERSION_V01",
        "CGP_VERSION_V02",
        "Point",
        "Constellation",
        "SuperNode",
        "CGP",
        "GeometryData",
        "ValidationResult",
        "TextFragment",
        "DecodedGeometry",
        "detect_cgp_version",
        "cgp_dict_to_model",
        "GeometryDecoder",
        "decode_cgp",
        "extract_text_from_cgp",
        "validate_cgp",
        "sign_cgp",
        "verify_cgp",
        "encrypt_anchor",
        "decrypt_anchor",
        "encrypt_anchors",
        "decrypt_anchors",
    ]
except Exception:  # pragma: no cover
    # Graceful fallback if dependencies unavailable
    pass

# New shared infrastructure modules (P4 extraction)
from .bootstrap import bootstrap_import_paths, ensure_import_paths  # noqa: F401
from .tensorzero import (  # noqa: F401
    tensorzero_openai_base,
    sync_openai_compat_env,
    check_tensorzero_connectivity,
)
from .nats_client import (  # noqa: F401
    NatsConnectionConfig,
    create_nats_connection,
    nats_connection,
    DEFAULT_NATS_URL,
)
from .health import (  # noqa: F401
    build_health_payload,
    create_health_endpoint,
    register_health_endpoint,
)
from .config import (  # noqa: F401
    BaseServiceSettings,
    TensorZeroSettings,
    env_bool,
)
from .logging import (  # noqa: F401
    configure_structlog,
    get_logger,
    setup_logging,
)

__all__ += [
    # bootstrap
    "bootstrap_import_paths",
    "ensure_import_paths",
    # tensorzero
    "tensorzero_openai_base",
    "sync_openai_compat_env",
    "check_tensorzero_connectivity",
    # nats_client
    "NatsConnectionConfig",
    "create_nats_connection",
    "nats_connection",
    "DEFAULT_NATS_URL",
    # health
    "build_health_payload",
    "create_health_endpoint",
    "register_health_endpoint",
    # config
    "BaseServiceSettings",
    "TensorZeroSettings",
    "env_bool",
    # logging
    "configure_structlog",
    "get_logger",
    "setup_logging",
]
