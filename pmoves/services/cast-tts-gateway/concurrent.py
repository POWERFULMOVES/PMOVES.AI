"""
Concurrent Casting

Parallel audio casting to multiple Google Cast devices.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime


@dataclass
class CastResult:
    """Result of casting to a single device."""

    device: str
    success: bool
    error: Optional[str] = None
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


@dataclass
class MultiCastResult:
    """Result of casting to multiple devices."""

    text: str
    total_devices: int
    successful: int
    failed: int
    results: list[CastResult] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "text": self.text,
            "total_devices": self.total_devices,
            "successful": self.successful,
            "failed": self.failed,
            "results": [r.__dict__ for r in self.results],
            "duration_ms": self.duration_ms,
            "success": self.failed == 0,
        }


class ConcurrentCaster:
    """Concurrent casting to multiple Cast devices."""

    def __init__(
        self,
        max_concurrent: int = 10,
        timeout_per_device: float = 30.0,
    ):
        """
        Initialize concurrent caster.

        Args:
            max_concurrent: Maximum parallel cast operations
            timeout_per_device: Timeout per device (seconds)
        """
        self.max_concurrent = max_concurrent
        self.timeout_per_device = timeout_per_device

    async def cast_to_devices(
        self,
        cast_fn: Callable[[str], dict],
        devices: list[str],
        text: str = "",
    ) -> MultiCastResult:
        """
        Cast to multiple devices concurrently.

        Args:
            cast_fn: Async function that takes device name and returns result dict
            devices: List of device names
            text: Text being cast (for logging)

        Returns:
            MultiCastResult with aggregate results
        """
        import time

        start_time = time.time()

        # Limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def cast_with_timeout(device: str) -> CastResult:
            """Cast to single device with timeout and error isolation."""
            try:
                async with semaphore:
                    result = await asyncio.wait_for(
                        cast_fn(device),
                        timeout=self.timeout_per_device,
                    )

                    duration_ms = int((time.time() - start_time) * 1000)

                    if result.get("success"):
                        return CastResult(
                            device=device,
                            success=True,
                            duration_ms=duration_ms,
                        )
                    else:
                        return CastResult(
                            device=device,
                            success=False,
                            error=result.get("error", "Unknown error"),
                            duration_ms=duration_ms,
                        )

            except asyncio.TimeoutError:
                return CastResult(
                    device=device,
                    success=False,
                    error=f"Timeout after {self.timeout_per_device}s",
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            except Exception as e:
                return CastResult(
                    device=device,
                    success=False,
                    error=str(e),
                    duration_ms=int((time.time() - start_time) * 1000),
                )

        # Execute all casts concurrently
        results = await asyncio.gather(
            *[cast_with_timeout(d) for d in devices],
            return_exceptions=False,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Count successes and failures
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        return MultiCastResult(
            text=text,
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            results=results,
            duration_ms=duration_ms,
        )

    async def cast_to_groups(
        self,
        cast_fn: Callable[[str], dict],
        groups: list[list[str]],
        text: str = "",
    ) -> list[MultiCastResult]:
        """
        Cast to multiple groups sequentially.

        Args:
            cast_fn: Async function that takes device name and returns result dict
            groups: List of device lists (groups)
            text: Text being cast

        Returns:
            List of MultiCastResult, one per group
        """
        group_results = []

        for group in groups:
            result = await self.cast_to_devices(cast_fn, group, text)
            group_results.append(result)

        return group_results

    def validate_devices(self, devices: list[str], available: list[str]) -> dict:
        """
        Validate device list against available devices.

        Args:
            devices: List of device names to validate
            available: List of available device names

        Returns:
            Validation result
        """
        available_set = set(available)
        valid = [d for d in devices if d in available_set]
        invalid = [d for d in devices if d not in available_set]

        return {
            "valid": valid,
            "invalid": invalid,
            "valid_count": len(valid),
            "invalid_count": len(invalid),
            "total": len(devices),
        }
