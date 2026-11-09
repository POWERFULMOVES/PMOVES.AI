# Graceful shutdown: stop signals and grace periods for data stores

**Node:** z890 · **Date:** 2026-08-21 · **Change class:** `compose:`
**Found by:** `make -C pmoves dep-matrix-check` (UNSAFE SHUTDOWN check)

---

## What was measured

**Zero of 111 services declared `stop_grace_period`.** Every one of them — including
every database — relies on Docker's default: **SIGTERM, then SIGKILL after 10
seconds**.

## Why that produced the 2026-08-19 outage

From the PostgreSQL manual (`server-shutdown.html`), verbatim:

| signal | mode | behaviour |
|---|---|---|
| `SIGTERM` | **Smart Shutdown** | "the server disallows new connections, but lets existing sessions end their work normally. **It shuts down only after all of the sessions terminate.**" |
| `SIGINT` | **Fast Shutdown** | "disallows new connections and sends all existing server processes SIGTERM, which will cause them to **abort their current transactions and exit promptly**. It then waits for all server processes to exit and finally shuts down." |
| `SIGQUIT` | Immediate | "without doing normal database shutdown processing. **This will lead to recovery (by replaying the WAL log) upon next start-up.** This is recommended only in emergencies." |

Docker's default stop signal is `SIGTERM`, which for PostgreSQL means **Smart
Shutdown — wait for every session to end**. Roughly 39 consumers hold pooled
connections to `supabase-db`; those sessions do not end inside 10 seconds. So the
sequence is:

```
docker compose down
  -> SIGTERM        postgres begins Smart Shutdown, waits for sessions
  -> (10 seconds)   sessions still open, shutdown has not completed
  -> SIGKILL        process destroyed mid-flight — no checkpoint, no clean exit
```

SIGKILL is strictly worse than SIGQUIT: the server gets no opportunity to do
anything at all. The next start must recover. That is precisely what was observed
on 2026-08-19:

```
supabase-db  LOG: syncing data directory (fsync), elapsed time: 230.18 s
gotrue       FATAL: the database system is starting up (SQLSTATE 57P03)
```

Six minutes of fsync, and every dependant failing behind it. The cause was not
the crash — it was the **shutdown**, days earlier, being unclean by default.

## The fix

Two settings per data store:

- **`stop_signal: SIGINT`** for PostgreSQL-family services. Fast Shutdown aborts
  in-flight transactions, checkpoints, and exits cleanly — no WAL recovery on the
  next start. This is the mode intended for an orchestrated stop.
- **`stop_grace_period`** large enough for that shutdown to finish before Docker
  escalates to SIGKILL.

Grace periods are sized by what the engine must flush, not by a single constant:

| service | grace | why |
|---|---|---|
| `supabase-db` | 90s | checkpoint + WAL flush with many open sessions |
| `archon-postgres` | 60s | same engine, far fewer sessions |
| `tensorzero-clickhouse` | 60s | flushes parts to disk; a kill mid-merge leaves temp parts |
| `neo4j` | 60s | page-cache flush and checkpoint |
| `minio` | 30s | completes in-flight PUTs before exit |
| `qdrant` | 30s | segment flush |
| `meilisearch` | 30s | index write |
| `open-notebook-surrealdb-ext` | 30s | RocksDB flush |
| `nats` | 30s | JetStream state flush |

`stop_signal` is left at the default for non-PostgreSQL engines — for those,
SIGTERM already means "shut down cleanly"; only PostgreSQL overloads SIGTERM to
mean "wait indefinitely for clients".

## Shutdown ORDER is separate from shutdown SAFETY

Grace periods make each container's exit clean. Order makes the *system's* exit
clean — a data store must not be stopped while dependants still hold sessions.
That order is the reverse of the bring-up layering:

```bash
make -C pmoves dep-matrix -- --format shutdown   # reverse-layer stop groups
```

Both halves are required. A correct order with a 10s SIGKILL still corrupts; a
long grace period in the wrong order still kills a store under load.

## A note on the detector

The first version of the `UNSAFE SHUTDOWN` check matched service names by
substring, so it flagged `nats-echo-req`, `nats-echo-res`, `a2ui-nats-bridge`,
`wger-nats-bridge` and `nats-init` — none of which hold state; they merely have
"nats" in the name. Matching was narrowed to a curated set of real store names.
An over-reporting check trains people to ignore it, which is how a real finding
gets missed.

## Verification

```bash
make -C pmoves compose-split
make -C pmoves dep-matrix-check          # UNSAFE SHUTDOWN should list only intended gaps
docker compose ... stop supabase-db      # then check the log for a clean shutdown:
#   "database system is shut down"  (clean)   vs
#   "database system was interrupted" (unclean, recovery follows)
```

The decisive evidence is in the **next start**: a clean shutdown logs
`database system was shut down at ...` and starts in seconds; an unclean one logs
`database system was interrupted` and runs recovery.

## Related

- `pmoves/docs/SERVICE_DEPENDENCY_MATRIX.md` + `make dep-matrix`
- `pmoves/docs/handoffs/weak-waits-service-started-on-data-stores-2026-08-21.md`
  (the bring-up half of the same problem)
