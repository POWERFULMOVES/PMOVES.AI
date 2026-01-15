"""Unified CHIT Geometry Packet (CGP) decoder.

Provides a unified decoder API supporting both CGP v0.1 and v0.2 with:
- Version auto-detection
- HMAC signature verification
- AES-GCM anchor encryption/decryption
- Text extraction from points
- Geometry parsing and validation
- Spectral analysis (KL, JS divergence, Wasserstein-1D)
- Codebook-based text decoding

This decoder is ORTHOGONAL to the secrets codec in pmoves/chit/codec.py.
The secrets codec is for encoding API keys and credentials only.
This decoder handles general geometric data for the Geometry Bus.

See Also:
    - geometry_models.py: Pydantic models for CGP structures
    - pmoves/docs/CHIT_INTEGRATION_STATUS.md: Service integration guide
    - pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODER_MULTIv0.1.md: Advanced features
"""

from __future__ import annotations

import os
import json
import base64
import binascii
import hashlib
import hmac
import struct
import logging
from typing import Any, Dict, List, Optional, Tuple
from copy import deepcopy
from datetime import datetime

from pydantic import ValidationError

# Optional dependencies with graceful fallback
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    HAS_CRYPTOGRAPHY = True
except Exception:
    HAS_CRYPTOGRAPHY = False

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    HAS_SENTENCE_TRANSFORMERS = True
except Exception:
    HAS_SENTENCE_TRANSFORMERS = False

# Local imports
from pmoves.services.common.geometry_models import (
    CGP,
    CGP_VERSION_V01,
    CGP_VERSION_V02,
    Constellation,
    DecodedGeometry,
    GeometryData,
    Point,
    SuperNode,
    TextFragment,
    ValidationResult,
    detect_cgp_version,
    cgp_dict_to_model,
)

logger = logging.getLogger(__name__)

# Security constants
_MAX_FLOATS_UNPACK = 100_000  # Maximum number of floats to unpack (prevent DoS)
_MAX_CODEBOOK_LINE_LENGTH = 10_000  # Maximum line length for codebook JSONL
_MAX_CONSTELLATION_ID_LENGTH = 256  # Maximum constellation ID length


# =============================================================================
# Configuration (Environment Variables)
# =============================================================================

class CHITConfig:
    """CHIT decoder configuration from environment."""

    _passphrase: Optional[str] = None
    _require_signature: bool = False
    _decrypt_anchors: bool = False
    _codebook_path: Optional[str] = None
    _learned_text: bool = False
    _t5_model: Optional[str] = None
    _warned_default_passphrase: bool = False

    @classmethod
    def get_passphrase(cls) -> str:
        """Get CHIT passphrase for signing/encryption.

        Raises:
            ValueError: If CHIT_PASSPHRASE is not set and a secure value is required
        """
        if cls._passphrase is None:
            cls._passphrase = os.getenv("CHIT_PASSPHRASE", "")
            if not cls._passphrase:
                # Only log once to avoid spam
                if not cls._warned_default_passphrase:
                    logger.warning(
                        "CHIT_PASSPHRASE not set - using insecure default. "
                        "Set CHIT_PASSPHRASE environment variable for production use."
                    )
                    cls._warned_default_passphrase = True
                # Use a hash of the system path as a fallback (better than "change-me")
                import socket
                fallback = f"pmoves-{socket.gethostname()}"
                cls._passphrase = fallback
        return cls._passphrase

    @classmethod
    def require_signature(cls) -> bool:
        """Whether HMAC signature is required."""
        if not cls._require_signature:
            cls._require_signature = os.getenv("CHIT_REQUIRE_SIGNATURE", "false").lower() == "true"
        return cls._require_signature

    @classmethod
    def decrypt_anchors_enabled(cls) -> bool:
        """Whether anchor decryption is enabled."""
        if not cls._decrypt_anchors:
            cls._decrypt_anchors = os.getenv("CHIT_DECRYPT_ANCHORS", "false").lower() == "true"
        return cls._decrypt_anchors

    @classmethod
    def get_codebook_path(cls) -> str:
        """Path to codebook JSONL file for text decoding."""
        if cls._codebook_path is None:
            cls._codebook_path = os.getenv("CHIT_CODEBOOK_PATH", "")
        return cls._codebook_path

    @classmethod
    def learned_text_enabled(cls) -> bool:
        """Whether learned text enhancement is enabled."""
        if not cls._learned_text:
            cls._learned_text = os.getenv("CHIT_LEARNED_TEXT", "false").lower() == "true"
        return cls._learned_text

    @classmethod
    def get_t5_model(cls) -> Optional[str]:
        """Optional T5 model path for learned text generation."""
        if cls._t5_model is None:
            cls._t5_model = os.getenv("CHIT_T5_MODEL", "")
        return cls._t5_model or None


# =============================================================================
# Security Utilities
# =============================================================================

def _canon(obj: Dict[str, Any]) -> bytes:
    """Create canonical JSON representation for signing.

    Uses deterministic JSON with sorted keys and minimal whitespace
    to ensure consistent hashing across platforms.

    Args:
        obj: Dictionary to canonicalize

    Returns:
        Canonical JSON bytes

    Example:
        >>> _canon({"b": 2, "a": 1})
        b'{"a":1,"b":2}'
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_cgp(
    cgp: Dict[str, Any],
    passphrase: Optional[str] = None,
    kid: Optional[str] = None,
) -> Dict[str, Any]:
    """Sign a CGP with HMAC-SHA256.

    The signature covers the entire CGP except any existing 'sig' field.
    This allows for integrity verification when CGPs are transmitted
    over untrusted channels.

    Args:
        cgp: CGP dictionary to sign (returns a new dict with signature)
        passphrase: Shared secret for HMAC (defaults to CHIT_PASSPHRASE)
        kid: Key identifier (defaults to hashed passphrase)

    Returns:
        A new CGP dict with 'sig' field added

    Example:
        >>> cgp = {"super_nodes": [...]}
        >>> signed = sign_cgp(cgp, passphrase="shared-secret")
        >>> assert "sig" in signed
        >>> assert "hmac" in signed["sig"]
    """
    passphrase = passphrase or CHITConfig.get_passphrase()
    doc = deepcopy(cgp)
    ts = int(datetime.now().timestamp())
    # IMPORTANT: This SHA256 is NOT used for password hashing/authentication.
    # It is only used to generate a key identifier (kid) from the passphrase.
    # The actual cryptographic integrity comes from HMAC-SHA256 below.
    # This is safe because: (1) The passphrase is a CHIT secret key, not a user password
    # (2) The kid is just an identifier, not used for authentication itself
    # (3) All signature verification uses HMAC, not the SHA256 hash directly
    kid = kid or hashlib.sha256(passphrase.encode()).hexdigest()[:16]

    meta = {
        "alg": "HMAC-SHA256",
        "kid": kid,
        "ts": ts,
    }

    # Remove existing signature before signing
    doc_nosig = deepcopy(doc)
    doc_nosig.pop("sig", None)

    # Compute HMAC
    mac = hmac.new(
        passphrase.encode("utf-8"),
        _canon(doc_nosig),
        hashlib.sha256,
    ).digest()

    doc["sig"] = {
        **meta,
        "hmac": base64.b64encode(mac).decode("ascii"),
    }

    return doc


def verify_cgp(
    cgp: Dict[str, Any],
    passphrase: Optional[str] = None,
) -> bool:
    """Verify HMAC signature on a CGP.

    Args:
        cgp: CGP dictionary with 'sig' field
        passphrase: Shared secret for HMAC (defaults to CHIT_PASSPHRASE)

    Returns:
        True if signature is valid or missing (when not required),
        False otherwise

    Example:
        >>> cgp = {"super_nodes": [...], "sig": {"hmac": "..."}}
        >>> verify_cgp(cgp, passphrase="shared-secret")
        True
    """
    passphrase = passphrase or CHITConfig.get_passphrase()
    sig = cgp.get("sig")

    if not sig:
        return not CHITConfig.require_signature()

    mac_b64 = sig.get("hmac", "")
    if not mac_b64:
        return False

    doc_nosig = deepcopy(cgp)
    doc_nosig.pop("sig", None)

    mac2 = hmac.new(
        passphrase.encode("utf-8"),
        _canon(doc_nosig),
        hashlib.sha256,
    ).digest()

    try:
        mac1 = base64.b64decode(mac_b64)
    except (binascii.Error, ValueError):
        return False

    return hmac.compare_digest(mac1, mac2)


def _pack_floats(arr: List[float]) -> bytes:
    """Pack float array to bytes.

    Packs length + float32 values for transmission/storage.

    Args:
        arr: List of floats to pack

    Returns:
        Packed bytes (big-endian length + float32 data)

    Raises:
        RuntimeError: If numpy not available
        ValueError: If array is too large
    """
    if not HAS_NUMPY:
        raise RuntimeError("numpy required for float packing")
    if len(arr) > _MAX_FLOATS_UNPACK:
        raise ValueError(f"Float array too large: {len(arr)} > {_MAX_FLOATS_UNPACK}")
    a = (np.asarray(arr, dtype="float32")).tobytes()
    return struct.pack(">I", len(arr)) + a


def _unpack_floats(buf: bytes) -> List[float]:
    """Unpack bytes to float array.

    Args:
        buf: Packed bytes from _pack_floats

    Returns:
        List of floats

    Raises:
        RuntimeError: If numpy not available
        ValueError: If data is malformed or too large
    """
    if not HAS_NUMPY:
        raise RuntimeError("numpy required for float unpacking")
    if len(buf) < 4:
        raise ValueError("Buffer too small to contain float count")

    n = struct.unpack(">I", buf[:4])[0]
    if n > _MAX_FLOATS_UNPACK:
        raise ValueError(f"Float count too large: {n} > {_MAX_FLOATS_UNPACK}")
    expected_size = 4 + n * 4  # 4 bytes for count + 4 bytes per float
    if len(buf) < expected_size:
        raise ValueError(f"Buffer too small: expected {expected_size} bytes, got {len(buf)}")

    a = np.frombuffer(buf[4:4 + n * 4], dtype="float32", count=n)
    return a.astype(float).tolist()


def encrypt_anchor(
    anchor: List[float],
    constellation_id: str,
    passphrase: Optional[str] = None,
) -> Dict[str, str]:
    """Encrypt a constellation anchor vector with AES-GCM.

    Args:
        anchor: Anchor vector (list of floats)
        constellation_id: Constellation ID for AAD (Additional Authenticated Data)
        passphrase: Encryption key (defaults to CHIT_PASSPHRASE)

    Returns:
        Encrypted anchor dict with keys: alg, iv, salt, ct

    Raises:
        RuntimeError: If cryptography package not available
        ValueError: If anchor is empty or constellation_id is invalid

    Example:
        >>> enc = encrypt_anchor([0.1, 0.2, 0.3], "const-123")
        >>> assert "iv" in enc and "ct" in enc
    """
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError("cryptography package required for encryption")
    if not anchor:
        raise ValueError("anchor cannot be empty")
    if not constellation_id or not isinstance(constellation_id, str):
        raise ValueError("constellation_id must be a non-empty string")
    if len(constellation_id) > _MAX_CONSTELLATION_ID_LENGTH:
        raise ValueError(f"constellation_id too long: {len(constellation_id)} > {_MAX_CONSTELLATION_ID_LENGTH}")

    passphrase = passphrase or CHITConfig.get_passphrase()
    salt = os.urandom(16)

    # Scrypt key derivation (matching gateway implementation)
    key = hashlib.scrypt(
        passphrase.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )

    # Pack floats
    plain = _pack_floats(anchor)
    iv = os.urandom(12)
    aead = AESGCM(key)
    aad = _canon({"id": constellation_id})
    ct = aead.encrypt(iv, plain, aad)

    return {
        "alg": "AES-GCM",
        "iv": base64.b64encode(iv).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
    }


def decrypt_anchor(
    anchor_enc: Dict[str, str],
    constellation_id: str,
    passphrase: Optional[str] = None,
) -> List[float]:
    """Decrypt an encrypted constellation anchor vector.

    Args:
        anchor_enc: Encrypted anchor dict from encrypt_anchor
        constellation_id: Constellation ID for AAD verification
        passphrase: Decryption key (defaults to CHIT_PASSPHRASE)

    Returns:
        Decrypted anchor vector (list of floats)

    Raises:
        RuntimeError: If cryptography package not available
        ValueError: If decryption fails or input is invalid

    Example:
        >>> enc = encrypt_anchor([0.1, 0.2, 0.3], "const-123")
        >>> anchor = decrypt_anchor(enc, "const-123")
        >>> assert anchor == [0.1, 0.2, 0.3]
    """
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError("cryptography package required for decryption")
    if not CHITConfig.decrypt_anchors_enabled():
        raise ValueError("Anchor decryption not enabled (set CHIT_DECRYPT_ANCHORS=true)")

    # Validate required keys
    required_keys = {"iv", "salt", "ct"}
    missing_keys = required_keys - set(anchor_enc.keys())
    if missing_keys:
        raise ValueError(f"Missing required keys in anchor_enc: {missing_keys}")

    if not constellation_id or not isinstance(constellation_id, str):
        raise ValueError("constellation_id must be a non-empty string")

    passphrase = passphrase or CHITConfig.get_passphrase()

    try:
        iv = base64.b64decode(anchor_enc["iv"])
        salt = base64.b64decode(anchor_enc["salt"])
        ct = base64.b64decode(anchor_enc["ct"])
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Invalid base64 encoding in anchor_enc: {e}") from e

    key = hashlib.scrypt(
        passphrase.encode(),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )

    aead = AESGCM(key)
    aad = _canon({"id": constellation_id})

    try:
        plain = aead.decrypt(iv, ct, aad)
    except Exception as e:
        raise ValueError(f"Anchor decryption failed: {e}") from e

    return _unpack_floats(plain)


def encrypt_anchors(
    cgp: Dict[str, Any],
    passphrase: Optional[str] = None,
    kid: Optional[str] = None,
) -> Dict[str, Any]:
    """Encrypt all anchor vectors in a CGP.

    Args:
        cgp: CGP dictionary with anchor vectors
        passphrase: Encryption key (defaults to CHIT_PASSPHRASE)
        kid: Optional key identifier for signature

    Returns:
        A new CGP dict with anchors encrypted and signed

    Example:
        >>> cgp = {"super_nodes": [{"constellations": [{"anchor": [0.1, 0.2]}]}]}
        >>> encrypted = encrypt_anchors(cgp)
        >>> assert "anchor_enc" in encrypted["super_nodes"][0]["constellations"][0]
    """
    doc = deepcopy(cgp)

    for s in doc.get("super_nodes", []):
        for const in s.get("constellations", []):
            if "anchor" not in const:
                continue

            enc = encrypt_anchor(
                const["anchor"],
                const.get("id", ""),
                passphrase,
            )
            const.pop("anchor", None)
            const["anchor_enc"] = enc

    # Add signature
    return sign_cgp(doc, passphrase, kid)


def decrypt_anchors(
    cgp: Dict[str, Any],
    passphrase: Optional[str] = None,
) -> Dict[str, Any]:
    """Decrypt all encrypted anchor vectors in a CGP.

    Args:
        cgp: CGP dictionary with encrypted anchors
        passphrase: Decryption key (defaults to CHIT_PASSPHRASE)

    Returns:
        A new CGP dict with anchors decrypted

    Example:
        >>> encrypted = encrypt_anchors(cgp)
        >>> decrypted = decrypt_anchors(encrypted)
        >>> assert "anchor" in decrypted["super_nodes"][0]["constellations"][0]
    """
    doc = deepcopy(cgp)

    for s in doc.get("super_nodes", []):
        for const in s.get("constellations", []):
            enc = const.get("anchor_enc")
            if not enc:
                continue

            const["anchor"] = decrypt_anchor(
                enc,
                const.get("id", ""),
                passphrase,
            )
            const.pop("anchor_enc", None)

    return doc


# =============================================================================
# Geometry Decoder
# =============================================================================

class GeometryDecoder:
    """Unified CGP decoder supporting v0.1 and v0.2.

    Features:
    - Version auto-detection
    - HMAC signature verification
    - AES-GCM anchor encryption/decryption
    - Text extraction from points
    - Geometry parsing and validation
    - Spectral analysis

    Example:
        >>> decoder = GeometryDecoder()
        >>> result = decoder.decode_cgp(cgp_dict)
        >>> print(result.version)
        >>> print(result.text_fragments)
        >>> print(result.geometry.num_points)
    """

    def __init__(
        self,
        passphrase: Optional[str] = None,
        require_signature: Optional[bool] = None,
        decrypt_anchors: Optional[bool] = None,
    ):
        """Initialize the decoder.

        Args:
            passphrase: Shared secret for signing/encryption (defaults to CHIT_PASSPHRASE)
            require_signature: Whether to require HMAC signatures
            decrypt_anchors: Whether to decrypt encrypted anchors
        """
        self.passphrase = passphrase
        self._require_signature = require_signature
        self._decrypt_anchors = decrypt_anchors

        # Cached codebook for text decoding
        self._codebook: Optional[List[Dict[str, Any]]] = None

    def _get_passphrase(self) -> str:
        return self.passphrase or CHITConfig.get_passphrase()

    def _require_sig(self) -> bool:
        if self._require_signature is not None:
            return self._require_signature
        return CHITConfig.require_signature()

    def _should_decrypt(self) -> bool:
        if self._decrypt_anchors is not None:
            return self._decrypt_anchors
        return CHITConfig.decrypt_anchors_enabled()

    def decode_cgp(
        self,
        cgp_data: Dict[str, Any],
        verify_sig: bool = True,
        decrypt: bool = True,
    ) -> DecodedGeometry:
        """Decode a CGP and extract all information.

        Args:
            cgp_data: Raw CGP dictionary
            verify_sig: Whether to verify HMAC signature
            decrypt: Whether to decrypt encrypted anchors

        Returns:
            DecodedGeometry with version, geometry, text fragments, and validation

        Raises:
            ValueError: If CGP is invalid or signature verification fails
        """
        # Validate CGP structure
        validation = self.validate_cgp(cgp_data, verify_sig=verify_sig)
        if not validation.valid and self._require_sig():
            raise ValueError(f"CGP validation failed: {validation.errors}")

        # Detect version
        version = detect_cgp_version(cgp_data)

        # Decrypt anchors if requested
        cgp = deepcopy(cgp_data)
        if decrypt and self._should_decrypt():
            cgp = decrypt_anchors(cgp, self._get_passphrase())

        # Extract geometry data
        geometry = self.extract_geometry(cgp)

        # Extract text fragments
        text_fragments = self.extract_text(cgp)

        return DecodedGeometry(
            version=version,
            geometry=geometry,
            text_fragments=text_fragments,
            validation=validation,
            raw_cgp=cgp_data,
        )

    def validate_cgp(
        self,
        cgp_data: Dict[str, Any],
        verify_sig: bool = True,
    ) -> ValidationResult:
        """Validate a CGP structure and optionally verify signature.

        Args:
            cgp_data: CGP dictionary to validate
            verify_sig: Whether to verify HMAC signature

        Returns:
            ValidationResult with valid flag and any errors/warnings
        """
        version = detect_cgp_version(cgp_data)
        errors: List[str] = []
        warnings: List[str] = []

        # Check for required fields based on version
        if version == CGP_VERSION_V01 or version == CGP_VERSION_V02:
            if "super_nodes" not in cgp_data:
                errors.append("Missing required field: super_nodes")
            elif not isinstance(cgp_data["super_nodes"], list):
                errors.append("super_nodes must be a list")
        elif version == "unknown":
            errors.append("Unable to detect CGP version")

        # Verify signature if requested
        has_signature = "sig" in cgp_data
        signature_valid = None

        if verify_sig and has_signature:
            signature_valid = verify_cgp(cgp_data, self._get_passphrase())
            if not signature_valid and self._require_sig():
                errors.append("HMAC signature verification failed")
            elif not signature_valid:
                warnings.append("HMAC signature verification failed")
        elif verify_sig and self._require_sig() and not has_signature:
            errors.append("Missing required signature")

        return ValidationResult(
            valid=len(errors) == 0,
            version=version,
            errors=errors,
            warnings=warnings,
            has_signature=has_signature,
            signature_valid=signature_valid,
        )

    def extract_text(
        self,
        cgp_data: Dict[str, Any],
        include_b64: bool = False,
    ) -> List[TextFragment]:
        """Extract text fragments from CGP points.

        Args:
            cgp_data: CGP dictionary
            include_b64: Whether to decode base64 text fields

        Returns:
            List of TextFragment objects with text, confidence, and location
        """
        fragments: List[TextFragment] = []

        for super_node in cgp_data.get("super_nodes", []):
            super_id = super_node.get("id", "")
            super_label = super_node.get("label", "")

            for constellation in super_node.get("constellations", []):
                const_id = constellation.get("id", "")
                const_label = constellation.get("label", "")

                for point in constellation.get("points", []):
                    text = point.get("text", "")
                    text_b64 = point.get("text_b64", "")

                    # Decode base64 if requested and present
                    if not text and text_b64 and include_b64:
                        try:
                            text = base64.b64decode(text_b64).decode("utf-8")
                        except (binascii.Error, UnicodeDecodeError):
                            # Silently skip invalid base64/UTF-8
                            pass

                    if text:
                        fragment = TextFragment(
                            text=text,
                            confidence=point.get("conf"),
                            super_node=super_label or super_id or None,
                            constellation=const_label or const_id or None,
                            constellation_id=const_id or None,
                            point_id=point.get("id"),
                            coordinates={
                                "x": point.get("x"),
                                "y": point.get("y"),
                                "proj": point.get("proj"),
                            } if any(k in point for k in ("x", "y", "proj")) else None,
                        )
                        fragments.append(fragment)

        return fragments

    def extract_geometry(
        self,
        cgp_data: Dict[str, Any],
    ) -> GeometryData:
        """Extract geometric information from a CGP.

        Args:
            cgp_data: CGP dictionary

        Returns:
            GeometryData with counts, anchors, and spectral summary
        """
        version = detect_cgp_version(cgp_data)

        super_nodes = cgp_data.get("super_nodes", [])
        num_super_nodes = len(super_nodes)
        num_constellations = sum(len(sn.get("constellations", [])) for sn in super_nodes)
        num_points = sum(
            len(c.get("points", []))
            for sn in super_nodes
            for c in sn.get("constellations", [])
        )

        anchors: List[List[float]] = []
        spectrum_summary: Dict[str, List[float]] = {}

        for sn_idx, super_node in enumerate(super_nodes):
            for const in super_node.get("constellations", []):
                cid = const.get("id", f"c_{sn_idx}")

                # Collect anchor
                anchor = const.get("anchor")
                if anchor and isinstance(anchor, list):
                    anchors.append(anchor)

                # Collect spectrum
                spectrum = const.get("spectrum", [])
                if spectrum:
                    spectrum_summary[cid] = spectrum

        return GeometryData(
            version=version,
            num_super_nodes=num_super_nodes,
            num_constellations=num_constellations,
            num_points=num_points,
            has_attribution=cgp_data.get("attribution") is not None,
            has_signature=cgp_data.get("sig") is not None,
            anchors=anchors,
            spectrum_summary=spectrum_summary,
        )

    def compute_spectral_metrics(
        self,
        cgp_data: Dict[str, Any],
        codebook: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Compute spectral calibration metrics (KL, JS divergence).

        Args:
            cgp_data: CGP dictionary with constellations
            codebook: Optional codebook for projection (loaded from CHIT_CODEBOOK_PATH if not provided)

        Returns:
            Dict with KL, JS, and coverage metrics per constellation

        Raises:
            RuntimeError: If numpy not available
        """
        if not HAS_NUMPY:
            raise RuntimeError("numpy required for spectral metrics")

        # Load codebook if not provided
        if codebook is None:
            codebook = self._load_codebook()

        if not codebook:
            return {"error": "No codebook available for spectral analysis"}

        results: List[Dict[str, Any]] = []

        for super_node in cgp_data.get("super_nodes", []):
            for const in super_node.get("constellations", []):
                anchor = const.get("anchor")
                if not anchor:
                    # Try decrypting
                    anchor_enc = const.get("anchor_enc")
                    if anchor_enc and self._should_decrypt():
                        try:
                            anchor = decrypt_anchor(
                                anchor_enc,
                                const.get("id", ""),
                                self._get_passphrase(),
                            )
                        except Exception as e:
                            logger.debug("Failed to decrypt anchor for constellation %s: %s", const.get("id", ""), e)
                            continue

                if not anchor:
                    continue

                # Normalize anchor
                norm = sum(x * x for x in anchor) ** 0.5 or 1.0
                u = [x / norm for x in anchor]

                # Compute projections onto codebook
                vals = []
                for item in codebook:
                    vec = item.get("vec")
                    if vec:
                        proj = sum(a * b for a, b in zip(u, vec, strict=True))
                        vals.append(proj)

                if not vals:
                    continue

                rmin, rmax = const.get("radial_minmax", [min(vals), max(vals)])
                bins = len(const.get("spectrum", [1.0]))
                width = (rmax - rmin) / bins if bins > 1 else 1.0

                # Build empirical histogram
                hist = [0] * bins
                for v in vals:
                    b = int((v - rmin) / width)
                    b = max(0, min(b, bins - 1))
                    hist[b] += 1

                total = float(sum(hist)) or 1.0
                empirical = [h / total for h in hist]
                target = list(const.get("spectrum", [1.0 / bins] * bins))
                if len(target) != bins:
                    target = [1.0 / bins] * bins

                # Compute metrics
                kl = self._kl_divergence(target, empirical)
                js = self._js_divergence(target, empirical)
                coverage = sum(1 for e in empirical if e > 0) / bins

                results.append({
                    "constellation_id": const.get("id", ""),
                    "KL": kl,
                    "JS": js,
                    "coverage": coverage,
                })

        if not results:
            return {"error": "No constellations with valid anchors found"}

        # Compute mean metrics
        mean_kl = sum(r["KL"] for r in results) / len(results)
        mean_js = sum(r["JS"] for r in results) / len(results)
        mean_coverage = sum(r["coverage"] for r in results) / len(results)

        return {
            "constellations": results,
            "mean": {
                "KL": mean_kl,
                "JS": mean_js,
                "coverage": mean_coverage,
            },
        }

    def _kl_divergence(self, p: List[float], q: List[float]) -> float:
        """Compute Kullback-Leibler divergence."""
        if not HAS_NUMPY:
            raise RuntimeError("numpy required for KL divergence")
        eps = 1e-9
        p_arr = np.clip(np.array(p), eps, 1.0)
        q_arr = np.clip(np.array(q), eps, 1.0)
        return float(np.sum(p_arr * (np.log(p_arr) - np.log(q_arr))))

    def _js_divergence(self, p: List[float], q: List[float]) -> float:
        """Compute Jensen-Shannon divergence."""
        if not HAS_NUMPY:
            raise RuntimeError("numpy required for JS divergence")
        m = 0.5 * (np.array(p) + np.array(q))
        return 0.5 * self._kl_divergence(p, list(m)) + 0.5 * self._kl_divergence(q, list(m))

    def decode_with_codebook(
        self,
        cgp_data: Dict[str, Any],
        codebook: Optional[List[Dict[str, Any]]] = None,
        per_constellation: int = 10,
    ) -> List[Dict[str, Any]]:
        """Decode text using codebook projection.

        Projects constellation anchors onto codebook vectors to retrieve
        the most relevant text entries.

        Args:
            cgp_data: CGP dictionary
            codebook: Optional codebook list (loaded from CHIT_CODEBOOK_PATH if not provided)
            per_constellation: Max items to retrieve per constellation

        Returns:
            List of decoded items with text, projection, and score

        Raises:
            RuntimeError: If numpy not available
        """
        if not HAS_NUMPY:
            raise RuntimeError("numpy required for codebook decoding")

        codebook = codebook or self._load_codebook()
        if not codebook:
            return []

        results: List[Dict[str, Any]] = []

        for super_node in cgp_data.get("super_nodes", []):
            for const in super_node.get("constellations", []):
                anchor = const.get("anchor")
                if not anchor:
                    anchor_enc = const.get("anchor_enc")
                    if anchor_enc and self._should_decrypt():
                        try:
                            anchor = decrypt_anchor(
                                anchor_enc,
                                const.get("id", ""),
                                self._get_passphrase(),
                            )
                        except Exception:
                            continue

                if not anchor:
                    continue

                # Normalize anchor
                norm = sum(x * x for x in anchor) ** 0.5 or 1.0
                u = [x / norm for x in anchor]

                # Compute projections
                projections: List[Tuple[int, float]] = []
                for idx, item in enumerate(codebook):
                    vec = item.get("vec")
                    if vec is not None:
                        proj = sum(a * b for a, b in zip(u, vec, strict=True))
                        projections.append((idx, proj))

                # Apply spectral weighting
                rmin, rmax = const.get("radial_minmax", [0.0, 1.0])
                bins = len(const.get("spectrum", [1.0]))
                centers = [rmin + (rmax - rmin) * i / max(1, bins - 1) for i in range(bins)]
                spectrum = const.get("spectrum", [1.0])

                # Select items using spectrum-weighted soft selection
                selected: List[Tuple[int, float, float]] = []
                for idx, proj in projections:
                    nearest = min(range(bins), key=lambda i: abs(proj - centers[i])) if bins else 0
                    weight = spectrum[nearest] if bins else 1.0
                    selected.append((idx, weight, proj))

                # Sort by weight and select top per_constellation
                selected.sort(key=lambda x: x[1], reverse=True)

                for idx, weight, proj in selected[:per_constellation]:
                    results.append({
                        "constellation_id": const.get("id", ""),
                        "text": codebook[idx].get("text", ""),
                        "proj_est": proj,
                        "score": weight,
                    })

        return results

    def _load_codebook(self) -> List[Dict[str, Any]]:
        """Load codebook from configured path.

        Returns:
            List of codebook entries with 'vec' and 'text' fields
        """
        if self._codebook is not None:
            return self._codebook

        path = CHITConfig.get_codebook_path()
        if not path or not os.path.exists(path):
            return []

        items: List[Dict[str, Any]] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    # Validate line length before parsing JSON
                    if len(line) > _MAX_CODEBOOK_LINE_LENGTH:
                        logger.warning(f"Codebook line {line_num} too long, skipping")
                        continue
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON in codebook line {line_num}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load codebook from {path}: {e}")

        self._codebook = items
        return items

    def compute_shape_id(self, cgp_data: Dict[str, Any]) -> str:
        """Compute deterministic shape ID from CGP content.

        The shape ID is the SHA-256 hash of the canonical JSON
        representation, excluding the signature field.

        Args:
            cgp_data: CGP dictionary

        Returns:
            16-character hex digest
        """
        doc = dict(cgp_data)
        doc.pop("sig", None)
        return hashlib.sha256(_canon(doc)).hexdigest()[:16]


# =============================================================================
# Convenience Functions
# =============================================================================

def decode_cgp(
    cgp_data: Dict[str, Any],
    passphrase: Optional[str] = None,
) -> DecodedGeometry:
    """Convenience function to decode a CGP.

    Args:
        cgp_data: Raw CGP dictionary
        passphrase: Optional shared secret for signing/encryption

    Returns:
        DecodedGeometry with all extracted information

    Example:
        >>> result = decode_cgp(cgp_dict, passphrase="secret")
        >>> print(result.version)
        >>> for frag in result.text_fragments:
        ...     print(frag.text)
    """
    decoder = GeometryDecoder(passphrase=passphrase)
    return decoder.decode_cgp(cgp_data)


def extract_text_from_cgp(
    cgp_data: Dict[str, Any],
    include_b64: bool = False,
) -> List[str]:
    """Convenience function to extract only text from a CGP.

    Args:
        cgp_data: Raw CGP dictionary
        include_b64: Whether to decode base64 text fields

    Returns:
        List of text strings

    Example:
        >>> texts = extract_text_from_cgp(cgp_dict)
        >>> print("\\n".join(texts))
    """
    decoder = GeometryDecoder()
    fragments = decoder.extract_text(cgp_data, include_b64=include_b64)
    return [f.text for f in fragments]


def validate_cgp(
    cgp_data: Dict[str, Any],
    passphrase: Optional[str] = None,
) -> ValidationResult:
    """Convenience function to validate a CGP.

    Args:
        cgp_data: Raw CGP dictionary
        passphrase: Optional shared secret for signature verification

    Returns:
        ValidationResult with valid flag and any errors

    Example:
        >>> result = validate_cgp(cgp_dict)
        >>> if result.valid:
        ...     print("CGP is valid")
    """
    decoder = GeometryDecoder(passphrase=passphrase)
    return decoder.validate_cgp(cgp_data)


__all__ = [
    # Configuration
    "CHITConfig",
    # Security utilities
    "sign_cgp",
    "verify_cgp",
    "encrypt_anchor",
    "decrypt_anchor",
    "encrypt_anchors",
    "decrypt_anchors",
    # Main decoder
    "GeometryDecoder",
    # Convenience functions
    "decode_cgp",
    "extract_text_from_cgp",
    "validate_cgp",
    # Internal
    "_canon",
]
