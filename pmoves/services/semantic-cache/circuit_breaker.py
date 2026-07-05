#!/usr/bin/env python3
"""Circuit breaker for the semantic cache pipeline.

Tracks consecutive failures across the cache stack. When open,
all cache operations are skipped and requests passthrough directly.
"""

from __future__ import annotations

import enum
import logging
import time

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Three-state circuit breaker with timeout-based recovery."""

    def __init__(self, max_failures: int = 5, reset_timeout: int = 60) -> None:
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Current state, auto-transitioning OPEN -> HALF_OPEN after timeout."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning OPEN -> HALF_OPEN")
        return self._state

    @property
    def is_open(self) -> bool:
        """True when circuit is OPEN (blocks all cache operations)."""
        return self.state == CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request should proceed through the cache pipeline."""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful operation — resets to CLOSED."""
        if self._state != CircuitState.CLOSED:
            logger.info("Circuit breaker closing (recovery succeeded)")
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed operation — may trip the circuit open."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker re-opening (HALF_OPEN failure)")
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.max_failures:
            logger.warning(
                "Circuit breaker opening (%d/%d failures)",
                self._failure_count,
                self.max_failures,
            )
            self._state = CircuitState.OPEN
