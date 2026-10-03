"""Unit tests for the persona_consumption CLI producer."""

from __future__ import annotations

import argparse

from pmoves.tools.persona_consumption import SUBJECT, build_event


def _args(**overrides):
    base = {
        "agent": "crush-spark",
        "user": None,
        "kind": "generic",
        "item": "session:start",
        "session": None,
        "domains": "agent-session,third-ref",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_subject_is_versioned():
    assert SUBJECT == "persona.consumption.recorded.v1"


def test_agent_event_shape():
    event = build_event(_args())
    assert event["consumer_kind"] == "agent"
    assert event["agent_id"] == "crush-spark"
    assert event["source"] == "cli"
    assert event["resonance_domains"] == ["agent-session", "third-ref"]
    assert "user_id" not in event


def test_human_event_shape():
    event = build_event(_args(agent=None, user="darkxside", kind="beat",
                              item="808 Low.m4a", domains=None))
    assert event["consumer_kind"] == "human"
    assert event["user_id"] == "darkxside"
    assert "agent_id" not in event
    assert "resonance_domains" not in event


def test_session_id_included_when_given():
    event = build_event(_args(session="abc-123"))
    assert event["session_id"] == "abc-123"
