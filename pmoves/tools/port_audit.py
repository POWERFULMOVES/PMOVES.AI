#!/usr/bin/env python3
"""Port Binding Security Audit — verifies Docker Compose port bindings.

Parses `docker compose config` output and classifies each published port as
localhost-only (127.0.0.1) or mesh-accessible (0.0.0.0).  Flags unexpected
0.0.0.0 bindings not in the mesh allowlist.

Usage:
    python tools/port_audit.py              # audit from pmoves/
    make -C pmoves port-audit               # via Makefile
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Services allowed to bind to 0.0.0.0 (mesh-accessible).
# Preferred policy is still loopback-by-default with reviewed mesh overrides.
# The compose file contains some historical broader defaults, so treat this tool
# as a tightening audit rather than proof that every current base binding is
# already ideal. For node-local opt-ins, copy reviewed entries from
# `pmoves/env.mesh-bind.example` and add those services here only on nodes where
# direct mesh exposure is intentional.
MESH_ALLOWED_SERVICES = set()

# Kong admin port is explicitly excluded from mesh
KONG_ADMIN_PORTS = {"8001"}


def parse_compose_config():
    """Run docker compose config and parse the YAML output as JSON."""
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            capture_output=True, text=True, cwd=str(ROOT), timeout=30,
        )
        if result.returncode != 0:
            print(f"WARNING: docker compose config failed: {result.stderr[:200]}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        print(f"WARNING: Could not run docker compose config: {e}", file=sys.stderr)
        return None


def audit_ports(config: dict) -> list[dict]:
    """Extract and classify port bindings from compose config."""
    findings = []
    services = config.get("services", {})

    for svc_name, svc_config in sorted(services.items()):
        ports = svc_config.get("ports", [])
        for port_entry in ports:
            if isinstance(port_entry, dict):
                host_ip = port_entry.get("host_ip", "0.0.0.0")
                published = str(port_entry.get("published", ""))
                target = str(port_entry.get("target", ""))
            elif isinstance(port_entry, str):
                # Parse string format: [host_ip:]host_port:container_port
                parts = port_entry.split(":")
                if len(parts) == 3:
                    host_ip, published, target = parts
                elif len(parts) == 2:
                    host_ip, published, target = "0.0.0.0", parts[0], parts[1]
                else:
                    continue
            else:
                continue

            if not host_ip:
                host_ip = "0.0.0.0"

            is_mesh = svc_name in MESH_ALLOWED_SERVICES
            is_kong_admin = svc_name == "supabase-kong" and published in KONG_ADMIN_PORTS

            if is_kong_admin:
                expected = "127.0.0.1"
            elif is_mesh:
                expected = "0.0.0.0"
            else:
                expected = "127.0.0.1"

            status = "OK" if host_ip == expected else "VIOLATION"

            findings.append({
                "service": svc_name,
                "host_port": published,
                "container_port": target,
                "bind": host_ip,
                "expected": expected,
                "status": status,
            })

    return findings


def print_report(findings: list[dict]) -> int:
    """Print audit report and return exit code (non-zero if violations)."""
    violations = [f for f in findings if f["status"] == "VIOLATION"]

    print(f"{'SERVICE':<35} {'HOST_PORT':>10} {'BIND':>12} {'EXPECTED':>12} {'STATUS':>10}")
    print("-" * 85)

    for f in findings:
        marker = "!!" if f["status"] == "VIOLATION" else "  "
        print(f"{marker}{f['service']:<33} {f['host_port']:>10} {f['bind']:>12} {f['expected']:>12} {f['status']:>10}")

    print(f"\nTotal: {len(findings)} ports | Violations: {len(violations)}")

    if violations:
        print("\nVIOLATIONS (unexpected 0.0.0.0 or wrong bind address):")
        for v in violations:
            print(f"  {v['service']}:{v['host_port']} bound to {v['bind']} (expected {v['expected']})")
        return 1

    print("\nAll port bindings match security policy.")
    return 0


def main() -> int:
    config = parse_compose_config()
    if config is None:
        print("ERROR: dynamic compose parsing failed — failing closed.", file=sys.stderr)
        print("Run 'docker compose config' manually to diagnose.", file=sys.stderr)
        return 1
    if not config.get("services"):
        print("ERROR: compose config returned no services — failing closed.", file=sys.stderr)
        return 1

    findings = audit_ports(config)
    return print_report(findings)


if __name__ == "__main__":
    sys.exit(main())
