"""Work Marshaling Service - P2P work allocation and distribution.

This service receives work requests from the P2P network and allocates
them to appropriate nodes based on capabilities, availability, and location.

Usage:
    from pmoves.services.work_marshaling import WorkMarshaling, run_marshaling

    # Run as standalone service
    await run_marshaling(
        nats_url="nats://localhost:4222",
        registry_url="http://localhost:8082",
    )

NATS Subjects:
    - compute.work.request.v1: Incoming work requests
    - compute.work.assigned.v1: Work assignment notifications
    - compute.work.completed.v1: Work completion notifications
    - compute.work.failed.v1: Work failure notifications
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from ..resource_detector.models import WorkRequest, WorkAssignment
from ..resource_detector.hardware import NodeTier

logger = logging.getLogger(__name__)


# NATS subjects for work marshaling
SUBJECTS = {
    "request": "compute.work.request.v1",
    "assigned": "compute.work.assigned.v1",
    "completed": "compute.work.completed.v1",
    "failed": "compute.work.failed.v1",
    "cancel": "compute.work.cancel.v1",
    "status": "compute.work.status.v1",
}


@dataclass
class WorkItem:
    """Active work item being tracked by the marshaler."""

    request: WorkRequest
    status: str = "pending"  # pending, assigned, running, completed, failed, cancelled
    assigned_node: Optional[str] = None
    assignment_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 300

    # Callbacks
    on_complete: Optional[Callable] = None
    on_failed: Optional[Callable] = None
    on_timeout: Optional[Callable] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if work item has expired."""
        if self.status in ("completed", "failed", "cancelled"):
            return False
        timeout = timedelta(seconds=self.timeout_seconds)
        return datetime.now() - self.created_at > timeout

    @property
    def is_stale(self) -> bool:
        """Check if assigned work is stale (node not responding)."""
        if self.status != "assigned":
            return False
        if self.assignment_time is None:
            return False
        stale_threshold = timedelta(seconds=60)
        return datetime.now() - self.assignment_time > stale_threshold


@dataclass
class MarshalingStats:
    """Statistics for the work marshaling service."""

    total_requests: int = 0
    assigned: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0
    retried: int = 0

    # Current state
    pending: int = 0
    running: int = 0

    # Timing
    avg_assignment_time_ms: float = 0.0
    avg_completion_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "total_requests": self.total_requests,
            "assigned": self.assigned,
            "completed": self.completed,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "timed_out": self.timed_out,
            "retried": self.retried,
            "pending": self.pending,
            "running": self.running,
            "avg_assignment_time_ms": round(self.avg_assignment_time_ms, 2),
            "avg_completion_time_ms": round(self.avg_completion_time_ms, 2),
        }


class WorkMarshaling:
    """Work marshaling service for P2P compute allocation.

    Listens for work requests, queries the node registry for suitable nodes,
    assigns work, and tracks completion.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        registry_url: str = "http://localhost:8082",
        assignment_timeout_seconds: int = 30,
        max_retries: int = 3,
        stale_check_interval_seconds: int = 60,
    ):
        """Initialize work marshaling service.

        Args:
            nats_url: NATS server URL
            registry_url: Node registry HTTP API URL
            assignment_timeout_seconds: Timeout for finding a node
            max_retries: Maximum retry attempts for failed work
            stale_check_interval_seconds: Interval for stale work checks
        """
        self.nats_url = nats_url
        self.registry_url = registry_url
        self.assignment_timeout = assignment_timeout_seconds
        self.max_retries = max_retries
        self.stale_check_interval = stale_check_interval_seconds

        # State
        self._work_items: Dict[str, WorkItem] = {}
        self._node_blacklist: Set[str] = set()
        self._stats = MarshalingStats()

        # NATS
        self._nc = None
        self._js = None
        self._subscriptions: List = []
        self._running = False
        self._stale_check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the marshaling service.

        Connects to NATS, subscribes to subjects, starts stale check task.
        """
        if self._running:
            logger.warning("Marshaling service already running")
            return

        try:
            import nats

            self._nc = await nats.connect(self.nats_url)
            self._js = self._nc.jetstream()

            logger.info(f"Connected to NATS at {self.nats_url}")

            # Subscribe to work requests
            await self._subscribe_requests()

            # Subscribe to completion notifications
            await self._subscribe_completions()

            # Subscribe to failure notifications
            await self._subscribe_failures()

            # Subscribe to status queries
            await self._subscribe_status()

            # Subscribe to cancellations
            await self._subscribe_cancellations()

            # Start stale check task
            self._stale_check_task = asyncio.create_task(self._stale_check_loop())

            self._running = True
            logger.info("Work marshaling service started")

        except ImportError:
            logger.error("nats-py not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to start marshaling service: {e}")
            raise

    async def stop(self):
        """Stop the marshaling service."""
        if not self._running:
            return

        self._running = False

        # Cancel stale check task
        if self._stale_check_task:
            self._stale_check_task.cancel()
            try:
                await self._stale_check_task
            except asyncio.CancelledError:
                pass

        # Unsubscribe and close NATS
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass

        if self._nc:
            await self._nc.close()

        logger.info("Work marshaling service stopped")

    async def _subscribe_requests(self):
        """Subscribe to work requests."""
        import nats
        import json

        async def on_request(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                request = WorkRequest.from_nats_message(payload)
                await self._handle_request(request, msg.reply)

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid work request message format: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "status": "error",
                        "error": "Invalid message format",
                        "error_id": "WORK_FORMAT_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())
            except (KeyError, ValueError, TypeError) as e:
                logger.error(f"Invalid work request payload: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "status": "error",
                        "error": "Invalid request parameters",
                        "error_id": "WORK_PARAM_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())
            except Exception as e:
                logger.error(f"Error processing work request: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "status": "error",
                        "error": "Request processing failed",
                        "error_id": "WORK_INTERNAL_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())

        # Subscribe with JetStream for durability
        try:
            await self._js.subscribe(
                subject=SUBJECTS["request"],
                stream="compute",
                durable_name="work-marshaling-requests",
                cb=on_request,
            )
            logger.info(f"Subscribed to {SUBJECTS['request']}")
        except Exception:
            # Fallback to regular subscription
            sub = await self._nc.subscribe(SUBJECTS["request"], cb=on_request)
            self._subscriptions.append(sub)
            logger.info(f"Subscribed to {SUBJECTS['request']} (non-JetStream)")

    async def _subscribe_completions(self):
        """Subscribe to work completion notifications."""
        import nats
        import json

        async def on_completion(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                work_id = payload.get("work_id")
                node_id = payload.get("node_id")

                await self._handle_completion(work_id, node_id, payload)

            except Exception as e:
                logger.error(f"Error processing completion: {e}", exc_info=True)

        sub = await self._nc.subscribe(SUBJECTS["completed"], cb=on_completion)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['completed']}")

    async def _subscribe_failures(self):
        """Subscribe to work failure notifications."""
        import nats
        import json

        async def on_failure(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                work_id = payload.get("work_id")
                node_id = payload.get("node_id")
                error = payload.get("error", "Unknown error")

                await self._handle_failure(work_id, node_id, error)

            except Exception as e:
                logger.error(f"Error processing failure: {e}", exc_info=True)

        sub = await self._nc.subscribe(SUBJECTS["failed"], cb=on_failure)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['failed']}")

    async def _subscribe_status(self):
        """Subscribe to status queries."""
        import nats
        import json

        async def on_status(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                work_id = payload.get("work_id")

                if work_id:
                    status = await self.get_work_status(work_id)
                else:
                    status = self.get_stats()

                if msg.reply:
                    await self._nc.publish(msg.reply, json.dumps(status).encode())

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid status query message format: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "error": "Invalid message format",
                        "error_id": "STATUS_FORMAT_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())
            except Exception as e:
                logger.error(f"Error processing status query: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "error": "Status query failed",
                        "error_id": "STATUS_INTERNAL_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())

        sub = await self._nc.subscribe(SUBJECTS["status"], cb=on_status)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['status']}")

    async def _subscribe_cancellations(self):
        """Subscribe to cancellation requests."""
        import nats
        import json

        async def on_cancel(msg):
            try:
                data = msg.data.decode()
                payload = json.loads(data)

                work_id = payload.get("work_id")
                result = await self.cancel_work(work_id)

                if msg.reply:
                    response = {"work_id": work_id, "cancelled": result}
                    await self._nc.publish(msg.reply, json.dumps(response).encode())

            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                logger.error(f"Invalid cancellation message format: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "work_id": payload.get("work_id") if 'payload' in locals() else None,
                        "cancelled": False,
                        "error": "Invalid message format",
                        "error_id": "CANCEL_FORMAT_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())
            except Exception as e:
                logger.error(f"Error processing cancellation: {e}", exc_info=True)
                if msg.reply:
                    error_response = {
                        "work_id": payload.get("work_id") if 'payload' in locals() else None,
                        "cancelled": False,
                        "error": "Cancellation failed",
                        "error_id": "CANCEL_INTERNAL_ERROR",
                    }
                    await self._nc.publish(msg.reply, json.dumps(error_response).encode())

        sub = await self._nc.subscribe(SUBJECTS["cancel"], cb=on_cancel)
        self._subscriptions.append(sub)
        logger.info(f"Subscribed to {SUBJECTS['cancel']}")

    async def _handle_request(self, request: WorkRequest, reply_subject: Optional[str] = None):
        """Handle incoming work request.

        Args:
            request: Work request
            reply_subject: Reply subject for response
        """
        import json

        work_id = str(uuid.uuid4())
        self._stats.total_requests += 1
        self._stats.pending += 1

        logger.info(f"Received work request: {work_id} ({request.workload_type})")

        # Create work item
        work_item = WorkItem(
            request=request,
            timeout_seconds=request.timeout_seconds,
            max_retries=self.max_retries,
        )
        self._work_items[work_id] = work_item

        # Try to assign
        start_time = datetime.now()

        try:
            assignment = await self._assign_work(request, work_id)

            if assignment is None:
                # No suitable node found
                work_item.status = "failed"
                work_item.error_message = "No suitable nodes available"
                self._stats.failed += 1
                self._stats.pending -= 1

                response = {
                    "work_id": work_id,
                    "status": "failed",
                    "error": "No suitable nodes available",
                }
            else:
                # Successfully assigned
                work_item.status = "assigned"
                work_item.assigned_node = assignment.node_id
                work_item.assignment_time = datetime.now()

                self._stats.assigned += 1
                self._stats.pending -= 1
                self._stats.running += 1

                # Update stats
                assignment_time_ms = (work_item.assignment_time - start_time).total_seconds() * 1000
                self._stats.avg_assignment_time_ms = (
                    (self._stats.avg_assignment_time_ms * (self._stats.assigned - 1) + assignment_time_ms)
                    / self._stats.assigned
                )

                response = {
                    "work_id": work_id,
                    "status": "assigned",
                    "node_id": assignment.node_id,
                    "connection_info": assignment.connection_info,
                    "assigned_at": work_item.assignment_time.isoformat(),
                }

                # Publish assignment notification
                await self._publish_assignment(work_id, assignment)

        except Exception as e:
            logger.error(f"Error assigning work: {e}")
            work_item.status = "failed"
            work_item.error_message = str(e)
            self._stats.failed += 1
            self._stats.pending -= 1

            response = {
                "work_id": work_id,
                "status": "failed",
                "error": str(e),
            }

        # Send response
        if reply_subject:
            await self._nc.publish(reply_subject, json.dumps(response).encode())

    async def _assign_work(self, request: WorkRequest, work_id: str) -> Optional[WorkAssignment]:
        """Assign work to a suitable node.

        Args:
            request: Work request
            work_id: Unique work identifier

        Returns:
            WorkAssignment if node found, None otherwise
        """
        import aiohttp

        # Build query parameters
        params = {
            "online_only": "true",
            "requires_gpu": "true" if request.required_gpu_slots > 0 else "false",
        }

        if request.min_tier:
            params["tier"] = request.min_tier.value

        if request.required_cpu_slots > 0:
            params["min_cpu"] = str(request.required_cpu_slots)

        if request.required_ram_mb > 0:
            params["min_ram_mb"] = str(request.required_ram_mb)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.registry_url}/query",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=self.assignment_timeout),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Node registry query failed: {resp.status}")
                        return None

                    data = await resp.json()
                    nodes = data.get("nodes", [])

                    if not nodes:
                        return None

                    # Filter out blacklisted nodes
                    available_nodes = [
                        n for n in nodes
                        if n.get("node_id") not in self._node_blacklist
                    ]

                    if not available_nodes:
                        # Clear blacklist if no nodes available
                        self._node_blacklist.clear()
                        available_nodes = nodes

                    # Select best node (lowest utilization score)
                    available_nodes.sort(
                        key=lambda n: n.get("utilization_score", 1.0)
                    )

                    best_node = available_nodes[0]
                    node_id = best_node["node_id"]
                    ipv4 = best_node.get("ipv4", "localhost")

                    # Build connection info
                    connection_info = {
                        "host": ipv4,
                        "port": 8080,  # Default work port
                        "api_endpoint": f"http://{ipv4}:8080/work/{work_id}",
                    }

                    return WorkAssignment(
                        request_id=work_id,
                        node_id=node_id,
                        assigned_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(seconds=request.timeout_seconds),
                        connection_info=connection_info,
                    )

        except asyncio.TimeoutError:
            logger.warning("Node registry query timed out")
            return None
        except Exception as e:
            logger.error(f"Error querying node registry: {e}")
            return None

    async def _publish_assignment(self, work_id: str, assignment: WorkAssignment):
        """Publish work assignment notification.

        Args:
            work_id: Work identifier
            assignment: Work assignment
        """
        import json

        notification = {
            "work_id": work_id,
            "request_id": assignment.request_id,
            "node_id": assignment.node_id,
            "assigned_at": assignment.assigned_at.isoformat(),
            "expires_at": assignment.expires_at.isoformat(),
            "connection_info": assignment.connection_info,
        }

        try:
            await self._nc.publish(
                SUBJECTS["assigned"],
                json.dumps(notification).encode(),
            )
        except Exception as e:
            logger.error(f"Error publishing assignment: {e}")

    async def _handle_completion(self, work_id: str, node_id: str, payload: Dict[str, Any]):
        """Handle work completion notification.

        Args:
            work_id: Work identifier
            node_id: Node that completed the work
            payload: Completion payload
        """
        work_item = self._work_items.get(work_id)
        if work_item is None:
            logger.warning(f"Unknown work ID in completion: {work_id}")
            return

        work_item.status = "completed"
        work_item.updated_at = datetime.now()

        self._stats.completed += 1
        self._stats.running -= 1

        # Remove from blacklist if it was there
        self._node_blacklist.discard(node_id)

        # Call completion callback if registered
        if work_item.on_complete:
            try:
                await work_item.on_complete(work_item, payload)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")

        logger.info(f"Work {work_id} completed by {node_id}")

    async def _handle_failure(self, work_id: str, node_id: str, error: str):
        """Handle work failure notification.

        Args:
            work_id: Work identifier
            node_id: Node that failed the work
            error: Error message
        """
        work_item = self._work_items.get(work_id)
        if work_item is None:
            logger.warning(f"Unknown work ID in failure: {work_id}")
            return

        # Add node to blacklist temporarily
        self._node_blacklist.add(node_id)

        # Check if we should retry
        if work_item.retry_count < work_item.max_retries:
            work_item.retry_count += 1
            work_item.status = "pending"
            work_item.assigned_node = None
            work_item.assignment_time = None

            self._stats.retried += 1
            self._stats.running -= 1
            self._stats.pending += 1

            logger.info(f"Retrying work {work_id} (attempt {work_item.retry_count})")

            # Retry assignment
            asyncio.create_task(self._retry_assignment(work_id))
        else:
            work_item.status = "failed"
            work_item.error_message = error
            work_item.updated_at = datetime.now()

            self._stats.failed += 1
            self._stats.running -= 1

            # Call failure callback if registered
            if work_item.on_failed:
                try:
                    await work_item.on_failed(work_item, error)
                except Exception as e:
                    logger.error(f"Error in failure callback: {e}")

            logger.error(f"Work {work_id} failed after {work_item.retry_count} retries: {error}")

    async def _retry_assignment(self, work_id: str):
        """Retry work assignment.

        Args:
            work_id: Work identifier
        """
        await asyncio.sleep(1)  # Brief delay before retry

        work_item = self._work_items.get(work_id)
        if work_item is None or work_item.status != "pending":
            return

        assignment = await self._assign_work(work_item.request, work_id)

        if assignment:
            work_item.status = "assigned"
            work_item.assigned_node = assignment.node_id
            work_item.assignment_time = datetime.now()

            self._stats.assigned += 1
            self._stats.pending -= 1
            self._stats.running += 1

            await self._publish_assignment(work_id, assignment)

    async def _stale_check_loop(self):
        """Periodic check for stale work items."""
        while self._running:
            try:
                await asyncio.sleep(self.stale_check_interval)
                await self._check_stale_work()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stale check loop: {e}")

    async def _check_stale_work(self):
        """Check for stale work items and handle them."""
        now = datetime.now()
        stale_items = []

        for work_id, work_item in self._work_items.items():
            if work_item.is_expired:
                # Work timed out
                work_item.status = "failed"
                work_item.error_message = "Work timed out"
                self._stats.timed_out += 1
                self._stats.running -= 1
                stale_items.append(work_id)

                # Blacklist the assigned node
                if work_item.assigned_node:
                    self._node_blacklist.add(work_item.assigned_node)

                # Call timeout callback
                if work_item.on_timeout:
                    try:
                        await work_item.on_timeout(work_item)
                    except Exception as e:
                        logger.error(f"Error in timeout callback: {e}")

            elif work_item.is_stale:
                # Assigned but node not responding, retry
                await self._handle_failure(
                    work_id,
                    work_item.assigned_node or "unknown",
                    "Node not responding",
                )

        # Clean up completed items
        to_remove = [
            work_id for work_id, item in self._work_items.items()
            if item.status in ("completed", "failed", "cancelled")
            and (now - item.updated_at).total_seconds() > 3600  # Keep for 1 hour
        ]

        for work_id in to_remove:
            del self._work_items[work_id]

        if stale_items:
            logger.info(f"Processed {len(stale_items)} stale work items")

    async def get_work_status(self, work_id: str) -> Dict[str, Any]:
        """Get status of a work item.

        Args:
            work_id: Work identifier

        Returns:
            Status dictionary
        """
        work_item = self._work_items.get(work_id)

        if work_item is None:
            return {
                "work_id": work_id,
                "status": "unknown",
                "error": "Work ID not found",
            }

        return {
            "work_id": work_id,
            "status": work_item.status,
            "workload_type": work_item.request.workload_type,
            "model_name": work_item.request.model_name,
            "assigned_node": work_item.assigned_node,
            "created_at": work_item.created_at.isoformat(),
            "updated_at": work_item.updated_at.isoformat(),
            "retry_count": work_item.retry_count,
            "error_message": work_item.error_message,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get marshaling service statistics.

        Returns:
            Statistics dictionary
        """
        return self._stats.to_dict()

    async def cancel_work(self, work_id: str) -> bool:
        """Cancel a work item.

        Args:
            work_id: Work identifier

        Returns:
            True if cancelled, False if not found or already complete
        """
        work_item = self._work_items.get(work_id)

        if work_item is None:
            return False

        if work_item.status in ("completed", "failed", "cancelled"):
            return False

        work_item.status = "cancelled"
        work_item.updated_at = datetime.now()

        self._stats.cancelled += 1
        self._stats.running -= 1

        logger.info(f"Work {work_id} cancelled")

        return True


async def run_marshaling(
    nats_url: str = "nats://localhost:4222",
    registry_url: str = "http://localhost:8082",
    assignment_timeout_seconds: int = 30,
    max_retries: int = 3,
):
    """Run the work marshaling service.

    Args:
        nats_url: NATS server URL
        registry_url: Node registry HTTP API URL
        assignment_timeout_seconds: Timeout for finding a node
        max_retries: Maximum retry attempts
    """
    marshaling = WorkMarshaling(
        nats_url=nats_url,
        registry_url=registry_url,
        assignment_timeout_seconds=assignment_timeout_seconds,
        max_retries=max_retries,
    )

    # Handle shutdown
    async def shutdown():
        logger.info("Shutting down marshaling service...")
        await marshaling.stop()

    import signal

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

    # Start service
    await marshaling.start()

    # Keep running
    try:
        while marshaling._running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await marshaling.stop()


if __name__ == "__main__":
    import sys
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
    registry_url = os.environ.get("NODE_REGISTRY_URL", "http://localhost:8082")

    try:
        asyncio.run(run_marshaling(nats_url, registry_url))
    except KeyboardInterrupt:
        logger.info("Marshaling service stopped by user")
