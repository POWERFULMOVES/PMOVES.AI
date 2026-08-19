# Cipher context

**Submodule:** [Pmoves-cipher/](https://github.com/POWERFULMOVES/Pmoves-cipher) + [pmoves-cipher-mcp/](https://github.com/POWERFULMOVES/pmoves-cipher-mcp)
**MCP server name:** `pmoves-cipher`
**Transport:** SSE at `http://localhost:8105/mcp/sse`
**Bearer auth:** `Authorization: Bearer ${CIPHER_API_TOKEN}` (header expands empty without the env var → 401, expected)
**Discovery entry:** `pmoves/config/agent_registry.yaml` → `mcp_servers.pmoves_cipher_mcp`

Cipher is the PMOVES memory layer. Every cross-session knowledge lookup, every durable plan/checkpoint/completion, every state-changing action's signed audit trail flows through it. This context captures what's encrypted, where the keys live, the NATS custody chain, and how a Mavis-class agent should use it.

## What cipher is for

Three distinct things, all served by the same MCP server:

1. **Persistent agent memory** — durable storage of plans, checkpoints, and completions across agent sessions. An agent that gets a cold start can re-read its prior plan, see what it tried, and pick up.
2. **Reasoning trace storage** — the long-form chain-of-thought or decision rationale. Not the same as the plan; the trace is the working memory, the plan is the durable artifact.
3. **CHIT custody chain** — the signed audit trail for state-changing actions. The CHIT signing flow (`make -C pmoves sign-trail`) reads cipher's memory of the action context, signs the payload, and writes the signed result back to cipher.

These three together make cipher the "long now" for PMOVES agents. Without cipher, every session starts from zero; with cipher, the agent inherits the prior context.

## What's encrypted

Cipher encrypts the **memory body** (the actual stored payload — plans, traces, completions) using the node's CHIT key. The **memory index** (titles, timestamps, category, search hits) is stored unencrypted so the MCP server can answer search queries without decrypting every record.

Encryption key: `$CHIT_PASSPHRASE` (per the `B850-CLAUDE::SECRETS-LANE-L4-L5` AGNOTE entry 2026-08-18, the container-side name is `CHIT_PASSPHRASE`; the host-side label that the secrets pipeline writes is also `CHIT_PASSPHRASE` after the sync-secrets-local.yml fix in PR #2605). The key is loaded at container start; without it, the cipher container refuses to decrypt anything.

Encryption scheme: HMAC-SHA256 + AES-256-GCM, per the cipher spec at `pmoves/docs/security/CHIT/` (the CHIT signing spec). The HMAC is the CHIT trail; the AES key is derived from the passphrase via PBKDF2.

## Where the keys live

| Key | Lives in | Used by | Notes |
|-----|----------|---------|-------|
| `$CHIT_PASSPHRASE` (host-side) | `pmoves/env.shared` (per node) | `secrets-funnel` pipeline; cipher container reads it via the env interpolation in compose | Per-node, never shared. The pipeline writes a different value per node, so a stolen value only exposes one node's memory. |
| `$CHIT_PASSPHRASE` (container-side) | `docker-compose.<overlay>.yml` env section | `pmoves-cipher-api-1` reads it at container start | Same value as the host side, just propagated via the env interpolation. |
| HMAC kid (the public identifier) | `pmoves/contracts/chit/manifest.json` | CHIT signing + verification | Public; identifies the signing key, not the key itself. |
| HMAC secret (the actual signing key) | `$CHIT_PASSPHRASE` derived | `make -C pmoves sign-trail` | Used at signing time; never written to disk. |

The CHIT trail unsigned-local fallback (no `$CHIT_PASSPHRASE` set) is acceptable in dev per the AGNOTE rules, but the trail is still recorded — just unsigned. A signed trail is the only kind that gates merge in production; an unsigned trail is informational.

## NATS custody chain

Cipher publishes three subjects that the wider PMOVES ecosystem subscribes to (per `.claude/context/nats-subjects.md`):

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `cipher.memory.stored.v1` | cipher-api → monitoring | Notify that a memory was stored |
| `cipher.memory.searched.v1` | cipher-api → monitoring | Notify that a memory search was performed |
| `cipher.reasoning.stored.v1` | cipher-api → monitoring | Notify that a reasoning trace was stored |

Cipher does NOT publish to `chit.signed.v1` directly. The CHIT signing flow is:
1. An agent decides to take a state-changing action.
2. The agent calls `make -C pmoves sign-trail SUMMARY=... AGENT=...`.
3. `sign-trail` reads the agent's context (often from cipher itself), composes a CHIT payload, signs it with the HMAC key derived from `$CHIT_PASSPHRASE`, and writes the signed payload to cipher.
4. `sign-trail` then publishes the signed event to `chit.signed.v1` on NATS.
5. Subscribers (AGNOTE trail writers, monitoring, downstream consumers) react to the signed event.

The HMAC signature is the custody mechanism. A signed trail can be verified offline against the public kid + the secret; a forged trail fails verification. This is what makes the AGNOTE append-only discipline work — the prior entry's signature is the trust anchor for the next entry.

## How a Mavis-class agent should use it

Three patterns, in priority order:

1. **Read on cold start.** Before doing work, search cipher for prior plans, recent completions, and AGNOTE entries tagged with your role. The `.claude/mcp.json` `pmoves-cipher` server exposes `cipher_search(query, category, limit)` and `cipher_read(record_id)` for this. Use the `category` filter to narrow (e.g. `category=agent_checkpoint` for the prior plan; `category=agent_completion` for what was tried).

2. **Write on phase boundaries.** Every BPM phase transition (define → assign → execute → review → close, per the harness v0 NATS subjects) should write a cipher record. The `cipher_store(record_type, payload, chit_signature?)` MCP method is the entry point. The record_type enum is `agent_plan | agent_checkpoint | agent_completion | reasoning_trace | chit_signed_event`.

3. **Sign before any state-changing action.** `make -C pmoves sign-trail` is the canonical entry point; raw HMAC calls bypass the audit chain. The damage-control hook redirects raw `hmac` / `openssl dgst -hmac` calls to an `ask` prompt, same as it does for raw `docker`. Don't bypass.

## What cipher is NOT

- Not a search engine. Cipher is a memory store; if the memory wasn't written, it can't be found. If a prior agent didn't record a decision, that decision is lost.
- Not a database. Cipher's search is best-effort text match over encrypted records; it's not a SQL query. For structured data (agent registry, model configs, NATS subjects), use the appropriate PMOVES subsystem.
- Not a key-value store. Cipher records have a schema (the four `agent_*` / `reasoning_trace` types plus the chit_signed_event type); the payload must conform.
- Not a real-time channel. Cipher's NATS subjects are for monitoring, not for inter-agent messaging. For that, use the NATS subjects registered in `pmoves/contracts/schemas/` directly (e.g. `pmoves.agent.task.v1`).

## Reference

- MCP server source: `pmoves-cipher-mcp/` (PMOVES fork of the cipher MCP)
- Memory source: `Pmoves-cipher/` (the cipher storage engine)
- MCP config: `.claude/mcp.json` → `pmoves-cipher` server
- Agent registry: `pmoves/config/agent_registry.yaml` → `mcp_servers.pmoves_cipher_mcp`
- NATS subjects: `.claude/context/nats-subjects.md` (search for `cipher.*`)
- AGNOTE body: `.claude/agents/memory-agent.md` (the Three-Body Memory Body)
- CHIT signing spec: `pmoves/docs/security/CHIT/` (CHIT trail signing reference)
- Signing entry point: `make -C pmoves sign-trail` (per `pmoves/Makefile`)
- Secrets pipeline: `pmoves/mk/codex.mk` → `secrets-funnel` target (the canonical funnel)
- Path verification: `.claude/mcp.json` `_note` on `pmoves-cipher` — `/mcp/sse` returns 200, `/api/mcp/sse` and `/sse` return 404 (PATH VERIFIED 2026-08-12)
