#!/usr/bin/env python3
"""Agent Zero smoke checks — PMOVES supervisor surface (services/agent-zero/main.py).

Verified against source 2026-09-03 (tests test_main.py:155-200, main.py:821-878,
floos_resolver.py:471-475):
  - GET  /healthz            -> 200, health payload (fallback /health via AGENT_ZERO_HEALTH_PATH_FALLBACK)
  - GET  /config/environment -> non-empty AgentZeroServiceConfig
  - GET  /mcp/commands       -> {default_form, runtime, commands} — default_form is the CHIT persona form
  - POST /mcp/execute        -> {cmd, result} — form.get returns the persona form in .result

The supervisor listens on 8080 (floos_resolver handoff default); upstream
Agent Zero core runs on 8081 with its own /api/health — don't confuse them.

Env: AGENT_ZERO_SUPERVISOR_URL (default http://localhost:8080)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AGENT_ZERO_SUPERVISOR_URL", "http://localhost:8080").rstrip("/")


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=10) as resp:
        if resp.status != 200:
            raise SystemExit(f"✗ {path} returned HTTP {resp.status}")
        return json.loads(resp.read().decode())


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 200:
            raise SystemExit(f"✗ {path} returned HTTP {resp.status}")
        return json.loads(resp.read().decode())


def health() -> None:
    try:
        data = _get("/healthz")
    except urllib.error.HTTPError as e:
        if e.code == 503:
            raise SystemExit("✗ /healthz 503 — supervisor up but dependencies degraded")
        raise
    print(f"✔ /healthz 200: {json.dumps(data)[:100]}…")
    cfg = _get("/config/environment")
    if not cfg:
        raise SystemExit("✗ /config/environment empty")
    print("✔ /config/environment non-empty")


def mcp_list() -> None:
    data = _get("/mcp/commands")
    cmds = data.get("commands") or []
    form = data.get("default_form")
    if not cmds:
        raise SystemExit(f"✗ /mcp/commands returned no commands: {json.dumps(data)[:200]}")
    print(f"✔ /mcp/commands: {len(cmds)} commands, default_form={'present' if form else 'MISSING'} (sample: {', '.join(str(c) for c in cmds[:5])})")


def mcp_exec() -> None:
    data = _post("/mcp/execute", {"cmd": "form.get", "arguments": {}})
    result = data.get("result") or {}
    form = result.get("form") or data.get("form") or result.get("default_form")
    if not form:
        raise SystemExit(f"✗ form.get returned no form: {json.dumps(data)[:200]}")
    print(f"✔ form.get via /mcp/execute ok — CHIT persona form present ({json.dumps(form)[:80]}…)")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "health"
    fn = {"health": health, "mcp-list": mcp_list, "mcp-exec": mcp_exec}.get(mode)
    if not fn:
        raise SystemExit(f"unknown mode: {mode} (health|mcp-list|mcp-exec)")
    fn()


if __name__ == "__main__":
    main()
