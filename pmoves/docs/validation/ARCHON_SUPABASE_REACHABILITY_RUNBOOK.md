# Runbook — Archon Supabase reachability + readiness gate

Measured on B850 / Knuckles, 2026-09-08. Patch:
[`patches/archon-supabase-reachability.patch`](patches/archon-supabase-reachability.patch).

**The compose files are READ-ONLY on this node. This runbook does not apply the patch.**

## Symptom

`pmoves-archon-1` reports `Up 5 days (healthy)`, `FailingStreak: 0`, to every
dashboard, while being completely non-functional. Its logs end at
`Failed to fetch credentials after 30 attempts` — a bounded retry that never resumes.

## Root cause — three independent faults, each sufficient on its own

### 1. Archon is pointed at a Supabase that does not exist here

`/healthz` volunteers its own configuration:

```json
{"detail":{"status":"degraded","service":"archon",
 "supabase":{"url":"http://host.docker.internal:54321","http":0},
 "error":"[Errno -2] Name or service not known"}}
```

`host.docker.internal:54321` is the **Supabase CLI local-dev default**, not this
deployment. The archon stanza sets `SUPABASE_URL` **nowhere**, so it inherits
whatever the tier environment supplies. Ten peer services in the same root compose
file already set the correct value:

```
$ grep -c 'SUPABASE_URL=.*supabase-kong:8000' pmoves/docker-compose.yml
10          # archon is not among them
```

### 2. `host.docker.internal` does not resolve, and nothing listens on :54321

| Check | Result |
|---|---|
| `getent hosts host.docker.internal` in-container | rc=2 (no result) |
| `.HostConfig.ExtraHosts` on the container | `[]` |
| `ss -ltn` on the host, port 54321 | nothing listening |
| *positive control:* total host listening sockets | 66 — `ss` is working |

On Linux, `host.docker.internal` is only defined when the container is given
`extra_hosts: ["host.docker.internal:host-gateway"]`. This one is not.

### 3. No shared Docker network with Supabase

| Container | Networks |
|---|---|
| `pmoves-archon-1` | `pmoves_app`, `pmoves_bus`, `pmoves_external` |
| `pmoves-supabase-kong-1` | `pmoves_api`, `pmoves_public` |
| `pmoves-supabase-db-1` | `pmoves_api`, `pmoves_data` |

No intersection. Docker's embedded DNS resolves container names only across a
**shared** user-defined network (see Provenance), so even the correct hostname
could not resolve.

#### Positive controls that make this network membership, not a DNS outage

Run from inside `pmoves-archon-1`:

```
FAIL  (rc=2): kong, supabase-kong, pmoves-supabase-kong-1,
              pmoves-supabase-db-1, db, postgres
OK    (rc=0): pmoves-archon-postgres -> 172.30.2.2   <- sibling on a SHARED network
OK    (rc=0): github.com             -> 140.82.114.4 <- upstream forwarding works
```

The resolver is healthy and egress is healthy. Only cross-network names fail.
This **disproves** the standing hypothesis that this node's Tailscale exit-node
egress break was responsible.

#### Positive control that the proposed fix target is live

From `pmoves-presign-1`, a container already on `pmoves_api`:

```
getent hosts supabase-kong        -> 172.30.1.30
curl http://supabase-kong:8000/         -> HTTP 401
curl http://supabase-kong:8000/rest/v1/ -> HTTP 401
```

401 is Kong correctly refusing an unauthenticated request — routing, TCP and HTTP
all work. The destination the patch points at is real and answering.

## The patch

Applied to the archon stanza in **both** `pmoves/docker-compose.yml` and the
`pmoves/docker-compose.agents.yml` overlay, so the drift gate sees them agree.

1. Add `SUPABASE_URL=${SUPABASE_URL:-http://supabase-kong:8000}` — matching the ten peers.
2. Add `pmoves_api` to `networks:` **and** to the `PMOVES_NETWORKS` self-declaration.
   `pmoves_api` is `internal: true`, so this grants no new egress; egress remains
   supplied solely by `pmoves_external`.
3. Repoint the healthcheck at the readiness *field* (see below).

Verification performed on the patch itself:

| Check | Result |
|---|---|
| 3/3 edit anchors unique **within the archon stanza** | pass (a naive whole-file match hits `PMOVES_NETWORKS` 12x) |
| Both patched files parse as YAML | pass |
| Originals also parse (control) | pass |
| `git apply --check` against `origin/main` | pass |
| Deliberately corrupted copy of the same patch | **rejected** — the check discriminates |

## Applying it (operator, on a node where compose is writable)

```bash
git apply pmoves/docs/validation/patches/archon-supabase-reachability.patch
make -C pmoves up-agents          # a RESTART IS REQUIRED: the 30-attempt
                                  # credential retry budget is already spent,
                                  # so archon will not recover on its own.
make -C pmoves archon-smoke       # must go from FAIL to pass
docker inspect pmoves-archon-1 --format '{{.State.Health.Status}}'
```

## Unverified / could-not-measure

- **Whether archon reaches `ready:true` after the patch.** Not measurable here:
  it needs a restart of a production service, which this lane may not perform.
  The patch removes three measured blockers; it does not prove there is no fourth.
  The `migration_required:true` flag in the payload hints a schema migration may
  still be outstanding — `migration/add_source_url_display_name.sql`, per the
  payload's own `migration_instructions`.
- **Whether `SUPABASE_URL` is set in the tier environment** to the bad value, versus
  defaulting there from code. Tier environment files are zero-access on this node,
  so this was inferred from `/healthz` output plus the absence of any `SUPABASE_URL`
  key in the archon compose stanza. The patch's `${SUPABASE_URL:-...}` form is
  deliberately chosen to be correct **either way**: an explicitly-set tier value still
  wins, so if the tier is the source of the bad value, that must be corrected there
  too. **Operator action required to confirm.**
- **Why three different service names answer on :3090** (`knowledge-api` on
  `/api/health`, `archon-backend` on `/health`, `archon` on `/healthz`). Not traced
  to source. Does not affect the patch.
