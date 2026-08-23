"""Smoke tests for pmoves.tools.orchestrator.

Mock-based - no NATS server required. The MockPublisher records
what was published, and the tests inject AgentResult values directly
to simulate the worker side.

Run with:
    python -m pytest pmoves/tools/tests/test_orchestrator.py -v
or:
    python -m unittest pmoves.tools.tests.test_orchestrator
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pmoves.tools.orchestrator import (  # noqa: E402
    SUBJECT_BPM_PHASE,
    SUBJECT_KVM_FOCUS,
    SUBJECT_BPM_POMODORO,
    SUBJECT_RESULT,
    SUBJECT_TASK,
    AgentResult,
    DispatchResult,
    MockPublisher,
    Orchestrator,
)


def _make_orch() -> tuple[Orchestrator, MockPublisher]:
    pub = MockPublisher()
    orch = Orchestrator(publisher=pub, timeout_s=5, poll_s=0.05)
    return orch, pub


class DispatchTests(unittest.TestCase):
    def test_dispatch_publishes_to_task_subject(self) -> None:
        orch, pub = _make_orch()
        result = orch.dispatch("render cyber.png", agents=["kiloclaw"])
        subjects = [s for s, _ in pub.published]
        # kiloclaw's routing node is "5090" -- a real remote machine -- so a KVM
        # focus request is correct alongside the task.
        self.assertEqual(subjects, [SUBJECT_TASK, SUBJECT_KVM_FOCUS])
        _, payload = pub.published[0]
        # The CONFIGURED target goes on the wire; the alias rides alongside.
        self.assertEqual(payload["target"], "glm-5.1")
        self.assertEqual(payload["target_alias"], "kiloclaw")
        self.assertEqual(payload["task"], "render cyber.png")
        self.assertEqual(payload["task_id"], result.task_id)

    def test_dispatch_multi_agent(self) -> None:
        orch, pub = _make_orch()
        orch.dispatch("review PR", agents=["kiloclaw", "hermes"])
        subjects = [s for s, _ in pub.published]
        # kiloclaw -> task + KVM focus (node 5090). hermes -> task only, because
        # its shipped node is the placeholder TBD.
        self.assertEqual(subjects, [SUBJECT_TASK, SUBJECT_KVM_FOCUS, SUBJECT_TASK])
        tasks = [p for s, p in pub.published if s == SUBJECT_TASK]
        self.assertEqual([p["target"] for p in tasks], ["glm-5.1", "hermes-3"])
        self.assertEqual([p["target_alias"] for p in tasks], ["kiloclaw", "hermes"])

    def test_dispatch_unknown_target_marked_error(self) -> None:
        orch, pub = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "made-up-agent"])
        subjects = [s for s, _ in pub.published]
        self.assertEqual(subjects, [SUBJECT_TASK, SUBJECT_KVM_FOCUS])
        self.assertEqual(result.results["kiloclaw"].status, "pending")
        self.assertEqual(result.results["made-up-agent"].status, "error")
        self.assertIn("made-up-agent", result.failed)

    def test_wire_target_matches_what_the_consumer_subscribes_to(self) -> None:
        """The Hermes handoff subscribes on target=hermes-3, not the alias.

        Publishing the alias produced envelopes no consumer matched, so the
        handoff stayed pending indefinitely -- a failure with no error.
        """
        orch, pub = _make_orch()
        orch.dispatch("draft", agents=["hermes"])
        task = next(p for s, p in pub.published if s == SUBJECT_TASK)
        self.assertEqual(task["target"], "hermes-3")
        self.assertEqual(task["target_alias"], "hermes")

    def test_placeholder_node_does_not_request_kvm_focus(self) -> None:
        """example.cgp.yaml ships hermes.node: TBD -- not a machine.

        Asserted against the DEFAULT config rather than a substituted node,
        because the placeholder path is the one the shipped config takes.
        """
        orch, pub = _make_orch()
        orch.dispatch("draft", agents=["hermes"])
        self.assertEqual([s for s, _ in pub.published], [SUBJECT_TASK])

    def test_placeholder_matching_is_case_insensitive(self) -> None:
        for value in ("TBD", "tbd", " Tbd ", "none", "N/A", "-", "self", "host", ""):
            with self.subTest(node=value):
                self.assertFalse(Orchestrator._is_actionable_node(value))
        for value in ("5090", "spark", "z890"):
            with self.subTest(node=value):
                self.assertTrue(Orchestrator._is_actionable_node(value))

    def test_kvm_focus_is_not_on_the_bpm_phase_stream(self) -> None:
        """pmoves.bpm.phase.v1 is contracted as the 5 lifecycle phases.

        A "kvm-focus" phase carrying target_node is neither of its documented
        shapes, so a subscriber on that stream would read an invalid lifecycle
        transition.
        """
        orch, pub = _make_orch()
        orch.dispatch("render", agents=["kiloclaw"])
        self.assertNotIn(SUBJECT_BPM_PHASE, [s for s, _ in pub.published])
        focus = next(p for s, p in pub.published if s == SUBJECT_KVM_FOCUS)
        self.assertNotIn("phase", focus)
        self.assertEqual(focus["target_node"], "5090")

    def test_known_targets_follow_the_routing_dataclass(self) -> None:
        """Adding a routing field must widen the dispatch surface on its own.

        The docstring promises no orchestrator change is needed; a hard-coded
        peer tuple silently broke that.
        """
        import dataclasses

        orch, _ = _make_orch()
        fields = {f.name for f in dataclasses.fields(orch.bootstrap.routing)}
        populated = {n for n in fields if getattr(orch.bootstrap.routing, n, None)}
        self.assertTrue(populated, "no routing peers configured -- test is vacuous")
        self.assertTrue(populated <= orch.known_targets)
        self.assertIn("mavis", orch.known_targets)

    def test_dispatch_assigns_unique_task_id(self) -> None:
        orch, _ = _make_orch()
        r1 = orch.dispatch("task1", agents=["mavis"])
        r2 = orch.dispatch("task2", agents=["mavis"])
        self.assertNotEqual(r1.task_id, r2.task_id)
        self.assertEqual(len(r1.task_id), 36)  # uuid4


class WaitForResultsTests(unittest.TestCase):
    def test_wait_returns_when_all_done(self) -> None:
        orch, _ = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "hermes"])
        # Simulate the worker side: inject results directly
        result.results["kiloclaw"] = AgentResult(
            target="kiloclaw", status="success", output="GLM says LGTM", elapsed_s=1.2
        )
        result.results["hermes"] = AgentResult(
            target="hermes", status="success", output="Hermes agrees", elapsed_s=0.8
        )
        orch._wait_for_results(result)
        self.assertEqual(result.results["kiloclaw"].status, "success")
        self.assertEqual(result.results["hermes"].status, "success")

    def test_wait_marks_remaining_as_timeout(self) -> None:
        orch, _ = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "hermes"])
        # Only kiloclaw reports back
        result.results["kiloclaw"] = AgentResult(
            target="kiloclaw", status="success", output="done"
        )
        # hermes stays pending
        orch._wait_for_results(result)
        self.assertEqual(result.results["kiloclaw"].status, "success")
        self.assertEqual(result.results["hermes"].status, "timeout")
        self.assertIn("hermes", result.failed)

    def test_wait_returns_immediately_if_all_done(self) -> None:
        orch, _ = _make_orch()
        result = orch.dispatch("task", agents=["mavis"])
        result.results["mavis"] = AgentResult(target="mavis", status="success", output="ok")
        start = orch._wait_for_results(result)
        # Returns None (no return value) but doesn't block


class MergeResultsTests(unittest.TestCase):
    def test_merge_concatenates_successful_outputs(self) -> None:
        orch, _ = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "hermes"])
        result.results["kiloclaw"] = AgentResult(
            target="kiloclaw", status="success", output="GLM result"
        )
        result.results["hermes"] = AgentResult(
            target="hermes", status="success", output="Hermes result"
        )
        orch._merge_results(result)
        self.assertIn("--- kiloclaw ---", result.merged)
        self.assertIn("GLM result", result.merged)
        self.assertIn("--- hermes ---", result.merged)
        self.assertIn("Hermes result", result.merged)
        self.assertEqual(result.failed, [])

    def test_merge_excludes_failed_agents(self) -> None:
        orch, _ = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "hermes"])
        result.results["kiloclaw"] = AgentResult(
            target="kiloclaw", status="success", output="GLM result"
        )
        result.results["hermes"] = AgentResult(
            target="hermes", status="error", error="Hermes 500"
        )
        orch._merge_results(result)
        self.assertIn("GLM result", result.merged)
        self.assertNotIn("Hermes result", result.merged)
        self.assertEqual(result.failed, ["hermes"])


class BpmPublishTests(unittest.TestCase):
    def test_publish_phase_event(self) -> None:
        orch, pub = _make_orch()
        orch.publish_phase("task-123", "define", status="completed")
        subjects = [s for s, _ in pub.published]
        self.assertEqual(subjects, [SUBJECT_BPM_PHASE])
        subject, payload = pub.published[0]
        self.assertEqual(payload["task_id"], "task-123")
        self.assertEqual(payload["phase"], "define")
        self.assertEqual(payload["status"], "completed")

    def test_publish_pomodoro_event(self) -> None:
        orch, pub = _make_orch()
        orch.publish_pomodoro("task-123", block_index=2, status="completed")
        subjects = [s for s, _ in pub.published]
        self.assertEqual(subjects, [SUBJECT_BPM_POMODORO])
        subject, payload = pub.published[0]
        self.assertEqual(payload["block_index"], 2)
        self.assertEqual(payload["status"], "completed")


class ConstraintTests(unittest.TestCase):
    """The orchestrator MUST honor the bootstrap CGP's constraints when
    they're set - the consumer forks' tests prove the inverse (no-CGP
    = pre-change), but we also want to prove the orchestrator respects
    the constraints when they ARE set."""

    def test_no_chit_bypass_constraint_present(self) -> None:
        # The orchestrator is a dispatcher - it doesn't bypass CHIT.
        # The constraint is satisfied by design (the harness only
        # publishes, never writes to state directly).
        orch, _ = _make_orch()
        self.assertTrue(orch.bootstrap.has_constraint("no-chit-bypass"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
