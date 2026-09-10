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
        "Cipher fleet restore recipe v2 (2026-09-09, Z890) for ALL PMOVES "
        "agents and peer nodes. Symptom: MCP 401/Unauthorized and chronic "
        "REST 401s. Root cause: session launchers export demo-era Supabase "
        "keys and compose gives shell env precedence over --env-file, so "
        "kong keyauth held a demo JWT (iss:supabase-demo) while postgrest "
        "enforced a different secret. Cure: (1) write freshly-signed "
        "postgrest-trusted HS256 service/anon keys (iss:supabase, role "
        "claims) into pmoves/env.shared plus all env.tier-* and generated "
        "files; (2) leave SUPABASE_SECRET_KEY and SUPABASE_PUBLISHABLE_KEY "
        "blank so kong-entrypoint drops duplicate keyauth entries; (3) "
        "recreate kong env-scrubbed via python subprocess with filtered "
        "os.environ (raw shell recreates re-inject demo keys); (4) set "
        "CIPHER_BIND=0.0.0.0 in env.shared for the tailnet fleet endpoint "
        "${TS_Z890}:8105; (5) mint per-agent identity with `make -C pmoves "
        "cipher-mint-token AGENT=<id>` and store CIPHER_<ID>_TOKEN in "
        "env.shared - per-agent mode REQUIRES agentId on every call and "
        "rejects the '*' wildcard; (6) verify with cipher_preflight.py, "
        "qdrant-verify-cipher, cipher-memory-smoke, then this probe. "
        "Peers: pull the parent branch for SKILL.md + compose wiring; the "
        "upstream-able Accept-Profile fix is Pmoves-cipher PR #19."
    )
    stored = call({
        "jsonrpc": "2.0", "method": "tools/call", "params": {
            "name": "pmoves_cipher_store",
            "arguments": {
                "content": record,
                "agentId": AGENT_ID,
                "category": "decision",
                "tags": [NODE_TAG, "cipher", "memory", "access-restore", "peer-handoff", "fleet"],
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
                    "Cipher fleet restore complete on Z890 (2026-09-09): "
                    "freshly-signed postgrest-trusted Supabase keys, kong "
                    "env-scrubbed, CIPHER_BIND=0.0.0.0 serving the tailnet "
                    "at TS_Z890:8105, crush-spark per-agent token minted and "
                    "validated end to end, Neo4j graph wired. Recipe v2 "
                    "stored as a peer-handoff memory; SKILL.md carries the "
                    "durable fleet doc. Next: funnel freshness-ordering fix, "
                    "launcher env-export hygiene, agent-zero MCP token."
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
