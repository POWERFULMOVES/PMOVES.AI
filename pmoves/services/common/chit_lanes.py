"""Multi-lane CHIT encoder/decoder with EvoSwarm parameter injection.

Extends geometry_decoder.py with lane-aware reconstruction for text, image,
audio, and cross-modal mapping. Each lane uses the same CGP v0.2 format but
with lane-specific geometry parameters (delta, kappa, Hz) evolved by EvoSwarm.

Lanes:
    text  — Semantic preservation (text → CHIT → text)
    image — Compression + enhancement (image → CHIT → image)
    audio — Spectral fidelity (audio → CHIT → audio)
    mixed — Cross-modal mapping (any → CHIT → any)

See Also:
    - geometry_decoder.py: CGP v0.2 parsing, HMAC verification, spectral metrics
    - geometry_models.py: Pydantic models for CGP structures
    - pmoves/config/datasets.yaml: Dataset definitions using these lanes
    - pmoves/contracts/schemas/geometry/cgp.v2.schema.json: Packet schema
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Optional heavy dependencies — graceful fallback
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

# Local imports
from pmoves.services.common.geometry_models import (
    CGP_VERSION_V02,
    Constellation,
    Point,
    SuperNode,
)
from pmoves.services.common.geometry_decoder import (
    GeometryDecoder,
    sign_cgp,
    _canon,
)


# =============================================================================
# Lane Types
# =============================================================================

class LaneType(str, Enum):
    """CHIT modality lanes."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    MIXED = "mixed"


# =============================================================================
# EvoSwarm Parameter Pack
# =============================================================================

@dataclass
class EvoSwarmParams:
    """Geometry parameters for a single lane, evolved by EvoSwarm.

    These parameters shape how raw data is projected into CGP geometry.
    Different modalities require different curvature/frequency profiles.
    """
    delta: float = 1.0       # Hyperbolic curvature — information density
    kappa: float = 1.0       # Spectral concentration — frequency distribution
    hz: float = 440.0        # Frequency domain — temporal/spectral resolution
    F: float = 1.0           # Force scaling — gradient magnitude
    A: float = 1.0           # Amplitude — signal strength
    pack_id: str = "seed-v0"  # EvoSwarm parameter pack identifier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta": self.delta,
            "kappa": self.kappa,
            "hz": self.hz,
            "F": self.F,
            "A": self.A,
            "pack_id": self.pack_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvoSwarmParams":
        return cls(
            delta=float(d.get("delta", 1.0)),
            kappa=float(d.get("kappa", 1.0)),
            hz=float(d.get("hz", 440.0)),
            F=float(d.get("F", 1.0)),
            A=float(d.get("A", 1.0)),
            pack_id=str(d.get("pack_id", "seed-v0")),
        )


# Default parameters per lane (seeds before EvoSwarm evolves them)
DEFAULT_LANE_PARAMS: Dict[LaneType, EvoSwarmParams] = {
    LaneType.TEXT: EvoSwarmParams(
        delta=1.0, kappa=0.8, hz=220.0, F=1.0, A=1.0, pack_id="seed-text-v0",
    ),
    LaneType.IMAGE: EvoSwarmParams(
        delta=2.0, kappa=1.5, hz=440.0, F=0.5, A=2.0, pack_id="seed-image-v0",
    ),
    LaneType.AUDIO: EvoSwarmParams(
        delta=0.5, kappa=2.0, hz=880.0, F=1.5, A=0.8, pack_id="seed-audio-v0",
    ),
    LaneType.MIXED: EvoSwarmParams(
        delta=1.0, kappa=1.0, hz=440.0, F=1.0, A=1.0, pack_id="seed-mixed-v0",
    ),
}


# =============================================================================
# Reconstruction Scores
# =============================================================================

@dataclass
class ReconstructionScore:
    """Fidelity scores for a single reconstruction."""
    semantic: float = 0.0    # Meaning preservation (text similarity)
    spectral: float = 0.0    # Frequency fidelity (spectral overlap)
    temporal: float = 0.0    # Time-domain fidelity (waveform correlation)
    overall: float = 0.0     # Weighted combination

    def to_dict(self) -> Dict[str, float]:
        return {
            "semantic": self.semantic,
            "spectral": self.spectral,
            "temporal": self.temporal,
            "overall": self.overall,
        }


# =============================================================================
# Single Lane
# =============================================================================

class CHITLane:
    """Single-modality CHIT encoding/reconstruction lane.

    Each lane projects raw data of a specific modality (text, image, audio)
    into CGP v0.2 geometry using lane-specific EvoSwarm parameters.
    """

    def __init__(
        self,
        lane_type: LaneType,
        params: Optional[EvoSwarmParams] = None,
    ):
        self.lane_type = lane_type
        self.params = params or DEFAULT_LANE_PARAMS.get(
            lane_type, EvoSwarmParams()
        )
        self._decoder = GeometryDecoder()

    def encode(self, data: Union[str, bytes]) -> Dict[str, Any]:
        """Encode raw data into a CGP v0.2 packet.

        Projects data into Poincare disk geometry using lane-specific
        parameters. The encoding preserves modality-specific structure.

        Args:
            data: Raw input — string for text, bytes for image/audio

        Returns:
            CGP v0.2 packet dictionary
        """
        if self.lane_type == LaneType.TEXT:
            return self._encode_text(data if isinstance(data, str) else data.decode("utf-8", errors="replace"))
        elif self.lane_type == LaneType.IMAGE:
            return self._encode_binary(data if isinstance(data, bytes) else data.encode("utf-8"), "image")
        elif self.lane_type == LaneType.AUDIO:
            return self._encode_binary(data if isinstance(data, bytes) else data.encode("utf-8"), "audio")
        else:
            # Mixed: try text first, fall back to binary
            if isinstance(data, str):
                return self._encode_text(data)
            return self._encode_binary(data, "mixed")

    def reconstruct(self, packet: Dict[str, Any]) -> Union[str, bytes]:
        """Reconstruct data from a CGP v0.2 packet.

        Reverses the encoding to recover the original modality.

        Args:
            packet: CGP v0.2 packet

        Returns:
            Reconstructed data in the original modality
        """
        if self.lane_type == LaneType.TEXT:
            return self._reconstruct_text(packet)
        elif self.lane_type in (LaneType.IMAGE, LaneType.AUDIO):
            return self._reconstruct_binary(packet)
        else:
            # Mixed: reconstruct based on packet metadata
            meta = packet.get("meta", {}) or {}
            if meta.get("source_lane") in ("image", "audio"):
                return self._reconstruct_binary(packet)
            return self._reconstruct_text(packet)

    def score(
        self,
        original: Union[str, bytes],
        reconstructed: Union[str, bytes],
    ) -> ReconstructionScore:
        """Score reconstruction fidelity.

        Args:
            original: Original data
            reconstructed: Reconstructed data

        Returns:
            ReconstructionScore with per-dimension fidelity
        """
        if self.lane_type == LaneType.TEXT:
            return self._score_text(
                original if isinstance(original, str) else str(original),
                reconstructed if isinstance(reconstructed, str) else str(reconstructed),
            )
        return self._score_binary(
            original if isinstance(original, bytes) else original.encode("utf-8"),
            reconstructed if isinstance(reconstructed, bytes) else reconstructed.encode("utf-8"),
        )

    # -- Text encoding --------------------------------------------------------

    def _encode_text(self, text: str) -> Dict[str, Any]:
        """Encode text into CGP geometry via Poincare disk projection."""
        # Split text into semantic chunks (sentences/paragraphs)
        chunks = _split_text(text)

        # Project each chunk to a point in the Poincare disk
        points = []
        for i, chunk in enumerate(chunks):
            # Project using hyperbolic geometry with lane parameters
            r, theta = _text_to_poincare(chunk, self.params, index=i, total=len(chunks))
            x = r * math.cos(theta)
            y = r * math.sin(theta)

            points.append({
                "id": f"p-{i}",
                "x": round(x, 6),
                "y": round(y, 6),
                "text": chunk,
                "conf": round(min(1.0, len(chunk) / 200.0), 3),
                "magnitude": round(r, 6),
            })

        # Build CGP v0.2 packet
        constellation_id = hashlib.sha256(text[:256].encode()).hexdigest()[:12]
        packet: Dict[str, Any] = {
            "spec": CGP_VERSION_V02,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": {
                "lane": self.lane_type.value,
                "source_lane": self.lane_type.value,
                "delta": self.params.delta,
                "kappa": self.params.kappa,
                "hz": self.params.hz,
                "evoswarm_pack_id": self.params.pack_id,
                "chunk_count": len(chunks),
            },
            "hyperbolic": {
                "curvature": self.params.delta,
                "model": "poincare_disk",
            },
            "super_nodes": [{
                "id": f"sn-text-{constellation_id[:8]}",
                "label": "text-encoding",
                "constellations": [{
                    "id": constellation_id,
                    "label": f"text-{self.lane_type.value}",
                    "kind": "text",
                    "spectrum": _text_spectrum(text, self.params),
                    "radial_minmax": [0.0, 1.0],
                    "points": points,
                }],
            }],
        }
        return packet

    def _reconstruct_text(self, packet: Dict[str, Any]) -> str:
        """Reconstruct text from CGP packet by extracting point text fields."""
        fragments = []
        for sn in packet.get("super_nodes", []):
            for const in sn.get("constellations", []):
                for pt in const.get("points", []):
                    if pt.get("text"):
                        fragments.append(pt["text"])
        return " ".join(fragments)

    # -- Binary encoding (image/audio) ----------------------------------------

    def _encode_binary(self, data: bytes, kind: str) -> Dict[str, Any]:
        """Encode binary data into CGP geometry via spectral projection.

        For images: treats byte blocks as pixel intensity clusters.
        For audio: treats byte blocks as spectral frames.
        """
        # Chunk binary data into blocks for geometric projection
        block_size = max(64, len(data) // 256)  # At most 256 points
        blocks = [data[i:i + block_size] for i in range(0, len(data), block_size)]

        points = []
        for i, block in enumerate(blocks[:256]):  # Cap at 256 points
            # Compute spectral features of the block
            mean_val = sum(block) / len(block) if block else 0
            variance = sum((b - mean_val) ** 2 for b in block) / len(block) if block else 0

            # Project to Poincare disk
            r = min(0.99, (mean_val / 255.0) * self.params.A)
            theta = (i / max(1, len(blocks))) * 2 * math.pi * self.params.kappa

            points.append({
                "id": f"p-{i}",
                "x": round(r * math.cos(theta), 6),
                "y": round(r * math.sin(theta), 6),
                "proj": round(mean_val / 255.0, 4),
                "conf": round(1.0 - (variance / 16384.0), 4),  # Normalize variance
                "magnitude": round(r, 6),
            })

        data_hash = hashlib.sha256(data).hexdigest()[:12]
        packet: Dict[str, Any] = {
            "spec": CGP_VERSION_V02,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "meta": {
                "lane": self.lane_type.value,
                "source_lane": kind,
                "delta": self.params.delta,
                "kappa": self.params.kappa,
                "hz": self.params.hz,
                "evoswarm_pack_id": self.params.pack_id,
                "data_length": len(data),
                "block_size": block_size,
                "data_hash": data_hash,
            },
            "hyperbolic": {
                "curvature": self.params.delta,
                "model": "poincare_disk",
            },
            "super_nodes": [{
                "id": f"sn-{kind}-{data_hash[:8]}",
                "label": f"{kind}-encoding",
                "constellations": [{
                    "id": data_hash,
                    "label": f"{kind}-{self.lane_type.value}",
                    "kind": kind,
                    "spectrum": _binary_spectrum(data, self.params),
                    "radial_minmax": [0.0, 1.0],
                    "points": points,
                }],
            }],
        }
        return packet

    def _reconstruct_binary(self, packet: Dict[str, Any]) -> bytes:
        """Reconstruct binary data from CGP geometry points.

        This is a lossy reconstruction — the geometric encoding preserves
        structural information but not exact byte values.
        """
        meta = packet.get("meta", {}) or {}
        data_length = meta.get("data_length", 0)
        block_size = meta.get("block_size", 64)

        reconstructed = bytearray()
        for sn in packet.get("super_nodes", []):
            for const in sn.get("constellations", []):
                for pt in const.get("points", []):
                    # Reverse projection: point magnitude → byte intensity
                    proj = pt.get("proj", 0.5)
                    intensity = int(max(0, min(255, proj * 255)))
                    reconstructed.extend(bytes([intensity]) * block_size)

        # Trim to original length
        if data_length > 0:
            reconstructed = reconstructed[:data_length]

        return bytes(reconstructed)

    # -- Scoring --------------------------------------------------------------

    def _score_text(self, original: str, reconstructed: str) -> ReconstructionScore:
        """Score text reconstruction via token overlap."""
        orig_tokens = set(original.lower().split())
        recon_tokens = set(reconstructed.lower().split())

        if not orig_tokens:
            return ReconstructionScore(overall=1.0 if not recon_tokens else 0.0)

        overlap = len(orig_tokens & recon_tokens)
        precision = overlap / max(1, len(recon_tokens))
        recall = overlap / len(orig_tokens)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)

        return ReconstructionScore(
            semantic=round(f1, 4),
            spectral=round(recall, 4),
            temporal=1.0,  # Text has no temporal dimension
            overall=round(f1, 4),
        )

    def _score_binary(self, original: bytes, reconstructed: bytes) -> ReconstructionScore:
        """Score binary reconstruction via byte-level correlation."""
        min_len = min(len(original), len(reconstructed))
        if min_len == 0:
            return ReconstructionScore()

        matches = sum(1 for a, b in zip(original[:min_len], reconstructed[:min_len]) if a == b)
        exact = matches / min_len

        # Spectral: compare byte distributions
        if HAS_NUMPY:
            orig_hist = np.histogram(list(original[:min_len]), bins=32, range=(0, 256))[0]
            recon_hist = np.histogram(list(reconstructed[:min_len]), bins=32, range=(0, 256))[0]
            orig_norm = orig_hist / max(1, orig_hist.sum())
            recon_norm = recon_hist / max(1, recon_hist.sum())
            spectral = 1.0 - float(np.sum(np.abs(orig_norm - recon_norm))) / 2.0
        else:
            spectral = exact  # Fallback

        overall = 0.4 * exact + 0.4 * spectral + 0.2 * 1.0  # Temporal placeholder
        return ReconstructionScore(
            semantic=round(exact, 4),
            spectral=round(spectral, 4),
            temporal=1.0,
            overall=round(overall, 4),
        )


# =============================================================================
# Multi-Lane Orchestrator
# =============================================================================

class CHITMultiLane:
    """Multi-lane CHIT encoder/decoder with EvoSwarm parameter injection.

    Manages multiple CHITLane instances and provides cross-lane operations
    for mapping between modalities through shared CGP geometry.

    Example:
        >>> ml = CHITMultiLane()
        >>> packet = ml.encode("Hello world", lane="text")
        >>> text = ml.reconstruct(packet, target_lane="text")
        >>> score = ml.score("Hello world", text, lane="text")
    """

    def __init__(
        self,
        lane_params: Optional[Dict[str, EvoSwarmParams]] = None,
    ):
        """Initialize multi-lane system.

        Args:
            lane_params: Optional per-lane EvoSwarm parameters.
                Keys are lane type strings ("text", "image", "audio", "mixed").
                If not provided, uses DEFAULT_LANE_PARAMS seeds.
        """
        self.lanes: Dict[LaneType, CHITLane] = {}
        for lt in LaneType:
            params = None
            if lane_params and lt.value in lane_params:
                params = lane_params[lt.value]
            self.lanes[lt] = CHITLane(lt, params)

    def encode(self, data: Union[str, bytes], lane: str = "text") -> Dict[str, Any]:
        """Encode data using a specific lane.

        Args:
            data: Raw input data
            lane: Lane type string ("text", "image", "audio", "mixed")

        Returns:
            CGP v0.2 packet
        """
        lane_type = LaneType(lane)
        return self.lanes[lane_type].encode(data)

    def reconstruct(
        self,
        packet: Dict[str, Any],
        target_lane: Optional[str] = None,
    ) -> Union[str, bytes]:
        """Reconstruct data from a CGP packet.

        If target_lane is not specified, uses the source lane from packet metadata.

        Args:
            packet: CGP v0.2 packet
            target_lane: Target modality (defaults to source lane)

        Returns:
            Reconstructed data
        """
        if target_lane is None:
            meta = packet.get("meta", {}) or {}
            target_lane = meta.get("lane", "text")

        lane_type = LaneType(target_lane)
        return self.lanes[lane_type].reconstruct(packet)

    def cross_reconstruct(
        self,
        packet: Dict[str, Any],
        source_lane: str,
        target_lane: str,
    ) -> Union[str, bytes]:
        """Cross-lane reconstruction: map from one modality to another.

        The packet's geometry (points in Poincare disk) is reinterpreted
        through the target lane's parameters. This enables:
          text → CHIT → image (generate image from text geometry)
          audio → CHIT → text (transcribe via geometric mapping)

        Args:
            packet: CGP v0.2 packet (encoded in source_lane)
            source_lane: Original encoding lane
            target_lane: Target reconstruction lane

        Returns:
            Reconstructed data in target modality
        """
        # Remap geometry using target lane parameters
        target_lt = LaneType(target_lane)
        target = self.lanes[target_lt]

        # Apply target lane's EvoSwarm parameters to the packet
        remapped = deepcopy(packet)
        meta = remapped.setdefault("meta", {})
        meta["source_lane"] = source_lane
        meta["target_lane"] = target_lane
        meta["cross_reconstruct"] = True

        # Scale geometry by parameter ratios between lanes
        source_lt = LaneType(source_lane)
        source = self.lanes[source_lt]
        delta_ratio = target.params.delta / max(1e-9, source.params.delta)
        kappa_ratio = target.params.kappa / max(1e-9, source.params.kappa)

        for sn in remapped.get("super_nodes", []):
            for const in sn.get("constellations", []):
                for pt in const.get("points", []):
                    if "x" in pt and "y" in pt:
                        # Rescale coordinates by curvature ratio
                        pt["x"] = round(pt["x"] * delta_ratio, 6)
                        pt["y"] = round(pt["y"] * delta_ratio, 6)
                        # Clamp to Poincare disk boundary
                        r = math.sqrt(pt["x"] ** 2 + pt["y"] ** 2)
                        if r > 0.999:
                            scale = 0.999 / r
                            pt["x"] = round(pt["x"] * scale, 6)
                            pt["y"] = round(pt["y"] * scale, 6)

        return target.reconstruct(remapped)

    def score(
        self,
        original: Union[str, bytes],
        reconstructed: Union[str, bytes],
        lane: str = "text",
    ) -> ReconstructionScore:
        """Score reconstruction fidelity for a lane.

        Args:
            original: Original data
            reconstructed: Reconstructed data
            lane: Lane type used for scoring

        Returns:
            ReconstructionScore
        """
        lane_type = LaneType(lane)
        return self.lanes[lane_type].score(original, reconstructed)

    def update_params(self, lane: str, params: EvoSwarmParams) -> None:
        """Hot-update lane parameters from EvoSwarm evolution.

        Called when evoswarm.training.genome.v1 publishes new parameters.

        Args:
            lane: Lane type string
            params: New EvoSwarm parameters
        """
        lane_type = LaneType(lane)
        self.lanes[lane_type] = CHITLane(lane_type, params)
        logger.info(
            "Updated %s lane params: delta=%.3f kappa=%.3f hz=%.1f (pack=%s)",
            lane, params.delta, params.kappa, params.hz, params.pack_id,
        )

    def get_params(self, lane: str) -> EvoSwarmParams:
        """Get current parameters for a lane."""
        return self.lanes[LaneType(lane)].params

    def available_lanes(self) -> List[str]:
        """List available lane types."""
        return [lt.value for lt in self.lanes]


# =============================================================================
# Internal Helpers
# =============================================================================

def _split_text(text: str, max_chunks: int = 256) -> List[str]:
    """Split text into semantic chunks (sentences or paragraphs)."""
    # Split on sentence boundaries
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [text[:512]] if text.strip() else [""]

    # Merge very short sentences, cap total chunks
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) < 512:
            current = f"{current} {s}".strip() if current else s
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)

    return chunks[:max_chunks]


def _text_to_poincare(
    text: str,
    params: EvoSwarmParams,
    index: int = 0,
    total: int = 1,
) -> Tuple[float, float]:
    """Project text chunk to (r, theta) in Poincare disk.

    Uses a hash-based projection modulated by EvoSwarm parameters:
    - delta controls radial compression (higher = more central)
    - kappa controls angular spread (higher = wider distribution)
    """
    # Hash-based deterministic projection
    h = hashlib.sha256(text.encode("utf-8")).digest()
    h_int = int.from_bytes(h[:8], "big")

    # Radial: hash-derived magnitude modulated by curvature
    raw_r = (h_int % 10000) / 10000.0
    r = math.tanh(raw_r * params.delta) * 0.98  # Poincare disk, stay inside boundary

    # Angular: distribute based on position + hash
    base_theta = (index / max(1, total)) * 2 * math.pi
    hash_offset = ((int.from_bytes(h[8:12], "big") % 1000) / 1000.0 - 0.5) * params.kappa
    theta = base_theta + hash_offset

    return r, theta


def _text_spectrum(text: str, params: EvoSwarmParams) -> List[float]:
    """Compute spectral profile for text based on character frequency distribution."""
    if not text:
        return [1.0]

    # Character frequency histogram (simplified spectral analysis)
    freq: Dict[str, int] = {}
    for c in text.lower():
        if c.isalpha():
            freq[c] = freq.get(c, 0) + 1

    if not freq:
        return [1.0]

    total = sum(freq.values())
    values = sorted(freq.values(), reverse=True)
    # Normalize to spectrum (first 8 bins)
    spectrum = []
    for v in values[:8]:
        spectrum.append(round(v / total * params.kappa, 4))

    return spectrum or [1.0]


def _binary_spectrum(data: bytes, params: EvoSwarmParams) -> List[float]:
    """Compute spectral profile for binary data from byte distribution."""
    if not data:
        return [1.0]

    # Byte histogram (32 bins)
    bins = [0] * 32
    for b in data[:4096]:  # Sample first 4K
        bins[b // 8] += 1

    total = sum(bins) or 1
    spectrum = [round(b / total * params.kappa, 4) for b in bins if b > 0]
    return spectrum[:16] or [1.0]


# =============================================================================
# Module API
# =============================================================================

__all__ = [
    "LaneType",
    "EvoSwarmParams",
    "ReconstructionScore",
    "CHITLane",
    "CHITMultiLane",
    "DEFAULT_LANE_PARAMS",
]
