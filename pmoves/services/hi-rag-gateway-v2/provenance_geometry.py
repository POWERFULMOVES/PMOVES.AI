"""Pure helpers that map accepted provenance payloads into geometry artifacts."""

from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Any, Dict, List, Optional

try:
    from pmoves.chit import CGP_SPEC_VERSION
except Exception:
    CGP_SPEC_VERSION = "chit.cgp.v1.0"

_STOPWORDS = {
    "about",
    "after",
    "also",
    "always",
    "among",
    "because",
    "before",
    "being",
    "between",
    "could",
    "every",
    "first",
    "from",
    "have",
    "into",
    "just",
    "many",
    "more",
    "other",
    "over",
    "really",
    "seems",
    "should",
    "since",
    "still",
    "that",
    "them",
    "then",
    "there",
    "these",
    "this",
    "those",
    "through",
    "very",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
}
_TERM_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-/]{2,}")

_PROVENANCE_SURFACE_CODE = """function surface(input) {
    const u = (input.u - 0.5) * Math.PI * 2.0;
    const v = (input.v - 0.5) * 2.4;
    const delta = input.delta ?? 0.45;
    const kappa = input.kappa ?? -0.35;
    const hz = input.hz ?? 0.25;
    const fitness = input.fitness ?? 0.82;
    const attribution = input.attribution ?? 0.88;
    const spectrum = input.spectrum ?? 0.55;
    const lineage = input.lineage ?? 0.6;

    const fold = 2.0 + delta * 5.0;
    const radius = 1.8 + (v + 1.2) * (1.1 + fitness * 1.7);
    const twist = u * (1.1 + hz * 6.0) + v * (1.8 + Math.abs(kappa) * 2.5);
    const ribbon = Math.sin(u * fold + lineage * Math.PI * 2.0) * (0.35 + spectrum * 0.9);
    const echo = Math.cos(v * (3.0 + delta * 4.0) - u * 0.5) * (0.2 + attribution * 0.8);

    const x = Math.cos(twist) * radius + ribbon * Math.cos(u * 2.0);
    const y = Math.sin(twist) * radius + ribbon * Math.sin(u * 2.0);
    const z = v * (3.2 + attribution * 2.4) + echo + Math.sin(u * (2.0 + fitness * 4.0)) * (0.3 + Math.abs(kappa) * 2.2);

    const r = 0.22 + attribution * 0.78;
    const g = 0.18 + fitness * 0.82;
    const b = 0.20 + hz * 0.80;
    const a = 0.58 + attribution * 0.30;

    return {
        x: x,
        y: y,
        z: z,
        r: Math.min(1, r),
        g: Math.min(1, g),
        b: Math.min(1, b),
        a: Math.min(1, a)
    };
}"""


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _stable_id(*parts: object) -> str:
    joined = "::".join(str(part).strip() for part in parts if str(part).strip())
    if not joined:
        joined = "provenance"
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]


def _coerce_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            numeric = float(text)
        except ValueError:
            return default
        if math.isfinite(numeric):
            return numeric
    return default


def _short_text(text: str, limit: int = 220) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def _token_fallbacks(text: str, *, limit: int) -> List[str]:
    tokens: List[str] = []
    seen = set()
    for match in _TERM_PATTERN.finditer(str(text or "").lower()):
        token = match.group(0)
        if token in _STOPWORDS or len(token) < 4 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _merge_term(
    bucket: Dict[str, Dict[str, Any]],
    term: Any,
    *,
    weight: Optional[float] = None,
    favorite: bool = False,
    anchor: bool = False,
) -> None:
    label = str(term or "").strip()
    if len(label) < 2:
        return
    key = label.lower()
    entry = bucket.get(key)
    normalized_weight = _coerce_float(weight, 0.0) or 0.0
    if entry is None:
        bucket[key] = {
            "term": label,
            "weight": normalized_weight,
            "favorite": bool(favorite),
            "anchor": bool(anchor),
        }
        return
    if normalized_weight > entry["weight"]:
        entry["weight"] = normalized_weight
    if len(label) > len(entry["term"]):
        entry["term"] = label
    entry["favorite"] = entry["favorite"] or bool(favorite)
    entry["anchor"] = entry["anchor"] or bool(anchor)


def extract_weighted_terms(payload: Dict[str, Any], *, max_terms: int = 8) -> List[Dict[str, Any]]:
    bucket: Dict[str, Dict[str, Any]] = {}
    favorite_words = [
        str(word).strip()
        for word in (payload.get("favorite_words") or [])
        if str(word).strip()
    ]
    anchor_terms = [
        str(word).strip()
        for word in (payload.get("anchor_terms") or [])
        if str(word).strip()
    ]
    favorite_keys = {word.lower() for word in favorite_words}
    anchor_keys = {word.lower() for word in anchor_terms}

    for item in payload.get("semantic_weights") or []:
        if not isinstance(item, dict):
            continue
        term = item.get("term") or item.get("word") or item.get("label")
        if not term:
            continue
        _merge_term(
            bucket,
            term,
            weight=item.get("weight") or item.get("score") or item.get("value"),
            favorite=bool(item.get("favorite")) or str(term).strip().lower() in favorite_keys,
            anchor=bool(item.get("anchor")) or str(term).strip().lower() in anchor_keys,
        )

    for index, word in enumerate(favorite_words):
        _merge_term(
            bucket,
            word,
            weight=max(0.35, 1.0 - index * 0.08),
            favorite=True,
            anchor=word.lower() in anchor_keys,
        )

    for index, word in enumerate(anchor_terms):
        _merge_term(
            bucket,
            word,
            weight=max(0.30, 0.9 - index * 0.07),
            favorite=word.lower() in favorite_keys,
            anchor=True,
        )

    if not bucket:
        for index, token in enumerate(_token_fallbacks(payload.get("text") or "", limit=max_terms)):
            _merge_term(bucket, token, weight=max(0.25, 0.9 - index * 0.07))

    entries = list(bucket.values())
    entries.sort(
        key=lambda item: (
            float(item.get("weight") or 0.0),
            1 if item.get("favorite") else 0,
            1 if item.get("anchor") else 0,
            item.get("term") or "",
        ),
        reverse=True,
    )
    entries = entries[: max_terms]
    if not entries:
        return [{"term": "signal", "weight": 1.0, "favorite": False, "anchor": False}]

    peak = max(float(item.get("weight") or 0.0) for item in entries)
    peak = peak if peak > 0 else 1.0
    normalized: List[Dict[str, Any]] = []
    for item in entries:
        weight = _clamp(float(item.get("weight") or 0.0) / peak, 0.15, 1.0)
        normalized.append(
            {
                "term": str(item.get("term") or "").strip(),
                "weight": round(weight, 4),
                "favorite": bool(item.get("favorite")),
                "anchor": bool(item.get("anchor")),
            }
        )
    return normalized


def provenance_payload_state_vector(
    payload: Dict[str, Any],
    *,
    weighted_terms: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    terms = weighted_terms or extract_weighted_terms(payload)
    weights = [float(item.get("weight") or 0.0) for item in terms] or [0.5]
    mean_weight = sum(weights) / len(weights)
    dispersion = sum(abs(weight - mean_weight) for weight in weights) / len(weights)
    favorite_ratio = sum(1 for item in terms if item.get("favorite")) / max(1, len(terms))
    anchor_ratio = sum(1 for item in terms if item.get("anchor")) / max(1, len(terms))
    provenance_refs = [str(ref).strip() for ref in (payload.get("provenance_refs") or []) if str(ref).strip()]
    lineage = _clamp(len(provenance_refs) / 5.0, 0.0, 1.0)
    noise_score = _clamp(_coerce_float((payload.get("scorecard") or {}).get("noise_score"), 0.18) or 0.18, 0.0, 1.0)
    delta = _clamp(0.14 + dispersion * 0.48 + noise_score * 0.32 + (1.0 - mean_weight) * 0.10, 0.05, 0.95)
    kappa = -_clamp(0.18 + anchor_ratio * 0.45 + favorite_ratio * 0.20 + lineage * 0.17, 0.12, 0.95)
    hz = _clamp(0.10 + noise_score * 0.56 + dispersion * 0.24 + (1.0 - mean_weight) * 0.10, 0.05, 0.95)
    fitness = _clamp(0.24 + (1.0 - noise_score) * 0.44 + lineage * 0.22 + mean_weight * 0.10, 0.05, 1.0)
    attribution = _clamp(
        0.12
        + (0.16 if payload.get("merkle_root") else 0.0)
        + (0.16 if payload.get("graphiti_mark") else 0.0)
        + lineage * 0.24
        + (1.0 - noise_score) * 0.14
        + anchor_ratio * 0.18,
        0.05,
        1.0,
    )
    # publish_gate: dedicated publish-authorization dimension, SEPARATE from
    # attribution (which is economic credit-weighting). 0.0 = held/closed (default),
    # 1.0 = released/open. Set per content item by the Hyperdimensions control
    # plane; opening it is what authorizes emit of content.publish.approved.v1.
    publish_gate = _clamp(_coerce_float(payload.get("publish_gate"), 0.0) or 0.0, 0.0, 1.0)
    return {
        "delta": round(delta, 4),
        "kappa": round(kappa, 4),
        "Hz": round(hz, 4),
        "F": round(fitness, 4),
        "A": round(attribution, 4),
        "publish_gate": round(publish_gate, 4),
        "spectrum": round(_clamp(mean_weight, 0.0, 1.0), 4),
        "lineage": round(lineage, 4),
        "dispersion": round(_clamp(dispersion, 0.0, 1.0), 4),
        "noise_score": round(noise_score, 4),
        "term_count": float(len(terms)),
    }


def provenance_payload_to_cgp(payload: Dict[str, Any]) -> Dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("accepted provenance payload requires non-empty text")

    weighted_terms = extract_weighted_terms(payload)
    state = provenance_payload_state_vector(payload, weighted_terms=weighted_terms)
    content_id = str(payload.get("content_id") or payload.get("shape_id") or _stable_id(text[:48])).strip()
    shape_id = str(payload.get("shape_id") or content_id or _stable_id(text[:48])).strip()
    namespace = str(payload.get("kb_namespace") or payload.get("namespace") or "pmoves").strip() or "pmoves"
    source_ref = str(payload.get("source_ref") or content_id).strip() or content_id

    theta = state["delta"] * math.pi
    phi = state["Hz"] * math.pi * 2.0
    radius = 6.5 + state["F"] * 3.0 + state["A"] * 2.0
    anchor = [
        round(radius * math.sin(theta) * math.cos(phi), 3),
        round(radius * math.sin(theta) * math.sin(phi), 3),
        round(radius * math.cos(theta), 3),
    ]

    points = []
    total = max(1, len(weighted_terms))
    for index, term in enumerate(weighted_terms):
        angle = phi + (index / total) * math.pi * 2.0
        arc = 0.8 + term["weight"] * 1.6
        z_offset = (index - (total - 1) / 2.0) * 0.28
        points.append(
            {
                "id": _stable_id(shape_id, "term", term["term"]),
                "label": term["term"],
                "text": term["term"],
                "modality": "text",
                "ref_id": source_ref,
                "source_ref": source_ref,
                "proj": round(term["weight"], 4),
                "conf": round(_clamp(state["A"] * 0.55 + term["weight"] * 0.45, 0.05, 1.0), 4),
                "offset": [
                    round(arc * math.cos(angle), 3),
                    round(arc * math.sin(angle), 3),
                    round(z_offset, 3),
                ],
                "meta": {
                    "favorite": bool(term.get("favorite")),
                    "anchor": bool(term.get("anchor")),
                    "weight": term["weight"],
                    "content_id": content_id,
                    "shape_id": shape_id,
                    "merkle_root": payload.get("merkle_root"),
                },
            }
        )

    constellation_meta = {
        "namespace": namespace,
        "modality": "text",
        "source_topic": "content.hirag.accepted.v1",
        "content_id": content_id,
        "shape_id": shape_id,
        "source_ref": source_ref,
        "accepted_reason": payload.get("accepted_reason"),
        "merkle_root": payload.get("merkle_root"),
        "graphiti_mark": payload.get("graphiti_mark"),
        "favorite_words": payload.get("favorite_words") or [],
        "anchor_terms": payload.get("anchor_terms") or [],
        "provenance_refs": payload.get("provenance_refs") or [],
        "state_vector": state,
        "scorecard": payload.get("scorecard") or {},
    }

    constellation = {
        "id": shape_id,
        "label": shape_id,
        "summary": _short_text(text),
        "anchor": anchor,
        "spectrum": [
            round(state["Hz"], 4),
            round(state["F"], 4),
            round(state["A"], 4),
        ],
        "radial_minmax": [0.0, round(radius, 3)],
        "points": points,
        "meta": constellation_meta,
    }

    return {
        "spec": CGP_SPEC_VERSION,
        "type": "geometry.cgp.v1",
        "id": _stable_id("provenance", shape_id),
        "label": shape_id,
        "source": "content.hirag.accepted.v1",
        "ts": time.time(),
        "meta": {
            **constellation_meta,
            "term_labels": [term["term"] for term in weighted_terms],
        },
        "super_nodes": [
            {
                "id": _stable_id("provenance-sn", shape_id),
                "label": f"Provenance {shape_id[:8]}",
                "type": "provenance_constellation",
                "x": state["delta"],
                "y": state["Hz"],
                "r": round(radius, 4),
                "state_vector": state,
                "constellations": [constellation],
            }
        ],
    }


def _param(name: str, value: float, *, minimum: float, maximum: float, runtime: float) -> Dict[str, Any]:
    step = 0.01
    if name == "kappa":
        step = 0.02
    return {
        "name": name,
        "value": round(value, 4),
        "min": round(minimum, 4),
        "max": round(maximum, 4),
        "step": step,
        "runtime": runtime,
    }


def provenance_payload_to_hyperdimensions_save(payload: Dict[str, Any]) -> Dict[str, Any]:
    weighted_terms = extract_weighted_terms(payload)
    state = provenance_payload_state_vector(payload, weighted_terms=weighted_terms)
    text = str(payload.get("text") or "").strip()
    content_id = str(payload.get("content_id") or payload.get("shape_id") or _stable_id(text[:48])).strip()
    shape_id = str(payload.get("shape_id") or content_id).strip() or content_id
    top_terms = [term["term"] for term in weighted_terms[:6]]

    return {
        "version": 1,
        "display": {
            "autoRotate": True,
            "showAxes": False,
            "showSurface": True,
            "showWireframe": False,
            "dirIntensity": 1.3,
            "ambientIntensity": 0.5,
            "shininess": 180,
            "globalSaturation": 1.4,
            "camera": {
                "position": {
                    "x": round(9.0 + state["Hz"] * 5.0, 4),
                    "y": round(-8.0 + state["delta"] * 12.0, 4),
                    "z": round(7.5 + state["A"] * 5.0, 4),
                },
                "target": {"x": 0.0, "y": 0.0, "z": 0.6},
            },
        },
        "parameters": {
            "uMin": 0.0,
            "uMax": 1.0,
            "vMin": 0.0,
            "vMax": 1.0,
            "uSegs": 220,
            "vSegs": 180,
        },
        "extraParameters": [
            _param("delta", state["delta"], minimum=0.05, maximum=0.95, runtime=8.0),
            _param("kappa", state["kappa"], minimum=-0.95, maximum=-0.05, runtime=11.0),
            _param("hz", state["Hz"], minimum=0.05, maximum=0.95, runtime=6.0),
            _param("fitness", state["F"], minimum=0.05, maximum=1.0, runtime=10.0),
            _param("attribution", state["A"], minimum=0.05, maximum=1.0, runtime=12.0),
            # Discrete publish gate (runtime=0.0 → does NOT oscillate; it is a
            # held/released state set by the control plane, not an animated axis).
            _param("publish_gate", state["publish_gate"], minimum=0.0, maximum=1.0, runtime=0.0),
            _param("spectrum", state["spectrum"], minimum=0.05, maximum=1.0, runtime=7.0),
            _param("lineage", state["lineage"], minimum=0.0, maximum=1.0, runtime=9.0),
        ],
        "surface": {
            "code": _PROVENANCE_SURFACE_CODE,
        },
        "outputs": {
            "coordConversion": "none",
            "rgbToHsv": False,
        },
        "meta": {
            "source_topic": "content.hirag.accepted.v1",
            "shape_id": shape_id,
            "content_id": content_id,
            "source_ref": payload.get("source_ref"),
            "accepted_reason": payload.get("accepted_reason"),
            "merkle_root": payload.get("merkle_root"),
            "graphiti_mark": payload.get("graphiti_mark"),
            "favorite_words": payload.get("favorite_words") or [],
            "anchor_terms": payload.get("anchor_terms") or [],
            "provenance_refs": payload.get("provenance_refs") or [],
            "state_vector": state,
            "top_terms": top_terms,
            "excerpt": _short_text(text, limit=280),
        },
    }
