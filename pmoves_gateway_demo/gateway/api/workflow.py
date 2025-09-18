import os
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gateway.api.chit import (
    CGP,
    GeometryDecodeTextRequest,
    geometry_decode_text,
    geometry_calibration_report,
    ingest_cgp,
)


router = APIRouter(prefix="/workflow", tags=["Workflow Demo"])


class DemoRunRequest(BaseModel):
    # If provided, use this CGP payload; otherwise fall back to the test fixture
    cgp: Dict[str, Any] | None = None
    shape_id: str | None = None
    per_constellation: int = 20
    codebook_path: str | None = None


@router.post("/demo_run")
def demo_run(body: DemoRunRequest) -> Dict[str, Any]:
    """Runs an end-to-end offline workflow using CHIT endpoints in-process.

    Stages:
      1) Ingest CGP (persist to `data/{shape_id}.json`)
      2) Decode text (geometry-only; codebook-driven)
      3) Produce calibration report and artifacts
    """

    # 1) Load CGP (fixture if not provided)
    if body.cgp is None:
        fixture = os.path.join("tests", "data", "cgp_fixture.json")
        if not os.path.exists(fixture):
            raise HTTPException(status_code=500, detail="Fixture cgp not found")
        cgp_obj = json.loads(open(fixture, "r", encoding="utf-8").read())
    else:
        cgp_obj = body.cgp

    cgp = CGP.model_validate(cgp_obj)

    # 2) Ingest/persist (shape_id is derived inside the endpoint from payload content)
    shape_id = ingest_cgp(cgp.model_dump())

    # 3) Decode text (geometry-only)
    const_ids = [const.id for sn in cgp.super_nodes for const in sn.constellations if const.id]
    decode_resp = geometry_decode_text(
        GeometryDecodeTextRequest(
            shape_id=shape_id,
            constellation_ids=const_ids,
            per_constellation=body.per_constellation,
            codebook_path=body.codebook_path,
        )
    )

    # 4) Calibration / reconstruction artifacts
    calib = geometry_calibration_report(cgp=cgp)

    # 5) Compose a manifest with helpful links
    manifest = {
        "shape_id": shape_id,
        "data_url": f"/data/{shape_id}.json",
        "artifacts": {
            "reconstruction_report": "/artifacts/reconstruction_report.md",
        },
        "decode": decode_resp,
        "calibration": calib,
        "viz": {
            # Client can POST /viz/constellation.svg with a Constellation object as needed
            "constellation_svg_endpoint": "/viz/constellation.svg",
            "recent": "/viz/recent",
        },
    }
    return manifest
