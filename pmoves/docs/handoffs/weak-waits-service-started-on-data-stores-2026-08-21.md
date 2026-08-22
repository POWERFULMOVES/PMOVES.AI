# Weak waits: `service_started` on data stores (9 edges)

**Node:** z890 · **Date:** 2026-08-21 · **Change class:** `compose:`
**Found by:** `make -C pmoves dep-matrix-check` (PR #2664)

---

## The failure this closes

`depends_on: {x: {condition: service_started}}` waits for a **process to exist**,
not for it to be **ready**. For a data store those are very different things.

Measured on 2026-08-19: `supabase-db` spent ~6 minutes in
`syncing data directory (fsync)` after an unclean shutdown. It was *started* the
whole time. Every dependant that waited only for `service_started` proceeded and
failed:

```
gotrue   : FATAL: the database system is starting up (SQLSTATE 57P03)  -> crash-loop
storage  : startupError, "the database system is starting up"
pooler   : Restarting (1)
realtime : Restarting (1)
```

Nothing was broken — the wait condition simply promised less than the caller
needed. This is the same family as a health endpoint returning 200 while the
thing behind it is dark.

## The trap, and why this was not a bulk find-and-replace

Flipping every `service_started` to `service_healthy` would have **hung two
services forever**. `service_healthy` can only be satisfied if the *target*
declares a `healthcheck`. Measured before changing anything:

| dependency target | healthcheck? | action |
|---|---|---|
| `nats` | YES | flip dependants |
| `minio` | YES | flip dependants |
| `qdrant` | YES | flip dependants |
| `supabase-postgrest` | **NO** | add healthcheck first |
| `open-notebook-surrealdb-ext` | **NO** | add healthcheck first |

That is exactly the `HEALTHCHECK GAP` case `dep-matrix-check` reports, and it is
why the tool distinguishes it from a cycle.

## Adding the two missing healthchecks

Both images are **distroless — no shell at all** (`docker exec ... sh` fails with
`executable file not found`). So `CMD-SHELL` is impossible and a `CMD` probe may
only exec a binary that actually exists in the image. Both were verified by
running the probe against the live containers.

### supabase-postgrest (`postgrest/postgrest:v14.12`)

PostgREST ships its own probe:

```
--ready    Checks the health of PostgREST by doing a request on
           the admin server /ready endpoint
```

It requires the admin server, which is off unless `PGRST_ADMIN_SERVER_PORT` is
set. Confirmed against the running container:

```
$ docker exec pmoves-supabase-postgrest-1 postgrest --ready
ERROR: Admin server is not running. Please check admin-server-port config.
exit=1
```

So the change is **two parts** — enabling the admin server *and* adding the
healthcheck. Adding only the healthcheck would produce a probe that can never
pass, which is worse than no healthcheck: it would mark the service permanently
unhealthy and then block `supabase-storage` forever.

The admin port is bound inside the container only; it is not published.

### The `--ready` trap (found by testing, not by reading)

Enabling the admin server is necessary but **not sufficient**. With only
`PGRST_ADMIN_SERVER_PORT` set, the probe still fails:

```
ERROR: The `--ready` flag cannot be used when server-host is configured as "!4".
       Please update your server-host config to "localhost".
```

`!4` (all-IPv4) is PostgREST's default. Taking the message literally and setting
`localhost` would bind the API to loopback **inside** the container and cut off
Kong and storage — a fix that trades a missing healthcheck for an outage.

Tested the alternatives against throwaway containers:

| `PGRST_SERVER_HOST` | `postgrest --ready` |
|---|---|
| `!4` (default) | refuses to run |
| `*` | refuses to run |
| `*4` | refuses to run |
| **`0.0.0.0`** | **runs** — reports real readiness state |

And `0.0.0.0` keeps the API externally reachable: a published-port request from
outside the container returned HTTP 503 (socket bound; 503 only because that
throwaway had a deliberately bogus DB URI).

So the change is **three parts, all required**: admin port, server host, and the
healthcheck. Any one alone is either inert or harmful. This is why the healthcheck
was added only after the probe was verified end to end rather than written from
the documentation.

### open-notebook-surrealdb-ext (`surrealdb/surrealdb:v2`)

SurrealDB ships `isready`. Verified against the live container:

```
$ docker exec pmoves-open-notebook-surrealdb /surreal isready --conn http://localhost:8000
OK
exit=0
```

Note the binary is at `/surreal` (image root), not on `PATH` in a way a shell
could resolve — there is no shell.

## The 9 edges

| dependant | target | was | now |
|---|---|---|---|
| `github-runner-ctl` | nats | started | healthy |
| `mesh-agent` | nats | started | healthy |
| `nats-echo-req` | nats | started | healthy |
| `nats-echo-res` | nats | started | healthy |
| `tokenism-simulator` | nats | started | healthy |
| `bgutil-pot-provider` | minio | started | healthy |
| `cipher-api` | qdrant | started | healthy |
| `supabase-storage` | supabase-postgrest | started | healthy (after new healthcheck) |
| `open-notebook-ext` | open-notebook-surrealdb-ext | started | healthy (after new healthcheck) |

`supabase-storage` already waited on `supabase-db` with `service_healthy`, so
this edge was not the only guard — but it was the one that let storage start
against a PostgREST that had not yet connected.

## Verification

```bash
make -C pmoves compose-split          # regenerate overlays from the canonical file
make -C pmoves dep-matrix-check       # WEAK WAIT count should be 0
make -C pmoves up-supabase            # storage must reach healthy, not hang
docker ps --filter name=supabase-postgrest --format '{{.Status}}'   # now reports health
```

Rollback is reverting the two healthcheck blocks and the nine `condition:` lines.

## Related

- `pmoves/docs/SERVICE_DEPENDENCY_MATRIX.md` (generated) + `make dep-matrix`
- 2026-08-19 disk-full incident handoffs (the fsync window that exposed this)
