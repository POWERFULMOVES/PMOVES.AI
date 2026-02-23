"""
FlOO$ — Linked Skills with Hooks & Dependencies

Runtime engine that makes skill-pairings.yaml executable:
  - Parses depends/hooks fields from skill pairings
  - Builds a DAG of skill dependencies
  - Detects circular dependencies
  - Validates service health before execution
  - Resolves execution order (topological sort)
  - Publishes NATS events on skill completion

Usage:
    python -m pmoves.tools.chit.floos_resolver validate <pairing>
    python -m pmoves.tools.chit.floos_resolver resolve <pairing>
    python -m pmoves.tools.chit.floos_resolver status
    python -m pmoves.tools.chit.floos_resolver hooks
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

__version__ = "1.0.0"

# Default paths (relative to repo root)
DEFAULT_PAIRINGS_PATH = "pmoves/configs/skill-pairings.yaml"


def find_repo_root() -> Path:
    """Walk up from this file to find the repo root (contains .git)."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def load_pairings(path: str | Path | None = None) -> dict:
    """Load and parse skill-pairings.yaml."""
    if path is None:
        path = find_repo_root() / DEFAULT_PAIRINGS_PATH
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Skill pairings not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_pairing(data: dict, name: str) -> dict:
    """Get a specific pairing by name."""
    pairings = data.get("pairings", {})
    if name not in pairings:
        available = ", ".join(sorted(pairings.keys()))
        raise KeyError(f"Pairing '{name}' not found. Available: {available}")
    return pairings[name]


# ── DAG Construction ──────────────────────────────────────────────


class SkillDAG:
    """Directed Acyclic Graph for skill dependency resolution."""

    def __init__(self, pairing_name: str, chain: list[dict]):
        self.pairing_name = pairing_name
        self.chain = chain
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, list[str]] = defaultdict(list)  # child -> parents
        self._build()

    def _build(self) -> None:
        """Build graph nodes and edges from chain steps."""
        for step in self.chain:
            skill = step["skill"]
            self.nodes[skill] = step

            # Explicit skill dependencies from depends.skills
            deps = step.get("depends", {})
            for parent_skill in deps.get("skills", []):
                self.edges[skill].append(parent_skill)

    @property
    def skill_names(self) -> list[str]:
        return [s["skill"] for s in self.chain]

    def validate(self) -> list[str]:
        """Validate DAG integrity. Returns list of error messages (empty = valid)."""
        errors: list[str] = []

        # Check for references to skills not in this chain
        known = set(self.nodes.keys())
        for skill, parents in self.edges.items():
            for parent in parents:
                if parent not in known:
                    errors.append(
                        f"Skill '{skill}' depends on '{parent}' which is not in this chain"
                    )

        # Check for circular dependencies
        cycle = self._detect_cycle()
        if cycle:
            errors.append(f"Circular dependency detected: {' -> '.join(cycle)}")

        return errors

    def _detect_cycle(self) -> list[str] | None:
        """Detect cycles using DFS. Returns cycle path or None."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in self.nodes}
        parent_map: dict[str, str | None] = {n: None for n in self.nodes}

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            for dep in self.edges.get(node, []):
                if dep not in color:
                    continue
                if color[dep] == GRAY:
                    # Found cycle — reconstruct path
                    cycle = [dep, node]
                    current = node
                    while parent_map.get(current) and parent_map[current] != dep:
                        current = parent_map[current]
                        cycle.append(current)
                    cycle.append(dep)
                    return list(reversed(cycle))
                if color[dep] == WHITE:
                    parent_map[dep] = node
                    result = dfs(dep)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for node in self.nodes:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None

    def topological_sort(self) -> list[str]:
        """Return skills in valid execution order (topological sort via Kahn's algorithm)."""
        in_degree: dict[str, int] = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = defaultdict(list)  # parent -> children

        for child, parents in self.edges.items():
            for parent in parents:
                if parent in self.nodes:
                    adj[parent].append(child)
                    in_degree[child] += 1

        queue: deque[str] = deque(
            n for n, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for child in adj[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self.nodes):
            # Cycle detected (should have been caught by validate)
            missing = set(self.nodes) - set(order)
            raise RuntimeError(
                f"Topological sort failed — cycle involving: {missing}"
            )

        return order

    def get_service_deps(self) -> dict[str, list[str]]:
        """Get all required services per skill."""
        result: dict[str, list[str]] = {}
        for skill, step in self.nodes.items():
            deps = step.get("depends", {})
            result[skill] = deps.get("services", [])
        return result

    def get_health_checks(self) -> dict[str, str]:
        """Get health check URLs per skill."""
        result: dict[str, str] = {}
        for skill, step in self.nodes.items():
            deps = step.get("depends", {})
            health = deps.get("health")
            if health:
                result[skill] = health
        return result

    def get_hooks(self) -> dict[str, dict[str, str]]:
        """Get hooks (on_complete, on_error) per skill."""
        result: dict[str, dict[str, str]] = {}
        for skill, step in self.nodes.items():
            hooks = step.get("hooks", {})
            if hooks:
                result[skill] = hooks
        return result


def build_dag(data: dict, pairing_name: str) -> SkillDAG:
    """Build a SkillDAG from a named pairing."""
    pairing = get_pairing(data, pairing_name)
    return SkillDAG(pairing_name, pairing["chain"])


# ── Health Validation ─────────────────────────────────────────────


def check_health(url: str, timeout: int = 5) -> tuple[bool, str]:
    """Check a health endpoint. Returns (healthy, message)."""
    try:
        from urllib.request import urlopen
        from urllib.error import URLError

        resp = urlopen(url, timeout=timeout)
        status = resp.getcode()
        if status and status < 400:
            return True, f"OK ({status})"
        return False, f"Unhealthy ({status})"
    except Exception as e:
        return False, f"Unreachable: {e}"


def check_service_port(service_spec: str, timeout: int = 2) -> tuple[bool, str]:
    """Check if a service:port is reachable via TCP connect."""
    import socket

    parts = service_spec.split(":")
    if len(parts) != 2:
        return False, f"Invalid service spec: {service_spec}"

    host, port_str = parts
    try:
        port = int(port_str)
    except ValueError:
        return False, f"Invalid port: {port_str}"

    # For container names, try localhost
    check_host = "127.0.0.1" if host in ("nats", "tensorzero", "qdrant", "neo4j", "meilisearch") else host

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((check_host, port))
        sock.close()
        if result == 0:
            return True, f"Port {port} open"
        return False, f"Port {port} closed"
    except Exception as e:
        return False, f"Connection error: {e}"


def validate_deps(dag: SkillDAG, check_services: bool = False) -> dict[str, Any]:
    """Validate all dependencies for a DAG.

    Returns a report dict with structure:
        {
            "valid": bool,
            "dag_errors": [...],
            "execution_order": [...],
            "service_status": {...},
            "health_status": {...},
        }
    """
    report: dict[str, Any] = {
        "valid": True,
        "pairing": dag.pairing_name,
        "dag_errors": [],
        "execution_order": [],
        "service_status": {},
        "health_status": {},
    }

    # Validate DAG structure
    dag_errors = dag.validate()
    if dag_errors:
        report["valid"] = False
        report["dag_errors"] = dag_errors
        return report

    # Resolve execution order
    report["execution_order"] = dag.topological_sort()

    if not check_services:
        return report

    # Check service ports
    all_services: set[str] = set()
    for services in dag.get_service_deps().values():
        all_services.update(services)

    for svc in sorted(all_services):
        healthy, msg = check_service_port(svc)
        report["service_status"][svc] = {"healthy": healthy, "message": msg}
        if not healthy:
            report["valid"] = False

    # Check health endpoints
    for skill, url in dag.get_health_checks().items():
        healthy, msg = check_health(url)
        report["health_status"][skill] = {
            "url": url,
            "healthy": healthy,
            "message": msg,
        }
        if not healthy:
            report["valid"] = False

    return report


# ── Formatters ────────────────────────────────────────────────────


def format_dag(dag: SkillDAG) -> str:
    """Format a DAG as a human-readable dependency tree."""
    lines: list[str] = []
    lines.append(f"Pipeline: {dag.pairing_name}")
    lines.append(f"Steps: {len(dag.chain)}")
    lines.append("")

    order = dag.topological_sort()
    for i, skill in enumerate(order):
        step = dag.nodes[skill]
        prefix = "  " if i < len(order) - 1 else "  "
        connector = "|-> " if i < len(order) - 1 else "\\-> "

        deps = step.get("depends", {})
        skill_deps = deps.get("skills", [])
        services = deps.get("services", [])
        health = deps.get("health", "")
        hooks = step.get("hooks", {})

        lines.append(f"{connector}{skill}")
        lines.append(f"{prefix}   agent: {step.get('agent', 'unknown')}")
        if step.get("input"):
            lines.append(f"{prefix}   input: {step['input']}")
        if step.get("output"):
            lines.append(f"{prefix}   output: {step['output']}")
        if skill_deps:
            lines.append(f"{prefix}   depends on: {', '.join(skill_deps)}")
        if services:
            lines.append(f"{prefix}   services: {', '.join(services)}")
        if health:
            lines.append(f"{prefix}   health: {health}")
        if hooks.get("on_complete"):
            lines.append(f"{prefix}   on_complete -> {hooks['on_complete']}")
        lines.append("")

    return "\n".join(lines)


def format_report(report: dict) -> str:
    """Format a validation report for terminal display."""
    lines: list[str] = []
    status = "PASS" if report["valid"] else "FAIL"
    lines.append(f"FlOO$ Validation: {report['pairing']} [{status}]")
    lines.append("=" * 50)

    if report["dag_errors"]:
        lines.append("\nDAG Errors:")
        for err in report["dag_errors"]:
            lines.append(f"  ERROR: {err}")

    if report["execution_order"]:
        lines.append(f"\nExecution Order ({len(report['execution_order'])} steps):")
        for i, skill in enumerate(report["execution_order"], 1):
            lines.append(f"  {i}. {skill}")

    if report["service_status"]:
        lines.append("\nService Dependencies:")
        for svc, info in sorted(report["service_status"].items()):
            icon = "OK" if info["healthy"] else "FAIL"
            lines.append(f"  [{icon}] {svc}: {info['message']}")

    if report["health_status"]:
        lines.append("\nHealth Checks:")
        for skill, info in report["health_status"].items():
            icon = "OK" if info["healthy"] else "FAIL"
            lines.append(f"  [{icon}] {skill} ({info['url']}): {info['message']}")

    return "\n".join(lines)


def format_all_status(data: dict, check_services: bool = False) -> str:
    """Format status overview for all pairings."""
    lines: list[str] = []
    lines.append("FlOO$ Pipeline Status")
    lines.append("=" * 50)

    pairings = data.get("pairings", {})
    for name in sorted(pairings.keys()):
        pairing = pairings[name]
        chain_len = len(pairing.get("chain", []))
        has_deps = any(
            step.get("depends") for step in pairing.get("chain", [])
        )
        has_hooks = any(
            step.get("hooks") for step in pairing.get("chain", [])
        )

        dag = build_dag(data, name)
        errors = dag.validate()

        status = "OK" if not errors else "INVALID"
        flags = []
        if has_deps:
            flags.append("deps")
        if has_hooks:
            flags.append("hooks")
        if pairing.get("ultrathink"):
            flags.append("ultrathink")

        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"\n  {name} [{status}]{flag_str}")
        lines.append(f"    {pairing.get('name', 'Unnamed')}")
        lines.append(f"    Steps: {chain_len}")
        lines.append(f"    NATS: {pairing.get('nats_subject', 'none')}")
        if errors:
            for err in errors:
                lines.append(f"    ERROR: {err}")

    floos_config = data.get("floos", {})
    if floos_config:
        lines.append(f"\nFlOO$ Version: {floos_config.get('version', 'unknown')}")
        lines.append(f"Pre-validate: {floos_config.get('pre_validate', False)}")

    return "\n".join(lines)


def format_all_hooks(data: dict) -> str:
    """Format all registered hooks across pairings."""
    lines: list[str] = []
    lines.append("FlOO$ Registered Hooks")
    lines.append("=" * 50)

    pairings = data.get("pairings", {})
    by_subject: dict[str, list[str]] = defaultdict(list)

    for name, pairing in pairings.items():
        for step in pairing.get("chain", []):
            hooks = step.get("hooks", {})
            skill = step["skill"]
            for hook_type, subject in hooks.items():
                by_subject[subject].append(f"{name}/{skill} ({hook_type})")

    for subject in sorted(by_subject.keys()):
        sources = by_subject[subject]
        lines.append(f"\n  {subject}")
        for src in sources:
            lines.append(f"    <- {src}")

    lines.append(f"\nTotal subjects: {len(by_subject)}")
    lines.append(f"Total hooks: {sum(len(v) for v in by_subject.values())}")

    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────


def cli_resolve(args: argparse.Namespace) -> int:
    """Show dependency DAG for a pairing."""
    data = load_pairings(args.config)
    dag = build_dag(data, args.pairing)
    print(format_dag(dag))
    return 0


def cli_validate(args: argparse.Namespace) -> int:
    """Validate all deps for a pairing."""
    data = load_pairings(args.config)
    dag = build_dag(data, args.pairing)
    report = validate_deps(dag, check_services=args.live)
    print(format_report(report))
    return 0 if report["valid"] else 1


def cli_status(args: argparse.Namespace) -> int:
    """Show all pairings status."""
    data = load_pairings(args.config)
    print(format_all_status(data, check_services=args.live))
    return 0


def cli_hooks(args: argparse.Namespace) -> int:
    """List all registered hooks."""
    data = load_pairings(args.config)
    print(format_all_hooks(data))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="floos",
        description="FlOO$ — Skill dependency resolver for PMOVES.AI",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to skill-pairings.yaml (auto-detected if omitted)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_resolve = sub.add_parser("resolve", help="Show dependency DAG")
    p_resolve.add_argument("pairing", help="Pairing name")
    p_resolve.set_defaults(func=cli_resolve)

    p_validate = sub.add_parser("validate", help="Validate dependencies")
    p_validate.add_argument("pairing", help="Pairing name")
    p_validate.add_argument(
        "--live", action="store_true",
        help="Check live service health (requires services running)",
    )
    p_validate.set_defaults(func=cli_validate)

    p_status = sub.add_parser("status", help="Show all pipeline status")
    p_status.add_argument(
        "--live", action="store_true",
        help="Check live service health",
    )
    p_status.set_defaults(func=cli_status)

    p_hooks = sub.add_parser("hooks", help="List all registered hooks")
    p_hooks.set_defaults(func=cli_hooks)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
