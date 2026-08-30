"""Tests for Neo4j client: driver management, query execution, migrations."""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Settings
from models import (
    GenImageResultMessage,
    AnalysisTopicsMessage,
    TopicItem,
    KBUpsertMessage,
    KBItem,
)
from neo4j_client import Neo4jClient


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_connect_initializes_driver(self, test_settings):
        with patch("neo4j_client.GraphDatabase") as MockGD:
            mock_driver = MagicMock()
            MockGD.driver.return_value = mock_driver
            client = Neo4jClient(test_settings)
            await client.connect()
            MockGD.driver.assert_called_once()
            mock_driver.verify_connectivity.assert_called_once()
            assert client._driver is mock_driver

    @pytest.mark.asyncio
    async def test_close_destroys_driver(self, neo4j_client, mock_neo4j_driver):
        await neo4j_client.close()
        mock_neo4j_driver.close.assert_called_once()
        assert neo4j_client._driver is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self, neo4j_client, mock_neo4j_driver):
        await neo4j_client.close()
        await neo4j_client.close()
        assert mock_neo4j_driver.close.call_count == 1

    def test_driver_property_raises_when_not_connected(self, test_settings):
        client = Neo4jClient(test_settings)
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = client.driver


class TestHealth:
    def test_healthy_when_connected(self, neo4j_client, mock_neo4j_driver):
        assert neo4j_client.is_healthy() is True

    def test_unhealthy_when_no_driver(self, test_settings):
        client = Neo4jClient(test_settings)
        assert client.is_healthy() is False

    def test_unhealthy_when_connectivity_fails(self, neo4j_client, mock_neo4j_driver):
        from neo4j.exceptions import ServiceUnavailable
        mock_neo4j_driver.verify_connectivity.side_effect = ServiceUnavailable("down")
        assert neo4j_client.is_healthy() is False


class TestQueryExecution:
    def test_execute_write_calls_session(self, neo4j_client, mock_neo4j_session):
        neo4j_client.execute_write("RETURN 1", {"x": 42})
        mock_neo4j_session.execute_write.assert_called()

    def test_execute_write_no_params(self, neo4j_client, mock_neo4j_session):
        neo4j_client.execute_write("RETURN 1")
        mock_neo4j_session.execute_write.assert_called()


class TestMigrations:
    def test_apply_migrations_success(self, neo4j_client, mock_neo4j_session, tmp_path):
        mig = tmp_path / "01_init.cypher"
        mig.write_text("CREATE CONSTRAINT; MERGE (n:Test);")
        neo4j_client._settings = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            migrations_dir=str(tmp_path),
        )
        neo4j_client.apply_migrations()
        assert mock_neo4j_session.run.call_count == 2

    def test_missing_dir(self, neo4j_client, mock_neo4j_session):
        neo4j_client._settings = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            migrations_dir="/nonexistent",
        )
        neo4j_client.apply_migrations()
        mock_neo4j_session.run.assert_not_called()

    def test_empty_dir(self, neo4j_client, mock_neo4j_session, tmp_path):
        neo4j_client._settings = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            migrations_dir=str(tmp_path),
        )
        neo4j_client.apply_migrations()
        mock_neo4j_session.run.assert_not_called()


class TestHandleGenImageResult:
    def test_stores_image(self, neo4j_client, mock_neo4j_session):
        msg = GenImageResultMessage(
            uri="s3://bucket/key.png",
            bucket="bucket",
            key="key.png",
            public_url="https://cdn/x.png",
            evt_id="e1",
            ts="2026-01-15",
            source="agent",
        )
        neo4j_client.handle_gen_image_result(msg)
        mock_neo4j_session.execute_write.assert_called_once()

    def test_skips_no_uri(self, neo4j_client, mock_neo4j_session):
        msg = GenImageResultMessage(uri=None)
        neo4j_client.handle_gen_image_result(msg)
        mock_neo4j_session.execute_write.assert_not_called()


class TestHandleAnalysisTopics:
    def test_stores_topics(self, neo4j_client, mock_neo4j_session):
        msg = AnalysisTopicsMessage(
            media_id="m1",
            topics=[TopicItem(label="AI", score=0.9)],
            ts="2026-01-15",
        )
        neo4j_client.handle_analysis_topics_result(msg)
        assert mock_neo4j_session.execute_write.call_count == 2

    def test_stores_multiple(self, neo4j_client, mock_neo4j_session):
        msg = AnalysisTopicsMessage(
            media_id="m1",
            topics=[TopicItem(label="AI", score=0.9), TopicItem(label="ML", score=0.8)],
            ts="2026-01-15",
        )
        neo4j_client.handle_analysis_topics_result(msg)
        assert mock_neo4j_session.execute_write.call_count == 3

    def test_no_topics(self, neo4j_client, mock_neo4j_session):
        msg = AnalysisTopicsMessage(media_id="m1", topics=[], ts="2026-01-15")
        neo4j_client.handle_analysis_topics_result(msg)
        assert mock_neo4j_session.execute_write.call_count == 1


class TestHandleKBUpsert:
    def test_stores_items(self, neo4j_client, mock_neo4j_session):
        msg = KBUpsertMessage(
            namespace="docs",
            items=[KBItem(id="1", text="hello", metadata={})],
            ts="2026-01-15",
        )
        neo4j_client.handle_kb_upsert_request(msg)
        mock_neo4j_session.execute_write.assert_called_once()

    def test_empty_items(self, neo4j_client, mock_neo4j_session):
        msg = KBUpsertMessage(namespace="docs", items=[], ts="2026-01-15")
        neo4j_client.handle_kb_upsert_request(msg)
        mock_neo4j_session.execute_write.assert_called_once()
