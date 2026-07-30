#!/usr/bin/env python3
"""
Jaeger Tracing Specialist - Observability Layer Agent

Analyzes distributed traces from Jaeger to identify performance bottlenecks,
cross-service correlations, and latency issues.

Usage:
    python pmoves/tools/observability/tracing_specialist.py query <service_name>
    python pmoves/tools/observability/tracing_specialist.py trace <trace_id>
    python pmoves/tools/observability/tracing_specialist.py bottleneck <service_name> --hours 1
    python pmoves/tools/observability/tracing_specialist.py compare <trace_id1> <trace_id2>

Environment:
    JAEGER_URL - Jaeger UI URL (default: http://localhost:16686)
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import requests

# Add repo root to path
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class JaegerTracingSpecialist:
    """Specialist agent for Jaeger distributed trace analysis."""

    def __init__(self, jaeger_url: str | None = None):
        """Initialize Jaeger client.

        Args:
            jaeger_url: Jaeger UI URL (default from env or localhost:16686)
        """
        self.jaeger_url = jaeger_url or os.getenv(
            "JAEGER_URL", "http://localhost:16686"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json"
        })

    def query_traces(
        self,
        service: str,
        limit: int = 20,
        lookback_hours: int = 1
    ) -> List[Dict[str, Any]]:
        """Query traces for a service.

        Args:
            service: Service name
            limit: Maximum number of traces
            lookbackHours: Lookback period in hours

        Returns:
            List of trace metadata
        """
        end = datetime.now()
        end - timedelta(hours=lookback_hours)

        params = {
            "service": service,
            "limit": str(limit),
            "lookback": f"{lookback_hours}h"
        }

        response = self.session.get(
            f"{self.jaeger_url}/api/traces",
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get("data", [])

    def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """Get detailed trace information.

        Args:
            trace_id: Trace ID

        Returns:
            Trace details with spans
        """
        response = self.session.get(
            f"{self.jaeger_url}/api/traces/{trace_id}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def analyze_bottlenecks(
        self,
        service: str,
        hours: int = 1,
        threshold_ms: float = 500.0
    ) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks in traces.

        Args:
            service: Service name
            hours: Lookback period
            threshold_ms: Latency threshold in milliseconds

        Returns:
            List of bottleneck spans
        """
        traces = self.query_traces(service, limit=100, lookback_hours=hours)

        bottlenecks = []

        for trace_data in traces:
            trace_id = trace_data.get("traceID", "unknown")
            trace = self.get_trace(trace_id)

            for span in trace.get("data", {}).get("spans", []):
                duration = span.get("duration", 0) / 1000  # Convert microseconds to ms

                if duration > threshold_ms:
                    operation = span.get("operationName", "unknown")
                    process = span.get("processID", "unknown")

                    bottlenecks.append({
                        "trace_id": trace_id,
                        "span_id": span.get("spanID", "unknown"),
                        "service": service,
                        "operation": operation,
                        "process": process,
                        "duration_ms": duration,
                        "threshold_ms": threshold_ms,
                        "excess_ms": duration - threshold_ms
                    })

        # Sort by excess latency descending
        bottlenecks.sort(key=lambda b: b["excess_ms"], reverse=True)

        return bottlenecks

    def compare_traces(self, trace_id1: str, trace_id2: str) -> Dict[str, Any]:
        """Compare two traces to identify performance differences.

        Args:
            trace_id1: First trace ID
            trace_id2: Second trace ID

        Returns:
            Comparison results
        """
        trace1 = self.get_trace(trace_id1)
        trace2 = self.get_trace(trace_id2)

        spans1 = trace1.get("data", {}).get("spans", [])
        spans2 = trace2.get("data", {}).get("spans", [])

        # Calculate total duration
        duration1 = max(s.get("duration", 0) for s in spans1) / 1000
        duration2 = max(s.get("duration", 0) for s in spans2) / 1000

        # Group by operation
        operations1 = {}
        operations2 = {}

        for span in spans1:
            op = span.get("operationName", "unknown")
            duration = span.get("duration", 0) / 1000
            operations1[op] = operations1.get(op, 0) + duration

        for span in spans2:
            op = span.get("operationName", "unknown")
            duration = span.get("duration", 0) / 1000
            operations2[op] = operations2.get(op, 0) + duration

        # Compare operations
        comparison = {
            "trace_id1": trace_id1,
            "trace_id2": trace_id2,
            "total_duration_ms": {
                "trace1": duration1,
                "trace2": duration2,
                "diff_ms": duration2 - duration1,
                "diff_percent": ((duration2 - duration1) / duration1 * 100) if duration1 > 0 else 0
            },
            "operation_comparison": []
        }

        all_ops = set(operations1.keys()) | set(operations2.keys())

        for op in sorted(all_ops):
            duration_op1 = operations1.get(op, 0)
            duration_op2 = operations2.get(op, 0)

            comparison["operation_comparison"].append({
                "operation": op,
                "trace1_ms": duration_op1,
                "trace2_ms": duration_op2,
                "diff_ms": duration_op2 - duration_op1,
                "diff_percent": ((duration_op2 - duration_op1) / duration_op1 * 100) if duration_op1 > 0 else float('inf')
            })

        return comparison

    def find_slow_spans(
        self,
        trace_id: str,
        threshold_percent: float = 10.0
    ) -> List[Dict[str, Any]]:
        """Find spans that contribute most to trace duration.

        Args:
            trace_id: Trace ID
            threshold_percent: Minimum duration percentage to include

        Returns:
            List of slow spans
        """
        trace = self.get_trace(trace_id)
        spans = trace.get("data", {}).get("spans", [])

        if not spans:
            return []

        total_duration = max(s.get("duration", 0) for s in spans)

        slow_spans = []
        for span in spans:
            duration = span.get("duration", 0)
            duration_percent = (duration / total_duration * 100) if total_duration > 0 else 0

            if duration_percent >= threshold_percent:
                slow_spans.append({
                    "span_id": span.get("spanID", "unknown"),
                    "operation": span.get("operationName", "unknown"),
                    "service": span.get("process", {}).get("serviceName", "unknown"),
                    "duration_ms": duration / 1000,
                    "duration_percent": duration_percent
                })

        slow_spans.sort(key=lambda s: s["duration_percent"], reverse=True)

        return slow_spans


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Jaeger Tracing Specialist - Observability Layer Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query traces for service")
    query_parser.add_argument("service", help="Service name")
    query_parser.add_argument("--limit", type=int, default=20, help="Result limit")
    query_parser.add_argument("--hours", type=int, default=1, help="Lookback period")

    # Trace command
    trace_parser = subparsers.add_parser("trace", help="Get trace details")
    trace_parser.add_argument("trace_id", help="Trace ID")

    # Bottleneck command
    bottleneck_parser = subparsers.add_parser("bottleneck", help="Find bottlenecks")
    bottleneck_parser.add_argument("service", help="Service name")
    bottleneck_parser.add_argument("--hours", type=int, default=1, help="Lookback period")
    bottleneck_parser.add_argument("--threshold", type=float, default=500.0, help="Latency threshold (ms)")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two traces")
    compare_parser.add_argument("trace_id1", help="First trace ID")
    compare_parser.add_argument("trace_id2", help="Second trace ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    specialist = JaegerTracingSpecialist()

    try:
        if args.command == "query":
            traces = specialist.query_traces(args.service, args.limit, args.hours)
            print(f"[+] Found {len(traces)} traces for {args.service}:")
            for trace in traces[:10]:
                trace_id = trace.get("traceID", "unknown")[:8]
                print(f"  - Trace {trace_id}...")
            if len(traces) > 10:
                print(f"  ... and {len(traces) - 10} more")

        elif args.command == "trace":
            trace = specialist.get_trace(args.trace_id)
            spans = trace.get("data", {}).get("spans", [])
            total_duration = max(s.get("duration", 0) for s in spans) / 1000 if spans else 0

            print(f"[+] Trace {args.trace_id}:")
            print(f"  Total duration: {total_duration:.2f}ms")
            print(f"  Spans: {len(spans)}")
            print("\n  Top 5 spans by duration:")
            for span in sorted(spans, key=lambda s: s.get("duration", 0), reverse=True)[:5]:
                duration = span.get("duration", 0) / 1000
                operation = span.get("operationName", "unknown")
                print(f"    {duration:.2f}ms - {operation}")

        elif args.command == "bottleneck":
            bottlenecks = specialist.analyze_bottlenecks(
                args.service,
                args.hours,
                args.threshold
            )
            print(f"[+] Found {len(bottlenecks)} bottlenecks for {args.service}:")
            for bottleneck in bottlenecks[:10]:
                print(f"  - {bottleneck['operation']}: {bottleneck['duration_ms']:.2f}ms "
                      f"(threshold: {bottleneck['threshold_ms']:.2f}ms, "
                      f"excess: +{bottleneck['excess_ms']:.2f}ms)")
            if len(bottlenecks) > 10:
                print(f"  ... and {len(bottlenecks) - 10} more")

        elif args.command == "compare":
            comparison = specialist.compare_traces(args.trace_id1, args.trace_id2)
            print("[+] Trace Comparison:")
            print("\n  Total Duration:")
            print(f"    Trace 1: {comparison['total_duration_ms']['trace1']:.2f}ms")
            print(f"    Trace 2: {comparison['total_duration_ms']['trace2']:.2f}ms")
            print(f"    Difference: {comparison['total_duration_ms']['diff_ms']:+.2f}ms "
                  f"({comparison['total_duration_ms']['diff_percent']:+.1f}%)")

            print("\n  Operation Breakdown:")
            for op_comp in comparison['operation_comparison']:
                print(f"    {op_comp['operation']}:")
                print(f"      Trace 1: {op_comp['trace1_ms']:.2f}ms")
                print(f"      Trace 2: {op_comp['trace2_ms']:.2f}ms")
                print(f"      Difference: {op_comp['diff_ms']:+.2f}ms "
                      f"({op_comp['diff_percent']:+.1f}%)")

        return 0

    except requests.RequestException as e:
        print(f"[!] Jaeger API request failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        return 130
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
