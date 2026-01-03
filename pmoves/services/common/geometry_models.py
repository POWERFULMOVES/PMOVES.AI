"""Pydantic models for CHIT Geometry Packets (CGP).

Provides type-safe models for CGP v0.1 and v0.2 structures. These models
are shared across services for consistent CGP handling.

See Also:
    - geometry_decoder.py: Unified CGP decoder using these models
    - pmoves/docs/PMOVESCHIT/PMOVESCHIT.md: Core CHIT specification
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, ValidationError, field_validator


# ============================================================================
# Version Detection
# ============================================================================

CGP_VERSION_V01 = "chit.cgp.v0.1"
CGP_VERSION_V02 = "chit.cgp.v0.2"
SUPPORTED_VERSIONS = {CGP_VERSION_V01, CGP_VERSION_V02}


# ============================================================================
# Core CGP Models (v0.1 structure with v0.2 extensions)
# ============================================================================

class Point(BaseModel):
    """A single point in geometric space.

    May represent:
    - A 2D point in the Poincaré disk (x, y)
    - A projected value (proj)
    - A text fragment with confidence
    - A reference to source content
    """

    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    proj: Optional[float] = None
    conf: Optional[float] = None
    text: Optional[str] = None
    text_b64: Optional[str] = Field(default=None, description="Base64-encoded text")
    source_ref: Optional[str] = Field(default=None, alias="source_ref")
    magnitude: float = 1.0
    anchor: Optional[List[float]] = Field(default=None, description="3D anchor vector")


class Constellation(BaseModel):
    """A collection of points with geometric metadata.

    Represents a cluster of related points in geometric space, with
    spectral characteristics and optional anchor for positioning.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    label: Optional[str] = None
    kind: Optional[str] = "default"
    anchor: Optional[List[float]] = Field(default=None, description="3D anchor vector")
    anchor_enc: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Encrypted anchor (AES-GCM)"
    )
    summary: Optional[str] = None
    radial_minmax: List[float] = Field(default_factory=lambda: [0.0, 1.0])
    spectrum: List[float] = Field(default_factory=lambda: [1.0])
    points: List[Point] = Field(default_factory=list)

    @field_validator("radial_minmax")
    @classmethod
    def validate_radial_minmax(cls, v: List[float]) -> List[float]:
        """Validate radial_minmax has exactly 2 elements with min <= max."""
        if len(v) != 2:
            raise ValueError("radial_minmax must have exactly 2 elements [min, max]")
        if v[0] > v[1]:
            raise ValueError(f"radial_minmax min must be <= max: got [{v[0]}, {v[1]}]")
        return v

    @field_validator("spectrum")
    @classmethod
    def normalize_spectrum(cls, v: List[float]) -> List[float]:
        """Normalize spectrum to sum to 1.0."""
        if not v:
            return [1.0]
        total = sum(v)
        if total > 0:
            return [x / total for x in v]
        # Return uniform distribution if all zeros
        return [1.0 / len(v)]


class SuperNode(BaseModel):
    """A super-node containing constellations.

    Represents a high-level grouping in the geometric hierarchy,
    such as a document, topic, or domain.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    label: Optional[str] = None
    summary: Optional[str] = None
    constellations: List[Constellation] = Field(default_factory=list)


class Attribution(BaseModel):
    """v0.2 attribution metadata.

    Contains Dirichlet weights for contribution tracking and
    optional Merkle proof for verification.
    """

    model_config = ConfigDict(extra="allow")

    dirichlet_weights: Optional[List[float]] = None
    merkle_proof: Optional[str] = None
    participants: Optional[List[str]] = None


class CGPSignature(BaseModel):
    """HMAC signature for CGP verification."""

    model_config = ConfigDict(extra="allow")

    hmac: Optional[str] = Field(default=None, description="Base64-encoded HMAC")
    algorithm: str = "sha256"
    timestamp: Optional[int] = None


class CGPMeta(BaseModel):
    """CGP metadata section."""

    model_config = ConfigDict(extra="allow")

    namespace: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    encoder: Optional[str] = None
    count: Optional[int] = None
    version: Optional[str] = Field(default=None, description="CGP version override")


class CGP(BaseModel):
    """CHIT Geometry Packet (CGP) - unified model for v0.1 and v0.2.

    The CGP is the core data structure for CHIT protocol, encoding
    geometric information with optional attribution and signatures.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    spec: str = Field(default=CGP_VERSION_V01, description="CGP spec version")
    meta: Dict[str, Any] = Field(default_factory=dict)
    super_nodes: List[SuperNode] = Field(default_factory=list)
    sig: Optional[CGPSignature] = Field(default=None, alias="sig")
    attribution: Optional[Attribution] = None

    @field_validator("spec")
    @classmethod
    def validate_spec(cls, v: str) -> str:
        """Validate CGP spec version is supported."""
        if v not in SUPPORTED_VERSIONS and not v.startswith("chit.cgp.v"):
            raise ValueError(f"Unsupported CGP spec: {v}")
        return v


# ============================================================================
# Geometry Data Models
# ============================================================================

class GeometryData(BaseModel):
    """Extracted geometric information from CGP."""

    model_config = ConfigDict(extra="allow")

    version: str
    num_super_nodes: int
    num_constellations: int
    num_points: int
    has_attribution: bool
    has_signature: bool
    anchors: List[List[float]] = Field(default_factory=list)
    spectrum_summary: Dict[str, List[float]] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Result of CGP validation."""

    model_config = ConfigDict(extra="allow")

    valid: bool
    version: str
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    has_signature: bool = False
    signature_valid: Optional[bool] = None


class TextFragment(BaseModel):
    """Extracted text fragment from CGP."""

    model_config = ConfigDict(extra="allow")

    text: str
    confidence: Optional[float] = None
    super_node: Optional[str] = None
    constellation: Optional[str] = None
    constellation_id: Optional[str] = None
    point_id: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None


class DecodedGeometry(BaseModel):
    """Result of decoding a CGP."""

    model_config = ConfigDict(extra="allow")

    version: str
    geometry: GeometryData
    text_fragments: List[TextFragment] = Field(default_factory=list)
    validation: ValidationResult
    raw_cgp: Dict[str, Any]


# ============================================================================
# Helper Functions
# ============================================================================

def detect_cgp_version(cgp: Dict[str, Any] | CGP) -> str:
    """Auto-detect CGP version from structure.

    Args:
        cgp: CGP data (dict or CGP model)

    Returns:
        Detected version string (e.g., "chit.cgp.v0.1")

    Examples:
        >>> detect_cgp_version({"spec": "chit.cgp.v0.1", ...})
        'chit.cgp.v0.1'
        >>> detect_cgp_version({"version": "0.2", "attribution": {...}})
        'chit.cgp.v0.2'
    """
    if isinstance(cgp, CGP):
        return cgp.spec

    # Check explicit spec field
    spec = cgp.get("spec", "")
    if spec and spec.startswith("chit.cgp.v"):
        return spec

    # Check meta version
    meta = cgp.get("meta", {}) or {}
    if isinstance(meta, dict):
        version = meta.get("version")
        if version:
            return f"chit.cgp.v{version}"

    # Check for v0.2 attribution field
    if cgp.get("attribution") is not None:
        return CGP_VERSION_V02

    # Default to v0.1 if super_nodes present
    if cgp.get("super_nodes"):
        return CGP_VERSION_V01

    # Unknown format
    return "unknown"


def cgp_dict_to_model(cgp: Dict[str, Any]) -> CGP:
    """Convert a CGP dict to a CGP model with validation.

    Args:
        cgp: Raw CGP dictionary

    Returns:
        Validated CGP model instance

    Raises:
        ValidationError: If CGP structure is invalid
    """
    # Extract signature if nested
    sig_data = cgp.get("sig")
    if sig_data and isinstance(sig_data, dict):
        try:
            cgp = dict(cgp)
            cgp["sig"] = CGPSignature.model_validate(sig_data)
        except ValidationError:
            # Keep original if validation fails - Pydantic will catch it later
            pass

    return CGP.model_validate(cgp)


__all__ = [
    "CGP_VERSION_V01",
    "CGP_VERSION_V02",
    "SUPPORTED_VERSIONS",
    "Point",
    "Constellation",
    "SuperNode",
    "Attribution",
    "CGPSignature",
    "CGPMeta",
    "CGP",
    "GeometryData",
    "ValidationResult",
    "TextFragment",
    "DecodedGeometry",
    "detect_cgp_version",
    "cgp_dict_to_model",
]
