#!/usr/bin/env python3
"""
Chat Relay Service - Phase 9

Bridges NATS agent responses to Supabase Realtime chat_messages table.

Flow:
  User Input (UI) → POST /api/chat/send
                          ↓
                    NATS: agent.request.v1
                          ↓
                    Agent Zero / Archon
                          ↓
                    NATS: agent.response.v1
                          ↓
                    chat-relay (this service)
                          ↓
                    INSERT chat_messages
                          ↓
                    Supabase Realtime → UI
"""

import asyncio
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import nats
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg
from supabase import create_client, Client as SupabaseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("chat-relay")


@dataclass
class Config:
    """Service configuration from environment."""
    nats_url: str
    supabase_url: str
    supabase_service_role_key: str
    health_port: int

    # NATS subjects
    agent_response_subject: str = "agent.response.v1"
    agent_request_subject: str = "agent.request.v1"

    # Durable consumer name for JetStream
    consumer_name: str = "chat-relay-consumer"
    stream_name: str = "PMOVES_EVENTS"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            nats_url=os.getenv("NATS_URL", "nats://nats:4222"),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            health_port=int(os.getenv("HEALTH_PORT", "8102")),
            agent_response_subject=os.getenv("AGENT_RESPONSE_SUBJECT", "agent.response.v1"),
            agent_request_subject=os.getenv("AGENT_REQUEST_SUBJECT", "agent.request.v1"),
        )

    def validate(self) -> None:
        if not self.supabase_url:
            raise ValueError("SUPABASE_URL is required")
        if not self.supabase_service_role_key:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required")


class ChatRelayService:
    """Main service that relays NATS messages to Supabase."""

    def __init__(self, config: Config):
        self.config = config
        self.nc: Optional[NATS] = None
        self.js = None  # JetStream context
        self.sub = None
        self.supabase: Optional[SupabaseClient] = None
        self.running = False
        self.messages_relayed = 0
        self.errors = 0
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_complete = False

    async def connect(self) -> None:
        """Connect to NATS and Supabase."""
        logger.info(f"Connecting to NATS at {self.config.nats_url}")

        self.nc = await nats.connect(
            self.config.nats_url,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,  # Infinite reconnects
            error_cb=self._on_nats_error,
            disconnected_cb=self._on_nats_disconnected,
            reconnected_cb=self._on_nats_reconnected,
        )

        # Get JetStream context
        self.js = self.nc.jetstream()

        logger.info(f"Connecting to Supabase at {self.config.supabase_url}")
        self.supabase = create_client(
            self.config.supabase_url,
            self.config.supabase_service_role_key,
        )

        logger.info("Connected to NATS and Supabase")

    async def _on_nats_error(self, e: Exception) -> None:
        logger.error(f"NATS error: {e}")
        self.errors += 1

    async def _on_nats_disconnected(self) -> None:
        logger.warning("NATS disconnected")

    async def _on_nats_reconnected(self) -> None:
        logger.info("NATS reconnected")

    async def subscribe(self) -> None:
        """Subscribe to agent response events."""
        logger.info(f"Subscribing to {self.config.agent_response_subject}")

        try:
            # Try JetStream subscription first
            self.sub = await self.js.subscribe(
                self.config.agent_response_subject,
                durable=self.config.consumer_name,
                cb=self._handle_message,
            )
            logger.info(f"JetStream subscription created: {self.config.consumer_name}")
        except Exception as e:
            # Fall back to core NATS subscription
            logger.warning(f"JetStream subscription failed ({e}), using core NATS")
            self.sub = await self.nc.subscribe(
                self.config.agent_response_subject,
                cb=self._handle_message,
            )
            logger.info("Core NATS subscription created")

    async def _handle_message(self, msg: Msg) -> None:
        """Handle incoming agent response message."""
        try:
            data = json.loads(msg.data.decode())
            logger.debug(f"Received message: {data}")

            # Extract fields from agent response
            session_id = data.get("session_id")
            owner_id = data.get("owner_id") or data.get("user_id")
            agent_id = data.get("agent_id") or data.get("agent")
            agent_name = data.get("agent_name") or agent_id
            content = data.get("content") or data.get("response") or data.get("message")
            message_type = data.get("message_type", "text")
            metadata = data.get("metadata", {})

            if not content:
                logger.warning(f"Message has no content: {data}")
                await msg.ack()
                return

            if not owner_id:
                # Use a default owner for system messages
                owner_id = os.getenv("DEFAULT_OWNER_ID", "00000000-0000-0000-0000-000000000000")

            # Insert into chat_messages table
            record = {
                "owner_id": owner_id,
                "role": "agent",
                "agent": agent_name,
                "agent_id": agent_id,
                "content": content,
                "message_type": message_type,
                "session_id": session_id,
                "metadata": metadata,
            }

            result = self.supabase.table("chat_messages").insert(record).execute()

            if result.data:
                self.messages_relayed += 1
                logger.info(f"Relayed message from {agent_name}: {content[:50]}...")
                # Only acknowledge after successful insert to prevent data loss
                await msg.ack()
            else:
                logger.error(f"Failed to insert message: {result}")
                self.errors += 1
                # Don't ack - let message be redelivered for retry

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message: {e}")
            self.errors += 1
            await msg.ack()  # Ack to avoid redelivery of bad messages
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.errors += 1
            # Don't ack - let it be redelivered

    async def run(self) -> None:
        """Main run loop."""
        self.running = True

        await self.connect()
        await self.subscribe()

        # Start health server
        health_task = asyncio.create_task(self._run_health_server())

        logger.info("Chat relay service running")

        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            health_task.cancel()
            await self.shutdown()

    async def shutdown(self) -> None:
        """Clean shutdown."""
        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            logger.info("Shutting down chat relay service")
            self.running = False

            if self.sub:
                try:
                    await self.sub.unsubscribe()
                except Exception as e:
                    # If the NATS connection is already closed (or mid-shutdown), unsubscribe may raise.
                    logger.warning(f"Subscription unsubscribe failed during shutdown: {e}")
                finally:
                    self.sub = None

            if self.nc:
                try:
                    await self.nc.drain()
                except Exception as e:
                    logger.warning(f"NATS drain failed during shutdown: {e}")
                finally:
                    self.nc = None

            self._shutdown_complete = True
            logger.info(f"Shutdown complete. Relayed {self.messages_relayed} messages, {self.errors} errors")

    async def _run_health_server(self) -> None:
        """Simple HTTP health server."""
        from aiohttp import web

        async def health_handler(request: web.Request) -> web.Response:
            return web.json_response({
                "status": "healthy" if self.running else "unhealthy",
                "service": "chat-relay",
                "messages_relayed": self.messages_relayed,
                "errors": self.errors,
                "nats_connected": self.nc.is_connected if self.nc else False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        async def metrics_handler(request: web.Request) -> web.Response:
            metrics = f"""# HELP chat_relay_messages_relayed Total messages relayed
# TYPE chat_relay_messages_relayed counter
chat_relay_messages_relayed {self.messages_relayed}

# HELP chat_relay_errors Total errors
# TYPE chat_relay_errors counter
chat_relay_errors {self.errors}

# HELP chat_relay_up Service status
# TYPE chat_relay_up gauge
chat_relay_up {1 if self.running else 0}
"""
            return web.Response(text=metrics, content_type="text/plain")

        app = web.Application()
        app.router.add_get("/healthz", health_handler)
        app.router.add_get("/metrics", metrics_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.config.health_port)

        logger.info(f"Health server listening on port {self.config.health_port}")
        await site.start()

        try:
            while self.running:
                await asyncio.sleep(1)
        finally:
            await runner.cleanup()


async def main() -> None:
    """Main entry point."""
    config = Config.from_env()

    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    service = ChatRelayService(config)

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(service.shutdown()))

    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
