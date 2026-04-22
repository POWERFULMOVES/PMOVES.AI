#!/usr/bin/env python3
"""
TensorZero LLM Observability MCP Server - Observability Layer

MCP server for TensorZero LLM performance and cost analysis.
Provides tools for agents to query LLM metrics from ClickHouse.

Usage:
    python tools/observability/mcp_tensorzero.py
    (Runs as MCP server via stdio)

Environment:
    TENSORZERO_CLICKHOUSE_URL - ClickHouse URL (default: http://localhost:8123)
    TENSORZERO_CLICKHOUSE_USER - ClickHouse user (default: tensorzero)
    TENSORZERO_CLICKHOUSE_PASSWORD - ClickHouse password (default: tensorzero)
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
server = Server("tensorzero-llm-observability")

# TensorZero ClickHouse configuration
CLICKHOUSE_URL = os.getenv("TENSORZERO_CLICKHOUSE_URL", "http://localhost:8123")
CLICKHOUSE_USER = os.getenv("TENSORZERO_CLICKHOUSE_USER", "tensorzero")
CLICKHOUSE_PASSWORD = os.getenv("TENSORZERO_CLICKHOUSE_PASSWORD", "tensorzero")


class TensorZeroClient:
    """TensorZero ClickHouse client for LLM metrics."""

    def __init__(
        self,
        clickhouse_url: str = CLICKHOUSE_URL,
        user: str = CLICKHOUSE_USER,
        password: str = CLICKHOUSE_PASSWORD
    ):
        self.clickhouse_url = clickhouse_url
        self.user = user
        self.password = password

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Execute SQL query on ClickHouse.

        Args:
            sql: SQL query

        Returns:
            Query results as list of dicts
        """
        params = {
            "query": sql,
            "database": "default",
            "format": "JSON"
        }

        response = requests.get(
            self.clickhouse_url,
            params=params,
            auth=(self.user, self.password),
            timeout=30
        )
        response.raise_for_status()
        return response.json().get("data", [])

    def get_model_performance(
        self,
        model: str | None = None,
        hours: int = 24
    ) -> dict[str, Any]:
        """Get LLM performance metrics.

        Args:
            model: Optional model name filter
            hours: Analysis period in hours

        Returns:
            Performance metrics
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        model_filter = f"AND model_name = '{model}'" if model else ""

        sql = f"""
        SELECT
            model_name,
            count() as total_requests,
            avg(latency) as avg_latency_ms,
            quantile(0.50)(latency) as p50_latency_ms,
            quantile(0.95)(latency) as p95_latency_ms,
            quantile(0.99)(latency) as p99_latency_ms,
            sum(prompt_tokens) as total_prompt_tokens,
            sum(completion_tokens) as total_completion_tokens
        FROM requests
        WHERE start_time >= now() - INTERVAL {hours} HOUR
          {model_filter}
        GROUP BY model_name
        ORDER BY total_requests DESC
        """

        results = self.query(sql)

        if not results:
            return {"error": "No data found for the specified period"}

        return {
            "period_hours": hours,
            "models": results
        }

    def get_cost_analysis(self, hours: int = 24) -> dict[str, Any]:
        """Analyze LLM costs by model and provider.

        Args:
            hours: Analysis period in hours

        Returns:
            Cost breakdown
        """
        sql = f"""
        SELECT
            model_name,
            provider_name,
            count() as total_requests,
            sum(prompt_tokens) as total_prompt_tokens,
            sum(completion_tokens) as total_completion_tokens,
            sum(prompt_tokens + completion_tokens) as total_tokens
        FROM requests
        WHERE start_time >= now() - INTERVAL {hours} HOUR
        GROUP BY model_name, provider_name
        ORDER BY total_tokens DESC
        """

        results = self.query(sql)

        # Estimate costs (approximate pricing)
        cost_per_1k_tokens = {
            "claude-opus-4-5": 15.0,
            "claude-sonnet-4-5": 3.0,
            "claude-haiku-4-5": 0.25,
            "gpt-4": 30.0,
            "gpt-3.5-turbo": 0.5,
            "default": 1.0
        }

        total_estimated_cost = 0.0

        for row in results:
            model = row.get("model_name", "default")
            total_tokens = row.get("total_tokens", 0)

            rate = cost_per_1k_tokens.get(model, cost_per_1k_tokens["default"])
            estimated_cost = (total_tokens / 1000) * rate
            row["estimated_cost_usd"] = estimated_cost
            total_estimated_cost += estimated_cost

        return {
            "period_hours": hours,
            "total_estimated_cost_usd": total_estimated_cost,
            "models": results
        }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="query_clickhouse",
            description="Execute SQL query on TensorZero ClickHouse",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "SQL query to execute"
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="get_model_performance",
            description="Get LLM performance metrics (latency, tokens, requests)",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Optional model name filter"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Analysis period in hours (default: 24)",
                        "default": 24
                    }
                }
            }
        ),
        Tool(
            name="get_cost_analysis",
            description="Analyze LLM costs by model and provider",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "number",
                        "description": "Analysis period in hours (default: 24)",
                        "default": 24
                    }
                }
            }
        ),
        Tool(
            name="compare_models",
            description="Compare performance between two models",
            inputSchema={
                "type": "object",
                "properties": {
                    "model1": {
                        "type": "string",
                        "description": "First model name"
                    },
                    "model2": {
                        "type": "string",
                        "description": "Second model name"
                    },
                    "hours": {
                        "type": "number",
                        "description": "Analysis period in hours (default: 24)",
                        "default": 24
                    }
                },
                "required": ["model1", "model2"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls."""

    client = TensorZeroClient()

    try:
        if name == "query_clickhouse":
            sql = arguments["sql"]

            results = client.query(sql)

            output = [f"Query results ({len(results)} rows):"]

            for row in results[:20]:  # Show first 20
                output.append(f"  {row}")

            if len(results) > 20:
                output.append(f"  ... and {len(results) - 20} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "get_model_performance":
            model = arguments.get("model")
            hours = arguments.get("hours", 24)

            perf = client.get_model_performance(model, hours)

            if "error" in perf:
                return [TextContent(type="text", text=f"Error: {perf['error']}")]

            output = [f"Model Performance (last {perf['period_hours']}h):"]

            for model_data in perf['models']:
                model_name = model_data['model_name']
                total_requests = model_data['total_requests']
                avg_latency = model_data['avg_latency_ms']
                p95_latency = model_data['p95_latency_ms']
                p99_latency = model_data['p99_latency_ms']
                total_tokens = model_data['total_prompt_tokens'] + model_data['total_completion_tokens']

                output.append(f"\n  Model: {model_name}")
                output.append(f"    Requests: {total_requests}")
                output.append(f"    Avg Latency: {avg_latency:.2f}ms")
                output.append(f"    P95 Latency: {p95_latency:.2f}ms")
                output.append(f"    P99 Latency: {p99_latency:.2f}ms")
                output.append(f"    Total Tokens: {total_tokens:,}")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "get_cost_analysis":
            hours = arguments.get("hours", 24)

            cost = client.get_cost_analysis(hours)

            output = [
                f"Cost Analysis (last {cost['period_hours']}h):",
                f"\nTotal Estimated Cost: ${cost['total_estimated_cost_usd']:.2f} USD",
                "\nBreakdown by Model:"
            ]

            for model_data in cost['models']:
                model_name = model_data['model_name']
                provider = model_data.get('provider_name', 'unknown')
                requests = model_data['total_requests']
                tokens = model_data['total_tokens']
                est_cost = model_data['estimated_cost_usd']

                output.append(f"\n  {model_name} ({provider}):")
                output.append(f"    Requests: {requests}")
                output.append(f"    Tokens: {tokens:,}")
                output.append(f"    Est Cost: ${est_cost:.4f} USD")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "compare_models":
            model1 = arguments["model1"]
            model2 = arguments["model2"]
            hours = arguments.get("hours", 24)

            sql = f"""
            SELECT
                model_name,
                count() as total_requests,
                avg(latency) as avg_latency_ms,
                quantile(0.95)(latency) as p95_latency_ms,
                sum(prompt_tokens) as total_prompt_tokens,
                sum(completion_tokens) as total_completion_tokens,
                sum(prompt_tokens + completion_tokens) as total_tokens
            FROM requests
            WHERE start_time >= now() - INTERVAL {hours} HOUR
              AND model_name IN ('{model1}', '{model2}')
            GROUP BY model_name
            """

            results = client.query(sql)

            output = [
                f"Model Comparison (last {hours}h):",
                "\nModels Found:"
            ]

            models_data = {}
            for row in results:
                model = row.get("model_name", "unknown")
                models_data[model] = row

            for model_name, data in models_data.items():
                output.append(f"\n  {model_name}:")
                output.append(f"    Requests: {data['total_requests']}")
                output.append(f"    Avg Latency: {data['avg_latency_ms']:.2f}ms")
                output.append(f"    P95 Latency: {data['p95_latency_ms']:.2f}ms")
                output.append(f"    Total Tokens: {data['total_tokens']:,}")

            if len(results) == 2:
                m1_data = models_data.get(model1, {})
                m2_data = models_data.get(model2, {})

                latency_diff = m2_data.get("avg_latency_ms", 0) - m1_data.get("avg_latency_ms", 0)
                token_diff = m2_data.get("total_tokens", 0) - m1_data.get("total_tokens", 0)
                request_diff = m2_data.get("total_requests", 0) - m1_data.get("total_requests", 0)

                output.append(f"\n  Differences:")
                output.append(f"    Latency: {latency_diff:+.2f}ms")
                output.append(f"    Tokens: {token_diff:+,}")
                output.append(f"    Requests: {request_diff:+,}")

            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"ClickHouse query failed: {e}")]
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
