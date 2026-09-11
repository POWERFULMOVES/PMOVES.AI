# NATS Schooling — the correspondence map (2026-09-11)

**Author:** CRUSH-GLM52 (Knuckles) · **Status:** research mapping, per operator direction (DARKXSIDE)
**Lane:** `docs/nats-schooling-mapping` · **Scope:** no topology changes, no live recreates — school only.

> The operator's framing: *"we built geo bus from it and never read the manual... since it proved
> useful now we need to go to school on it to see where else it maps back or new patterns that
> eluded."* The first school finding is that **the class materials already exist** — the fleet
> wrote them and then kept running the flag-launched broker:

| Material | Where |
|---|---|
| v0 design spec (accounts, leaf, MCP, rollout, acceptance) | `pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md` (z890-claude) |
| The PMOVES hub config + Dockerfile + entrypoint | `PMOVES-nats-server/pmoves/` (README + `pmoves-nats.conf`) |
| Working examples: edge/cloud leaf, resolver preload, compose | `PMOVES-nats-server/pmoves/examples/` |
| JetStream stream design (slice 3+6, retention hazards) | `pmoves/docs/specs/nats-broker-deploy-slice3-streams-2026-08-01.md` |
| Subject corpus (2,261 + 488 lines) | `.claude/context/nats-subjects.md`, `geometry-nats-subjects.md` |
| Cipher traps (name-collision, facade-health, node-local state) | `claude-b850` memories, retrieved 2026-09-11 |

---

## 1. Measured now vs designed (the delta)

| Dimension | Running on Knuckles (2026-09-11) | Fork/spec target |
|---|---|---|
| Launch | CLI flags (`-js -m 8222 --user/--pass`) | `pmoves-nats.conf` baked in image |
| Tenancy | ONE global account, shared `nats:pmoves` | SYS / CORE / EDGE / CLOUD accounts (nsc, memory resolver) |
| Auth | plaintext user/pass | nsc-minted `.creds` (JWT + nkey), funnel-materialized |
| Leafnodes | **none** — no 7422 listener anywhere | `leafnodes { listen: 0.0.0.0:7422 }` + account-scoped leaves |
| Monitoring | 8222→loopback:9223, unguarded HTTP | SYS account guards `$SYS.*`; HTTP stays loopback-bound |
| WebSocket | none (a2ui rides a **manual bridge container**) | `websocket { port: 8080 }` for A2UI/browser |
| MQTT | none | ready-but-commented (jetson prosodic ears) |
| Streams | 8 (slice 3+6 landed; TOKENISM_ATTRIBUTION keeps silent-discard retention) | durable CHIT trails / tokenism / mesh per spec §6 |
| Payload | default (1MB) | `max_payload: 8MB` (CGP/geometry/prosodic run large) |

The historical leaf bug is documented in the spec §1: `elder-melchor-leaf.conf` remotes at the
**client port 4222** with plaintext creds — per the manual a leaf attaches at the hub's **7422**.
It has never been a real leaf.

## 2. The correspondence map — where NATS maps back onto PMOVES

| NATS capability (the manual) | PMOVES pattern it maps to | Status |
|---|---|---|
| **Accounts + nkeys + resolver** | Identity proposal §5 (PR #2935, ground 5: "the bus has no identity"). The spec's **two-gate model** is the designed answer: account = *who may cross a boundary* (transport trust), CHIT signature = *provenance inside the payload*. A leaf message is trusted only if it clears both. | Designed, undeployed. The proposal should cite the spec rather than treat per-agent auth as greenfield. |
| **Subject-scoped permissions** (per-user pub/sub allow lists) | Room-manifest `allowed_subjects` **ceilings** + `agent_registry.yaml` → `<agent>.nats.publishes`. B850's measured rule: the ceiling is a bound, `publishes` is the flow, and the defect direction is *widening publishes to match a ceiling* (#2734). NATS permissions give the same ceiling a **transport-level enforcement** instead of prose. | Corpus exists; enforcement absent. |
| **Leafnodes (7422)** | Fleet topology: jetsons (EDGE), Hostinger KVMs (CLOUD), one hub. **This is the open operator decision** — see §5. | Examples written; nothing attached. |
| **Exports/imports across accounts** | The curated public surface: CORE→EDGE job dispatch + prosodic control; EDGE→CORE mesh/STT/`tokenism.prosodic.bpm.v1` (signed); everything else hub-private *by construction*. This is the "cross-swarm federation" the identity proposal wanted — as subject curation, not a new protocol. | Spec §5 matrix. |
| **JetStream** | CHIT-trail durability, tokenism attribution, slice-3/6 streams (COMFY_COLLAB / ROOMS / HELPDESK, `limits` retention). The TOKENISM_ATTRIBUTION silent-discard hazard is the standing counterexample to copy. | Partial (8 streams live). |
| **$SYS system account** | Every "could-not-measure the bus" episode this week: the facade reports healthy while fronting a broker that may not exist; `/varz` needs the monitoring port. `$SYS.*` events + SYS-guarded monitoring make bus state *observable as data*. | Absent. |
| **WebSocket port** | `pmoves-a2ui-nats-bridge` is a hand-built bridge doing what the server does natively; browsers/A2UI could connect direct over the tailnet. | Bridge container running; native path specced. |
| **MQTT** | Jetson "prosodic ears" + sensors publishing without a full NATS client. | Ready, commented. |
| **max_payload 8MB** | CGP / geometry / prosodic packets — the reason the flag exists in the target conf. | Default today. |

## 3. Patterns that eluded us (found in the manual, not yet in any PMOVES doc)

1. **Imports with subject transformation** — an account can import `foo` as `bar`. Cross-account
   surfaces can be *renamed curations*, not just filtered ones. No PMOVES pattern uses this; the
   export matrix (spec §5) could present stable public names while CORE internals move.
2. **Service-type imports** (req/reply across accounts) — PMOVES request/reply today is intra-account
   only. Room orchestrator ↔ edge tool calls could cross zones as services.
3. **KV and Object Store buckets** (JetStream-backed) — candidate home for P7 room-stage /
   transient session state (the "persistent room stage vs transient session state" split the room
   contract already demands), and for funnel-rendered config distribution.
4. **Message headers** — NATS carries structured headers natively. CHIT provenance currently rides
   *in-body* by explicit design (spec §6/§11). Whether an envelope-header form is worth proposing
   is a **school question for the spec owner**, not a change here.
5. **Leaf-local JetStream buffering** — an edge leaf with its own store buffers while the tailnet
   link is down; the edge examples note this as optional. Relevant to island-mode coordination.

## 4. Hardening the surfaces we already got wrong (cipher-assisted)

B850's cross-agent memories (retrieved this session) name the trap families; each maps onto a NATS
surface this schooling should reinforce:

| Trap (measured, in Cipher) | NATS-side reinforcement |
|---|---|
| **Name collision** — a container *named* nats that is not a broker confirmed "broker exists" | Identify brokers by `.Config.Image`/`.Config.Cmd`, never by name; the SYS account makes identity checkable over the wire |
| **Facade health** — the event-bus healthcheck probes itself; healthy ≠ broker reachable | Healthchecks must round-trip the broker (pub/sub, not self-GET); `$SYS` events as the fleet-visible signal |
| **Node-local state** — fixes living in hand-run argv/flags vanish on recreate | The conf belongs in the fork (git) + funnel-rendered resolver_preload — exactly what the overlay does |
| **Empty is not evidence** — confident zeros from truncated/wrong instruments | Bus measurements state denominators (streams/conns counts, both sides) |
| **Gated publisher read as wired** — `sign_trail.py` publishes `agent.graphiti.signed.v1` but `CHIT_SIGN_PUBLISH` is unset fleet-wide | Wire the env gates before declaring any subject "live" in the corpus |

## 5. The one decision everything waits on: hub placement

Three candidate answers, each grounded in a measured fact:

| Option | Grounded in | Tension |
|---|---|---|
| **z890 hub** (spec §4, Aug 7) | The spec + leaf examples assume it | Register guardrail (Jul 2): *Knuckles is the data-tier home; z890 must NOT double-launch Postgres/NATS (split-brain)* |
| **Knuckles hub** | The guardrail + this node now runs the restored broker | Spec's CORE-services list assumes z890 service density |
| **Promote kvm4-2** | kvm4-2 runs a **live fleet broker today** (measured 2026-09-05) — it is already the de-facto hub | Neither spec nor guardrail names it; leaf-cloud examples treat KVMs as leaves |

Standing the broker up locally (done, 2026-09-11) was safe under all three. **No leaf should be
wired until this is called** — the split-brain guardrail and the spec disagree, and that is an
operator topology decision, not an implementation detail.

### 5.1 Operator direction (2026-09-11, DARKXSIDE): the question was descript, not a menu

The operator's call, on being shown the three options: *"doesn't answer — is descript."* The
direction is **not to pin one hub at all**, but a **three-in-one floating topology**:

> split-brain-safe **local** broker per capable node · a **multi-lane** broker role that floats ·
> **projecting to nodes on the local mesh, connecting mesh and mesh** · **dynamic constraint
> optimization for hardware scaling** — "so the ecosystem is present across" — optimizing for
> maximum mechanical flexibility.

In NATS-native terms this is exactly the capability triangle the manual already provides — none of
which requires choosing a permanent hub:

| Operator phrase | NATS-native mechanism |
|---|---|
| split-brain-safe local | a broker on every capable node (as Knuckles now runs), with **single-writer/RAFT-anchored JetStream streams** so a partition heals rather than forks |
| multi-lane floating broker | **cluster** (RAFT quorum) whose members can live on different nodes — the "lane" follows capacity, not a name |
| connecting mesh and mesh | **gateways** — full mesh-to-mesh federation between clusters, the piece no PMOVES doc has ever used |
| projecting to nodes on local mesh | **leafnodes** at the edge of each island (jetsons, KVMs) attaching to the nearest lane |
| dynamic constraint optimizing for hardware | placement decided by measured capacity (VRAM/class/uptime), not by a static spec table — the MOF capacity-class doctrine, applied to broker placement |

What this changes in §6: step 1 becomes **"size the lanes"** (which nodes cluster, which leaf,
which gateway) rather than "decide the hub." The split-brain guardrail is satisfied not by
exile of a second broker but by stream-level single-writer semantics — the thing the accounts+RAFT
design is *for*. This remains a design record: no wiring has changed on any node.

## 6. Paced rollout (spec §9, updated with today's deltas)

1. **Size the lanes** (§5.1 — operator direction received): which nodes cluster (RAFT), which
   leaf, which gateway; placement by measured capacity, not a static table.
2. **Mint** — nsc operator PMOVES → SYS/CORE/EDGE/CLOUD + users; seeds to CHIT-vault custody track
   (#1901 precedent); manifest entries, never hand-env.
3. **Hub** — deploy the fork overlay on the chosen node; publish 7422; SYS-guarded monitoring;
   CORE clients on `.creds`.
4. **Migrate CORE** — services' `NATS_URL` → CORE creds; flat-namespace traffic unchanged
   intra-CORE (acceptance test §10).
5. **EDGE then CLOUD leaves** — attach per examples; prove isolation + export round-trip.
6. **MCP** — `pmoves-nats-mcp` to CORE creds + CHIT-signed publish path (spec §7b; NATS_CREDS
   wiring PRs #2936/#2937 already open).
7. Along the way: WebSocket decision (native vs bridge), MQTT enablement per-account, stream
   retention fixes (TOKENISM_ATTRIBUTION).

## 7. Acceptance (already written — spec §10)

Leaf handshake at 7422 / isolation denials / export round-trips / two-layer trust (valid CHIT sig
accepted, unsigned crosses transport but fails verification) / SYS-guarded monitoring / cred
rotation without traffic loss. Nothing here weakens the v0 exclusions: no Go patches, no
broker-level CHIT enforcement, memory resolver.

---

*Schooling seed stored to Cipher (crush_glm52). Correspondence corrections welcome — the map is
the deliverable, not a deployment.*
