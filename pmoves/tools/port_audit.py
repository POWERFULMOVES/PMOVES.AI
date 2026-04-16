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
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIND_FILE = ROOT / "env.mesh-bind.local"
PORT_AUDIT_BIND_FILE_ENV = "PORT_AUDIT_BIND_FILE"

# Bind vars that intentionally map to mesh-accessible services when the local
# ignored bind file opts them into 0.0.0.0 exposure.
BIND_VAR_TO_SERVICES = {
    "AGENT_ZERO_BIND": {"agent-zero"},
    "BOTZ_BIND": {"botz-gateway"},
    "CHANNEL_MONITOR_BIND": {"channel-monitor"},
    "DEEPRESEARCH_BIND": {"deepresearch-local"},
    "EVO_CONTROLLER_BIND": {"evo-controller"},
    "FLUTE_BIND": {"flute-gateway"},
    "GPU_ORCHESTRATOR_BIND": {"gpu-orchestrator"},
    "HIRAG_BIND": {"hi-rag-gateway-v2", "hi-rag-gateway-v2-gpu"},
    "HIRAG_V1_BIND": {"hi-rag-gateway"},
    "KONG_PROXY_BIND": {"supabase-kong"},
    "NATS_BIND": {"nats"},
    "PMOVES_UI_BIND": {"pmoves-ui"},
    "PMOVES_YT_BIND": {"pmoves-yt"},
    "PUBLISHER_DISCORD_BIND": {"publisher-discord"},
    "SUPASERCH_BIND": {"supaserch"},
    "TENSORZERO_BIND": {"tensorzero-gateway"},
    "TTS_BIND": {"ultimate-tts-studio"},
}

# Kong admin port is explicitly excluded from mesh
KONG_ADMIN_PORTS = {"8001"}


def load_mesh_allowed_services() -> tuple[Path, set[str], set[str]]:
    """Load mesh-allowed service names from a local ignored bind override file."""
    bind_file = Path(os.environ.get(PORT_AUDIT_BIND_FILE_ENV, str(DEFAULT_BIND_FILE)))
    allowed_services: set[str] = set()
    unmapped_vars: set[str] = set()

    if not bind_file.exists():
        return bind_file, allowed_services, unmapped_vars

    try:
        for raw_line in bind_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            bind_var, bind_value = line.split("=", 1)
            bind_var = bind_var.strip()
            bind_value = bind_value.strip().strip('"').strip("'")
            if bind_value != "0.0.0.0":
                continue

            mapped_services = BIND_VAR_TO_SERVICES.get(bind_var)
            if mapped_services:
                allowed_services.update(mapped_services)
            elif bind_var.endswith("_BIND"):
                unmapped_vars.add(bind_var)
    except OSError as exc:
        print(f"WARNING: Could not read bind override file {bind_file}: {exc}", file=sys.stderr)

    return bind_file, allowed_services, unmapped_vars


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


def audit_ports(config: dict, mesh_allowed_services: set[str]) -> list[dict]:
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

            is_mesh = svc_name in mesh_allowed_services
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


def print_report(
    findings: list[dict],
    bind_file: Path,
    mesh_allowed_services: set[str],
    unmapped_vars: set[str],
) -> int:
    """Print audit report and return exit code (non-zero if violations)."""
    violations = [f for f in findings if f["status"] == "VIOLATION"]

    if bind_file.exists():
        source = ", ".join(sorted(mesh_allowed_services)) or "none"
        print(f"Local mesh allowlist file: {bind_file}")
        print(f"Reviewed mesh exceptions loaded: {source}")
        if unmapped_vars:
            print(f"WARNING: Unmapped *_BIND entries ignored by audit: {', '.join(sorted(unmapped_vars))}")
        print("")

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

    bind_file, mesh_allowed_services, unmapped_vars = load_mesh_allowed_services()
    findings = audit_ports(config, mesh_allowed_services)
    return print_report(findings, bind_file, mesh_allowed_services, unmapped_vars)


if __name__ == "__main__":
    sys.exit(main())
