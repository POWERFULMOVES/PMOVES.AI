# PMOVES-spynel — Review + Registry (lane: docs/spynel-review-registry)

**Claimed:** 2026-09-13T12:30:00Z by HERMES-AGENT (elder-melchor), TTL 48h.
**Paired with:** B850-CLAUDE / CRUSH-GLM52 (Knuckles) — integration half (unclaimed at review time; this lane files the review/registry half per operator direction).

## What it is

- Fork `POWERFULMOVES/PMOVES-spynel`, created 2026-09-12T22:27Z, of `agent0ai/spynel` (Go, "One chat, unlimited AI orchestration" — multi-agent TUI with one elected workspace server per workspace; 19★ upstream, actively pushed).
- Fork state at review: **exact upstream parity** (0 ahead / 0 behind @ 80328a17). No PMOVES overlay yet.
- Shape: single Go binary (`cmd/spynel`), 255 `.go` files across `internal/` (app, localapi, orchestrator, workspace templates for chat/developer/heartbeat/notification/reviewer agents), npm launcher, 231-line install.sh.

## Review findings (pair-review, filed for the integration lane to address)

### Passes — security posture measured in source, not assumed
1. **Local API auth is done right** (`internal/localapi/server.go`): Bearer token with length check + `crypto/subtle.ConstantTimeCompare` — no timing side channel, no plaintext compare.
2. **Transport is a private unix-domain socket** (`socket_unix.go`): `net.ListenUnix`, `0o600` perms, token in a sidecar descriptor file, stale-socket handling refuses to blind-delete; `SetUnlinkOnClose(false)` + owned-file tracking on close.
3. **Windows degrades loudly** (`socket_windows.go`): every socket entrypoint returns explicit "unsupported on Windows" errors — no silent fallback to an unauthenticated TCP bind. (Relevant to this fleet: elder-melchor/z890/5090 are Windows nodes. Local API = Linux/macOS only until an overlay adds a named-pipe transport.)
4. **Bounded request framing**: `maxRequestBytes = 1 << 20` on the authenticated loopback endpoint.
5. **install.sh**: `set -eu`, HOME-anchored install root, absolute-path validation, no `sudo` in the default path (5 sudo mentions are macOS helpers), bundle validation delegated to the verified native binary.

### Findings (filed, none blocking for a parity fork)
- **F1 (P2, network):** the install/bootstrap README path pipes remote content (`curl -LsSf …/install.sh | sh`). Standard for the upstream project; for fleet installs prefer cloning this fork and building from source (`go build ./cmd/spynel`) — the fork IS the trusted path, the CDN is not.
- **F2 (P3, provenance):** fork carries no PMOVES marker yet (no PMOVES.AI_INTEGRATION.md, no hardened branch). Before any compose/Pinokio integration lands, the overlay needs: integration doc, `PMOVES.AI-Edition-Hardened` branch, fork_registry sync decision. The registry half is done in this lane; the overlay half belongs to Knuckles.
- **F3 (P3, ops):** single-binary TUI + workspace server assumes an interactive seat. Headless fleet deployment (KVMs) needs the local API over a transport Windows supports, or stays Linux-only. Not a defect — a deployment-class note.
- **F4 (P3):** `agentdocs` + workspace templates mean the tool composes agent prompts from repo docs — on THIS fleet that pattern is governed (AGNOTES context rules); if integration adopts spynel's agent templates, they must be reconciled with the AGENTS.md/AGNOTE conventions, not run in parallel.

### Registry state after this lane
- `fork_registry.json`: PMOVES-spynel registered — upstream `agent0ai/spynel`, sync=true (at parity, no overlay to carry), branch `main`, reason cites the consumed-or-archived decision owed by the unconsumed-fork audit.
- Register: CLAIM row filed (this lane) with GRAPHITI_MARK; RELEASE to follow when the pair-review findings are dispositioned by the integration lane.

## Verdict

Sound, well-engineered upstream (the auth/transport code is above average for this class). Fork is correctly positioned at parity for evaluation. **No blockers.** Integration lane owes: PMOVES overlay (F2), source-build install path for fleet nodes (F1), Windows transport decision (F3), template governance (F4).
