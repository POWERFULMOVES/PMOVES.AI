#!/usr/bin/env python3
"""
Loki Logs MCP Server - Observability Layer

MCP server for Loki log analysis and pattern detection.
Provides tools for agents to query Loki logs and extract errors.

Usage:
    python tools/observability/mcp_loki.py
    (Runs as MCP server via stdio)

Environment:
    LOKI_URL - Loki server URL (default: http://localhost:3100)
"""

import asyncio
import os
import sys
import re
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
server = Server("loki-logs")

# Loki configuration
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")


class LokiClient:
    """Loki client for log queries."""

    def __init__(self, base_url: str = LOKI_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def query(self, logql: str, limit: int = 100) -> dict[str, Any]:
        """Execute LogQL query.

        Args:
            logql: LogQL expression
            limit: Maximum number of results

        Returns:
            Query result as dict
        """
        params = {
            "query": logql,
            "limit": str(limit)
        }

        response = self.session.get(
            f"{self.base_url}/loki/api/v1/query_range",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def query_range(
        self,
        logql: str,
        start: datetime,
        end: datetime,
        limit: int = 1000
    ) -> dict[str, Any]:
        """Execute LogQL range query.

        Args:
            logql: LogQL expression
            start: Start time
            end: End time
            limit: Maximum number of results

        Returns:
            Range query result as dict
        """
        params = {
            "query": logql,
            "start": start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "limit": str(limit)
        }

        response = self.session.get(
            f"{self.base_url}/loki/api/v1/query_range",
            params=params,
            timeout=60
        )
        response.raise_for_status()
        return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="query_logs",
            description="Execute a LogQL query on Loki",
            inputSchema={
                "type": "object",
                "properties": {
                    "logql": {
                        "type": "string",
                        "description": "LogQL expression to query"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results (default: 100)",
                        "default": 100
                    }
                },
                "required": ["logql"]
            }
        ),
        Tool(
            name="extract_errors",
            description="Extract error logs for a service",
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
                    }
                },
                "required": ["service"]
            }
        ),
        Tool(
            name="correlate_logs",
            description="Correlate logs across services by trace or request ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "Trace ID to correlate"
                    },
                    "request_id": {
                        "type": "string",
                        "description": "Request ID to correlate"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Lookback period in hours (default: 1)",
                        "default": 1
                    }
                }
            }
        ),
        Tool(
            name="detect_patterns",
            description="Detect regex patterns in logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern"
                    },
                    "service": {
                        "type": "string",
                        "description": "Optional service filter"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Lookback period in hours (default: 24)",
                        "default": 24
                    }
                },
                "required": ["pattern"]
            }
        )
    ]


def extract_log_level(line: str) -> str:
    """Extract log level from log line.

    Args:
        line: Log line content

    Returns:
        Log level (info, warn, error, debug)
    """
    line_upper = line.upper()

    if "ERROR" in line_upper or "EXCEPTION" in line_upper or "FATAL" in line_upper:
        return "error"
    elif "WARN" in line_upper:
        return "warn"
    elif "DEBUG" in line_upper:
        return "debug"
    else:
        return "info"


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls."""

    client = LokiClient()

    try:
        if name == "query_logs":
            logql = arguments["logql"]
            limit = arguments.get("limit", 100)

            result = client.query(logql, limit)

            output = [f"Query: {logql}"]
            output.append(f"Results: {len(result.get('data', {}).get('result', []))} streams")

            for stream in result.get("data", {}).get("result", [])[:20]:
                stream_labels = stream.get("stream", {})
                values = stream.get("values", [])

                labels_str = ", ".join(f"{k}={v}" for k, v in stream_labels.items())
                output.append(f"\n  Stream: {labels_str}")
                output.append(f"  Entries: {len(values)}")

                for entry in values[:3]:
                    timestamp_ns, line = entry
                    timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1e9)
                    output.append(f"    [{timestamp}] {line[:100]}")

                if len(values) > 3:
                    output.append(f"    ... and {len(values) - 3} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "extract_errors":
            service = arguments["service"]
            hours = arguments.get("hours", 1)

            end = datetime.now()
            start = end - timedelta(hours=hours)

            # LogQL for error logs
            logql = f'{{service="{service}"}} |~ "(?i)(error|exception|fatal|panic)"'

            result = client.query_range(logql, start, end, limit=500)

            errors = []
            for stream in result.get("data", {}).get("result", []):
                service_name = stream.get("stream", {}).get("service", service)
                host = stream.get("stream", {}).get("host", "unknown")

                for entry in stream.get("values", []):
                    timestamp_ns, line = entry
                    timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1e9)

                    errors.append({
                        "timestamp": timestamp.isoformat(),
                        "service": service_name,
                        "host": host,
                        "line": line,
                        "level": extract_log_level(line)
                    })

            # Sort by timestamp descending
            errors.sort(key=lambda e: e["timestamp"], reverse=True)

            output = [f"Error Logs for {service} (last {hours}h):"]
            output.append(f"Found {len(errors)} errors")

            for error in errors[:20]:  # Show first 20
                level = error.get("level", "info").upper()
                output.append(f"\n  [{level}] {error['timestamp']}")
                output.append(f"  {error['line'][:100]}")

            if len(errors) > 20:
                output.append(f"\n  ... and {len(errors) - 20} more errors")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "correlate_logs":
            trace_id = arguments.get("trace_id")
            request_id = arguments.get("request_id")
            hours = arguments.get("hours", 1)

            if not trace_id and not request_id:
                return [TextContent(type="text", text="Error: Must provide either trace_id or request_id")]

            end = datetime.now()
            start = end - timedelta(hours=hours)

            if trace_id:
                logql = f'{{service="{service}"}} |~ "{trace_id}"'
            else:
                logql = f'{{service="{service}"}} |~ "{request_id}"

            result = client.query_range(logql, start, end, limit=1000)

            correlated = {}
            for stream in result.get("data", {}).get("result", []):
                service = stream.get("stream", {}).get("service", "unknown")
                if service not in correlated:
                    correlated[service] = []

                for entry in stream.get("values", []):
                    timestamp_ns, line = entry
                    timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1e9)

                    correlated[service].append({
                        "timestamp": timestamp.isoformat(),
                        "line": line
                    })

            # Sort each service's logs chronologically
            for service in correlated:
                correlated[service].sort(key=lambda e: e["timestamp"])

            output = [f"Correlated Logs Across {len(correlated)} Services:"]

            for service, logs in correlated.items():
                output.append(f"\n{service}: {len(logs)} entries")

                for log in logs[:3]:  # Show first 3 per service
                    output.append(f"  {log['timestamp']} - {log['line'][:80]}")

                if len(logs) > 3:
                    output.append(f"  ... and {len(logs) - 3} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "detect_patterns":
            pattern = arguments["pattern"]
            service = arguments.get("service")
            hours = arguments.get("hours", 24)

            end = datetime.now()
            start = end - timedelta(hours=hours)

            logql = f'{{service="{service}"}}' if service else ""
            logql += f' |~ "{pattern}"'

            result = client.query_range(logql, start, end, limit=1000)

            matches = []
            for stream in result.get("data", {}).get("result", []):
                stream_info = stream.get("stream", {})
                service_name = stream_info.get("service", "unknown")
                container = stream_info.get("container", "unknown")

                for entry in stream.get("values", []):
                    timestamp_ns, line = entry
                    timestamp = datetime.fromtimestamp(int(timestamp_ns) / 1e9)

                    # Extract pattern matches
                    regex_matches = re.findall(pattern, line, re.IGNORECASE)

                    matches.append({
                        "timestamp": timestamp.isoformat(),
                        "service": service_name,
                        "container": container,
                        "line": line,
                        "matches": regex_matches
                    })

            # Sort by timestamp descending
            matches.sort(key=lambda e: e["timestamp"], reverse=True)

            output = [f"Pattern Matches for '{pattern}' (last {hours}h):"]
            output.append(f"Found {len(matches)} matches")

            for match in matches[:20]:  # Show first 20
                output.append(f"\n  {match['timestamp']} ({match['service']}): {match['line'][:80]}")

            if len(matches) > 20:
                output.append(f"\n  ... and {len(matches) - 20} more matches")

            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Loki query failed: {e}")]
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
