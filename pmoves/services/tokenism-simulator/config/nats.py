"""
NATS Message Bus Integration for PMOVES Tokenism Simulator

Following PMOVES.AI patterns:
- JSON message encoding
- Async connection handling
- Basic publish/subscribe (JetStream can be added later)
"""

import asyncio
import json
import logging
from typing import Any, Callable, Optional
from datetime import datetime, timezone

import nats

from config import NATSConfig

logger = logging.getLogger(__name__)


class NATSClient:
    """
    NATS client for PMOVES.AI integration.

    Publishes simulation results to:
    - tokenism.simulation.result.v1
    - tokenism.calibration.result.v1
    - tokenism.cgp.ready.v1
    """

    def __init__(self, config: NATSConfig):
        """Initialize NATS client with configuration.

        Args:
            config: NATS connection configuration including URL, client name,
                    and JetStream settings.

        Note:
            The client is not connected until :meth:`connect` is called.
        """
        self.config = config
        self.nc: Optional[nats.aio.client.Client] = None
        self.js: Optional[nats.aio.client.JetStreamContext] = None
        self._connected = False
        self._subscribers = []

    async def connect(self) -> None:
        """Connect to NATS with retry logic.

        Raises:
            ConnectionError: If connection fails after max retry attempts
        """
        backoff = 1.0
        max_backoff = 30.0
        max_attempts = 5

        for attempt in range(max_attempts):
            try:
                options = {
                    'servers': self.config.url,
                    'name': self.config.client_name,
                    'connect_timeout': 10,
                    'reconnect_time_wait': 2,
                    'max_reconnect_attempts': -1,  # Infinite reconnect after initial
                }

                self.nc = await nats.connect(**options)
                self._connected = True

                # Try to enable JetStream if configured
                if self.config.jetstream_enabled:
                    try:
                        self.js = self.nc.jetstream()
                        logger.info("JetStream enabled")
                    except Exception as e:
                        logger.warning(f"JetStream not available: {e}")

                logger.info(f"Connected to NATS at {self.config.url}")
                return

            except Exception as e:
                logger.warning(
                    f"NATS connection attempt {attempt+1}/{max_attempts} failed: {e}"
                )
                if attempt < max_attempts - 1:
                    logger.info(f"Retrying in {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)

        raise ConnectionError(
            f"Failed to connect to NATS at {self.config.url} after {max_attempts} attempts"
        )

    async def publish(self, subject: str, data: dict[str, Any]) -> bool:
        """
        Publish a message to a NATS subject.

        Args:
            subject: NATS subject to publish to
            data: Message data (will be JSON serialized)

        Returns:
            True if published successfully, False otherwise
        """
        if not self._connected or not self.nc:
            logger.warning("NATS not connected, cannot publish")
            return False

        try:
            # Add metadata to message
            envelope = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'source': self.config.client_name,
                'data': data,
            }

            payload = json.dumps(envelope).encode('utf-8')

            # Publish (JetStream will ack if available)
            await self.nc.publish(subject, payload)
            logger.debug(f"Published to {subject}")

            return True

        except Exception as e:
            logger.error(f"Error publishing to {subject}: {e}")
            return False

    async def publish_simulation_result(self, result: dict[str, Any]) -> bool:
        """Publish simulation result to tokenism.simulation.result.v1.

        Args:
            result: Simulation result data including metrics and parameters.

        Returns:
            True if published successfully, False if NATS not connected.
        """
        return await self.publish(self.config.simulation_result_subject, result)

    async def publish_calibration_result(self, result: dict[str, Any]) -> bool:
        """Publish calibration result to tokenism.calibration.result.v1.

        Args:
            result: Calibration result including parameter adjustments.

        Returns:
            True if published successfully, False if NATS not connected.
        """
        return await self.publish(self.config.calibration_result_subject, result)

    async def publish_cgp_packet(self, cgp_data: dict[str, Any]) -> bool:
        """Publish CHIT geometry packet to tokenism.cgp.ready.v1.

        Args:
            cgp_data: CHIT Geometry Packet with wealth distribution geometry.

        Returns:
            True if published successfully, False if NATS not connected.
        """
        return await self.publish(self.config.cgp_ready_subject, cgp_data)

    async def subscribe(
        self,
        subject: str,
        handler: Callable[[dict[str, Any]], Any],
        queue_group: Optional[str] = None
    ) -> bool:
        """
        Subscribe to a NATS subject.

        Args:
            subject: NATS subject to subscribe to
            handler: Async callback function for messages
            queue_group: Optional queue group for load balancing

        Returns:
            True if subscribed successfully, False otherwise
        """
        if not self._connected or not self.nc:
            logger.warning("NATS not connected, cannot subscribe")
            return False

        try:
            async def message_handler(msg: nats.aio.client.Msg):
                try:
                    data = json.loads(msg.data.decode('utf-8'))
                    await handler(data)
                except Exception as e:
                    logger.error(f"Error handling message from {subject}: {e}")

            sub = await self.nc.subscribe(
                subject,
                queue=queue_group,
                cb=message_handler,
            )

            self._subscribers.append(sub)
            logger.info(f"Subscribed to {subject}")
            return True

        except Exception as e:
            logger.error(f"Error subscribing to {subject}: {e}")
            return False

    async def close(self) -> None:
        """Close NATS connection and cleanup resources.

        Unsubscribes all active subscriptions and closes the NATS connection.
        Safe to call multiple times (idempotent).
        """
        if self.nc:
            await self.nc.close()
            self._connected = False
            logger.info("NATS connection closed")

    def is_connected(self) -> bool:
        """Check if connected to NATS.

        Returns:
            True if connected to NATS server, False otherwise.
        """
        return self._connected and self.nc is not None


# Global NATS client instance
_nats_client: Optional[NATSClient] = None


async def get_nats_client(config: Optional[NATSConfig] = None) -> NATSClient:
    """Get or create the global NATS client.

    Raises:
        ConnectionError: If NATS connection fails
    """
    global _nats_client

    if _nats_client is None:
        cfg = config or NATSConfig()
        _nats_client = NATSClient(cfg)
        try:
            await _nats_client.connect()
        except Exception as e:
            # Reset client on connection failure so it can be retried
            _nats_client = None
            raise

    return _nats_client
