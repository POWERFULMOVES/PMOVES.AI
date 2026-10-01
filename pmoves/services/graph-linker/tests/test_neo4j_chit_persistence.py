"""Behavioural tests: graph-linker PERSISTS its CHIT signature and refuses
unsigned writes.

These use only the Neo4jClient / NATSHandler surface, which predates the
fail-closed signer, so they also run against the old code as a
failing-before control. `CHIT_SIGN_NEO4J=true` is set because the old signer
did nothing without it; the new signer ignores it (signing is unconditional).
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (  # noqa: E402
    AnalysisTopicsMessage,
    GenImageResultMessage,
    KBItem,
    KBUpsertMessage,
    TopicItem,
)
from nats_handler import MockNATSMessage, counters  # noqa: E402

CHIT_FIELDS = ("chit_sig", "chit_kid", "chit_signed_at")


@pytest.fixture(autouse=True)
def _sign_flag(monkeypatch):
    monkeypatch.setenv("CHIT_SIGN_NEO4J", "true")


def _tx_calls(session):
    """(cypher, params) for every tx.run the mocked session received."""
    return [(c.args[0], c.kwargs) for c in session.run.call_args_list]


def _assert_persisted(cypher, params, var):
    for field in CHIT_FIELDS:
        assert f"{var}.{field} = ${field}" in cypher, (var, field)
        assert isinstance(params.get(field), str) and params[field], field


class TestSignaturePersisted:
    def test_gen_image_stamps_asset_and_generation(self, neo4j_client, mock_neo4j_session):
        neo4j_client.handle_gen_image_result(GenImageResultMessage(
            uri="s3://b/k.png", bucket="b", evt_id="evt-1",
            ts="2026-01-15T12:00:00Z", source="comfyui-agent",
        ))
        [(cypher, params)] = _tx_calls(mock_neo4j_session)
        _assert_persisted(cypher, params, "a")
        _assert_persisted(cypher, params, "g")

    def test_topics_stamp_media_topic_and_edge(self, neo4j_client, mock_neo4j_session):
        neo4j_client.handle_analysis_topics_result(AnalysisTopicsMessage(
            media_id="m-1", topics=[TopicItem(label="AI", score=0.9)],
            ts="2026-01-15T12:00:00Z",
        ))
        (media_cy, media_p), (topic_cy, topic_p) = _tx_calls(mock_neo4j_session)
        _assert_persisted(media_cy, media_p, "m")
        _assert_persisted(topic_cy, topic_p, "t")
        _assert_persisted(topic_cy, topic_p, "r")

    def test_kb_upsert_stamps_namespace_and_items(self, neo4j_client, mock_neo4j_session):
        neo4j_client.handle_kb_upsert_request(KBUpsertMessage(
            namespace="docs", items=[KBItem(id="kb-1", text="hi")],
            ts="2026-01-15T12:00:00Z",
        ))
        [(cypher, params)] = _tx_calls(mock_neo4j_session)
        _assert_persisted(cypher, params, "ns")
        _assert_persisted(cypher, params, "k")

    def test_no_unused_sig_parameter(self, neo4j_client, mock_neo4j_session):
        neo4j_client.execute_write("RETURN 1", {"x": 1})
        [(_, params)] = _tx_calls(mock_neo4j_session)
        assert "sig" not in params


class TestNoKeyNoWrite:
    def test_execute_write_refused_without_key(
        self, clear_chit_key, neo4j_client, mock_neo4j_driver, mock_neo4j_session,
    ):
        with pytest.raises(Exception):
            neo4j_client.execute_write("RETURN 1", {"x": 1})
        mock_neo4j_session.execute_write.assert_not_called()
        mock_neo4j_session.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_dead_lettered_without_key(
        self, clear_chit_key, nats_handler, mock_neo4j_session, mock_nats_client,
        gen_image_envelope,
    ):
        nats_handler._nc = mock_nats_client
        failed_before = counters.failed
        cb = nats_handler._make_callback("gen.image.result.v1")
        await cb(MockNATSMessage(json.dumps(gen_image_envelope).encode()))
        assert counters.failed == failed_before + 1
        mock_nats_client.publish.assert_awaited_once()
        dead = json.loads(mock_nats_client.publish.await_args.args[1])
        assert "CHIT" in dead["error"]
        mock_neo4j_session.run.assert_not_called()
