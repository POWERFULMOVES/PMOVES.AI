"""
PMOVES Gateway Agent - NATS Integration Module

Provides NATS message bus integration for Gateway Agent to:
1. Subscribe to BoTZ Gateway work availability events
2. Publish tool execution results
3. Enable credential sharing via SecretManager

NATS Subjects:
- botz.workitem.available.v1 - Work items available from BoTZ Gateway
- botz.workitem.claimed.v1 - Work item claimed notification
- botz.workitem.completed.v1 - Work item completed notification
- botz.gateway.heartbeat.v1 - Gateway Agent heartbeat
- gateway.tool.executed.v1 - Tool execution results
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import nats
    from nats.js.api import ConsumerConfig, DeliverPolicy
    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False

logger = logging.getLogger(__name__)


# Configuration
NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
NATS_USER = os.environ.get("NATS_USER", "")
NATS_PASS = os.environ.get("NATS_PASS", "")
NATS_ENABLED = os.environ.get("NATS_ENABLED", "true").lower() == "true"

# BoTZ Gateway integration subjects
BOTZ_WORKITEM_AVAILABLE = "botz.workitem.available.v1"
BOTZ_WORKITEM_CLAIMED = "botz.workitem.claimed.v1"
BOTZ_WORKITEM_COMPLETED = "botz.workitem.completed.v1"
BOTZ_HEARTBEAT = "botz.gateway.heartbeat.v1"

# Gateway Agent subjects
GATEWAY_TOOL_EXECUTED = "gateway.tool.executed.v1"
GATEWAY_HEARTBEAT = "gateway.agent.heartbeat.v1"
GATEWAY_CREDENTIAL_REQUEST = "gateway.credential.request.v1"
GATEWAY_CREDENTIAL_RESPONSE = "gateway.credential.response.v1"

# Skill level mapping (Gateway Agent tool categories → BoTZ skill levels)
SKILL_LEVEL_MAPPING = {
    # Basic skills - Simple tool execution
    "basic": [
        "general", "api", "documents"
    ],
    # TAC (Tool-Augmented Code) enabled - Code-related tools
    "tac_enabled": [
        "automation", "infrastructure"
    ],
    # MCP Augmented - Advanced MCP tools
    "mcp_augmented": [
        "memory", "execution"
    ],
    # Agentic - Complex multi-step tools
    "agentic": [
        "research", "vision"
    ]
}


def infer_skill_level(category: str) -> str:
    """
    Map Gateway Agent tool category to BoTZ skill level.

    Args:
        category: Gateway Agent tool category

    Returns:
        BoTZ skill level (basic, tac_enabled, mcp_augmented, agentic)
    """
    for skill_level, categories in SKILL_LEVEL_MAPPING.items():
        if category in categories:
            return skill_level
    return "basic"


class NATSIntegration:
    """NATS message bus integration for Gateway Agent"""

    def __init__(self):
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[nats.js.JetStreamContext] = None
        self._running = False
        self._subscriptions: List[nats.js.Subscription] = []
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Connect to NATS server"""
        if not NATS_AVAILABLE:
            logger.warning("NATS not available - nats-python library not installed")
            return False

        if not NATS_ENABLED:
            logger.info("NATS integration disabled by NATS_ENABLED environment variable")
            return False

        try:
            # Build connection options
            options = {
                "servers": NATS_URL,
                "name": "gateway-agent",
                "reconnected_wait": 2,
                "max_reconnect_attempts": 10,
                "connect_timeout": 10,
            }

            # Add authentication if provided
            if NATS_USER and NATS_PASS:
                options["user"] = NATS_USER
                options["password"] = NATS_PASS

            self.nc = await nats.connect(**options)
            self.js = self.nc.jetstream()

            logger.info(f"Connected to NATS at {NATS_URL}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from NATS server"""
        self._running = False

        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe from all subscriptions
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception as e:
                logger.warning(f"Error unsubscribing: {e}")
        self._subscriptions.clear()

        # Close connection
        if self.nc:
            try:
                await self.nc.close()
            except Exception as e:
                logger.warning(f"Error closing NATS connection: {e}")

        logger.info("Disconnected from NATS")

    async def subscribe_to_workitem_available(
        self,
        callback,
        stream: str = "BOTZ_COORDINATION",
        consumer: str = "gateway-agent"
    ) -> bool:
        """
        Subscribe to BoTZ Gateway work item availability events.

        Args:
            callback: Async callback function(work_item_data)
            stream: JetStream stream name
            consumer: Consumer name

        Returns:
            True if subscription successful
        """
        if not self.js:
            logger.warning("NATS JetStream not available")
            return False

        try:
            # Create or update consumer
            consumer_config = ConsumerConfig(
                ack_policy="explicit",
                deliver_policy=DeliverPolicy.ALL,
                filter_subject=f"{BOTZ_WORKITEM_AVAILABLE}",
                durable_name=consumer,
            )

            try:
                # Add consumer
                await self.js.add_consumer(stream, consumer_config)
                logger.info(f"Created NATS consumer: {consumer}")
            except Exception as e:
                # Consumer might already exist
                if "already exists" not in str(e):
                    logger.warning(f"Error creating consumer: {e}")

            # Subscribe
            sub = await self.js.pull_subscribe(
                subject=f"{BOTZ_WORKITEM_AVAILABLE}",
                stream=stream,
                consumer=consumer,
                cb=callback
            )

            self._subscriptions.append(sub)
            logger.info(f"Subscribed to {BOTZ_WORKITEM_AVAILABLE}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to workitem available: {e}")
            return False

    async def publish_workitem_claimed(
        self,
        workitem_id: str,
        gateway_agent_id: str,
        skill_level: str = "basic"
    ) -> bool:
        """
        Publish work item claimed notification.

        Args:
            workitem_id: Work item ID
            gateway_agent_id: Gateway Agent instance ID
            skill_level: BoTZ skill level

        Returns:
            True if published successfully
        """
        if not self.nc:
            return False

        try:
            message = {
                "workitem_id": workitem_id,
                "claimed_by": "gateway-agent",
                "gateway_agent_id": gateway_agent_id,
                "skill_level": skill_level,
                "claimed_at": datetime.now().isoformat(),
            }

            await self.nc.publish(
                BOTZ_WORKITEM_CLAIMED,
                json.dumps(message).encode()
            )

            logger.debug(f"Published workitem claimed: {workitem_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish workitem claimed: {e}")
            return False

    async def publish_workitem_completed(
        self,
        workitem_id: str,
        result: Dict[str, Any],
        execution_time_ms: int
    ) -> bool:
        """
        Publish work item completion notification.

        Args:
            workitem_id: Work item ID
            result: Execution result
            execution_time_ms: Execution time in milliseconds

        Returns:
            True if published successfully
        """
        if not self.nc:
            return False

        try:
            message = {
                "workitem_id": workitem_id,
                "completed_by": "gateway-agent",
                "success": result.get("success", True),
                "execution_time_ms": execution_time_ms,
                "completed_at": datetime.now().isoformat(),
                "result": result.get("result") if result.get("success") else None,
                "error": result.get("error") if not result.get("success") else None,
            }

            await self.nc.publish(
                BOTZ_WORKITEM_COMPLETED,
                json.dumps(message).encode()
            )

            logger.debug(f"Published workitem completed: {workitem_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish workitem completed: {e}")
            return False

    async def publish_tool_executed(
        self,
        tool_name: str,
        category: str,
        skill_level: str,
        result: Dict[str, Any],
        execution_time_ms: int
    ) -> bool:
        """
        Publish tool execution event.

        Args:
            tool_name: Tool name
            category: Tool category
            skill_level: BoTZ skill level
            result: Execution result
            execution_time_ms: Execution time in milliseconds

        Returns:
            True if published successfully
        """
        if not self.nc:
            return False

        try:
            message = {
                "tool_name": tool_name,
                "category": category,
                "skill_level": skill_level,
                "success": result.get("success", True),
                "execution_time_ms": execution_time_ms,
                "executed_at": datetime.now().isoformat(),
                "gateway_agent": "gateway-agent",
            }

            await self.nc.publish(
                GATEWAY_TOOL_EXECUTED,
                json.dumps(message).encode()
            )

            logger.debug(f"Published tool executed: {tool_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish tool executed: {e}")
            return False

    async def start_heartbeat(self, interval_seconds: int = 15) -> None:
        """
        Start periodic heartbeat to announce Gateway Agent availability.

        Args:
            interval_seconds: Heartbeat interval in seconds
        """
        if not self.nc or self._running:
            return

        self._running = True

        async def heartbeat_loop():
            while self._running:
                try:
                    message = {
                        "gateway_agent": "gateway-agent",
                        "port": os.environ.get("PORT", "8100"),
                        "skill_levels": list(SKILL_LEVEL_MAPPING.keys()),
                        "timestamp": datetime.now().isoformat(),
                        "status": "healthy",
                    }

                    await self.nc.publish(
                        GATEWAY_HEARTBEAT,
                        json.dumps(message).encode()
                    )

                    logger.debug("Published Gateway Agent heartbeat")

                except Exception as e:
                    logger.warning(f"Heartbeat error: {e}")

                await asyncio.sleep(interval_seconds)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(f"Started heartbeat (interval: {interval_seconds}s)")

    async def subscribe_to_credential_requests(
        self,
        secret_manager,  # SecretManager instance
        stream: str = "BOTZ_COORDINATION"
    ) -> bool:
        """
        Subscribe to credential request events from BoTZ Gateway.

        Enables credential sharing: BoTZ Gateway can request credentials
        for tools it wants to execute.

        Args:
            secret_manager: SecretManager instance
            stream: JetStream stream name

        Returns:
            True if subscription successful
        """
        if not self.js:
            return False

        async def credential_callback(msg):
            """Handle credential request"""
            try:
                data = json.loads(msg.data.decode())
                service = data.get("service")
                request_id = data.get("request_id")

                # Get credential from SecretManager
                credential = secret_manager.get_credential(service)

                # Publish response
                response = {
                    "request_id": request_id,
                    "service": service,
                    "has_credential": credential is not None,
                    "timestamp": datetime.now().isoformat(),
                }

                await self.nc.publish(
                    GATEWAY_CREDENTIAL_RESPONSE,
                    json.dumps(response).encode()
                )

                await msg.ack()

                logger.debug(f"Responded to credential request for {service}")

            except Exception as e:
                logger.error(f"Credential request error: {e}")
                await msg.nak()

        try:
            sub = await self.js.subscribe(
                subject=GATEWAY_CREDENTIAL_REQUEST,
                stream=stream,
                cb=credential_callback
            )

            self._subscriptions.append(sub)
            logger.info(f"Subscribed to {GATEWAY_CREDENTIAL_REQUEST}")
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to credential requests: {e}")
            return False

    async def publish_credential_available(
        self,
        services: List[str]
    ) -> bool:
        """
        Publish available credentials announcement.

        Args:
            services: List of services with available credentials

        Returns:
            True if published successfully
        """
        if not self.nc:
            return False

        try:
            message = {
                "gateway_agent": "gateway-agent",
                "services": services,
                "timestamp": datetime.now().isoformat(),
            }

            await self.nc.publish(
                f"{GATEWAY_CREDENTIAL_REQUEST}.available",
                json.dumps(message).encode()
            )

            logger.info(f"Published {len(services)} available credentials")
            return True

        except Exception as e:
            logger.error(f"Failed to publish credential available: {e}")
            return False


# Global NATS integration instance
nats_integration = NATSIntegration()
