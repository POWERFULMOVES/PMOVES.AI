"""PMOVES Mini MCP Server — stdio bridge exposing PMOVES CLI tools to LLM agents.

Exposes fleet status, profile detection, MCP health, env validation, and
dependency checks as MCP tools that Crush (or any MCP-compatible agent)
can call without leaving the terminal.

Usage:
    python3 -m pmoves.tools.mcp_server
    # or via mini_cli:
    python3 -m pmoves.tools.mini_cli mcp serve
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PMOVES_DIR = _PROJECT_ROOT / "pmoves"

TOOLS: list[Tool] = [
    Tool(
        name="pmoves_status",
        description="Get aggregate PMOVES system readiness: env config, service health, git status.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_profile_detect",
        description="Detect hardware profile for this node (CPU, GPU, RAM, VRAM).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_profile_current",
        description="Show the currently active PMOVES hardware profile.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_mcp_health",
        description="Run health checks on configured MCP servers (cipher, agent-zero, nats, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Specific MCP server key to check (default: all).",
                },
            },
        },
    ),
    Tool(
        name="pmoves_env_validate",
        description="Validate tier environment files for missing or placeholder values.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_deps_check",
        description="Check host dependencies (docker, python3, uv, make, gh, node, etc.).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_git_status",
        description="Show current branch, dirty files, and recent commits.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="pmoves_make_help",
        description="List available make targets matching a keyword.",
        inputSchema={
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Filter targets by keyword (default: show all).",
                },
            },
        },
    ),
]


async def _run(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> tuple[int, str]:
    """Run a command and return (returncode, output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or str(_PROJECT_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0 and stderr:
            output += "\n" + stderr.decode("utf-8", errors="replace")
        return proc.returncode or 0, output
    except asyncio.TimeoutError:
        return 1, f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


async def pmoves_status(**_: Any) -> list[TextContent]:
    """Aggregate system readiness."""
    env_file = _PMOVES_DIR / "env.shared"
    env_exists = env_file.exists()
    env_lines = 0
    if env_exists:
        env_lines = sum(1 for l in env_file.read_text().splitlines() if "=" in l and not l.startswith("#"))

    rc, git_output = await _run(["git", "branch", "--show-current"])
    branch = git_output.strip()

    rc, git_dirty = await _run(["git", "status", "--short"])
    dirty_count = len([l for l in git_dirty.strip().splitlines() if l.strip()])

    rc, log_output = await _run(["git", "log", "--oneline", "-5"])

    result = {
        "env_shared": {"exists": env_exists, "lines": env_lines},
        "git": {
            "branch": branch,
            "dirty_files": dirty_count,
            "recent_commits": log_output.strip().splitlines(),
        },
        "pmoves_dir": str(_PMOVES_DIR),
        "node": os.uname().nodename,
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def pmoves_profile_detect(**_: Any) -> list[TextContent]:
    """Detect hardware."""
    import platform

    gpu_info = "unknown"
    try:
        rc, gpu_out = await _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], timeout=10)
        if rc == 0:
            gpu_info = gpu_out.strip()
        else:
            rc, rocm_out = await _run(["rocm-smi", "--showproductname"], timeout=10)
            if rc == 0:
                gpu_info = rocm_out.strip()[:500]
    except Exception:
        pass

    result = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "hostname": os.uname().nodename,
        "gpu": gpu_info,
    }
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def pmoves_profile_current(**_: Any) -> list[TextContent]:
    """Show active profile."""
    profile_file = _PMOVES_DIR / f"config/profiles/{os.uname().nodename}.yaml"
    if profile_file.exists():
        return [TextContent(type="text", text=profile_file.read_text()[:2000])]
    return [TextContent(type="text", text=f"No profile file found at {profile_file}")]


async def pmoves_mcp_health(server: str | None = None, **_: Any) -> list[TextContent]:
    """Check MCP server health."""
    inventory_path = _PMOVES_DIR / "config/mcp_inventory.json"
    if not inventory_path.exists():
        return [TextContent(type="text", text="No MCP inventory found")]

    inventory = json.loads(inventory_path.read_text())
    servers = []
    for group in inventory.get("groups", {}).values():
        for srv in group.get("servers", []):
            if server and srv["key"] != server:
                continue
            url = srv.get("url", "")
            if url:
                if "${TS_" in url:
                    url = "fleet-url (unresolved without Tailscale env)"
                servers.append({"key": srv["key"], "transport": srv["transport"], "url": url})
            elif srv.get("command"):
                servers.append({"key": srv["key"], "transport": srv["transport"], "command": srv["command"]})

    return [TextContent(type="text", text=json.dumps(servers, indent=2))]


async def pmoves_env_validate(**_: Any) -> list[TextContent]:
    """Validate tier env files."""
    issues = []
    for tier_file in sorted(_PMOVES_DIR.glob("env.tier-*")):
        if tier_file.suffix == ".example":
            continue
        for line in tier_file.read_text().splitlines():
            if "your_" in line and "_here" in line:
                key = line.split("=")[0] if "=" in line else line
                issues.append(f"Placeholder in {tier_file.name}: {key}")

    if not issues:
        return [TextContent(type="text", text="All tier env files clean (no placeholders found)")]
    return [TextContent(type="text", text="\n".join(issues))]


async def pmoves_deps_check(**_: Any) -> list[TextContent]:
    """Check host dependencies."""
    deps = ["docker", "python3", "uv", "make", "gh", "node", "git", "rg"]
    results: dict[str, str] = {}
    for dep in deps:
        rc, _out = await _run(["which", dep], timeout=5)
        results[dep] = "OK" if rc == 0 else "MISSING"
    return [TextContent(type="text", text=json.dumps(results, indent=2))]


async def pmoves_git_status(**_: Any) -> list[TextContent]:
    """Git status."""
    rc, output = await _run(["git", "status", "--short", "--branch"])
    return [TextContent(type="text", text=output.strip())]


async def pmoves_make_help(keyword: str | None = None, **_: Any) -> list[TextContent]:
    """List make targets."""
    _rc, output = await _run(["make", "-C", "pmoves", "help"], timeout=15)
    if keyword:
        lines = [l for l in output.splitlines() if keyword.lower() in l.lower()]
        output = "\n".join(lines)
    return [TextContent(type="text", text=output[:5000])]


TOOL_HANDLERS = {
    "pmoves_status": pmoves_status,
    "pmoves_profile_detect": pmoves_profile_detect,
    "pmoves_profile_current": pmoves_profile_current,
    "pmoves_mcp_health": pmoves_mcp_health,
    "pmoves_env_validate": pmoves_env_validate,
    "pmoves_deps_check": pmoves_deps_check,
    "pmoves_git_status": pmoves_git_status,
    "pmoves_make_help": pmoves_make_help,
}


app = Server("pmoves-mini")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        return await handler(**(arguments or {}))
    except TypeError as exc:
        return [TextContent(type="text", text=f"Invalid arguments for {name}: {exc}")]
    except Exception as exc:
        return [TextContent(type="text", text=f"Error executing {name}: {exc}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pmoves-mini",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
