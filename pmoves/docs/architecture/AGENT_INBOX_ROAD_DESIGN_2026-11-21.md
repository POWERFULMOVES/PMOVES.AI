# Agent Inbox Road: design (2026-11-21)

**Status:** DESIGN, awaiting operator and reviewer ACK. Nothing in this document is live
except the prototype from PR #3505 (a draft), listed under "Prototype state".
**Lane:** `feat/agent-inbox-road`. Control: B850-CLAUDE (Knuckles).
**Parent intent:** `pmoves/docs/architecture/EVOLUTION_FABRIC_RFC.md:127` ("maintain the
persistent NATS inbox before cross-node delegation is considered reliable"), `:335`, `:356`;
`pmoves/configs/tac_trees/evolution-fabric.tac.yaml:100` (`spark_persistent_inbox_verified`);
Grand Convergence design rule D4 (every agent has at least one direct NATS subscription);
`PMOVES_MOF_ARCHITECTURE.md:204` ("Every agent must have NATS pub/sub capability beyond
hierarchical parent-child communication").

This is not a new lineage. The inbox has been a precondition for SPARK and for reliable
cross-node delegation since 2026-08-04 and was never built.

## 1. What already exists (reuse, do not rebuild)

| Piece | Where | State |
|---|---|---|
| Addressed task envelope + alias routing | `pmoves/tools/orchestrator.py:58,147,202`, `pmoves/tools/agent_task_subscriber.py` | Core pub/sub, not durable. Its docstring: "routing tables are hints -- nothing dispatches to a node until a subscriber like this is running". |
| Common event envelope | `pmoves/contracts/schemas/common/envelope.schema.json` | Required: id, topic, ts, version, source, payload. `additionalProperties:false`, and **no `sig` field** (gap, see 4). |
| CHIT signing / verification | `pmoves/tools/sign_trail.py` -> `chit_security.sign_cgp`; `chit_security.py:347 verify_cgp_detailed` | Signs with HMAC-SHA256 under a `kid`. It is a deployment-wide key until per-agent keys exist, which makes it **attribution, not authentication** (#3317 is the authentication lane). |
| Identity | `pmoves/tools/node_identity.py` (`resolve_identity`, `resolve_cipher_agent_id`), `pmoves/config/signing_identity_cards.yaml` | Card `agent_id` is the sender key. Alters (e.g. `b850-ledger`) are presentation only and are never the sender. |
| Stream provisioning | `pmoves/scripts/nats/init_streams.sh` (+ `validate_streams.py`) | Canonical creator (ROOMS, HELPDESK, ARCHON, ...). Agent Zero creates only `AGENTZERO` (`services/agent_zero/controller.py:414-440`). |
| Tokenism credit hook | `tokenism.attribution.recorded.v1` (PMOVES-ToKenism-Multi `chit-nats-publisher.ts:258-275`; live producer `services/semantic-cache/tokenism.py`) | Can attribute a delivered message: address = sender card id, action = `message.delivered`, category = room. |
| Rooms | `pmoves/config/rooms/catalog.json`, `ROOMS` stream on `room.>`, `room.session.updated.v1` | Stage-lifecycle events only. No room membership, no messaging, and no durable ROOMS consumer in the repo. |
| Review-request protocol | `pmoves/docs/operations/PAIR_REVIEW_RECIPROCITY.md:124-155`, `KRISS_KROSS_ACCORD.md:28-52` | Any AGInT may request a review. The deliverable and the `ACK::` lines are defined; there is **no request message**, which this inbox would carry. |

## 2. Measured facts this design rests on (knuckles, 2026-11-21)

- nats-server **2.11.8** (`nats:2.11.8-alpine`). Upstream latest is v2.15.3. Upgrading is a separate, tested change.
- One account (`$G`) plus `$SYS`: no leaf nodes, cluster, websocket or MQTT. The accounts/leaf topology
  (`pmoves/docs/specs/nats-accounts-leaf-topology-v0-spec-2026-08-07.md`) is design only.
- **Broad subscribers exist:** `services/nats-echo/nats_echo.py:38` defaults to `>`, and
  Agent Zero's events bus supports `pmoves.>` (`subjects.py:87`) and subscribes `pmoves.agent.>` (`bus.py:24`).
- 12 streams; subjects are disjoint. `mesh.gpu.>` is the only `mesh.*` stream.

**Consequence: confidentiality is not achievable by subject naming.** In a single
account, any connection can subscribe to `>`. Until NATS accounts and per-user subject permissions
are live, **inbox messages are not private**: no secrets in bodies, and the docs and the `read` output
must say so. Privacy is a property of the account topology (Open decision A below), not of this tool.

## 3. Design

### 3.1 Subjects (outside Agent Zero's namespace)

- Agent inbox: `mesh.inbox.agent.<agent_id>.v1`
- Room inbox (fan-out): `mesh.inbox.room.<room_id>.v1`

These are not under `pmoves.agent.>` (Agent Zero) or `room.>` (owned by the ROOMS stream; a subject
can belong to only one stream). They are registered in `.claude/context/nats-subjects.md`. The
`topics.json` row needs the schema below first (KNOWN_ROAD=schema grant).

### 3.2 Stream (one creator)

`AGENT_INBOX` on `mesh.inbox.>`: file storage, limits retention, max age 14d, size cap, 2-minute dedup window.
It is created **only** by `init_streams.sh`, and `validate_streams.py` checks it, including retention, storage
and max age. The inbox tool never creates the stream: it calls `stream_info` and exits 3 when the stream is absent.
Per-agent durable consumers stay create-only in the tool. Each filters on its own agent subject plus the room
subjects it has joined; multi-filter consumers arrived in nats-server 2.10 and must be measured on 2.11.8 before relying on them.

When the NATS fork family is organized (section 6), this block moves into the declarative stream
manifest in the `PMOVES-nats-server` overlay, alongside every other stream.

### 3.3 Envelope (common schema + CHIT)

```
{ id, topic: <subject>, ts, version: "v1", source: <node>,
  actor: <signing-card agent_id>, correlation_id, parent_id,
  payload: { to: [<agent_id>|room:<room_id>, ...], body, reply_to },
  sig: { alg, kid, hmac } }
```

- The sender is resolved with `node_identity.resolve_identity`. A `--from` that disagrees is refused.
- Each recipient must exist in `signing_identity_cards.yaml` or `catalog.json`; an unknown recipient exits 1.
- Signed with `sign_cgp(kid=actor)`. The receiver runs `verify_cgp_detailed` and stores the status with the record.
  `read` shows `OK_UNPINNED` as "deployment-attested", never as proof of the sender. `MISMATCH` and
  `NO_SIGNATURE` are quarantined and not shown as instructions.
- `reply_to` must be an inbox subject; any other subject is refused.
- **Gap:** `envelope.schema.json` has no `sig`. Either amend it, or add `agent-inbox/message.v1.schema.json`
  extending it. Both are protected (KNOWN_ROAD=schema grant).

### 3.4 Fan-out

Publish once per recipient subject with `Nats-Msg-Id = <actor>:<recipient>:<id>` and a shared
`correlation_id`. A duplicate ack exits 1. Room fan-out publishes to the room subject, and members'
consumers filter on it. Membership comes from the room catalog, with the manifest's `allowed_subjects`
as a ceiling that is never widened (`ROOM_MANIFEST_CONTRACT.md:240-278`).

### 3.5 Operator room (OpenRoom)

There is no NATS path into PMOVES-OpenRoom today: it reads HTTP (`/api/rooms`, `/api/p7/*`). A bridge
would consume `mesh.inbox.room.<operator_room>.v1` and expose it through a read route. `darkxsides.room`
is private, owner-only and at rehearsal, so **mirroring into it is an operator decision** (Open decision C).

### 3.6 Reading at turn start

`agent-inbox-read AGENT=<id>` prints messages newer than the cursor and moves the cursor only
after printing succeeds. The cursor uses an fcntl lock and mkstemp. The subscriber writes a heartbeat, and
read exits 3 when it is stale. Harness wiring (a Claude Code hook, Crush prompt wiring) is a follow-up lane.

### 3.7 Credit

On delivery, optionally emit `tokenism.attribution.recorded.v1` (address = actor,
action = `message.delivered`, category = room or `direct`, chit_id = message id). This is off by default,
and the ToKenism owner must review it before it is turned on.

## 4. PR #3505 disposition

**Keep:** create-only stream and consumer with refuse-on-drift; durable explicit-ack pull consumers; fsync
before ack; the cursor's complete-line reads and rotation reset; `url_shape` and the rule that errors never
print the URL; exit-3 mapping; removal of the 5090-CODEX default; the installer's `env -i` probe and its
`set --` fix before sourcing with-env.sh; the Linger warning.

**Rework, in order** (from the code-review of 2026-11-21: 2 P1, 8 P2, 6 P3):
1. Namespace to `mesh.inbox.*` (P1, Agent Zero overlap).
2. Stream creation moved to `init_streams.sh` and `validate_streams.py`.
3. Identity resolved through the cards; recipients checked against them.
4. Envelope plus CHIT signing and verification (P1, self-asserted sender), plus the schema grant.
5. Fan-out with per-recipient message ids and room subjects.
6. P2 fixes: duplicate ack exits 1; cursor after print; fcntl lock and mkstemp; heartbeat staleness;
   `RestartPreventExitStatus=1` and refuse installs from a worktree; existence check compares retention.
7. **Remove the Cipher `to:<agent>` fallback**: cipher search is scoped to the caller's agentId, so the
   recipient never sees it.
8. Tests that drive `run_send` and `run_inbox` against an in-process fake and fail on behaviour,
   not on missing symbols.

## 5. Prototype state (live on knuckles, made before the design review)

- Stream `AGENT_INBOX` on `pmoves.agent.inbox.*.v1` (2 test messages, no secrets); consumers
  `inbox-b850-claude` and `inbox-crush`.
- Enabled user units `pmoves-agent-inbox@{b850-claude,crush}.service`, running worktree code.
- **No one sends through it until rework step 1 lands**, because those subjects are inside `pmoves.agent.>`.
- Retirement (operator decision D): `systemctl --user disable --now` both units; removing the stream is an
  operator action (the guard blocks `nats stream delete`).

## 6. NATS fork family (scope for a sibling lane)

Inventory: 110 tracked NATS paths. Duplicates: `GEOMETRY_CGP` has three creators (`init_streams.sh:103`,
`setup_geometry_streams.sh:54`, `geometry_bus_stream.py:128`); `TOKENISM_ATTRIBUTION` and `BOTZ_COORDINATION`
are created only by the geometry script and are missing from `validate_streams.py`. There are four leaf configs.
Compose mounts the monorepo `pmoves-nats.conf` over the fork's baked one.

Proposed layout:
- **`PMOVES-nats-server` overlay `pmoves/`**: conf/ (hub, leaf), streams/ (one declarative manifest, the single creator), scripts/ (init, validate, tls), topology/ (the spec), compose fragments.
- **`pmoves-nats-mcp`** promoted to its own fork, linked as a gitlink.
- **`Pmoves-nats.py`**: the shared client helpers (`common/nats_client.py` etc.) as a package.
- **`PMOVES-natscli-CHIT-EeZz`**: CLI and capability helpers.
- **`Pmoves-nats-architecture-and-design`**: specs and ADR-style records.

Service publishers and consumers stay in the monorepo. Order: single stream creator -> inbox as a
manifest entry -> server upgrade 2.11.8 -> 2.15.x (separate, tested) -> re-sync `PMOVES-nats-server` (1 behind upstream).

## 7. Open decisions

- **A. NATS credential and account target** (open since 2026-10-07). Spark-local credentials (tactical), or the 5090
  hub plus leaf nodes with accounts (strategic). Only B gives cross-node inboxes, privacy through subject
  permissions, and `agent.peer.heartbeat.v1`. **Provenance gap:** the register (`AGNOTE4482PHI.t1.md:3445`)
  cites `reviews/NATS_DUAL_DESIGN_REVIEW_2026-10-07.md`, which is in neither the tree nor git history.
- **B. Where the "CHIT underneath every protocol" principle is recorded.** It is operator intent, but the MOF and Grand
  Convergence docs place CHIT at L2 (information) and NATS at L3 (transport); A2A, ACP and MCP get no layer.
  This design applies CHIT per message. Recording the principle in the architecture docs is a separate edit.
- **C. Operator room.** Mirror into `darkxsides.room`, a separate operator room, or none yet.
- **D. Prototype.** Keep running until the rework lands, or stop the two units now.

## 8. Reviewers (PAIR_REVIEW_RECIPROCITY protocol)

- Stream layout and provisioning: the owner of `init_streams.sh`, via Agent Zero's lane (`agent0-sidecar`, which ran
  the 2026-10-07 fleet comms lane).
- New subjects: `nats-subject-auditor`.
- Signing and verification: `chit-compliance-reviewer`.
- Credit hook: the ToKenism owner.
- Operator room: the operator.

Each reviewer posts a PR comment ending `ACK::<reviewer>::AGENT-INBOX-ROAD-REVIEW-2026-11-21`
and appends a REVIEW row.

## Provenance

Research on 2026-11-21 by four read-only agents dispatched by B850-CLAUDE: the PR #3505 code-review, the NATS fork family
and topology, CHIT, MOF and Tokenism, and comms plan docs including archived and deleted ones. Prior reviews:
`reviews/FLEET_COMMS_PROTOCOLS_2026-10-07.md`, `reviews/ACP_FORKS_NATS_TOPOLOGY_REVIEW_2026-10-07.md`.
