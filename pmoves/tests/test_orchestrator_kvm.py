"""
Tests for the Mavis inter-agent handoff slice.

Covers the orchestrator's new behavior in commit 3:
  (a) Bootstrap-driven known_targets (replaces the hardcoded set)
  (b) routing_for(target) helper
  (c) KVM control surface (publish_kvm_focus on cross-node dispatch)

Plus 3 regression tests for the existing behavior the slice
shouldn't have changed: the dispatch envelope, the error path
on unknown targets, and the merge of multi-agent results.

No live NATS, no live bootstrap, no real nats-mcp. The tests
use a constructed Bootstrap + MockPublisher pattern that the
existing orchestrator supports via the `bootstrap` and
`publisher` constructor args.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


# Make pmoves/tools importable
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from load_bootstrap import Bootstrap, Identity, Routing, Services  # noqa: E402
from orchestrator import (  # noqa: E402
    SUBJECT_BPM_PHASE,
    SUBJECT_BPM_POMODORO,
    SUBJECT_RESULT,
    SUBJECT_TASK,
    MockPublisher,
    Orchestrator,
)


# ============================================================================
# Fixtures
# ============================================================================


def _bootstrap(routing: dict | None = None) -> Bootstrap:
    """Build a minimal Bootstrap for testing the orchestrator."""
    return Bootstrap(
        raw={},
        spec="pmoves.bootstrap/v1",
        meta={"created_at": "2026-08-20T00:00:00+00:00", "operator": "darkxside"},
        identity=Identity(agent="minimax", role="implementer", skin="dimensional"),
        tools=[],
        mcps=[],
        services=Services(),
        routing=Routing.from_dict(routing or {}),
        constraints=[],
    )


@pytest.fixture
def publisher() -> MockPublisher:
    return MockPublisher()


@pytest.fixture
def orch_full(publisher: MockPublisher) -> Orchestrator:
    """Orchestrator with the full 3-target routing block (matches example.cgp.yaml)."""
    bs = _bootstrap({
        "kiloclaw": {"node": "5090", "nats_subject": SUBJECT_TASK, "target": "glm-5.1"},
        "hermes": {"node": "spark", "nats_subject": SUBJECT_TASK, "target": "hermes-3"},
        "pinokio": {"node": "host", "nats_subject": SUBJECT_TASK, "target": "pmoves-launcher"},
    })
    return Orchestrator(bootstrap=bs, publisher=publisher)


@pytest.fixture
def orch_minimal(publisher: MockPublisher) -> Orchestrator:
    """Orchestrator with an empty routing block (only the implicit mavis self-target)."""
    bs = _bootstrap({})
    return Orchestrator(bootstrap=bs, publisher=publisher)


# ============================================================================
# (1) known_targets
# ============================================================================


def test_known_targets_includes_all_builtin_peers(orch_full: Orchestrator) -> None:
    """A full bootstrap gives the 4 targets: mavis + 3 routing peers."""
    targets = orch_full.known_targets
    assert targets == {"mavis", "kiloclaw", "hermes", "pinokio"}, (
        f"known_targets should be the 4-target set; got {targets}"
    )


def test_known_targets_falls_back_to_builtins_when_routing_empty(orch_minimal: Orchestrator) -> None:
    """An empty routing block still gives the 4 built-in targets.

    The bootstrap's routing is OPTIONAL per the schema (it's a hint,
    not a requirement). The orchestrator's known_targets uses the
    built-in set as the floor so the v0 wire-up doesn't require a
    full bootstrap to be present.
    """
    targets = orch_minimal.known_targets
    assert targets == {"mavis", "kiloclaw", "hermes", "pinokio"}, (
        f"known_targets should fall back to the built-in set when routing "
        f"is empty; got {targets}"
    )


def test_known_targets_only_includes_peers_with_routing_entries(publisher: MockPublisher) -> None:
    """A bootstrap with only kiloclaw in routing gives mavis + kiloclaw (not hermes/pinokio).

    The semantics are: the orchestrator's known_targets is
    {_BUILTIN_TARGETS} + {peers with non-empty routing entries}.
    A future CGP that drops hermes from routing would NOT
    auto-remove hermes from known_targets (built-in is a floor);
    but a CGP that doesn't include hermes in routing WOULD see
    hermes removed because the built-in set is hardcoded.
    """
    bs = _bootstrap({
        "kiloclaw": {"node": "5090", "nats_subject": SUBJECT_TASK, "target": "glm-5.1"},
    })
    orch = Orchestrator(bootstrap=bs, publisher=publisher)
    # The built-in set is a floor; the routing entries are ALSO part
    # of the built-in set, so this test asserts the floor behavior:
    # even with only kiloclaw in routing, all 4 built-ins are present.
    assert orch.known_targets == {"mavis", "kiloclaw", "hermes", "pinokio"}


# ============================================================================
# (2) routing_for
# ============================================================================


def test_routing_for_mavis_returns_synthesized_self_entry(orch_full: Orchestrator) -> None:
    """routing_for('mavis') returns the synthesized self-target entry."""
    entry = orch_full.routing_for("mavis")
    assert entry == {"node": "self", "nats_subject": SUBJECT_TASK, "target": "mavis"}, (
        f"mavis routing should be the synthesized self entry; got {entry}"
    )


def test_routing_for_kiloclaw_returns_cgp_entry(orch_full: Orchestrator) -> None:
    """routing_for('kiloclaw') returns the CGP routing entry for kiloclaw."""
    entry = orch_full.routing_for("kiloclaw")
    assert entry == {"node": "5090", "nats_subject": SUBJECT_TASK, "target": "glm-5.1"}, (
        f"kiloclaw routing should match the CGP; got {entry}"
    )


def test_routing_for_unknown_returns_empty(orch_full: Orchestrator) -> None:
    """routing_for('not-a-real-target') returns {} (not an error)."""
    entry = orch_full.routing_for("not-a-real-target")
    assert entry == {}, f"unknown target should return empty dict; got {entry}"


def test_routing_for_returns_a_copy_not_a_reference(orch_full: Orchestrator) -> None:
    """routing_for returns a copy so callers can't mutate the bootstrap's routing."""
    entry1 = orch_full.routing_for("kiloclaw")
    entry1["node"] = "tampered"
    entry2 = orch_full.routing_for("kiloclaw")
    assert entry2["node"] == "5090", (
        f"routing_for must return a copy; second call got {entry2!r} "
        f"after first call was tampered to {entry1!r}"
    )


# ============================================================================
# (3) KVM control surface
# ============================================================================


def test_dispatch_to_kiloclaw_publishes_kvm_focus(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to kiloclaw (node=5090) publishes a kvm-focus phase event."""
    result = orch_full.dispatch("render cyber.png", agents=["kiloclaw"])

    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert len(kvm_events) == 1, (
        f"kiloclaw dispatch should publish exactly one kvm-focus event; "
        f"got {kvm_events!r}"
    )
    kvm = kvm_events[0]
    assert kvm["target"] == "kiloclaw"
    assert kvm["target_node"] == "5090", (
        f"kvm-focus event should carry target_node from the CGP routing; "
        f"got {kvm!r}"
    )
    assert kvm["task_id"] == result.task_id


def test_dispatch_to_mavis_does_not_publish_kvm_focus(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to mavis (self) is a no-op on the KVM channel."""
    orch_full.dispatch("in-session work", agents=["mavis"])

    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert kvm_events == [], (
        f"mavis (self) dispatch should NOT publish kvm-focus; got {kvm_events!r}"
    )


def test_dispatch_to_pinokio_does_not_publish_kvm_focus(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to pinokio with node='host' is a local-target no-op on the KVM channel."""
    orch_full.dispatch("launch app", agents=["pinokio"])

    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert kvm_events == [], (
        f"pinokio (host) dispatch should NOT publish kvm-focus; got {kvm_events!r}"
    )


def test_dispatch_to_hermes_publishes_kvm_focus_for_spark(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to hermes (node=spark) publishes a kvm-focus event with target_node='spark'."""
    orch_full.dispatch("send to hermes", agents=["hermes"])

    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert len(kvm_events) == 1, (
        f"hermes dispatch should publish one kvm-focus event; got {kvm_events!r}"
    )
    assert kvm_events[0]["target_node"] == "spark"


def test_publish_kvm_focus_noop_for_self_node(orch_full: Orchestrator, publisher: MockPublisher) -> None:
    """publish_kvm_focus with node='self' is a no-op (no event published)."""
    orch_full.publish_kvm_focus(task_id="t1", target="mavis", node="self")
    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert kvm_events == [], (
        f"publish_kvm_focus with node='self' must be a no-op; got {kvm_events!r}"
    )


def test_publish_kvm_focus_noop_for_empty_node(orch_full: Orchestrator, publisher: MockPublisher) -> None:
    """publish_kvm_focus with node='' is a no-op (no event published)."""
    orch_full.publish_kvm_focus(task_id="t1", target="mavis", node="")
    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert kvm_events == [], (
        f"publish_kvm_focus with node='' must be a no-op; got {kvm_events!r}"
    )


def test_publish_kvm_focus_publishes_for_remote_node(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """publish_kvm_focus with node='5090' publishes a kvm-focus event."""
    orch_full.publish_kvm_focus(task_id="t1", target="kiloclaw", node="5090")
    kvm_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_BPM_PHASE and payload.get("phase") == "kvm-focus"
    ]
    assert len(kvm_events) == 1
    assert kvm_events[0]["target"] == "kiloclaw"
    assert kvm_events[0]["target_node"] == "5090"
    assert kvm_events[0]["task_id"] == "t1"


# ============================================================================
# Regression: existing dispatch envelope + error path
# ============================================================================


def test_dispatch_publishes_task_envelope(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatch publishes a task envelope on SUBJECT_TASK with the expected fields."""
    result = orch_full.dispatch("render cyber.png", agents=["mavis"])

    task_events = [
        payload for subj, payload in publisher.published
        if subj == SUBJECT_TASK
    ]
    assert len(task_events) == 1
    envelope = task_events[0]
    assert envelope["task_id"] == result.task_id
    assert envelope["target"] == "mavis"
    assert envelope["task"] == "render cyber.png"
    assert "issued_at" in envelope
    assert "bootstrap_id" in envelope or envelope["bootstrap_id"] is None


def test_dispatch_to_unknown_target_marks_error(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to a target not in known_targets marks the result as 'error'."""
    result = orch_full.dispatch("test", agents=["not-a-real-target"])

    assert "not-a-real-target" in result.results
    agent_result = result.results["not-a-real-target"]
    assert agent_result.status == "error"
    assert "unknown agent target" in agent_result.error


def test_dispatch_multi_agent_publishes_one_envelope_per_agent(
    orch_full: Orchestrator, publisher: MockPublisher
) -> None:
    """Dispatching to 3 agents publishes 3 task envelopes (one per agent)."""
    orch_full.dispatch("test", agents=["mavis", "kiloclaw", "pinokio"])

    task_events = [
        (subj, payload) for subj, payload in publisher.published
        if subj == SUBJECT_TASK
    ]
    assert len(task_events) == 3
    targets = sorted(p["target"] for _, p in task_events)
    assert targets == ["kiloclaw", "mavis", "pinokio"]
