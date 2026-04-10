"""Tests for NATS handler: message handling, reconnection, dead-letter."""

import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Settings
from models import NATSMessage
from nats_handler import NATSHandler, counters, MockNATSMessage
from neo4j_client import Neo4jClient


@pytest.fixture(autouse=True)
def reset_counters():
    counters.received = 0
    counters.processed = 0
    counters.failed = 0
    counters.dead_lettered = 0


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_connect_creates_client(self, nats_handler):
        with patch("nats_handler.NATSClient") as MockNC:
            mock_nc = AsyncMock()
            mock_nc.connect = AsyncMock()
            MockNC.return_value = mock_nc
            await nats_handler.connect()
            mock_nc.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_raises_when_not_connected(self, nats_handler):
        with pytest.raises(RuntimeError, match="not connected"):
            await nats_handler.subscribe()

    @pytest.mark.asyncio
    async def test_subscribe_to_all_subjects(self, nats_handler):
        mock_nc = AsyncMock()
        mock_nc.subscribe = AsyncMock()
        nats_handler._nc = mock_nc
        await nats_handler.subscribe()
        assert mock_nc.subscribe.call_count == 3
        subjects = [call.args[0] for call in mock_nc.subscribe.call_args_list]
        assert "gen.image.result.v1" in subjects
        assert "analysis.extract_topics.result.v1" in subjects
        assert "kb.upsert.request.v1" in subjects

    @pytest.mark.asyncio
    async def test_close_drains_and_closes(self, nats_handler):
        mock_nc = AsyncMock()
        mock_sub = AsyncMock()
        nats_handler._nc = mock_nc
        nats_handler._subscriptions = [mock_sub]
        await nats_handler.close()
        mock_sub.drain.assert_called_once()
        mock_nc.close.assert_called_once()
        assert nats_handler._nc is None

    @pytest.mark.asyncio
    async def test_close_handles_error(self, nats_handler):
        mock_nc = AsyncMock()
        mock_nc.close.side_effect = Exception("err")
        nats_handler._nc = mock_nc
        nats_handler._subscriptions = []
        await nats_handler.close()
        assert nats_handler._nc is None


class TestConnectionState:
    def test_not_connected_when_no_client(self, nats_handler):
        assert nats_handler.is_connected is False

    def test_connected(self, nats_handler):
        mock_nc = MagicMock()
        mock_nc.is_connected = True
        nats_handler._nc = mock_nc
        assert nats_handler.is_connected is True

    def test_disconnected(self, nats_handler):
        mock_nc = MagicMock()
        mock_nc.is_connected = False
        nats_handler._nc = mock_nc
        assert nats_handler.is_connected is False


class TestMessageRouting:
    @pytest.mark.asyncio
    async def test_handle_gen_image(self, nats_handler, neo4j_client, gen_image_envelope):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(json.dumps(gen_image_envelope).encode(), "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.received == 1
        assert counters.processed == 1
        assert counters.failed == 0

    @pytest.mark.asyncio
    async def test_handle_analysis_topics(self, nats_handler, neo4j_client, analysis_topics_envelope):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(json.dumps(analysis_topics_envelope).encode(), "analysis.extract_topics.result.v1")
        callback = nats_handler._make_callback("analysis.extract_topics.result.v1")
        await callback(msg)
        assert counters.processed == 1

    @pytest.mark.asyncio
    async def test_handle_kb_upsert(self, nats_handler, neo4j_client, kb_upsert_envelope):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(json.dumps(kb_upsert_envelope).encode(), "kb.upsert.request.v1")
        callback = nats_handler._make_callback("kb.upsert.request.v1")
        await callback(msg)
        assert counters.processed == 1


class TestDeadLetter:
    @pytest.mark.asyncio
    async def test_dead_letter_on_failure(self, nats_handler, neo4j_client, gen_image_envelope):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        neo4j_client._driver.session.return_value.__enter__ = MagicMock(
            return_value=MagicMock(execute_write=MagicMock(side_effect=Exception("neo4j down")))
        )
        neo4j_client._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        msg = MockNATSMessage(json.dumps(gen_image_envelope).encode(), "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.failed == 1
        assert counters.dead_lettered == 1
        mock_nc.publish.assert_called_once()
        call_args = mock_nc.publish.call_args
        dl_data = json.loads(call_args.args[1])
        assert dl_data["original_subject"] == "gen.image.result.v1"
        assert "neo4j down" in dl_data["error"]

    @pytest.mark.asyncio
    async def test_dead_letter_when_nats_down(self, nats_handler, neo4j_client, gen_image_envelope):
        nats_handler._nc = None
        neo4j_client._driver.session.return_value.__enter__ = MagicMock(
            return_value=MagicMock(execute_write=MagicMock(side_effect=Exception("fail")))
        )
        neo4j_client._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        msg = MockNATSMessage(json.dumps(gen_image_envelope).encode(), "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.failed == 1


class TestCounters:
    def test_snapshot(self):
        counters.received = 10
        counters.processed = 8
        counters.failed = 2
        counters.dead_lettered = 1
        snap = counters.snapshot()
        assert snap["nats_messages_received"] == 10
        assert snap["nats_messages_processed"] == 8
        assert snap["nats_messages_failed"] == 2
        assert snap["nats_messages_dead_lettered"] == 1
