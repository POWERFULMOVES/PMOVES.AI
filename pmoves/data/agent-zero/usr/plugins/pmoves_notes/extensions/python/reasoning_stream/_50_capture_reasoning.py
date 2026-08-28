"""PMOVES.Notes extension — capture the agent's reasoning stream.

Runs at the ``reasoning_stream`` extension point, which Agent Zero calls with
``text`` = the cumulative reasoning produced by the chat model (see
``Agent.handle_reasoning_stream``). We stash the latest full reasoning on the
agent so the ``reasoning_stream_end`` hook can persist it once the stream
finishes. This is the correct source of chain-of-thought — ``loop_data.last_response``
is the agent's response/tool-call, not its reasoning.
"""

from __future__ import annotations

from helpers.extension import Extension

REASONING_DATA_KEY = "_pmoves_notes_reasoning"


class CaptureReasoning(Extension):
    """Stash the latest full reasoning text on the agent for later persistence."""

    async def execute(self, text: str = "", **kwargs) -> None:
        if not self.agent:
            return
        if isinstance(text, str) and text.strip():
            self.agent.set_data(REASONING_DATA_KEY, text)
