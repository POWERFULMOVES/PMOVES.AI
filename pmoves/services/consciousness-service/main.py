"""
Consciousness Service - FastAPI Application.

Provides HTTP endpoints for:
1. CHR (Constellation Harvest Regularization) algorithm
2. CGP (Constellation Geometry Protocol) generation
3. Persona threshold evaluation
4. Health monitoring
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import nats
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field

from cgp_mapper import CGPMapper
from chr_algorithm import CHRConfig, CHRResult, chr_result_to_cgp, run_chr
from persona_gate import PersonaGateService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment configuration
SERVICE_NAME = os.environ.get("SERVICE_NAME", "consciousness-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8105"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:pmoves@nats:4222")
CHIT_PASSPHRASE = os.environ.get("CHIT_PROD_PASSPHRASE", "pmoves-chit-default")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://supabase-kong:8000")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Prometheus metrics
cgp_packets_generated = Counter(
    "consciousness_cgp_packets_generated_total",
    "Total CGP packets generated and published",
)
chr_runs_completed = Counter(
    "consciousness_chr_runs_completed_total",
    "Total CHR algorithm runs completed",
)
persona_evaluations = Counter(
    "consciousness_persona_evaluations_total",
    "Total persona threshold evaluations",
)
nats_connected_gauge = Gauge(
    "consciousness_nats_connected",
    "Whether the service is connected to NATS (1=yes, 0=no)",
)


# =============================================================================
# Request/Response Models
# =============================================================================


class TheoryInput(BaseModel):
    """Input model for theory-to-CGP conversion."""

    name: str
    category: str
    subcategory: str = ""
    description: str = ""
    proponents: List[str] = []


class PersonaEvalInput(BaseModel):
    """Input model for persona evaluation."""

    persona_id: str
    metrics: Dict[str, Any]


class TextUnit(BaseModel):
    """A text unit for CHR clustering."""

    id: str
    text: str
    namespace: str = "pmoves.consciousness"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CHRConfigInput(BaseModel):
    """Configuration for CHR algorithm with bounds validation."""

    K: int = Field(default=8, ge=2, le=100, description="Number of constellations (2-100)")
    iters: int = Field(default=30, ge=1, le=1000, description="Optimization iterations (1-1000)")
    bins: int = Field(default=8, ge=2, le=64, description="Spectrum bins for slab entropy (2-64)")
    beta: float = Field(default=12.0, ge=0.1, le=100.0, description="Softmax temperature (0.1-100)")
    seed: int = Field(default=42, ge=0, description="Random seed")


class CHRRequest(BaseModel):
    """Request model for CHR algorithm."""

    units: List[TextUnit] = Field(min_length=1, max_length=10000, description="Text units to cluster (1-10000)")
    config: Optional[CHRConfigInput] = None
    encrypt_anchors: bool = False
    publish_to_nats: bool = True


class CHRResponse(BaseModel):
    """Response model for CHR results."""

    status: str
    shape_id: str
    namespace: str
    K: int
    mhep: float
    Hg: float
    Hs: float
    num_constellations: int
    num_points: int
    cgp: Optional[Dict[str, Any]] = None
    published: bool = False


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    nats_connected: bool = False
    chr_available: bool = False


# =============================================================================
# NATS Publisher
# =============================================================================


class NATSPublisher:
    """NATS publisher for Geometry Bus."""

    def __init__(self, url: str):
        self.url = url
        self.nc: Optional[nats.aio.client.Client] = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to NATS server."""
        try:
            self.nc = await nats.connect(self.url)
            self._connected = True
            logger.info(f"Connected to NATS at {self.url}")
            return True
        except Exception as e:
            logger.warning(f"NATS connection failed: {e}")
            return False

    async def close(self):
        """Close NATS connection."""
        if self.nc:
            try:
                await self.nc.drain()
                logger.info("NATS connection closed")
            except Exception as e:
                logger.warning(f"Error closing NATS: {e}")
            finally:
                self._connected = False

    async def publish_cgp(self, cgp: Dict[str, Any]) -> bool:
        """Publish CGP to Geometry Bus."""
        if not self._connected or not self.nc:
            return False

        try:
            payload = json.dumps(cgp).encode()

            # Publish to geometry bus
            await self.nc.publish("geometry.cgp.v1", payload)
            await self.nc.publish("tokenism.cgp.ready.v1", payload)

            logger.info(f"Published CGP to geometry.cgp.v1: {cgp.get('shape_id', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish CGP: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self._connected


# =============================================================================
# Global service instances
# =============================================================================

cgp_mapper: CGPMapper = None
persona_gate: PersonaGateService = None
nats_publisher: NATSPublisher = None


# =============================================================================
# Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    global cgp_mapper, persona_gate, nats_publisher

    logger.info(f"Starting {SERVICE_NAME}...")

    # Initialize services
    cgp_mapper = CGPMapper()
    persona_gate = PersonaGateService()
    nats_publisher = NATSPublisher(NATS_URL)

    # Connect to NATS
    try:
        await nats_publisher.connect()
    except Exception as e:
        logger.warning(f"NATS connection failed (non-fatal): {e}")

    # Connect persona gate to NATS
    try:
        await persona_gate.connect()
        await persona_gate.subscribe()
        logger.info("Persona gate connected to NATS")
    except Exception as e:
        logger.warning(f"Persona gate NATS connection failed (non-fatal): {e}")

    logger.info(f"{SERVICE_NAME} started successfully")

    yield

    # Cleanup
    logger.info(f"Shutting down {SERVICE_NAME}...")
    if cgp_mapper:
        await cgp_mapper.close()
    if persona_gate:
        await persona_gate.close()
    if nats_publisher:
        await nats_publisher.close()
    logger.info(f"{SERVICE_NAME} shutdown complete")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Consciousness Service",
    description="CHR Algorithm, CGP Auto-Mapper, and Persona Gate evaluation service",
    version="0.2.0",
    lifespan=lifespan,
)


# =============================================================================
# Health & Metrics
# =============================================================================


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return HealthResponse(
        status="healthy",
        service=SERVICE_NAME,
        version="0.2.0",
        nats_connected=nats_publisher.is_connected() if nats_publisher else False,
        chr_available=True,
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    nats_connected_gauge.set(1 if (nats_publisher and nats_publisher.is_connected()) else 0)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# =============================================================================
# CHR Endpoints
# =============================================================================


@app.post("/chr/run", response_model=CHRResponse)
async def run_chr_endpoint(request: CHRRequest):
    """
    Run CHR (Constellation Harvest Regularization) algorithm.

    Clusters text units into constellations and generates CGP packet.
    Optionally publishes to NATS Geometry Bus.
    """
    # Check if we have passphrase
    passphrase = CHIT_PASSPHRASE

    # Build unit dicts
    units = [u.model_dump() for u in request.units]

    # Parse config - Pydantic validation ensures bounds
    config_input = request.config or CHRConfigInput()
    config = CHRConfig(
        K=config_input.K,
        iters=config_input.iters,
        bins=config_input.bins,
        beta=config_input.beta,
        seed=config_input.seed,
    )

    try:
        # Run CHR algorithm
        result = run_chr(units, config=config)

        # Convert to CGP
        cgp = chr_result_to_cgp(
            result,
            passphrase=passphrase,
            encrypt_anchors=request.encrypt_anchors,
        )

        # Publish to NATS if requested
        published = False
        if request.publish_to_nats and nats_publisher:
            published = await nats_publisher.publish_cgp(cgp)

        # Update metrics
        chr_runs_completed.inc()
        if published:
            cgp_packets_generated.inc()

        # Count points
        num_points = sum(len(c.points) for c in result.constellations)

        return CHRResponse(
            status="success",
            shape_id=result.shape_id,
            namespace=result.namespace,
            K=result.K,
            mhep=result.mhep,
            Hg=result.Hg,
            Hs=result.Hs,
            num_constellations=len(result.constellations),
            num_points=num_points,
            cgp=cgp if not published else None,  # Don't include in response if published
            published=published,
        )

    except Exception as e:
        logger.error(f"CHR execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="CHR execution failed") from None


@app.post("/chr/from-supabase")
async def run_chr_from_supabase(
    namespace: str = "pmoves.consciousness",
    K: int = Field(default=8, ge=2, le=100, description="Number of constellations (2-100)"),
    limit: int = Field(default=500, ge=1, le=10000, description="Max theories to fetch (1-10000)"),
    publish: bool = True,
):
    """
    Run CHR on consciousness theories from Supabase.

    Fetches chunks from pmoves_core.consciousness_theories and runs CHR.
    """
    import httpx

    try:
        # Fetch from Supabase via PostgREST with Accept-Profile header
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Accept-Profile": "pmoves_core"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/rest/v1/consciousness_theories",
                headers=headers,
                params={
                    "namespace": f"eq.{namespace}",
                    "limit": str(limit),
                },
            )
            response.raise_for_status()
            theories = response.json()

        if not theories:
            return {"status": "error", "message": "No theories found"}

        # Convert to TextUnits
        units = [
            {
                "id": t["id"],
                "text": t.get("content", t.get("description", t.get("title", ""))),
                "namespace": namespace,
                "metadata": {
                    "title": t.get("title", ""),
                    "category": t.get("category", ""),
                },
            }
            for t in theories
        ]

        # Run CHR
        config = CHRConfig(K=K)
        result = run_chr(units, config=config)

        # Convert to CGP
        passphrase = CHIT_PASSPHRASE
        cgp = chr_result_to_cgp(result, passphrase=passphrase, encrypt_anchors=False)

        # Publish to NATS
        published = False
        if publish and nats_publisher:
            published = await nats_publisher.publish_cgp(cgp)

        # Update metrics
        chr_runs_completed.inc()
        if published:
            cgp_packets_generated.inc()

        return {
            "status": "success",
            "shape_id": result.shape_id,
            "namespace": result.namespace,
            "K": result.K,
            "mhep": result.mhep,
            "num_constellations": len(result.constellations),
            "num_points": sum(len(c.points) for c in result.constellations),
            "published": published,
        }

    except httpx.HTTPError as e:
        logger.error(f"Supabase fetch failed: {e}")
        raise HTTPException(status_code=502, detail="Supabase fetch failed") from None
    except Exception as e:
        logger.error(f"CHR from Supabase failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="CHR execution failed") from None


# =============================================================================
# Original CGP Endpoints (for backward compatibility)
# =============================================================================


@app.post("/cgp/generate")
async def generate_cgp(theory: TheoryInput):
    """
    Generate CGP packet from consciousness theory.

    Maps theory dimensions to geometric coordinates for Hi-RAG v2.
    """
    if not cgp_mapper:
        raise HTTPException(status_code=503, detail="CGP mapper not initialized")

    try:
        theory_dict = theory.model_dump()
        packet = cgp_mapper.theory_to_constellation(theory_dict)
        return {"status": "success", "packet": packet}
    except Exception:
        logger.error("CGP generation failed", exc_info=True)
        raise HTTPException(status_code=500, detail="CGP generation failed") from None


@app.post("/cgp/publish")
async def publish_cgp(theory: TheoryInput):
    """
    Generate and publish CGP packet to Hi-RAG v2.

    Creates geometric representation and sends to knowledge graph.
    """
    if not cgp_mapper:
        raise HTTPException(status_code=503, detail="CGP mapper not initialized")

    try:
        theory_dict = theory.model_dump()
        packet = cgp_mapper.theory_to_constellation(theory_dict)
        result = await cgp_mapper.publish_to_hirag(packet)
        return {"status": "published", "packet": packet, "result": result}
    except Exception:
        logger.error("CGP publish failed", exc_info=True)
        raise HTTPException(status_code=500, detail="CGP publish failed") from None


@app.post("/cgp/batch")
async def batch_publish_cgp(theories: List[TheoryInput]):
    """
    Batch process and publish multiple theories as CGP packets.
    """
    if not cgp_mapper:
        raise HTTPException(status_code=503, detail="CGP mapper not initialized")

    try:
        theory_dicts = [t.model_dump() for t in theories]
        results = await cgp_mapper.batch_publish(theory_dicts)
        return {
            "status": "completed",
            "total": len(results),
            "successful": sum(1 for r in results if r["status"] == "success"),
            "results": results,
        }
    except Exception:
        logger.error("Batch CGP publish failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Batch CGP publish failed") from None


# =============================================================================
# Persona Endpoints (for backward compatibility)
# =============================================================================


@app.post("/persona/evaluate")
async def evaluate_persona(input_data: PersonaEvalInput):
    """
    Evaluate persona against threshold gates.

    Checks metrics against configured thresholds and returns pass/fail.
    """
    if not persona_gate:
        raise HTTPException(status_code=503, detail="Persona gate not initialized")

    try:
        result = await persona_gate.evaluate(input_data.persona_id, input_data.metrics)
        persona_evaluations.inc()
        return result
    except Exception:
        logger.error("Persona evaluation failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Persona evaluation failed") from None


@app.get("/persona/thresholds")
async def get_thresholds():
    """Get current persona evaluation thresholds."""
    if not persona_gate:
        raise HTTPException(status_code=503, detail="Persona gate not initialized")

    return {"thresholds": persona_gate.thresholds}


@app.put("/persona/thresholds")
async def update_thresholds(thresholds: Dict[str, float]):
    """Update persona evaluation thresholds."""
    if not persona_gate:
        raise HTTPException(status_code=503, detail="Persona gate not initialized")

    persona_gate.update_thresholds(thresholds)
    return {"status": "updated", "thresholds": persona_gate.thresholds}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
