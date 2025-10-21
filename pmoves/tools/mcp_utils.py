"""MCP toolkit helpers for pmoves mini CLI."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import yaml


MCP_DIR = Path(__file__).resolve().parents[1] / "config" / "mcp"


@dataclass
class MCPTool:
    id: str
    name: str
    required_commands: List[str]
    setup_instructions: List[str]
    health_check: dict


def load_mcp_tools(directory: Path | None = None) -> Dict[str, MCPTool]:
    directory = directory or MCP_DIR
    tools: Dict[str, MCPTool] = {}
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue
        tool = MCPTool(
            id=data["id"],
            name=data.get("name", data["id"]),
            required_commands=data.get("required_commands", []) or [],
            setup_instructions=data.get("setup_instructions", []) or [],
            health_check=data.get("health_check", {}) or {},
        )
        tools[tool.id] = tool
    return tools


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def run_health_check(tool: MCPTool) -> bool:
    command = tool.health_check.get("command")
    if not command:
        return True
    try:
        result = subprocess.run(command, check=False, capture_output=True)
    except FileNotFoundError:
        return False
    return result.returncode == 0
