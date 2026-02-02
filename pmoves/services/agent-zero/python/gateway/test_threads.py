#!/usr/bin/env python3
"""
Test script for Agent Zero Thread Execution

Tests all 6 thread types:
- Base (B): Single prompt-response
- Parallel (P): Multiple agents simultaneously
- Chained (C): Sequential dependencies
- Fusion (F): Multi-model consensus
- Big (L): Large-scale autonomous planning
- Long (Z): Long-running background tasks

Run: python -m gateway.test_threads
"""

import asyncio
import json
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, "/home/pmoves/pmoves-phase5-threads/pmoves/services/agent-zero/python")

from gateway.threads import (
    ThreadFactory,
    ThreadType,
    ThreadStatus,
    BaseSimpleThread,
    ParallelThread,
    ChainedThread,
    FusionThread,
    BigThread,
    LongThread
)
from gateway.gateway import Gateway


class ThreadTester:
    """Test suite for thread execution."""

    def __init__(self):
        self.test_results = []

    def print_header(self, title: str):
        """Print test section header."""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")

    def print_result(self, test_name: str, result: dict, duration_ms: int):
        """Print test result."""
        status_icon = "✓" if result.get("success") else "✗"
        print(f"\n{status_icon} {test_name}")
        print(f"  Status: {result.get('status', 'unknown')}")
        print(f"  Duration: {duration_ms}ms")
        if result.get("error"):
            print(f"  Error: {result['error']}")
        if result.get("output"):
            output_preview = str(result["output"])[:150]
            print(f"  Output: {output_preview}...")

    async def test_base_thread(self) -> dict:
        """Test Base (Simple) thread execution."""
        self.print_header("Test 1: Base Thread (B)")

        thread = BaseSimpleThread(
            thread_id="test-base-1",
            context={"test": True, "user": "alice"},
            prompt="What is the weather today?",
            agent="weather-agent"
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Base Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "base", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_parallel_thread(self) -> dict:
        """Test Parallel thread execution."""
        self.print_header("Test 2: Parallel Thread (P)")

        thread = ParallelThread(
            thread_id="test-parallel-1",
            context={"test": True},
            tasks=[
                {"name": "task_a", "prompt": "Research topic A"},
                {"name": "task_b", "prompt": "Research topic B"},
                {"name": "task_c", "prompt": "Research topic C"}
            ],
            merge_strategy="concatenate"
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Parallel Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "parallel", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_chained_thread(self) -> dict:
        """Test Chained thread execution."""
        self.print_header("Test 3: Chained Thread (C)")

        thread = ChainedThread(
            thread_id="test-chained-1",
            context={"test": True},
            stages=[
                {"name": "plan", "agent": "architect", "task": "Create plan"},
                {"name": "build", "agent": "builder", "task": "Implement"},
                {"name": "audit", "agent": "auditor", "task": "Review"}
            ]
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Chained Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "chained", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_fusion_thread(self) -> dict:
        """Test Fusion thread execution."""
        self.print_header("Test 4: Fusion Thread (F)")

        thread = FusionThread(
            thread_id="test-fusion-1",
            context={"test": True},
            models=["opus-4-5", "sonnet-4-5", "haiku"],
            consensus_threshold=0.7
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Fusion Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "fusion", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_big_thread(self) -> dict:
        """Test Big thread execution."""
        self.print_header("Test 5: Big Thread (L)")

        plan_steps = [{"name": f"step_{i}", "task": f"Execute step {i}"} for i in range(1, 21)]

        thread = BigThread(
            thread_id="test-big-1",
            context={"test": True},
            plan_steps=plan_steps,
            batch_size=5
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Big Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "big", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_long_thread(self) -> dict:
        """Test Long thread execution (with quick stop)."""
        self.print_header("Test 6: Long Thread (Z)")

        thread = LongThread(
            thread_id="test-long-1",
            context={"test": True},
            task=lambda: None,
            interval_seconds=1,
            max_iterations=3  # Limit iterations for testing
        )

        start = datetime.utcnow()
        result = await thread.execute()
        duration = int((datetime.utcnow() - start).total_seconds() * 1000)

        self.print_result("Long Thread", {
            "success": result.status == ThreadStatus.COMPLETED,
            "status": result.status.value,
            "output": result.result
        }, duration)

        return {"name": "long", "passed": result.status == ThreadStatus.COMPLETED}

    async def test_thread_factory(self) -> dict:
        """Test ThreadFactory."""
        self.print_header("Test 7: ThreadFactory")

        factory_results = []

        # Test creating each thread type
        thread_types = [
            (ThreadType.BASE, {"prompt": "test prompt"}),
            (ThreadType.PARALLEL, {"tasks": []}),
            (ThreadType.CHAINED, {"stages": []}),
            (ThreadType.FUSION, {"models": ["opus-4-5"]}),
            (ThreadType.BIG, {"plan_steps": []}),
            (ThreadType.LONG, {"task": lambda: None, "interval_seconds": 60})
        ]

        for thread_type, kwargs in thread_types:
            try:
                thread = ThreadFactory.create_thread(
                    thread_type=thread_type,
                    thread_id=f"factory-{thread_type.value}",
                    context={},
                    **kwargs
                )
                factory_results.append({
                    "type": thread_type.value,
                    "success": True,
                    "thread_id": thread.thread_id
                })
            except Exception as e:
                factory_results.append({
                    "type": thread_type.value,
                    "success": False,
                    "error": str(e)
                })

        all_passed = all(r["success"] for r in factory_results)

        self.print_result("ThreadFactory", {
            "success": all_passed,
            "status": "completed" if all_passed else "failed",
            "output": factory_results
        }, 0)

        return {"name": "factory", "passed": all_passed}

    async def test_gateway_dispatch(self) -> dict:
        """Test Gateway task dispatch."""
        self.print_header("Test 8: Gateway Task Dispatch")

        gateway = Gateway()
        await gateway.initialize()

        test_tasks = [
            {
                "task_id": "gateway-test-1",
                "intent": "Create a REST API with parallel processing",
                "requirements": {"complexity": "medium", "agents": ["architect", "builder"]}
            },
            {
                "task_id": "gateway-test-2",
                "intent": "Review security implementation",
                "requirements": {"complexity": "low", "agents": ["auditor"]}
            }
        ]

        results = []
        for task in test_tasks:
            result = await gateway.dispatch_task(task)
            results.append({
                "task_id": task["task_id"],
                "status": result.status.value,
                "thread_type": result.thread_type.value
            })

        all_passed = all(r["status"] == "completed" for r in results)

        self.print_result("Gateway Dispatch", {
            "success": all_passed,
            "status": "completed" if all_passed else "failed",
            "output": results
        }, 0)

        return {"name": "gateway", "passed": all_passed}

    async def test_metrics_endpoint(self) -> dict:
        """Test Gateway metrics endpoint."""
        self.print_header("Test 9: Gateway Metrics Endpoint")

        gateway = Gateway()
        await gateway.initialize()

        # Execute a few tasks to generate metrics
        tasks = [
            {"intent": "Test task 1", "requirements": {"complexity": "low"}},
            {"intent": "Test task 2", "requirements": {"complexity": "medium"}},
        ]

        for task in tasks:
            await gateway.dispatch_task(task)

        # Get metrics
        metrics = await gateway.metrics()

        self.print_result("Metrics Endpoint", {
            "success": bool(metrics),
            "status": "completed",
            "output": {
                "total_threads": metrics.get("thread_executions_total"),
                "completed": metrics.get("thread_executions_completed"),
                "failed": metrics.get("thread_executions_failed"),
                "by_type": metrics.get("thread_executions_by_type")
            }
        }, 0)

        return {"name": "metrics", "passed": bool(metrics)}

    async def run_all_tests(self):
        """Run all thread execution tests."""
        print("\n" + "="*70)
        print("  AGENT ZERO THREAD EXECUTION TEST SUITE")
        print("="*70)
        print(f"\nStarted at: {datetime.utcnow().isoformat()}")

        # Run tests
        tests = [
            self.test_base_thread(),
            self.test_parallel_thread(),
            self.test_chained_thread(),
            self.test_fusion_thread(),
            self.test_big_thread(),
            self.test_long_thread(),
            self.test_thread_factory(),
            self.test_gateway_dispatch(),
            self.test_metrics_endpoint()
        ]

        results = await asyncio.gather(*tests)
        self.test_results = results

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        self.print_header("TEST SUMMARY")

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["passed"])

        print(f"\nTotal Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        print("\nDetailed Results:")
        for result in self.test_results:
            status_icon = "✓" if result["passed"] else "✗"
            print(f"  {status_icon} {result['name'].capitalize()} Thread: {'PASS' if result['passed'] else 'FAIL'}")

        print(f"\nCompleted at: {datetime.utcnow().isoformat()}")

        if passed_tests == total_tests:
            print("\n✓ All tests passed!")
            return 0
        else:
            print(f"\n✗ {total_tests - passed_tests} test(s) failed")
            return 1


async def main():
    """Main entry point."""
    tester = ThreadTester()
    exit_code = await tester.run_all_tests()
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
