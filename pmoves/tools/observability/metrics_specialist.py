#!/usr/bin/env python3
"""
Prometheus Metrics Specialist - Observability Layer Agent

Analyzes Prometheus metrics to detect anomalies, trends, and performance issues.
Feeds insights back to Agent Zero for task assignment and system optimization.

Usage:
    python pmoves/tools/observability/metrics_specialist.py query <metric_name>
    python pmoves/tools/observability/metrics_specialist.py anomaly <service_name>
    python pmoves/tools/observability/metrics_specialist.py trend <metric_name> --hours 24

Environment:
    PROMETHEUS_URL - Prometheus server URL (default: http://localhost:9090)
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


class PrometheusMetricsSpecialist:
    """Specialist agent for Prometheus metrics analysis and anomaly detection."""

    def __init__(self, prometheus_url: str | None = None):
        """Initialize Prometheus client.

        Args:
            prometheus_url: Prometheus server URL (default from env or localhost:9090)
        """
        self.prometheus_url = prometheus_url or os.getenv(
            "PROMETHEUS_URL", "http://localhost:9090"
        )
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def query(self, query: str, time: str | None = None) -> Dict[str, Any]:
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
            f"{self.prometheus_url}/api/v1/query",
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
    ) -> Dict[str, Any]:
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
            f"{self.prometheus_url}/api/v1/query_range",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def detect_anomalies(self, service: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Detect metric anomalies for a service.

        Args:
            service: Service name to analyze
            hours: Lookback period in hours

        Returns:
            List of detected anomalies
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        anomalies = []

        # Check for high error rate
        error_rate_query = 'rate({service}_errors_total[5m]) > 0.05'
        try:
            result = self.query_range(error_rate_query, start, end)
            if result["data"]["result"]:
                anomalies.append({
                    "type": "high_error_rate",
                    "severity": "critical",
                    "service": service,
                    "description": "Error rate exceeding 5% threshold",
                    "metric": "error_rate",
                    "value": result["data"]["result"]
                })
        except Exception as e:
            print(f"[WARN] Error rate check failed: {e}")

        # Check for high latency
        latency_query = 'rate({service}_latency_seconds_bucket[5m])'
        try:
            result = self.query_range(latency_query, start, end)
            if result["data"]["result"]:
                anomalies.append({
                    "type": "high_latency",
                    "severity": "warning",
                    "service": service,
                    "description": "Latency percentile p95 above threshold",
                    "metric": "latency_p95",
                    "value": result["data"]["result"]
                })
        except Exception as e:
            print(f"[WARN] Latency check failed: {e}")

        # Check for resource saturation (CPU, memory)
        cpu_query = f'rate(process_cpu_seconds_total{{service="{service}"}}[5m]) > 0.8'
        try:
            result = self.query_range(cpu_query, start, end)
            if result["data"]["result"]:
                anomalies.append({
                    "type": "cpu_saturation",
                    "severity": "warning",
                    "service": service,
                    "description": "CPU usage above 80%",
                    "metric": "cpu_usage",
                    "value": result["data"]["result"]
                })
        except Exception as e:
            print(f"[WARN] CPU check failed: {e}")

        return anomalies

    def trend_analysis(
        self,
        metric: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze metric trends over time.

        Args:
            metric: Metric name or PromQL expression
            hours: Analysis period in hours

        Returns:
            Trend analysis results
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        result = self.query_range(metric, start, end, step="1h")

        if not result["data"]["result"]:
            return {"error": "No data returned for metric"}

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
            return {"error": "No valid values in result"}

        # Calculate trend statistics
        avg_value = sum(values) / len(values)
        min_value = min(values)
        max_value = max(values)

        # Simple trend detection (first half vs second half)
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid if mid > 0 else avg_value
        second_half_avg = sum(values[mid:]) / (len(values) - mid) if len(values) > mid else avg_value

        trend_direction = "stable"
        if second_half_avg > first_half_avg * 1.1:
            trend_direction = "increasing"
        elif second_half_avg < first_half_avg * 0.9:
            trend_direction = "decreasing"

        return {
            "metric": metric,
            "period_hours": hours,
            "avg": avg_value,
            "min": min_value,
            "max": max_value,
            "trend": trend_direction,
            "change_percent": ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        }

    def list_service_metrics(self, service: str) -> List[str]:
        """List available metrics for a service.

        Args:
            service: Service name pattern

        Returns:
            List of metric names matching the service
        """
        # Use label values to find matching metrics
        response = self.session.get(
            f"{self.prometheus_url}/api/v1/label/__name__/values",
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

        return matching_metrics[:50]  # Limit to prevent overwhelming output


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Prometheus Metrics Specialist - Observability Layer Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Query command
    query_parser = subparsers.add_parser("query", help="Execute PromQL query")
    query_parser.add_argument("promql", help="PromQL expression")
    query_parser.add_argument("--time", help="Optional timestamp")

    # Anomaly detection command
    anomaly_parser = subparsers.add_parser("anomaly", help="Detect anomalies")
    anomaly_parser.add_argument("service", help="Service name to analyze")
    anomaly_parser.add_argument("--hours", type=int, default=1, help="Lookback period")

    # Trend analysis command
    trend_parser = subparsers.add_parser("trend", help="Analyze metric trends")
    trend_parser.add_argument("metric", help="Metric name or PromQL expression")
    trend_parser.add_argument("--hours", type=int, default=24, help="Analysis period")

    # List metrics command
    list_parser = subparsers.add_parser("list", help="List service metrics")
    list_parser.add_argument("service", help="Service name pattern")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    specialist = PrometheusMetricsSpecialist()

    try:
        if args.command == "query":
            result = specialist.query(args.promql, args.time)
            print("[+] Query result:")
            print(result)

        elif args.command == "anomaly":
            anomalies = specialist.detect_anomalies(args.service, args.hours)
            if anomalies:
                print(f"[!] Found {len(anomalies)} anomalies for {args.service}:")
                for anomaly in anomalies:
                    print(f"  - {anomaly['type']} ({anomaly['severity']}): {anomaly['description']}")
            else:
                print(f"[+] No anomalies detected for {args.service}")

        elif args.command == "trend":
            trend = specialist.trend_analysis(args.metric, args.hours)
            if "error" in trend:
                print(f"[!] {trend['error']}")
            else:
                print(f"[+] Trend analysis for {trend['metric']}:")
                print(f"  Period: {trend['period_hours']}h")
                print(f"  Average: {trend['avg']:.2f}")
                print(f"  Range: [{trend['min']:.2f}, {trend['max']:.2f}]")
                print(f"  Trend: {trend['trend']} ({trend['change_percent']:+.1f}%)")

        elif args.command == "list":
            metrics = specialist.list_service_metrics(args.service)
            print(f"[+] Found {len(metrics)} metrics for {args.service}:")
            for metric in metrics[:20]:  # Show first 20
                print(f"  - {metric}")
            if len(metrics) > 20:
                print(f"  ... and {len(metrics) - 20} more")

        return 0

    except requests.RequestException as e:
        print(f"[!] Prometheus query failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        return 130
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
