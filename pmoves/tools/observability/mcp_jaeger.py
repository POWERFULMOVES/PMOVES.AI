#!/usr/bin/env python3
"""
Jaeger Tracing MCP Server - Observability Layer

MCP server for Jaeger distributed trace analysis.
Provides tools for agents to query traces and identify bottlenecks.

Usage:
    python tools/observability/mcp_jaeger.py
    (Runs as MCP server via stdio)

Environment:
    JAEGER_URL - Jaeger UI URL (default: http://localhost:16686)
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add repo root to path
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Initialize MCP server
server = Server("jaeger-tracing")

# Jaeger configuration
JAEGER_URL = os.getenv("JAEGER_URL", "http://localhost:16686")


class JaegerClient:
    """Jaeger client for trace analysis."""

    def __init__(self, base_url: str = JAEGER_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json"
        })

    def query_traces(
        self,
        service: str,
        limit: int = 20,
        lookback_hours: int = 1
    ) -> list[dict[str, Any]]:
        """Query traces for a service.

        Args:
            service: Service name
            limit: Maximum number of traces
            lookback_hours: Lookback period in hours

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
            f"{self.base_url}/api/traces",
            params=params,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()
        return data.get("data", [])

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        """Get detailed trace information.

        Args:
            trace_id: Trace ID

        Returns:
            Trace details with spans
        """
        response = self.session.get(
            f"{self.base_url}/api/traces/{trace_id}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="query_traces",
            description="Query traces for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of traces (default: 20)",
                        "default": 20
                    },
                    "hours": {
                        "type": "number",
                        "description": "Lookback period in hours (default: 1)",
                        "default": 1
                    }
                },
                "required": ["service"]
            }
        ),
        Tool(
            name="get_trace",
            description="Get detailed trace information",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "Trace ID"
                    }
                },
                "required": ["trace_id"]
            }
        ),
        Tool(
            name="analyze_bottlenecks",
            description="Identify performance bottlenecks in traces",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Lookback period in hours (default: 1)",
                        "default": 1
                    },
                    "threshold_ms": {
                        "type": "number",
                        "description": "Latency threshold in milliseconds (default: 500)",
                        "default": 500
                    }
                },
                "required": ["service"]
            }
        ),
        Tool(
            name="compare_traces",
            description="Compare two traces to identify performance differences",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace_id1": {
                        "type": "string",
                        "description": "First trace ID"
                    },
                    "trace_id2": {
                        "type": "string",
                        "description": "Second trace ID"
                    }
                },
                "required": ["trace_id1", "trace_id2"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls."""

    client = JaegerClient()

    try:
        if name == "query_traces":
            service = arguments["service"]
            limit = arguments.get("limit", 20)
            hours = arguments.get("hours", 1)

            traces = client.query_traces(service, limit, hours)

            output = [f"Found {len(traces)} traces for {service} (last {hours}h):"]

            for trace in traces[:10]:  # Show first 10
                trace_id = trace.get("traceID", "unknown")[:8]
                output.append(f"  - Trace {trace_id}...")

            if len(traces) > 10:
                output.append(f"  ... and {len(traces) - 10} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "get_trace":
            trace_id = arguments["trace_id"]

            trace = client.get_trace(trace_id)
            spans = trace.get("data", [{}])[0].get("spans", [])

            if not spans:
                total_duration = 0
            else:
                total_duration = max(s.get("duration", 0) for s in spans) / 1000  # Convert microseconds to ms

            output = [
                f"Trace {trace_id}:",
                f"Total duration: {total_duration:.2f}ms",
                f"Spans: {len(spans)}",
                "\nTop 5 spans by duration:"
            ]

            # Sort spans by duration descending
            sorted_spans = sorted(spans, key=lambda s: s.get("duration", 0), reverse=True)[:5]

            for span in sorted_spans:
                duration = span.get("duration", 0) / 1000  # Convert microseconds to ms
                operation = span.get("operationName", "unknown")
                output.append(f"  {duration:.2f}ms - {operation}")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "analyze_bottlenecks":
            service = arguments["service"]
            hours = arguments.get("hours", 1)
            threshold_ms = arguments.get("threshold_ms", 500)

            traces = client.query_traces(service, limit=100, lookback_hours=hours)

            bottlenecks = []

            for trace_data in traces:
                trace_id = trace_data.get("traceID", "unknown")
                trace = client.get_trace(trace_id)

                for span in trace.get("data", {}).get("spans", []):
                    duration = span.get("duration", 0) / 1000  # Convert microseconds to ms

                    if duration > threshold_ms:
                        operation = span.get("operationName", "unknown")
                        process = span.get("processID", "unknown")

                        bottlenecks.append({
                            "trace_id": trace_id[:8],
                            "operation": operation,
                            "process": process,
                            "duration_ms": duration,
                            "excess_ms": duration - threshold_ms
                        })

            # Sort by excess latency descending
            bottlenecks.sort(key=lambda b: b["excess_ms"], reverse=True)

            output = [f"Bottlenecks for {service} (threshold: {threshold_ms}ms):"]
            output.append(f"Found {len(bottlenecks)} bottlenecks")

            for bottleneck in bottlenecks[:10]:  # Show first 10
                output.append(
                    f"\n  - {bottleneck['operation']}: {bottleneck['duration_ms']:.2f}ms "
                    f"(threshold: {threshold_ms}ms, excess: +{bottleneck['excess_ms']:.2f}ms)"
                )

            if len(bottlenecks) > 10:
                output.append(f"\n  ... and {len(bottlenecks) - 10} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "compare_traces":
            trace_id1 = arguments["trace_id1"]
            trace_id2 = arguments["trace_id2"]

            trace1 = client.get_trace(trace_id1)
            trace2 = client.get_trace(trace_id2)

            spans1 = trace1.get("data", {}).get("spans", [])
            spans2 = trace2.get("data", {}).get("spans", [])

            # Calculate total duration
            duration1 = max(s.get("duration", 0) for s in spans1) / 1000 if spans1 else 0
            duration2 = max(s.get("duration", 0) for s in spans2) / 1000 if spans2 else 0

            output = [
                "Trace Comparison:",
                "\nTotal Duration:",
                f"  Trace 1: {duration1:.2f}ms",
                f"  Trace 2: {duration2:.2f}ms",
                f"  Difference: {duration2 - duration1:+.2f}ms"
            ]

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
            all_ops = set(operations1.keys()) | set(operations2.keys())

            if all_ops:
                output.append("\nOperation Breakdown:")

                for op in sorted(all_ops):
                    duration_op1 = operations1.get(op, 0)
                    duration_op2 = operations2.get(op, 0)

                    diff = duration_op2 - duration_op1
                    diff_percent = ((diff / duration_op1 * 100) if duration_op1 > 0 else float('inf'))

                    output.append(f"  {op}:")
                    output.append(f"    Trace 1: {duration_op1:.2f}ms")
                    output.append(f"    Trace 2: {duration_op2:.2f}ms")
                    output.append(f"    Difference: {diff:+.2f}ms ({diff_percent:+.1f}%)")

            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Jaeger API request failed: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Main entry point for MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
