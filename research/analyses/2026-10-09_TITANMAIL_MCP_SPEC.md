# TitanMail MCP — Seed Spec

**Date:** 2026-10-09 · **Status:** SEED (design only — no implementation started) · **Placement target:** KVM2 (Hostinger VPS), loopback bind, tailnet-only access

Grounded in: `research/analyses/2026-10-08_ARAGON_EMAIL_TOOLING_MAILRIGHT_CDP_ANALYSIS.md` (Richard Aragon, transcript `Wwi-NEPzenc`, 2026-10-08). Key verified facts from that analysis: Microsoft **EmailBench** (2026-09-25, Enron-based, ~33% raw baseline); Aragon's reconstruction jumped **86% → 99.3%** on date-sensitive retrieval by passing **exact date/time in the API call** (GPT Luna, $0.10/$0.50 in/out); **Mail Right** (released) is the reference email-agent platform; **Agentic CDP v0.1** (released) is the deterministic-first record-unification pattern.

## Mandates

### (a) Exact-datetime injection — mandatory, all email queries

No email query may rely on model-inferred "today". The titanmail MCP server resolves and injects exact current datetime server-side into every provider API call, and every retrieval call takes explicit ISO-8601 datetime parameters. This is the load-bearing fix (86% → 99.3% in the Aragon reconstruction) and applies equally to gmail/outlook transports. A0's EXTRAS `current_datetime` discipline is already in place on the consumer side; titanmail enforces it at the **server** boundary so clients cannot skip it.

### (b) ≥99% date-sensitive retrieval with EmailBench-style smoke harness

Target: **≥99%** on date-sensitive queries. Ship a smoke harness (Enron fixture or live-inbox sample, following Aragon's corrected-benchmark construction) that runs date-window queries through the MCP server and scores retrieval accuracy in CI. Below target = failing build, not a footnote.

### (c) Deterministic-first dedup (Agentic CDP pattern)

Message/thread/contact dedup uses deterministic keys first (Message-ID, normalized addresses, canonical datetime windows) with AI assist only as tie-breaker — never as primary matcher. Precision bar: **three-nines (99.9%)**; below two-nines dedup is net-harm (consistent with the fleet circuit-breaker principle).

### (d) Composio gmail/outlook connectors as transport

The MCP server exposes email operations; the actual provider transport is composio's gmail/outlook connectors (the composio MCP proxy deployed on the same node — see `pmoves/docs/operations/MCP_SERVER_NODE_MAP.md`, composio row, status PLANNED). Titanmail adds the datetime-injection, dedup, and eval layers composio does not provide. Auth: `COMPOSIO_API_KEY` via env file only (never CLI/logs).

### (e) Mail Right as reference architecture

Mail Right's released platform is the architectural reference for the email-agent layer (retrieval → task extraction → action). Titanmail reproduces the load-bearing retrieval discipline, not the full platform; it is the MCP-native slice of that pattern for the PMOVES fleet.

## Wiring (post-build)

```bash
# env.shared.example addition once deployed:
PMOVES_TITANMAIL_MCP_ENDPOINT=http://kvm2:<PORT>/sse
```

Loopback-only bind on KVM2; fleet access via Tailscale; seed via `A0_SET_mcp_servers` streamable-http entry (see node-map doc). Port recorded in `MCP_SERVER_NODE_MAP.md` after deploy.

## Open items

- Composio proxy deployment on KVM2 **blocked 2026-10-09**: SSH unreachable from Windows host (both routes timed out; circuit-breaker stop) and `HOSTINGER_SSH_PRIVATE_KEY` in `env.tier-agent` is structurally truncated — re-funnel before any KVM2 lane.
- Harness fixture choice (Enron vs live-inbox sample) to be settled at build start.
