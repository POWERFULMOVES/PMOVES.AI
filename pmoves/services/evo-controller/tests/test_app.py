import json
import importlib.util
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("pmoves.services.evo_controller.app", MODULE_PATH)
assert SPEC and SPEC.loader
app = importlib.util.module_from_spec(SPEC)
sys.modules["pmoves.services.evo_controller.app"] = app
SPEC.loader.exec_module(app)

EvoConfig = app.EvoConfig
EvoSwarmController = app.EvoSwarmController


@pytest.mark.asyncio
async def test_tick_publishes_pack_id(monkeypatch):
    config = EvoConfig(rest_url="https://example.supabase.co/rest/v1", service_key=None)
    controller = EvoSwarmController(config)

    server_pack: dict[str, Any] = {
        "id": "pack-123",
        "version": "v20240101-000000",
        "namespace": "pmoves",
        "modality": "video",
        "status": "draft",
        "pack_type": "cg_builder",
        "params": {"K": 8},
        "energy": {"note": "placeholder"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/geometry_cgp_v1"):
            return httpx.Response(200, json=[{"payload": {"namespace": "pmoves"}}])
        if request.method == "POST" and request.url.path.endswith("/geometry_parameter_packs"):
            prefer = request.headers.get("Prefer", "")
            assert "return=representation" in prefer
            body = json.loads(request.content)
            assert isinstance(body, list)
            record = body[0]
            assert record["namespace"] == "pmoves"
            response_record = {**record, **server_pack}
            return httpx.Response(201, json=[response_record])
        raise AssertionError(f"Unexpected request {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    controller._client = httpx.AsyncClient(transport=transport)

    published_requests: list[dict[str, Any]] = []

    class DummyPublishResponse:
        def raise_for_status(self) -> None:  # pragma: no cover - trivial
            return None

    class DummyPublishClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> "DummyPublishClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict[str, Any]) -> DummyPublishResponse:
            published_requests.append(json)
            return DummyPublishResponse()

        async def aclose(self) -> None:  # pragma: no cover - compatibility
            return None

    monkeypatch.setattr(httpx, "AsyncClient", DummyPublishClient)

    await controller._tick()

    await controller._client.aclose()

    assert published_requests, "expected geometry.swarm.meta.v1 publish"
    payload = published_requests[0]["payload"]
    assert payload["pack_id"] == server_pack["id"]
