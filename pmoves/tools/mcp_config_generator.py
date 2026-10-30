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
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pmoves.tools.node_gateway_profile import (  # noqa: E402
    ENV_OVERRIDE as _GATEWAY_PROFILE_VAR,
    resolve as resolve_node_gateway_profile,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PMOVES_DIR = PROJECT_ROOT / "pmoves"
INVENTORY_PATH = PMOVES_DIR / "config" / "mcp_inventory.json"

# Map of client -> default output path relative to repo root
DEFAULT_OUTPUTS = {
    "claude": PROJECT_ROOT / ".claude" / "mcp.json",
    "kimi": PROJECT_ROOT / ".kimi" / "mcp.json",
    "kilocode": PROJECT_ROOT / "kilo.json",
    "opencode": PROJECT_ROOT / ".opencode" / "config.json",
    "hermes": Path.home() / ".hermes" / "profiles" / "pmoves-hermes" / "config.yaml",
    "crush": Path.home() / ".config" / "crush" / "crush.json",
    # MiniMax Code (the Mavis desktop client). The native runtime owns
    # ~/.minimax/mcp.json -- it carries runtime-managed keys (`configured`,
    # `builtin`) and pre-existing entries (composio) that the generator
    # MERGES into rather than replaces.
    "minimax": Path.home() / ".minimax" / "mcp.json",
}

# Client bootstrap profiles (pmoves.bootstrap/v1) that pin the roster for a
# client. When a client has a profile, ONLY the tools the profile declares
# are rendered -- the profile is load-bearing, not documentation. That keeps
# the profile and the generated config diffable against each other: every
# `tools[].key` in the profile must exist in the inventory (fail-closed), and
# every rendered key must be declared in the profile.
#
# Added 2026-10-26 for the MiniMax Code client parity lane.
CLIENT_PROFILES: Dict[str, Path] = {
    "minimax": PROJECT_ROOT / "pmoves" / "configs" / "mavis_collection" / "clients" / "minimax-code.yaml",
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
    endpoint_pinned: bool = False
    disabled: bool = False

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


def _expand(value: str, env: Dict[str, str], *, allow_os_environ: bool = True) -> str:
    """Expand ${VAR} and ${VAR:-default} placeholders.

    Resolution order: explicit ``env`` (from --set) first, then ``os.environ``
    (only when *allow_os_environ* is True).

    When *allow_os_environ* is False (tracked config generation), unresolved
    placeholders are preserved as-is so secret values never leak into
    committed files.
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

        val = env.get(var)
        if not val and allow_os_environ:
            val = os.environ.get(var)
        if val:
            result.append(val)
        elif default:
            if allow_os_environ:
                # Recursively expand default so nested fallbacks resolve.
                result.append(_expand(default, env))
            else:
                # Tracked config: preserve the full ${VAR:-default} placeholder so
                # secrets and local overrides are not committed to the repo.
                result.append(value[start:i])
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
                # client_args replaces args for one client only, so a client can run
                # the same server in a narrower mode without forking the entry.
                args=server.get("client_args", {}).get(client, server.get("args", [])),
                env=server.get("env", {}),
                headers=server.get("headers", {}),
                timeout=server.get("timeout"),
                clients=server.get("clients"),
                endpoint=server.get("endpoint"),
                endpoint_prefix=server.get("endpoint_prefix"),
                endpoint_pinned=server.get("endpoint_pinned", False),
                # disabled_clients emits the entry disabled for those clients only.
                disabled=server.get("disabled", False) or client in server.get("disabled_clients", []),
            )
            if not spec.supports_client(client):
                continue
            # Resolve endpoint-specific URL defaults for groups that define them.
            # The caller's endpoint preference overrides the server's default so
            # the same server key can be rendered for fleet (Tailscale) or local
            # (localhost) consumers without duplicating inventory entries.
            # An entry may instead PIN its endpoint. A pinned entry is not a
            # server rendered at whichever endpoint the caller wants -- it
            # exists to sit alongside its sibling at the other endpoint, so
            # letting the caller rewrite it would collapse the pair into two
            # copies of one URL and silently drop the endpoint it was added for.
            if spec.endpoint_pinned and spec.endpoint:
                target_endpoint = spec.endpoint
            else:
                target_endpoint = endpoint or spec.endpoint
            if target_endpoint and spec.url is None:
                prefix = spec.endpoint_prefix or spec.key.split("-")[0]
                key = f"{prefix}_{target_endpoint}_url"
                if key in defaults:
                    spec.url = defaults[key]
            specs.append(spec)
    return specs


def _render_env(env: Dict[str, str], context: Dict[str, str], **kw: Any) -> Dict[str, str]:
    return {k: _expand(v, context, **kw) for k, v in env.items()}


def _render_headers(headers: Dict[str, str], context: Dict[str, str], **kw: Any) -> Dict[str, str]:
    return {k: _expand(v, context, **kw) for k, v in headers.items()}


def _render_args(args: List[str], context: Dict[str, str], **kw: Any) -> List[str]:
    return [_expand(a, context, **kw) for a in args]


# ---------------------------------------------------------------------------
# Client renderers
# ---------------------------------------------------------------------------


def render_claude_kimi(specs: List[ServerSpec], context: Dict[str, str], **kw: Any) -> Dict[str, Any]:
    """Render mcpServers block for Claude Code / Kimi Code CLI."""
    servers: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.description:
            entry["description"] = spec.description
        if spec.transport in ("sse", "http"):
            entry["type"] = spec.transport
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["command"] = command
            entry["args"] = _render_args(args, context, **kw)
            if spec.env:
                entry["env"] = _render_env(spec.env, context, **kw)
            if spec.timeout:
                entry["timeout"] = spec.timeout
        else:
            continue
        if spec.disabled:
            entry["disabled"] = True
        servers[spec.key] = entry
    return {"mcpServers": servers}


def render_kilocode(specs: List[ServerSpec], context: Dict[str, str], **kw: Any) -> Dict[str, Any]:
    """Render KiloCode mcp + permission blocks."""
    mcp: Dict[str, Any] = {}
    permissions: Dict[str, str] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.transport in ("sse", "http"):
            entry["type"] = "remote"
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "local"
            entry["command"] = [command, *_render_args(args, context, **kw)]
            if spec.env:
                entry["environment"] = _render_env(spec.env, context, **kw)
        else:
            continue
        if spec.disabled:
            # Kilo's MCP schema (McpLocalConfig / McpRemoteConfig at
            # https://app.kilo.ai/config.json) has `enabled`, not `disabled`,
            # and sets additionalProperties false.
            entry["enabled"] = False
        mcp[spec.key] = entry
        permissions[f"{spec.key}_*"] = "allow"
    return {"mcp": mcp, "permission": permissions}


def render_hermes(specs: List[ServerSpec], context: Dict[str, str], **kw: Any) -> Dict[str, Any]:
    """Render Hermes Agent config.yaml mcp_servers block."""
    servers: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {"enabled": not spec.disabled}
        if spec.transport in ("sse", "http"):
            entry["type"] = spec.transport
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "stdio"
            entry["command"] = command
            entry["args"] = _render_args(args, context, **kw)
            if spec.env:
                entry["env"] = _render_env(spec.env, context, **kw)
        else:
            continue
        servers[spec.key] = entry
    return {"mcp_servers": servers}


def render_crush(specs: List[ServerSpec], context: Dict[str, str], **kw: Any) -> Dict[str, Any]:
    """Render Crush CLI crush.json mcp block."""
    mcp: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {}
        if spec.transport == "sse":
            entry["type"] = "sse"
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "http":
            entry["type"] = "http"
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["type"] = "stdio"
            entry["command"] = command
            entry["args"] = _render_args(args, context, **kw)
            if spec.env:
                entry["env"] = _render_env(spec.env, context, **kw)
        else:
            continue
        if spec.timeout:
            entry["timeout"] = spec.timeout
        if spec.disabled:
            entry["disabled"] = True
        mcp[spec.key] = entry
    return {"mcp": mcp}


def _abs_repo_relative(value: Any, root: Optional[Path] = None) -> Any:
    """Absolutize a repo-relative `./`-prefixed path against the repo root.

    THE RULE is identical to pmoves/tools/mcp_roster_normalize.py :: _abs_path
    -- a value that starts with "./" is joined to the repo root, anything else
    is returned untouched. Reusing the rule (rather than inventing one) is the
    point: two places now resolve the same declared path the same way.

    WHY THE MINIMAX RENDERER NEEDS IT (the P2 review finding on #3418).

    MiniMax Code reads its roster from `~/.minimax/mcp.json` -- OUTSIDE the
    repo. Every other client reads a TRACKED roster INSIDE the repo and hands
    it to the binary with `--mcp-config`, so a repo-relative path inside it
    resolves against the repo the client was pointed at.

    The MiniMax launcher resolves ROOT but never cd's there and never
    absolutizes anything, so the inventory's

        uv --directory ./pmoves-nats-mcp run python -m nats_mcp.server

    was resolved against the CALLER's working directory. Launched from
    anywhere but the repo root, the NATS MCP server simply failed to start --
    and the failure mode is a server that is ABSENT, not an error the operator
    could read or act on.

    So the MiniMax renderer absolutizes repo-relative stdio paths against the
    repo root. Two things deliberately do NOT change:

      * The tracked `.claude/mcp.json` keeps `./pmoves-hirag-mcp` relative.
        The other renderers are untouched -- absolutizing a path inside a
        repo-rooted roster would break the contract that roster already has.
      * Expansion order. The path is absolutized BEFORE `${VAR}` expansion,
        matching mcp_roster_normalize.py's P3-then-P4 order, so a value the
        operator supplies at runtime stays their responsibility.
    """
    if not isinstance(value, str) or not value.startswith("./"):
        return value
    return os.path.join(str(root or PROJECT_ROOT), value[2:])


def render_minimax(
    specs: List[ServerSpec],
    context: Dict[str, str],
    *,
    root: Optional[Path] = None,
    **kw: Any,
) -> Dict[str, Any]:
    """Render MiniMax Code mcpServers block (native `~/.minimax/mcp.json`).

    WHY A DEDICATE RENDERER. MiniMax Code (the Mavis desktop client) does
    not read the Claude/Kimi `mcpServers` shape verbatim -- it is close, but
    it carries three extra per-server keys and one different key name:

      * `type`            -- REQUIRED. The Claude renderer omits it (Claude
                             infers from the presence of `url`); MiniMax
                             requires an explicit transport discriminator.
      * `enabled`         -- MiniMax uses `enabled`, not `disabled`. The
                             inventory's `disabled: true` therefore renders
                             as `enabled: false` (same mapping KiloCode
                             already uses for its own schema).
      * `configured`      -- the MiniMax runtime marks a server as
                             "configured" once it has been wired; the merge
                             path preserves the operator's existing value.
      * `builtin`         -- false for PMOVES-owned servers (true only for
                             servers the client ships itself).

    The `type` vocabulary is the MiniMax MCP contract: `stdio` takes
    `command`/`args`/`env`; `http` / `streamable-http` / `sse` take
    `url`/`headers`. stdio and remote fields are never mixed on one entry.

    `root` is the repo root that repo-relative stdio paths resolve against.
    It defaults to this module's own PROJECT_ROOT. See `_abs_repo_relative`
    for why this client -- and only this client -- needs it.
    """
    servers: Dict[str, Any] = {}
    for spec in specs:
        entry: Dict[str, Any] = {
            "type": spec.transport,
            "enabled": not spec.disabled,
            "configured": True,
            "builtin": False,
        }
        if spec.description:
            entry["description"] = spec.description
        if spec.transport in ("sse", "http", "streamable-http"):
            entry["url"] = _expand(spec.url or "", context, **kw)
            if spec.headers:
                entry["headers"] = _render_headers(spec.headers, context, **kw)
        elif spec.transport == "stdio":
            command, args = _split_command_args(spec.command or "", spec.args)
            entry["command"] = _abs_repo_relative(command, root)
            # Absolutize BEFORE expansion -- see _abs_repo_relative.
            abs_args = [_abs_repo_relative(a, root) for a in args]
            entry["args"] = _render_args(abs_args, context, **kw)
            if spec.env:
                entry["env"] = _render_env(spec.env, context, **kw)
        else:
            continue
        if spec.timeout:
            entry["timeout_ms"] = spec.timeout
        servers[spec.key] = entry
    return {"mcpServers": servers}


RENDERERS = {
    "claude": render_claude_kimi,
    "kimi": render_claude_kimi,
    "opencode": render_claude_kimi,
    "kilocode": render_kilocode,
    "hermes": render_hermes,
    "crush": render_crush,
    "minimax": render_minimax,
}

# Renderers that resolve repo-relative paths against the repo root.
#
# WHY ONLY MINIMAX. Every other client reads a TRACKED roster that lives
# INSIDE the repo (`.claude/mcp.json`, `.kimi/mcp.json`, `kilo.json`,
# `.opencode/config.json`, the Hermes profile) and hands it to the binary
# with `--mcp-config`. A repo-relative path inside a repo-rooted roster is
# resolved by the client against the repo -- which is correct, and is what
# `.claude/mcp.json`'s deliberate `./pmoves-hirag-mcp` depends on.
#
# The MiniMax client is the odd one out: it reads `~/.minimax/mcp.json`,
# which lives OUTSIDE the repo, so nothing about it is repo-rooted. Its
# repo-relative stdio paths have to be absolutized at render time or they
# resolve against whatever directory the client happened to be started in.
# See _abs_repo_relative.
ROOT_AWARE_RENDERERS = ("minimax",)

# ---------------------------------------------------------------------------
# Merge / write helpers
# ---------------------------------------------------------------------------

# Keys the MiniMax RUNTIME owns, not the generator.
#
# WHY THIS LIST EXISTS. The renderer docstring (render_minimax) promises:
# "`configured` -- the MiniMax runtime marks a server as 'configured' once it
# has been wired; the merge path preserves the operator's existing value."
# That promise was FALSE until this constant was introduced: the rendered
# overlay always supplied `configured: True` and `builtin: False`, and
# _deep_merge overwrites scalars with the overlay, so a regeneration
# silently reset whatever the runtime had decided.
#
# THE CONSEQUENCE (the bug this fixes). A server the operator had NOT yet
# finished wiring came back marked `configured: true` -- falsely claiming it
# was live. And a server the runtime had marked `builtin: true` came back
# marked `builtin: false` -- stripping a runtime-owned marker. Either way
# the regenerated file disagreed with the runtime's own state.
#
# THE FIX. These keys are supplied by the renderer only for NEW entries.
# On merge, an entry that ALREADY exists in the on-disk config keeps the
# runtime's value verbatim. That is what "the merge path preserves the
# operator's existing value" has to mean for it to be true.
#
# Deliberately NOT a general "preserve these keys" list for every client:
# only MiniMax's runtime owns these names. Claude/Kimi/Kilo have no such
# keys, and inventing a shared mechanism for one client would be a
# workaround, not a fix.
MINIMAX_RUNTIME_MANAGED_KEYS = ("configured", "builtin")


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


def _restore_minimax_runtime_managed(
    existing: Dict[str, Any], rendered: Dict[str, Any]
) -> Dict[str, Any]:
    """Re-apply the MiniMax runtime's own values onto a freshly rendered roster.

    Call this AFTER `_deep_merge`, because the merge is what overwrites them:
    the rendered overlay carries `configured: True` / `builtin: False` for
    every server, and `_deep_merge` lets the overlay win on scalars.

    For each server that ALREADY existed in the on-disk config, the
    runtime-managed keys are copied back from the on-disk value. Servers
    that are NEW in this render keep the renderer's defaults -- there is no
    runtime state for a server the runtime has never seen.

    Returns a NEW dict; the inputs are not mutated.
    """
    existing_servers = existing.get("mcpServers")
    if not isinstance(existing_servers, dict):
        # Nothing to preserve. Return a copy of the render.
        return dict(rendered)

    result = dict(rendered)
    rendered_servers = rendered.get("mcpServers")
    if not isinstance(rendered_servers, dict):
        return result

    merged_servers = dict(rendered_servers)
    for server_key, on_disk in existing_servers.items():
        if not isinstance(on_disk, dict):
            continue
        current = merged_servers.get(server_key)
        if not isinstance(current, dict):
            # The render does not carry this server (it was dropped from
            # the roster). Leave it alone -- do not resurrect it.
            continue
        # COPY the per-server dict before touching it. `merged_servers` holds
        # the SAME dict objects as `rendered`, so assigning into `current`
        # in place would mutate the caller's input -- which this function
        # promises not to do. The copy is written back so the restored
        # values are the ones that land on disk.
        updated = dict(current)
        for managed_key in MINIMAX_RUNTIME_MANAGED_KEYS:
            if managed_key not in on_disk:
                # The runtime has not expressed an opinion about this key
                # on this entry. The renderer's default stands.
                continue
            updated[managed_key] = on_disk[managed_key]
        merged_servers[server_key] = updated

    result["mcpServers"] = merged_servers
    return result


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


def _profile_tool_keys(client: str, profile_path: Optional[Path] = None) -> Optional[List[str]]:
    """Return the tool keys a client's bootstrap profile declares.

    Returns None when the client has no profile (every other client keeps
    the whole-inventory behaviour). Raises MCPConfigError when a declared
    key is missing from the inventory -- fail-closed, because a profile
    that names a server the fleet does not run is a silent broken roster.
    """
    if client not in CLIENT_PROFILES:
        return None
    path = profile_path or CLIENT_PROFILES[client]
    if not path.exists():
        raise MCPConfigError(f"Client profile not found for '{client}': {path}")
    try:
        import yaml  # local import: the generator's core path does not need PyYAML
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise MCPConfigError(
            f"Client profile '{path}' requires PyYAML to read the roster. "
            f"Install pyyaml or pass --no-profile-filter."
        ) from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tools = (data.get("super_nodes") or {}).get("tools") or []
    keys: List[str] = []
    for entry in tools:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if key:
            keys.append(key)
    if not keys:
        raise MCPConfigError(
            f"Client profile '{path}' declares no tools[].key entries -- "
            f"refusing to render an empty roster for '{client}'."
        )
    return keys


def generate_for_client(
    client: str,
    *,
    inventory: Optional[Dict[str, Any]] = None,
    endpoint: str = "fleet",
    context: Optional[Dict[str, str]] = None,
    allow_os_environ: bool = True,
    profile_path: Optional[Path] = None,
    use_profile: bool = True,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    inventory = inventory or load_inventory()
    context = context or {}
    if client not in RENDERERS:
        raise MCPConfigError(f"Unknown client: {client}")
    specs = _collect_servers(inventory, client, endpoint)
    if use_profile:
        declared = _profile_tool_keys(client, profile_path)
        if declared is not None:
            by_key = {spec.key: spec for spec in specs}
            missing = [k for k in declared if k not in by_key]
            if missing:
                raise MCPConfigError(
                    f"Client profile for '{client}' declares tool keys that the "
                    f"inventory does not resolve for this client/endpoint: "
                    f"{', '.join(missing)}. Either the inventory entry is "
                    f"missing, is allowlisted to other clients only, or the "
                    f"endpoint mode ({endpoint}) excludes it."
                )
            specs = [by_key[k] for k in declared]
    # Only the MiniMax renderer resolves repo-relative paths, because only the
    # MiniMax client reads its roster from OUTSIDE the repo. See
    # _abs_repo_relative for the whole argument; the short form is that the
    # other clients read a repo-rooted roster and would be BROKEN by it.
    extra: Dict[str, Any] = {}
    if root is not None and client in ROOT_AWARE_RENDERERS:
        extra["root"] = root
    return RENDERERS[client](specs, context, allow_os_environ=allow_os_environ, **extra)


def write_client_config(
    client: str,
    output_path: Path,
    *,
    merge: bool = True,
    inventory: Optional[Dict[str, Any]] = None,
    endpoint: str = "fleet",
    context: Optional[Dict[str, str]] = None,
    allow_os_environ: bool = True,
    profile_path: Optional[Path] = None,
    use_profile: bool = True,
    root: Optional[Path] = None,
) -> Path:
    """Generate and write config for a single client.

    For JSON clients (Claude, Kimi, KiloCode, Crush, MiniMax) the output is merged with
    the existing file when merge=True. For Hermes, a YAML mcp_servers snippet
    is printed to stdout; callers are responsible for injecting it into the
    Hermes config.yaml because YAML round-tripping is left to the Hermes
    bootstrap script.

    `root` is the repo root that repo-relative stdio paths resolve against,
    for the clients that need it (ROOT_AWARE_RENDERERS). It defaults to the
    generator's own PROJECT_ROOT.
    """
    rendered = generate_for_client(client, inventory=inventory, endpoint=endpoint, context=context,
                                   allow_os_environ=allow_os_environ, profile_path=profile_path,
                                   use_profile=use_profile, root=root)

    if client == "hermes":
        # Hermes is YAML; write a snippet file for the bootstrap script to merge.
        # NEVER overwrite the real config.yaml directly.
        snippet_path = output_path.with_suffix(".mcp_snippet.json") if output_path.suffix == ".yaml" else output_path
        snippet_path.parent.mkdir(parents=True, exist_ok=True)
        snippet_path.write_text(
            "# PMOVES MCP servers (auto-generated by mcp_config_generator.py)\n"
            "# Merge this into your Hermes config.yaml under the top-level `mcp_servers:` key.\n"
            + json.dumps(rendered, indent=2),
            encoding="utf-8",
        )
        return snippet_path

    if merge:
        _backup_once(output_path)
        existing = _load_json_or_empty(output_path)
        final = _deep_merge(existing, rendered)
        if client == "minimax":
            # The rendered overlay carries `configured: True` /
            # `builtin: False` for every server, and _deep_merge lets the
            # overlay win on scalars -- so the merge is exactly what
            # clobbers the runtime's own values. Restore them AFTER the
            # merge. See MINIMAX_RUNTIME_MANAGED_KEYS.
            final = _restore_minimax_runtime_managed(existing, final)
    else:
        final = rendered

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    # Owner-only on POSIX.
    #
    # WHY NOW (2026-10-26). A rendered config CAN hold expanded secrets --
    # the agent-zero MCP token rides in the URL PATH, and the cipher +
    # flute headers carry API keys. For the tracked repo configs the
    # placeholders are preserved (allow_os_environ=False), so those files
    # stay secret-free. But a LIVE per-node config (the MiniMax client's
    # ~/.minimax/mcp.json, the Hermes profile) is written with the values
    # expanded, and the default umask would leave it world-readable.
    #
    # This is a no-op on Windows (no POSIX mode bits); the mode is still
    # applied when the same generator runs on a Linux fleet node.
    try:
        os.chmod(output_path, 0o600)
    except (OSError, NotImplementedError):  # pragma: no cover - platform guard
        pass
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
    parser.add_argument(
        "--client-profile",
        type=Path,
        default=None,
        help=(
            "Path to a pmoves.bootstrap/v1 client profile that pins the roster "
            f"for a client. Defaults to the profile registered for that client "
            f"({', '.join(sorted(CLIENT_PROFILES)) or 'none'})."
        ),
    )
    parser.add_argument(
        "--no-profile-filter",
        action="store_true",
        help=(
            "Render the whole inventory for the client instead of the roster its "
            "bootstrap profile declares."
        ),
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

    # Seed THIS NODE's Docker MCP gateway profile.
    #
    # The inventory carries ${PMOVES_MCP_PROFILE_ID} rather than a profile name
    # because there is no fleet-wide one: it used to hold the literal
    # `pmoves_5090_web`, so every node rendered a config that launched the
    # 5090's gateway. Seeding the CONTEXT rather than special-casing the
    # gateway's server key keeps this in the expansion path every other value
    # already uses -- no key-specific branch to keep in sync with the inventory.
    #
    # setdefault, so an explicit `--set PMOVES_MCP_PROFILE_ID=...` still wins;
    # _expand also consults os.environ, but only for clients that allow it, and
    # the placeholder has to resolve for the tracked ones too.
    if _GATEWAY_PROFILE_VAR not in context:
        resolved, why = resolve_node_gateway_profile()
        if resolved:
            context[_GATEWAY_PROFILE_VAR] = resolved
        else:
            # Loud, and specific about the consequence. Silently emitting a
            # literal `${PMOVES_MCP_PROFILE_ID}` into a client config is the
            # kind of well-formed-but-dead entry this generator exists to avoid.
            print(
                f"WARNING: {_GATEWAY_PROFILE_VAR} unresolved ({why}); the Docker MCP "
                f"gateway entry will keep the literal placeholder and will not start. "
                f"Pass --set {_GATEWAY_PROFILE_VAR}=<profile> or declare "
                f"docker_mcp.gateway_profile in this node's pmoves/config/profiles/<id>.yaml.",
                file=sys.stderr,
            )

    clients = list(RENDERERS.keys()) if args.client == "all" else [args.client]

    # Reject --client all with a single --output: each client would overwrite
    # the same file, leaving only the last client's config.
    if args.client == "all" and args.output and not args.output_dir:
        print("ERROR: --client all requires --output-dir, not --output "
              "(clients would overwrite each other)", file=sys.stderr)
        return 2

    # Determine whether this is a tracked-config write (repo-relative paths).
    # Tracked configs must preserve ${VAR} placeholders, never expand secrets.
    tracked_clients = {"claude", "kimi", "kilocode", "opencode"}

    for client in clients:
        output = args.output
        if output is None:
            if args.client == "all" and args.output_dir:
                output = args.output_dir / f"mcp.{client}.json"
            else:
                output = DEFAULT_OUTPUTS[client]

        is_tracked = client in tracked_clients and output.is_relative_to(PROJECT_ROOT)
        rendered = generate_for_client(
            client, inventory=inventory, endpoint=args.endpoint, context=context,
            allow_os_environ=not is_tracked,
            profile_path=args.client_profile,
            use_profile=not args.no_profile_filter,
        )

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
            allow_os_environ=not is_tracked,
            profile_path=args.client_profile,
            use_profile=not args.no_profile_filter,
        )
        print(f"OK Wrote {client} MCP config to {written}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
