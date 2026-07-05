# pmoves/tools/cgp_v2_build.py
"""Pure builders for CGP v2 extension blocks: hyperbolic, attribution, Merkle.

No I/O, no network. Consumed by beats_to_cgp.py. Outputs validate against
pmoves/contracts/schemas/geometry/cgp.v2.schema.json.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Mapping

import numpy as np

from pmoves.tools.hyperbolic_encode import encode_hierarchy


def _sha256_hex(data: bytes) -> str:
    return "0x" + hashlib.sha256(data).hexdigest()


def merkle_root(leaves: List[str]) -> str:
    """Binary Merkle root over leaf strings. Stable for a given ordered list.

    Empty -> sha256(b"") sentinel. Odd levels duplicate the last node.
    """
    if not leaves:
        return _sha256_hex(b"")
    level = [_sha256_hex(leaf.encode("utf-8")) for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [
            _sha256_hex((level[i] + level[i + 1]).encode("utf-8"))
            for i in range(0, len(level), 2)
        ]
    return level[0]


def build_attribution(raw_contributions: Mapping[str, float]) -> Dict[str, Any]:
    """Dirichlet attribution: alpha_i = max(raw_i, 0); weight_i = alpha_i / sum.

    All-zero -> uniform weights. merkle_root over sorted contributor addresses.
    """
    addrs = sorted(raw_contributions)
    alphas = [max(float(raw_contributions[a]), 0.0) for a in addrs]
    total = float(sum(alphas))
    n = len(addrs)
    if total <= 0.0:
        weights = [1.0 / n] * n if n else []
    else:
        weights = [a / total for a in alphas]
    contributors = [
        {
            "address": addr,
            "weight": round(w, 9),
            "raw_contribution": round(float(raw_contributions[addr]), 9),
            "alpha_component": round(a, 9),
        }
        for addr, a, w in zip(addrs, alphas, weights)
    ]
    return {
        "dirichlet_alpha": [round(a, 9) for a in alphas],
        "total_alpha": round(total, 9),
        "contributors": contributors,
        "merkle_root": merkle_root(addrs),
    }


def build_hyperbolic_block(
    groups: Mapping[str, np.ndarray],
    members: Mapping[str, Mapping[str, np.ndarray]],
    *,
    max_radius: float = 0.95,
) -> Dict[str, Any]:
    points = encode_hierarchy(groups, members, max_radius=max_radius)
    depth = max((p["depth"] for p in points), default=0)
    return {
        "space": "poincare_disk",
        "curvature": -1,
        "max_radius": max_radius,
        "points": points,
        "hierarchy_depth": depth,
    }
