"""Tests for Pydantic model validation and envelope parsing."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import (
    NATSMessage,
    GenImageResultMessage,
    AnalysisTopicsMessage,
    KBUpsertMessage,
    KBItem,
    TopicItem,
    HealthResponse,
    ReadyResponse,
    parse_s3,
)


class TestParseS3:
    def test_valid_s3_uri(self):
        bucket, key = parse_s3("s3://my-bucket/path/to/file.png")
        assert bucket == "my-bucket"
        assert key == "path/to/file.png"

    def test_valid_deep_path(self):
        bucket, key = parse_s3("s3://bucket/a/b/c/d/e.txt")
        assert bucket == "bucket"
        assert key == "a/b/c/d/e.txt"

    def test_invalid_no_scheme(self):
        bucket, key = parse_s3("/local/path/file.txt")
        assert bucket is None
        assert key is None

    def test_invalid_empty(self):
        bucket, key = parse_s3("")
        assert bucket is None
        assert key is None

    def test_invalid_no_key(self):
        bucket, key = parse_s3("s3://bucket/")
        assert bucket is None
        assert key is None

    def test_invalid_no_path_after_bucket(self):
        bucket, key = parse_s3("s3://bucket")
        assert bucket is None
        assert key is None


class TestNATSMessage:
    def test_full_envelope(self):
        data = {
            "topic": "gen.image.result.v1",
            "id": "evt-001",
            "ts": "2026-01-15T12:00:00Z",
            "source": "agent-x",
            "payload": {"key": "value"},
        }
        msg = NATSMessage.model_validate(data)
        assert msg.topic == "gen.image.result.v1"
        assert msg.id == "evt-001"
        assert msg.source == "agent-x"
        assert msg.payload == {"key": "value"}

    def test_minimal_envelope(self):
        msg = NATSMessage.model_validate({})
        assert msg.topic == ""
        assert msg.id is None
        assert msg.source == "unknown"
        assert msg.payload == {}

    def test_from_json_bytes(self):
        raw = json.dumps({"topic": "test", "id": "123", "payload": {"x": 1}}).encode()
        msg = NATSMessage.model_validate_json(raw)
        assert msg.topic == "test"
        assert msg.payload["x"] == 1


class TestGenImageResultMessage:
    def test_from_envelope_full(self, gen_image_envelope):
        env = NATSMessage.model_validate(gen_image_envelope)
        msg = GenImageResultMessage.from_envelope(env)
        assert msg.uri == "s3://pmoves-images/gen/abc123.png"
        assert msg.bucket == "pmoves-images"
        assert msg.key == "gen/abc123.png"
        assert msg.public_url == "https://cdn.pmoves.ai/gen/abc123.png"
        assert msg.presigned_url == "https://s3.aws.com/signed?token=xyz"
        assert msg.evt_id == "evt-001"
        assert msg.source == "comfyui-agent"

    def test_from_envelope_no_uri(self):
        env = NATSMessage.model_validate({"topic": "gen.image.result.v1", "payload": {}})
        msg = GenImageResultMessage.from_envelope(env)
        assert msg.uri is None
        assert msg.bucket is None

    def test_from_envelope_invalid_s3(self):
        env = NATSMessage.model_validate({"payload": {"artifact_uri": "not-s3"}})
        msg = GenImageResultMessage.from_envelope(env)
        assert msg.uri == "not-s3"
        assert msg.bucket is None

    def test_from_envelope_no_meta(self):
        env = NATSMessage.model_validate({"payload": {"artifact_uri": "s3://b/k"}})
        msg = GenImageResultMessage.from_envelope(env)
        assert msg.uri == "s3://b/k"
        assert msg.public_url is None


class TestAnalysisTopicsMessage:
    def test_from_envelope_full(self, analysis_topics_envelope):
        env = NATSMessage.model_validate(analysis_topics_envelope)
        msg = AnalysisTopicsMessage.from_envelope(env)
        assert msg.media_id == "media-456"
        assert len(msg.topics) == 2
        assert msg.topics[0].label == "AI"
        assert msg.topics[0].score == 0.95

    def test_empty_topics(self):
        env = NATSMessage.model_validate({"payload": {"media_id": "m1", "topics": []}})
        msg = AnalysisTopicsMessage.from_envelope(env)
        assert msg.topics == []

    def test_missing_media_id(self):
        env = NATSMessage.model_validate({"payload": {}})
        msg = AnalysisTopicsMessage.from_envelope(env)
        assert msg.media_id == "unknown"


class TestKBUpsertMessage:
    def test_from_envelope_full(self, kb_upsert_envelope):
        env = NATSMessage.model_validate(kb_upsert_envelope)
        msg = KBUpsertMessage.from_envelope(env)
        assert msg.namespace == "docs"
        assert len(msg.items) == 2
        assert msg.items[0].id == "kb-001"

    def test_empty_items(self):
        env = NATSMessage.model_validate({"payload": {"namespace": "test"}})
        msg = KBUpsertMessage.from_envelope(env)
        assert msg.items == []

    def test_default_namespace(self):
        env = NATSMessage.model_validate({"payload": {}})
        msg = KBUpsertMessage.from_envelope(env)
        assert msg.namespace == "default"


class TestHealthModels:
    def test_health_defaults(self):
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.service == "graph-linker"
        assert resp.version == "0.2.0"

    def test_ready_defaults(self):
        resp = ReadyResponse()
        assert resp.status == "ready"
        assert resp.neo4j == "unknown"
        assert resp.nats == "unknown"
