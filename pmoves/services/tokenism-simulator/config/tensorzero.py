"""
TensorZero LLM Gateway Integration for PMOVES Tokenism Simulator

Following PMOVES.AI patterns:
- Centralized LLM calls through TensorZero
- Observability via ClickHouse
- Standard chat completions API
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from config import TensorZeroConfig

logger = logging.getLogger(__name__)


class TensorZeroError(Exception):
    """Base exception for TensorZero failures.

    Attributes:
        transient: If True, the error may be resolved by retrying (e.g., temporary network issues)
    """

    def __init__(self, message: str, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class TensorZeroHTTPError(TensorZeroError):
    """HTTP error from TensorZero gateway.

    Attributes:
        status_code: HTTP status code
        response_text: Response body from server
    """

    def __init__(self, status_code: int, response_text: str) -> None:
        self.status_code = status_code
        self.response_text = response_text
        # 5xx errors may be transient, 4xx are not
        transient = status_code >= 500
        super().__init__(
            f"HTTP {status_code}: {response_text}",
            transient=transient
        )


class TensorZeroTimeoutError(TensorZeroError):
    """Timeout waiting for TensorZero response.

    Timeout errors are typically transient - the service may be under load.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, transient=True)


class TensorZeroConnectionError(TensorZeroError):
    """Network connection error to TensorZero.

    Connection errors are typically transient - may indicate network issues.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, transient=True)


@dataclass
class LLMMessage:
    """LLM message for TensorZero chat completions."""
    role: str
    content: str


@dataclass
class LLMResponse:
    """LLM response from TensorZero."""
    content: str
    model: str
    tokens_used: int = 0
    latency_ms: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)


class TensorZeroClient:
    """
    Client for TensorZero LLM gateway.

    Provides:
    - Chat completions for simulation analysis
    - Risk assessment reports
    - Natural language explanations
    """

    def __init__(self, config: TensorZeroConfig):
        self.config = config
        self.base_url = config.url.rstrip('/')
        self.model = config.model
        self.timeout = config.timeout

    async def chat_completion(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """
        Send chat completion request to TensorZero.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated content

        Raises:
            TensorZeroHTTPError: On HTTP errors (4xx/5xx)
            TensorZeroTimeoutError: On request timeout
            TensorZeroConnectionError: On network connection failures
            TensorZeroError: On other failures
        """
        start_time = datetime.now(timezone.utc)

        try:
            payload = {
                'model': self.model,
                'messages': [
                    {'role': m.role, 'content': m.content}
                    for m in messages
                ],
                'temperature': temperature,
                'max_tokens': max_tokens,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f'{self.base_url}/v1/chat/completions',
                    json=payload,
                )
                response.raise_for_status()

            latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            data = response.json()
            choice = data.get('choices', [{}])[0]
            message = choice.get('message', {})
            content = message.get('content', '')

            return LLMResponse(
                content=content,
                model=data.get('model', self.model),
                tokens_used=data.get('usage', {}).get('total_tokens', 0),
                latency_ms=int(latency),
                raw_response=data,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from TensorZero: {e.response.status_code} {e.response.text}")
            raise TensorZeroHTTPError(e.response.status_code, e.response.text) from e
        except httpx.TimeoutException as e:
            logger.error(f"Timeout calling TensorZero after {self.timeout}s")
            raise TensorZeroTimeoutError(
                f"TensorZero timeout after {self.timeout}s"
            ) from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error to TensorZero at {self.base_url}")
            raise TensorZeroConnectionError(
                f"Cannot connect to TensorZero at {self.base_url}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error calling TensorZero: {e}")
            raise TensorZeroError(f"TensorZero request failed: {e}") from e

    async def analyze_simulation(
        self,
        simulation_data: dict[str, Any],
    ) -> str:
        """
        Generate natural language analysis of simulation results.

        Args:
            simulation_data: Simulation results to analyze

        Returns:
            Analysis text

        Raises:
            TensorZeroHTTPError: On HTTP errors
            TensorZeroTimeoutError: On timeout
            TensorZeroConnectionError: On connection failures
            TensorZeroError: On other failures
        """
        system_prompt = """You are a token economy analyst for PMOVES.AI.
Analyze the provided simulation results and provide:
1. Executive summary of key findings
2. Risk assessment (low/medium/high)
3. Notable trends or anomalies
4. Recommendations for calibration

Be concise but thorough. Use markdown formatting."""

        user_prompt = f"""Analyze the following token economy simulation results:

```json
{simulation_data}
```

Provide your analysis."""

        messages = [
            LLMMessage(role='system', content=system_prompt),
            LLMMessage(role='user', content=user_prompt),
        ]

        response = await self.chat_completion(messages)
        return response.content

    async def generate_risk_report(
        self,
        metrics: dict[str, Any],
    ) -> str:
        """
        Generate risk assessment report.

        Args:
            metrics: Key metrics including Gini coefficient, poverty rate, etc.

        Returns:
            Risk report

        Raises:
            TensorZeroHTTPError: On HTTP errors
            TensorZeroTimeoutError: On timeout
            TensorZeroConnectionError: On connection failures
            TensorZeroError: On other failures
        """
        system_prompt = """You are a risk assessment specialist for PMOVES.AI.
Generate a risk report based on token economy metrics.
Rate each risk factor as Low, Medium, or High with justification."""

        user_prompt = f"""Generate a risk report for the following metrics:

```json
{metrics}
```

Include:
- Wealth inequality risk (based on Gini coefficient)
- Economic stability risk
- Token circulation risk
- Overall risk rating"""

        messages = [
            LLMMessage(role='system', content=system_prompt),
            LLMMessage(role='user', content=user_prompt),
        ]

        response = await self.chat_completion(messages)
        return response.content

    async def suggest_calibration(
        self,
        current_params: dict[str, Any],
        observed_data: dict[str, Any],
        target_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Suggest parameter calibration based on observed vs target data.

        Args:
            current_params: Current simulation parameters
            observed_data: Observed real-world data
            target_metrics: Target metrics to achieve

        Returns:
            Calibration suggestions

        Raises:
            TensorZeroHTTPError: On HTTP errors
            TensorZeroTimeoutError: On timeout
            TensorZeroConnectionError: On connection failures
            TensorZeroError: On other failures
        """
        system_prompt = """You are a calibration specialist for PMOVES.AI.
Suggest parameter adjustments to align simulation with observed data.
Return your response as a JSON object with 'suggestions' and 'confidence' keys."""

        user_prompt = f"""Current parameters:
```json
{current_params}
```

Observed data:
```json
{observed_data}
```

Target metrics:
```json
{target_metrics}
```

Suggest calibration adjustments."""

        messages = [
            LLMMessage(role='system', content=system_prompt),
            LLMMessage(role='user', content=user_prompt),
        ]

        response = await self.chat_completion(messages, temperature=0.3)
        return response.raw_response


# Global TensorZero client
_tensorzero_client: Optional[TensorZeroClient] = None


def get_tensorzero_client(config: Optional[TensorZeroConfig] = None) -> TensorZeroClient:
    """Get or create the global TensorZero client."""
    global _tensorzero_client

    if _tensorzero_client is None:
        cfg = config or TensorZeroConfig()
        _tensorzero_client = TensorZeroClient(cfg)

    return _tensorzero_client
