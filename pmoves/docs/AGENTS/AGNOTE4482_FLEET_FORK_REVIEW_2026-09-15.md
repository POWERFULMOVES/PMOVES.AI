# Fleet fork review — Spynel, Registry, NATS clients, pipecat-context-hub, e2b stack, CONCH

**Node:** SPARK · **Date:** 2026-09-15 · **Lane:** fork-registry reconciliation (operator-directed)
**Scope:** the six org forks named for review + the e2b selfhosted stack + the CONCH creator
pipeline, "to ensure PMOVES and CHIT."

## Summary table (state after this lane)

| Repo | Upstream | Registry before | Action this lane |
|---|---|---|---|
| `PMOVES-spynel` | `agent0ai/spynel` | registered (#3047) | none — reviewed below, integration lane already delivered its overlay |
| `PMOVES-registry` | `agentclientprotocol/registry` | **missing** | registered |
| `PMOVES-natscli-CHIT-EeZz` | `nats-io/natscli` | **missing** | registered (decision owed) |
| `Pmoves-nats.net` | `nats-io/nats.net` | **missing** | registered (decision owed) |
| `Pmoves-pipecat-context-hub` | `pipecat-ai/pipecat-context-hub` | **missing** | registered |
| e2b stack (`PMOVES-E2B-Danger-Room`, `-Desktop`, `-Spells`, `PMOVES-Danger-infra`) | — | registered | none needed |

## Per-repo findings

### PMOVES-spynel — reviewed, integrated, done by prior lanes
The HERMES-AGENT pair-review (`pmoves/docs/services/spynel/REVIEW-REGISTRY.md`) measured the
security posture in source (constant-time token compare, private UDS transport, bounded
framing, loud Windows degradation) and filed F1–F4 against the integration lane. The fork
registry entry now carries the delivered hardened branch + integration doc. **Nothing owed
from this lane.** Standing note: fleet installs build from the fork (`go build ./cmd/spynel`),
never the CDN pipe (F1).

### PMOVES-registry — the shared-registry substrate (the important one)
Fork of the **official ACP registry** (`agentclientprotocol/registry`), actively tracking
upstream (MiniMax Code 0.2.7, harn 0.10.135, factory-droid 0.218.1 merged within days). This
is the neutral, protocol-level counterpart to `pmoves/config/agent_registry.yaml`: ACP answers
"which agents speak the protocol and how do I reach them"; the PMOVES registry answers "who
exists in THIS fleet, with what identity/role." **Open wiring** (the "a0 and archon share
registry" line): a mapping layer or sync job between ACP entries and the PMOVES registry, so a
minted agent (Archon door) is discoverable by every harness (ACP) the day it exists. That is
the registry half of the model-assisted harness bring-up loop.

### PMOVES-natscli-CHIT-EeZz — decision owed
At upstream parity; **no CHIT delta committed** despite the name. The signed-publish surface
already ships in `pmoves-nats-mcp` (CHIT-aware subjects, canonical signer). Either (a) land the
CHIT delta this fork exists for (e.g. signed `nats pub`/audit trail for operators on the CLI),
or (b) archive it per the unconsumed-fork doctrine. Registered with sync=true so it keeps
tracking while the decision is open.

### Pmoves-nats.net — decision owed
.NET async NATS client (JetStream, KV, Object Store, Services), tracking upstream closely.
Natural consumer: `PMOVES-E2B-Danger-Room-Desktop` or other C# surfaces. No in-repo consumer
today — same consumed-or-archived decision, registered so the audit sees it.

### Pmoves-pipecat-context-hub — wire it into Flute
Local-first MCP server carrying Pipecat docs, examples, and API context for coding agents.
This is precisely a Flute Gateway context option: any agent touching the voice lanes can have
authoritative Pipecat API context without web calls. **Recommended next step:** add as an MCP
entry (gateway-agent registry) alongside the existing pipecat forks, before further voice
overlay work.

### e2b selfhosted stack — registered and coherent
`PMOVES-E2B-Danger-Room`, `-Desktop`, `-Spells`, `PMOVES-Danger-infra` all carry registry
entries; the in-repo `agent-sandbox` skill and the e2b MCP endpoints (sandbox create/execute/
spell/desktop) are the live surface. No gaps found at the registry layer; runtime wiring is
the standing danger-room lane.

### CONCH creator pipeline — in-repo, not a fork
No org repo; the pipeline lives in-repo (CONCH execution guide, persona lane). For grounded
personas the load-bearing pieces are: `pmoves/docs/AGENTS/PERSONAS.md` (schema + seeds), the
third-ref consumption reference (persona-thirdref, live), and the ACP registry above for
cross-agent discovery of minted personas. CONCH work continues as an in-repo lane.

## CHIT posture across the set

- Signed publishes: covered (`pmoves-nats-mcp`, canonical signer; CHIT-aware subjects).
- natscli-CHIT fork: delta owed or archive (above).
- Registry/parity forks: no CHIT surface required at parity; any overlay that lands must
  follow the CHIT-aware-service pattern (fail-closed passphrase, signed trail) as evo-controller
  and the swarm-meta contract demonstrated this week.

## Provenance

- Repo states via GitHub API (fork flags, `source` upstreams, recent commits) — 2026-09-15.
- `pmoves/config/fork_registry.json` (82 entries after this lane; `_schema`, `_source` intact).
- Prior art: `pmoves/docs/services/spynel/REVIEW-REGISTRY.md` (#3047 lane),
  `AGNOTE4482_MODEL_ASSISTED_HARNESS_BRINGUP.md` (#3061).
