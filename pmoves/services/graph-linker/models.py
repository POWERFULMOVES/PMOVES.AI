"""Pydantic models for graph-linker NATS messages and Cypher operations.

Backward-compatible with the original linker.py JSON envelope schema:
    { "topic": str, "id": str, "ts": str, "source": str, "payload": {...} }
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field


def parse_s3(uri: str) -> tuple[Optional[str], Optional[str]]:
    """""""""Parse an s3:// URI into (bucket, key). Returns (None, None) on failure."""""""""
    m = re.match(r"^s3://([^/]+)/(.+)$", uri)
    if not m:
        return None, None
    return m.group(1), m.group(2)


class NATSMessage(BaseModel):
    """""""""Top-level envelope arriving on any NATS subject."""""""""
    topic: str = ""
    id: Optional[str] = None
    ts: Optional[str] = None
    source: str = "unknown"
    payload: dict[str, Any] = Field(default_factory=dict)


class ImageResultMeta(BaseModel):
    public_url: Optional[str] = None
    presigned_url: Optional[str] = None


class ImageResultPayload(BaseModel):
    artifact_uri: Optional[str] = None
    meta: Optional[ImageResultMeta] = None


class GenImageResultMessage(BaseModel):
    """""""""Parsed model for gen.image.result.v1 messages."""""""""
    uri: Optional[str] = None
    bucket: Optional[str] = None
    key: Optional[str] = None
    public_url: Optional[str] = None
    presigned_url: Optional[str] = None
    evt_id: Optional[str] = None
    ts: Optional[str] = None
    source: str = "unknown"

    @classmethod
    def from_envelope(cls, env: NATSMessage) -> "GenImageResultMessage":
        p = env.payload
        uri = p.get("artifact_uri")
        bucket, key = parse_s3(uri) if uri else (None, None)
        meta = p.get("meta") or {}
        return cls(
            uri=uri,
            bucket=bucket,
            key=key,
            public_url=meta.get("public_url"),
            presigned_url=meta.get("presigned_url"),
            evt_id=env.id,
            ts=env.ts,
            source=env.source,
        )


class TopicItem(BaseModel):
    label: str = ""
    score: float = 0.0


class AnalysisTopicsMessage(BaseModel):
    """""""""Parsed model for analysis.extract_topics.result.v1 messages."""""""""
    media_id: str = "unknown"
    topics: list[TopicItem] = Field(default_factory=list)
    ts: Optional[str] = None

    @classmethod
    def from_envelope(cls, env: NATSMessage) -> "AnalysisTopicsMessage":
        p = env.payload
        raw_topics = p.get("topics", [])
        topics = [
            TopicItem(label=t.get("label", ""), score=float(t.get("score", 0.0)))
            for t in raw_topics
        ]
        return cls(
            media_id=p.get("media_id", "unknown"),
            topics=topics,
            ts=env.ts,
        )


class KBItem(BaseModel):
    id: Optional[str] = None
    text: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class KBUpsertMessage(BaseModel):
    """""""""Parsed model for kb.upsert.request.v1 messages."""""""""
    namespace: str = "default"
    items: list[KBItem] = Field(default_factory=list)
    ts: Optional[str] = None

    @classmethod
    def from_envelope(cls, env: NATSMessage) -> "KBUpsertMessage":
        p = env.payload
        raw_items = p.get("items", [])
        items = [
            KBItem(id=x.get("id"), text=x.get("text"), metadata=x.get("metadata"))
            for x in raw_items
        ]
        return cls(
            namespace=p.get("namespace", "default"),
            items=items,
            ts=env.ts,
        )


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "graph-linker"
    version: str = "0.2.0"


class ReadyResponse(BaseModel):
    status: str = "ready"
    neo4j: str = "unknown"
    nats: str = "unknown"
