# NATS Configuration — PMOVES.AI

## Overview

NATS is the JetStream-enabled event broker and primary message bus for all
inter-service coordination in PMOVES.AI.  Every agent, worker, and orchestrator
communicates through NATS subjects.

- **Image:** `nats:2.11.8-alpine`
- **Client port:** 4222 (`${NATS_PORT:-4222}:4222`)
- **Monitoring:** container port 8222, published on the host as 9223 by default (`${NATS_MONITORING_PORT:-9223}:8222`). The in-container healthcheck dials `wget http://localhost:8222/varz`; host-side probes must use the published port (see [NATS monitor port](#nats-monitor-port)).
- **JetStream:** enabled (`-js` flag)
- **Auth:** `--user ${NATS_USER:-nats} --pass ${NATS_PASSWORD:-pmoves}`
- **WebSocket:** not configured in main compose (available in DoX standalone at 9222/9223)

## Standard Configuration

```bash
NATS_URL=nats://nats:pmoves@nats:4222
```

Authentication is mandatory.  The NATS server is started with `--user nats
--pass pmoves`.  All clients must include credentials in the connection URL.

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

Created by `nats-init` sidecar (`pmoves/scripts/nats/init_streams.sh`):

| Stream                 | Subject         | Retention | Max Age | Max Size | Notes |
|------------------------|-----------------|-----------|---------|----------|-------|
| `GEOMETRY_CGP`         | `geometry.>`    | limits    | 30d     | 1 GB     | CGP schema events, swarm signals |
| `TOKENISM_ATTRIBUTION` | `tokenism.>`    | interest  | 90d     | 2 GB     | **Migration risk**: existing stream uses `interest`; the silent-discard hazard (no bound consumer = message vanished) is documented inline. Lane 5 (2026-08-01) added new streams with `limits` to avoid the same pitfall. |
| `BOTZ_COORDINATION`    | `botz.>`        | limits    | 7d      | 500 MB   | BoTZ gateway skill events |
| `MESH_GPU`             | `mesh.gpu.>`    | limits    | 7d      | 1 GB     | DGX Spark GB10 GPU mesh |
| `CONTENT_PROVENANCE`   | `content.>`     | limits    | 90d     | 2 GB     | SPARK shaped packets / provenance |
| `COMFY_COLLAB`         | `comfy.collab.>`| limits    | 7d      | 1 GB     | **Lane 5 added** — Creator Collab slice 3 (`comfy.collab.{prompt,progress,artifact}.v1`); without this, comfy-watcher publishes vanished |
| `ROOMS`                | `room.>`        | limits    | 7d      | 500 MB   | **Lane 5 added** — P7 room presence/directory/manifest; `p7.room.*` is intentionally separate (see init script) |
| `HELPDESK`             | `helpdesk.>`    | limits    | 30d     | 1 GB     | **Lane 5 added** — PMOVES-helpdesk intake/routed/room-suggested audit ledger |

## NATS monitor port

The NATS HTTP monitor (`/varz`, `/connz`, `/jsz`, `/healthz`) listens on **8222
inside the container**. What answers on the **host** depends on the node's compose
layout, and on most nodes host 8222 refuses the connection. A refused 8222 from the
host therefore says nothing about whether NATS is up or who is subscribed.

| Layout | Compose source | Host port | ports.yaml slot |
|--------|----------------|-----------|-----------------|
| Default (base compose; the VPS/KVM override inherits it) | `docker-compose.yml`: `${NATS_MONITORING_BIND:-127.0.0.1}:${NATS_MONITORING_PORT:-9223}:8222` | **9223** | `NATS_MONITORING_PORT` |
| Z890 leaf | `docker-compose.z890.yml`: `127.0.0.1:${NATS_LEAF_8222_PORT:-8222}:8222` | **8222** | `NATS_LEAF_8222_PORT` |
| Jetson edge leaf | `docker-compose.jetson-edge.override.yml` publishes 4222 only | none | none |
| Standalone cipher stack | `pmoves/scripts/start-cipher-stack.sh` runs its own NATS with `-p 8222:8222` | **8222** | none |

`NATS_MONITORING_BIND` can also move the host off loopback. Do not hardcode either
half. Ask Docker instead, from the repo root:

```bash
NATS_MONITOR_URL=$(bash .claude/scripts/nats-endpoint.sh) || echo "assumed, not measured: $NATS_MONITOR_URL"
curl -s "$NATS_MONITOR_URL/varz"
```

The script exits 0 with the URL it read from `docker port`, or exits 1 with the
default (`http://localhost:9223`) when it could not measure. `NATS_MONITOR_URL` is
used here instead of `NATS_URL` because `NATS_URL` is the `nats://` client URL
everywhere else in the stack.

New host-side loopback URLs on port 8222 under `pmoves/docs/` and
`pmoves/configs/` fail
`pmoves/tests/tools/test_nats_monitor_host_port_ratchet.py`. Legitimate uses
(in-container healthchecks, the Z890 layout) are allowlisted there with a reason.

## Debugging

### Check NATS health

8222 is the container-side monitor port; on most nodes it does not answer on the
host. Derive the host URL first (run from the repo root; see
[NATS monitor port](#nats-monitor-port)):

```bash
NATS_MONITOR_URL=$(bash .claude/scripts/nats-endpoint.sh)
curl -s "$NATS_MONITOR_URL/varz"
```

### List active connections

```bash
curl -s "$NATS_MONITOR_URL/connz"
```

### Verify JetStream streams

```bash
docker exec pmoves-nats-1 nats stream ls --server=nats://nats:pmoves@localhost:4222
```

### Publish a test message

```bash
nats pub "test.ping.v1" '{"ts": "'$(date -Iseconds)'"}'  \
  --server=nats://nats:pmoves@localhost:4222
```

### Common issues

- **Connection refused:** Verify NATS container is healthy (`docker inspect
  pmoves-nats-1 --format '{{.State.Health.Status}}'`)
- **Auth failure:** Ensure `NATS_URL` includes `nats:pmoves@` credentials
- **Missing stream:** Run `nats-init` sidecar to recreate JetStream streams
