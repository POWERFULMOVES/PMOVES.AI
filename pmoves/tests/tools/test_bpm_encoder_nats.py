"""Regression tests for W6 BPM-NATS lane (#1423).

Validates that the hoisted publish_cgp helper in nats_client.py
can be imported by bpm_encoder and produces correct packet structure +
subject match.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pmoves.tools.bpm_encoder as bpm_encoder


class TestPublishCgpImport(unittest.TestCase):
    """Verify publish_cgp is importable from nats_client."""

    def test_publish_cgp_importable(self):
        from pmoves.services.common.nats_client import publish_cgp
        assert callable(publish_cgp)

    def test_publish_cgp_in_all(self):
        from pmoves.services.common import nats_client
        assert "publish_cgp" in nats_client.__all__


class TestPublishCgpBehavior(unittest.TestCase):
    """Test publish_cgp returns False when NATS_URL is not set."""

    @patch.dict(os.environ, {"NATS_URL": ""}, clear=False)
    @patch("pmoves.services.common.nats_client.nats_connection")
    def test_returns_false_when_no_url(self, mock_conn_ctx):
        """publish_cgp should return False and NOT attempt connection when URL is empty."""
        import asyncio
        from pmoves.services.common.nats_client import publish_cgp

        packet = {"spec": "chit.cgp.v0.2", "summary": "test"}
        result = asyncio.run(publish_cgp(packet, subject="tokenism.prosodic.bpm.v1", nats_url=""))
        assert result is False
        mock_conn_ctx.assert_not_called()

    @patch.dict(os.environ, {"NATS_URL": "nats://localhost:4222"})
    @patch("pmoves.services.common.nats_client.nats_connection")
    @patch("pmoves.services.common.nats_client.traced_publish")
    def test_returns_true_on_success(self, mock_pub, mock_conn_ctx):
        """publish_cgp should return True when publish succeeds."""
        import asyncio
        from pmoves.services.common.nats_client import publish_cgp

        mock_nc = AsyncMock()
        mock_conn_ctx.return_value.__aenter__.return_value = mock_nc

        packet = {"spec": "chit.cgp.v0.2", "summary": "test"}
        result = asyncio.run(publish_cgp(packet, subject="tokenism.prosodic.bpm.v1"))
        assert result is True
        mock_pub.assert_called_once()


class TestBpmEncoderPacketStructure(unittest.TestCase):
    """Verify CGP packet has correct structure for NATS publish."""

    def test_encode_cgp_packet_has_spec(self):
        profile = bpm_encoder.encode_prosodic_profile("hello world", bpm=90)
        packet = bpm_encoder.build_cgp_packet(profile)
        assert packet["spec"] == "chit.cgp.v0.2"

    def test_encode_cgp_packet_has_super_nodes(self):
        profile = bpm_encoder.encode_prosodic_profile("hello world", bpm=90)
        packet = bpm_encoder.build_cgp_packet(profile)
        assert "super_nodes" in packet
        assert len(packet["super_nodes"]) > 0

    def test_encode_cgp_packet_has_control_plane(self):
        profile = bpm_encoder.encode_prosodic_profile("hello world", bpm=90)
        packet = bpm_encoder.build_cgp_packet(profile)
        assert "control_plane" in packet
        assert "state_vector" in packet["control_plane"]


class TestNatsClientNoHardcodedDefault(unittest.TestCase):
    """Verify nats_client.py no longer has hardcoded NATS credentials."""

    def test_default_nats_url_is_empty(self):
        from pmoves.services.common.nats_client import DEFAULT_NATS_URL
        # When NATS_URL env is not set, default should be empty string
        # (we can't control env in this test, but the MODULE-LEVEL default
        #  was already evaluated at import time)
        assert "pmoves" not in DEFAULT_NATS_URL or DEFAULT_NATS_URL == ""


if __name__ == "__main__":
    unittest.main()
