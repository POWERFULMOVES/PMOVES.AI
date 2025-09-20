import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from gateway.main import app
from gateway.api import chit
from gateway.api.chit import compute_shape_id
from pmoves.services.common.shape_store import ShapeStore


def _reset_shape_store():
    store = ShapeStore(capacity=256)
    chit.set_shape_store(store)
    app.state.shape_store = store
    chit._shape_to_constellations.clear()  # type: ignore[attr-defined]
    return store


def test_geometry_event_decode_and_jump():
    _reset_shape_store()
    client = TestClient(app)

    cgp = {
        "spec": "chit.cgp.v0.1",
        "meta": {},
        "super_nodes": [
            {
                "id": "sn-1",
                "constellations": [
                    {
                        "id": "const-1",
                        "anchor": [1.0, 0.0, 0.0],
                        "summary": "demo",
                        "radial_minmax": [0.0, 1.0],
                        "spectrum": [0.3, 0.4, 0.3],
                        "points": [
                            {
                                "id": "pt-1",
                                "modality": "video",
                                "ref_id": "yt123",
                                "t_start": 12.5,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    envelope = {"type": "geometry.cgp.v1", "data": cgp}
    resp = client.post("/geometry/event", json=envelope)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    shape_id = compute_shape_id(cgp)
    decode_resp = client.post(
        "/geometry/decode/text",
        json={
            "shape_id": shape_id,
            "constellation_ids": ["const-1"],
            "codebook_path": "tests/data/codebook.jsonl",
        },
    )
    assert decode_resp.status_code == 200
    data = decode_resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)

    jump = client.get("/shape/point/pt-1/jump")
    assert jump.status_code == 200
    locator = jump.json()["locator"]
    assert locator["modality"] == "video"
    assert locator["ref_id"] == "yt123"

    data_path = Path("data") / f"{shape_id}.json"
    if data_path.exists():
        data_path.unlink()
        if not any(Path("data").iterdir()):
            os.rmdir("data")
