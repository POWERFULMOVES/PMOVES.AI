"""
FlOO$ — Linked Skills with Hooks & Dependencies

Runtime engine that makes skill-pairings.yaml executable:
  - Parses depends/hooks fields from skill pairings
  - Builds a DAG of skill dependencies
  - Detects circular dependencies
  - Validates service health before execution
  - Resolves execution order (topological sort)
  - Executes skill pipelines end-to-end via MCP
  - Publishes NATS hook events on step/pipeline completion

Usage:
    python -m pmoves.tools.chit.floos_resolver validate <pairing>
    python -m pmoves.tools.chit.floos_resolver resolve <pairing>
    python -m pmoves.tools.chit.floos_resolver status
    python -m pmoves.tools.chit.floos_resolver hooks
    python -m pmoves.tools.chit.floos_resolver run <pairing> [--dry-run] [--context k=v ...]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

__version__ = "2.0.0"

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


# ── Runtime Types ─────────────────────────────────────────────────


@dataclass
class StepResult:
    """Result of executing a single pipeline step."""

    skill: str
    success: bool
    output: Any = None
    duration_s: float = 0.0
    error: str | None = None
    mcp_response: dict | None = None


@dataclass
class PipelineResult:
    """Result of executing a full pipeline."""

    pairing: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    total_duration_s: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── NATS Hook Publisher ───────────────────────────────────────────


def _strict_hooks_enabled() -> bool:
    return os.environ.get("FLOOS_STRICT_HOOKS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _manual_hook_envelope(
    subject: str,
    payload: dict,
    *,
    correlation_id: str | None = None,
    source: str = "floos",
) -> dict:
    env = {
        "id": str(uuid.uuid4()),
        "topic": subject,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "v1",
        "source": source,
        "payload": payload,
    }
    if correlation_id:
        env["correlation_id"] = correlation_id
    return env


def _build_hook_envelope(
    subject: str,
    payload: dict,
    *,
    correlation_id: str | None = None,
    source: str = "floos",
) -> dict:
    """Build a hook envelope, using topics.json validation when registered."""
    try:
        from pmoves.services.common.events import envelope as contract_envelope

        return contract_envelope(
            subject,
            payload,
            correlation_id=correlation_id,
            source=source,
        )
    except KeyError:
        if _strict_hooks_enabled():
            raise
        print(
            f"WARNING: hook '{subject}' is not registered in topics.json; "
            "publishing without schema validation",
            file=sys.stderr,
        )
        return _manual_hook_envelope(
            subject,
            payload,
            correlation_id=correlation_id,
            source=source,
        )


async def publish_hook(
    subject: str,
    payload: dict,
    *,
    correlation_id: str | None = None,
    source: str = "floos",
    nats_url: str | None = None,
) -> dict:
    """Publish a hook event to NATS.

    Registered subjects are validated through topics.json. Unregistered
    convention-based hook subjects warn by default and fail when
    FLOOS_STRICT_HOOKS=true.
    """
    env = _build_hook_envelope(
        subject,
        payload,
        correlation_id=correlation_id,
        source=source,
    )

    url = nats_url or os.environ.get(
        "NATS_URL", "nats://nats:pmoves@nats:4222"
    )

    try:
        from nats.aio.client import Client as NATS

        nc = NATS()
        await nc.connect(servers=[url])
        try:
            await nc.publish(subject, json.dumps(env).encode())
        finally:
            await nc.close()
    except ImportError:
        print(
            f"WARNING: hook '{subject}' not published because nats-py is not installed",
            file=sys.stderr,
        )
    except Exception as exc:
        print(
            f"WARNING: hook '{subject}' publish failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

    return env


# ── Step & Pipeline Execution ─────────────────────────────────────


def _resolve_step_input(step: dict, context: dict[str, Any]) -> dict:
    """Build the arguments dict for a step from the pipeline context."""
    input_ref = step.get("input")
    if not input_ref:
        return {}

    if isinstance(input_ref, str):
        keys = [input_ref]
    elif isinstance(input_ref, list):
        keys = input_ref
    else:
        return {}

    args: dict[str, Any] = {}
    for key in keys:
        if key in context:
            args[key] = context[key]
        else:
            print(
                f"WARNING: step input '{key}' not found in pipeline context",
                file=sys.stderr,
            )
    return args


def _mcp_call(
    endpoint: str, skill: str, arguments: dict, timeout: int = 300
) -> dict:
    """Synchronous HTTP POST to MCP endpoint. Returns parsed JSON response."""
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError

    parsed = urlparse(endpoint)
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError(f"MCP endpoint must be localhost, got: {parsed.hostname}")

    body = json.dumps({"cmd": skill, "arguments": arguments}).encode()
    req = Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urlopen(req, timeout=timeout)
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(
            f"MCP '{skill}' returned HTTP {exc.code}: {error_body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"MCP '{skill}' connection failed: {exc.reason}"
        ) from exc

    raw = resp.read().decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"MCP '{skill}' returned non-JSON: {raw[:200]}"
        ) from exc


async def execute_step(
    step: dict,
    context: dict[str, Any],
    handoff: dict,
    *,
    correlation_id: str | None = None,
) -> StepResult:
    """Execute a single pipeline step via MCP and publish hook events.

    1. Resolves input from context dict
    2. POSTs to MCP endpoint with retry/backoff
    3. On success: publishes on_complete hook, stores output in context
    4. On failure: publishes on_error hook, returns failed StepResult
    """
    skill = step["skill"]
    start = time.monotonic()

    arguments = _resolve_step_input(step, context)
    endpoint = handoff.get("mcp_endpoint", "http://localhost:8080/mcp/command")
    timeout = handoff.get("step_timeout", 300)

    retry_cfg = handoff.get("retry", {})
    max_attempts = retry_cfg.get("max_attempts", 3)
    backoff_ms = retry_cfg.get("backoff_ms", 1000)
    backoff_mult = retry_cfg.get("backoff_multiplier", 2)

    nats_url = handoff.get("nats_url")
    hooks = step.get("hooks", {})
    pairing_name = context.get("__pipeline__", "unknown")

    last_error = ""
    mcp_resp: dict | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            mcp_resp = _mcp_call(endpoint, skill, arguments, timeout=timeout)
            break  # success — exit retry loop
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_attempts:
                wait_s = (backoff_ms / 1000) * (backoff_mult ** (attempt - 1))
                await asyncio.sleep(wait_s)
    else:
        # All attempts exhausted
        duration = time.monotonic() - start

        if hooks.get("on_error"):
            await publish_hook(
                hooks["on_error"],
                {
                    "step": skill,
                    "pipeline": pairing_name,
                    "status": "failed",
                    "duration_s": round(duration, 2),
                    "error": last_error,
                    "correlation_id": correlation_id or "",
                },
                correlation_id=correlation_id,
                nats_url=nats_url,
            )

        return StepResult(
            skill=skill,
            success=False,
            duration_s=round(duration, 2),
            error=last_error,
            mcp_response=mcp_resp,
        )

    # Success processing (outside retry loop)
    duration = time.monotonic() - start
    output_key = step.get("output")
    output_val = mcp_resp.get("result", mcp_resp)

    if output_key:
        context[output_key] = output_val

    # Publish on_complete hook (best-effort)
    if hooks.get("on_complete"):
        await publish_hook(
            hooks["on_complete"],
            {
                "step": skill,
                "pipeline": pairing_name,
                "status": "completed",
                "duration_s": round(duration, 2),
                "output_keys": [output_key] if output_key else [],
                "correlation_id": correlation_id or "",
            },
            correlation_id=correlation_id,
            nats_url=nats_url,
        )

    return StepResult(
        skill=skill,
        success=True,
        output=output_val,
        duration_s=round(duration, 2),
        mcp_response=mcp_resp,
    )


async def execute_pipeline(
    data: dict,
    pairing_name: str,
    *,
    initial_context: dict[str, Any] | None = None,
    check_health: bool = True,
) -> PipelineResult:
    """Execute a full skill pipeline end-to-end.

    1. Builds DAG, validates structure
    2. Optionally checks service health
    3. Executes steps in topological order
    4. Chains step outputs via in-memory context dict
    5. Publishes pipeline completion event on success
    """
    pipeline_start = time.monotonic()
    correlation_id = str(uuid.uuid4())

    # Build and validate
    dag = build_dag(data, pairing_name)
    errors = dag.validate()
    if errors:
        return PipelineResult(
            pairing=pairing_name,
            success=False,
            error=f"DAG validation failed: {'; '.join(errors)}",
        )

    pairing = get_pairing(data, pairing_name)
    handoff = data.get("handoff", {})

    # Health check gate
    if check_health:
        report = validate_deps(dag, check_services=True)
        if not report["valid"]:
            failures = []
            for svc, info in report.get("service_status", {}).items():
                if not info["healthy"]:
                    failures.append(f"{svc}: {info['message']}")
            for skill, info in report.get("health_status", {}).items():
                if not info["healthy"]:
                    failures.append(f"{skill}: {info['message']}")
            return PipelineResult(
                pairing=pairing_name,
                success=False,
                error=f"Health check failed: {'; '.join(failures)}",
            )

    # Execute in topological order
    order = dag.topological_sort()
    context: dict[str, Any] = {"__pipeline__": pairing_name}
    if initial_context:
        context.update(initial_context)

    results: list[StepResult] = []

    for skill_name in order:
        step = dag.nodes[skill_name]
        result = await execute_step(
            step, context, handoff, correlation_id=correlation_id
        )
        results.append(result)

        if not result.success:
            total = time.monotonic() - pipeline_start
            return PipelineResult(
                pairing=pairing_name,
                success=False,
                steps=results,
                total_duration_s=round(total, 2),
                context=context,
                error=f"Step '{skill_name}' failed: {result.error}",
            )

    total = time.monotonic() - pipeline_start

    # Publish pipeline completion (best-effort)
    nats_subject = pairing.get("nats_subject")
    if nats_subject:
        await publish_hook(
            nats_subject,
            {
                "pipeline": pairing_name,
                "status": "completed",
                "steps": len(results),
                "duration_s": round(total, 2),
                "correlation_id": correlation_id,
            },
            correlation_id=correlation_id,
            nats_url=handoff.get("nats_url"),
        )

    return PipelineResult(
        pairing=pairing_name,
        success=True,
        steps=results,
        total_duration_s=round(total, 2),
        context=context,
    )


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
        prefix = "| " if i < len(order) - 1 else "  "
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


def cli_run(args: argparse.Namespace) -> int:
    """Execute a pipeline (or show execution plan with --dry-run)."""
    data = load_pairings(args.config)

    # Parse --context key=value pairs into a dict
    initial_ctx: dict[str, Any] = {}
    for item in args.context or []:
        if "=" not in item:
            print(f"ERROR: Invalid context format '{item}' (expected key=value)")
            return 1
        k, v = item.split("=", 1)
        initial_ctx[k] = v

    if args.dry_run:
        # Dry run: validate, show execution plan, no MCP calls
        dag = build_dag(data, args.pairing)
        errors = dag.validate()
        if errors:
            print(f"FlOO$ Dry Run: {args.pairing} [INVALID]")
            for err in errors:
                print(f"  ERROR: {err}")
            return 1

        order = dag.topological_sort()
        handoff = data.get("handoff", {})
        pairing = get_pairing(data, args.pairing)

        print(f"FlOO$ Dry Run: {args.pairing}")
        print("=" * 50)
        print(f"Pipeline: {pairing.get('name', args.pairing)}")
        print(f"MCP endpoint: {handoff.get('mcp_endpoint', 'http://localhost:8080/mcp/command')}")
        print(f"Step timeout: {handoff.get('step_timeout', 300)}s")
        retry = handoff.get("retry", {})
        print(f"Retry: {retry.get('max_attempts', 3)} attempts, {retry.get('backoff_ms', 1000)}ms backoff")
        if initial_ctx:
            print(f"Initial context: {initial_ctx}")
        print(f"\nExecution Plan ({len(order)} steps):")

        for i, skill in enumerate(order, 1):
            step = dag.nodes[skill]
            print(f"\n  {i}. {skill}")
            print(f"     agent: {step.get('agent', 'unknown')}")
            inp = step.get("input")
            if inp:
                src = f"context[{inp}]" if isinstance(inp, str) else f"context[{inp}]"
                print(f"     input: {src}")
            out = step.get("output")
            if out:
                print(f"     output -> context[{out}]")
            hooks = step.get("hooks", {})
            if hooks.get("on_complete"):
                print(f"     hook(on_complete): {hooks['on_complete']}")
            if hooks.get("on_error"):
                print(f"     hook(on_error): {hooks['on_error']}")

        nats_subj = pairing.get("nats_subject")
        if nats_subj:
            print(f"\nCompletion event: {nats_subj}")
        print("\n[DRY RUN — no MCP calls made]")
        return 0

    # Live execution
    result = asyncio.run(
        execute_pipeline(
            data,
            args.pairing,
            initial_context=initial_ctx or None,
            check_health=not args.skip_health,
        )
    )

    # Format output
    status = "SUCCESS" if result.success else "FAILED"
    print(f"FlOO$ Run: {args.pairing} [{status}]")
    print("=" * 50)

    for sr in result.steps:
        icon = "OK" if sr.success else "FAIL"
        print(f"  [{icon}] {sr.skill} ({sr.duration_s}s)")
        if sr.error:
            print(f"         error: {sr.error}")

    print(f"\nTotal: {result.total_duration_s}s")
    if result.error:
        print(f"Error: {result.error}")

    return 0 if result.success else 1


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

    p_run = sub.add_parser("run", help="Execute a pipeline")
    p_run.add_argument("pairing", help="Pairing name")
    p_run.add_argument(
        "--dry-run", action="store_true",
        help="Show execution plan without making MCP calls",
    )
    p_run.add_argument(
        "--skip-health", action="store_true",
        help="Skip service health checks before execution",
    )
    p_run.add_argument(
        "--context", nargs="*", metavar="KEY=VALUE",
        help="Initial context values (e.g., --context model_id=bert-base)",
    )
    p_run.set_defaults(func=cli_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
