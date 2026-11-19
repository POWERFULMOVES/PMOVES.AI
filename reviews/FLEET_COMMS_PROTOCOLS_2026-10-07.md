# Fleet Comms Establishment — CHIT(NATS) / MCP / A2A / ACP (2026-10-07)

**Author:** agent0-sidecar (A0 digital-twin) · **Claim:** CLAIM 2026-10-07T10:08Z → RELEASE (this doc) in AGNOTE4482PHI.t1.md
**Context:** Spark A0 stood up same day (see `reviews/SPARK_A0_STANDUP_RUNBOOK_2026-10-07.md` §0) — this lane establishes the four comms protocols on top of that posture.

## Lane status matrix (all measured 2026-10-07)

| Lane | Status | Evidence | Unblock path |
|---|---|---|---|
| **MCP** | ✅ **LIVE cross-node** | `https://pmoves-spark.tailcad9b4.ts.net/a0/mcp/commands` → 200, full command registry (default_form POWERFULMOVES); `/mcp/execute` shape verified. Facade on 8080 (REST, no inbound auth by design); protocol server on 8081 (X-API-KEY gated, `/healthz` intentionally absent) | None — operational. Client auth for 8081 uses AGENT_ZERO_API_KEY (len 43, on-node) |
| **NATS (CHIT transport)** | 🟡 transport PROVEN on-node; sidecar creds STALE | Spark: `nats://[user:pw]@127.0.0.1:4222` (from A0 container env) → CONNECTED v2.11.8, pub/sub round-trip PASS, JetStream enabled (2 streams / 4 consumers). Sidecar env.shared creds (pw len 6) → `Authorization Violation` vs Spark's pw len 40 | Secrets funnel only (per #3269 dual-credential rotation bridge + #2953 NATS_CREDS materialization): rehydrate sidecar NATS_USER/NATS_PASSWORD from the same source Spark's compose reads. NEVER hand-copy values (2026-04 audit standard) |
| **A2A** | 🟡 live-but-gated (by design) | `/.well-known/agent-card.json` → 401 without auth; 403 `JWT validation failed` with AGENT_ZERO_API_KEY (it's a key, not a JWT). `A2A_DISCOVERY_PUBLIC=false`, `A2A_TASKS_PUBLIC=false` in container env | Either (a) operator flips the two flags for tailnet-only exposure, or (b) obtain a WebUI-login JWT for the service account. Gate decision is operator's (exposure policy) |
| **ACP** | ⚪ contract mapped; adapter build scoped | Registry (POWERFULMOVES fork = upstream structure): per-agent dir + `agent.schema.json` + `FORMAT.md` + `CONTRIBUTING.md`; **CI-verified requirement: agents must return valid `authMethods` in the ACP handshake** (AUTHENTICATION.md, auth-methods RFD). 41 agents currently listed | Build an ACP adapter for A0 (JSON-RPC handshake wrapper exposing an authMethod — candidate: bearer over tailnet TLS). Then PR per CONTRIBUTING.md. Sized: 1-2 sessions |

## NATS topology (grounded)
- **Prod hub: 5090 node** (`:7422` leafnodes accept) ← z890 leaf (`nats-leaf-z890.conf`, `:4222`) ← containers. Spark runs its own NATS (0.0.0.0:4222, JetStream) — A0 connected over the compose network.
- Sidecar↔Spark direct: raw TCP to `100.89.7.106:4222` works (banner verified); needs the rotated creds via funnel.
- `pmoves-nats-mcp` (local repo) = MCP wrapper over NATS publish/subscribe — candidate bridge so any MCP client can speak over the bus once sidecar creds rotate.

## CHIT-over-NATS wiring (what exists vs what this lane adds)
- EXISTS: `AGENT_ZERO_EVENTS_TOKEN` (len 32) in nats container env; CHIT passphrase slots (prod len 43) in nats env; CHIT signing flow documented in `pmoves/docs/security/`.
- THIS LANE adds: measured transport (on-node smoke PASS), the cred-divergence diagnosis (stale dev creds in sidecar), and the rotation path citation (#3269 decision B). The sidecar cannot join the bus until it receives rotated creds through the funnel.

## Follow-ups executed in this lane
- **PR #3296** opened: `fix(ci): clm-eval-spark encoder — Ollama :11434 readiness replaces vLLM :8090` (branch `fix/clm-eval-ollama-encoder`, commit b08ffaa94). vLLM dropped (GB10 engine-init fail), Ollama embeddings readiness probe + `ENCODER=OLLAMA-FALLBACK` caveat in-band.
- **8081 chat uFr2lU6a: CLOSED** — history shows the three-task report delivered from main @ `1411e15c8` (compose fix + Jev triage + reviews; no edits/commits from that instance).

## Follow-ups remaining (owner-tagged)
1. **Sidecar NATS creds rotation** — operator + funnel (per #3269/#2953); then I run the cross-node pub/sub smoke and wire CHIT event publishes.
2. **A2A gate decision** — operator: flags-vs-JWT for tailnet exposure; then agent-card + task round-trip from sidecar.
3. **ACP adapter build** — scoped follow-up (handshake wrapper + authMethods; entry PR to PMOVES-registry per CONTRIBUTING.md).
4. **5082/5083 UI restore** — fresh clone now unblocked (229G free); `make -C pmoves up-agents` per runbook §0.
5. **Merge #3296** after CI + review (Conventional Commits compliant, Testing section in body).

*All probes redacted of secret values; lengths/names only. Channels: sidecar→tailnet TLS, Windows-CLI ssh→Spark (powerfulmoves, key auth), GitHub API (GITHUB_TOKEN).*