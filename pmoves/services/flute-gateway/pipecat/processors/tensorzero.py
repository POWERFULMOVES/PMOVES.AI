"""TensorZero LLM processor for pipecat pipelines.

Routes LLM calls through the TensorZero gateway for unified model access
and observability. Supports streaming for faster TTS handoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

import httpx

logger = logging.getLogger(__name__)

# Pipecat imports - gracefully handle if not installed
try:
    from pipecat.frames.frames import (
        EndFrame,
        ErrorFrame,
        Frame,
        LLMFullResponseEndFrame,
        LLMFullResponseStartFrame,
        LLMMessagesFrame,
        TextFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    PIPECAT_AVAILABLE = True
except ImportError:
    PIPECAT_AVAILABLE = False

    # Stub classes for when pipecat not installed (type hints only)
    class FrameProcessor:  # type: ignore[no-redef]
        """Stub FrameProcessor for when pipecat not installed."""

        async def cancel(self) -> None:
            """Stub cancel method."""
            pass

        async def cleanup(self) -> None:
            """Stub cleanup method."""
            pass

    Frame = object
    FrameDirection = None


class TensorZeroLLMProcessor(FrameProcessor):
    """Pipecat LLM processor using TensorZero gateway.

    This processor routes LLM calls through TensorZero (port 3030) for:
    - Unified access to multiple model providers (OpenAI, Anthropic, etc.)
    - Observability and metrics via ClickHouse
    - Token tracking and latency monitoring

    Attributes:
        base_url: TensorZero gateway URL.
        model: Default model to use for completions.
        stream: Whether to stream responses.

    Example:
        >>> llm = TensorZeroLLMProcessor(
        ...     base_url="http://localhost:3030",
        ...     model="claude-sonnet-4-5"
        ... )
        >>> pipeline = Pipeline([..., llm, ...])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:3030",
        model: str = "claude-sonnet-4-5",
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ):
        """Initialize TensorZero LLM processor.

        Args:
            base_url: TensorZero gateway URL.
            model: Model name for completions.
            stream: Enable streaming responses.
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            timeout: Request timeout in seconds.
        """
        if not PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is required for TensorZeroLLMProcessor. "
                "Install with: pip install pipecat-ai[silero]"
            )

        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._stream = stream
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout

        self._client: Optional[httpx.AsyncClient] = None
        self._generating = False

    @property
    def model(self) -> str:
        """Get current model name."""
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        """Set model name for completions."""
        self._model = value

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _complete_streaming(
        self, messages: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Stream completion from TensorZero.

        Args:
            messages: OpenAI-format messages list.

        Yields:
            Text chunks from streaming response.
        """
        client = await self._ensure_client()

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": True,
        }

        try:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not self._generating:
                        break

                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and chunk["choices"]:
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.HTTPStatusError as e:
            logger.error(f"TensorZero HTTP error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"TensorZero streaming error: {e}")
            raise

    async def _complete_batch(self, messages: list[dict]) -> str:
        """Get batch completion from TensorZero.

        Args:
            messages: OpenAI-format messages list.

        Returns:
            Complete response text.
        """
        client = await self._ensure_client()

        payload = {
            "model": self._model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": False,
        }

        response = await client.post(
            f"{self._base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = response.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0].get("message", {}).get("content", "")

        return ""

    async def process_frame(
        self, frame: Frame, direction: FrameDirection
    ) -> AsyncGenerator[Frame, None]:
        """Process incoming frames and generate LLM responses.

        Args:
            frame: Input frame (LLMMessagesFrame triggers completion).
            direction: Frame direction (downstream/upstream).

        Yields:
            LLMFullResponseStartFrame: Before generation begins.
            TextFrame: Response text chunks (streaming) or full response.
            LLMFullResponseEndFrame: After generation completes.
            ErrorFrame: On generation errors.
        """
        await super().process_frame(frame, direction)

        if isinstance(frame, LLMMessagesFrame):
            messages = frame.messages
            if not messages:
                yield frame
                return

            yield LLMFullResponseStartFrame()
            self._generating = True

            full_response = ""
            try:
                if self._stream:
                    async for chunk in self._complete_streaming(messages):
                        if not self._generating:
                            break
                        full_response += chunk
                        yield TextFrame(text=chunk)
                else:
                    full_response = await self._complete_batch(messages)
                    yield TextFrame(text=full_response)

                logger.debug(
                    f"TensorZero LLM completed: {len(full_response)} chars"
                )

            except Exception as e:
                error_msg = f"TensorZero LLM error: {e}"
                logger.error(error_msg)
                yield ErrorFrame(error=error_msg)

            finally:
                self._generating = False
                yield LLMFullResponseEndFrame()

        elif isinstance(frame, EndFrame):
            self._generating = False
            yield frame

        else:
            yield frame

    async def cancel(self) -> None:
        """Cancel ongoing generation and cleanup resources."""
        self._generating = False
        # Close HTTP client to prevent resource leaks on cancellation
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().cancel()

    async def cleanup(self) -> None:
        """Cleanup HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().cleanup()
