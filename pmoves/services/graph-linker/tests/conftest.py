"""Shared test fixtures for graph-linker test suite."""

from __future__ import annotations

import json
import sys
import os
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Settings
from models import (
    NATSMessage,
    GenImageResultMessage,
    AnalysisTopicsMessage,
    KBUpsertMessage,
)
from neo4j_client import Neo4jClient
from nats_handler import NATSHandler


# -- Test settings -------------------------------------------------------

@pytest.fixture
def test_settings() -> Settings:
    """""""""Return settings with test-friendly defaults."""""""""
    return Settings(
        neo4j_url="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        neo4j_database="test",
        nats_url="nats://nats:pmoves@nats:4222",
        migrations_dir="migrations",
        subjects=[
            "gen.image.result.v1",
            "analysis.extract_topics.result.v1",
            "kb.upsert.request.v1",
        ],
    )


# -- Mock Neo4j ----------------------------------------------------------

@pytest.fixture
def mock_neo4j_session():
    """""""""Create a mock Neo4j session that records executed queries."""""""""
    session = MagicMock()
    session.run = MagicMock(return_value=MagicMock())
    session.execute_write = MagicMock(
        side_effect=lambda fn, *args, **kwargs: fn(session, *args, **kwargs)
        if args else fn(session)
    )
    return session


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    """""""""Create a mock Neo4j driver with a configurable session."""""""""
    driver = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=mock_neo4j_session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    driver.verify_connectivity = MagicMock()
    driver.close = MagicMock()
    return driver


@pytest.fixture
def neo4j_client(test_settings, mock_neo4j_driver) -> Neo4jClient:
    """""""""Create a Neo4jClient with a pre-injected mock driver."""""""""
    client = Neo4jClient(test_settings)
    client._driver = mock_neo4j_driver
    return client


# -- Mock NATS -----------------------------------------------------------

@pytest.fixture
def mock_nats_client():
    """""""""Create a mock NATS client."""""""""
    nc = AsyncMock()
    nc.is_connected = True
    nc.subscribe = AsyncMock()
    nc.publish = AsyncMock()
    nc.close = AsyncMock()
    return nc


@pytest.fixture
def nats_handler(test_settings, neo4j_client):
    """""""""Create a NATSHandler with mock Neo4j client."""""""""
    return NATSHandler(test_settings, neo4j_client)


# -- Sample messages -----------------------------------------------------

@pytest.fixture
def gen_image_envelope() -> dict:
    """""""""Sample gen.image.result.v1 envelope."""""""""
    return {
        "topic": "gen.image.result.v1",
        "id": "evt-001",
        "ts": "2026-01-15T12:00:00Z",
        "source": "comfyui-agent",
        "payload": {
            "artifact_uri": "s3://pmoves-images/gen/abc123.png",
            "meta": {
                "public_url": "https://cdn.pmoves.ai/gen/abc123.png",
                "presigned_url": "https://s3.aws.com/signed?token=xyz",
            },
        },
    }


@pytest.fixture
def analysis_topics_envelope() -> dict:
    """""""""Sample analysis.extract_topics.result.v1 envelope."""""""""
    return {
        "topic": "analysis.extract_topics.result.v1",
        "id": "evt-002",
        "ts": "2026-01-15T12:05:00Z",
        "source": "topic-extractor",
        "payload": {
            "media_id": "media-456",
            "topics": [
                {"label": "AI", "score": 0.95},
                {"label": "generative", "score": 0.82},
            ],
        },
    }


@pytest.fixture
def kb_upsert_envelope() -> dict:
    """""""""Sample kb.upsert.request.v1 envelope."""""""""
    return {
        "topic": "kb.upsert.request.v1",
        "id": "evt-003",
        "ts": "2026-01-15T12:10:00Z",
        "source": "ingest-worker",
        "payload": {
            "namespace": "docs",
            "items": [
                {"id": "kb-001", "text": "Hello world", "metadata": {"page": 1}},
                {"id": "kb-002", "text": "Another doc", "metadata": {"page": 2}},
            ],
        },
    }


# -- FastAPI test client -------------------------------------------------

@pytest.fixture
def app_client() -> Generator[TestClient, None, None]:
    """""""""Create a FastAPI TestClient with mocked external dependencies."""""""""
    with patch("app.Neo4jClient") as MockNeo4j,          patch("app.NATSHandler") as MockNATS,          patch("app.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            neo4j_url="bolt://localhost:7687",
            neo4j_password="test",
            nats_url="nats://nats:pmoves@nats:4222",
        )

        neo4j_inst = MagicMock()
        neo4j_inst.is_healthy.return_value = True
        neo4j_inst.connect = AsyncMock()
        neo4j_inst.close = AsyncMock()
        neo4j_inst.apply_migrations = MagicMock()
        MockNeo4j.return_value = neo4j_inst

        nats_inst = MagicMock()
        nats_inst.is_connected = True
        nats_inst.connect = AsyncMock()
        nats_inst.subscribe = AsyncMock()
        nats_inst.close = AsyncMock()
        MockNATS.return_value = nats_inst

        from app import app
        with TestClient(app) as client:
            yield client
