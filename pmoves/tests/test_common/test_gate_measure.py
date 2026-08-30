"""Tests for ``pmoves.services.common.gate_measure``.

Covers the syntactic measure (jsonschema), the semantic measure
(TensorZero embedding + Qdrant search via patched HTTP), drift detection
threshold behaviour, and the v2 signature projection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from pmoves.services.common import gate_measure


SIMPLE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["subject", "command"],
    "properties": {
        "subject": {"type": "string"},
        "command": {"type": "string"},
    },
    "additionalProperties": False,
}


def test_syntactic_pass_with_valid_payload() -> None:
    payload = {"subject": "archon.command.issue.v1", "command": "build"}
    with patch.object(gate_measure, "_embed", return_value=None):
        result = gate_measure.measure_junction(
            junction_id="archon.command.issue.v1",
            layer="intent",
            payload=payload,
            schema=SIMPLE_SCHEMA,
            sample_rate=0.0,
        )
    assert result.syntactic_pass is True
    assert result.syntactic_errors == []


def test_syntactic_fail_records_errors() -> None:
    payload = {"command": "build"}  # missing required "subject"
    result = gate_measure.measure_junction(
        junction_id="archon.command.issue.v1",
        layer="intent",
        payload=payload,
        schema=SIMPLE_SCHEMA,
        sample_rate=0.0,
    )
    assert result.syntactic_pass is False
    assert any("subject" in err for err in result.syntactic_errors)
    assert result.drift_flag is False  # drift only fires when syntactic passes


def test_drift_flag_fires_on_low_semantic_score() -> None:
    payload = {"subject": "archon.command.issue.v1", "command": "novel-action"}
    fake_neighbors = [
        {"score": 0.12, "payload": {"phrase_id": "p-1"}},
        {"score": 0.05, "payload": {}},
    ]
    with (
        patch.object(gate_measure, "_embed", return_value=[0.1] * 16),
        patch.object(gate_measure, "_qdrant_search", return_value=fake_neighbors),
        patch.object(gate_measure, "_qdrant_upsert_drift") as upsert,
    ):
        result = gate_measure.measure_junction(
            junction_id="archon.command.issue.v1",
            layer="intent",
            payload=payload,
            schema=SIMPLE_SCHEMA,
            sample_rate=1.0,
            drift_threshold=0.3,
        )
    assert result.syntactic_pass is True
    assert result.semantic_score == pytest.approx(0.12)
    assert result.drift_flag is True
    assert upsert.called, "drift events must be captured to gate_drift_dynamo"


def test_phrase_anchor_populated_above_match_threshold() -> None:
    payload = {"subject": "archon.command.issue.v1", "command": "ship"}
    fake_neighbors = [
        {"score": 0.92, "payload": {"phrase_id": "phrase-canonical-1"}},
        {"score": 0.74, "payload": {"phrase_id": "phrase-canonical-2"}},
        {"score": 0.40, "payload": {"phrase_id": "phrase-not-anchored"}},
    ]
    with (
        patch.object(gate_measure, "_embed", return_value=[0.1] * 16),
        patch.object(gate_measure, "_qdrant_search", return_value=fake_neighbors),
    ):
        result = gate_measure.measure_junction(
            junction_id="archon.command.issue.v1",
            layer="intent",
            payload=payload,
            schema=SIMPLE_SCHEMA,
            sample_rate=1.0,
            phrase_match_threshold=0.7,
        )
    assert result.phrase_anchor == ["phrase-canonical-1", "phrase-canonical-2"]
    assert result.drift_flag is False  # 0.92 > 0.3


def test_sampling_skips_semantic_measure_but_still_passes_syntactic() -> None:
    payload = {"subject": "agent-zero.dispatch.exec.v1", "command": "exec"}
    with patch.object(gate_measure, "_embed") as emb:
        result = gate_measure.measure_junction(
            junction_id="agent-zero.dispatch.exec.v1",
            layer="execution",
            payload=payload,
            schema=SIMPLE_SCHEMA,
            sample_rate=0.0,
        )
    assert result.syntactic_pass is True
    assert result.sampled is False
    assert result.semantic_score == 0.0
    assert result.drift_flag is False
    emb.assert_not_called()


def test_to_signature_fields_projects_v2_keys() -> None:
    measurement = gate_measure.JunctionMeasurement(
        junction_id="agent-graphiti.signature.emitted.v2",
        layer="observation",
        syntactic_pass=True,
        semantic_score=0.55,
        drift_flag=False,
        upstream_intent_id="11111111-2222-3333-4444-555555555555",
        phrase_anchor=["p-1"],
        measurement_id="m-1",
        timestamp="2026-04-25T00:00:00+00:00",
    )
    fields = measurement.to_signature_fields()
    assert set(fields) == {
        "junction_id",
        "layer",
        "syntactic_pass",
        "semantic_score",
        "drift_flag",
        "upstream_intent_id",
        "phrase_anchor",
    }
    assert fields["upstream_intent_id"] == "11111111-2222-3333-4444-555555555555"


def test_drift_event_payload_has_summary() -> None:
    payload = {"subject": "test.subject.v1", "command": "noop"}
    measurement = gate_measure.JunctionMeasurement(
        junction_id="test.junction",
        layer="intent",
        syntactic_pass=True,
        semantic_score=0.05,
        drift_flag=True,
        upstream_intent_id=None,
        phrase_anchor=[],
        measurement_id="m-2",
        timestamp="2026-04-25T00:00:00+00:00",
    )
    event = gate_measure.measurement_to_drift_event(measurement, payload)
    assert event["junction_id"] == "test.junction"
    assert event["drift_flag"] is True
    assert "subject=test.subject.v1" in event["payload_summary"]


def test_empty_neighbors_do_not_trigger_drift_cold_start_guard() -> None:
    """Cold junction: no baseline in Qdrant yet → semantic_score must be 1.0, not 0.0.

    Without the cold-start guard, semantic_score stays at 0.0 which is below
    any realistic drift_threshold, causing every valid payload to false-positive.
    """
    payload = {"subject": "archon.command.issue.v1", "command": "first-ever-action"}
    with (
        patch.object(gate_measure, "_embed", return_value=[0.1] * 16),
        patch.object(gate_measure, "_qdrant_search", return_value=[]),
        patch.object(gate_measure, "_qdrant_upsert_drift") as upsert,
    ):
        result = gate_measure.measure_junction(
            junction_id="archon.command.issue.v1",
            layer="intent",
            payload=payload,
            schema=SIMPLE_SCHEMA,
            sample_rate=1.0,
            drift_threshold=0.3,
        )
    assert result.syntactic_pass is True
    assert result.semantic_score == pytest.approx(1.0)
    assert result.drift_flag is False
    assert result.phrase_anchor == []
    assert not upsert.called, "no drift event should be captured on cold start"
