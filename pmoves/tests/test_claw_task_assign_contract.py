"""claw.task.assign.v1 is registered and its schema matches the documented payload.

Before registration, POST /events/publish with this topic was an unhandled
KeyError -> HTTP 500 (node 5090, 2026-11-23). Payload shape:
.claude/context/nats-subjects.md, "CLAW Agent Delegation Subjects".
"""

import pytest
from jsonschema import ValidationError

from services.common import events

TOPIC = "claw.task.assign.v1"
DOCUMENTED = {
    "from": "pmoves-4090",
    "to": "pmoves-spark",
    "task": "cascade-wave-B",
    "files_released": ["pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md"],
    "after_pr": [1504, 1506, 1507],
    "note": "Wave A complete. SPARK may open feat/spark-tz-glm5-minimax-sync PRs.",
}


def test_topic_is_registered():
    assert TOPIC in events.known_topics()
    assert events.schema_path(TOPIC).replace("\\", "/").endswith(
        "schemas/claw/task.assign.v1.schema.json"
    )


def test_documented_payload_validates_and_envelopes():
    assert events.validate_payload(TOPIC, DOCUMENTED) == DOCUMENTED
    env = events.envelope(TOPIC, {"from": "a", "to": "b", "task": "t"}, source="test")
    assert env["topic"] == TOPIC


@pytest.mark.parametrize("missing", ["from", "to", "task"])
def test_required_fields(missing):
    payload = {k: v for k, v in DOCUMENTED.items() if k != missing}
    with pytest.raises(ValidationError):
        events.validate_payload(TOPIC, payload)


@pytest.mark.parametrize(
    "bad",
    [
        {"after_pr": ["1504"]},
        {"files_released": [1]},
        {"note": 7},
        {"unexpected": True},
    ],
)
def test_optional_field_types_and_no_extra_fields(bad):
    with pytest.raises(ValidationError):
        events.validate_payload(TOPIC, {"from": "a", "to": "b", "task": "t", **bad})
