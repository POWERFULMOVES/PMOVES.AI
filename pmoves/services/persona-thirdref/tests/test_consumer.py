"""Tests for persona-thirdref — mock NATS/Supabase per repo convention."""

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main as thirdref  # noqa: E402


def sample_event(**over):
    event = {
        "consumer_kind": "agent",
        "agent_id": "crush-spark",
        "item_kind": "youtube_video",
        "item_id": "dQw4w9WgXcQ",
        "source": "cli",
        "timestamp": "2026-09-08T18:00:00Z",
    }
    event.update(over)
    return {k: v for k, v in event.items() if v is not None}


class StubJoiner(thirdref.Joiner):
    def __init__(self, row=None):
        super().__init__("http://stub", "key")
        self.row = row if row is not None else {
            "resonance_domain": "ai-ml",
            "resonance_secondary": ["science-philosophy"],
            "persona_signal": "mavis",
            "curriculum_track": "ai-engineering",
        }
        self.asked = []

    def youtube_video(self, video_id):
        self.asked.append(video_id)
        return self.row


class Recorder:
    def __init__(self):
        self.published = []

    async def __call__(self, subject, payload):
        self.published.append((subject, payload))


def test_consumption_schema_accepts_valid_event():
    thirdref.validate_consumption(sample_event())


def test_schema_rejects_missing_item():
    event = sample_event()
    del event["item_id"]
    with pytest.raises(jsonschema.ValidationError):
        thirdref.validate_consumption(event)


def test_human_requires_user_id():
    with pytest.raises(jsonschema.ValidationError):
        thirdref.validate_consumption(sample_event(consumer_kind="human", agent_id=None))


def test_join_merges_enrichment_and_provided_domains():
    joiner = StubJoiner()
    event = sample_event(resonance_domains=["media-creative"])
    domains = thirdref.join_domains(event, joiner)
    assert domains == ["ai-ml", "science-philosophy", "media-creative"]
    assert joiner.asked == [event["item_id"]]


def test_join_degrades_without_joiner():
    domains = thirdref.join_domains(sample_event(), None)
    assert domains == []


def test_trace_shape_is_schema_valid():
    trace = thirdref.build_trace(sample_event(), ["ai-ml"])
    assert trace["interaction_type"] == "media"
    assert trace["resonance_domains"] == ["ai-ml"]
    assert trace["agent_id"] == "crush-spark"
    assert trace["tool_ids"] == ["youtube:dQw4w9WgXcQ"]


def test_trace_beat_modality_is_audio():
    trace = thirdref.build_trace(sample_event(item_kind="beat"), [])
    assert trace["media_modality"] == "audio"


@pytest.mark.asyncio
async def test_handle_emits_trace():
    rec = Recorder()
    svc = thirdref.Service(joiner=StubJoiner(), publisher=rec)
    result = await svc.handle(sample_event())
    assert rec.published[0][0] == "shape.trace.recorded.v1"
    assert result["trace"]["resonance_domains"][0] == "ai-ml"
    assert result["profile"] is None


@pytest.mark.asyncio
async def test_profile_fires_at_threshold():
    rec = Recorder()
    svc = thirdref.Service(joiner=StubJoiner(), publisher=rec,
                           accumulator=thirdref.Accumulator(threshold=3))
    for _ in range(3):
        await svc.handle(sample_event())
    profiles = [p for s, p in rec.published if s == "shape.profile.updated.v1"]
    assert len(profiles) == 1
    weights = profiles[0]["resonance_weights"]
    assert weights["ai-ml"] == pytest.approx(0.5)
    assert weights["science-philosophy"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_human_and_agent_accumulate_separately():
    rec = Recorder()
    svc = thirdref.Service(joiner=StubJoiner(), publisher=rec,
                           accumulator=thirdref.Accumulator(threshold=2))
    await svc.handle(sample_event(consumer_kind="human", user_id="darkxside", agent_id=None))
    await svc.handle(sample_event(consumer_kind="human", user_id="darkxside", agent_id=None))
    profiles = [p for s, p in rec.published if s == "shape.profile.updated.v1"]
    assert len(profiles) == 1
    assert profiles[0]["identity"] == "user:darkxside"
    assert svc.accumulator.events.get("agent:crush-spark", 0) == 0


@pytest.mark.asyncio
async def test_invalid_event_raises():
    svc = thirdref.Service(joiner=StubJoiner(), publisher=Recorder())
    with pytest.raises(jsonschema.ValidationError):
        await svc.handle({"consumer_kind": "agent"})


@pytest.mark.asyncio
async def test_generic_item_carries_caller_domains_only():
    rec = Recorder()
    svc = thirdref.Service(joiner=StubJoiner(), publisher=rec)
    await svc.handle(sample_event(item_kind="generic", item_id="sketch",
                                  resonance_domains=["creative-arts"]))
    assert rec.published[0][1]["resonance_domains"] == ["creative-arts"]


class StubJS:
    """Async JetStream stub for _ensure_stream tests."""

    def __init__(self, existing_subjects=None, exists=True):
        from types import SimpleNamespace
        self.calls = []
        cfg = SimpleNamespace(subjects=list(existing_subjects or []))
        self.info = SimpleNamespace(config=cfg)
        self._exists = exists

    async def stream_info(self, name):
        if not self._exists:
            raise thirdref.NotFoundError("no stream")
        return self.info

    async def update_stream(self, config):
        self.calls.append(("update", sorted(config.subjects)))

    async def add_stream(self, config):
        self.calls.append(("add", sorted(config.subjects), config.name))


@pytest.mark.asyncio
async def test_ensure_stream_creates_when_missing():
    js = StubJS(exists=False)
    await thirdref._ensure_stream(js, "PMOVES-PERSONA")
    kind, subjects, name = js.calls[0]
    assert kind == "add"
    assert subjects == ["persona.consumption.recorded.v1"]
    assert name == "PMOVES-PERSONA"


@pytest.mark.asyncio
async def test_ensure_stream_widens_never_narrows():
    js = StubJS(existing_subjects=["other.subject.v1"])
    await thirdref._ensure_stream(js, "PMOVES-PERSONA")
    kind, subjects = js.calls[0]
    assert kind == "update"
    assert subjects == ["other.subject.v1", "persona.consumption.recorded.v1"]


@pytest.mark.asyncio
async def test_ensure_stream_noop_when_bound():
    js = StubJS(existing_subjects=["persona.consumption.recorded.v1"])
    await thirdref._ensure_stream(js, "PMOVES-PERSONA")
    assert js.calls == []
