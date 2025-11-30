"""Small utilities for encoding/decoding CHIT Geometry Packets (CGP).

The goal is to provide a pragmatic bridge between the CHIT design docs and
automation in this repository.  The helpers below intentionally avoid heavy ML
dependencies; they simply structure secrets into CGP-compatible JSON for
transport and restore.
"""

from __future__ import annotations

import hashlib
import json
import base64
import binascii
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Tuple

CGP_SPEC = "chit.cgp.v0.1"


def _hash_to_anchor(seed: str, dims: int = 3) -> Tuple[float, ...]:
    """Derive a deterministic pseudo-anchor vector from a seed string."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    anchors = []
    for idx in range(dims):
        chunk = digest[idx * 8 : (idx + 1) * 8]
        num = int.from_bytes(chunk, "big", signed=False)
        anchors.append((num % 2000 - 1000) / 1000.0)  # map to [-1, 1)
    return tuple(anchors)


def encode_secret_map(
    secrets: Mapping[str, str],
    *,
    namespace: str,
    description: str,
    include_cleartext: bool = True,
) -> Dict[str, object]:
    """Build a CGP payload from a mapping of secrets."""
    if not secrets:
        raise ValueError("secrets mapping is empty")

    constellations = []
    for idx, (key, value) in enumerate(sorted(secrets.items())):
        anchor = _hash_to_anchor(f"{namespace}:{key}")
        point_payload: MutableMapping[str, object] = {
            "id": f"{key}-value",
            "magnitude": 1.0,
            "anchor": anchor,
        }
        if include_cleartext:
            point_payload["text"] = value
        else:
            encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
            point_payload["text_b64"] = encoded

        constellations.append(
            {
                "id": f"{namespace}-{idx}",
                "label": key,
                "kind": "secret",
                "points": [point_payload],
            }
        )

    packet: Dict[str, object] = {
        "spec": CGP_SPEC,
        "meta": {
            "namespace": namespace,
            "description": description,
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "encoder": "pmoves.chit.codec.encode_secret_map",
            "count": len(constellations),
        },
        "super_nodes": [
            {
                "id": namespace,
                "label": f"{namespace} secrets",
                "summary": description,
                "constellations": constellations,
            }
        ],
    }
    return packet


def decode_secret_map(cgp: Mapping[str, object]) -> Dict[str, str]:
    """Reconstruct a secret map from a CGP payload."""
    if cgp.get("spec") != CGP_SPEC:
        raise ValueError(f"Unsupported CGP spec: {cgp.get('spec')!r}")

    super_nodes = cgp.get("super_nodes")
    if not isinstance(super_nodes, list) or not super_nodes:
        raise ValueError("CGP missing super_nodes")

    secrets: Dict[str, str] = {}

    for node in super_nodes:
        constellations = node.get("constellations", [])
        if not isinstance(constellations, list):
            continue
        for const in constellations:
            key = const.get("label")
            if not isinstance(key, str):
                continue
            points = const.get("points") or []
            if not points:
                continue
            point = points[0]
            if "text" in point:
                value = point["text"]
            elif "text_b64" in point:
                encoded = point["text_b64"]
                if not isinstance(encoded, str):
                    continue
                try:
                    decoded = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    # Fall back to hex encoding for backwards compatibility with legacy payloads.
                    try:
                        decoded = bytes.fromhex(encoded)
                    except ValueError:
                        continue
                value = decoded.decode("utf-8")
            else:
                continue
            secrets[key] = value

    return secrets


def load_cgp(path: str | Path) -> Dict[str, object]:
    """Read a CGP JSON file."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
