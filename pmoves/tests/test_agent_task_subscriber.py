"""Tests for the Mavis harness node-side worker (agent_task_subscriber).

Wire contract only -- matching, envelope shape, handler loading. No
NATS server required (the transport is exercised live on-node).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PMOVES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PMOVES_DIR.parent))

from pmoves.tools.agent_task_subscriber import (  # noqa: E402
    AgentTaskSubscriber,
    SUBJECT_RESULT,
    SUBJECT_TASK,
    default_handler,
    load_handler,
)


def _envelope(target="glm-5.1", alias="kiloclaw", task="wire the spark subscriber"):
    return {
        "task_id": "test-task-1",
        "target": target,
        "target_alias": alias,
        "task": task,
        "context": {},
        "bootstrap_id": "bs-1",
        "issued_at": 1.0,
    }


class TestMatching:
    def test_matches_wire_target(self):
        sub = AgentTaskSubscriber("glm-5.1", ["kiloclaw"], default_handler, "url")
        assert sub._addresses_me(_envelope())

    def test_matches_alias(self):
        sub = AgentTaskSubscriber("glm-5.1", ["kiloclaw"], default_handler, "url")
        assert sub._addresses_me(_envelope(target="something-else"))

    def test_rejects_foreign_target(self):
        sub = AgentTaskSubscriber("mavis", [], default_handler, "url")
        assert not sub._addresses_me(_envelope())

    def test_mavis_self_target(self):
        sub = AgentTaskSubscriber("mavis", [], default_handler, "url")
        assert sub._addresses_me(_envelope(target="mavis", alias="mavis"))

    def test_empty_alias_list_matches_nothing_extra(self):
        sub = AgentTaskSubscriber("hermes-3", [], default_handler, "url")
        assert not sub._addresses_me(_envelope(target="", alias="hermes"))


class TestHandler:
    def test_default_handler_acknowledges(self):
        out = default_handler(_envelope())
        assert out.startswith("acknowledged by default handler")

    def test_load_builtin_handler(self):
        fn = load_handler(
            "pmoves.tools.agent_task_subscriber:default_handler"
        )
        assert fn is default_handler

    def test_load_handler_rejects_bad_spec(self):
        with pytest.raises(SystemExit):
            load_handler("no-colon-here")

    def test_custom_handler_output_flows_to_result(self):
        def shout(env):
            return f"SHOUT:{env['task']}"

        sub = AgentTaskSubscriber("mavis", [], shout, "url")
        env = _envelope(target="mavis", alias="mavis")
        assert sub.handler(env) == f"SHOUT:{env['task']}"


class TestSubjects:
    def test_subjects_match_orchestrator(self):
        # The worker must listen and publish on exactly the subjects the
        # dispatcher (pmoves/tools/orchestrator.py) uses.
        from pmoves.tools.orchestrator import (
            SUBJECT_RESULT as ORCH_RESULT,
            SUBJECT_TASK as ORCH_TASK,
        )

        assert SUBJECT_TASK == ORCH_TASK
        assert SUBJECT_RESULT == ORCH_RESULT


class TestProfileWire:
    """kiloclaw.yaml must keep describing the harness subjects."""

    def test_profile_declares_harness_subjects(self):
        import yaml

        profile = yaml.safe_load(
            (PMOVES_DIR / "configs" / "agent-profiles" / "kiloclaw.yaml").read_text()
        )
        subs = profile["nats"]["subscribe"]
        pubs = profile["nats"]["publish"]
        assert SUBJECT_TASK in subs, "kiloclaw must subscribe to the dispatch subject"
        assert SUBJECT_RESULT in pubs, "kiloclaw must publish results"

    def test_profile_affinity_includes_portable_node(self):
        import yaml

        profile = yaml.safe_load(
            (PMOVES_DIR / "configs" / "agent-profiles" / "kiloclaw.yaml").read_text()
        )
        assert "laptop-4090" in profile["node_affinity"]

    def test_routing_example_names_both_nodes(self):
        text = (
            PMOVES_DIR
            / "contracts"
            / "schemas"
            / "pmoves-bootstrap"
            / "example.cgp.yaml"
        ).read_text()
        assert "laptop-4090" in text, (
            "routing.kiloclaw comment must acknowledge the portable node"
        )

    def test_schema_kiloclaw_examples(self):
        schema = json.loads(
            (
                PMOVES_DIR
                / "contracts"
                / "schemas"
                / "pmoves-bootstrap"
                / "v1.schema.json"
            ).read_text()
        )
        kiloclaw = schema["properties"]["routing"]["properties"]["kiloclaw"]
        assert "laptop-4090" in kiloclaw["properties"]["node"]["examples"]
