# ACP Forks Review & NATS Repo Audit — Topology Correction (2026-10-07)

**Author:** agent0-sidecar · **Trigger:** operator links — 3 PMOVES ACP forks + clients page + POWERFULMOVES nats repos (`q=nats`) — review ACP for adapter planning and validate NATS topology against the fleet's own repos/docs
**Evidence base:** fresh clones at `/tmp/acp-review/` (PMOVES-agent-client-protocol @ 4d75b46 2026-10-07, PMOVES-acp-typescript-sdk @ 17720e4 2026-10-05, PMOVES-acp-python-sdk @ 79671b0 2026-10-07), 7 nats forks inventoried via API, `plugins/a0_acp/index.yaml` (fork), `pmoves/configs/nats-leaf-z890.conf`, live probes from the earlier lane.

---

## 1. Three ACP forks — inventory and freshness

| Repo | HEAD | What it is |
|---|---|---|
| `PMOVES-agent-client-protocol` | **2026-10-07** (#2322) | The protocol repo (Rust workspace): schema source (`agent-client-protocol-schema/`), docs (`docs/protocol/`, `docs/rfds/`), registry tooling. Tracks upstream closely |
| `PMOVES-acp-typescript-sdk` | 2026-10-05 | TS SDK — client/agent halves, release-please, schema tracking |
| `PMOVES-acp-python-sdk` | **2026-10-07** (#164) | Python SDK (`agent-client-protocol` on PyPI): generated Pydantic schema, asyncio stdio transports, `Agent`/`Client` base classes, contrib utilities, runnable examples |

Both SDKs track upstream tightly — the forks are current, not stale. **The PMOVES delta lives in the plugins fork, not the SDKs** (see §3).

## 2. The registry/authMethods contract (what the registry CI enforces)

From `docs/rfds/acp-agent-registry.mdx` + the live registry:
- Manifest = `<id>/agent.json` in the registry repo; required: `id`, `name`, `version`, `description`, `distribution`.
- `distribution`: `binary` / `npx` / `uvx`. **CI rejects `binary` entries that don't ship darwin+linux+windows** — so for a Python agent the right path is `uvx` (pure-Python package).
- Registry README: curated list of agents supporting **user authentication**; "All agents are verified via CI to ensure they return valid `authMethods` in the ACP handshake."
- `docs/rfds/get-auth-state.mdx` (auth/status RFD): clients query auth state post-`initialize` instead of probing via `session/new` errors. Maps 1:1 onto our A2A gate question — same philosophy, different protocol.

**Design consequence for PMOVES:** a registry-listed A0 must expose a clean authMethod — our candidate is **bearer over tailnet TLS** (the AGENT_ZERO_API_KEY pattern already proven on the 8081 protocol server), with the get-auth-state capability implemented so clients can query before session creation.

## 3. The adapter already exists — adopt + extend, don't build

Key finding: `plugins/a0_acp` in the PMOVES-a0-plugins fork (permanent 12-path delta) points to **`3clyp50/a0_acp`** — "Expose Agent Zero as an ACP stdio agent for editor-native sessions, workspace prompts, streaming updates, and session resume/fork support."

**Revised lane: ADOPT + VALIDATE + REGISTER.**
1. **Adopt**: run a0_acp against Spark A0's API (bearer auth over the `/a0` tailnet serve).
2. **Validate** with the Python SDK harness: `echo_agent.py` pattern (`Agent` class → `initialize`/`new_session` → `run_agent` stdio loop), contrib session accumulator for streaming/resume checks.
3. **Register**: manifest `pmoves-agent-zero/agent.json` with `uvx` distribution (pure-Python), repository + license; CI-verifiable authMethods.
4. The 3 SDKs' role: validation harness + (optionally) upstream contribution of fixes; the a0_acp adapter is the product surface.

## 4. NATS repos audit + topology correction

`q=nats` under POWERFULMOVES = **7 upstream mirror forks** (nats-server, nats.py, nats.net, natscli, nats-docker, prometheus-nats-exporter, nats-architecture-and-design) — reference corpus, no PMOVES-specific cookbooks. Validating topology against them + local configs:

### 4a. Correction to my earlier doc (FLEET_COMMS_PROTOCOLS_2026-10-07.md)

| Claim (earlier) | Corrected (measured) |
|---|---|
| "Prod hub is the 5090 (:7422)" | That is the **fleet-hub DESIGN** per `pmoves/configs/nats-leaf-z890.conf` — but the conf's own header says the leaf "works standalone until hub is ready". The hub is **not yet the live prod path** |
| "Spark runs its own NATS" | Precisely: Spark's `pmoves-nats-1` is an **independent JetStream island** (v2.11.8, 2 streams/4 consumers) that only its local containers reach over the compose network. It is **not in the z890↔5090 leaf diagram** |
| — | Spark A0's healthz connection is to **Spark-local NATS**, not the fleet hub. Cross-fleet CHIT/NATS messaging therefore requires either attaching Spark as a leaf (same conf pattern) or rotating sidecar creds onto Spark-local |

### 4b. Grounded current state (unchanged parts stand)
- Sidecar env.shared creds stale (pw len 6) vs Spark-local (pw len 40) → `Authorization Violation`; rotation via funnel only (#3269 decision-B bridge, #2953 NATS_CREDS materialization).
- `pmoves-nats-mcp` (local repo) remains the sanctioned MCP-over-NATS bridge once creds align.
- Geometry bus (`geometry.>` wildcard, `geometry.cgp.v1`, gateway chit.py endpoints, a2ui-nats-bridge) is the first CHIT-signed consumer to wire once any of these transports unblock.

## 5. Sequencing (operator-decision-gated)

1. **Now (no decisions needed):** adopt/validate a0_acp against Spark A0 via the tailnet serve; echo-agent harness from the Python SDK.
2. **Decision A — NATS cred target:** rotate sidecar creds onto **Spark-local** (fastest, both nodes already use it) **or** stand up the 5090 hub + attach Spark/z890 as leaves (fleet design, more moving parts). Funnel path applies either way (#3269/#2953).
3. **Decision B — A2A gate:** flags-vs-JWT (from the comms doc) — note get-auth-state RFD offers a cleaner long-term answer for both A2A and ACP.
4. **Then:** registry manifest (`pmoves-agent-zero`, uvx) → PR per CONTRIBUTING.md → CI verifies authMethods.

*Secrets: values never printed; lengths/names only. Clones at /tmp/acp-review/ are disposable.*