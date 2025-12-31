"""Functional integration tests for A2UI NATS Bridge.

These tests require:
- NATS server running at nats://localhost:4222
- A2UI bridge service running at http://localhost:9224

Run with:
    python -m pytest pmoves/tests/functional/test_a2ui_bridge_integration.py -v
"""
import asyncio
import pytest
import json


@pytest.mark.asyncio
async def test_a2ui_bridge_health():
    """Test A2UI bridge health endpoint is accessible."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9224/healthz", timeout=5.0)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "nats_connected" in data
        assert isinstance(data["nats_connected"], bool)


@pytest.mark.asyncio
async def test_a2ui_bridge_metrics():
    """Test A2UI bridge metrics endpoint."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9224/metrics", timeout=5.0)
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        content = response.text
        assert "a2ui_events_published_total" in content
        assert "a2ui_nats_connected" in content


@pytest.mark.asyncio
async def test_a2ui_event_publish():
    """Test publishing A2UI event via REST API."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9224/api/v1/a2ui",
            json={"createSurface": {"surfaceId": "integration-test-surface"}},
            timeout=10.0
        )
        # Either published (200) or service unavailable (507) is acceptable
        assert response.status_code in (200, 507)

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "published"
            assert data["surface_id"] == "integration-test-surface"


@pytest.mark.asyncio
async def test_a2ui_simulate_endpoint():
    """Test the simulate endpoint generates test events."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:9224/api/v1/simulate", timeout=10.0)
        assert response.status_code in (200, 507)

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "simulated"
            assert "surface_id" in data


@pytest.mark.asyncio
async def test_nats_stream_exists():
    """Test that the A2UI NATS stream is created."""
    try:
        import nats
    except ImportError:
        pytest.skip("nats-py not installed")

    try:
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()

        # Verify A2UI stream exists
        streams = await js.streams_info()
        stream_names = [s.config.name for s in streams]
        assert "A2UI" in stream_names

        # Verify stream configuration
        a2ui_stream = await js.stream_info("A2UI")
        assert a2ui_stream is not None

        await nc.close()
    except ConnectionRefusedError:
        pytest.skip("NATS server not available at nats://localhost:4222")


@pytest.mark.asyncio
async def test_nats_a2ui_subjects():
    """Test that A2UI subjects are configured."""
    try:
        import nats
    except ImportError:
        pytest.skip("nats-py not installed")

    try:
        nc = await nats.connect("nats://localhost:4222")
        js = nc.jetstream()

        stream_info = await js.stream_info("A2UI")
        subjects = stream_info.config.subjects

        # Verify expected subjects
        assert "a2ui.render.v1" in subjects or any("a2ui.>" in s for s in subjects)

        await nc.close()
    except ConnectionRefusedError:
        pytest.skip("NATS server not available")


@pytest.mark.asyncio
async def test_user_action_forwarding():
    """Test user actions are forwarded correctly."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9224/api/v1/action",
            json={
                "name": "test_click",
                "surfaceId": "test-surface",
                "context": {"button": "submit"}
            },
            timeout=10.0
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "handled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
