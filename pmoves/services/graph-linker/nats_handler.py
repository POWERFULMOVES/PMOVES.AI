"""NATS subscription handler with reconnection logic and dead-letter publishing.

Subscribes to the same NATS subjects as the original linker.py:
  - gen.image.result.v1
  - analysis.extract_topics.result.v1
  - kb.upsert.request.v1
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

import structlog
from nats.aio.client import Client as NATSClient
from nats.aio.subscription import Subscription
from nats.errors import ConnectionClosedError, NoServersError, TimeoutError as NATSTimeoutError

from config import Settings
from models import (
    NATSMessage,
    GenImageResultMessage,
    AnalysisTopicsMessage,
    KBUpsertMessage,
)
from neo4j_client import Neo4jClient

logger = structlog.get_logger(__name__)


class _Counters:
    """""""""In-process message counters for /metrics endpoint."""""""""
    def __init__(self) -> None:
        self.received: int = 0
        self.processed: int = 0
        self.failed: int = 0
        self.dead_lettered: int = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "nats_messages_received": self.received,
            "nats_messages_processed": self.processed,
            "nats_messages_failed": self.failed,
            "nats_messages_dead_lettered": self.dead_lettered,
        }


counters = _Counters()


class MockNATSMessage:
    """""""""Simulates a nats.aio.msg.Msg for testing."""""""""
    def __init__(self, data: bytes, subject: str = ""):
        self.data = data
        self.subject = subject


class NATSHandler:
    """""""""Manages NATS connection, subscriptions, reconnection, and dead-letter publishing."""""""""

    def __init__(self, settings: Settings, neo4j_client: Neo4jClient) -> None:
        self._settings = settings
        self._neo4j = neo4j_client
        self._nc: Optional[NATSClient] = None
        self._subscriptions: list[Subscription] = []

    # -- Lifecycle --------------------------------------------------------

    async def connect(self) -> None:
        """""""""Connect to NATS with reconnection settings."""""""""
        self._nc = NATSClient()
        try:
            await self._nc.connect(
                servers=[self._settings.nats_url],
                name=self._settings.nats_name,
                reconnect_time_wait=self._settings.nats_reconnect_wait,
                max_reconnect_attempts=self._settings.nats_max_reconnect_attempts,
                pending_msg_limit=self._settings.nats_pending_msg_limit,
            )
            logger.info("nats.connected", url=self._settings.nats_url)
        except (ConnectionClosedError, NoServersError, NATSTimeoutError) as exc:
            logger.error("nats.connection_failed", error=str(exc))
            raise

    async def subscribe(self) -> None:
        """""""""Subscribe to all configured NATS subjects."""""""""
        if self._nc is None:
            raise RuntimeError("NATS not connected")

        for subject in self._settings.subjects:
            sub = await self._nc.subscribe(subject, cb=self._make_callback(subject))
            self._subscriptions.append(sub)
            logger.info("nats.subscribed", subject=subject)

    async def close(self) -> None:
        """""""""Drain subscriptions and close NATS connection."""""""""
        if self._nc:
            try:
                for sub in self._subscriptions:
                    await sub.drain()
                await self._nc.close()
            except Exception as exc:
                logger.warning("nats.close_error", error=str(exc))
            finally:
                self._nc = None
                self._subscriptions.clear()
                logger.info("nats.closed")

    @property
    def is_connected(self) -> bool:
        """""""""Check if NATS connection is alive."""""""""
        return self._nc is not None and self._nc.is_connected

    # -- Callback factory -------------------------------------------------

    def _make_callback(self, subject: str) -> Callable:
        """""""""Create a message callback bound to a specific subject."""""""""
        async def _callback(msg: Any) -> None:
            counters.received += 1
            try:
                await self._handle_message(subject, msg)
                counters.processed += 1
            except Exception as exc:
                counters.failed += 1
                logger.error("nats.message_failed", subject=subject, error=str(exc))
                await self._publish_dead_letter(subject, msg, str(exc))

        return _callback

    async def _handle_message(self, subject: str, msg: Any) -> None:
        """""""""Deserialize, route, and process a NATS message."""""""""
        raw = msg.data.decode("utf-8") if isinstance(msg.data, bytes) else msg.data
        envelope = NATSMessage.model_validate_json(raw)

        if subject == "gen.image.result.v1":
            parsed = GenImageResultMessage.from_envelope(envelope)
            self._neo4j.handle_gen_image_result(parsed)
        elif subject == "analysis.extract_topics.result.v1":
            parsed = AnalysisTopicsMessage.from_envelope(envelope)
            self._neo4j.handle_analysis_topics_result(parsed)
        elif subject == "kb.upsert.request.v1":
            parsed = KBUpsertMessage.from_envelope(envelope)
            self._neo4j.handle_kb_upsert_request(parsed)
        else:
            logger.warning("nats.unknown_subject", subject=subject)

    # -- Dead-letter ------------------------------------------------------

    async def _publish_dead_letter(
        self,
        subject: str,
        original_msg: Any,
        error: str,
    ) -> None:
        """""""""Publish failed message to dead-letter subject."""""""""
        counters.dead_lettered += 1
        dead_letter = {
            "original_subject": subject,
            "error": error,
            "data": (
                original_msg.data.decode("utf-8")
                if isinstance(original_msg.data, bytes)
                else str(original_msg.data)
            ),
        }
        try:
            if self._nc and self._nc.is_connected:
                await self._nc.publish(
                    self._settings.dead_letter_subject,
                    json.dumps(dead_letter).encode("utf-8"),
                )
                logger.info(
                    "dead_letter.published",
                    original_subject=subject,
                    dead_letter_subject=self._settings.dead_letter_subject,
                )
            else:
                logger.warning("dead_letter.nats_unavailable", original_subject=subject)
        except Exception as exc:
            logger.error("dead_letter.publish_failed", error=str(exc))
