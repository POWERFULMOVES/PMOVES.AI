#!/usr/bin/env python3
"""One-shot authenticated MCP round-trip: store, search, checkpoint.

Repo-relative by construction: the token comes from bearer_token() in
cipher_preflight (process env -> repo env candidates) and the endpoint is a
flag with the roster default. Nothing node-specific is baked in.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from cipher_preflight import bearer_token  # noqa: E402

ENDPOINT = "http://localhost:8105/mcp"
AGENT_ID = "crush"
NODE_TAG = "z890"


def call(payload: dict, token: str) -> dict:
    """POST one JSON-RPC payload; unwrap the SSE data line if present."""
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    for line in body.splitlines():
        if line.startswith("data:"):
            body = line[5:].strip()
            break
    return json.loads(body)


def tool_result(rpc: dict) -> str:
    """Extract the first text content block from a tools/call response."""
    text = (rpc.get("result") or {}).get("content", [{}])[0].get("text", "")
    return text


def main() -> int:
    """Initialize, store a restore record, search it back, save a checkpoint."""
    token = bearer_token()
    if not token:
        print("NO TOKEN: cannot authenticate", file=sys.stderr)
        return 3

    init = call({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "z890-crush-restore", "version": "1.0"},
        },
    }, token)
    server = init.get("result", {}).get("serverInfo", {})
    print(f"initialize OK server={server.get('name')} v{server.get('version')}")

    record = (
        "Z890 Crush cipher access restored (2026-09-09). Symptom: "
        "pmoves-cipher-local MCP Unauthorized because the live crush.json "
        "predated the generator's Bearer header fix. Reproducible restore, "
        "no hardcoded paths: (1) CIPHER_API_TOKEN lives in pmoves/env.shared "
        "via secrets-funnel; (2) regenerate with "
        "`python3 -m pmoves.tools.mini_cli crush setup`; (3) launch via "
        "crush-pmoves so the process env carries the token for the "
        "${CIPHER_API_TOKEN:-} placeholder; (4) verify with "
        "`python pmoves/tools/cipher_preflight.py` which now authenticates. "
        "Fleet entry pmoves-cipher (${TS_Z890}:8105) stays gated until the "
        "tailnet hostname resolves in env. Cipher is fleet-wide memory for "
        "ALL PMOVES agents per agents.md, not a single-node tool."
    )
    stored = call({
        "jsonrpc": "2.0", "method": "tools/call", "params": {
            "name": "pmoves_cipher_store",
            "arguments": {
                "content": record,
                "agentId": AGENT_ID,
                "category": "decision",
                "tags": [NODE_TAG, "cipher", "memory", "access-restore"],
            },
        }, "id": 2,
    }, token)
    print("store ->", tool_result(stored)[:200])

    searched = call({
        "jsonrpc": "2.0", "method": "tools/call", "params": {
            "name": "pmoves_cipher_search",
            "arguments": {
                "query": "cipher access restore crush",
                "agentId": AGENT_ID,
                "limit": 3,
            },
        }, "id": 3,
    }, token)
    results = json.loads(tool_result(searched)).get("results", [])
    print(f"search -> {len(results)} hit(s); top id="
          f"{results[0].get('id') if results else 'NONE'}")

    checkpoint = call({
        "jsonrpc": "2.0", "method": "tools/call", "params": {
            "name": "pmoves_cipher_session_save",
            "arguments": {
                "agentId": AGENT_ID,
                "summary": (
                    "Restored cipher memory access on Z890: regenerated "
                    "crush.json with Bearer auth, fixed cipher_preflight to "
                    "authenticate (14/14 tests), verified store+search "
                    "round-trip over POST /mcp. Next lanes: fleet cipher "
                    "bind on KVM, SKILL.md fleet-wide rewrite, agent-zero "
                    "MCP token, venv+VSCode+Pinokio review."
                ),
                "harness": "crush",
                "model": "glm-5.3-flash",
                "activeLanes": ["cipher-access-restore"],
                "contextPaths": ["pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md"],
            },
        }, "id": 4,
    }, token)
    print("checkpoint ->", tool_result(checkpoint)[:160])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
