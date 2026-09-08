# Validation matches shape

> Validation for each service must be based on **functionality and usage** — that is
> what turns the light green, not a switch — and **validation should match shape**.

## The defect class

A *switch* proves a process is running. A *shape-matched probe* proves the service
does the thing it exists to do. Most of this fleet's validation is switches, and a
switch cannot distinguish "working" from "up but useless".

The decisive case, measured on B850 2026-09-08: `pmoves-archon-1` reported
`Up 5 days (healthy)`, `FailingStreak: 0` to every dashboard while being completely
non-functional — it could not resolve Supabase at all. Meanwhile the shape-matched
probes **already caught it**:

```
make -C pmoves archon-smoke      -> FAIL: archon /healthz => 401     exit 2
make -C pmoves archon-mcp-smoke  -> ✖ archon-mcp not reachable :8051  exit 2
```

**So shape validation exists and works here. It is simply not wired to the light.**
The container healthcheck polls a liveness endpoint and reports `healthy` to every
dashboard; the functional probe sits in a Makefile that only a human runs.

## Why the default idiom is a switch

This is not carelessness — it is the pattern the vendor teaches. Docker's own
`HEALTHCHECK` reference gives this as its worked example:

```dockerfile
HEALTHCHECK --interval=5m --timeout=3s CMD curl -f http://localhost/ || exit 1
```

That is precisely the archon healthcheck. And it cannot work, because of how the
two vendors' semantics compose:

- **Docker:** "The command's exit status indicates the health status... 0: success —
  the container is healthy and ready for use. 1: unhealthy."
- **curl:** `-f, --fail` — "Fail with error code 22 ... for HTTP response codes at
  **400 or greater**. By default, curl does not consider HTTP response codes to
  indicate failure." curl's own manual adds: *"This method is not fail-safe and there
  are occasions where non-successful response codes slip through."*

So a service that answers **HTTP 200 carrying a failure payload** passes forever.
Archon does exactly that:

```
GET :3090/api/health -> HTTP 200
{"status":"migration_required","ready":false,"migration_required":true,
 "message":"Schema check error: ConnectError: [Errno -2] Name or service not known"}
```

Measured `curl -f` exits, in-container: `/api/health` → **0**;
`/health` → 22 (503); `/healthz` → 22 (503). The healthcheck was pointed at the one
endpoint of the three that **cannot fail**.

## The pattern

**Validate a service through the interface its consumers actually use, asserting on
the thing that makes it useful.** Concretely, match the probe to the service's shape:

| If the service… | …then validate by | Not by |
|---|---|---|
| **Stores** | write a scoped test key, read it back, assert the value matches, delete it | `GET /healthz` |
| **Publishes** | publish to a scratch subject, consume it back, assert the payload | "the broker is up" |
| **Authenticates** | present a credential and assert **accepted**; present a bad one and assert **rejected** | "the port is open" |
| **Computes / transforms** | submit a fixed input, assert on the output's shape and a known field | "the model loaded" |
| **Retrieves / ranks** | query for a seeded doc, assert it comes back **and** that the score/`embedding_id` shows the real path, not a lexical fallback | "returns 200" |
| **Proxies / routes** | assert the request reached the *backend* (a backend-specific header or body), not just that the proxy answered | "gateway is healthy" |

### Three rules that make a probe trustworthy

1. **Assert on the field that means "working", not on the transport.** HTTP 200 is
   transport. `ready:true` is meaning. If the payload carries a readiness field, the
   probe must read it.
2. **Attach a positive control to every green, and a negative control to every red.**
   A probe that cannot fail is worthless; so is a probe that cannot pass. Both have
   happened here — this fleet has a recorded case of a preflight that could only ever
   report DOWN because it never sent the bearer the endpoint required.
3. **Report three outcomes, not two.** `0` clean / `1` findings / `3` could-not-measure.
   Could-not-measure is **not** a pass. Collapsing it into "healthy" is how a
   liveness switch launders ignorance into confidence.

### Wiring the light to the function

A shape-matched probe that only a human runs has not changed the reported state.
Ranked by how directly the reported state derives from function:

1. **Best — the container healthcheck IS the functional probe.** The reported state
   *is* the function; nothing to keep in sync. Costs container CPU on every interval,
   so keep it cheap and idempotent.
2. **Good — the healthcheck parses the readiness field** of an endpoint the service
   already exposes. Nearly free, no new endpoint. This is what the Archon patch does:
   `curl -fsS .../api/health | grep -q '"ready":true' || exit 1`
   (`grep` is present in that image; `jq` is not — verified in-container.)
3. **Acceptable — the healthcheck points at an endpoint that already fails correctly.**
   Archon's `/healthz` already returns 503 and names the exact error. Cheapest possible
   change *if* you can confirm the endpoint returns 200 in the healthy state — which
   for Archon could not be confirmed without a restart, so option 2 was chosen instead.
4. **Weakest — a scheduled external prober** writes state somewhere the dashboard reads.
   Adds a component that can itself fail silently; needs its own liveness story.

**Anti-pattern:** leaving the functional probe in a Makefile and calling the service
validated. That is the state this document exists to correct.

## Scope note

This pattern is deliberately not applied fleet-wide in one pass. See the ranked
backlog in `VALIDATION_SHAPE_INVENTORY.md`. Converting a switch to a shape probe
without a positive control just replaces a check that always passes with one nobody
trusts.

## Provenance

| Source | Version / date | Taken |
|---|---|---|
| [Docker `HEALTHCHECK` reference](https://docs.docker.com/reference/dockerfile/) | fetched 2026-09-08 | Exit-status→health mapping (0 healthy / 1 unhealthy / 2 reserved); the canonical `curl -f ... \|\| exit 1` example |
| [Docker Engine networking](https://docs.docker.com/engine/network/) | fetched 2026-09-08 | Container-name resolution requires a **shared** user-defined network; embedded DNS at 127.0.0.11 forwards external lookups upstream |
| [curl manual, `-f, --fail`](https://curl.se/docs/manpage.html) | fetched 2026-09-08 | Fails only at HTTP ≥400, exit 22; "by default curl does not consider HTTP response codes to indicate failure"; the "not fail-safe" caveat |
| `pmoves/docker-compose.yml` archon stanza L3538-3673 | `origin/main` @ 21789f225 | Healthcheck definition, networks, absence of `SUPABASE_URL`, `PMOVES_NETWORKS` self-declaration |
| `pmoves/docker-compose.agents.yml` archon stanza L269-404 | `origin/main` @ 21789f225 | Byte-identical overlay stanza — must be patched in lockstep |
| `pmoves/Makefile` L3921-3945 | `origin/main` @ 21789f225 | `archon-mcp-smoke`, `archon-ui-smoke`, `archon-smoke`, `archon-upload-smoke` recipes |
| Live containers on B850 | measured 2026-09-08 | Network membership, DNS resolution + controls, health payloads and `curl -f` exits, presence of `grep`/absence of `jq` |
