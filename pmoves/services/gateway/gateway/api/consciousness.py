"""Consciousness theory demo endpoints for the gateway.

Provides CGP packet generation from the Kuhn Landscape consciousness taxonomy.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .chit import ingest_cgp

router = APIRouter(prefix="/workflow", tags=["Consciousness Demo"])
logger = logging.getLogger("pmoves.gateway.consciousness")

# Path to consciousness taxonomy
# From gateway/api/consciousness.py to pmoves/data/consciousness/
TAXONOMY_PATH = Path(__file__).resolve().parents[4] / "data" / "consciousness" / "kuhn_full_taxonomy.json"


class ConsciousnessDemoRequest(BaseModel):
    """Input for consciousness demo endpoint."""

    theory_category: Optional[str] = Field(
        default=None,
        description="Filter by category (e.g., 'materialism', 'dualism', 'panpsychism')"
    )
    max_theories: int = Field(default=10, ge=1, le=100)
    output_format: Literal["json", "cgp", "both"] = Field(default="json")


class TheoryInfo(BaseModel):
    """Information about a consciousness theory."""

    name: str
    description: str
    proponents: List[str]
    category: str
    subcategory: str


class ConsciousnessDemoResponse(BaseModel):
    """Response from consciousness demo endpoint."""

    theories: List[TheoryInfo]
    cgp_packets: Optional[List[Dict[str, Any]]] = None
    shape_ids: Optional[List[str]] = None
    total_theories: int
    categories_available: List[str]


def _load_taxonomy() -> Dict[str, Any]:
    """Load the consciousness taxonomy JSON."""
    if not TAXONOMY_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Consciousness taxonomy not found at {TAXONOMY_PATH}"
        )
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _extract_theories(
    taxonomy: Dict[str, Any],
    category_filter: Optional[str] = None,
    max_theories: int = 10
) -> tuple[List[TheoryInfo], List[str]]:
    """Extract theories from taxonomy, optionally filtered by category."""
    theories: List[TheoryInfo] = []
    categories: List[str] = []

    for cat_key, cat_data in taxonomy.get("categories", {}).items():
        cat_id = cat_data.get("id", cat_key)
        categories.append(cat_id)

        # Skip if filtering and category doesn't match
        if category_filter and cat_id.lower() != category_filter.lower():
            continue

        for subcat_key, subcat_data in cat_data.get("subcategories", {}).items():
            for theory in subcat_data.get("theories", []):
                if len(theories) >= max_theories:
                    break
                theories.append(TheoryInfo(
                    name=theory.get("name", "Unknown"),
                    description=theory.get("description", ""),
                    proponents=theory.get("proponents", []),
                    category=cat_id,
                    subcategory=subcat_key,
                ))
            if len(theories) >= max_theories:
                break
        if len(theories) >= max_theories:
            break

    return theories, sorted(set(categories))


def _theory_to_cgp(theory: TheoryInfo, idx: int) -> Dict[str, Any]:
    """Convert a theory to a CGP packet."""
    # Generate geometric coordinates based on theory properties
    angle = (idx / 10) * math.tau  # Spread around circle
    magnitude = min(1.0, 0.3 + len(theory.description) / 500.0)
    anchor = [
        round(math.cos(angle) * magnitude, 6),
        round(math.sin(angle) * magnitude, 6),
        round(len(theory.proponents) / 5.0, 6)  # Z based on proponent count
    ]

    # Create points from proponents
    points = []
    for pidx, proponent in enumerate(theory.proponents[:5]):
        p_angle = angle + (pidx * 0.1)
        points.append({
            "id": f"pt:{theory.name.replace(' ', '_')}:{pidx}",
            "modality": "theory",
            "ref_id": f"theory:{theory.name}",
            "proj": round(0.5 + pidx * 0.1, 4),
            "conf": round(0.8 - pidx * 0.05, 4),
            "text": proponent,
            "meta": {
                "category": theory.category,
                "subcategory": theory.subcategory,
            }
        })

    constellation = {
        "id": f"conscious:{theory.name.replace(' ', '_')}",
        "summary": theory.name,
        "anchor": anchor,
        "radial_minmax": [0.0, 1.0],
        "spectrum": _spectrum_for_category(theory.category),
        "points": points,
        "meta": {
            "description": theory.description,
            "category": theory.category,
            "subcategory": theory.subcategory,
            "proponents": theory.proponents,
        }
    }

    return {
        "spec": "chit.cgp.v0.1",
        "meta": {
            "source": "consciousness-taxonomy",
            "theory": theory.name,
            "category": theory.category,
        },
        "super_nodes": [{
            "id": f"sn:{theory.category}",
            "label": theory.category.replace("_", " ").title(),
            "summary": f"Consciousness theory: {theory.name}",
            "constellations": [constellation],
        }]
    }


def _spectrum_for_category(category: str) -> List[float]:
    """Generate a color spectrum based on category."""
    spectrums = {
        "materialism": [0.8, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0],
        "dualism": [0.0, 0.8, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0],
        "panpsychism": [0.0, 0.0, 0.8, 0.1, 0.1, 0.0, 0.0, 0.0],
        "idealism": [0.0, 0.0, 0.0, 0.8, 0.1, 0.1, 0.0, 0.0],
        "neutral_monism": [0.0, 0.0, 0.0, 0.0, 0.8, 0.1, 0.1, 0.0],
        "non_reductionism": [0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.1, 0.1],
    }
    # Default spectrum if category not found
    default = [0.125] * 8
    cat_key = category.lower().replace("-", "_").replace(" ", "_")
    return spectrums.get(cat_key, default)


@router.post("/consciousness_demo", response_model=ConsciousnessDemoResponse)
async def consciousness_demo(body: ConsciousnessDemoRequest) -> ConsciousnessDemoResponse:
    """Generate CGP packets from consciousness theories.

    This endpoint loads the Kuhn Landscape consciousness taxonomy and generates
    CGP (Constellation Geometry Protocol) packets for visualization.

    - **theory_category**: Filter by category (materialism, dualism, panpsychism, etc.)
    - **max_theories**: Maximum number of theories to return (default: 10)
    - **output_format**: Response format - 'json' (theories only), 'cgp' (packets only), 'both'
    """
    taxonomy = _load_taxonomy()
    theories, categories = _extract_theories(
        taxonomy,
        category_filter=body.theory_category,
        max_theories=body.max_theories
    )

    if not theories:
        raise HTTPException(
            status_code=404,
            detail=f"No theories found for category: {body.theory_category}"
        )

    response = ConsciousnessDemoResponse(
        theories=theories,
        total_theories=len(theories),
        categories_available=categories,
    )

    if body.output_format in ("cgp", "both"):
        cgp_packets = []
        shape_ids = []
        for idx, theory in enumerate(theories):
            cgp = _theory_to_cgp(theory, idx)
            cgp_packets.append(cgp)
            # Optionally ingest to shape store
            try:
                shape_id = ingest_cgp(cgp)
                shape_ids.append(shape_id)
            except Exception as exc:
                logger.warning("Failed to ingest CGP for %s: %s", theory.name, exc)
                shape_ids.append(f"error:{theory.name}")

        response.cgp_packets = cgp_packets
        response.shape_ids = shape_ids

    return response


@router.get("/consciousness_categories")
async def list_consciousness_categories() -> Dict[str, Any]:
    """List available consciousness theory categories."""
    taxonomy = _load_taxonomy()
    categories = {}
    for cat_key, cat_data in taxonomy.get("categories", {}).items():
        cat_id = cat_data.get("id", cat_key)
        theory_count = sum(
            len(subcat.get("theories", []))
            for subcat in cat_data.get("subcategories", {}).values()
        )
        categories[cat_id] = {
            "name": cat_key.replace("_", " "),
            "description": cat_data.get("description", ""),
            "theory_count": theory_count,
            "subcategories": list(cat_data.get("subcategories", {}).keys()),
        }
    return {
        "categories": categories,
        "total_categories": len(categories),
        "source": taxonomy.get("source", {}),
    }
