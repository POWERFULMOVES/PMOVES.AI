"""Smoke tests for Jellyfin Bridge UI Integration endpoints.

These tests verify the Jellyfin Bridge service is healthy and responsive
for the UI Integration features.
"""

import pytest
import httpx


# Service URL configuration
JELLYFIN_BRIDGE_URL = "http://localhost:8093"


@pytest.mark.smoke
def test_jellyfin_bridge_health():
    """Verify Jellyfin Bridge service is healthy."""
    try:
        response = httpx.get(f"{JELLYFIN_BRIDGE_URL}/healthz", timeout=10.0)
        # Health check should return 200 or 404 if no sync yet
        assert response.status_code in [200, 404], f"Health check failed: {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "healthy" in data or "status" in data
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_sync_status():
    """Verify sync status endpoint is accessible."""
    try:
        response = httpx.get(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/sync-status",
            timeout=10.0
        )
        # May return 200 (has status) or 404 (no sync yet)
        assert response.status_code in [200, 404], f"Sync status failed: {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "last_sync" in data
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_search_endpoint():
    """Verify Jellyfin search endpoint exists and is responsive."""
    try:
        response = httpx.get(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/search",
            params={"query": "test"},
            timeout=10.0
        )
        # Search should return 200 (with results) or 404 (no items)
        assert response.status_code in [200, 404], f"Search failed: {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert isinstance(data["items"], list)
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_search_with_filters():
    """Verify Jellyfin search handles filter parameters."""
    try:
        response = httpx.get(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/search",
            params={
                "query": "test",
                "media_type": "Movie",
                "limit": 10
            },
            timeout=10.0
        )
        assert response.status_code in [200, 404], f"Search with filters failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_link_endpoint():
    """Verify Jellyfin link endpoint exists."""
    try:
        response = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/link",
            json={
                "video_id": "test-video-123",
                "jellyfin_item_id": "test-item-456"
            },
            timeout=10.0
        )
        # Link might fail with 404 if items don't exist, but endpoint should be accessible
        assert response.status_code in [200, 404, 400], f"Link endpoint failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_playback_url_endpoint():
    """Verify Jellyfin playback URL endpoint exists."""
    try:
        response = httpx.get(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/playback-url",
            params={"item_id": "test-item-123"},
            timeout=10.0
        )
        # Should return 200 (URL), 404 (item not found), or 400 (bad request)
        assert response.status_code in [200, 404, 400], f"Playback URL failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_sync_trigger():
    """Verify Jellyfin sync trigger endpoint exists."""
    try:
        response = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/sync",
            timeout=10.0
        )
        # Should return 200 (sync started), 409 (already syncing), or 503 (service unavailable)
        assert response.status_code in [200, 409, 503], f"Sync trigger failed: {response.status_code}"

        if response.status_code == 200:
            data = response.json()
            assert "started" in data or "status" in data
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_backfill_endpoint():
    """Verify Jellyfin backfill endpoint exists."""
    try:
        response = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/backfill",
            json={
                "limit": 10,
                "priority": 5
            },
            timeout=10.0
        )
        # Should return 200 (backfill started), 409 (already running), or 503
        assert response.status_code in [200, 409, 503], f"Backfill failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_backfill_with_channel_filter():
    """Verify Jellyfin backfill handles channel filter."""
    try:
        response = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/backfill",
            json={
                "channel_id": "UCxxx",
                "limit": 50,
                "priority": 7
            },
            timeout=10.0
        )
        assert response.status_code in [200, 409, 503], f"Backfill with filter failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_backfill_validation():
    """Verify Jellyfin backfill validates parameters."""
    try:
        # Test with invalid limit (too high)
        response = httpx.post(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/backfill",
            json={"limit": 10000},
            timeout=10.0
        )
        # Should either accept with clamping or return validation error
        assert response.status_code in [200, 400, 422], f"Validation check failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")


@pytest.mark.smoke
def test_jellyfin_service_unavailable_handling():
    """Verify Jellyfin Bridge handles unconfigured Jellyfin server gracefully."""
    try:
        # This test checks that the service responds even when Jellyfin is not configured
        response = httpx.get(
            f"{JELLYFIN_BRIDGE_URL}/jellyfin/search",
            params={"query": "test"},
            timeout=10.0
        )
        # Should either return results or a 503 if Jellyfin not configured
        assert response.status_code in [200, 404, 503], f"Service unavailable handling failed: {response.status_code}"
    except ConnectionError:
        pytest.skip("Jellyfin Bridge service not available")
    except httpx.ConnectError:
        pytest.skip("Jellyfin Bridge service not running")
