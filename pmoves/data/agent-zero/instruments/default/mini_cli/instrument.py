"""
Mini CLI Instrument for Agent Zero

Enables Agent Zero to execute PMOVES Mini CLI commands for:
- Environment management and secrets handling
- Hardware profile detection and application
- MCP toolkit verification and setup
- Compose stack bring-up and tear-down
- Model bundle management
- Agent delegation (Codex/Crush/ASO)

Based on PMOVES Mini CLI Spec (docs/PMOVES_MINI_CLI_SPEC.md)
"""

import subprocess
import json
from typing import Dict, Any, List, Optional
from pathlib import Path


class MiniCliInstrument:
    """Execute PMOVES Mini CLI commands from Agent Zero."""

    def __init__(self):
        self.repo_root = Path("/home/pmoves/PMOVES.AI")
        self.cli_module = "pmoves.tools.mini_cli"

    def execute(self, command: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute a Mini CLI command.

        Args:
            command: The Mini CLI command (e.g., "init", "profile detect", "bring-up core")
            args: Optional additional arguments

        Returns:
            Dictionary with command output, stderr, exit code, and success status
        """
        cmd_parts = command.split()
        full_args = cmd_parts + (args or [])
        cmd = ["python3", "-m", self.cli_module] + full_args

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=120  # Extended timeout for model operations
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "success": result.returncode == 0,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Command timed out after 120 seconds",
                "exit_code": -1,
                "success": False,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "success": False,
                "command": " ".join(cmd)
            }

    # === Core Commands ===

    def bootstrap(
        self,
        registry: Optional[str] = None,
        service: Optional[List[str]] = None,
        accept_defaults: bool = False,
        output: Optional[str] = None,
        with_glancer: bool = False
    ) -> Dict[str, Any]:
        """Bootstrap env files and stage provisioning bundle."""
        args = []
        if registry:
            args.extend(["--registry", registry])
        if service:
            for s in service:
                args.extend(["--service", s])
        if accept_defaults:
            args.append("--accept-defaults")
        if output:
            args.extend(["--output", output])
        if with_glancer:
            args.append("--with-glancer")
        return self.execute("bootstrap", args)

    def init(self, generate: bool = False, manifest: Optional[str] = None) -> Dict[str, Any]:
        """Run onboarding helper - secrets sync + env generation."""
        args = []
        if generate:
            args.append("--generate")
        if manifest:
            args.extend(["--manifest", manifest])
        return self.execute("init", args)

    def status(self, provisioning_path: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate readiness status (env, MCP, compose, models, Glancer)."""
        args = []
        if provisioning_path:
            args.extend(["--provisioning-path", provisioning_path])
        return self.execute("status", args)

    # === Hardware Profiles ===

    def profile_list(self) -> Dict[str, Any]:
        """List available hardware profiles."""
        return self.execute("profile list")

    def profile_show(self, profile_id: str) -> Dict[str, Any]:
        """Show details for a specific profile including hardware, compose overrides, model bundles."""
        return self.execute("profile show", [profile_id])

    def profile_detect(self, top: int = 3) -> Dict[str, Any]:
        """Inspect hardware and suggest matching profiles."""
        return self.execute("profile detect", ["--top", str(top)])

    def profile_apply(self, profile_id: str) -> Dict[str, Any]:
        """Set active profile (writes to ~/.pmoves/profile.yaml)."""
        return self.execute("profile apply", [profile_id])

    def profile_current(self) -> Dict[str, Any]:
        """Get the currently active profile."""
        return self.execute("profile current")

    # === MCP Toolkit Management ===

    def mcp_list(self) -> Dict[str, Any]:
        """List configured MCP toolkits with availability status."""
        return self.execute("mcp list")

    def mcp_health(self) -> Dict[str, Any]:
        """Run MCP health checks on all configured toolkits."""
        return self.execute("mcp health")

    def mcp_setup(self, tool_id: str) -> Dict[str, Any]:
        """Get setup instructions for an MCP tool."""
        return self.execute("mcp setup", [tool_id])

    # === CHIT Secret Management ===

    def secrets_encode(
        self,
        env_file: Optional[str] = None,
        output: Optional[str] = None,
        no_cleartext: bool = False
    ) -> Dict[str, Any]:
        """Encode env file to CHIT CGP bundle."""
        args = []
        if env_file:
            args.extend(["--env-file", env_file])
        if output:
            args.extend(["--out", output])
        if no_cleartext:
            args.append("--no-cleartext")
        return self.execute("secrets encode", args)

    def secrets_decode(
        self,
        cgp: Optional[str] = None,
        output: Optional[str] = None
    ) -> Dict[str, Any]:
        """Decode CHIT CGP bundle to env format."""
        args = []
        if cgp:
            args.extend(["--cgp", cgp])
        if output:
            args.extend(["--out", output])
        return self.execute("secrets decode", args)

    # === Dependency Management ===

    def deps_check(self) -> Dict[str, Any]:
        """Report whether host dependencies are available."""
        return self.execute("deps check")

    def deps_install(
        self,
        manager: Optional[str] = None,
        assume_yes: bool = False,
        use_container: bool = False,
        container_image: str = "python:3.11-slim"
    ) -> Dict[str, Any]:
        """Install missing dependencies on host or via container."""
        args = []
        if manager:
            args.extend(["--manager", manager])
        if assume_yes:
            args.append("--yes")
        if use_container:
            args.extend(["--use-container", "--container-image", container_image])
        return self.execute("deps install", args)

    # === Automation Management ===

    def automations_list(self) -> Dict[str, Any]:
        """List n8n automations and channels."""
        return self.execute("automations list")

    def automations_webhooks(self) -> Dict[str, Any]:
        """Show webhook endpoints."""
        return self.execute("automations webhooks")

    def automations_channels(self, channel: str) -> Dict[str, Any]:
        """Filter automations by channel keyword."""
        return self.execute("automations channels", [channel])

    # === Tailscale Integration ===

    def tailscale_authkey(
        self,
        env_file: Optional[str] = None,
        secret_file: Optional[str] = None,
        sign: bool = True
    ) -> Dict[str, Any]:
        """Capture a Tailnet auth key (requires interactive input)."""
        args = []
        if env_file:
            args.extend(["--env-file", env_file])
        if secret_file:
            args.extend(["--secret-file", secret_file])
        if not sign:
            args.append("--no-sign")
        return self.execute("tailscale authkey", args)

    def tailscale_join(self, env_file: Optional[str] = None, force_reauth: bool = False) -> Dict[str, Any]:
        """Join the tailnet using pmoves scripts."""
        args = []
        if env_file:
            args.extend(["--env-file", env_file])
        if force_reauth:
            args.append("--force-reauth")
        return self.execute("tailscale join", args)

    def tailscale_rejoin(self, env_file: Optional[str] = None) -> Dict[str, Any]:
        """Force re-auth join to the tailnet."""
        args = []
        if env_file:
            args.extend(["--env-file", env_file])
        return self.execute("tailscale rejoin", args)

    # === Build Tools (Crush) ===

    def crush_setup(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Generate Crush configuration for PMOVES."""
        args = []
        if path:
            args.extend(["--path", path])
        return self.execute("crush setup", args)

    def crush_status(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Show Crush configuration details."""
        args = []
        if path:
            args.extend(["--path", path])
        return self.execute("crush status", args)

    def crush_preview(self) -> Dict[str, Any]:
        """Print generated Crush configuration JSON."""
        return self.execute("crush preview")

    # === Utility Methods ===

    def list_commands(self) -> List[str]:
        """List all available Mini CLI commands."""
        return [
            # Core
            "init", "status", "bootstrap",
            # Profiles
            "profile list", "profile show", "profile detect",
            "profile apply", "profile current",
            # MCP
            "mcp list", "mcp health", "mcp setup",
            # Secrets
            "secrets encode", "secrets decode",
            # Automations
            "automations list", "automations webhooks", "automations channels",
            # Dependencies
            "deps check", "deps install",
            # Tailscale
            "tailscale authkey", "tailscale join", "tailscale rejoin",
            # Crush
            "crush setup", "crush status", "crush preview"
        ]


# Agent Zero instrument metadata
INSTRUMENT_METADATA = {
    "name": "mini_cli",
    "description": "Execute PMOVES Mini CLI commands for environment, hardware, MCP, and secret management",
    "version": "1.0.0",
    "author": "PMOVES.AI",
    "requires": ["python3", "pmoves.tools.mini_cli"],
    "spec": "docs/PMOVES_MINI_CLI_SPEC.md"
}


# Singleton instance
_instance = None

def get_instrument() -> MiniCliInstrument:
    """Get or create the Mini CLI instrument instance."""
    global _instance
    if _instance is None:
        _instance = MiniCliInstrument()
    return _instance
