"""
Error Recovery

Automatic retry logic with exponential backoff and circuit breaker pattern.
"""

import asyncio
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable, Any
from datetime import datetime
from enum import Enum


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class RetryPolicy:
    """Retry configuration policy."""

    max_attempts: int = 3
    backoff_base: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.backoff_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)

        return delay

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "max_attempts": self.max_attempts,
            "backoff_base": self.backoff_base,
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "jitter": self.jitter,
        }


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3
    success_threshold: int = 2

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "half_open_max_calls": self.half_open_max_calls,
            "success_threshold": self.success_threshold,
        }


@dataclass
class CircuitBreakerState:
    """Circuit breaker runtime state."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    opened_at: Optional[float] = None
    half_open_calls: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_failure_time_iso": datetime.fromtimestamp(self.last_failure_time).isoformat() + "Z"
            if self.last_failure_time
            else None,
            "last_success_time": self.last_success_time,
            "last_success_time_iso": datetime.fromtimestamp(self.last_success_time).isoformat() + "Z"
            if self.last_success_time
            else None,
            "opened_at": self.opened_at,
            "opened_at_iso": datetime.fromtimestamp(self.opened_at).isoformat() + "Z"
            if self.opened_at
            else None,
            "half_open_calls": self.half_open_calls,
        }


class CircuitBreaker:
    """Circuit breaker for failing devices with thread-safe state transitions."""

    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.state = CircuitBreakerState()
        self._lock = threading.Lock()

    def record_success(self):
        """
        Record a successful call (thread-safe).

        Updates circuit breaker state, potentially transitioning from
        HALF_OPEN to CLOSED if success threshold is met.
        """
        with self._lock:
            self.state.success_count += 1
            self.state.last_success_time = time.time()

            if self.state.state == CircuitState.HALF_OPEN:
                self.state.half_open_calls += 1

                # Check if we should close circuit
                if self.state.half_open_calls >= self.config.half_open_max_calls:
                    if self.state.success_count >= self.config.success_threshold:
                        self.state.state = CircuitState.CLOSED
                        self.state.failure_count = 0
                        self.state.half_open_calls = 0

            elif self.state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.state.failure_count = max(0, self.state.failure_count - 1)

    def record_failure(self):
        """
        Record a failed call (thread-safe).

        Updates circuit breaker state, potentially transitioning from
        CLOSED or HALF_OPEN to OPEN if failure threshold is met.
        """
        with self._lock:
            self.state.failure_count += 1
            self.state.last_failure_time = time.time()

            if self.state.state == CircuitState.CLOSED:
                # Check if we should open circuit
                if self.state.failure_count >= self.config.failure_threshold:
                    self.state.state = CircuitState.OPEN
                    self.state.opened_at = time.time()

            elif self.state.state == CircuitState.HALF_OPEN:
                # Open circuit again on failure
                self.state.state = CircuitState.OPEN
                self.state.opened_at = time.time()
                self.state.half_open_calls = 0

    def allow_request(self) -> bool:
        """
        Check if request should be allowed (thread-safe).

        Returns:
            True if allowed, False if circuit is open or at capacity in HALF_OPEN
        """
        with self._lock:
            if self.state.state == CircuitState.CLOSED:
                return True

            elif self.state.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self.state.opened_at:
                    elapsed = time.time() - self.state.opened_at
                    if elapsed >= self.config.recovery_timeout:
                        # Transition to half-open
                        self.state.state = CircuitState.HALF_OPEN
                        self.state.half_open_calls = 0
                        return True

                return False

            elif self.state.state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                return self.state.half_open_calls < self.config.half_open_max_calls

            return False

    def get_state(self) -> CircuitBreakerState:
        """
        Get current circuit breaker state (thread-safe snapshot).

        Returns:
            CircuitBreakerState: Current state snapshot
        """
        with self._lock:
            # Return a copy to avoid external modification
            return CircuitBreakerState(
                state=self.state.state,
                failure_count=self.state.failure_count,
                success_count=self.state.success_count,
                last_failure_time=self.state.last_failure_time,
                last_success_time=self.state.last_success_time,
                opened_at=self.state.opened_at,
                half_open_calls=self.state.half_open_calls,
            )

    def reset(self):
        """
        Reset circuit breaker to closed state (thread-safe).

        Resets all counters and transitions to CLOSED state,
        allowing requests to flow again immediately.
        """
        with self._lock:
            self.state = CircuitBreakerState()


class RecoveryManager:
    """Orchestrates recovery strategies."""

    def __init__(self):
        """Initialize recovery manager."""
        self.retry_policy = RetryPolicy()
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.circuit_config = CircuitBreakerConfig()

    def configure_retry(
        self,
        max_attempts: int = 3,
        backoff_base: float = 2.0,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ) -> dict:
        """
        Configure retry policy.

        Args:
            max_attempts: Maximum retry attempts
            backoff_base: Exponential backoff base
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Add random jitter to delays

        Returns:
            Result dict
        """
        self.retry_policy = RetryPolicy(
            max_attempts=max_attempts,
            backoff_base=backoff_base,
            initial_delay=initial_delay,
            max_delay=max_delay,
            jitter=jitter,
        )

        return {
            "success": True,
            "policy": self.retry_policy.to_dict(),
            "message": "Updated retry policy",
        }

    def configure_circuit_breaker(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
    ) -> dict:
        """
        Configure circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before trying half-open
            half_open_max_calls: Max calls in half-open state
            success_threshold: Successes to close circuit

        Returns:
            Result dict
        """
        self.circuit_config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
            success_threshold=success_threshold,
        )

        # Update all existing circuit breakers
        for breaker in self.circuit_breakers.values():
            breaker.config = self.circuit_config

        return {
            "success": True,
            "config": self.circuit_config.to_dict(),
            "message": "Updated circuit breaker configuration",
        }

    def get_circuit_breaker(self, key: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for key.

        Args:
            key: Circuit breaker key (e.g., device name)

        Returns:
            CircuitBreaker instance
        """
        if key not in self.circuit_breakers:
            self.circuit_breakers[key] = CircuitBreaker(self.circuit_config)

        return self.circuit_breakers[key]

    def list_circuit_breakers(self) -> dict[str, CircuitBreakerState]:
        """
        List all circuit breaker states.

        Returns:
            Dict mapping keys to states
        """
        return {
            key: breaker.get_state()
            for key, breaker in self.circuit_breakers.items()
        }

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        circuit_breaker_key: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Execute function with retry logic and circuit breaker.

        Args:
            func: Async function to execute
            *args: Function arguments
            circuit_breaker_key: Optional circuit breaker key
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        # Check circuit breaker
        if circuit_breaker_key:
            breaker = self.get_circuit_breaker(circuit_breaker_key)
            if not breaker.allow_request():
                raise Exception(f"Circuit breaker open for '{circuit_breaker_key}'")

        last_exception = None

        for attempt in range(self.retry_policy.max_attempts):
            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Record success
                if circuit_breaker_key:
                    breaker = self.get_circuit_breaker(circuit_breaker_key)
                    breaker.record_success()

                return result

            except Exception as e:
                last_exception = e

                # Record failure
                if circuit_breaker_key:
                    breaker = self.get_circuit_breaker(circuit_breaker_key)
                    breaker.record_failure()

                # Check if we should retry
                if attempt < self.retry_policy.max_attempts - 1:
                    delay = self.retry_policy.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    # Last attempt failed
                    break

        # All retries exhausted
        raise last_exception or Exception("All retry attempts exhausted")

    def reset_circuit_breaker(self, key: str) -> dict:
        """
        Reset circuit breaker for key.

        Args:
            key: Circuit breaker key

        Returns:
            Result dict
        """
        if key in self.circuit_breakers:
            self.circuit_breakers[key].reset()
            return {
                "success": True,
                "message": f"Reset circuit breaker for '{key}'",
            }
        else:
            return {
                "success": False,
                "error": f"Circuit breaker '{key}' not found",
            }
