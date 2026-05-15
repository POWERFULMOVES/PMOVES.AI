# pmoves-nats-mcp

MCP (Model Context Protocol) bridge that exposes the PMOVES.AI NATS event bus to Claude Code.

## Tools

| Tool | Purpose |
|------|---------|
| `nats_publish(subject, payload, headers?)` | Fire-and-forget publish to a subject (e.g. `archon.mint.agent.v1`). |
| `nats_subscribe(subject, timeout_seconds?, max_messages?)` | Subscribe + wait + return captured payloads. Supports wildcards (`*`, `>`). |

## Setup

```bash
cd pmoves-nats-mcp
uv sync
```

## Smoke test (stdio)

```bash
# Confirm the server starts (Ctrl-C to exit):
uv run python -m nats_mcp.server
```

## Wire into Claude Code

Add to `.claude/mcp.json` once smoke-tested. **The roadmap (Wave 0 / Task 10) deliberately leaves this commented out — operator opt-in.**

```jsonc
{
  "mcpServers": {
    "pmoves-nats": {
      "command": "uv",
      "args": ["--directory", "./pmoves-nats-mcp", "run", "python", "-m", "nats_mcp.server"],
      "env": {
        "NATS_URL": "nats://nats:pmoves@127.0.0.1:4222"
      }
    }
  }
}
```

## Environment

- `NATS_URL` — connection URL (default `nats://nats:pmoves@127.0.0.1:4222`).

## Design notes

- Each tool call opens and closes its own NATS connection. Trade-off: simpler/safer (no shared state in a stdio server) at the cost of per-call connect latency. For high-frequency use, switch to a long-lived shared `Client` guarded by an `asyncio.Lock`.
- `nats_subscribe` is bounded by both `timeout_seconds` and `max_messages` so it always returns. JetStream consumer state is **not** created — for durable consumption use a service-side subscriber.
- For request/reply, use `nats_subscribe` against a reply inbox after publishing with a `reply` header (TODO: expose a single `nats_request` helper in a follow-up).

## Subject conventions

PMOVES subjects follow `<domain>.<entity>.<event>.v<n>`:

- `archon.mint.agent.v1`, `archon.mint.skill.v1`, `archon.mint.confirmed.v1`
- `archon.qa.result.v1`
- `chit.signed.v1`
- `tokenism.*`, `geometry.*`, `p7.nats.launch`, `p7.nats.session`

See `.claude/context/nats-subjects.md` and `geometry-nats-subjects.md` for the live registry. Use the `pmoves-nats-subject-audit` skill to diff declared vs live subjects.
