# pmoves/tools/hyperbolic_encode.py
"""Pure Poincaré-disk encoder for CGP v2 hyperbolic blocks.

Maps a hierarchy (group -> track) into the Poincaré disk: depth controls
Euclidean radius (root near centre, leaves toward the boundary but always
|z| < max_radius < 1), angle comes from a 2-D direction so semantically
similar items sit in similar directions. No external services; numpy only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

import numpy as np


def _radius_for_depth(depth: int, max_radius: float) -> float:
    # Geometric saturation toward the boundary: depth 0 -> 0, depth->inf -> max_radius.
    # r(d) = max_radius * (1 - 0.5 ** d)
    return round(max_radius * (1.0 - 0.5 ** depth), 6)


def _angle_from_vector(vector: np.ndarray) -> float:
    if vector.shape[0] < 2:
        vector = np.concatenate([vector, np.zeros(2 - vector.shape[0])])
    theta = math.atan2(float(vector[1]), float(vector[0]))
    if theta < 0:
        theta += 2 * math.pi
    return theta


def poincare_encode(
    angle: Optional[float] = None,
    *,
    vector: Optional[np.ndarray] = None,
    depth: int = 0,
    max_radius: float = 0.95,
) -> Dict[str, float]:
    if angle is None:
        if vector is None:
            raise ValueError("poincare_encode requires either angle or vector")
        angle = _angle_from_vector(np.asarray(vector, dtype=float))
    theta = float(angle) % (2 * math.pi)
    r = _radius_for_depth(int(depth), max_radius)
    return {
        "x": round(r * math.cos(theta), 6),
        "y": round(r * math.sin(theta), 6),
        "r": r,
        "theta": round(theta, 6),
        "depth": int(depth),
    }


def encode_hierarchy(
    groups: Mapping[str, np.ndarray],
    members: Mapping[str, Mapping[str, np.ndarray]],
    *,
    max_radius: float = 0.95,
) -> list[Dict[str, Any]]:
    """Return a flat list of poincare_point dicts (groups depth=1, tracks depth=2)."""
    points: list[Dict[str, Any]] = []
    for gid in sorted(groups):
        gp = poincare_encode(vector=np.asarray(groups[gid], dtype=float), depth=1, max_radius=max_radius)
        gp["id"] = gid
        points.append(gp)
        for tid in sorted(members.get(gid, {})):
            tp = poincare_encode(vector=np.asarray(members[gid][tid], dtype=float), depth=2, max_radius=max_radius)
            tp["id"] = tid
            tp["parent_id"] = gid
            points.append(tp)
    return points
