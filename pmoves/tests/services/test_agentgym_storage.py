#!/usr/bin/env python3
"""
Unit Tests for AgentGym Supabase Storage.

Tests the SupabaseStorage:
- get_stats returns dict
- Storage initialization
- Client creation
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../services/agentgym-rl-coordinator")
)

from coordinator import SupabaseStorage


# ============================================================================
# Test SupabaseStorage
# ============================================================================

class TestSupabaseStorage:
    """Test Supabase storage functionality"""

    @pytest.fixture
    def storage(self):
        """Create a test storage instance"""
        return SupabaseStorage(
            supabase_url="http://localhost:3010",
            supabase_key="test-key",
        )

    def test_storage_initialization(self, storage):
        """Storage should initialize with correct attributes"""
        assert storage.supabase_url == "http://localhost:3010"
        assert storage.supabase_key == "test-key"

    @pytest.mark.asyncio
    async def test_get_stats_returns_dict(self, storage):
        """get_stats should return a dictionary"""
        with patch.object(storage, "_get_client") as mock_client_class:
            # Create a mock client instance
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            # Mock the HTTP response
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [], "count": 0}
            mock_client.get.return_value = mock_resp

            stats = await storage.get_stats()
            assert isinstance(stats, dict)

    @pytest.mark.asyncio
    async def test_close(self, storage):
        """close should cleanup resources"""
        # Should not raise any exceptions
        await storage.close()
