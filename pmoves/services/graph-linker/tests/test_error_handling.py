"""Tests for error scenarios, dead-letter, and edge cases."""

import json
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Settings
from nats_handler import counters, MockNATSMessage
from neo4j_client import Neo4jClient


@pytest.fixture(autouse=True)
def reset_counters():
    counters.received = 0
    counters.processed = 0
    counters.failed = 0
    counters.dead_lettered = 0


class TestInvalidMessages:
    @pytest.mark.asyncio
    async def test_malformed_json_dead_letter(self, nats_handler, neo4j_client):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(b"not valid json{", "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.failed == 1
        assert counters.dead_lettered == 1
        mock_nc.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_payload_no_crash(self, nats_handler, neo4j_client, mock_neo4j_session):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(json.dumps({"topic": "gen.image.result.v1", "payload": {}}).encode(), "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.processed == 1
        assert counters.failed == 0

    @pytest.mark.asyncio
    async def test_unknown_subject_ok(self, nats_handler, neo4j_client, mock_neo4j_session):
        mock_nc = AsyncMock()
        nats_handler._nc = mock_nc
        msg = MockNATSMessage(json.dumps({"payload": {}}).encode(), "unknown.subject")
        callback = nats_handler._make_callback("unknown.subject")
        await callback(msg)
        assert counters.processed == 1


class TestNeo4jErrors:
    def test_execute_write_reraises(self, neo4j_client, mock_neo4j_session):
        from neo4j.exceptions import Neo4jError
        mock_neo4j_session.execute_write.side_effect = Neo4jError("query failed")
        with pytest.raises(Neo4jError, match="query failed"):
            neo4j_client.execute_write("RETURN 1")

    @pytest.mark.asyncio
    async def test_auth_failure(self, test_settings):
        with patch("neo4j_client.GraphDatabase") as MockGD:
            from neo4j.exceptions import AuthError
            MockGD.driver.return_value.verify_connectivity.side_effect = AuthError("bad")
            client = Neo4jClient(test_settings)
            with pytest.raises(AuthError):
                await client.connect()

    @pytest.mark.asyncio
    async def test_unavailable(self, test_settings):
        with patch("neo4j_client.GraphDatabase") as MockGD:
            from neo4j.exceptions import ServiceUnavailable
            MockGD.driver.return_value.verify_connectivity.side_effect = ServiceUnavailable("down")
            client = Neo4jClient(test_settings)
            with pytest.raises(ServiceUnavailable):
                await client.connect()


class TestNATSErrors:
    @pytest.mark.asyncio
    async def test_connection_failure(self, nats_handler):
        with patch("nats_handler.NATSClient") as MockNC:
            from nats.errors import NoServersError
            mock_nc = AsyncMock()
            mock_nc.connect.side_effect = NoServersError()
            MockNC.return_value = mock_nc
            with pytest.raises(NoServersError):
                await nats_handler.connect()

    @pytest.mark.asyncio
    async def test_dead_letter_publish_failure(self, nats_handler, neo4j_client, gen_image_envelope):
        mock_nc = AsyncMock()
        mock_nc.publish.side_effect = Exception("pub fail")
        nats_handler._nc = mock_nc
        neo4j_client._driver.session.return_value.__enter__ = MagicMock(
            return_value=MagicMock(execute_write=MagicMock(side_effect=Exception("neo4j")))
        )
        neo4j_client._driver.session.return_value.__exit__ = MagicMock(return_value=False)
        msg = MockNATSMessage(json.dumps(gen_image_envelope).encode(), "gen.image.result.v1")
        callback = nats_handler._make_callback("gen.image.result.v1")
        await callback(msg)
        assert counters.failed == 1


class TestMigrationErrors:
    def test_migration_failure_reraises(self, neo4j_client, mock_neo4j_session, tmp_path):
        from neo4j.exceptions import Neo4jError
        mig = tmp_path / "01_fail.cypher"
        mig.write_text("INVALID;")
        neo4j_client._settings = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            migrations_dir=str(tmp_path),
        )
        mock_neo4j_session.run.side_effect = Neo4jError("syntax")
        with pytest.raises(Neo4jError):
            neo4j_client.apply_migrations()


class TestConfigValidation:
    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("NEO4J_URL", "bolt://custom:7687")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")
        monkeypatch.setenv("PORT", "9999")
        s = Settings()
        assert s.neo4j_url == "bolt://custom:7687"
        assert s.neo4j_password == "secret"
        assert s.port == 9999

    def test_defaults(self):
        s = Settings(neo4j_password="test")
        assert s.neo4j_user == "neo4j"
        assert s.port == 8090
        assert len(s.subjects) == 3
