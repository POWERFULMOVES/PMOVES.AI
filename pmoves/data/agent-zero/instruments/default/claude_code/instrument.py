"""
Claude Code CLI Instrument for Agent Zero

Enables Agent Zero to execute Claude Code CLI slash commands for:
- Knowledge retrieval (Hi-RAG, SupaSerch, DeepResearch)
- Service health verification
- Agent coordination
- Deployment operations
- Environment management (BoTZ)

Based on TAC (Tactical Agentic Coding) integration.
"""

import subprocess
import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path


class ClaudeCodeInstrument:
    """Execute Claude Code CLI slash commands from Agent Zero."""

    def __init__(self):
        self.repo_root = Path("/home/pmoves/PMOVES.AI")
        self.commands_dir = self.repo_root / ".claude" / "commands"
        self.context_dir = self.repo_root / ".claude" / "context"
        self.pmoves_dir = self.repo_root / "pmoves"

    def execute_command(
        self,
        command: str,
        prompt: Optional[str] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Execute a Claude Code slash command by parsing and running its implementation.

        Args:
            command: Slash command (e.g., "/search:hirag", "/health:check-all")
            prompt: Optional prompt/query for the command
            timeout: Command timeout in seconds

        Returns:
            Dictionary with output, stderr, exit code, and success status
        """
        # Parse command category and name
        parts = command.lstrip("/").split(":")
        if len(parts) != 2:
            return {
                "success": False,
                "error": f"Invalid command format: {command}. Expected /category:name"
            }

        category, name = parts
        command_file = self.commands_dir / category / f"{name}.md"

        if not command_file.exists():
            return {
                "success": False,
                "error": f"Command not found: {command}",
                "available": self.list_commands()
            }

        # Route to appropriate handler based on category
        handlers = {
            "search": self._execute_search,
            "health": self._execute_health,
            "agents": self._execute_agents,
            "deploy": self._execute_deploy,
            "botz": self._execute_botz
        }

        handler = handlers.get(category)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown command category: {category}"
            }

        return handler(name, prompt, timeout)

    def _execute_search(
        self,
        name: str,
        query: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute search commands."""
        if not query:
            return {"success": False, "error": "Search commands require a query"}

        if name == "hirag":
            # Query Hi-RAG v2
            payload = json.dumps({"query": query, "top_k": 10, "rerank": True})
            cmd = [
                "curl", "-s", "-X", "POST", "http://localhost:8086/hirag/query",
                "-H", "Content-Type: application/json",
                "-d", payload
            ]
        elif name == "supaserch":
            # Query SupaSerch
            payload = json.dumps({"query": query})
            cmd = [
                "curl", "-s", "-X", "POST", "http://localhost:8099/supaserch/query",
                "-H", "Content-Type: application/json",
                "-d", payload
            ]
        elif name == "deepresearch":
            # Publish to NATS for DeepResearch
            payload = json.dumps({"query": query, "requester": "agent-zero"})
            cmd = ["nats", "pub", "research.deepresearch.request.v1", payload]
        else:
            return {"success": False, "error": f"Unknown search command: {name}"}

        return self._run_command(cmd, timeout)

    def _execute_health(
        self,
        name: str,
        query: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute health check commands."""
        if name == "check-all":
            cmd = ["make", "verify-all"]
            return self._run_command(cmd, timeout, cwd=str(self.pmoves_dir))
        elif name == "metrics":
            # Query Prometheus
            promql = query or "up"
            cmd = [
                "curl", "-s", "-G", "http://localhost:9090/api/v1/query",
                "--data-urlencode", f"query={promql}"
            ]
            return self._run_command(cmd, timeout)
        else:
            return {"success": False, "error": f"Unknown health command: {name}"}

    def _execute_agents(
        self,
        name: str,
        prompt: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute agent commands."""
        if name == "status":
            cmd = ["curl", "-s", "http://localhost:8080/healthz"]
        elif name == "mcp-query":
            if not prompt:
                return {"success": False, "error": "MCP query requires a prompt"}
            payload = json.dumps({"query": prompt})
            cmd = [
                "curl", "-s", "-X", "POST", "http://localhost:8080/mcp/query",
                "-H", "Content-Type: application/json",
                "-d", payload
            ]
        else:
            return {"success": False, "error": f"Unknown agents command: {name}"}

        return self._run_command(cmd, timeout)

    def _execute_deploy(
        self,
        name: str,
        prompt: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute deployment commands."""
        if name == "smoke-test":
            cmd = ["bash", "scripts/smoke-tests.sh"]
            return self._run_command(cmd, timeout, cwd=str(self.pmoves_dir))
        elif name == "services":
            cmd = ["docker", "compose", "ps"]
            return self._run_command(cmd, timeout, cwd=str(self.pmoves_dir))
        elif name == "up":
            cmd = ["docker", "compose", "up", "-d"]
            return self._run_command(cmd, timeout, cwd=str(self.pmoves_dir))
        else:
            return {"success": False, "error": f"Unknown deploy command: {name}"}

    def _execute_botz(
        self,
        name: str,
        args: Optional[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute BoTZ commands via Mini CLI."""
        cli_module = "pmoves.tools.mini_cli"

        if name == "init":
            cmd_args = ["init"]
            if args and "--generate" in args:
                cmd_args.append("--generate")
        elif name == "profile":
            if not args:
                return {"success": False, "error": "Profile command requires action (list, show, detect, apply, current)"}
            cmd_args = ["profile"] + args.split()
        elif name == "mcp":
            if not args:
                return {"success": False, "error": "MCP command requires action (list, health, setup)"}
            cmd_args = ["mcp"] + args.split()
        elif name == "secrets":
            if not args:
                return {"success": False, "error": "Secrets command requires action (encode, decode)"}
            cmd_args = ["secrets"] + args.split()
        else:
            return {"success": False, "error": f"Unknown botz command: {name}"}

        cmd = ["python3", "-m", cli_module] + cmd_args
        return self._run_command(cmd, timeout, cwd=str(self.repo_root))

    def _run_command(
        self,
        cmd: List[str],
        timeout: int,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a shell command and return results."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd or str(self.repo_root)
            )

            # Try to parse JSON output
            output = result.stdout
            try:
                parsed = json.loads(output)
                output = parsed
            except json.JSONDecodeError:
                pass

            return {
                "success": result.returncode == 0,
                "output": output,
                "stderr": result.stderr if result.stderr else None,
                "exit_code": result.returncode,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": " ".join(cmd)
            }

    def list_commands(self) -> List[str]:
        """List all available Claude Code slash commands."""
        commands = []
        if not self.commands_dir.exists():
            return commands

        for category_dir in self.commands_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith("."):
                category = category_dir.name
                for cmd_file in category_dir.glob("*.md"):
                    name = cmd_file.stem
                    commands.append(f"/{category}:{name}")

        return sorted(commands)

    def get_command_help(self, command: str) -> Dict[str, Any]:
        """Get help text for a specific command."""
        parts = command.lstrip("/").split(":")
        if len(parts) != 2:
            return {"success": False, "error": "Invalid command format"}

        category, name = parts
        command_file = self.commands_dir / category / f"{name}.md"

        if not command_file.exists():
            return {"success": False, "error": f"Command not found: {command}"}

        return {
            "success": True,
            "command": command,
            "help": command_file.read_text()
        }

    def get_context(self, context_name: str) -> Dict[str, Any]:
        """Read a context documentation file."""
        context_file = self.context_dir / f"{context_name}.md"

        if not context_file.exists():
            available = [f.stem for f in self.context_dir.glob("*.md")]
            return {
                "success": False,
                "error": f"Context not found: {context_name}",
                "available": available
            }

        return {
            "success": True,
            "context": context_name,
            "content": context_file.read_text()
        }

    # Convenience methods for common operations

    def search_hirag(self, query: str) -> Dict[str, Any]:
        """Search Hi-RAG v2 knowledge base."""
        return self.execute_command("/search:hirag", query)

    def search_deepresearch(self, query: str) -> Dict[str, Any]:
        """Initiate DeepResearch query."""
        return self.execute_command("/search:deepresearch", query)

    def check_health(self) -> Dict[str, Any]:
        """Run full health check on all services."""
        return self.execute_command("/health:check-all")

    def get_metrics(self, promql: str = "up") -> Dict[str, Any]:
        """Query Prometheus metrics."""
        return self.execute_command("/health:metrics", promql)

    def agent_status(self) -> Dict[str, Any]:
        """Check Agent Zero health status."""
        return self.execute_command("/agents:status")


# Agent Zero instrument metadata
INSTRUMENT_METADATA = {
    "name": "claude_code",
    "description": "Execute Claude Code CLI slash commands for PMOVES service interaction",
    "version": "1.0.0",
    "author": "PMOVES.AI",
    "requires": ["curl", "nats", "docker"],
    "commands_dir": ".claude/commands/",
    "context_dir": ".claude/context/"
}


# Singleton instance
_instance = None

def get_instrument() -> ClaudeCodeInstrument:
    """Get or create the Claude Code instrument instance."""
    global _instance
    if _instance is None:
        _instance = ClaudeCodeInstrument()
    return _instance
