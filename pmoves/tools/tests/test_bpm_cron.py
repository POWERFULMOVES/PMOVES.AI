"""Smoke tests for pmoves.tools.bpm_cron.

Mock-based - no NATS, no real timers. The MockPublisher from
orchestrator.py records what the cron publishes; the tests inspect
that and the task's internal state.

Run with:
    python -m pytest pmoves/tools/tests/test_bpm_cron.py -v
or:
    python -m unittest pmoves.tools.tests.test_bpm_cron
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from pmoves.tools.bpm_cron import (  # noqa: E402
    DEFAULT_BLOCKS_PER_PHASE,
    DEFAULT_CHECKIN_MINUTES,
    DEFAULT_WORK_MINUTES,
    BpmCron,
    BpmTask,
    Phase,
    PomodoroBlock,
)
from pmoves.tools.orchestrator import MockPublisher  # noqa: E402


def _make_cron() -> tuple[BpmCron, MockPublisher, BpmTask]:
    pub = MockPublisher()
    cron = BpmCron(publisher=pub)
    task = BpmTask(
        name="test-task",
        description="test",
        agents=["mavis", "kiloclaw"],
    )
    cron.start(task)
    return cron, pub, task


class PhaseEnumTests(unittest.TestCase):
    def test_phase_order(self) -> None:
        order = Phase.order()
        self.assertEqual(
            [p.value for p in order],
            ["define", "assign", "execute", "review", "close"],
        )


class BpmTaskTests(unittest.TestCase):
    def test_default_block_counts(self) -> None:
        task = BpmTask(name="t", description="d")
        for phase in Phase.order():
            self.assertEqual(len(task.blocks[phase.value]), DEFAULT_BLOCKS_PER_PHASE)

    def test_multi_block_per_phase(self) -> None:
        task = BpmTask(name="t", description="d", blocks_per_phase=3)
        for phase in Phase.order():
            self.assertEqual(len(task.blocks[phase.value]), 3)
            for i, block in enumerate(task.blocks[phase.value]):
                self.assertEqual(block.block_index, i)

    def test_default_work_and_checkin(self) -> None:
        task = BpmTask(name="t", description="d")
        for blocks in task.blocks.values():
            for b in blocks:
                self.assertEqual(b.work_minutes, DEFAULT_WORK_MINUTES)
                self.assertEqual(b.checkin_minutes, DEFAULT_CHECKIN_MINUTES)


class StartTests(unittest.TestCase):
    def test_start_publishes_phase_define_started(self) -> None:
        cron, pub, _ = _make_cron()
        phases = [p for s, p in pub.published if s == "pmoves.bpm.phase.v1"]
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0]["phase"], "define")
        self.assertEqual(phases[0]["status"], "started")

    def test_start_publishes_first_pomodoro(self) -> None:
        cron, pub, _ = _make_cron()
        pomos = [p for s, p in pub.published if s == "pmoves.bpm.pomodoro.v1"]
        self.assertEqual(len(pomos), 1)
        self.assertEqual(pomos[0]["status"], "started")
        self.assertEqual(pomos[0]["block_index"], 0)

    def test_start_sets_started_at(self) -> None:
        cron, _, task = _make_cron()
        self.assertGreater(task.started_at, 0)
        self.assertFalse(task.is_closed)
        self.assertEqual(task.current_phase, Phase.DEFINE)


class AdvanceTests(unittest.TestCase):
    def test_advance_moves_to_next_phase(self) -> None:
        cron, _, task = _make_cron()
        cron.advance(task.name)
        self.assertEqual(task.current_phase, Phase.ASSIGN)

    def test_advance_publishes_phase_completed_then_started(self) -> None:
        cron, pub, task = _make_cron()
        cron.advance(task.name)
        phase_events = [p for s, p in pub.published if s == "pmoves.bpm.phase.v1"]
        # Started (define) + Completed (define) + Started (assign) = 3
        self.assertEqual(len(phase_events), 3)
        self.assertEqual(phase_events[1]["status"], "completed")
        self.assertEqual(phase_events[2]["status"], "started")
        self.assertEqual(phase_events[2]["phase"], "assign")

    def test_advance_explicit_to_phase(self) -> None:
        cron, _, task = _make_cron()
        cron.advance(task.name, to_phase=Phase.EXECUTE)
        # Skipped assign, went to execute
        self.assertEqual(task.current_phase, Phase.EXECUTE)

    def test_advance_backwards_rejected(self) -> None:
        cron, _, task = _make_cron()
        cron.advance(task.name, to_phase=Phase.ASSIGN)
        with self.assertRaises(ValueError) as ctx:
            cron.advance(task.name, to_phase=Phase.DEFINE)
        self.assertIn("backwards", str(ctx.exception))

    def test_advance_at_close_closes_task(self) -> None:
        cron, _, task = _make_cron()
        for _ in range(4):  # define -> assign -> execute -> review -> close
            cron.advance(task.name)
        self.assertTrue(task.is_closed)


class CompleteBlockTests(unittest.TestCase):
    def test_complete_block_marks_completed(self) -> None:
        cron, pub, task = _make_cron()
        cron.complete_block(task.name)
        block = task.blocks[Phase.DEFINE.value][0]
        self.assertEqual(block.status, "completed")
        self.assertGreater(block.completed_at, 0)
        pomo_events = [p for s, p in pub.published if s == "pmoves.bpm.pomodoro.v1"]
        self.assertTrue(any(e["status"] == "completed" for e in pomo_events))

    def test_complete_block_advances_phase_when_last_block(self) -> None:
        cron, _, task = _make_cron()  # 1 block per phase
        cron.complete_block(task.name)
        # 1 block per phase, so completing the only block advances
        self.assertEqual(task.current_phase, Phase.ASSIGN)

    def test_complete_block_stays_in_phase_when_more_blocks(self) -> None:
        pub = MockPublisher()
        cron = BpmCron(publisher=pub)
        task = BpmTask(name="multi", description="", blocks_per_phase=2)
        cron.start(task)
        cron.complete_block(task.name)
        # 2 blocks, completed 1, still in define, on block 1
        self.assertEqual(task.current_phase, Phase.DEFINE)
        self.assertEqual(task.current_block, 1)


class RecordDeliverableTests(unittest.TestCase):
    def test_record_and_retrieve(self) -> None:
        cron, _, task = _make_cron()
        cron.record_deliverable(task.name, Phase.DEFINE, "intent: render Pillar 4")
        cron.advance(task.name, to_phase=Phase.ASSIGN)
        cron.record_deliverable(task.name, Phase.ASSIGN, "kiloclaw dispatched")
        status = cron.status(task.name)
        self.assertEqual(status["deliverables"]["define"], "intent: render Pillar 4")
        self.assertEqual(status["deliverables"]["assign"], "kiloclaw dispatched")


class CloseTests(unittest.TestCase):
    def test_close_marks_remaining_blocks_skipped(self) -> None:
        cron, pub, task = _make_cron()
        # Skip ahead to review without completing blocks
        cron.advance(task.name, to_phase=Phase.REVIEW)
        cron.close(task.name)
        # The blocks in define/assign/execute should be skipped
        for phase in (Phase.DEFINE, Phase.ASSIGN, Phase.EXECUTE):
            for block in task.blocks[phase.value]:
                if block.status != "completed":
                    self.assertEqual(block.status, "skipped", f"{phase.value} block not skipped")
        self.assertTrue(task.is_closed)

    def test_close_publishes_phase_completed(self) -> None:
        cron, pub, task = _make_cron()
        for _ in range(4):
            cron.advance(task.name)
        phase_completed = [p for s, p in pub.published if s == "pmoves.bpm.phase.v1" and p["status"] == "completed" and p["phase"] == "close"]
        self.assertEqual(len(phase_completed), 1)


class StatusTests(unittest.TestCase):
    def test_status_includes_all_phases(self) -> None:
        cron, _, task = _make_cron()
        status = cron.status(task.name)
        self.assertEqual(set(status["phases"].keys()), {"define", "assign", "execute", "review", "close"})
        self.assertEqual(status["current_phase"], "define")
        self.assertEqual(status["is_closed"], False)

    def test_status_after_advance(self) -> None:
        cron, _, task = _make_cron()
        cron.advance(task.name)
        status = cron.status(task.name)
        self.assertEqual(status["current_phase"], "assign")

    def test_list_tasks(self) -> None:
        cron, _, _ = _make_cron()
        cron.register(BpmTask(name="second", description=""))
        self.assertEqual(cron.list_tasks(), ["second", "test-task"])


class RejectTests(unittest.TestCase):
    def test_advance_unknown_task_raises(self) -> None:
        pub = MockPublisher()
        cron = BpmCron(publisher=pub)
        with self.assertRaises(KeyError) as ctx:
            cron.advance("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
