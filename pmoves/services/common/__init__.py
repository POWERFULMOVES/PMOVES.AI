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

# New shared infrastructure modules (P4 extraction).
#
# Each import is wrapped independently in try/except so that CLI-only virtual
# environments (e.g., the pmoves tooling venv used by `brand_defaults.py`,
# `ensure_env_shared.py`, etc.) can `import pmoves.services.common` without
# needing every service-runtime dependency (fastapi, pydantic-settings,
# nats-py, structlog, ...). Service runtime containers install the full
# deps and get the complete surface; CLI tools degrade gracefully by
# skipping the helpers they don't need. Matches the existing try/except
# pattern used above for CHIT Geometry imports.

try:
    from .bootstrap import bootstrap_import_paths, ensure_import_paths  # noqa: F401
    __all__ += ["bootstrap_import_paths", "ensure_import_paths"]
except ImportError:
    pass

try:
    from .tensorzero import (  # noqa: F401
        tensorzero_openai_base,
        sync_openai_compat_env,
        check_tensorzero_connectivity,
    )
    __all__ += [
        "tensorzero_openai_base",
        "sync_openai_compat_env",
        "check_tensorzero_connectivity",
    ]
except ImportError:
    pass

try:
    from .model_fitness import (  # noqa: F401
        build_model_candidate_record,
        build_model_fitness_event,
        normalize_model_fitness,
        verify_agent_identity,
        require_trusted_agent_identity,
    )
    __all__ += [
        "build_model_candidate_record",
        "build_model_fitness_event",
        "normalize_model_fitness",
        "verify_agent_identity",
        "require_trusted_agent_identity",
    ]
except ImportError:
    pass

try:
    from .nats_client import (  # noqa: F401
        NatsConnectionConfig,
        create_nats_connection,
        nats_connection,
        DEFAULT_NATS_URL,
    )
    __all__ += [
        "NatsConnectionConfig",
        "create_nats_connection",
        "nats_connection",
        "DEFAULT_NATS_URL",
    ]
except ImportError:
    pass

try:
    from .health import (  # noqa: F401
        build_health_payload,
        create_health_endpoint,
        register_health_endpoint,
    )
    __all__ += [
        "build_health_payload",
        "create_health_endpoint",
        "register_health_endpoint",
    ]
except ImportError:
    pass

try:
    from .config import (  # noqa: F401
        BaseServiceSettings,
        TensorZeroSettings,
        env_bool,
    )
    __all__ += ["BaseServiceSettings", "TensorZeroSettings", "env_bool"]
except ImportError:
    pass

try:
    from .logging import (  # noqa: F401
        configure_structlog,
        get_logger,
        setup_logging,
    )
    __all__ += ["configure_structlog", "get_logger", "setup_logging"]
except ImportError:
    pass
