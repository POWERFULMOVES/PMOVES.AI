# Voice Lane 2 — cast-tts bring-up — task card 2026-09-23

**Date:** 2026-09-23
**From:** elder-melchor Hermes dispatch (voice-stack heal session, 2026-09-23)
**To:** **z890-claude** (primary implementer) · 5090-claude (secondary — registry affinity is `[5090, z890]`)
**Coordination:** Village Rule — CLAIM this lane in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` before starting item work; release with an ACK line when done.
**Related:** `pmoves/docs/voice/QUICKSTART_CAST.md`, `pmoves/docs/voice/cast-integration.md`,
`pmoves/services/cast-tts-gateway/` (incl. `CLAUDE.md`, `docker-compose.yml`),
`pmoves/Makefile` (`OVERLAY_PROFILES_MEDIA`, `up-voice`), registry `cast_tts_gateway`
(`pmoves/config/agent_registry.yaml:938`).
**Status:** OPEN (unclaimed)

---

## Current receipted state (measured, not asserted)

| Surface | State | Receipt |
|---|---|---|
| cast-tts-gateway container/code | **shipped in-tree, NOT running on any node** | `pmoves/services/cast-tts-gateway/` — 22 files (service.py, fallback.py, scheduler.py, recovery.py, device_manager.py, flute_client.py, …) |
| registry entry | `cast_tts_gateway` port **8060**, health `/healthz`, layers `[L0,L2,L4]`, `compose_profile: cast`, team media | `pmoves/config/agent_registry.yaml:938` |
| NATS contract (registry) | publishes `voice.cast.completed.v1`, `voice.cast.failed.v1`, `voice.cast.health_alert.v1`, `device.cast.discovered.v1`; `subscribes: []` | same registry block |
| NATS contract (service CLAUDE.md) | publishes `voice.cast.started.v1`, `voice.cast.finished.v1`; **subscribes `voice.cast.request.v1`** | `services/cast-tts-gateway/CLAUDE.md:30-33` — **drifts from the registry in BOTH directions; Step 1 must settle truth** |
| quickstart health contract | `GET :8060/healthz` → `{"status":"healthy","flute_gateway":"healthy","devices_discovered":N}` | `docs/voice/QUICKSTART_CAST.md:22-30` |
| bring-up docs | QUICKSTART (5 steps: deploy → discover → speech → A0 MCP → NATS events) + full cast-integration.md | `docs/voice/QUICKSTART_CAST.md` |
| bring-up known road | **none dedicated** — "comes up via `bringup-with-ui` or full mesh" | `services/cast-tts-gateway/CLAUDE.md:57` |
| standalone compose | `services/cast-tts-gateway/docker-compose.yml` — hardened (user 65532, read-only, cap_drop ALL, 1CPU/512M), `FLUTE_GATEWAY_URL=http://flute-gateway:8055`, `NATS_URL=nats://nats:pmoves@nats:4222`, external nets `pmoves_app/pmoves_bus/pmoves_api/pmoves_monitoring` | the file itself |
| flute dependency | up, `:8055` healthz 200 (elder, post 2026-09-23 heal) | Lane 1 receipt |
| CHIT integration | **Partial** — cast events logged, not CHIT-signed; Full tier is Wave-2 | `CLAUDE.md:43` citing `docs/audit/CHIT_INTEGRATION_STATUS.md` |
| elder receipt | port **8060 in the registry**; the 2026-09-23 heal receipt on elder covered kokoro :8004 + flute :8055 only | heal session log |

**The gap this lane closes:** a fully-shipped service whose bring-up story is "run the full
mesh or read a quickstart" — no dedicated known road, no smoke, NATS contract drifting
between registry and code, and **zero receipted running instance on any node**.

## Target state

- cast-tts-gateway running + healthz-200 on the target node, receipted;
- `make -C pmoves cast-up` / `cast-smoke` / `cast-down` known roads (mk/ pattern, ONE
  include line in the Makefile);
- NATS subjects reconciled ONE way (registry == code) with the deciding evidence cited;
- docs (`QUICKSTART_CAST.md`, `CLAUDE.md`) match the landed reality;
- a live end-to-end receipt: text → flute synth → audible playback on a real Cast device,
  plus observed `voice.cast.*` / `device.cast.*` events.

## Steps (bite-sized, exact commands)

### Step 0 — claim + preflight (~15 min)

Claim the lane (see Coordination). Preconditions on the target node:

```bash
curl -sS http://localhost:8055/healthz      # flute up (Lane 1 dependency)
docker network ls | grep pmoves_            # app/bus/api/monitoring external nets exist
catt scan                                   # ≥1 Cast device on THIS broadcast domain
```

mDNS discovery is LAN-bound (see `services/cast-tts-gateway/CLAUDE.md` §Device discovery):
across Tailscale it needs the destination on the same broadcast domain. No local device →
run the lane on the node that has speakers, not over the tailnet.

### Step 1 — settle the NATS truth (before writing any code)

Read what the code ACTUALLY publishes/subscribes (`grep -rn "voice.cast\|device.cast"`
`services/cast-tts-gateway/*.py`), then decide the one true contract. Then either fix the
registry block (`agent_registry.yaml:938-967`) or the code — cite the grep + a live
`nats sub` capture in the PR. **Do not average the two sources.**

### Step 2 — bring it up (first receipt)

```bash
cd pmoves/services/cast-tts-gateway && docker compose up -d
curl -sS http://localhost:8060/healthz
# expect {"status":"healthy","flute_gateway":"healthy","devices_discovered":0}
curl -sS -X POST http://localhost:8060/cast/discover
```

If the flute dependency reports down inside the container's response, check
`FLUTE_GATEWAY_URL` resolution (`http://flute-gateway:8055` requires the pmoves_app net and
a running flute with that network alias).

### Step 3 — first cast (the receipt that matters)

```bash
curl -sS -X POST http://localhost:8060/cast/speech \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello from PMOVES voice agent!","device":"<device-from-discover>"}'
nats sub -s nats://nats:pmoves@127.0.0.1:4222 "voice.cast.>"
```

Record: HTTP response, `device.cast.discovered.v1` + `voice.cast.*` events observed,
device audible confirmation. 127.0.0.1 not localhost for host-side NATS (`mk/voice.mk:98-100`).

### Step 4 — known roads (mk/ pattern)

New `pmoves/mk/cast.mk` with `cast-{build,up,down,status,logs,smoke}` — following the
voice.mk / node-edition convention (standalone `*.compose.yml` naming stays OUTSIDE the
damage-control glob; make targets are the sanctioned invocation path; ONE include line in
`pmoves/Makefile` after the last mk/ include). Compose-validate + WSL dry-run before merge:

```bash
docker compose -f pmoves/services/cast-tts-gateway/docker-compose.yml config --quiet
wsl -d Ubuntu-24.04 -- bash -lc 'cd /mnt/c/<repo>/pmoves && make -n cast-smoke'
```

### Step 5 — reconcile docs + registry

- Update `services/cast-tts-gateway/CLAUDE.md` known-roads line once `cast-up` exists;
- QUICKSTART_CAST.md matches the new targets;
- registry `cast_tts_gateway` row reflects the settled NATS contract;
- note the hardened compose already pins user 65532 / read-only / cap_drop ALL — preserve those.

### Step 6 — PR

- `cast-smoke` mirrors the flute negative-control discipline where feasible (e.g. flute
  dependency down → gateway healthz must report `flute_gateway` DOWN, not silently healthy);
- explicit `-R POWERFULMOVES/PMOVES.AI` on every `gh` call; **merge is operator-gated**.

## Validation receipts (what "done" means)

- `curl :8060/healthz` → `status: healthy` + `devices_discovered ≥ 1`, pasted in the PR;
- one `cast/speech` round-trip with observed NATS events + audible confirmation;
- `make -C pmoves cast-smoke` exit 0 on the target node; `cast-down` cleanly tears down;
- NATS contract single-sourced (registry == code == docs), evidence cited;
- WSL `make -n cast-smoke` dry-run + compose `config --quiet` rc 0 in the PR body.

## Node affinity

- **Primary: z890-claude** — registry affinity `[5090, z890]`; elder's 2026-09-23 heal
  receipt covers only flute/kokoro, so this lane starts cold wherever it runs. z890 takes it
  to balance against Lane 1 on 5090 (collision-free division: one voice lane per node).
- Secondary: 5090-claude.
- Elder note: if the operator wants the first receipt from elder (flute freshly healed
  there), confirm elder's LAN has a Cast device first (Step 0 `catt scan`); otherwise the
  lane runs wherever the speakers are.

## Skills to load before starting

| Skill | Why |
|---|---|
| `pmoves-voice-fabric` | **Required.** flute dependency contract, auth dialect, port truth |
| `pmoves-node-edition-services` | **Required.** mk/ + compose conventions, container-port/host-port rule, compose-validate, WSL dry-run |
| `pmoves-registry-first` | registry row edits (NATS reconciliation) must follow registry data conventions |
| `pmoves-ci-gates` | If the ratchet / gitlink gate fires on the PR |
| `hermes-pmoves-pr-review` | PR discipline for this repo |

## Guardrails / out of scope

- **Never fork synthesis logic into cast-gateway** — synthesis is flute's job; this service
  is discovery + transport + casting (`CLAUDE.md` pairing rule).
- No silent transport fallback for remote cast — surface the mDNS/LAN limitation explicitly.
- CHIT-signing the cast events stays Wave-2 (its own lane).
- Hardened compose posture (non-root, read-only, cap_drop) is a floor, not an obstacle — do
  not relax it to make bring-up easier.
