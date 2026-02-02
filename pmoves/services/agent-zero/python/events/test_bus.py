#!/usr/bin/env python3
"""
Test Script for Event Bus Functionality

Tests event bus publishing, subscribing, and metrics.
Run this to verify NATS connectivity and event coordination.

Usage:
    # Start NATS first
    docker compose up -d nats

    # Run tests
    python pmoves/services/agent-zero/python/events/test_bus.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from events.bus import EventBus, Event, get_event_bus
from events.subjects import (
    AGENT_STARTED,
    TASK_CREATED,
    TASK_COMPLETED,
    ALL_AGENT_EVENTS,
    ALL_PMOVES_EVENTS,
)
from events.schema import SchemaValidator, AGENT_STARTED_SCHEMA

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("pmoves.agent_zero.events.test")


class EventBusTester:
    """Test suite for event bus functionality."""

    def __init__(self):
        self.bus: EventBus = None
        self.received_events = []
        self.test_passed = 0
        self.test_failed = 0

    async def setup(self):
        """Initialize event bus for testing."""
        logger.info("Setting up event bus...")
        self.bus = EventBus(nats_url="nats://localhost:4222")
        await self.bus.connect()

        # Register schema for AGENT_STARTED events
        self.bus.validators["AGENT_STARTED"] = SchemaValidator(AGENT_STARTED_SCHEMA)
        logger.info("Event bus connected and schemas registered")

    async def teardown(self):
        """Cleanup after tests."""
        if self.bus:
            await self.bus.close()
            logger.info("Event bus closed")

    async def test_basic_publish_subscribe(self):
        """Test basic publish and subscribe functionality."""
        logger.info("\n=== Test 1: Basic Publish/Subscribe ===")

        try:
            # Subscribe to test subject
            received = []

            async def handler(event):
                logger.info(f"Received event: {event.type}")
                received.append(event)

            await self.bus.subscribe("pmoves.test.>", handler)

            # Publish test event
            await self.bus.publish(
                subject="pmoves.test.basic.v1",
                event_type="TEST_EVENT",
                data={"message": "Hello from event bus"},
                source="test-suite"
            )

            # Wait for delivery
            await asyncio.sleep(0.5)

            if len(received) > 0:
                logger.info("✓ Basic publish/subscribe works")
                self.test_passed += 1
            else:
                logger.error("✗ No events received")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def test_agent_lifecycle_events(self):
        """Test agent lifecycle event publishing with schema validation."""
        logger.info("\n=== Test 2: Agent Lifecycle Events ===")

        try:
            received = []

            async def handler(event):
                logger.info(f"Agent event: {event.type} - {event.data.get('agent_id')}")
                received.append(event)

            await self.bus.subscribe(ALL_AGENT_EVENTS, handler)

            # Publish AGENT_STARTED event (with schema validation)
            await self.bus.publish(
                subject=AGENT_STARTED,
                event_type="AGENT_STARTED",
                data={
                    "agent_id": "agent-zero",
                    "agent_type": "orchestrator",
                    "capabilities": ["code_generation", "mcp_tools"],
                    "version": "1.0.0"
                },
                source="agent-zero"
            )

            await asyncio.sleep(0.5)

            if len(received) > 0:
                logger.info("✓ Agent lifecycle events work")
                self.test_passed += 1
            else:
                logger.error("✗ No agent events received")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def test_task_workflow_events(self):
        """Test task workflow event sequence."""
        logger.info("\n=== Test 3: Task Workflow Events ===")

        try:
            received = []

            async def handler(event):
                logger.info(f"Task event: {event.type}")
                received.append(event)

            await self.bus.subscribe("pmoves.work.>", handler)

            # Simulate task lifecycle
            task_id = "test-task-123"

            # Task created
            await self.bus.publish(
                subject=TASK_CREATED,
                event_type="TASK_CREATED",
                data={
                    "task_id": task_id,
                    "task_type": "code_generation",
                    "instruction": "Create hello world function",
                    "priority": 1
                },
                source="agent-zero"
            )

            await asyncio.sleep(0.2)

            # Task completed
            await self.bus.publish(
                subject=TASK_COMPLETED,
                event_type="TASK_COMPLETED",
                data={
                    "task_id": task_id,
                    "result": {"code": "print('hello world')"},
                    "duration_ms": 150
                },
                source="agent-zero"
            )

            await asyncio.sleep(0.5)

            if len(received) >= 2:
                logger.info(f"✓ Task workflow events work ({len(received)} events)")
                self.test_passed += 1
            else:
                logger.error(f"✗ Expected 2 events, got {len(received)}")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def test_wildcard_subscriptions(self):
        """Test wildcard subscription patterns."""
        logger.info("\n=== Test 4: Wildcard Subscriptions ===")

        try:
            pmoves_count = 0
            agent_count = 0

            async def count_all(event):
                nonlocal pmoves_count
                pmoves_count += 1

            async def count_agent(event):
                nonlocal agent_count
                agent_count += 1

            # Subscribe to all PMOVES events
            await self.bus.subscribe(ALL_PMOVES_EVENTS, count_all)

            # Subscribe to agent events only
            await self.bus.subscribe(ALL_AGENT_EVENTS, count_agent)

            # Publish various events
            await self.bus.publish(
                subject="pmoves.agent.started.v1",
                event_type="AGENT_STARTED",
                data={"agent_id": "agent-1"},
                source="test"
            )

            await self.bus.publish(
                subject="pmoves.work.task.created.v1",
                event_type="TASK_CREATED",
                data={"task_id": "task-1"},
                source="test"
            )

            await asyncio.sleep(0.5)

            # ALL_PMOVES should catch both, ALL_AGENT only one
            if pmoves_count >= 2 and agent_count >= 1:
                logger.info(f"✓ Wildcard subscriptions work (all: {pmoves_count}, agent: {agent_count})")
                self.test_passed += 1
            else:
                logger.error(f"✗ Wildcard mismatch (all: {pmoves_count}, agent: {agent_count})")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def test_metrics_tracking(self):
        """Test event metrics collection."""
        logger.info("\n=== Test 5: Metrics Tracking ===")

        try:
            # Reset metrics
            self.bus.reset_metrics()

            # Publish some events
            for i in range(3):
                await self.bus.publish(
                    subject=f"pmoves.test.metric.v1",
                    event_type="TEST_METRIC",
                    data={"index": i},
                    source="test"
                )

            await asyncio.sleep(0.5)

            metrics = self.bus.get_metrics()
            logger.info(f"Metrics: {metrics}")

            if metrics["events_published"] >= 3:
                logger.info("✓ Metrics tracking works")
                self.test_passed += 1
            else:
                logger.error(f"✗ Expected at least 3 published, got {metrics['events_published']}")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def test_schema_validation(self):
        """Test JSON schema validation."""
        logger.info("\n=== Test 6: Schema Validation ===")

        try:
            # Valid event
            await self.bus.publish(
                subject=AGENT_STARTED,
                event_type="AGENT_STARTED",
                data={
                    "agent_id": "test-agent",
                    "capabilities": ["test"]
                },
                source="test"
            )

            logger.info("✓ Valid event passed schema validation")
            self.test_passed += 1

            # Invalid event (missing required field)
            try:
                await self.bus.publish(
                    subject=AGENT_STARTED,
                    event_type="AGENT_STARTED",
                    data={
                        # Missing agent_id
                        "capabilities": ["test"]
                    },
                    source="test"
                )
                logger.error("✗ Invalid event should have failed validation")
                self.test_failed += 1

            except ValueError as e:
                logger.info(f"✓ Invalid event rejected: {e}")
                self.test_passed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1

    async def run_all_tests(self):
        """Run all test suites."""
        logger.info("=" * 60)
        logger.info("PMOVES.AI Event Bus Test Suite")
        logger.info("=" * 60)

        await self.setup()

        await self.test_basic_publish_subscribe()
        await self.test_agent_lifecycle_events()
        await self.test_task_workflow_events()
        await self.test_wildcard_subscriptions()
        await self.test_metrics_tracking()
        await self.test_schema_validation()

        await self.teardown()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Test Summary")
        logger.info("=" * 60)
        logger.info(f"Passed: {self.test_passed}")
        logger.info(f"Failed: {self.test_failed}")
        logger.info("=" * 60)

        return self.test_failed == 0


async def main():
    """Main test entry point."""
    tester = EventBusTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
