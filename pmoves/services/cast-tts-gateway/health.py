"""
Device Health Monitoring

Continuous health monitoring for Cast devices with metrics and alerts.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
from collections import deque


@dataclass
class HealthAlert:
    """Health alert configuration."""

    device: str
    metric: str  # "availability", "latency", "success_rate"
    threshold: float
    action: str  # "publish_nats", "log", "webhook"
    webhook_url: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "device": self.device,
            "metric": self.metric,
            "threshold": self.threshold,
            "action": self.action,
            "webhook_url": self.webhook_url,
            "enabled": self.enabled,
        }


@dataclass
class DeviceHealth:
    """Health status for a Cast device."""

    device: str
    online: bool = True
    availability: float = 1.0  # 0.0 to 1.0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0  # 0.0 to 1.0
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    last_check: Optional[float] = None
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    latency_samples: deque[float] = field(default_factory=lambda: deque(maxlen=100))
    # Track recent checks in sliding window for accurate availability calculation
    recent_checks: deque[tuple[float, bool]] = field(
        default_factory=lambda: deque(maxlen=1000)
    )  # (timestamp, success) tuples
    created_at: float = field(default_factory=time.time)

    def record_check(self, success: bool, latency_ms: float = 0.0):
        """
        Record a health check result with sliding window tracking.

        Args:
            success: Whether the check succeeded
            latency_ms: Latency in milliseconds
        """
        self.total_checks += 1
        self.last_check = time.time()

        if success:
            self.successful_checks += 1
            self.last_success = time.time()
            self.latency_samples.append(latency_ms)
        else:
            self.failed_checks += 1
            self.last_failure = time.time()

        # Track in sliding window (max 1000 entries)
        self.recent_checks.append((time.time(), success))

        # Recalculate metrics
        self._recalculate_metrics()

    def _recalculate_metrics(self):
        """
        Recalculate health metrics using sliding window.

        Uses recent checks from the last hour for accurate availability calculation.
        """
        if self.total_checks == 0:
            return

        # Availability: ratio of successful checks in last hour (using sliding window)
        one_hour_ago = time.time() - 3600
        recent_checks = [
            (timestamp, success)
            for timestamp, success in self.recent_checks
            if timestamp > one_hour_ago
        ]

        if recent_checks:
            recent_successful = sum(1 for _, success in recent_checks if success)
            recent_total = len(recent_checks)
            self.availability = recent_successful / recent_total if recent_total > 0 else 0.0
        else:
            # No checks in last hour, fall back to overall metrics
            self.availability = self.successful_checks / self.total_checks if self.total_checks > 0 else 0.0

        # Success rate: overall ratio (all time)
        self.success_rate = self.successful_checks / self.total_checks

        # Average latency (from recent samples)
        if self.latency_samples:
            self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)

        # Online status
        self.online = (self.last_success or 0) > (self.last_failure or 0)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "device": self.device,
            "online": self.online,
            "availability": round(self.availability, 3),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "success_rate": round(self.success_rate, 3),
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "last_check": self.last_check,
            "last_check_iso": datetime.fromtimestamp(self.last_check).isoformat() + "Z"
            if self.last_check
            else None,
            "last_success": self.last_success,
            "last_success_iso": datetime.fromtimestamp(self.last_success).isoformat() + "Z"
            if self.last_success
            else None,
            "last_failure": self.last_failure,
            "last_failure_iso": datetime.fromtimestamp(self.last_failure).isoformat() + "Z"
            if self.last_failure
            else None,
            "latency_sample_count": len(self.latency_samples),
            "created_at": self.created_at,
            "created_at_iso": datetime.fromtimestamp(self.created_at).isoformat() + "Z",
        }


class HealthMonitor:
    """Continuous health monitoring for Cast devices."""

    def __init__(
        self,
        check_interval: float = 60.0,
        alert_callback: Optional[Callable[[str, dict], Any]] = None,
    ):
        """
        Initialize health monitor.

        Args:
            check_interval: Seconds between health checks
            alert_callback: Async callback for alerts (device, alert_data)
        """
        self.check_interval = check_interval
        self.alert_callback = alert_callback
        self.health_status: dict[str, DeviceHealth] = {}
        self.alerts: list[HealthAlert] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self, check_fn: Callable[[str], tuple[bool, float]]):
        """
        Start health monitoring.

        Args:
            check_fn: Async function that takes device name and returns (success, latency_ms)
        """
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop(check_fn))

    async def stop(self):
        """Stop health monitoring."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_health(self, device: str) -> Optional[DeviceHealth]:
        """
        Get health status for a device.

        Args:
            device: Device name

        Returns:
            DeviceHealth if found, None otherwise
        """
        return self.health_status.get(device)

    def list_health(self) -> list[DeviceHealth]:
        """
        List health status for all devices.

        Returns:
            List of DeviceHealth objects
        """
        return list(self.health_status.values())

    async def configure_alert(
        self,
        device: str,
        metric: str,
        threshold: float,
        action: str = "publish_nats",
        webhook_url: Optional[str] = None,
    ) -> dict:
        """
        Configure a health alert.

        Args:
            device: Device name
            metric: Metric to monitor ("availability", "latency", "success_rate")
            threshold: Alert threshold value
            action: Alert action ("publish_nats", "log", "webhook")
            webhook_url: Webhook URL for action="webhook"

        Returns:
            Result dict
        """
        if metric not in ["availability", "latency", "success_rate"]:
            return {
                "success": False,
                "error": f"Invalid metric: {metric}",
            }

        if action not in ["publish_nats", "log", "webhook"]:
            return {
                "success": False,
                "error": f"Invalid action: {action}",
            }

        if action == "webhook" and not webhook_url:
            return {
                "success": False,
                "error": "webhook_url required for action=webhook",
            }

        alert = HealthAlert(
            device=device,
            metric=metric,
            threshold=threshold,
            action=action,
            webhook_url=webhook_url,
        )

        self.alerts.append(alert)

        return {
            "success": True,
            "alert": alert.to_dict(),
            "message": f"Configured alert for {device} {metric}",
        }

    def list_alerts(self) -> list[HealthAlert]:
        """
        List all configured alerts.

        Returns:
            List of HealthAlert objects
        """
        return [a for a in self.alerts if a.enabled]

    async def _monitor_loop(self, check_fn: Callable[[str], tuple[bool, float]]):
        """
        Main health monitoring loop.

        Args:
            check_fn: Async function that takes device name and returns (success, latency_ms)
        """
        while self._running:
            try:
                async with self._lock:
                    # Check all devices with health status
                    for device_name in list(self.health_status.keys()):
                        try:
                            success, latency_ms = await check_fn(device_name)

                            health = self.health_status.get(device_name)
                            if health:
                                health.record_check(success, latency_ms)

                                # Check alerts
                                await self._check_alerts(health)

                        except Exception as e:
                            print(f"Health check error for {device_name}: {e}")

                # Sleep until next check
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Monitor loop error: {e}")
                await asyncio.sleep(5)

    def track_device(self, device_name: str):
        """
        Start tracking a device.

        Args:
            device_name: Device name
        """
        if device_name not in self.health_status:
            self.health_status[device_name] = DeviceHealth(device=device_name)

    def untrack_device(self, device_name: str):
        """
        Stop tracking a device.

        Args:
            device_name: Device name
        """
        self.health_status.pop(device_name, None)

    async def _check_alerts(self, health: DeviceHealth):
        """
        Check if any alerts should be triggered.

        Args:
            health: Device health status
        """
        if not self.alert_callback:
            return

        for alert in self.alerts:
            if not alert.enabled:
                continue

            if alert.device != health.device:
                continue

            # Check metric against threshold
            trigger = False
            if alert.metric == "availability":
                trigger = health.availability < alert.threshold
            elif alert.metric == "latency":
                trigger = health.avg_latency_ms > alert.threshold
            elif alert.metric == "success_rate":
                trigger = health.success_rate < alert.threshold

            if trigger:
                await self.alert_callback(
                    health.device,
                    {
                        "alert": alert.to_dict(),
                        "current_health": health.to_dict(),
                        "triggered_at": datetime.utcnow().isoformat() + "Z",
                    },
                )
