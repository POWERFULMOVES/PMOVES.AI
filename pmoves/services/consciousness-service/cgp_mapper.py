"""
CGP Auto-Mapper: Transform consciousness theories into Constellation Geometry Protocol packets.

This module maps theories from the consciousness taxonomy into geometric representations
for Hi-RAG v2 indexing and retrieval.
"""

import os
import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# Configuration
HIRAG_V2_URL = os.environ.get("HIRAG_V2_URL", "http://hi-rag-gateway-v2:8086")
GEOMETRY_EVENT_ENDPOINT = f"{HIRAG_V2_URL}/geometry/event"


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
            CGP v1 format packet with geometric coordinates and metadata
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
        z = radius * math.cos(theta)

        theory_id = f"{category}:{name.lower().replace(' ', '_')}"

        cgp_packet = {
            "version": "cgp.v1",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "theory": {
                "id": theory_id,
                "name": name,
                "category": category,
                "subcategory": subcategory,
            },
            "geometry": {
                "coordinates": {
                    "cartesian": {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)},
                    "spherical": {
                        "radius": round(radius, 4),
                        "phi": round(phi, 4),
                        "theta": round(theta, 4),
                    },
                },
                "dimensions": {
                    "empirical_support": round(empirical, 4),
                    "philosophical_coherence": round(coherence, 4),
                    "integration_potential": round(integration, 4),
                },
            },
            "metadata": {
                "description": description,
                "proponents": proponents,
                "constellation_anchor": self._calculate_constellation_anchor(
                    x, y, z, category
                ),
            },
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
            packet: CGP v1 format packet

        Returns:
            Response from Hi-RAG v2 API
        """
        try:
            response = await self.client.post(
                GEOMETRY_EVENT_ENDPOINT,
                json=packet,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                f"Published CGP packet for theory {packet['theory']['id']} to Hi-RAG v2"
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
                        "theory_id": packet["theory"]["id"],
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
                        "error": str(e),
                    }
                )
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(
            f"Batch published {len(results)} theories ({success_count} successful)"
        )
        return results
