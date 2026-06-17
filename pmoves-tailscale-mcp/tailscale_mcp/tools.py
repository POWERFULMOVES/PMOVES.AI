"""MCP tool definitions + handlers for the PMOVES Tailscale bridge.

A thin wrapper over the local `tailscale` CLI (Integration Rule: leverage, don't
duplicate). Gives agents/skills durable control of the tailnet from the node they run
on — **no `TAILSCALE_API_KEY` needed** (that's the complementary admin-API path).

  | this MCP (local CLI)                 | the npm `tailscale-mcp` (admin API)     |
  |--------------------------------------|------------------------------------------|
  | node-local control + diagnostics     | tailnet-wide admin (ACL, devices)        |
  | exit-node use, serve, funnel, ssh,   | approve routes, manage keys, edit ACL,   |
  | metrics, status, netcheck, ping      | tag devices, delete stale nodes          |
  | no creds (uses the joined daemon)    | needs TAILSCALE_API_KEY + TAILSCALE_TAILNET |

Integration seams this unlocks:
  - `ts_serve`   → expose Jellyfin (:8096) / Pinokio apps to the tailnet over auto-TLS
  - `ts_funnel`  → public ingress (443/8443/10000) without port-forward
  - `ts_metrics` → tailscaled Prometheus metrics for the observability stack
  - `ts_ssh`     → run commands on fleet nodes over the tailnet (bypasses blocked port-22)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from typing import Any

from mcp.types import TextContent, Tool

DEFAULT_TIMEOUT = 30.0

# Validate hostnames before handing them to the shell-free CLI (defense-in-depth even
# though we never use a shell). Starts alnum; alnum/dot/hyphen after.
_SAFE_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def _ts_bin() -> str:
    """Resolve the tailscale binary: TAILSCALE_BIN override → PATH → common Windows path."""
    override = os.environ.get("TAILSCALE_BIN")
    if override:
        return override
    found = shutil.which("tailscale")
    if found:
        return found
    win = r"C:\Program Files\Tailscale\tailscale.exe"
    return win if os.path.exists(win) else "tailscale"


async def _run(args: list[str], timeout: float = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    """Run `tailscale <args>` with NO shell. Single seam — tests monkeypatch this.
    Returns (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        _ts_bin(), *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return (124, "", f"tailscale {args[0] if args else ''} timed out after {timeout}s")
    return (proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))


def _text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, default=str))]


def _allowed_hosts() -> set[str] | None:
    """Optional allowlist for ts_ssh targets via TAILSCALE_SSH_ALLOWED_HOSTS (comma list).
    None = no restriction beyond the hostname pattern (trusted local MCP)."""
    raw = os.environ.get("TAILSCALE_SSH_ALLOWED_HOSTS", "").strip()
    return {h.strip() for h in raw.split(",") if h.strip()} or None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
async def handle_ts_status(peers: bool = True) -> list[TextContent]:
    """Tailnet inventory: self + peers, online state, exit-node advertisement/use."""
    args = ["status", "--json"]
    if not peers:
        args.append("--peers=false")
    rc, out, err = await _run(args)
    if rc != 0:
        return _text({"error": "tailscale status failed", "detail": err.strip() or out.strip()})
    try:
        d = json.loads(out)
    except json.JSONDecodeError:
        return _text({"error": "could not parse status json", "raw": out[:500]})
    self_ = d.get("Self", {})
    exit_status = d.get("ExitNodeStatus") or {}
    nodes = []
    for p in ({"_self": self_, **(d.get("Peer") or {})}).values():
        if not p:
            continue
        nodes.append({
            "host": p.get("HostName"),
            "dns": p.get("DNSName", "").rstrip("."),
            "online": p.get("Online"),
            "exit_node_option": p.get("ExitNodeOption"),  # approved+usable exit node
            "is_self": p.get("ID") == self_.get("ID"),
            "os": p.get("OS"),
        })
    return _text({
        "magic_dns_suffix": d.get("MagicDNSSuffix"),
        "self": self_.get("HostName"),
        "using_exit_node": exit_status.get("ID"),
        "nodes": nodes,
    })


async def handle_ts_exit_node(action: str = "list", node: str = "") -> list[TextContent]:
    """list | suggest | set (node=<name>) | clear — manage this node's exit-node usage."""
    action = (action or "list").lower()
    if action == "list":
        rc, out, err = await _run(["exit-node", "list"])
        return _text({"action": "list", "ok": rc == 0, "output": (out or err).strip()})
    if action == "suggest":
        rc, out, err = await _run(["exit-node", "suggest"])
        return _text({"action": "suggest", "ok": rc == 0, "output": (out or err).strip()})
    if action == "clear":
        rc, out, err = await _run(["set", "--exit-node="])
        return _text({"action": "clear", "ok": rc == 0, "detail": (err or out).strip()})
    if action == "set":
        if not node or not _SAFE_HOST.fullmatch(node):
            return _text({"error": "set requires a valid 'node' hostname/IP"})
        rc, out, err = await _run(["set", f"--exit-node={node}", "--exit-node-allow-lan-access"])
        return _text({"action": "set", "node": node, "ok": rc == 0, "detail": (err or out).strip()})
    return _text({"error": f"unknown action '{action}'", "valid": ["list", "suggest", "set", "clear"]})


async def handle_ts_serve(action: str = "status", port: int = 0, bg: bool = True) -> list[TextContent]:
    """Tailnet-internal HTTPS (auto-TLS MagicDNS). status | set (port=<n>) | reset.
    Use to expose Jellyfin/Pinokio to tailnet members without nginx."""
    action = (action or "status").lower()
    if action == "status":
        rc, out, err = await _run(["serve", "status"])
        return _text({"action": "status", "ok": rc == 0, "output": (out or err).strip()})
    if action == "reset":
        rc, out, err = await _run(["serve", "reset"])
        return _text({"action": "reset", "ok": rc == 0, "detail": (err or out).strip()})
    if action == "set":
        if not (1 <= int(port) <= 65535):
            return _text({"error": "set requires a valid 'port' (1-65535)"})
        args = ["serve"] + (["--bg"] if bg else []) + [str(int(port))]
        rc, out, err = await _run(args)
        return _text({"action": "set", "port": int(port), "ok": rc == 0, "output": (out or err).strip()})
    return _text({"error": f"unknown action '{action}'", "valid": ["status", "set", "reset"]})


async def handle_ts_funnel(action: str = "status", port: int = 0, https: int = 443, bg: bool = True) -> list[TextContent]:
    """PUBLIC ingress over Tailscale relays (ports 443/8443/10000 only). status | set | reset.
    Powerful — exposes a local port to the whole internet."""
    action = (action or "status").lower()
    if action == "status":
        rc, out, err = await _run(["funnel", "status"])
        return _text({"action": "status", "ok": rc == 0, "output": (out or err).strip()})
    if action == "reset":
        rc, out, err = await _run(["funnel", "reset"])
        return _text({"action": "reset", "ok": rc == 0, "detail": (err or out).strip()})
    if action == "set":
        if int(https) not in (443, 8443, 10000):
            return _text({"error": "funnel https port must be 443, 8443, or 10000"})
        if not (1 <= int(port) <= 65535):
            return _text({"error": "set requires a valid local 'port' (1-65535)"})
        args = ["funnel"] + (["--bg"] if bg else []) + [f"--https={int(https)}", f"localhost:{int(port)}"]
        rc, out, err = await _run(args)
        return _text({"action": "set", "port": int(port), "https": int(https), "ok": rc == 0, "output": (out or err).strip()})
    return _text({"error": f"unknown action '{action}'", "valid": ["status", "set", "reset"]})


async def handle_ts_ssh(host: str, command: str, timeout: float = 60.0) -> list[TextContent]:
    """Run a command on a fleet node over Tailscale SSH (bypasses blocked port-22).
    Subject to the tailnet SSH ACL + check-mode re-auth. Host must match the allowlist
    (TAILSCALE_SSH_ALLOWED_HOSTS) when set."""
    if not host or not _SAFE_HOST.fullmatch(host):
        return _text({"error": "invalid host"})
    allow = _allowed_hosts()
    if allow is not None and host not in allow:
        return _text({"error": f"host '{host}' not in TAILSCALE_SSH_ALLOWED_HOSTS", "allowed": sorted(allow)})
    if not command.strip():
        return _text({"error": "empty command"})
    # tailscale ssh <user@host> <command...> — pass the command as a single arg list elem;
    # tailscale wraps system ssh and verifies the host key via the coordination server.
    rc, out, err = await _run(["ssh", host, command], timeout=timeout)
    return _text({"host": host, "rc": rc, "stdout": out.strip(), "stderr": err.strip()})


async def handle_ts_metrics() -> list[TextContent]:
    """tailscaled Prometheus metrics (tailscaled_inbound/outbound_bytes_total by path, etc.)
    for the observability stack."""
    rc, out, err = await _run(["metrics", "print"])
    if rc != 0:
        return _text({"error": "tailscale metrics failed", "detail": err.strip() or out.strip()})
    return _text({"format": "prometheus", "metrics": out.strip()})


async def handle_ts_netcheck() -> list[TextContent]:
    """Physical-network conditions: UDP, IPv4/IPv6, NAT, DERP latency."""
    rc, out, err = await _run(["netcheck", "--format=json"])
    if rc != 0:
        return _text({"error": "netcheck failed", "detail": err.strip() or out.strip()})
    try:
        return _text({"netcheck": json.loads(out)})
    except json.JSONDecodeError:
        return _text({"netcheck_raw": out.strip()})


async def handle_ts_ping(host: str, count: int = 1) -> list[TextContent]:
    """Ping a tailnet device over Tailscale only (reveals direct vs DERP relay path)."""
    if not host or not _SAFE_HOST.fullmatch(host):
        return _text({"error": "invalid host"})
    count = max(1, min(int(count), 10))
    rc, out, err = await _run(["ping", f"--c={count}", host])
    return _text({"host": host, "ok": rc == 0, "output": (out or err).strip()})


TOOLS: list[Tool] = [
    Tool(
        name="ts_status",
        description="Tailnet inventory from the local node: peers, online state, which nodes are "
                    "approved exit nodes, and which exit node (if any) this node is using.",
        inputSchema={"type": "object", "properties": {
            "peers": {"type": "boolean", "default": True, "description": "include peer nodes"}}},
    ),
    Tool(
        name="ts_exit_node",
        description="Manage THIS node's exit-node usage. action: list (advertised+approved) | "
                    "suggest (lowest-latency recommendation) | set (route egress via node=<name>) | "
                    "clear (stop using an exit node).",
        inputSchema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["list", "suggest", "set", "clear"], "default": "list"},
            "node": {"type": "string", "description": "exit-node hostname/IP (for action=set)"}}},
    ),
    Tool(
        name="ts_serve",
        description="Tailscale Serve — expose a local port to TAILNET members over auto-TLS HTTPS "
                    "(e.g. Jellyfin :8096, a Pinokio app). action: status | set (port) | reset.",
        inputSchema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["status", "set", "reset"], "default": "status"},
            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            "bg": {"type": "boolean", "default": True, "description": "persist across reboots"}}},
    ),
    Tool(
        name="ts_funnel",
        description="Tailscale Funnel — expose a local port to the PUBLIC internet (ports 443/8443/"
                    "10000 only), no port-forward. action: status | set (port, https) | reset. Powerful.",
        inputSchema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["status", "set", "reset"], "default": "status"},
            "port": {"type": "integer", "minimum": 1, "maximum": 65535, "description": "local backend port"},
            "https": {"type": "integer", "enum": [443, 8443, 10000], "default": 443},
            "bg": {"type": "boolean", "default": True}}},
    ),
    Tool(
        name="ts_ssh",
        description="Run a command on a fleet node over Tailscale SSH (bypasses blocked port-22; "
                    "subject to the tailnet SSH ACL + check-mode re-auth). Durable remote fleet control.",
        inputSchema={"type": "object", "properties": {
            "host": {"type": "string", "description": "tailnet node, e.g. pmoves-kvm2"},
            "command": {"type": "string", "description": "command to run on the node"},
            "timeout": {"type": "number", "default": 60}}, "required": ["host", "command"]},
    ),
    Tool(
        name="ts_metrics",
        description="tailscaled Prometheus metrics (throughput by path, advertised/approved routes) "
                    "for the observability stack.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ts_netcheck",
        description="Physical-network diagnostics: UDP, IPv4/IPv6, NAT type, DERP latency.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ts_ping",
        description="Ping a tailnet device over Tailscale only; shows direct vs DERP-relay path.",
        inputSchema={"type": "object", "properties": {
            "host": {"type": "string"}, "count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 1}},
            "required": ["host"]},
    ),
]

TOOL_HANDLERS = {
    "ts_status": handle_ts_status,
    "ts_exit_node": handle_ts_exit_node,
    "ts_serve": handle_ts_serve,
    "ts_funnel": handle_ts_funnel,
    "ts_ssh": handle_ts_ssh,
    "ts_metrics": handle_ts_metrics,
    "ts_netcheck": handle_ts_netcheck,
    "ts_ping": handle_ts_ping,
}
