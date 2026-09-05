# PMOVES Fleet Sentinel

The registry consumer that connects the autonetwork primitives: announce listener →
health poller → Known-Road self-heal → `/registry.json` for Pinokio/CLI/A2UI consumption.

## What it closes

Services could already announce on `services.announce.v1` and a registry class existed —
but nothing consumed the registry to drive launchers, health-watch, or self-heal. The
sentinel is that consumer (design: `docs/services/IDE_PINOKIO_FLEET_CONSOLE_PLAN.md`).

## Environment

| Variable | Default | Description |
| --- | --- | --- |
| `NATS_URL` | `nats://nats:pmoves@nats:4222` | NATS bus (announce subject) |
| `SENTINEL_POLL_INTERVAL` | `30` | Health poll seconds |
| `SENTINEL_FAILURE_THRESHOLD` | `3` | Consecutive failures before restart |
| `SENTINEL_RESTART_COOLDOWN` | `600` | Min seconds between restarts per service |
| `SENTINEL_SELF_HEAL` | `1` | Enable Known-Road restarts (`0` = observe-only) |
| `SENTINEL_PMOVES_DIR` | `/srv/pmoves` | pmoves checkout for make invocations |
| `SENTINEL_ACTION_TRAIL` | `/data/fleet-sentinel/actions.jsonl` | Append-only restart trail |

## API (port 8116)

- `GET /healthz` — sentinel status + listener state + service count
- `GET /registry.json` — the Pinokio/A2UI consumption surface (slug, url, tier, health, port per service)
- `GET /actions` — restart history (last 100)

## Self-heal contract

The ONLY restart path is the Known Road: `bash scripts/with-env.sh make secrets-funnel &&
make up-<slug>` — never raw `docker restart` (bypasses env re-projection; damage-control
blocks it for exactly that reason). Rate-limited to one restart per service per cooldown;
every action appended to the jsonl trail (known-roads.jsonl discipline).

## Consumers

- **Pinokio** `pmoves-services` launcher: fetch `/registry.json`, render menu rows with
  ServiceTier icons, health chips; status.js curls health_check URLs directly
- **CLI**: `make fleet-registry` (showtime family) prints the same JSON
- **A2UI**: `pm-service-registry` web component (separate PR) binds registry.json
