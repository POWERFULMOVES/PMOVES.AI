#!/usr/bin/env python3
"""
Loki Logs Specialist - Observability Layer Agent

Analyzes Loki logs to extract patterns, detect errors, and correlate events across services.
Feeds insights back to Agent Zero for debugging and system optimization.

Usage:
    python pmoves/tools/observability/logs_specialist.py query <logql>
    python pmoves/tools/observability/logs_specialist.py errors <service_name> --hours 1
    python pmoves/tools/observability/logs_specialist.py correlate --trace <trace_id>
    python pmoves/tools/observability/logs_specialist.py pattern <regex_pattern>

Environment:
    LOKI_URL - Loki server URL (default: http://localhost:3100)
"""

import argparse
import os
import re
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import requests

# Add repo root to path
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


class LokiLogsSpecialist:
    """Specialist agent for Loki log analysis and pattern detection."""

    def __init__(self, loki_url: str | None = None):
        """Initialize Loki client.

        Args:
            loki_url: Loki server URL (default from env or localhost:3100)
        """
        self.loki_url = loki_url or os.getenv(
            "LOKI_URL", "http://localhost:3100"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def query(self, logql: str, limit: int = 100) -> Dict[str, Any]:
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
            f"{self.loki_url}/loki/api/v1/query_range",
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
    ) -> Dict[str, Any]:
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
            f"{self.loki_url}/loki/api/v1/query_range",
            params=params,
            timeout=60
        )
        response.raise_for_status()
        return response.json()

    def extract_errors(self, service: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Extract error logs for a service.

        Args:
            service: Service name
            hours: Lookback period in hours

        Returns:
            List of error log entries with context
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        # LogQL for error logs
        logql = f'{{service="{service}"}} |~ "(?i)(error|exception|fatal|panic)"'

        result = self.query_range(logql, start, end, limit=500)

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
                    "level": self._extract_log_level(line)
                })

        return sorted(errors, key=lambda e: e["timestamp"], reverse=True)

    def correlate_logs(
        self,
        trace_id: str | None = None,
        request_id: str | None = None,
        hours: int = 1
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Correlate logs across services by trace or request ID.

        Args:
            trace_id: Optional trace ID
            request_id: Optional request ID
            hours: Lookback period

        Returns:
            Correlated logs grouped by service
        """
        if not trace_id and not request_id:
            raise ValueError("Must provide either trace_id or request_id")

        end = datetime.now()
        start = end - timedelta(hours=hours)

        if trace_id:
            logql = f'|~ "{trace_id}"'
        else:
            logql = f'|~ "{request_id}"'

        result = self.query_range(logql, start, end, limit=1000)

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

        return correlated

    def detect_patterns(
        self,
        pattern: str,
        service: str | None = None,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Detect regex patterns in logs.

        Args:
            pattern: Regular expression pattern
            service: Optional service filter
            hours: Lookback period

        Returns:
            List of matching log entries
        """
        end = datetime.now()
        start = end - timedelta(hours=hours)

        logql = f'{{service="{service}"}}' if service else ""
        logql += f' |~ "{pattern}"'

        result = self.query_range(logql, start, end, limit=1000)

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

        return sorted(matches, key=lambda e: e["timestamp"], reverse=True)

    def _extract_log_level(self, line: str) -> str:
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


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Loki Logs Specialist - Observability Layer Agent"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Query command
    query_parser = subparsers.add_parser("query", help="Execute LogQL query")
    query_parser.add_argument("logql", help="LogQL expression")
    query_parser.add_argument("--limit", type=int, default=100, help="Result limit")

    # Errors command
    errors_parser = subparsers.add_parser("errors", help="Extract error logs")
    errors_parser.add_argument("service", help="Service name")
    errors_parser.add_argument("--hours", type=int, default=1, help="Lookback period")

    # Correlate command
    correlate_parser = subparsers.add_parser("correlate", help="Correlate logs")
    correlate_parser.add_argument("--trace", help="Trace ID")
    correlate_parser.add_argument("--request", help="Request ID")
    correlate_parser.add_argument("--hours", type=int, default=1, help="Lookback period")

    # Pattern command
    pattern_parser = subparsers.add_parser("pattern", help="Detect patterns")
    pattern_parser.add_argument("regex", help="Regular expression pattern")
    pattern_parser.add_argument("--service", help="Filter by service")
    pattern_parser.add_argument("--hours", type=int, default=24, help="Lookback period")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    specialist = LokiLogsSpecialist()

    try:
        if args.command == "query":
            result = specialist.query(args.logql, args.limit)
            print("[+] Query results:")
            print(json.dumps(result, indent=2))

        elif args.command == "errors":
            errors = specialist.extract_errors(args.service, args.hours)
            print(f"[+] Found {len(errors)} error logs for {args.service}:")
            for error in errors[:20]:  # Show first 20
                level = error.get("level", "info").upper()
                print(f"  [{level}] {error['timestamp']} - {error['line'][:100]}")
            if len(errors) > 20:
                print(f"  ... and {len(errors) - 20} more errors")

        elif args.command == "correlate":
            correlated = specialist.correlate_logs(args.trace, args.request, args.hours)
            print(f"[+] Correlated logs across {len(correlated)} services:")
            for service, logs in correlated.items():
                print(f"\n  {service}: {len(logs)} entries")
                for log in logs[:3]:  # Show first 3 per service
                    print(f"    {log['timestamp']} - {log['line'][:80]}")
                if len(logs) > 3:
                    print(f"    ... and {len(logs) - 3} more")

        elif args.command == "pattern":
            matches = specialist.detect_patterns(args.regex, args.service, args.hours)
            print(f"[+] Found {len(matches)} matches for pattern '{args.regex}':")
            for match in matches[:20]:
                print(f"  {match['timestamp']} ({match['service']}): {match['line'][:80]}")
            if len(matches) > 20:
                print(f"  ... and {len(matches) - 20} more matches")

        return 0

    except requests.RequestException as e:
        print(f"[!] Loki query failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Interrupted")
        return 130
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
