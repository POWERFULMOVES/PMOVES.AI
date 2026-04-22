#!/usr/bin/env python3
"""
Prometheus Metrics MCP Server - Observability Layer

MCP server for Prometheus metrics analysis and anomaly detection.
Provides tools for agents to query Prometheus metrics and detect issues.

Usage:
    python tools/observability/mcp_prometheus.py
    (Runs as MCP server via stdio)

Environment:
    PROMETHEUS_URL - Prometheus server URL (default: http://localhost:9090)
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
server = Server("prometheus-metrics")

# Prometheus configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")


class PrometheusClient:
    """Prometheus client for metrics queries."""

    def __init__(self, base_url: str = PROMETHEUS_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def query(self, query: str, time: str | None = None) -> dict[str, Any]:
        """Execute PromQL query.

        Args:
            query: PromQL expression
            time: Optional timestamp (RFC3339 or Unix timestamp)

        Returns:
            Query result as dict
        """
        params = {"query": query}
        if time:
            params["time"] = time

        response = self.session.get(
            f"{self.base_url}/api/v1/query",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "15s"
    ) -> dict[str, Any]:
        """Execute PromQL range query.

        Args:
            query: PromQL expression
            start: Start time
            end: End time
            step: Query resolution step

        Returns:
            Range query result as dict
        """
        params = {
            "query": query,
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step
        }

        response = self.session.get(
            f"{self.base_url}/api/v1/query_range",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="query_metrics",
            description="Execute a PromQL query on Prometheus",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "PromQL expression to query"
                    },
                    "time": {
                        "type": "string",
                        "description": "Optional timestamp (RFC3339 or Unix timestamp)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="detect_anomalies",
            description="Detect metric anomalies for a service (error rate, latency, CPU)",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name to analyze"
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
            name="trend_analysis",
            description="Analyze metric trends over time",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "Metric name or PromQL expression"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Analysis period in hours (default: 24)",
                        "default": 24
                    }
                },
                "required": ["metric"]
            }
        ),
        Tool(
            name="list_service_metrics",
            description="List available metrics for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name pattern"
                    }
                },
                "required": ["service"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls."""

    client = PrometheusClient()

    try:
        if name == "query_metrics":
            query = arguments["query"]
            time = arguments.get("time")

            result = client.query(query, time)

            if result.get("status") == "success":
                data = result.get("data", {})
                result_type = data.get("resultType")
                results = data.get("result", [])

                output = [f"Query: {query}"]
                output.append(f"Result Type: {result_type}")
                output.append(f"Results: {len(results)} series found")

                for series in results[:10]:  # Limit to first 10
                    metric = series.get("metric", {})
                    value = series.get("value", [None, None])[1]

                    metric_labels = ", ".join(f"{k}={v}" for k, v in metric.items())
                    output.append(f"  {metric_labels}: {value}")

                if len(results) > 10:
                    output.append(f"  ... and {len(results) - 10} more")

                return [TextContent(type="text", text="\n".join(output))]
            else:
                error = result.get("error", "Unknown error")
                return [TextContent(type="text", text=f"Error: {error}")]

        elif name == "detect_anomalies":
            service = arguments["service"]
            hours = arguments.get("hours", 1)

            end = datetime.now()
            start = end - timedelta(hours=hours)

            anomalies = []

            # Check for high error rate
            error_rate_query = f'rate(errors_total{{service="{service}"}}[5m]) > 0.05'
            try:
                result = client.query_range(error_rate_query, start, end)
                if result["data"]["result"]:
                    anomalies.append({
                        "type": "high_error_rate",
                        "severity": "critical",
                        "description": f"Error rate exceeding 5% threshold"
                    })
            except Exception as e:
                pass  # Check failed, skip

            # Check for high latency
            latency_query = f'rate(latency_seconds_bucket{{service="{service}"}}[5m])'
            try:
                result = client.query_range(latency_query, start, end)
                if result["data"]["result"]:
                    anomalies.append({
                        "type": "high_latency",
                        "severity": "warning",
                        "description": f"Latency percentile p95 above threshold"
                    })
            except Exception as e:
                pass  # Check failed, skip

            # Check for resource saturation
            cpu_query = f'rate(process_cpu_seconds_total{{service="{service}"}}[5m]) > 0.8'
            try:
                result = client.query_range(cpu_query, start, end)
                if result["data"]["result"]:
                    anomalies.append({
                        "type": "cpu_saturation",
                        "severity": "warning",
                        "description": f"CPU usage above 80%"
                    })
            except Exception as e:
                pass  # Check failed, skip

            output = [f"Anomaly Detection for {service} (last {hours}h):"]
            if anomalies:
                for anomaly in anomalies:
                    output.append(f"  - {anomaly['type'].upper()} ({anomaly['severity']}): {anomaly['description']}")
            else:
                output.append("  No anomalies detected")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "trend_analysis":
            metric = arguments["metric"]
            hours = arguments.get("hours", 24)

            end = datetime.now()
            start = end - timedelta(hours=hours)

            result = client.query_range(metric, start, end, step="1h")

            if not result["data"]["result"]:
                return [TextContent(type="text", text="No data returned for metric")]

            # Extract values for trend analysis
            values = []
            for series in result["data"]["result"]:
                for value in series.get("values", []):
                    timestamp, value = value
                    try:
                        values.append(float(value))
                    except (ValueError, TypeError):
                        continue

            if not values:
                return [TextContent(type="text", text="No valid values in result")]

            # Calculate trend statistics
            avg_value = sum(values) / len(values)
            min_value = min(values)
            max_value = max(values)

            # Simple trend detection
            mid = len(values) // 2
            first_half_avg = sum(values[:mid]) / mid if mid > 0 else avg_value
            second_half_avg = sum(values[mid:]) / (len(values) - mid) if len(values) > mid else avg_value

            trend_direction = "stable"
            if second_half_avg > first_half_avg * 1.1:
                trend_direction = "increasing"
            elif second_half_avg < first_half_avg * 0.9:
                trend_direction = "decreasing"

            change_percent = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0

            output = [
                f"Trend Analysis for {metric}",
                f"Period: {hours}h",
                f"Average: {avg_value:.2f}",
                f"Range: [{min_value:.2f}, {max_value:.2f}]",
                f"Trend: {trend_direction} ({change_percent:+.1f}%)"
            ]

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "list_service_metrics":
            service = arguments["service"]

            # Use label values to find matching metrics
            response = client.session.get(
                f"{client.base_url}/api/v1/label/__name__/values",
                timeout=30
            )
            response.raise_for_status()

            all_metrics = response.json().get("data", [])

            # Filter for service-specific metrics
            service_pattern = service.lower().replace("-", "_")
            matching_metrics = [
                m for m in all_metrics
                if service_pattern in m.lower()
            ]

            output = [f"Found {len(matching_metrics)} metrics for {service}:"]

            for metric in matching_metrics[:50]:  # Limit to 50
                output.append(f"  - {metric}")

            if len(matching_metrics) > 50:
                output.append(f"  ... and {len(matching_metrics) - 50} more")

            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Prometheus query failed: {e}")]
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
