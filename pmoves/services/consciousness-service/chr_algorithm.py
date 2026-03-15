"""
CHR (Constellation Harvest Regularization) Algorithm.

Implements geometric clustering for consciousness theory embeddings.
Based on PMOVES-DoX/backend/app/chr_pipeline.py with CGP integration.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding Model Cache
# =============================================================================

_ST_MODEL: Optional["SentenceTransformer"] = None  # type: ignore


# =============================================================================
# CHIT Security (Inline for standalone service)
# =============================================================================


def _canon(obj: Dict[str, Any]) -> bytes:
    """Create canonical JSON representation for signing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_cgp(cgp: Dict[str, Any], passphrase: str, kid: Optional[str] = None) -> Dict[str, Any]:
    """Sign a CGP with HMAC-SHA256."""
    doc = json.loads(json.dumps(cgp))  # deep copy
    ts = int(datetime.now().timestamp())
    kid = kid or hashlib.sha256(passphrase.encode()).hexdigest()[:16]

    meta = {
        "alg": "HMAC-SHA256",
        "kid": kid,
        "ts": ts,
    }

    # Remove existing signature before signing
    doc_nosig = json.loads(json.dumps(doc))
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


@dataclass
class CHRConfig:
    """Configuration for CHR algorithm."""

    K: int = 8  # Number of constellations
    iters: int = 30  # Optimization iterations
    bins: int = 8  # Spectrum bins (for slab entropy)
    beta: float = 12.0  # Softmax temperature
    seed: int = 42  # Random seed


@dataclass
class ConstellationResult:
    """Result for a single constellation."""

    id: str
    anchor: List[float]
    spectrum: List[float]
    points: List[Dict[str, Any]]
    radial_minmax: Tuple[float, float]
    summary: str = ""


@dataclass
class CHRResult:
    """Complete CHR result with CGP-ready structure."""

    namespace: str
    K: int
    mhep: float  # Mean Helmoltz Entropy Profile
    Hg: float  # Global entropy
    Hs: float  # Spectrum entropy
    constellations: List[ConstellationResult]
    embeddings: np.ndarray
    anchors: np.ndarray
    labels: np.ndarray
    shape_id: str = ""


def _softmax(x: np.ndarray, axis: int = 1) -> np.ndarray:
    """Numerically stable softmax."""
    x_max = x.max(axis=axis, keepdims=True)
    e = np.exp(x - x_max)
    return e / (e.sum(axis=axis, keepdims=True) + 1e-9)


def _entropy(arr: np.ndarray, bins: int = 16) -> float:
    """Compute entropy of a distribution via histogram."""
    data_range = arr.max() - arr.min()
    if data_range == 0:
        return 0.0

    unique_vals = len(np.unique(arr))
    bins = min(bins, unique_vals) if unique_vals > 0 else 1

    try:
        hist, _ = np.histogram(arr, bins=bins, density=True)
    except ValueError:
        try:
            hist, _ = np.histogram(arr, bins="auto", density=True)
        except ValueError:
            return 0.0

    p = hist / (hist.sum() + 1e-9)
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def _maybe_st_model():
    """Try to load sentence-transformers model (cached)."""
    global _ST_MODEL

    if _ST_MODEL is not None:
        return _ST_MODEL

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded and cached sentence-transformers model")
        return _ST_MODEL
    except Exception as e:
        logger.warning(f"sentence-transformers not available: {e}")
        return None


def embed_texts(texts: List[str]) -> Tuple[np.ndarray, str]:
    """Generate embeddings for texts with fallback."""
    texts = [t if isinstance(t, str) else str(t) for t in texts]

    model = _maybe_st_model()
    if model is not None:
        try:
            vecs = model.encode(
                texts,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return vecs.astype(np.float32), "sentence-transformers/all-MiniLM-L6-v2"
        except Exception as e:
            logger.warning(f"Model encode failed: {e}")

    # Fallback: hashing vectorizer
    from sklearn.feature_extraction.text import HashingVectorizer  # type: ignore

    hv = HashingVectorizer(n_features=2**12, alternate_sign=False, norm=None)
    X = hv.transform(texts).astype(np.float32)
    X = X.toarray()

    # l2-normalize
    norms = np.linalg.norm(X, axis=1, keepdims=True) + 1e-9
    X = X / norms

    return X.astype(np.float32), "HashingVectorizer"


def _init_anchors(Z: np.ndarray, K: int, seed: int = 42) -> np.ndarray:
    """Initialize anchor vectors using PCA-inspired selection."""
    rng = np.random.default_rng(seed)

    # Pick K random rows and orthonormalize
    idx = rng.choice(Z.shape[0], size=min(K, Z.shape[0]), replace=False)
    U = Z[idx]

    # l2 normalize rows
    U = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)

    if U.shape[0] < K:
        # pad with random vectors
        pad = rng.normal(size=(K - U.shape[0], Z.shape[1]))
        pad = pad / (np.linalg.norm(pad, axis=1, keepdims=True) + 1e-9)
        U = np.vstack([U, pad])

    return U.astype(np.float32)


def _compute_spectrum(
    projections: np.ndarray, bins: int = 8
) -> Tuple[List[float], Tuple[float, float]]:
    """Compute slab entropy spectrum."""
    rmin = float(projections.min())
    rmax = float(projections.max())

    if rmax - rmin < 1e-9:
        # All values are the same
        return [1.0 / bins] * bins, (rmin, rmax)

    hist, _ = np.histogram(projections, bins=bins, range=(rmin, rmax), density=True)

    # Normalize to get probability distribution
    total = hist.sum()
    if total > 0:
        hist = hist / total

    return hist.tolist(), (rmin, rmax)


def run_chr(
    units: List[Dict[str, Any]],
    config: Optional[CHRConfig] = None,
) -> CHRResult:
    """
    Run CHR algorithm on text units.

    Args:
        units: List of dicts with 'id' and 'text' keys
        config: Optional CHRConfig (uses defaults if not provided)

    Returns:
        CHRResult with constellations and embeddings
    """
    if not units:
        raise ValueError("No units provided")

    config = config or CHRConfig()

    # Extract texts
    texts = [u.get("text", "") for u in units]
    ids = [u.get("id", f"chunk-{i}") for i, u in enumerate(units)]

    # Generate embeddings
    Z, backend = embed_texts(texts)
    logger.info(f"Generated {Z.shape} embeddings using {backend}")

    # Initialize anchors
    U = _init_anchors(Z, K=config.K, seed=config.seed)

    Hg_traj: List[float] = []
    Hs_traj: List[float] = []

    # Main optimization loop
    for iteration in range(config.iters):
        U_norm = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)
        proj = Z @ U_norm.T  # [N, K]

        # Soft assignments over constellations
        p = _softmax(config.beta * proj, axis=1)  # [N, K]

        # Update anchors as weighted means
        U_new = np.zeros_like(U)
        for j in range(config.K):
            w = p[:, j : j + 1]
            num = (w * Z).sum(axis=0)
            norm = np.linalg.norm(num)

            if norm < 1e-8:
                U_new[j] = U[j]  # Keep previous anchor
            else:
                U_new[j] = num / norm

        U = U_new

        # Compute entropy measures
        r = proj.max(axis=1)
        Hg = _entropy(r, bins=config.bins)

        Hs_list = []
        for j in range(config.K):
            Hs_list.append(_entropy(proj[:, j], bins=config.bins))
        Hs = float(np.mean(Hs_list)) if Hs_list else Hg

        Hg_traj.append(float(Hg))
        Hs_traj.append(float(Hs))

    # Final projections and hard labels
    U_norm = U / (np.linalg.norm(U, axis=1, keepdims=True) + 1e-9)
    proj = Z @ U_norm.T
    labels = proj.argmax(axis=1)
    r = proj.max(axis=1)

    # Compute MHEP (Mean Helmoltz Entropy Profile)
    if len(Hg_traj) >= 2 and Hg_traj[0] > 1e-9 and Hs_traj[0] > 1e-9:
        drop_g = max(0.0, (Hg_traj[0] - Hg_traj[-1]) / Hg_traj[0])
        drop_s = max(0.0, (Hs_traj[0] - Hs_traj[-1]) / Hs_traj[0])
        mhep = (drop_g + drop_s) * 50.0
    else:
        mhep = 0.0

    # Build constellation results
    constellations: List[ConstellationResult] = []
    for j in range(config.K):
        mask = labels == j
        if not mask.any():
            continue

        const_points_idx = np.where(mask)[0]
        const_proj = proj[const_points_idx, j]

        # Compute spectrum for this constellation
        spectrum, (rmin, rmax) = _compute_spectrum(const_proj, bins=config.bins)

        # Build points list
        points = []
        for idx in const_points_idx:
            points.append({
                "id": ids[idx],
                "text": texts[idx][:500],  # Truncate for CGP size
                "proj": float(const_proj[np.where(const_points_idx == idx)[0][0]]),
                "conf": float(r[idx]),
            })

        # Sort by projection
        points.sort(key=lambda p: p["proj"], reverse=True)

        constellations.append(
            ConstellationResult(
                id=f"constellation-{j}",
                anchor=U_norm[j].tolist(),
                spectrum=spectrum,
                points=points[:50],  # Limit points per constellation
                radial_minmax=(rmin, rmax),
                summary=f"Constellation {j} with {len(points)} points",
            )
        )

    # Compute shape ID from result hash
    namespace = units[0].get("namespace", "pmoves.consciousness")
    result_hash = hashlib.sha256(
        f"{namespace}-{config.K}-{len(units)}-{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:16]

    return CHRResult(
        namespace=namespace,
        K=config.K,
        mhep=float(mhep),
        Hg=float(Hg_traj[-1]) if Hg_traj else 0.0,
        Hs=float(Hs_traj[-1]) if Hs_traj else 0.0,
        constellations=constellations,
        embeddings=Z,
        anchors=U_norm,
        labels=labels,
        shape_id=result_hash,
    )


def chr_result_to_cgp(
    result: CHRResult,
    passphrase: str,
    encrypt_anchors: bool = False,
) -> Dict[str, Any]:
    """
    Convert CHR result to CGP packet.

    Args:
        result: CHRResult from run_chr
        passphrase: CHIT passphrase for signing
        encrypt_anchors: Whether to encrypt anchor vectors

    Returns:
        CGP packet ready for NATS publication

    Raises:
        ValueError: If encrypt_anchors is True (not implemented)
    """
    if encrypt_anchors:
        raise ValueError("Anchor encryption not implemented - do not set encrypt_anchors=True")

    super_node = {
        "id": f"{result.namespace}-super",
        "label": result.namespace,
        "summary": f"CHR clustering with {result.K} constellations, MHEP={result.mhep:.2f}",
        "constellations": [],
    }

    for const in result.constellations:
        constellation: Dict[str, Any] = {
            "id": const.id,
            "summary": const.summary,
            "spectrum": const.spectrum,
            "radial_minmax": list(const.radial_minmax),
            "points": const.points,
            "anchor": const.anchor,  # Always include plain anchor
        }

        super_node["constellations"].append(constellation)

    cgp = {
        "spec": "chit.cgp.v0.1",
        "summary": f"CHR: {result.namespace} with {result.K} constellations",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "meta": {
            "algorithm": "CHR",
            "namespace": result.namespace,
            "K": result.K,
            "mhep": result.mhep,
            "Hg": result.Hg,
            "Hs": result.Hs,
            "shape_id": result.shape_id,
        },
        "super_nodes": [super_node],
    }

    # Sign the CGP using inline function
    return sign_cgp(cgp, passphrase=passphrase)
