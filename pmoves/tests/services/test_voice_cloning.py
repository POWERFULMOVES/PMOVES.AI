#!/usr/bin/env python3
"""
Unit Tests for Voice Cloning Provider.

Tests the VoiceCloningProvider and CloningSynthesisProvider:
- Status constants are properly defined
- Health check returns boolean
- Provider initialization with correct parameters
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../services/flute-gateway")
)

from providers.cloning import VoiceCloningProvider, CloningSynthesisProvider


# ============================================================================
# Test VoiceCloningProvider
# ============================================================================

class TestVoiceCloningProvider:
    """Test voice cloning provider functionality"""

    @pytest.fixture
    def provider(self, monkeypatch):
        """Create a test provider instance"""
        monkeypatch.setenv("SUPABASE_URL", "http://localhost:3010")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
        return VoiceCloningProvider(
            supabase_url="http://localhost:3010",
            supabase_key="test-key",
            ultimate_tts_url="http://localhost:7860",
            presign_url="http://localhost:8088",
            nats_client=None,
        )

    def test_status_constants_defined(self):
        """Status constants should be properly defined"""
        assert VoiceCloningProvider.STATUS_PENDING == "pending"
        assert VoiceCloningProvider.STATUS_TRAINING == "training"
        assert VoiceCloningProvider.STATUS_COMPLETED == "completed"
        assert VoiceCloningProvider.STATUS_FAILED == "failed"

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self, provider):
        """Health check should return boolean"""
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value = AsyncMock()
            mock_resp = AsyncMock()
            mock_resp.status_code = 200
            mock_client.return_value.get.return_value = mock_resp
            result = await provider.health_check()
            assert isinstance(result, bool)

    def test_provider_initialization(self):
        """Provider should initialize with correct attributes"""
        provider = VoiceCloningProvider(
            supabase_url="http://localhost:3010",
            supabase_key="test-key",
            ultimate_tts_url="http://localhost:7860",
            presign_url="http://localhost:8088",
            nats_client=None,
        )
        assert provider.supabase_url == "http://localhost:3010"
        assert provider.ultimate_tts_url == "http://localhost:7860"
        assert provider.presign_url == "http://localhost:8088"


# ============================================================================
# Test CloningSynthesisProvider
# ============================================================================

class TestCloningSynthesisProvider:
    """Test cloned voice synthesis provider"""

    def test_synthesis_provider_initialization(self):
        """Synthesis provider should initialize with correct attributes"""
        provider = CloningSynthesisProvider(
            ultimate_tts_url="http://localhost:7860",
            default_model="rvc_test",
        )
        assert provider.ultimate_tts_url == "http://localhost:7860"
        assert provider.default_model == "rvc_test"
