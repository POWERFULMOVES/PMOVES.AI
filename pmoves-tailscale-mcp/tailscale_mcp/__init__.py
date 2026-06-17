"""PMOVES Tailscale MCP bridge — thin MCP server over the local `tailscale` CLI.

Durable, node-local fleet control: exit-node use, Serve/Funnel exposure, Tailscale-SSH
remote commands, tailscaled metrics, and netcheck/ping diagnostics. Requires no API key
(uses the joined daemon); complements the admin-API `tailscale-mcp` (ACL/route/device mgmt).
Per the Integration Rule: leverage, don't duplicate — every tool is a typed CLI passthrough.
"""

__version__ = "0.1.0"
