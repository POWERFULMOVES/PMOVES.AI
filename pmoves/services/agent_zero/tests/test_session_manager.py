from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

import pytest

from services.agent_zero.controller import (
    AgentZeroRuntime,
    AgentZeroSessionManager,
    TerminalSessionError,
)


class DummyPublisher:
    def __init__(self) -> None:
        self.events: List[Tuple[str, Dict[str, Any]]] = []

    async def __call__(self, topic: str, payload: Dict[str, Any], **kwargs: Any) -> None:
        self.events.append((topic, payload))


@pytest.mark.asyncio
async def test_session_manager_processes_task() -> None:
    publisher = DummyPublisher()
    runtime = AgentZeroRuntime(publisher)
    manager = AgentZeroSessionManager(runtime)

    envelope = {
        "id": "evt-1",
        "topic": "agentzero.task.v1",
        "payload": {
            "session_id": "sess-1",
            "task_id": "task-1",
            "instructions": "echo hello",
        },
    }

    result = await manager.enqueue(envelope)
    assert any(topic == "agentzero.task.status.v1" for topic, _ in publisher.events)
    assert any(topic == "agentzero.task.result.v1" for topic, _ in publisher.events)
    assert result
    await manager.shutdown()


@pytest.mark.asyncio
async def test_session_manager_requires_session_id() -> None:
    publisher = DummyPublisher()
    runtime = AgentZeroRuntime(publisher)
    manager = AgentZeroSessionManager(runtime)

    with pytest.raises(TerminalSessionError):
        await manager.enqueue({"topic": "agentzero.task.v1", "payload": {"task_id": "x"}})

    await manager.shutdown()
