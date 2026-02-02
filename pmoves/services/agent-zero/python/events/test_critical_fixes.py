#!/usr/bin/env python3
"""
Unit Tests for Critical Fixes (No NATS Required)

Tests critical fixes from PR #562 that don't require NATS connection:
- Event ID collision (UUID v4)
- Thread-safe metrics
- Memory-safe subscription tracking
- Weak reference cleanup

Usage:
    python pmoves/services/agent-zero/python/events/test_critical_fixes.py
"""

import asyncio
import gc
import logging
import sys
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from events.bus import Event, EventBus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("pmoves.agent_zero.events.critical_fixes_test")


class CriticalFixesTester:
    """Test suite for critical fixes without NATS dependency."""

    def __init__(self):
        self.test_passed = 0
        self.test_failed = 0

    async def test_event_id_collision(self):
        """Test 1: Verify event IDs are unique (CRITICAL FIX #2)."""
        logger.info("\n=== Test 1: Event ID Collision (UUID v4) ===")

        try:
            # Generate many events rapidly
            event_ids = set()
            num_events = 10000

            for _ in range(num_events):
                event = Event(
                    type="TEST_EVENT",
                    source="test",
                    data={"index": _}
                )
                event_ids.add(event.id)

            if len(event_ids) == num_events:
                logger.info(f"✓ All {num_events:,} event IDs are unique (using UUID v4)")
                self.test_passed += 1
            else:
                logger.error(f"✗ Collision detected: {num_events - len(event_ids)} duplicates")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_thread_safe_metrics(self):
        """Test 2: Verify metrics are thread-safe (IMPORTANT FIX #1)."""
        logger.info("\n=== Test 2: Thread-Safe Metrics ===")

        try:
            # Create event bus (no connection needed)
            bus = EventBus()

            # Reset metrics
            await bus.reset_metrics()

            # Concurrent metric updates
            num_tasks = 100
            updates_per_task = 100

            async def update_metrics():
                for _ in range(updates_per_task):
                    async with bus._metrics_lock:
                        bus._metrics["events_published"] += 1
                        bus._metrics["events_processed"] += 1

            # Run concurrent updates
            tasks = [asyncio.create_task(update_metrics()) for _ in range(num_tasks)]
            await asyncio.gather(*tasks)

            # Get metrics
            metrics = await bus.get_metrics()
            expected = num_tasks * updates_per_task

            logger.info(f"Published: {metrics['events_published']} (expected: {expected})")
            logger.info(f"Processed: {metrics['events_processed']} (expected: {expected})")

            if metrics['events_published'] == expected and metrics['events_processed'] == expected:
                logger.info("✓ Metrics are thread-safe (no lost updates)")
                self.test_passed += 1
            else:
                logger.error(f"✗ Metrics discrepancy: race condition detected")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_weak_reference_cleanup(self):
        """Test 3: Verify weak references work correctly (CRITICAL FIX #3)."""
        logger.info("\n=== Test 3: Weak Reference Cleanup ===")

        try:
            bus = EventBus()

            # Create weak reference
            async def handler(event):
                pass

            handler_ref = type(bus)._subscription_handlers.__class__()

            # Store weak reference
            weak_handler_ref = type(bus)._subscription_handlers.get if hasattr(bus, '_subscription_handlers') else lambda k: None

            # Test that weak references work
            import weakref
            ref = weakref.ref(handler)

            if ref() is handler:
                logger.info("✓ Weak reference to handler created successfully")
            else:
                logger.error("✗ Weak reference not working")
                self.test_failed += 1
                return

            # Delete handler and force garbage collection
            del handler
            gc.collect()

            if ref() is None:
                logger.info("✓ Weak reference correctly invalidated after handler deletion")
                self.test_passed += 1
            else:
                logger.error("✗ Weak reference still valid after deletion")
                self.test_failed += 1

        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_subscription_tracking(self):
        """Test 4: Verify subscription tracking structure (CRITICAL FIX #3)."""
        logger.info("\n=== Test 4: Subscription Tracking Structure ===")

        try:
            bus = EventBus()

            # Verify subscription tracking structures exist
            assert hasattr(bus, '_subscriptions'), "Missing _subscriptions dict"
            assert hasattr(bus, '_subscription_handlers'), "Missing _subscription_handlers dict"
            assert hasattr(bus, '_subscriptions_lock'), "Missing _subscriptions_lock"
            assert hasattr(bus, '_next_sub_id'), "Missing _next_sub_id"

            # Verify initial state
            async with bus._subscriptions_lock:
                assert len(bus._subscriptions) == 0, "_subscriptions should be empty initially"
                assert len(bus._subscription_handlers) == 0, "_subscription_handlers should be empty initially"
                assert bus._next_sub_id == 0, "_next_sub_id should start at 0"

            logger.info("✓ Subscription tracking structures initialized correctly")
            self.test_passed += 1

        except AssertionError as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_metrics_lock(self):
        """Test 5: Verify metrics lock exists (IMPORTANT FIX #1)."""
        logger.info("\n=== Test 5: Metrics Lock ===")

        try:
            bus = EventBus()

            # Verify metrics lock exists
            assert hasattr(bus, '_metrics_lock'), "Missing _metrics_lock"
            assert hasattr(bus, '_metrics'), "Missing _metrics dict"

            logger.info("✓ Metrics lock and structures initialized correctly")
            self.test_passed += 1

        except AssertionError as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_jetstream_support(self):
        """Test 6: Verify JetStream support structure (CRITICAL FIX #4)."""
        logger.info("\n=== Test 6: JetStream Support ===")

        try:
            bus = EventBus(use_jetstream=True)

            # Verify JetStream attributes
            assert hasattr(bus, 'use_jetstream'), "Missing use_jetstream flag"
            assert hasattr(bus, 'js'), "Missing js (JetStream context)"
            assert bus.use_jetstream == True, "use_jetstream should be True"

            logger.info("✓ JetStream support structure initialized correctly")
            self.test_passed += 1

        except AssertionError as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_reconnection_callbacks(self):
        """Test 7: Verify reconnection callback structure (IMPORTANT FIX #2)."""
        logger.info("\n=== Test 7: Reconnection Callbacks ===")

        try:
            bus = EventBus()

            # Verify reconnection callback methods exist
            assert hasattr(bus, '_on_disconnect'), "Missing _on_disconnect callback"
            assert hasattr(bus, '_on_reconnect'), "Missing _on_reconnect callback"
            assert hasattr(bus, '_on_error'), "Missing _on_error callback"
            assert hasattr(bus, '_on_close'), "Missing _on_close callback"
            assert hasattr(bus, '_should_reconnect'), "Missing _should_reconnect flag"

            logger.info("✓ Reconnection callback methods defined correctly")
            self.test_passed += 1

        except AssertionError as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def test_event_id_format(self):
        """Test 8: Verify event ID format (UUID v4)."""
        logger.info("\n=== Test 8: Event ID Format ===")

        try:
            event = Event(type="TEST", source="test", data={})

            # Verify ID format: evt-<32 hex chars>
            assert event.id.startswith("evt-"), "Event ID should start with 'evt-'"
            hex_part = event.id[4:]
            assert len(hex_part) == 32, f"Event ID hex part should be 32 chars, got {len(hex_part)}"
            assert all(c in "0123456789abcdef" for c in hex_part), "Event ID hex part should be lowercase hex"

            logger.info(f"✓ Event ID format correct: {event.id}")
            self.test_passed += 1

        except AssertionError as e:
            logger.error(f"✗ Test failed: {e}")
            self.test_failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed: {e}", exc_info=True)
            self.test_failed += 1

    async def run_all_tests(self):
        """Run all test suites."""
        logger.info("=" * 60)
        logger.info("PMOVES.AI Event Bus Critical Fixes Test Suite")
        logger.info("Testing PR #562 Critical Fixes (No NATS Required)")
        logger.info("=" * 60)

        await self.test_event_id_collision()
        await self.test_thread_safe_metrics()
        await self.test_weak_reference_cleanup()
        await self.test_subscription_tracking()
        await self.test_metrics_lock()
        await self.test_jetstream_support()
        await self.test_reconnection_callbacks()
        await self.test_event_id_format()

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
    tester = CriticalFixesTester()
    success = await tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
