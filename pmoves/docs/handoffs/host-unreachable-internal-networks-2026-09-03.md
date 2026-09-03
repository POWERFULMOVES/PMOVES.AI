# Handoff — 34 services declare a port they can never publish

**From:** 4090-CLAUDE (PMOVES-4090)
**Date:** 2026-09-03
**Status:** measured; fix not applied
**Doubles as:** the `handoff:` artifact for
`KNOWN_ROAD=compose:handoff:host-unreachable-internal-networks-2026-09-03.md`

---

## The mechanism

A container attached **only** to Docker networks marked `internal: true` cannot
publish a port to the host. Docker accepts the `ports:` mapping, stores it in
`HostConfig.PortBindings`, and **never activates it** — no error, no warning, and
the container reports healthy.

That combination is what makes it hard to see:

```
docker inspect  PortBindings: {"8504/tcp":[{"HostIp":"127.0.0.1","HostPort":"8504"}]}   ← looks right
docker ps       ports=[8504/tcp]                                                        ← no mapping
curl            000
```

`docker inspect` shows what Docker was *asked* to do. `docker ps` shows what it
*did*. Only the second one is the truth, and the first is the one that looks
authoritative.

## Measured 2026-09-03 (4090)

Parsed the five `STACK_FILES` compose documents directly (no docker invocation):

```
internal networks: pmoves_api, pmoves_app, pmoves_bus, pmoves_data, pmoves_monitoring
services with ports:                            86
host-unreachable (ports + internal-only nets):  34
```

**The 34:**

a2ui-nats-bridge · a2ui-renderer · consciousness-service · gateway-agent ·
gpu-orchestrator · grayjay-plugin-host · grayjay-server · hf-research-agent ·
invidious-companion-proxy · langextract · llama-throughput-lab · meilisearch ·
nats_event_bus · neo4j · notebook-sync · nvidia-nim · p7-room-orchestrator ·
pdf-ingest · pinokio_bridge · qdrant · retrieval-eval · session-context-worker ·
supabase-gotrue · supabase-pooler · supabase-realtime · supabase-storage ·
supabase-studio · supaserch · tensorzero-clickhouse · tokenism-simulator ·
tokenism-ui · voice-relay · voice-sampler · watch-folder-router

## SCOPE CORRECTION (added after first publication)

**34 is an upper bound on the files parsed, not a measurement of what runs.**

The audit read only the five `STACK_FILES` documents. Services started by targets
that use a DIFFERENT compose file are not covered, and a service defined in more
than one file may run with networks the parsed definition does not show.

Confirmed false positive: `p7-room-orchestrator` is listed below, but the
container that actually runs (`pmoves-p7`, started by `up-openroom` from another
file) is on `pmoves_app pmoves_bus pmoves_external` — it HAS the external
network and publishes `127.0.0.1:8120` successfully, returning 200.

So the list is a set of CANDIDATES to check, not a verdict per service. Before
acting on any row, verify against the running container:

```
docker inspect <container> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
docker ps --format '{{.Names}} {{.Ports}}'      # a real HOST:PORT->CONTAINER mapping, or nothing
```

The static parse is still the right way to FIND the class — it is how the class
was found — but a compose file is a declaration and a container is a fact, and
this repo has several services declared in two files at once.

## Two sub-classes — they need different fixes

**A. Should be host-reachable, is not.** `tokenism-ui`, `supaserch`,
`p7-room-orchestrator`, `voice-relay`, `a2ui-renderer`, `gateway-agent`,
`langextract`, `consciousness-service`, and similar app-tier services. These
want a host port and cannot have one.
→ Fix: multi-home onto `pmoves_external`, exactly as `flute-gateway` already is
(`pmoves_api pmoves_app pmoves_bus pmoves_external`).

**B. Correctly internal, but the `ports:` line is a lie.** `qdrant`, `neo4j`,
`tensorzero-clickhouse`, `supabase-pooler`, and the other data-tier services.
These *should* stay internal. The defect is the `ports:` declaration, which
reads as an interface contract that nothing enforces and nobody can use.
→ Fix: drop `ports:`, or move it behind a documented, opt-in overlay.

**Do not bulk-add `pmoves_external`.** Class B is internal on purpose; putting a
credential store on a non-internal network to satisfy a `ports:` line that
should not exist would be a security regression dressed as a bug fix.

## Why this went unseen

The register predicted it before this session started:

> `gw-priority` is applied to **0 of the 107** services multi-homed on
> `pmoves_external` + an internal tier; it appears once in the entire repo as a
> COMMENT in `services/common/topology.py:27`. It is the documented fix for the
> **host-unreachable class** (the Flute→TTS bug).

> `clip-embed` declares `PMOVES_NETWORKS` with no `networks:` key so it
> **self-reports a topology it does not have**.

So the class was named, the fix was named, and the count of services carrying
the fix was zero. This handoff is the same finding with a number attached.

## How it presented (worth reading before debugging one of these)

Chasing `tokenism-ui` produced **four** confident, wrong causes before the real
one, each of which explained the symptom:

1. `recreate-svc` is profile-blind, so profiled attributes were dropped.
2. A raw `docker compose up` bypass I ran myself while debugging (caught by the
   damage-control hook — it dropped the whole `COMPOSE_ENV_FILES` chain, so any
   conclusion from it would have been about my command, not the pipeline).
3. A stale container that `up -d` skipped because it was healthy.
4. A host bind-address policy (`0.0.0.0` vs `127.0.0.1`).

The actual cause was **one boolean on a network object**, reachable in a single
`docker network inspect`. When a port will not publish, check
`docker network inspect <net> --format '{{.Internal}}'` FIRST; it is one command
and it eliminates the whole class.

## Confounder: `recreate-svc` is genuinely profile-blind

Not the cause here, but real and worth its own fix. `recreate-svc` runs
`$(DC) up -d --force-recreate --no-deps $(SVC)` with no `--profile`, and its own
help text uses `SVC=flute-gateway` — a service under `--profile orchestration`.
Compose then applies a definition without profiled attributes and reports
success. Either resolve the service's profile, accept `PROFILE=`, or fail loudly
when the named service is not in the active profile set.

## Suggested order

1. Fix class A for the services actually needed on the host — smallest set
   first (`tokenism-ui`, `tokenism-simulator`), verified by `docker ps` showing
   a real mapping, not by `inspect`.
2. Decide class B per service: drop `ports:` or move it to an opt-in overlay.
3. `gw-priority` across the multi-homed population — the register's original
   item, now with a measured denominator.
4. `recreate-svc` profile handling.

## Verification contract

A fix is proven when `docker ps` shows `HOST:PORT->CONTAINER/tcp` **and** a host
request returns a non-`000` status. `docker inspect` PortBindings is not
evidence — it is what produced the false confidence above.

## Related

- PR #2884 — the embedding-routing handoff, same `KNOWN_ROAD` mechanism.
- `pmoves/services/common/topology.py:27` — the `gw-priority` comment.
