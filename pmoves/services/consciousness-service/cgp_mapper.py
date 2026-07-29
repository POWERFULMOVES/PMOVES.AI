"""
CGP Auto-Mapper: Transform consciousness theories into Constellation Geometry Protocol packets.

This module maps theories from the consciousness taxonomy into geometric representations
for Hi-RAG v2 indexing and retrieval.

Features:
- Zeta spectral filtering for CGP spectrum optimization
- Multi-scale spectral analysis
- Harmonic weighting using Riemann zeta zeros
"""

import os
import logging
import math
from datetime import datetime
from typing import Any, Dict, List

import httpx

from pmoves.chit import CGP_SPEC_VERSION

from chr_algorithm import chit_signature_required, get_chit_signing_key, sign_cgp

# Zeta filter for spectral analysis
try:
    from pmoves.tools.zeta_filter import (
        ZetaInspiredFilter,
        analyze_spectrum,
        optimize_spectrum_scale,
    )
    ZETA_FILTER_AVAILABLE = True
except ImportError:
    ZETA_FILTER_AVAILABLE = False
    logging.warning("zeta_filter not available - spectral filtering disabled")

logger = logging.getLogger(__name__)

# Configuration
HIRAG_V2_URL = os.environ.get("HIRAG_V2_URL", "http://hi-rag-gateway-v2:8086")
GEOMETRY_EVENT_ENDPOINT = f"{HIRAG_V2_URL}/geometry/event"

# Zeta filter configuration
ZETA_NUM_ZEROS = int(os.environ.get("ZETA_NUM_ZEROS", "10"))
ZETA_DECAY_FACTOR = float(os.environ.get("ZETA_DECAY_FACTOR", "0.9"))
ZETA_ENABLED = os.environ.get("ZETA_FILTER_ENABLED", "true").lower() == "true"


class CGPMapper:
    """
    Transform consciousness theories into CGP (Constellation Geometry Protocol) packets.

    Maps theoretical dimensions to geometric coordinates, applies constellation anchoring,
    and publishes to Hi-RAG v2 for knowledge graph integration.
    """

    def __init__(self):
        """Initialize the CGP mapper with geometric configuration."""
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("CGPMapper initialized")

    async def close(self):
        """Close HTTP client resources."""
        await self.client.aclose()

    def theory_to_constellation(self, theory: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map theory dimensions to geometric coordinates using constellation anchoring.

        Args:
            theory: Dictionary containing theory metadata with fields:
                - name: Theory name
                - proponents: List of proponents
                - description: Text description
                - category: Taxonomy category
                - subcategory: Taxonomy subcategory

        Returns:
            CGP v1.0 format packet (chit.cgp.v1.0) with geometric coordinates and metadata
        """
        name = theory.get("name", "Unknown Theory")
        proponents = theory.get("proponents", [])
        description = theory.get("description", "")
        category = theory.get("category", "unknown")
        subcategory = theory.get("subcategory", "")

        # Derive geometric dimensions from theory characteristics
        empirical = self._calculate_empirical_support(name, proponents, description)
        coherence = self._calculate_philosophical_coherence(description, category)
        integration = self._calculate_integration_potential(category, subcategory)

        # Map 3D theory space to spherical coordinates
        radius = empirical * 10.0
        phi = coherence * 2 * math.pi
        theta = integration * math.pi

        # Convert spherical to Cartesian coordinates
        x = radius * math.sin(theta) * math.cos(phi)
        y = radius * math.sin(theta) * math.sin(phi)
        radius * math.cos(theta)

        theory_id = f"{category}:{name.lower().replace(' ', '_')}"

        # Calculate spectrum for this constellation (3D dimensions → 3-value spectrum)
        raw_spectrum = [
            round(empirical, 4),  # Dimension 1: empirical support
            round(coherence, 4),  # Dimension 2: philosophical coherence
            round(integration, 4),  # Dimension 3: integration potential
        ]

        # Normalize spectrum to sum to 1.0 (probability distribution)
        spectrum_sum = sum(raw_spectrum)
        if spectrum_sum > 0:
            spectrum = [round(s / spectrum_sum, 4) for s in raw_spectrum]
        else:
            spectrum = [0.333, 0.333, 0.334]  # Equal distribution

        # Apply zeta spectral filtering if enabled
        zeta_analysis = None
        if ZETA_ENABLED and ZETA_FILTER_AVAILABLE:
            try:
                zeta_filter = ZetaInspiredFilter(
                    num_zeros=ZETA_NUM_ZEROS,
                    decay_factor=ZETA_DECAY_FACTOR
                )
                zeta_analysis = zeta_filter.analyze_spectrum(spectrum)
                # Use zeta-filtered spectrum as the anchor (preserves harmonic structure)
                zeta_analysis["filtered"]

                # Add zeta metadata to packet
                zeta_meta = {
                    "zeta_filter_enabled": True,
                    "zeta_num_zeros": ZETA_NUM_ZEROS,
                    "entropy": zeta_analysis["entropy"],
                    "concentration": zeta_analysis["concentration"],
                    "dominant_index": zeta_analysis["dominant_index"],
                }
                logger.debug(f"Applied zeta filtering to {theory_id}: entropy={zeta_analysis['entropy']:.4f}")
            except Exception as e:
                logger.warning(f"Zeta filtering failed for {theory_id}: {e}")
                zeta_meta = {"zeta_filter_enabled": False, "error": "processing failed"}
        else:
            zeta_meta = {"zeta_filter_enabled": False}

        cgp_packet = {
            "spec": CGP_SPEC_VERSION,
            "summary": f"Consciousness Theory: {name} ({category})",
            "created_at": datetime.now(timezone.utc).isoformat() + "Z",
            "super_nodes": [
                {
                    "id": f"consciousness_{category}",
                    "label": "Consciousness Theory",
                    "summary": f"Theory cluster for {category} consciousness theories",
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "r": round(radius, 4),
                    "constellations": [
                        {
                            "id": theory_id,
                            "summary": description[:200] if description else f"{name} theory",
                            "anchor": spectrum,  # 3D spectrum as anchor
                            "spectrum": spectrum,
                            "points": [
                                {
                                    "id": f"{theory_id}_proponents",
                                    "modality": "text",
                                    "proj": round(min(len(proponents) * 0.1, 1.0), 4),
                                    "conf": 0.9,
                                    "summary": f"Proponents: {', '.join(proponents[:3])}" + ("..." if len(proponents) > 3 else ""),
                                }
                            ],
                            "meta": {
                                "namespace": "consciousness",
                                "category": category,
                                "subcategory": subcategory,
                                "theory_name": name,
                            }
                        }
                    ]
                }
            ],
            "meta": {
                "source": "consciousness-service.theory.v1",
                "tags": ["consciousness", "theory", category],
                "hyperbolic_encoding": {
                    "space": "poincare_disk",
                    "curvature": -1,
                },
                "zeta_analysis": zeta_meta,
            }
        }

        logger.debug(f"Generated CGP packet for theory {theory_id}")
        return cgp_packet

    def _calculate_empirical_support(
        self, name: str, proponents: List[str], description: str
    ) -> float:
        """Calculate empirical support score (0-1) based on theory characteristics."""
        score = 0.5
        score += min(len(proponents) * 0.05, 0.2)
        empirical_keywords = [
            "experimental",
            "evidence",
            "data",
            "neural",
            "brain",
            "measurement",
            "observation",
            "empirical",
            "neuroscience",
        ]
        keyword_count = sum(
            1 for kw in empirical_keywords if kw.lower() in description.lower()
        )
        score += min(keyword_count * 0.03, 0.15)
        return min(score, 1.0)

    def _calculate_philosophical_coherence(
        self, description: str, category: str
    ) -> float:
        """Calculate philosophical coherence score (0-1)."""
        score = 0.5
        if len(description) > 100:
            score += 0.1
        if len(description) > 200:
            score += 0.1
        rigor_keywords = [
            "theory",
            "framework",
            "principle",
            "argument",
            "logic",
            "coherent",
            "consistent",
            "systematic",
        ]
        keyword_count = sum(
            1 for kw in rigor_keywords if kw.lower() in description.lower()
        )
        score += min(keyword_count * 0.04, 0.2)
        return min(score, 1.0)

    def _calculate_integration_potential(
        self, category: str, subcategory: str
    ) -> float:
        """Calculate integration potential score (0-1)."""
        score = 0.5
        integrative_categories = ["relational", "embodied", "quantum", "holistic"]
        if any(ic in category.lower() for ic in integrative_categories):
            score += 0.2
        if "computational" in category.lower() or "information" in category.lower():
            score += 0.15
        return min(score, 1.0)

    def _calculate_constellation_anchor(
        self, x: float, y: float, z: float, category: str
    ) -> str:
        """Calculate constellation anchor point for theory clustering."""
        x_bucket = int(x / 2.0) * 2
        y_bucket = int(y / 2.0) * 2
        z_bucket = int(z / 2.0) * 2
        return f"{category}_{x_bucket}_{y_bucket}_{z_bucket}"

    async def publish_to_hirag(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish CGP packet to Hi-RAG v2 geometry event endpoint.

        Args:
            packet: CGP v1.0 format packet (chit.cgp.v1.0)

        Returns:
            Response from Hi-RAG v2 API

        Raises:
            RuntimeError: If CHIT_REQUIRE_SIGNATURE is set and no signing key is available
        """
        # CHIT-sign at the publish boundary (single choke point for
        # /cgp/publish, /cgp/batch and batch_publish). Empty key = dev mode,
        # unsigned with a warning, unless fail-closed is switched on.
        signing_key = get_chit_signing_key()
        if signing_key:
            packet = sign_cgp(packet, passphrase=signing_key)
        elif chit_signature_required():
            raise RuntimeError(
                "CHIT_REQUIRE_SIGNATURE is set but no signing key is available "
                "(set CHIT_SIGNING_KEY or CHIT_PASSPHRASE)"
            )
        else:
            logger.warning("No CHIT signing key set — publishing CGP unsigned (dev mode)")
        try:
            response = await self.client.post(
                GEOMETRY_EVENT_ENDPOINT,
                json=packet,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"Published CGP packet for theory {packet['super_nodes'][0]['constellations'][0]['id']} to Hi-RAG v2"
            )
            return result
        except httpx.HTTPError as e:
            logger.error(f"Failed to publish CGP packet to Hi-RAG v2: {e}")
            raise

    async def batch_publish(
        self, theories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process and publish multiple theories as CGP packets."""
        results = []
        for theory in theories:
            try:
                packet = self.theory_to_constellation(theory)
                result = await self.publish_to_hirag(packet)
                results.append(
                    {
                        "theory_id": packet["super_nodes"][0]["constellations"][0]["id"],
                        "status": "success",
                        "result": result,
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to process theory {theory.get('name', 'unknown')}: {e}"
                )
                results.append(
                    {
                        "theory_id": theory.get("name"),
                        "status": "error",
                        "error": "processing failed",
                    }
                )
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(
            f"Batch published {len(results)} theories ({success_count} successful)"
        )
        return results
