"""claw.task.assign.v1 is registered and its schema matches the documented payload.

Before registration, POST /events/publish with this topic was an unhandled
KeyError -> HTTP 500 (node 5090, 2026-11-23). Payload shape:
.claude/context/nats-subjects.md, "CLAW Agent Delegation Subjects".

Command-class hardening (security review 2026-11-23): a receiver acts on this
payload, so field sizes are bounded and files_released must be repo-relative.
"""

import pytest
from jsonschema import ValidationError

from services.common import events

TOPIC = "claw.task.assign.v1"
MINIMAL = {"from": "a", "to": "b", "task": "t"}
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
    env = events.envelope(TOPIC, dict(MINIMAL), source="test")
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
        {"after_pr": [0]},
        {"files_released": [1]},
        {"note": 7},
        {"unexpected": True},
    ],
)
def test_optional_field_types_and_no_extra_fields(bad):
    with pytest.raises(ValidationError):
        events.validate_payload(TOPIC, {**MINIMAL, **bad})


@pytest.mark.parametrize(
    "path",
    [
        "../x",
        "a/../b",
        "a/..",
        "..",
        "/etc/passwd",
        "\\\\server\\share",
        "C:/x",
        "c:\\x",
        "a\\..\\b",
        "",
    ],
)
def test_files_released_must_be_repo_relative(path):
    with pytest.raises(ValidationError):
        events.validate_payload(TOPIC, {**MINIMAL, "files_released": [path]})


@pytest.mark.parametrize("path", ["pmoves/docs/x.md", "a..b/c.txt", "README.md"])
def test_files_released_accepts_repo_relative(path):
    events.validate_payload(TOPIC, {**MINIMAL, "files_released": [path]})


@pytest.mark.parametrize(
    "bad",
    [
        {"note": "x" * 2001},
        {"task": "t" * 201},
        {"task": "has space"},
        {"task": "semi;colon"},
        {"task": "slash/path"},
        {"from": "f" * 65},
        {"to": "t" * 65},
    ],
)
def test_field_bounds(bad):
    with pytest.raises(ValidationError):
        events.validate_payload(TOPIC, {**MINIMAL, **bad})


def test_field_bounds_inclusive_limits():
    events.validate_payload(
        TOPIC,
        {"from": "f" * 64, "to": "t" * 64, "task": "T" * 200, "note": "n" * 2000},
    )
