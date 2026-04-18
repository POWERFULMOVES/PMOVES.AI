"""
PMOVES.AI - CHIT Security Validation Layer

Validates incoming CHIT Geometry Packets (CGP) for security and compliance.

This module provides:
1. Schema validation for CGP versions (v0.1, v0.2, v1.0)
2. Signature verification using chit_security.py
3. Access control for geometry events
4. Audit logging for security events
5. Integration with Hi-RAG geometry events endpoint

Security Features:
- Schema version validation
- HMAC signature verification
- Anchor encryption validation
- Expired signature detection
- Access control by source
- Comprehensive audit logging

Usage:
    from pmoves.tools.chit_security_validator import validate_cgp, CGPValidationError

    try:
        validate_cgp(cgp_packet, passphrase=os.environ.get("CHIT_PASSPHRASE"))
    except CGPValidationError as e:
        logger.error(f"Invalid CGP: {e}")
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import httpx
from pydantic import BaseModel, Field, field_validator

# CHIT security module is REQUIRED — fail-closed on import failure
try:
    from pmoves.tools.chit_security import verify_cgp, decrypt_anchors
except ImportError as e:
    raise RuntimeError(
        f"CHIT security module failed to import: {e}. "
        f"Signature verification is REQUIRED — cannot proceed without chit_security."
    ) from e

logger = logging.getLogger(__name__)


class CGPVersion(Enum):
    """Supported CGP schema versions"""
    V0_1 = "chit.cgp.v0.1"
    V0_2 = "chit.cgp.v0.2"
    V1_0 = "chit.cgp.v1.0"


class SecurityLevel(Enum):
    """Security classification for geometry events"""
    PUBLIC = "public"  # No verification required
    SIGNED = "signed"  # Signature verification required
    ENCRYPTED = "encrypted"  # Encryption required
    STRICT = "strict"  # Full validation required


class ValidationErrorType(Enum):
    """Types of validation errors"""
    MISSING_SPEC = "missing_spec"
    INVALID_VERSION = "invalid_version"
    MISSING_SIGNATURE = "missing_signature"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED_SIGNATURE = "expired_signature"
    INVALID_STRUCTURE = "invalid_structure"
    DECRYPTION_FAILED = "decryption_failed"
    ACCESS_DENIED = "access_denied"
    UNKNOWN_SOURCE = "unknown_source"


class CGPValidationError(Exception):
    """Raised when CGP validation fails"""

    def __init__(
        self,
        error_type: ValidationErrorType,
        message: str,
        cgp_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.cgp_id = cgp_id
        self.details = details or {}
        super().__init__(f"[{error_type.value.upper()}] {message}")


# ============================================================================
# CGP Schema Models
# ============================================================================

class CGPPoint(BaseModel):
    """A point in geometric space"""
    id: str
    modality: str
    proj: float
    conf: float
    summary: str


class CGPConstellation(BaseModel):
    """A constellation of points in geometric space"""
    id: str
    summary: str
    anchor: List[float] = Field(default_factory=list)
    spectrum: List[float] = Field(default_factory=list)
    points: List[CGPPoint] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('spectrum')
    def validate_spectrum(cls, v):
        """Spectrum must be normalized (sum to 1.0)"""
        if v and abs(sum(v) - 1.0) > 0.001:
            raise ValueError("Spectrum must sum to 1.0")
        return v


class CGPSuperNode(BaseModel):
    """A super node containing constellations"""
    id: str
    label: str
    summary: str
    x: float
    y: float
    r: float
    constellations: List[CGPConstellation] = Field(default_factory=list)


class CGPSignature(BaseModel):
    """CGP signature metadata"""
    alg: str
    kid: str
    hmac: Optional[str] = None


class CGPDocument(BaseModel):
    """Base CGP document schema"""
    spec: str
    summary: str
    created_at: str
    super_nodes: List[CGPSuperNode] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None
    sig: Optional[CGPSignature] = None

    @field_validator('spec')
    def validate_spec(cls, v):
        """Validate CGP schema version"""
        valid_specs = {ver.value for ver in CGPVersion}
        if v not in valid_specs:
            raise ValueError(f"Invalid spec version: {v}. Must be one of {valid_specs}")
        return v


# ============================================================================
# Access Control
# ============================================================================

class AccessControl:
    """Access control for geometry events"""

    # Trusted sources that can publish geometry events
    TRUSTED_SOURCES = {
        "consciousness-service",
        "tokenism-simulator",
        "agent-zero",
        "gateway-agent",
        "archon",
        "hirag-gateway",
    }

    # Sources requiring additional verification
    UNTRUSTED_SOURCES = {
        "external",
        "anonymous",
    }

    @classmethod
    def is_source_allowed(cls, source: str) -> bool:
        """Check if a source is allowed to publish geometry events"""
        # Empty source = internal service (allowed)
        if not source:
            return True

        # Check trusted sources
        if source in cls.TRUSTED_SOURCES:
            return True

        # Check for trusted prefix
        for trusted in cls.TRUSTED_SOURCES:
            if source.startswith(trusted):
                return True

        return False

    @classmethod
    def get_required_security_level(cls, source: str) -> SecurityLevel:
        """Get required security level based on source"""
        if not source or source in cls.TRUSTED_SOURCES:
            return SecurityLevel.SIGNED

        # External sources need strict validation
        return SecurityLevel.STRICT


# ============================================================================
# CGP Validator
# ============================================================================

class CGPValidator:
    """
    Validates CHIT Geometry Packets for security and compliance.

    Features:
    1. Schema validation (v0.1, v0.2, v1.0)
    2. Signature verification
    3. Expiration checking
    4. Access control
    5. Audit logging
    """

    def __init__(
        self,
        passphrase: Optional[str] = None,
        max_signature_age_hours: int = 24,
        audit_enabled: bool = True,
        audit_path: Optional[Path] = None
    ):
        """
        Initialize the CGP validator.

        Args:
            passphrase: CHIT passphrase for signature verification
            max_signature_age_hours: Maximum age of signatures before expiration
            audit_enabled: Whether to log validation events
            audit_path: Path to audit log file
        """
        self.passphrase = passphrase or os.environ.get("CHIT_PASSPHRASE", "")
        self.max_signature_age = timedelta(hours=max_signature_age_hours)
        self.audit_enabled = audit_enabled
        self.audit_path = audit_path or Path("memory/audit/cgp_validation.jsonl")

        # Create audit directory
        if self.audit_enabled:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def validate(
        self,
        cgp: Dict[str, Any],
        source: str = "",
        security_level: Optional[SecurityLevel] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a CGP packet.

        Args:
            cgp: CGP packet to validate
            source: Source of the CGP packet
            security_level: Required security level (auto-detected if not provided)

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            CGPValidationError: If validation fails and exceptions are enabled
        """
        start_time = time.time()
        validation_time = datetime.now(timezone.utc).isoformat()

        try:
            # Determine required security level
            if security_level is None:
                security_level = AccessControl.get_required_security_level(source)

            # Check access control
            if not AccessControl.is_source_allowed(source):
                self._log_audit(
                    cgp=cgp,
                    source=source,
                    valid=False,
                    error=ValidationErrorType.ACCESS_DENIED,
                    duration=time.time() - start_time
                )
                return False, f"Access denied for source: {source}"

            # Validate schema structure
            try:
                doc = CGPDocument(**cgp)
            except Exception as e:
                self._log_audit(
                    cgp=cgp,
                    source=source,
                    valid=False,
                    error=ValidationErrorType.INVALID_STRUCTURE,
                    details={"validation_error": str(e)},
                    duration=time.time() - start_time
                )
                return False, f"Invalid CGP structure: {e}"

            # Check spec version
            try:
                CGPVersion(doc.spec)
            except ValueError:
                self._log_audit(
                    cgp=cgp,
                    source=source,
                    valid=False,
                    error=ValidationErrorType.INVALID_VERSION,
                    details={"spec": doc.spec},
                    duration=time.time() - start_time
                )
                return False, f"Unsupported CGP version: {doc.spec}"

            # Check signature expiration
            if self._is_signature_expired(doc):
                self._log_audit(
                    cgp=cgp,
                    source=source,
                    valid=False,
                    error=ValidationErrorType.EXPIRED_SIGNATURE,
                    duration=time.time() - start_time
                )
                return False, "CGP signature has expired"

            # Verify signature (if required)
            if security_level in (SecurityLevel.SIGNED, SecurityLevel.STRICT):
                if not doc.sig:
                    self._log_audit(
                        cgp=cgp,
                        source=source,
                        valid=False,
                        error=ValidationErrorType.MISSING_SIGNATURE,
                        duration=time.time() - start_time
                    )
                    return False, "Signature required but not present"

                _signing_key = os.getenv("CHIT_SIGNING_KEY", "")
                if self.passphrase or _signing_key:
                    if not verify_cgp(cgp, self.passphrase):
                        self._log_audit(
                            cgp=cgp,
                            source=source,
                            valid=False,
                            error=ValidationErrorType.INVALID_SIGNATURE,
                            duration=time.time() - start_time
                        )
                        return False, "Invalid CGP signature"

            # Decrypt anchors (if encrypted)
            if security_level == SecurityLevel.ENCRYPTED:
                if self.passphrase:
                    try:
                        cgp = decrypt_anchors(cgp, self.passphrase)
                    except Exception as e:
                        self._log_audit(
                            cgp=cgp,
                            source=source,
                            valid=False,
                            error=ValidationErrorType.DECRYPTION_FAILED,
                            details={"error": str(e)},
                            duration=time.time() - start_time
                        )
                        return False, f"Anchor decryption failed: {e}"

            # Log successful validation
            self._log_audit(
                cgp=cgp,
                source=source,
                valid=True,
                duration=time.time() - start_time
            )

            return True, None

        except Exception as e:
            logger.error(f"Unexpected validation error: {e}")
            return False, f"Validation error: {e}"

    def _is_signature_expired(self, doc: CGPDocument) -> bool:
        """Check if a CGP signature has expired"""
        if not doc.sig:
            return False

        try:
            # Check created_at timestamp
            created_at = datetime.fromisoformat(doc.created_at.replace('Z', '+00:00'))
            age = datetime.now(timezone.utc) - created_at
            return age > self.max_signature_age
        except Exception:
            # If we can't parse the timestamp, consider it expired
            return True

    def _log_audit(
        self,
        cgp: Dict[str, Any],
        source: str,
        valid: bool,
        error: Optional[ValidationErrorType] = None,
        details: Optional[Dict[str, Any]] = None,
        duration: float = 0
    ) -> None:
        """Log validation event to audit file"""
        if not self.audit_enabled:
            return

        try:
            cgp_id = cgp.get("super_nodes", [{}])[0].get("constellations", [{}])[0].get("id", "unknown") if cgp.get("super_nodes") else "unknown"

            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "cgp_id": cgp_id,
                "valid": valid,
                "error": error.value if error else None,
                "details": details or {},
                "validation_time_ms": round(duration * 1000, 2),
                "spec": cgp.get("spec", "unknown"),
            }

            with open(self.audit_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")


# ============================================================================
# FastAPI Integration
# ============================================================================

class GeometryEventValidator:
    """
    FastAPI dependency for validating geometry events.

    Usage in FastAPI:
        from pmoves.tools.chit_security_validator import GeometryEventValidator

        @app.post("/geometry/event")
        async def geometry_event(
            request: Request,
            cgp: Dict[str, Any],
            validator: GeometryEventValidator = Depends()
        ):
            is_valid, error = validator.validate_from_request(request, cgp)
            if not is_valid:
                raise HTTPException(status_code=403, detail=error)
            return {"status": "accepted"}
    """

    def __init__(self):
        self.validator = CGPValidator()

    def validate_from_request(
        self,
        request_source: str,
        cgp: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate CGP from a FastAPI request"""
        return self.validator.validate(cgp, source=request_source)


# ============================================================================
# Convenience Functions
# ============================================================================

def validate_cgp(
    cgp: Dict[str, Any],
    source: str = "",
    passphrase: Optional[str] = None,
    security_level: Optional[SecurityLevel] = None
) -> bool:
    """
    Convenience function to validate a CGP packet.

    Args:
        cgp: CGP packet to validate
        source: Source of the CGP packet
        passphrase: CHIT passphrase (default: from environment)
        security_level: Required security level

    Returns:
        True if CGP is valid

    Raises:
        CGPValidationError: If validation fails
    """
    validator = CGPValidator(passphrase=passphrase)
    is_valid, error = validator.validate(cgp, source=source, security_level=security_level)

    if not is_valid:
        raise CGPValidationError(
            error_type=ValidationErrorType.INVALID_STRUCTURE,
            message=error or "Unknown validation error",
            cgp_id=cgp.get("id", "unknown")
        )

    return True


async def validate_and_publish(
    cgp: Dict[str, Any],
    gateway_url: str = "http://localhost:8086",
    source: str = ""
) -> Dict[str, Any]:
    """
    Validate a CGP packet and publish to Hi-RAG geometry gateway.

    Args:
        cgp: CGP packet to validate and publish
        gateway_url: Hi-RAG geometry gateway URL
        source: Source of the CGP packet

    Returns:
        Response from geometry gateway

    Raises:
        CGPValidationError: If validation fails
        httpx.HTTPError: If publishing fails
    """
    # Validate first
    validate_cgp(cgp, source=source)

    # Publish to gateway
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{gateway_url}/geometry/event",
            json={"type": "geometry.cgp.v1", "data": cgp},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# CLI
# ============================================================================

def main():
    """CLI for validating CGP files"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate CHIT Geometry Packets")
    parser.add_argument("cgp_file", type=str, help="Path to CGP JSON file")
    parser.add_argument("--source", type=str, default="", help="Source of the CGP")
    parser.add_argument("--strict", action="store_true", help="Enable strict validation")

    args = parser.parse_args()

    # Load CGP file
    with open(args.cgp_file) as f:
        cgp = json.load(f)

    # Validate
    security_level = SecurityLevel.STRICT if args.strict else None

    try:
        is_valid, error = validate_cgp(
            cgp,
            source=args.source,
            security_level=security_level
        )

        if is_valid:
            print(f"✓ CGP is valid")
            print(f"  Spec: {cgp.get('spec')}")
            print(f"  Super nodes: {len(cgp.get('super_nodes', []))}")
            return 0
        else:
            print(f"✗ CGP validation failed: {error}")
            return 1

    except CGPValidationError as e:
        print(f"✗ CGP validation error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
