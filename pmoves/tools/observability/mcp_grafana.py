#!/usr/bin/env python3
"""
Grafana Dashboard MCP Server - Observability Layer

MCP server for Grafana dashboard management.
Provides tools for agents to manage dashboards and alerts.

Usage:
    python tools/observability/mcp_grafana.py
    (Runs as MCP server via stdio)

Environment:
    GRAFANA_URL - Grafana server URL (default: http://localhost:3000)
    GRAFANA_API_KEY - Grafana API key (optional, for authenticated requests)
"""

import asyncio
import os
import sys
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
server = Server("grafana-dashboard")

# Grafana configuration
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY")


class GrafanaClient:
    """Grafana client for dashboard management."""

    def __init__(self, base_url: str = GRAFANA_URL, api_key: str | None = GRAFANA_API_KEY):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        if api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}"
            })

    def list_dashboards(self, folder_filter: str | None = None) -> list[dict[str, Any]]:
        """List all Grafana dashboards.

        Args:
            folder_filter: Optional folder name filter

        Returns:
            List of dashboard metadata
        """
        params = {}
        if folder_filter:
            params["folderIds"] = folder_filter

        response = self.session.get(
            f"{self.base_url}/api/search",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_dashboard(self, dashboard_uid: str) -> dict[str, Any]:
        """Get dashboard details by UID.

        Args:
            dashboard_uid: Dashboard UID

        Returns:
            Dashboard configuration
        """
        response = self.session.get(
            f"{self.base_url}/api/dashboards/uid/{dashboard_uid}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list_dashboards",
            description="List all Grafana dashboards",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Optional folder name filter"
                    }
                }
            }
        ),
        Tool(
            name="get_dashboard",
            description="Get dashboard details by UID",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_uid": {
                        "type": "string",
                        "description": "Dashboard UID"
                    }
                },
                "required": ["dashboard_uid"]
            }
        ),
        Tool(
            name="create_dashboard",
            description="Create a new dashboard (basic template)",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Dashboard title"
                    },
                    "template": {
                        "type": "string",
                        "description": "Dashboard template (default, service, overview)",
                        "enum": ["default", "service", "overview"],
                        "default": "default"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="configure_alert",
            description="Configure alert on a dashboard panel",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_uid": {
                        "type": "string",
                        "description": "Dashboard UID"
                    },
                    "panel_id": {
                        "type": "number",
                        "description": "Panel ID to alert on"
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Alert threshold value"
                    },
                    "condition": {
                        "type": "string",
                        "description": "Alert condition (greater, less, equal)",
                        "enum": ["greater", "less", "equal"],
                        "default": "greater"
                    }
                },
                "required": ["dashboard_uid", "panel_id", "threshold"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle MCP tool calls."""

    client = GrafanaClient()

    try:
        if name == "list_dashboards":
            folder = arguments.get("folder")

            dashboards = client.list_dashboards(folder)

            output = [f"Found {len(dashboards)} dashboards:"]

            for db in dashboards[:20]:  # Show first 20
                title = db.get("title", "untitled")
                uid = db.get("uid", "unknown")
                output.append(f"  - {title} (UID: {uid})")

            if len(dashboards) > 20:
                output.append(f"  ... and {len(dashboards) - 20} more")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "get_dashboard":
            dashboard_uid = arguments["dashboard_uid"]

            dashboard = client.get_dashboard(dashboard_uid)
            dashboard_data = dashboard.get("dashboard", {})
            meta = dashboard.get("meta", {})

            title = dashboard_data.get("title", "untitled")
            uid = meta.get("slug", dashboard_uid)
            version = dashboard_data.get("version", 0)

            panels = dashboard_data.get("panels", [])
            rows = dashboard_data.get("rows", [])

            output = [
                f"Dashboard: {title}",
                f"UID: {uid}",
                f"Version: {version}",
                f"\nStructure:",
                f"  Panels: {len(panels)}",
                f"  Rows: {len(rows)}"
            ]

            if panels:
                output.append(f"\nPanels (first 10):")
                for panel in panels[:10]:
                    panel_title = panel.get("title", "untitled")
                    panel_id = panel.get("id", 0)
                    panel_type = panel.get("type", "unknown")
                    output.append(f"  [{panel_id}] {panel_title} ({panel_type})")

                if len(panels) > 10:
                    output.append(f"  ... and {len(panels) - 10} more panels")

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "create_dashboard":
            title = arguments["title"]
            template = arguments.get("template", "default")

            # Build basic dashboard template
            dashboard_config = {
                "title": title,
                "tags": ["observability", "pmoves"],
                "timezone": "browser",
                "refresh": "30s",
                "panels": [],
                "schemaVersion": 38,
                "version": 1
            }

            # Add template-specific panels
            if template == "service":
                dashboard_config["panels"] = [
                    {
                        "id": 1,
                        "title": "Request Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'rate(http_requests_total[5m])',
                                "refId": "A"
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "title": "Error Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'rate(http_errors_total[5m])',
                                "refId": "A"
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "title": "Latency (p95)",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'histogram_quantile(0.95, http_request_duration_seconds_bucket)',
                                "refId": "A"
                            }
                        ]
                    }
                ]
            elif template == "overview":
                dashboard_config["panels"] = [
                    {
                        "id": 1,
                        "title": "Service Health",
                        "type": "stat",
                        "targets": [
                            {
                                "expr": 'up{job="pmoves"}',
                                "refId": "A"
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "title": "Container CPU",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'rate(container_cpu_usage_seconds_total[5m])',
                                "refId": "A"
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "title": "Container Memory",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'container_memory_usage_bytes',
                                "refId": "A"
                            }
                        ]
                    }
                ]

            payload = {
                "dashboard": dashboard_config,
                "message": f"Created dashboard '{title}' via Observability MCP",
                "overwrite": False
            }

            response = client.session.post(
                f"{client.base_url}/api/dashboards/db",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            result = response.json()
            uid = result.get("uid", "N/A")
            url = f"{client.base_url}/d/{uid}"

            output = [
                f"Dashboard created successfully!",
                f"Title: {title}",
                f"Template: {template}",
                f"UID: {uid}",
                f"URL: {url}"
            ]

            return [TextContent(type="text", text="\n".join(output))]

        elif name == "configure_alert":
            dashboard_uid = arguments["dashboard_uid"]
            panel_id = arguments["panel_id"]
            threshold = arguments["threshold"]
            condition = arguments.get("condition", "greater")

            # Get current dashboard
            current = client.get_dashboard(dashboard_uid)
            dashboard_config = current["dashboard"]

            # Find target panel
            panel = None
            for p in dashboard_config.get("panels", []):
                if p.get("id") == panel_id:
                    panel = p
                    break

            if not panel:
                return [TextContent(type="text", text=f"Error: Panel {panel_id} not found in dashboard")]

            # Add alert configuration
            panel["alert"] = {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [threshold],
                            "type": condition
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["A", "5m", "now"]
                        },
                        "reducer": {
                            "params": [],
                            "type": "avg"
                        },
                        "type": "query"
                    }
                ],
                "executionErrorState": "alerting",
                "frequency": "60s",
                "handler": 1,
                "message": f"Alert: {panel.get('title', 'Panel')} has exceeded threshold {threshold}",
                "name": f"{panel.get('title', 'Panel')} Alert",
                "noDataState": "no_data",
                "notifications": []
            }

            # Update dashboard
            payload = {
                "dashboard": dashboard_config,
                "message": "Added alert configuration via Observability MCP",
                "overwrite": True
            }

            response = client.session.post(
                f"{client.base_url}/api/dashboards/db",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            output = [
                f"Alert configured successfully!",
                f"Dashboard: {dashboard_uid}",
                f"Panel ID: {panel_id}",
                f"Panel Title: {panel.get('title', 'Panel')}",
                f"Threshold: {threshold}",
                f"Condition: {condition}"
            ]

            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except requests.RequestException as e:
        return [TextContent(type="text", text=f"Grafana API request failed: {e}")]
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
