"""Generate PMOVES MCP server configs for every supported agent stack.

Reads pmoves/config/mcp_inventory.json and emits client-native snippets for:
  - Claude Code / Kimi Code CLI  ->  mcp.json  (mcpServers)
  - KiloCode                    ->  kilo.json fragment (mcp + permission)
  - Hermes Agent                ->  Hermes config.yaml mcp_servers block
  - Crush CLI                   ->  crush.json mcp block

The generator is idempotent and safe to run from any bootstrap path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = PROJECT_ROOT / "pmoves"
INVENTORY_PATH = PMOVES_DIR / "config" / "mcp_inventory.json"

# Map of client -> default output path relative to repo root
DEFAULT_OUTPUTS = {
    "claude": PROJECT_ROOT / ".claude" / "mcp.json",
    "kimi": PROJECT_ROOT / ".kimi" / "mcp.json",
    "kilocode": PROJECT_ROOT / "kilo.json",
    "hermes": Path.home() / ".hermes" / "profiles" / "pmoves-hermes" / "config.yaml",
    "crush": Path.home() / ".config" / "crush" / "crush.json",
}


class MCPConfigError(Exception):
    pass


@dataclass
class ServerSpec:
    key: str
    description: str
    transport: str
    url: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[int] = None
    clients: Optional[List[str]] = None
    endpoint: Optional[str] = None
    endpoint_prefix: Optional[str] = None

    def supports_client(self, client: str) -> bool:
        if self.clients is None:
            return True
        return client in self.clients


def load_inventory(path: Optional[Path] = None) -> Dict[str, Any]:
    path = path or INVENTORY_PATH
    if not path.exists():
        raise MCPConfigError(f"MCP inventory not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise MCPConfigError(f"Unsupported inventory version: {data.get('version')}")
    return data


def _expand(value: str, env: Dict[str, str]) -> str:
    """Expand ${VAR} and ${VAR:-default} placeholders from env then os.environ.

    Supports nested default expressions such as ${VAR:-${OTHER:-fallback}}.
    """
    result: List[str] = []
    i = 0
    while i < len(value):
        if value[i] != "$" or i + 1 >= len(value) or value[i + 1] != "{":
            result.append(value[i])
            i += 1
            continue

        # Find matching closing brace, honoring nesting.
        start = i
        depth = 1
        i += 2
        while i < len(value) and depth > 0:
            if value[i] == "{":
                depth += 1
            elif value[i] == "}":
                depth -= 1
            i += 1
        inner = value[start + 2 : i - 1]

        # Split var from :-default.
        colon_dash = inner.find(":-")
        if colon_dash >= 0:
            var = inner[:colon_dash]
            default = inner[colon_dash + 2 :]
        else:
            var = inner
            default = ""

        val = env.get(var) or os.environ.get(var)
        if val:
            result.append(val)
        elif default:
            # Recursively expand default so nested fallbacks resolve.
            result.append(_expand(default, env))
        else:
            result.append(value[start:i])

    return "".join(result)


def _split_command_args(command: str, args: List[str]) -> Tuple[str, List[str]]:
    """Return executable + args.

    Commands are kept as declared (npx, uv, docker, etc.) so generated configs
    remain portable across nodes and merge cleanly with existing hand-written
    entries that use the same short names.
    """
    return command, list(args)


def _collect_servers(inventory: Dict[str, Any], client: str, endpoint: str) -> List[ServerSpec]:
    specs: List[ServerSpec] = []
    defaults = inventory.get("defaults", {})

    for group in inventory.get("groups", {}).values():
        for server in group.get("servers", []):
            spec = ServerSpec(
                key=server["key"],
                description=server.get("description", ""),
                transport=server["transport"],
                url=server.get("url"),
                command=server.get("command"),
                args=server.get("args", []),
                env=server.get("env", {}),
                headers=server.get("headers", {}),
                timeout=server.get("timeout"),
                clients=server.get("clients"),
                endpoint=server.get("endpoint"),
                endpoint_prefix=server.get("endpoint_prefix"),
            )
            if not spec.supports_client(client):
                continue
            # Resolve endpoint-specific URL defaults for groups that define them.
            # The caller's endpoint preference overrides the server's default so
            # the same server key can be rendered for fleet (Tailscale) or local
            # (localhost) consumers without duplicating inventory entries.
            target_endpoint = endpoint or spec.endpoint
            if target_endpoint and spec.url is None:
                prefix = spec.endpoint_prefix or spec.key.split("-")[0]
                key = f"{prefix}_{target_endpoint}_url"
                if key in defaults:
                    spec.url = defaults[key]
            specs.append(spec)
    return specs


def _render_env(env: Dict[str, str], context: Dict[str, str]) -> Dict[str, str]:
    return {k: _expand(v, context) for k, v in env.items()}


def _render_headers(headers: Dict[str, str], context: Dict[str, str]) -> Dict[str, str]:
    return {k: _expand(v, context) for k, v in headers.items()}


def _render_args(args: List[str], context: Dict[str, str]) -> List[str]:
    return [_expand(a, context) for a in args]


# ---------------------------------------------------------------------------
# Client renderers
# ---------------------------------------------------------------------------


def render_claude_kimi(specs: List[ServerSpec], context: Dict[str, str]) -> Dict[str, Any]:
    """Render mcpServers block for Claude Code / Kimi Code CLI."""
    servers: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.description:
            entry["description"] = spec.description
        if spec.transport in ("sse", "http"):
            entry["type"] = spec.transport
            entry["url"] = _expand(spec.url or "", context)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["command"] = command
            entry["args"] = _render_args(args, context)
            if spec.env:
                entry["env"] = _render_env(spec.env, context)
            if spec.timeout:
                entry["timeout"] = spec.timeout
        else:
            continue
        servers[spec.key] = entry
    return {"mcpServers": servers}


def render_kilocode(specs: List[ServerSpec], context: Dict[str, str]) -> Dict[str, Any]:
    """Render KiloCode mcp + permission blocks."""
    mcp: Dict[str, Any] = {}
    permissions: Dict[str, str] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.transport in ("sse", "http"):
            entry["type"] = "remote"
            entry["url"] = _expand(spec.url or "", context)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "local"
            entry["command"] = [command, *_render_args(args, context)]
            if spec.env:
                entry["environment"] = _render_env(spec.env, context)
        else:
            continue
        mcp[spec.key] = entry
        permissions[f"{spec.key}_*"] = "allow"
    return {"mcp": mcp, "permission": permissions}


def render_hermes(specs: List[ServerSpec], context: Dict[str, str]) -> Dict[str, Any]:
    """Render Hermes Agent config.yaml mcp_servers block."""
    servers: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {"enabled": True}
        if spec.transport in ("sse", "http"):
            entry["type"] = spec.transport
            entry["url"] = _expand(spec.url or "", context)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "stdio"
            entry["command"] = command
            entry["args"] = _render_args(args, context)
            if spec.env:
                entry["env"] = _render_env(spec.env, context)
        else:
            continue
        servers[spec.key] = entry
    return {"mcp_servers": servers}


def render_crush(specs: List[ServerSpec], context: Dict[str, str]) -> Dict[str, Any]:
    """Render Crush CLI crush.json mcp block."""
    mcp: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.transport == "sse":
            entry["type"] = "sse"
            entry["url"] = _expand(spec.url or "", context)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context)
        elif spec.transport == "http":
            entry["type"] = "http"
            entry["url"] = _expand(spec.url or "", context)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "stdio"
            entry["command"] = command
            entry["args"] = _render_args(args, context)
        else:
            continue
        if spec.timeout:
            entry["timeout"] = spec.timeout
        mcp[spec.key] = entry
    return {"mcp": mcp}


RENDERERS = {
    "claude": render_claude_kimi,
    "kimi": render_claude_kimi,
    "opencode": render_claude_kimi,
    "kilocode": render_kilocode,
    "hermes": render_hermes,
    "crush": render_crush,
}


# ---------------------------------------------------------------------------
# Merge / write helpers
# ---------------------------------------------------------------------------


def _deep_merge(base: Any, overlay: Any, *, _key: Optional[str] = None) -> Any:
    """Recursively merge overlay into base.

    Dicts are merged. For lists, the merge behavior depends on context:
    - 'args' values are ordered command-line arguments: overlay replaces base.
    - Other lists are concatenated with duplicates removed.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = dict(base)
        for key, value in overlay.items():
            result[key] = _deep_merge(result.get(key), value, _key=key)
        return result
    if isinstance(base, list) and isinstance(overlay, list):
        if _key == "args":
            return list(overlay)
        return list(base) + [item for item in overlay if item not in base]
    return overlay


def _load_json_or_empty(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MCPConfigError(f"Invalid JSON in {path}: {exc}")


def _backup_once(path: Path) -> None:
    backup = Path(str(path) + ".pre-mcp-bootstrap.bak")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)


def generate_for_client(
    client: str,
    *,
    inventory: Optional[Dict[str, Any]] = None,
    endpoint: str = "fleet",
    context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    inventory = inventory or load_inventory()
    context = context or {}
    if client not in RENDERERS:
        raise MCPConfigError(f"Unknown client: {client}")
    specs = _collect_servers(inventory, client, endpoint)
    return RENDERERS[client](specs, context)


def write_client_config(
    client: str,
    output_path: Path,
    *,
    merge: bool = True,
    inventory: Optional[Dict[str, Any]] = None,
    endpoint: str = "fleet",
    context: Optional[Dict[str, str]] = None,
) -> Path:
    """Generate and write config for a single client.

    For JSON clients (Claude, Kimi, KiloCode, Crush) the output is merged with
    the existing file when merge=True. For Hermes, a YAML mcp_servers snippet
    is printed to stdout; callers are responsible for injecting it into the
    Hermes config.yaml because YAML round-tripping is left to the Hermes
    bootstrap script.
    """
    rendered = generate_for_client(client, inventory=inventory, endpoint=endpoint, context=context)

    if client == "hermes":
        # Hermes is YAML; return the rendered snippet and let the bootstrap
        # script merge it surgically. We do not overwrite the whole YAML file.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            f"# PMOVES MCP servers (auto-generated by mcp_config_generator.py)\n"
            f"# Merge this into your Hermes config.yaml under the top-level `mcp_servers:` key.\n"
            + json.dumps(rendered, indent=2),
            encoding="utf-8",
        )
        return output_path

    if merge:
        _backup_once(output_path)
        existing = _load_json_or_empty(output_path)
        final = _deep_merge(existing, rendered)
    else:
        final = rendered

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    return output_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate PMOVES MCP configs for agent stacks."
    )
    parser.add_argument(
        "--client",
        choices=list(RENDERERS.keys()) + ["all"],
        required=True,
        help="Target agent stack (or 'all').",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: client-specific known path).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="When --client=all, write each client config into this directory.",
    )
    parser.add_argument(
        "--endpoint",
        choices=["local", "fleet"],
        default="fleet",
        help="Prefer local URLs (localhost) or fleet URLs (Tailscale) where applicable.",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Overwrite the output file instead of merging with existing config.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=INVENTORY_PATH,
        help="Path to mcp_inventory.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rendered config to stdout instead of writing files.",
    )
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        default=[],
        help="Override context variable for ${...} expansion (can be repeated).",
    )
    args = parser.parse_args(argv)

    inventory = load_inventory(args.inventory)
    context: Dict[str, str] = {}
    for item in args.set:
        if "=" not in item:
            print(f"ERROR: --set expects KEY=VALUE, got: {item}", file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        context[k] = v

    clients = list(RENDERERS.keys()) if args.client == "all" else [args.client]

    for client in clients:
        output = args.output
        if output is None:
            if args.client == "all" and args.output_dir:
                output = args.output_dir / f"mcp.{client}.json"
            else:
                output = DEFAULT_OUTPUTS[client]

        rendered = generate_for_client(client, inventory=inventory, endpoint=args.endpoint, context=context)

        if args.dry_run:
            print(f"# --- {client} -> {output} ---")
            print(json.dumps(rendered, indent=2))
            continue

        written = write_client_config(
            client,
            output,
            merge=not args.no_merge,
            inventory=inventory,
            endpoint=args.endpoint,
            context=context,
        )
        print(f"OK Wrote {client} MCP config to {written}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
