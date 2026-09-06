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
| `SENTINEL_POLL_CONCURRENCY` | `16` | Max concurrent health probes per cycle |
| `SENTINEL_HTTP_TIMEOUT` | `5` | Per-probe timeout seconds |
| `SENTINEL_FAILURE_THRESHOLD` | `3` | Consecutive failures before restart |
| `SENTINEL_RESTART_COOLDOWN` | `600` | Min seconds between restarts per service |
| `SENTINEL_STALE_FACTOR` | `2.0` | Multiple of a declared announce interval before `stale` |
| `SENTINEL_SELF_HEAL` | `1` | Enable Known-Road restarts (`0` = observe-only) |
| `SENTINEL_HEAL_ALLOWLIST` | *(unset)* | Comma-separated slugs eligible for self-heal; unset = any slug matching the slug pattern |
| `SENTINEL_PMOVES_DIR` | `/srv/pmoves` | Mounted **repo root**; the Makefile is resolved at `<dir>/pmoves/Makefile` |
| `SENTINEL_ACTION_TRAIL` | `/data/fleet-sentinel/actions.jsonl` | Append-only restart trail |

## API (port 8116)

- `GET /healthz` — `listener_mode`, `listener_connected`, `listener_error`, service count,
  and `self_heal` (`operational` \| `unavailable`) with `self_heal_reason`
- `GET /registry.json` — the Pinokio/A2UI consumption surface (slug, url, tier, health, port per service)
- `GET /actions` — restart history (last 100), each entry carrying `status`
  (`executed` \| `deferred` \| `refused` \| `error`)

## Untrusted input: the slug boundary

A slug arrives from a NATS announcement, so anyone able to publish on
`services.announce.v1` controls it, and it ends up in an argv position of a `make`
invocation. It is guarded by an **allowlist**, not a denylist:

```
^[a-z0-9][a-z0-9-]{0,63}$
```

DNS-label shape only. Anchored with `^...$` and no `re.MULTILINE`, and the character
class excludes newline, so a payload cannot smuggle a second line past the match. The
restart path builds a **fixed argv** through `asyncio.create_subprocess_exec` — there is
no shell, so metacharacters have no interpreter to reach even if the pattern were widened.
Because the whole argument is `up-<slug>` and the pattern forbids a leading `-`, a slug
can never be read by `make` as an option. `known_road_restart()` re-applies the pattern at
its own entry rather than trusting its caller (fail-closed), and refuses with a recorded
`status: refused` action.

## Self-heal contract, and when it is NOT operational

The ONLY restart path is the Known Road: `bash scripts/with-env.sh make secrets-funnel`
then `make up-<slug>` — never raw `docker restart` (bypasses env re-projection;
damage-control blocks it for exactly that reason). Rate-limited to one attempt per
service per cooldown; every action is appended to the jsonl trail.

The container is deliberately built **without a Docker socket** — a sentinel holding the
socket would be a fleet-wide privilege escalation. `python:3.12-slim` also ships neither
`make` nor the Docker CLI. So on the shipped image the Known Road cannot be executed
in-container.

Rather than spawn a subprocess that is guaranteed to fail and record that as an attempted
heal, the sentinel **probes its capability at startup and before every attempt** and, when
a prerequisite is missing, records `status: deferred` with the specific missing piece and
reports `self_heal: unavailable` on `/healthz`. It does **not** clear the service's failure
counter in that case — the registry keeps saying the service is down.

To make self-heal actually operational, an operator must supply a constrained route to a
Docker daemon **and** `make`. Both are deployment decisions, not code:

- a host-side runner that tails `/actions` (or the jsonl trail) and executes the Known
  Road on the host — the current recommendation, since it keeps the sentinel socket-free; or
- a socket **proxy** scoped to `POST /containers/*/restart` plus `make` + the Docker CLI
  added to the image.

Until one of those exists, treat the sentinel as an observability surface. `/healthz` will
say so in `self_heal_reason` — it will not claim a capability it does not have.

## Consumers

- **Pinokio** `pmoves-services` launcher: fetch `/registry.json`, render menu rows with
  ServiceTier icons, health chips; status.js curls health_check URLs directly
- **CLI**: `make fleet-registry` (showtime family) prints the same JSON
- **A2UI**: `pm-service-registry` web component (separate PR) binds registry.json
