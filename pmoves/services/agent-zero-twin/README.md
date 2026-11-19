# PMOVES-Agent-Zero Standalone Digital Twin

Status: DRAFT v2 (2026-10-08). v2 adds the ingestion + grounding layer — see INGESTION-GROUNDING.md. Host research verified via A0 CLI (read-only); compose now attaches external host networks pmoves_app/pmoves_bus/pmoves_data and adds ring-ingest (twin-ingest worker). Still blocked on host repo placement + commit.

## Answers baked into this design

1. **Corrected images/compose**: the twin runs the SAME corrected image as prod
   (`pmoves-agent-zero:latest` = `sha256:b2358c0d...`, `P 3290759`, branch pin
   `AGENT_ZERO_REF=PMOVES.AI-Edition-Hardened`). The compose ref-pin fix from
   2026-10-03 is the same change this stack carries forward.

2. **SPARK == DARKXSIDE instance?** YES. SPARK is the standalone
   instance at `127.0.0.1:8092` (container `pmoves-agent-zero-darkxside`,
   `pmoves-agent-zero:latest`). It already runs the corrected image, so the twin
   is SPARK's parity target: same image, same connection surfaces, portable host.

3. **Standalone == same connections, anywhere**: every integration is a
   **profile (ring)** — the twin boots on any hardware/OS with whatever rings
   the host supports, and never fails just because a ring is missing.

## Ring model — "Ferris wheels with ferromagnetic rings"

The metaphor maps 1:1 to the dependency architecture:

| Metaphor | Architecture |
|---|---|
| Concentric wheels around the hub | dependency rings around the agent core (ring-0 = agent-zero) |
| Ferromagnetic rings, concentric but multiple | sidecars attach via the `pmoves-twin-net` bridge; multiple rings co-exist without touching |
| Spin / harmonic resonance | each ring runs at its own cadence: healthcheck intervals + event loops |
| The jiggle == van der Waals contact | rings never hard-bind; they couple loosely through network aliases. The health-probe latency wiggle is the coupling signal — fleet-sentinel watches it the way LDF watches dispersion forces |
| Jev sparse image | rings stay sparse: `profiles:` keeps unused rings out of memory/disk; the hub runs even bare |
| Prosodic evo listener router | NATS ring-3 subjects (`agentzero.task.v1`, `agentzero.memory.update`) are the rhythm channel; router evolves subscriptions per load |
| CHIT renderer | ring-4 on-demand jobs: secrets materialization + docs-constellation rendering, invoked when a ring joins |

## Hardware/OS adaptation

- `TWIN_GPU=auto` — detects nvidia runtime; falls back to CPU inference lane.
- `TWIN_DOCKER_SOCK` — Linux socket default; Windows pipe override in `.env`.
- `TWIN_RING_*=auto` — auto-detect which rings the host can support.

## Bring-up

```bash
# full resonance (all rings)
docker compose -f docker-compose.twin.yml --profile ring-llm --profile ring-memory --profile ring-bus up -d
# hub only (sparse Jev state)
docker compose -f docker-compose.twin.yml up -d
```

## TODO before merge
- [ ] place under `pmoves/services/agent-zero-twin/` in PMOVES.AI (needs CLI)
- [ ] generate `env/` from the CHIT funnel (never copy tier files by hand)
- [ ] init-a0.sh parity check: instruments/knowledge binds like prod mounts
- [ ] fleet-sentinel jiggle probe: scrape ring healthz latencies
- [ ] compose-provenance-audit registration for the new build stanza
