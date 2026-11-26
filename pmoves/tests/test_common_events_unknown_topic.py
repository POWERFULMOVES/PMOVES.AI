"""services.common.events: unknown topics raise a typed, KeyError-compatible error."""

import pytest

from services.common import events


def test_unknown_topic_error_is_a_key_error_subclass():
    with pytest.raises(KeyError) as excinfo:
        events.schema_path("no.such.topic.v1")
    assert isinstance(excinfo.value, events.UnknownTopicError)
    assert excinfo.value.topic == "no.such.topic.v1"
    assert "Unknown topic: no.such.topic.v1" in str(excinfo.value)


def test_load_schema_and_validate_share_the_unknown_topic_error():
    with pytest.raises(events.UnknownTopicError):
        events.load_schema("no.such.topic.v1")
    with pytest.raises(events.UnknownTopicError):
        events.validate_payload("no.such.topic.v1", {})


def test_known_topics_is_sorted_and_matches_registry():
    names = events.known_topics()
    assert names == sorted(names)
    assert "chit.economics.usage.v1" in names
    assert events.schema_path("chit.economics.usage.v1").endswith(
        "economics.usage.v1.schema.json"
    )
