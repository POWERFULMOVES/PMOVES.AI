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

# Ensure __all__ exists before extending (telemetry may not define it)
if '__all__' not in globals():
    __all__ = []

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
