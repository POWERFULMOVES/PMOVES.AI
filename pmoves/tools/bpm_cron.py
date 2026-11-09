"""bpm_cron.py - PMOVES.AI BPM/pomodoro scheduler.

Redesigned Mavis cron. The old mavis cron was a set of standalone
timers; the new one is a BPM engine where each scheduled item is
a BPM task with 5 phases (define -> assign -> execute -> review ->
close) and pomodoro focus blocks (25-min work + 5-min check-in) per
phase.

Why BPM not just cron:

- The DARKXSIDE-public content pipeline is multi-step (react to a
  video, extract the salient frames, generate a 6-eye-third-eye
  Pillar 4 visual, render through ComfyUI, post to the channel).
  Treating each step as a cron entry loses the cross-step context
  (the rendered visual needs the prompt that drove the previous
  step). BPM keeps the task envelope.
- The public engagement workflow (react -> comment -> share ->
  analyze -> post) maps 1:1 to the 5 BPM phases. The harness
  reads the CGP and the BPM cron, schedules a task, the
  orchestrator dispatches per phase, the operator (or an agent)
  reviews per phase, the cron closes.
- Multi-agent orchestration: a BPM task can be assigned to Mavis
  + KiloClaw + Hermes in parallel per phase. The orchestrator
  merges results per phase; the BPM cron tracks the merged result
  as the phase's deliverable.

NATS subjects (planned v0 contract; align with .claude/context/nats-subjects.md
in the next session):

- pmoves.bpm.phase.v1     - phase start/completed/failed events
- pmoves.bpm.pomodoro.v1 - focus-block start/completed/skipped events

The cron publishes to both. The orchestrator (or any agent) can
subscribe to know when to act.

Pomodoro defaults (per the operator's earlier flag):

- WORK_MINUTES = 25 (focus block)
- CHECKIN_MINUTES = 5 (operator check-in / agent handoff)
- BLOCKS_PER_PHASE = 1 (one focus block per phase; multi-block
  tasks can override per task)

The defaults are env-driven so an operator can shorten the
intervals for a development loop (e.g. 5/1 min for fast iteration).

Usage:

    from pmoves.tools.bpm_cron import BpmCron, BpmTask, MockPublisher
    from pmoves.tools.orchestrator import Orchestrator

    pub = MockPublisher()
    orch = Orchestrator(publisher=pub)
    cron = BpmCron(publisher=pub, work_minutes=25, checkin_minutes=5)

    task = BpmTask(
        name="react-to-video-123",
        description="React to https://youtu.be/abc and generate a Pillar 4 visual",
        agents=["mavis", "kiloclaw"],
    )
    cron.start(task)
    # ... time passes, the cron ticks through phases ...
    cron.advance(task.name, "execute")  # operator check-in
    cron.advance(task.name, "review")
    cron.close(task.name)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol


# ---- Phase model -------------------------------------------------------------


class Phase(str, Enum):
    """The 5 BPM phases. Matches the orchestrator's publish_phase keys."""

    DEFINE = "define"     # capture intent, scope, success criteria
    ASSIGN = "assign"     # dispatch to agents, set up the workspace
    EXECUTE = "execute"   # agents do the work
    REVIEW = "review"     # operator (or an agent) checks the result
    CLOSE = "close"       # archive, mark done, post to NATS

    @classmethod
    def order(cls) -> list["Phase"]:
        return [cls.DEFINE, cls.ASSIGN, cls.EXECUTE, cls.REVIEW, cls.CLOSE]


# ---- Config ------------------------------------------------------------------


DEFAULT_WORK_MINUTES = 25
DEFAULT_CHECKIN_MINUTES = 5
DEFAULT_BLOCKS_PER_PHASE = 1
ENV_WORK_MINUTES = "PMOVES_BPM_WORK_MINUTES"
ENV_CHECKIN_MINUTES = "PMOVES_BPM_CHECKIN_MINUTES"
ENV_BLOCKS_PER_PHASE = "PMOVES_BPM_BLOCKS_PER_PHASE"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---- Task model --------------------------------------------------------------


@dataclass
class PomodoroBlock:
    """A 25-min work + 5-min check-in pair within a phase."""

    block_index: int
    work_minutes: int
    checkin_minutes: int
    started_at: float = 0.0
    completed_at: float = 0.0
    status: str = "pending"  # pending | started | completed | skipped


@dataclass
class BpmTask:
    """A scheduled BPM task with 5 phases and N pomodoro blocks per phase."""

    name: str
    description: str
    agents: list[str] = field(default_factory=lambda: ["mavis"])
    work_minutes: int = DEFAULT_WORK_MINUTES
    checkin_minutes: int = DEFAULT_CHECKIN_MINUTES
    blocks_per_phase: int = DEFAULT_BLOCKS_PER_PHASE
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_phase: Phase = Phase.DEFINE
    current_block: int = 0
    started_at: float = 0.0
    closed_at: float = 0.0
    blocks: dict[str, list[PomodoroBlock]] = field(default_factory=dict)
    deliverables: dict[str, str] = field(default_factory=dict)
    # deliverables maps phase name (e.g. "execute") -> the merged output

    def __post_init__(self) -> None:
        for phase in Phase.order():
            self.blocks.setdefault(phase.value, [
                PomodoroBlock(
                    block_index=i,
                    work_minutes=self.work_minutes,
                    checkin_minutes=self.checkin_minutes,
                )
                for i in range(self.blocks_per_phase)
            ])

    @property
    def is_closed(self) -> bool:
        return self.closed_at > 0

    def current_phase_blocks(self) -> list[PomodoroBlock]:
        return self.blocks.get(self.current_phase.value, [])


# ---- Engine ------------------------------------------------------------------


class BpmCron:
    """The BPM/pomodoro scheduler. Drives tasks through their phases."""

    def __init__(
        self,
        publisher: Any,  # Publisher from orchestrator.py; loose type to avoid circular import
        work_minutes: int | None = None,
        checkin_minutes: int | None = None,
        blocks_per_phase: int | None = None,
    ) -> None:
        self.publisher = publisher
        self.work_minutes = work_minutes or _int_env(ENV_WORK_MINUTES, DEFAULT_WORK_MINUTES)
        self.checkin_minutes = checkin_minutes or _int_env(ENV_CHECKIN_MINUTES, DEFAULT_CHECKIN_MINUTES)
        self.blocks_per_phase = blocks_per_phase or _int_env(ENV_BLOCKS_PER_PHASE, DEFAULT_BLOCKS_PER_PHASE)
        self._tasks: dict[str, BpmTask] = {}

    def register(self, task: BpmTask) -> None:
        self._tasks[task.name] = task

    def start(self, task: BpmTask) -> None:
        """Start a task at the DEFINE phase. Publishes the first pomodoro block."""
        task.started_at = time.time()
        self._tasks[task.name] = task
        self._publish_phase(task, Phase.DEFINE, "started")
        self._start_block(task, Phase.DEFINE, 0)

    def advance(self, task_name: str, to_phase: Phase | None = None) -> None:
        """Advance a task to the next phase (or an explicit one).

        Marks the current phase's remaining blocks as skipped, closes
        the current phase, publishes the transition, and starts the
        first block of the new phase.
        """
        task = self._require(task_name)
        if task.is_closed:
            raise ValueError(f"task {task_name!r} is already closed")
        # Mark remaining blocks in the current phase as skipped
        for block in task.current_phase_blocks()[task.current_block:]:
            if block.status == "pending":
                block.status = "skipped"
                self._publish_pomodoro(task, block, "skipped")
        # Close the current phase
        self._publish_phase(task, task.current_phase, "completed")
        # Decide the next phase
        if to_phase is None:
            order = Phase.order()
            idx = order.index(task.current_phase)
            if idx == len(order) - 1:
                # Already at CLOSE - close the task
                self.close(task_name)
                return
            to_phase = order[idx + 1]
        else:
            # Validate the explicit phase is reachable
            current_idx = Phase.order().index(task.current_phase)
            target_idx = Phase.order().index(to_phase)
            if target_idx < current_idx:
                raise ValueError(
                    f"cannot advance backwards: {task.current_phase.value} -> {to_phase.value}"
                )
        # Skip any intermediate phases (mark blocks as skipped)
        current_idx = Phase.order().index(task.current_phase)
        target_idx = Phase.order().index(to_phase)
        for intermediate in Phase.order()[current_idx + 1:target_idx]:
            for block in task.blocks[intermediate.value]:
                if block.status == "pending":
                    block.status = "skipped"
                    self._publish_pomodoro(task, block, "skipped")
            self._publish_phase(task, intermediate, "skipped")
        # Move to the target phase
        task.current_phase = to_phase
        task.current_block = 0
        self._publish_phase(task, to_phase, "started")
        self._start_block(task, to_phase, 0)
        # If we just entered CLOSE, the task is done - auto-close.
        # The close() function publishes the close-completed event and
        # marks any remaining earlier-phase blocks as skipped.
        if to_phase == Phase.CLOSE:
            self.close(task_name)

    def complete_block(self, task_name: str, phase: Phase | None = None, block_index: int | None = None) -> None:
        """Mark a block as completed. Used by the agent (or operator) when the work is done.

        If all blocks in the phase are completed, auto-advances to
        the next phase. If the phase is the last one, auto-closes
        the task.
        """
        task = self._require(task_name)
        target_phase = phase or task.current_phase
        target_index = block_index if block_index is not None else task.current_block
        blocks = task.blocks[target_phase.value]
        if target_index >= len(blocks):
            raise ValueError(f"block index {target_index} out of range for phase {target_phase.value}")
        block = blocks[target_index]
        if block.status == "started":
            block.completed_at = time.time()
            block.status = "completed"
            self._publish_pomodoro(task, block, "completed")
            # Move to next block in the phase
            if target_index + 1 < len(blocks):
                task.current_block = target_index + 1
                self._start_block(task, target_phase, target_index + 1)
            else:
                # All blocks done - advance
                self.advance(task_name)

    def record_deliverable(self, task_name: str, phase: Phase, output: str) -> None:
        """Record the merged output of a phase. The next phase's agents
        read this when they start."""
        task = self._require(task_name)
        task.deliverables[phase.value] = output

    def close(self, task_name: str) -> None:
        """Mark a task as closed. Marks any remaining blocks as skipped and publishes a close event.

        Idempotent: calling close() on an already-closed task is a no-op
        (avoids double-publishing the close-completed event when
        advance() auto-closes after entering CLOSE).
        """
        task = self._require(task_name)
        if task.is_closed:
            return
        for phase in Phase.order():
            for block in task.blocks[phase.value]:
                if block.status != "completed" and block.status != "skipped":
                    block.status = "skipped"
                    self._publish_pomodoro(task, block, "skipped")
            if not any(b.status == "completed" for b in task.blocks[phase.value]):
                self._publish_phase(task, phase, "skipped")
        task.closed_at = time.time()
        task.current_phase = Phase.CLOSE
        self._publish_phase(task, Phase.CLOSE, "completed")

    def status(self, task_name: str) -> dict[str, Any]:
        """Return a JSON-serializable status snapshot for the task."""
        task = self._require(task_name)
        return {
            "name": task.name,
            "task_id": task.task_id,
            "current_phase": task.current_phase.value,
            "current_block": task.current_block,
            "started_at": task.started_at,
            "closed_at": task.closed_at,
            "is_closed": task.is_closed,
            "agents": task.agents,
            "phases": {
                p.value: [
                    {
                        "block_index": b.block_index,
                        "status": b.status,
                        "started_at": b.started_at,
                        "completed_at": b.completed_at,
                    }
                    for b in task.blocks[p.value]
                ]
                for p in Phase.order()
            },
            "deliverables": task.deliverables,
        }

    def list_tasks(self) -> list[str]:
        return sorted(self._tasks.keys())

    # ---- Internals --------------------------------------------------------

    def _start_block(self, task: BpmTask, phase: Phase, block_index: int) -> None:
        block = task.blocks[phase.value][block_index]
        block.started_at = time.time()
        block.status = "started"
        self._publish_pomodoro(task, block, "started")

    def _publish_phase(self, task: BpmTask, phase: Phase, status: str) -> None:
        self.publisher.publish("pmoves.bpm.phase.v1", {
            "task_id": task.task_id,
            "task_name": task.name,
            "phase": phase.value,
            "status": status,
            "issued_at": time.time(),
        })

    def _publish_pomodoro(self, task: BpmTask, block: PomodoroBlock, status: str) -> None:
        self.publisher.publish("pmoves.bpm.pomodoro.v1", {
            "task_id": task.task_id,
            "task_name": task.name,
            "block_index": block.block_index,
            "status": status,
            "issued_at": time.time(),
        })

    def _require(self, task_name: str) -> BpmTask:
        if task_name not in self._tasks:
            raise KeyError(f"unknown task {task_name!r}; registered: {self.list_tasks()}")
        return self._tasks[task_name]


# ---- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bpm_cron", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="start a BPM task")
    p_start.add_argument("name", help="task name (idempotent within a session)")
    p_start.add_argument("--description", default="", help="task description")
    p_start.add_argument("--agent", action="append", default=["mavis"], help="target agent (repeatable)")
    p_start.add_argument("--work-minutes", type=int, default=None, help="focus block length (default 25)")
    p_start.add_argument("--checkin-minutes", type=int, default=None, help="check-in length (default 5)")
    p_start.add_argument("--blocks-per-phase", type=int, default=None, help="blocks per phase (default 1)")

    p_adv = sub.add_parser("advance", help="advance a task to the next phase")
    p_adv.add_argument("name", help="task name")
    p_adv.add_argument("--to", default="", help="explicit target phase (default: next)")

    p_done = sub.add_parser("complete-block", help="complete the current pomodoro block")
    p_done.add_argument("name", help="task name")

    p_close = sub.add_parser("close", help="close a task")
    p_close.add_argument("name", help="task name")

    p_status = sub.add_parser("status", help="print task status as JSON")
    p_status.add_argument("name", help="task name")

    args = p.parse_args(argv)

    # Lazy import to avoid a circular import
    from pmoves.tools.orchestrator import MockPublisher
    pub = MockPublisher()
    cron = BpmCron(publisher=pub)

    if args.cmd == "start":
        task = BpmTask(
            name=args.name,
            description=args.description,
            agents=args.agent,
            work_minutes=args.work_minutes or DEFAULT_WORK_MINUTES,
            checkin_minutes=args.checkin_minutes or DEFAULT_CHECKIN_MINUTES,
            blocks_per_phase=args.blocks_per_phase or DEFAULT_BLOCKS_PER_PHASE,
        )
        cron.start(task)
        print(json.dumps(cron.status(args.name), indent=2))
        return 0

    if args.cmd == "advance":
        target = Phase(args.to) if args.to else None
        # The CLI's cron instance is stateless (re-loaded each call).
        # For real use, the harness keeps a single BpmCron instance
        # in memory and the CLI is for debugging. Here we create a
        # task with the same name to honor the advance.
        task = BpmTask(name=args.name, description="")
        cron.register(task)
        cron.advance(args.name, to_phase=target)
        print(json.dumps(cron.status(args.name), indent=2))
        return 0

    if args.cmd == "complete-block":
        task = BpmTask(name=args.name, description="")
        cron.register(task)
        cron.complete_block(args.name)
        print(json.dumps(cron.status(args.name), indent=2))
        return 0

    if args.cmd == "close":
        task = BpmTask(name=args.name, description="")
        cron.register(task)
        cron.close(args.name)
        print(json.dumps(cron.status(args.name), indent=2))
        return 0

    if args.cmd == "status":
        task = BpmTask(name=args.name, description="")
        cron.register(task)
        print(json.dumps(cron.status(args.name), indent=2))
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
