# NATS Configuration — PMOVES.AI

## Overview

NATS is the JetStream-enabled event broker and primary message bus for all
inter-service coordination in PMOVES.AI.  Every agent, worker, and orchestrator
communicates through NATS subjects.

- **Image:** `nats:2.11.8-alpine`
- **Client port:** 4222 (`${NATS_PORT:-4222}:4222`)
- **Monitoring:** 8222 (internal only — used by healthcheck: `curl http://localhost:8222/varz`)
- **JetStream:** enabled (`-js` flag)
- **WebSocket:** not configured in main compose (available in DoX standalone at 9222/9223)

## Standard Configuration

```
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

## JetStream Streams

Created by `nats-init` sidecar (`pmoves/scripts/nats/init_streams.sh`):

| Stream                 | Subject      | Retention | Max Age | Max Size |
|------------------------|--------------|-----------|---------|----------|
| `GEOMETRY_CGP`         | `geometry.>` | limits    | 30d     | 1 GB     |
| `TOKENISM_ATTRIBUTION` | `tokenism.>` | interest  | 90d     | 2 GB     |
| `BOTZ_COORDINATION`    | `botz.>`     | limits    | 7d      | 500 MB   |

## Debugging

### Check NATS health

```bash
curl http://localhost:8222/varz
```

### List active connections

```bash
curl http://localhost:8222/connz
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
