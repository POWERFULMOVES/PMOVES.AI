"""
Consciousness Service - FastAPI Application.

Provides HTTP endpoints for:
1. CGP (Constellation Geometry Protocol) generation from theories
2. Persona threshold evaluation
3. Health monitoring
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cgp_mapper import CGPMapper
from persona_gate import PersonaGateService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environment configuration
SERVICE_NAME = os.environ.get("SERVICE_NAME", "consciousness-service")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", "8096"))


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


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


# Global service instances
cgp_mapper: CGPMapper = None
persona_gate: PersonaGateService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    global cgp_mapper, persona_gate

    logger.info(f"Starting {SERVICE_NAME}...")

    # Initialize services
    cgp_mapper = CGPMapper()
    persona_gate = PersonaGateService()

    # Connect to NATS
    try:
        await persona_gate.connect()
        await persona_gate.subscribe()
        logger.info("Persona gate connected to NATS")
    except Exception as e:
        logger.warning(f"NATS connection failed (non-fatal): {e}")

    logger.info(f"{SERVICE_NAME} started successfully")

    yield

    # Cleanup
    logger.info(f"Shutting down {SERVICE_NAME}...")
    if cgp_mapper:
        await cgp_mapper.close()
    if persona_gate:
        await persona_gate.close()
    logger.info(f"{SERVICE_NAME} shutdown complete")


app = FastAPI(
    title="Consciousness Service",
    description="CGP Auto-Mapper and Persona Gate evaluation service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return HealthResponse(
        status="healthy",
        service=SERVICE_NAME,
        version="0.1.0",
    )


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    # Basic metrics - can be expanded with prometheus_client
    return {
        "service": SERVICE_NAME,
        "cgp_packets_generated": 0,  # TODO: Track actual count
        "persona_evaluations": 0,  # TODO: Track actual count
    }


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
    except Exception as e:
        logger.error(f"CGP generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        logger.error(f"CGP publish failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        logger.error(f"Batch CGP publish failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        return result
    except Exception as e:
        logger.error(f"Persona evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
