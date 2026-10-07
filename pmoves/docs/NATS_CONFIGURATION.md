# NATS Configuration — PMOVES.AI

## Overview

NATS is the JetStream-enabled event broker and primary message bus for all
inter-service coordination in PMOVES.AI.  Every agent, worker, and orchestrator
communicates through NATS subjects.

- **Image:** `nats:2.11.8-alpine`
- **Client port:** 4222 (`${NATS_PORT:-4222}:4222`)
- **Monitoring:** container port 8222, published on the **host as 9223**
  (`${NATS_MONITORING_BIND}:${NATS_MONITORING_PORT:-9223}:8222`, bind defaults to loopback).
  From the host use `http://localhost:9223/...`; `localhost:8222` only works *inside*
  the container (that is what the compose healthcheck uses). Node overlays may
  differ — `docker-compose.z890.yml` publishes the monitor on host port 8222 (loopback) — so check
  `docker port pmoves-nats-1` when in doubt.
- **JetStream:** enabled (`-js`, store `--store_dir /data/js` on the `pmoves-nats-js` volume)
- **Auth:** single user/password from `NATS_USER` / `NATS_PASSWORD` (`--user` / `--pass` flags).
  Compose carries fallback defaults so a blank env still boots; those defaults are
  for local bring-up only and **MUST be overridden per node** via the secrets
  funnel (`make -C pmoves secrets-funnel`).
- **WebSocket:** not configured in main compose (available in DoX standalone at 9222/9223)

## Standard Configuration

```bash
NATS_URL=nats://<user>:<password>@nats:4222            # in-stack (pmoves_bus)
NATS_URL=nats://<user>:<password>@pmoves-kvm4-2:4222   # fleet hub (tailnet-only)
```

Authentication is mandatory.  The NATS server is started with `--user
"$NATS_USER" --pass "$NATS_PASSWORD"`.  All clients must include credentials in
the connection URL; read it from `$NATS_URL` rather than hard-coding a literal
value in code, docs, or editor configs.

The fleet hub is reached by its Tailscale MagicDNS name `pmoves-kvm4-2`.
`nats.pmoves.ai` is a reserved name that does not currently resolve — do not
point clients at it.

## Environment Variable Sources

NATS credentials follow the **tier isolation model**.  The `NATS_URL` variable
is defined in tier-specific env files, not in `env.shared`:

| Tier file          | Services                                        |
|--------------------|-------------------------------------------------|
| `env.tier-agent`   | agent-zero, archon, mesh-agent                  |
| `env.tier-worker`  | comfy-watcher, extract-worker, ffmpeg-whisper    |
| `env.tier-ui`      | pmoves-ui, a2ui                                 |

Reference credentials are kept in `env.shared` as `NATS_USER` and
`NATS_PASSWORD` for bootstrap scripts.

## Common Subjects

Full catalog: `.claude/context/nats-subjects.md`

| Subject                              | Publisher         | Purpose                    |
|--------------------------------------|-------------------|----------------------------|
| `ingest.file.added.v1`               | PMOVES.YT         | New file ingested          |
| `ingest.transcript.ready.v1`         | ffmpeg-whisper     | Transcript completed       |
| `research.deepresearch.request.v1`   | SupaSerch / UI     | Research task request      |
| `mesh.gpu.status.v1`                 | gpu-orchestrator   | GPU heartbeat (5s)         |
| `claude.code.tool.executed.v1`       | Claude Code hooks  | CLI tool telemetry         |
| `agent.graphiti.signed.v1`           | BoTZ gateway       | Agent trail attribution    |
| `geometry.cgp.v1`                    | Tokenism           | CGP schema events          |
| `geometry.swarm.meta.v1`            | Tokenism           | Swarm meta signals         |
| `tokenism.cgp.ready.v1`             | Tokenism Simulator | CGP readiness              |
| `tokenism.simulation.result.v1`     | Tokenism Simulator | Simulation results         |
| `botz.skill.registered.v1`          | BoTZ gateway       | Skill registration         |
| `comfy.collab.prompt.v1`             | comfy-watcher, comfyui, creator-canvas-primary | Creator Collab slice 3 prompt (COMFY_COLLAB stream) |
| `comfy.collab.progress.v1`           | comfy-watcher, comfyui | Creator Collab slice 3 progress (COMFY_COLLAB stream) |
| `comfy.collab.artifact.v1`           | comfy-watcher, comfyui | Creator Collab slice 3 artifact (COMFY_COLLAB stream) |
| `room.presence.v1`                  | p7-room-orchestrator, notebook-workbench, creator-canvas-primary | P7 room presence (ROOMS stream) |
| `room.directory.v1`                 | p7-room-orchestrator | P7 room directory snapshot (ROOMS stream) |
| `helpdesk.intake.opened.v1`          | pmoves-helpdesk-skill | Helpdesk intake opened (HELPDESK stream) |
| `helpdesk.intake.routed.v1`          | pmoves-helpdesk-skill | Helpdesk intake routed (HELPDESK stream) |
| `helpdesk.room.suggested.v1`         | room-suggest-skill | Helpdesk suggested a room (HELPDESK stream) |

## JetStream Streams

Created by the `nats-init` one-shot (`pmoves/scripts/nats/init_streams.sh`).
This table mirrors the `add_stream` calls in the script **body** (not its header
comment). Every stream uses `--storage file --discard old --replicas 1`.

| Stream                 | Subject          | Retention | Max Age (`--max-age`) | Max Size (`--max-bytes`) | Notes |
|------------------------|------------------|-----------|-----------------------|--------------------------|-------|
| `GEOMETRY_CGP`         | `geometry.>`     | limits    | 30d (`720h`)          | 1 GiB (`1073741824`)     | CGP schema events, swarm signals |
| `TOKENISM_ATTRIBUTION` | `tokenism.>`     | limits    | 90d (`2160h`)         | 2 GiB (`2147483648`)     | Attribution ledger. Retention is immutable after creation: a node whose stream predates the switch to `limits` keeps `interest` until the stream is removed (only when empty) and re-created — see the migration note in the script. |
| `BOTZ_COORDINATION`    | `botz.>`         | limits    | 7d (`168h`)           | 500 MB (`524288000`)     | BoTZ gateway skill events |
| `MESH_GPU`             | `mesh.gpu.>`     | limits    | 7d (`168h`)           | 1 GiB (`1073741824`)     | DGX Spark GB10 GPU mesh |
| `CONTENT_PROVENANCE`   | `content.>`      | limits    | 90d (`2160h`)         | 2 GiB (`2147483648`)     | SPARK shaped packets / provenance |
| `COMFY_COLLAB`         | `comfy.collab.>` | limits    | 7d (`168h`)           | 1 GiB (`1073741824`)     | Creator Collab slice 3 (`comfy.collab.{prompt,progress,artifact}.v1`) |
| `ROOMS`                | `room.>`         | limits    | 7d (`168h`)           | 500 MB (`524288000`)     | P7 room presence/directory/manifest; `p7.room.*` is intentionally separate (see init script) |
| `HELPDESK`             | `helpdesk.>`     | limits    | 30d (`720h`)          | 1 GiB (`1073741824`)     | PMOVES-helpdesk intake/routed/room-suggested audit ledger |
| `ARCHON`               | `archon.>`       | limits    | 30d (`720h`)          | 512 MiB (`536870912`)    | `archon.mint.*` governance records (agent/skill/creator/confirmed) |

> The validator (`pmoves/scripts/nats/validate_streams.py`) keeps its own
> `EXPECTED_STREAMS` list "in sync with init_streams.sh". At the time of writing
> it still records `interest` for `TOKENISM_ATTRIBUTION` (the legacy value). The
> script body above is the source of truth for what gets created.

### How streams get created on each node

Streams are **per broker**. Each node that runs its own `nats` service needs
them created locally; they are not replicated from the hub.

1. **`nats-init` one-shot.** `make -C pmoves overlay-up-bus` runs
   `up -d nats nats-init` (base + core overlays). `nats-init` is a
   `natsio/nats-box` container that waits for `nats` to be healthy, runs
   `init_streams.sh` (idempotent — existing streams are left as-is), and exits.
   Services such as agent-zero, p7-room-orchestrator and botz-gateway gate on
   `nats-init: service_completed_successfully`. To re-run the script by hand:
   `make -C pmoves nats-streams-init`.
2. **Verify.** `make -C pmoves nats-streams-validate` lists the streams via
   nats-box and asserts every expected stream is present
   (`make -C pmoves nats-streams-list` for an ad-hoc listing).

A node that is **missing a stream** still accepts core-published messages on
that subject family, but with no stream (and no live subscriber) the message is
not stored — it is silently dropped and the publisher gets no error. After any
bring-up, `nats-streams-validate` is the check that confirms a node will retain
events.

## Accounts / leaf hub (`nats-hub`, profile-gated)

`pmoves/docker-compose.core.yml` also defines a **`nats-hub`** service that is
**off by default** (compose profile `nats-hub`). It is the accounts/leafnode hub
from the v0 spec (§9 Phase 2), built from the `PMOVES-nats-server` fork
(`../PMOVES-nats-server/pmoves`, image `ghcr.io/powerfulmoves/pmoves-nats:pmoves-latest`):

- **Accounts:** four trust zones (SYS / CORE / EDGE / CLOUD) loaded through a
  **memory resolver** (`resolver: MEMORY` + `resolver_preload`) from nsc-minted
  account JWTs, configured by the mounted `pmoves/config/nats/pmoves-nats.conf`
  (which carries the required `operator:` directive).
- **Leafnodes:** listener on **7422** for EDGE/CLOUD leaf attachment
  (4222 remains the client port; leaves must use 7422).
- **Monitoring:** loopback-only by default on its own bind var
  (`NATS_HUB_MONITORING_BIND`), host port 9223 → container 8222.
- **Trust material** is funnel-rendered; the fork entrypoint fails fast without it.

The default `nats` service remains the flag-launched single-principal bus until
the operator cuts over. Rollout phases, gates and acceptance tests:
[`operations/NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md`](operations/NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md).

## Debugging

### Check NATS health

```bash
# host port 9223 -> container 8222 (loopback bind by default)
curl http://localhost:9223/varz
curl http://localhost:9223/jsz      # JetStream summary
```

### List active connections

```bash
curl http://localhost:9223/connz
```

### Verify JetStream streams

```bash
make -C pmoves nats-streams-validate   # asserts the expected streams exist
make -C pmoves nats-streams-list       # ad-hoc listing via nats-box
```

### Publish a test message

```bash
make -C pmoves nats-pub SUBJECT=test.ping.v1 PAYLOAD='{"ts":"2026-10-07T00:00:00Z"}'
# or, with the nats CLI and your env loaded:
nats pub "test.ping.v1" '{"ts": "'$(date -Iseconds)'"}' --server="$NATS_URL"
```

### Common issues

- **Connection refused:** Verify NATS container is healthy (`docker inspect
  pmoves-nats-1 --format '{{.State.Health.Status}}'`)
- **Auth failure:** Ensure `NATS_URL` includes `<user>:<password>@` credentials
  matching this node's `NATS_USER` / `NATS_PASSWORD`
- **Missing stream:** Run `make -C pmoves nats-streams-init` (or re-run the
  `nats-init` one-shot), then `make -C pmoves nats-streams-validate`
