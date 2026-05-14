#!/usr/bin/env python3
"""
Grafana Dashboard Specialist - Observability Layer Agent

Manages Grafana dashboards, datasources, and alert configurations.
Creates and updates visualizations based on system metrics and observability data.

Usage:
    python pmoves/tools/observability/dashboard_specialist.py list
    python pmoves/tools/observability/dashboard_specialist.py create <dashboard_title> --template <template_name>
    python pmoves/tools/observability/dashboard_specialist.py update <dashboard_uid> --metrics
    python pmoves/tools/observability/dashboard_specialist.py alert <dashboard_uid> --threshold <value>

Environment:
    GRAFANA_URL - Grafana server URL (default: http://localhost:3002)
    GRAFANA_API_KEY - Grafana API key (optional, for authenticated requests)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

# Add repo root to path
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class GrafanaDashboardSpecialist:
    """Specialist agent for Grafana dashboard management and visualization."""

    def __init__(
        self,
        grafana_url: str | None = None,
        api_key: str | None = None
    ):
        """Initialize Grafana client.

        Args:
            grafana_url: Grafana server URL (default from env or localhost:3002)
            api_key: Grafana API key (optional)
        """
        self.grafana_url = grafana_url or os.getenv(
            "GRAFANA_URL", "http://localhost:3002"
        )
        self.api_key = api_key or os.getenv("GRAFANA_API_KEY")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}"
            })

    def list_dashboards(self, folder_filter: str | None = None) -> List[Dict[str, Any]]:
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
            f"{self.grafana_url}/api/search",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_dashboard(self, dashboard_uid: str) -> Dict[str, Any]:
        """Get dashboard details by UID.

        Args:
            dashboard_uid: Dashboard UID

        Returns:
            Dashboard configuration
        """
        response = self.session.get(
            f"{self.grafana_url}/api/dashboards/uid/{dashboard_uid}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def create_dashboard(
        self,
        title: str,
        template: str = "default",
        metrics: List[Dict[str, Any]] | None = None
    ) -> Dict[str, Any]:
        """Create a new dashboard.

        Args:
            title: Dashboard title
            template: Dashboard template name (default, service, overview)
            metrics: List of metric queries to visualize

        Returns:
            Created dashboard details
        """
        dashboard_config = self._build_dashboard_template(title, template, metrics)

        payload = {
            "dashboard": dashboard_config,
            "message": f"Created dashboard '{title}' via Observability Agent",
            "overwrite": False
        }

        response = self.session.post(
            f"{self.grafana_url}/api/dashboards/db",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def update_dashboard(
        self,
        dashboard_uid: str,
        metrics: List[Dict[str, Any]] | None = None
    ) -> Dict[str, Any]:
        """Update existing dashboard with new metrics.

        Args:
            dashboard_uid: Dashboard UID
            metrics: List of metric queries to add

        Returns:
            Updated dashboard details
        """
        # Get existing dashboard
        current = self.get_dashboard(dashboard_uid)
        dashboard_config = current["dashboard"]

        # Add new metric panels
        if metrics:
            for i, metric in enumerate(metrics):
                panel = self._build_panel_from_metric(metric, i)
                dashboard_config["panels"].append(panel)

        payload = {
            "dashboard": dashboard_config,
            "message": "Updated dashboard via Observability Agent",
            "overwrite": True
        }

        response = self.session.post(
            f"{self.grafana_url}/api/dashboards/db",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def configure_alert(
        self,
        dashboard_uid: str,
        panel_id: int,
        threshold: float,
        condition: str = "greater"
    ) -> Dict[str, Any]:
        """Configure alert on a dashboard panel.

        Args:
            dashboard_uid: Dashboard UID
            panel_id: Panel ID to alert on
            threshold: Alert threshold value
            condition: Alert condition (greater, less, equal)

        Returns:
            Alert configuration result
        """
        # Get current dashboard
        current = self.get_dashboard(dashboard_uid)
        dashboard_config = current["dashboard"]

        # Find target panel
        panel = None
        for p in dashboard_config.get("panels", []):
            if p.get("id") == panel_id:
                panel = p
                break

        if not panel:
            raise ValueError(f"Panel {panel_id} not found in dashboard")

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
            "message": "Added alert configuration via Observability Agent",
            "overwrite": True
        }

        response = self.session.post(
            f"{self.grafana_url}/api/dashboards/db",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def _build_dashboard_template(
        self,
        title: str,
        template: str,
        metrics: List[Dict[str, Any]] | None
    ) -> Dict[str, Any]:
        """Build dashboard configuration from template.

        Args:
            title: Dashboard title
            template: Template name
            metrics: Optional metric queries

        Returns:
            Dashboard configuration
        """
        config = {
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
            config["panels"].extend([
                self._build_panel_from_metric({
                    "title": "Request Rate",
                    "query": 'rate(http_requests_total[5m])',
                    "type": "graph"
                }, 1),
                self._build_panel_from_metric({
                    "title": "Error Rate",
                    "query": 'rate(http_errors_total[5m])',
                    "type": "graph"
                }, 2),
                self._build_panel_from_metric({
                    "title": "Latency (p95)",
                    "query": 'histogram_quantile(0.95, http_request_duration_seconds_bucket)',
                    "type": "graph"
                }, 3),
            ])
        elif template == "overview":
            config["panels"].extend([
                self._build_panel_from_metric({
                    "title": "Service Health",
                    "query": 'up{job="pmoves"}',
                    "type": "stat"
                }, 1),
                self._build_panel_from_metric({
                    "title": "Container CPU",
                    "query": 'rate(container_cpu_usage_seconds_total[5m])',
                    "type": "graph"
                }, 2),
                self._build_panel_from_metric({
                    "title": "Container Memory",
                    "query": 'container_memory_usage_bytes',
                    "type": "graph"
                }, 3),
            ])

        # Add custom metric panels if provided
        if metrics:
            for i, metric in enumerate(metrics, start=len(config["panels"]) + 1):
                config["panels"].append(
                    self._build_panel_from_metric(metric, i)
                )

        return config

    def _build_panel_from_metric(self, metric: Dict[str, Any], panel_id: int) -> Dict[str, Any]:
        """Build Grafana panel from metric definition.

        Args:
            metric: Metric definition with title, query, type
            panel_id: Panel ID

        Returns:
            Panel configuration
        """
        panel_type = metric.get("type", "graph")

        panel = {
            "id": panel_id,
            "title": metric.get("title", f"Panel {panel_id}"),
            "type": panel_type,
            "gridPos": {
                "h": 8,
                "w": 12,
                "x": (panel_id - 1) % 2 * 12,
                "y": ((panel_id - 1) // 2) * 8
            },
            "targets": [
                {
                    "expr": metric.get("query", "up"),
                    "refId": "A",
                    "datasource": {
                        "type": "prometheus",
                        "uid": "PD8C576611E679907"
                    }
                }
            ]
        }

        if panel_type == "stat":
            panel["gridPos"]["w"] = 6
            panel["options"] = {
                "graphMode": "area",
                "colorMode": "value"
            }
        elif panel_type == "graph":
            panel["options"] = {
                "legend": {
                    "displayMode": "table",
                    "placement": "bottom"
                }
            }

        return panel


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Grafana Dashboard Specialist - Observability Layer Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List dashboards")
    list_parser.add_argument("--folder", help="Filter by folder name")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create dashboard")
    create_parser.add_argument("title", help="Dashboard title")
    create_parser.add_argument("--template", default="default", help="Dashboard template")
    create_parser.add_argument("--metrics", help="JSON file with metric definitions")

    # Update command
    update_parser = subparsers.add_parser("update", help="Update dashboard")
    update_parser.add_argument("dashboard_uid", help="Dashboard UID")
    update_parser.add_argument("--metrics", help="JSON file with metric definitions")

    # Alert command
    alert_parser = subparsers.add_parser("alert", help="Configure alert")
    alert_parser.add_argument("dashboard_uid", help="Dashboard UID")
    alert_parser.add_argument("--panel-id", type=int, required=True, help="Panel ID")
    alert_parser.add_argument("--threshold", type=float, required=True, help="Alert threshold")
    alert_parser.add_argument("--condition", default="greater", help="Alert condition")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    specialist = GrafanaDashboardSpecialist()

    try:
        if args.command == "list":
            dashboards = specialist.list_dashboards(args.folder)
            print(f"[+] Found {len(dashboards)} dashboards:")
            for db in dashboards[:20]:
                print(f"  - {db.get('title')} (UID: {db.get('uid')})")
            if len(dashboards) > 20:
                print(f"  ... and {len(dashboards) - 20} more")

        elif args.command == "create":
            metrics = None
            if args.metrics:
                with open(args.metrics) as f:
                    metrics = json.load(f)

            result = specialist.create_dashboard(args.title, args.template, metrics)
            uid = result.get("uid", "N/A")
            url = f"{specialist.grafana_url}/d/{uid}"
            print(f"[+] Dashboard created: {url}")

        elif args.command == "update":
            metrics = None
            if args.metrics:
                with open(args.metrics) as f:
                    metrics = json.load(f)

            result = specialist.update_dashboard(args.dashboard_uid, metrics)
            print(f"[+] Dashboard updated: {args.dashboard_uid}")

        elif args.command == "alert":
            result = specialist.configure_alert(
                args.dashboard_uid,
                args.panel_id,
                args.threshold,
                args.condition
            )
            print(f"[+] Alert configured on panel {args.panel_id}")

        return 0

    except requests.RequestException as e:
        print(f"[!] Grafana API request failed: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"[!] Metrics file not found: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        return 130
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
