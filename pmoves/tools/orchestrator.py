"""orchestrator.py - the Mavis multi-agent dispatcher.

The runtime side of the Mavis harness. Reads the bootstrap CGP,
publishes tasks to the right NATS subjects, and merges results back
from peer agents (KiloClaw on 5090, Hermes on TBD, etc.).

The orchestrator does NOT replace the consumer forks' tools - it
publishes work to them. The consumer forks (PMOVES-hermes-agent,
PMOVES-pinokio) read the CGP, register the PMOVES tools alongside
their own, and respond on pmoves.agent.result.v1. The orchestrator
is the dispatcher; the forks are the workers.

NATS subjects (per .claude/context/nats-subjects.md - to be verified
in the next session; the values here are the planned v0 contract):

- pmoves.agent.task.v1     - Mavis publishes the task here
- pmoves.agent.result.v1   - Worker publishes the result back here
- pmoves.bpm.phase.v1      - BPM cron publishes phase transitions
- pmoves.bpm.pomodoro.v1   - Focus-block boundaries

The transport is abstracted behind a Publisher interface so the
orchestrator can be tested with a mock (no real NATS server
required) and the consumer forks can wire to a real pmoves-nats-mcp
later.

Usage:

    from pmoves.tools.load_bootstrap import load_bootstrap
    from pmoves.tools.orchestrator import Orchestrator, NatsPublisher

    bs = load_bootstrap()
    pub = NatsPublisher()  # uses pmoves-nats-mcp
    orch = Orchestrator(bootstrap=bs, publisher=pub)
    result = orch.dispatch(
        task="render cyber.png as the Pillar 4 encoding skin",
        agents=["mavis", "kiloclaw"],  # mavis = self; kiloclaw = GLM-5.1
    )
    print(result.merged)  # the combined output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from pmoves.tools.load_bootstrap import Bootstrap, load_bootstrap

# NATS subjects (planned v0 contract; align with .claude/context/nats-subjects.md
# in the next session before any actual NATS deploy).
SUBJECT_TASK = "pmoves.agent.task.v1"
SUBJECT_RESULT = "pmoves.agent.result.v1"
SUBJECT_BPM_PHASE = "pmoves.bpm.phase.v1"
SUBJECT_BPM_POMODORO = "pmoves.bpm.pomodoro.v1"

# Per the bootstrap CGP: mavis can be a target (the agent points at
# itself for tasks that should stay in-session); kiloclaw = GLM-5.1 on
# 5090; hermes = NousResearch (location TBD).
KNOWN_TARGETS = {"mavis", "kiloclaw", "hermes"}


# ---- Transport ---------------------------------------------------------------


class Publisher(Protocol):
    """The orchestrator publishes via this interface.

    A real implementation wraps pmoves-nats-mcp (the PMOVES-built NATS
    server) or nats-py. The tests use a MockPublisher that records
    what was published without actually sending anything.
    """

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        ...


class MockPublisher:
    """In-memory Publisher for tests. Records everything in `.published`."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    def publish(self, subject: str, payload: dict[str, Any]) -> None:
        self.published.append((subject, payload))


# ---- Result types ------------------------------------------------------------


@dataclass
class AgentResult:
    """The result from a single dispatched agent."""

    target: str
    status: str  # "success" | "error" | "pending" | "timeout"
    output: str = ""
    error: str = ""
    elapsed_s: float = 0.0


@dataclass
class DispatchResult:
    """The result of dispatching a task to one or more agents."""

    task_id: str
    task: str
    results: dict[str, AgentResult] = field(default_factory=dict)
    merged: str = ""
    failed: list[str] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        return all(r.status == "success" for r in self.results.values())

    @property
    def any_succeeded(self) -> bool:
        return any(r.status == "success" for r in self.results.values())


# ---- Orchestrator ------------------------------------------------------------


class Orchestrator:
    """Multi-agent dispatcher. Loads the CGP, publishes tasks, merges results.

    The orchestrator is intentionally thin - it doesn't know how
    agents do their work, only how to publish to the right subject
    and correlate prompt_id -> result. The agent logic lives in
    the consumer forks (PMOVES-hermes-agent, PMOVES-pinokio).
    """

    def __init__(
        self,
        bootstrap: Bootstrap | None = None,
        publisher: Publisher | None = None,
        timeout_s: int = 300,
        poll_s: float = 1.0,
    ) -> None:
        self.bootstrap = bootstrap or load_bootstrap()
        self.publisher = publisher or MockPublisher()
        self.timeout_s = timeout_s
        self.poll_s = poll_s

    def dispatch(
        self,
        task: str,
        agents: list[str],
        context: dict[str, Any] | None = None,
        identity: str | None = None,
    ) -> DispatchResult:
        """Dispatch a task to one or more agents and wait for results.

        agents is a list of targets - one of "mavis" (self), "kiloclaw"
        (GLM-5.1 on 5090), or "hermes" (NousResearch, TBD node).
        identity overrides the bootstrap's identity block for this
        dispatch (e.g. critic role for a review pass).

        Returns a DispatchResult with one AgentResult per agent. The
        `merged` field is a simple concat of all successful outputs
        (the orchestrator doesn't try to be smart about merging -
        that's an Mavis-side concern that can re-dispatch on merge
        failure).
        """
        task_id = str(uuid.uuid4())
        context = context or {}
        if identity:
            context["identity"] = identity

        result = DispatchResult(task_id=task_id, task=task)
        deadline = time.monotonic() + self.timeout_s
        for agent in agents:
            if agent not in KNOWN_TARGETS:
                result.results[agent] = AgentResult(
                    target=agent,
                    status="error",
                    error=f"unknown agent target {agent!r}; known: {sorted(KNOWN_TARGETS)}",
                )
                result.failed.append(agent)
                continue
            result.results[agent] = AgentResult(target=agent, status="pending")

            self.publisher.publish(SUBJECT_TASK, {
                "task_id": task_id,
                "target": agent,
                "task": task,
                "context": context,
                "bootstrap_id": self.bootstrap.meta.get("bootstrap_id"),
                "issued_at": time.time(),
            })

        # Wait for results. The orchestrator polls the publisher's
        # published list for matching result entries (the test mock
        # pattern; a real impl would subscribe to SUBJECT_RESULT via
        # pmoves-nats-mcp). For the v0 wire-up, we simulate the wait
        # by accepting injected results via _receive_result() before
        # the deadline.
        # In the real world, a NATS subscriber would push results
        # into result.results[agent] from another thread.
        time.sleep(0)  # yield

        # If all agents are still pending after the yield, the caller
        # is expected to inject results via _receive_result() and
        # call _wait_for_results() explicitly (the test pattern).
        # The deadline check is a no-op here - _wait_for_results does
        # the actual work.
        _ = deadline  # documented for future use

        self._merge_results(result)
        return result

    def _receive_result(self, task_id: str, result: AgentResult) -> None:
        """Inject a result from a real subscriber (production) or the test.

        Not part of the public API in the wire-up sense - the NATS
        subscriber calls this when a result comes in. The test calls
        it directly to avoid a real NATS roundtrip.
        """
        # The orchestrator doesn't keep its own pending-results map
        # in v0; the caller's DispatchResult is the source of truth.
        # We expose a hook so the caller can mutate the result they
        # already hold - this is intentionally minimal.
        raise NotImplementedError(
            "use DispatchResult.results[target] = AgentResult(...) directly"
        )

    def _wait_for_results(self, result: DispatchResult) -> None:
        """Block until all dispatched agents have reported or timeout.

        Used by the test pattern: dispatch, then call _wait_for_results
        which polls until all results have a non-pending status. A
        real implementation would subscribe to SUBJECT_RESULT and
        push into result.results[agent] from the callback.
        """
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            if all(r.status != "pending" for r in result.results.values()):
                return
            time.sleep(self.poll_s)
        # Deadline hit - mark any still-pending as timeout
        for agent, r in result.results.items():
            if r.status == "pending":
                r.status = "timeout"
                result.failed.append(agent)

    def _merge_results(self, result: DispatchResult) -> None:
        """Concatenate successful outputs. Real Mavis would re-dispatch
        on merge failure; the orchestrator just collects for now."""
        chunks: list[str] = []
        for agent, r in result.results.items():
            if r.status == "success" and r.output:
                chunks.append(f"--- {agent} ---\n{r.output}")
        result.merged = "\n\n".join(chunks)
        result.failed = [a for a, r in result.results.items() if r.status != "success"]

    def publish_phase(self, task_id: str, phase: str, status: str = "started") -> None:
        """Publish a BPM phase transition event. Used by bpm_cron.py."""
        self.publisher.publish(SUBJECT_BPM_PHASE, {
            "task_id": task_id,
            "phase": phase,  # define | assign | execute | review | close
            "status": status,  # started | completed | failed
            "issued_at": time.time(),
        })

    def publish_pomodoro(self, task_id: str, block_index: int, status: str = "started") -> None:
        """Publish a pomodoro focus-block boundary. Used by bpm_cron.py."""
        self.publisher.publish(SUBJECT_BPM_POMODORO, {
            "task_id": task_id,
            "block_index": block_index,
            "status": status,  # started | completed | skipped
            "issued_at": time.time(),
        })


# ---- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="orchestrator", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_pub = sub.add_parser("publish", help="publish a task to the orchestrator")
    p_pub.add_argument("task", help="the task text")
    p_pub.add_argument("--agent", action="append", default=[], help="target agent (repeatable)")
    p_pub.add_argument("--identity", default="", help="override identity.role for this dispatch")

    args = p.parse_args(argv)

    if args.cmd == "publish":
        bs = load_bootstrap()
        orch = Orchestrator(bootstrap=bs, publisher=MockPublisher())
        agents = args.agent or ["mavis"]
        result = orch.dispatch(args.task, agents, identity=args.identity or None)
        for agent, r in result.results.items():
            print(f"  {agent}: status={r.status} error={r.error}")
        # Note: in CLI mode with MockPublisher, we don't actually
        # receive any results - the orchestrator is a dispatcher, the
        # real wait happens in the calling process via _wait_for_results.
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
