"""Tests for beats_to_voice NATS push model."""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import beats_to_voice


class TestNatsPublishCgp(unittest.IsolatedAsyncioTestCase):
    async def test_publish_success(self):
        """_nats_publish_cgp returns True when nats connects and publishes."""
        mock_nc = AsyncMock()
        mock_nats = MagicMock()
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        with patch.dict("sys.modules", {"nats": mock_nats}):
            result = await beats_to_voice._nats_publish_cgp({"spec": "chit.cgp.v0.2"})

        assert result is True
        mock_nc.publish.assert_awaited_once()
        mock_nc.drain.assert_awaited_once()
        subject_used = mock_nc.publish.call_args[0][0]
        assert subject_used == beats_to_voice.NATS_SUBJECT

    async def test_publish_nats_unavailable(self):
        """_nats_publish_cgp returns False when nats-py is not installed."""
        with patch.dict("sys.modules", {"nats": None}):
            result = await beats_to_voice._nats_publish_cgp({"spec": "chit.cgp.v0.2"})
        assert result is False


class TestListenHandler(unittest.IsolatedAsyncioTestCase):
    async def test_handler_runs_pipeline_and_publishes(self):
        """Listen handler calls run_pipeline with response_text and uses configured agent_id."""
        mock_nc = AsyncMock()
        mock_nats = MagicMock()
        mock_nats.connect = AsyncMock(return_value=mock_nc)

        msg = MagicMock()
        msg.data = json.dumps({
            "response_text": "Hello from Agent Zero",
            "user_id": "z890-claude",  # originator — should NOT become agent_id
        }).encode("utf-8")

        called = {}
        subscribed = asyncio.Event()

        def fake_pipeline(**kwargs):
            called.update(kwargs)
            return {"cgp_packet": {"spec": "chit.cgp.v0.2", "id": "test-id"}}

        captured_handlers: list = []

        async def fake_subscribe(subject, cb):
            captured_handlers.append(cb)
            subscribed.set()

        mock_nc.subscribe = fake_subscribe
        mock_nc.drain = AsyncMock()

        with patch.dict("sys.modules", {"nats": mock_nats}):
            with patch.object(beats_to_voice, "run_pipeline", side_effect=fake_pipeline):
                task = asyncio.create_task(
                    beats_to_voice._listen_loop(
                        "nats://localhost:4222",
                        "voice.agent.response.v1",
                        "default",
                        "4090-claude",
                        "http://localhost:8055",
                    )
                )
                await asyncio.wait_for(subscribed.wait(), timeout=2.0)
                await captured_handlers[0](msg)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        assert called.get("text") == "Hello from Agent Zero"
        assert called.get("agent_id") == "4090-claude"  # configured agent_id, not user_id
        mock_nc.publish.assert_awaited()


class TestRunPipelinePublishNats(unittest.TestCase):
    def test_publish_nats_false_by_default(self):
        """run_pipeline with publish_nats=False does not set nats_published key."""
        with patch.object(beats_to_voice, "_check_flute_health", return_value=False):
            results = beats_to_voice.run_pipeline(
                text="test text", bpm=90, publish_nats=False
            )
        assert "nats_published" not in results["stages"]["cgp"]

    def test_publish_nats_true_sets_key(self):
        """run_pipeline with publish_nats=True sets nats_published in cgp stage."""
        with patch.object(beats_to_voice, "_check_flute_health", return_value=False):
            with patch.object(beats_to_voice, "_nats_publish_cgp", new=AsyncMock(return_value=True)):
                results = beats_to_voice.run_pipeline(
                    text="test text", bpm=90, publish_nats=True
                )
        assert results["stages"]["cgp"]["nats_published"] is True


if __name__ == "__main__":
    unittest.main()
