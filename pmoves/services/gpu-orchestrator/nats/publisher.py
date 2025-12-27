"""NATS publisher for GPU mesh events."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Optional

try:
    from nats.aio.client import Client as NATS
    from nats.aio.errors import ErrConnectionClosed, ErrTimeout

    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False

from config import get_settings

logger = logging.getLogger(__name__)


# NATS subjects for GPU events
class GpuSubjects:
    """NATS subjects for GPU orchestrator events."""

    STATUS = "mesh.gpu.status.v1"
    MODEL_LOADED = "mesh.gpu.model.loaded.v1"
    MODEL_UNLOADED = "mesh.gpu.model.unloaded.v1"
    VRAM_WARNING = "mesh.gpu.vram.warning.v1"
    COMMAND = "mesh.gpu.command.v1"


class GpuNatsPublisher:
    """Publishes GPU status and events to NATS.

    Events:
    - mesh.gpu.status.v1: Periodic status updates (every 5s)
    - mesh.gpu.model.loaded.v1: Model loaded event
    - mesh.gpu.model.unloaded.v1: Model unloaded event
    - mesh.gpu.vram.warning.v1: VRAM threshold warning
    """

    def __init__(
        self,
        nats_url: Optional[str] = None,
        status_interval: float = 5.0,
    ):
        settings = get_settings()
        self.nats_url = nats_url or settings.nats_url
        self.status_interval = status_interval
        self.vram_warning_threshold = settings.vram_warning_threshold

        self._nc: Optional["NATS"] = None
        self._connected = False
        self._status_task: Optional[asyncio.Task] = None
        self._get_status_callback: Optional[Callable] = None
        self._last_warning_sent: Optional[datetime] = None

    async def connect(self) -> bool:
        """Connect to NATS server."""
        if not NATS_AVAILABLE:
            logger.warning("NATS library not available - running without NATS")
            return False

        try:
            self._nc = NATS()
            await self._nc.connect(
                servers=[self.nats_url],
                reconnect_time_wait=2,
                max_reconnect_attempts=-1,  # Unlimited
            )
            self._connected = True
            logger.info(f"Connected to NATS at {self.nats_url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from NATS."""
        await self.stop_status_loop()

        if self._nc and self._connected:
            try:
                await self._nc.close()
            except Exception as e:
                logger.debug(f"Error closing NATS connection: {e}")

        self._connected = False
        logger.info("Disconnected from NATS")

    def set_status_callback(self, callback: Callable) -> None:
        """Set callback to get current GPU status for publishing."""
        self._get_status_callback = callback

    async def start_status_loop(self) -> None:
        """Start periodic status publishing."""
        if self._status_task is None:
            self._status_task = asyncio.create_task(self._status_loop())
            logger.info(f"Started GPU status publishing (interval: {self.status_interval}s)")

    async def stop_status_loop(self) -> None:
        """Stop periodic status publishing."""
        if self._status_task:
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass
            self._status_task = None
            logger.info("Stopped GPU status publishing")

    async def _status_loop(self) -> None:
        """Publish GPU status periodically."""
        while True:
            try:
                await asyncio.sleep(self.status_interval)

                if self._get_status_callback:
                    status = await self._get_status_callback()
                    await self.publish_status(status)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status loop: {e}")

    async def publish_status(self, status: Dict) -> None:
        """Publish GPU status event."""
        if not self._connected:
            return

        try:
            await self._publish(
                GpuSubjects.STATUS,
                {
                    "type": "mesh.gpu.status.v1",
                    "data": status,
                    "ts": int(datetime.now().timestamp()),
                },
            )

            # Check for VRAM warning
            metrics = status.get("metrics", {})
            vram_percent = metrics.get("vram_usage_percent", 0)

            if vram_percent >= self.vram_warning_threshold * 100:
                await self._maybe_send_vram_warning(metrics)

        except Exception as e:
            logger.error(f"Error publishing status: {e}")

    async def publish_model_loaded(self, model_key: str, vram_mb: int) -> None:
        """Publish model loaded event."""
        if not self._connected:
            return

        await self._publish(
            GpuSubjects.MODEL_LOADED,
            {
                "type": "mesh.gpu.model.loaded.v1",
                "model_key": model_key,
                "vram_mb": vram_mb,
                "ts": int(datetime.now().timestamp()),
            },
        )
        logger.debug(f"Published model loaded event: {model_key}")

    async def publish_model_unloaded(self, model_key: str) -> None:
        """Publish model unloaded event."""
        if not self._connected:
            return

        await self._publish(
            GpuSubjects.MODEL_UNLOADED,
            {
                "type": "mesh.gpu.model.unloaded.v1",
                "model_key": model_key,
                "ts": int(datetime.now().timestamp()),
            },
        )
        logger.debug(f"Published model unloaded event: {model_key}")

    async def _maybe_send_vram_warning(self, metrics: Dict) -> None:
        """Send VRAM warning if not recently sent."""
        now = datetime.now()

        # Rate limit warnings to once per minute
        if self._last_warning_sent:
            if (now - self._last_warning_sent).total_seconds() < 60:
                return

        await self._publish(
            GpuSubjects.VRAM_WARNING,
            {
                "type": "mesh.gpu.vram.warning.v1",
                "vram_usage_percent": metrics.get("vram_usage_percent"),
                "used_vram_mb": metrics.get("used_vram_mb"),
                "free_vram_mb": metrics.get("free_vram_mb"),
                "threshold_percent": self.vram_warning_threshold * 100,
                "ts": int(now.timestamp()),
            },
        )

        self._last_warning_sent = now
        logger.warning(
            f"VRAM warning: {metrics.get('vram_usage_percent'):.1f}% used "
            f"(threshold: {self.vram_warning_threshold * 100}%)"
        )

    async def _publish(self, subject: str, data: Dict) -> None:
        """Publish a message to NATS."""
        if not self._nc or not self._connected:
            return

        try:
            payload = json.dumps(data).encode()
            await self._nc.publish(subject, payload)
        except ErrConnectionClosed:
            logger.warning("NATS connection closed, attempting reconnect...")
            self._connected = False
        except ErrTimeout:
            logger.warning("NATS publish timeout")
        except Exception as e:
            logger.error(f"Error publishing to {subject}: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS."""
        return self._connected
