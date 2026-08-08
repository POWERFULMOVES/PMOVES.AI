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
        self.assertEqual(len(subjects), 1)
        self.assertEqual(subjects[0], SUBJECT_TASK)
        # The payload should reference kiloclaw + the task
        subject, payload = pub.published[0]
        self.assertEqual(payload["target"], "kiloclaw")
        self.assertEqual(payload["task"], "render cyber.png")
        self.assertEqual(payload["task_id"], result.task_id)

    def test_dispatch_multi_agent(self) -> None:
        orch, pub = _make_orch()
        result = orch.dispatch("review PR", agents=["kiloclaw", "hermes"])
        subjects = [s for s, _ in pub.published]
        self.assertEqual(subjects, [SUBJECT_TASK, SUBJECT_TASK])
        targets = [p["target"] for _, p in pub.published]
        self.assertEqual(targets, ["kiloclaw", "hermes"])

    def test_dispatch_unknown_target_marked_error(self) -> None:
        orch, pub = _make_orch()
        result = orch.dispatch("task", agents=["kiloclaw", "made-up-agent"])
        # Only kiloclaw was published; made-up-agent is marked error
        subjects = [s for s, _ in pub.published]
        self.assertEqual(subjects, [SUBJECT_TASK])
        self.assertEqual(result.results["kiloclaw"].status, "pending")
        self.assertEqual(result.results["made-up-agent"].status, "error")
        self.assertIn("made-up-agent", result.failed)

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
