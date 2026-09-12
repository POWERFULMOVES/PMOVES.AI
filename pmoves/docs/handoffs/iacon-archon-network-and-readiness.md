# Operation IACON — attach Archon to its dependency network, and make its healthcheck able to fail

**Lane:** `infra/iacon-archon-network`
**Owner:** B850-CLAUDE (Knuckles)
**Opened:** 2026-09-12
**Known Road reason:** this file — `KNOWN_ROAD=compose:handoff:iacon-archon-network-and-readiness.md`

## Why a compose Known Road is needed

`pmoves/docker-compose.yml` is a `readOnlyPath` in the `compose` Known Road domain.
Two edits to the `archon` service are required and both are structural, so neither
can be expressed anywhere else:

1. add `pmoves_api` to the service's `networks:` list;
2. replace the healthcheck so it fails when the service reports `ready: false`.

## Measured state before the change (B850 / Knuckles, 2026-09-12T08:17Z)

`GET http://127.0.0.1:3090/api/health` returned **HTTP 200** with body:

```json
{"status":"migration_required","service":"knowledge-api","ready":false,
 "migration_required":true,
 "message":"Schema check error: ConnectError: [Errno -2] Name or service not known"}
```

Container health status: `healthy`, `FailingStreak=0` — for nine days.
The healthcheck is `curl -fsS http://localhost:3090/api/health || exit 1`, and
`curl -f` keys on the HTTP status code only. The endpoint answers 200 while
saying `ready:false` in the body, so the check cannot observe the failure it
exists to observe.

Network membership, measured via `docker inspect`:

| container | networks |
|---|---|
| `pmoves-archon-1` | `pmoves_app`, `pmoves_bus`, `pmoves_external` |
| `pmoves-supabase-kong-1` | `pmoves_api`, `pmoves_public` |
| `pmoves-supabase-gotrue-1` | `pmoves_api` |
| `pmoves-supabase-pooler-1` | `pmoves_data` |

No overlap. `Errno -2` here is a **membership** failure, not a DNS outage —
`nats` and `pmoves-nats-1` both resolve from inside the same container.

## Two independent defects, not one

Attaching the network is necessary but **not sufficient**. After attaching
`pmoves_api` the name resolves and PostgREST answers, yet `/api/health` still
reported `Errno -2`. The second defect is env precedence.

`/app/services/archon/main.py:_ensure_supabase_env()` rewrites
`os.environ["SUPABASE_URL"]` at startup with this priority:

1. `ARCHON_SUPABASE_BASE_URL`
2. `SUPA_REST_URL` stripped of its `/rest/v1` suffix
3. existing `SUPABASE_URL` (left as-is)

The shared env supplies `SUPA_REST_URL=http://host.docker.internal:54321/rest/v1`
(the Supabase **CLI** dev topology), which outranks the correct service-level
`SUPABASE_URL=http://supabase-kong:8000`. The wrapper therefore forces
`SUPABASE_URL=http://host.docker.internal:54321`, and the container has
`extra_hosts: []`, so `host.docker.internal` does not resolve, giving `Errno -2`.

This is why the outage read as purely a network problem for nine days: the
network *was* broken, and fixing it alone changes nothing observable.

Note the measurement trap: `/proc/1/environ` still shows the correct
`SUPABASE_URL=http://supabase-kong:8000`, because that file is the process's
*startup* env and the rewrite happens in `os.environ` afterwards. Reading
`/proc/1/environ` alone would have cleared the service of this defect.

The fix uses the wrapper's own documented highest-precedence knob rather than
fighting it: set `ARCHON_SUPABASE_BASE_URL` to the in-cluster Kong base.

## Out of scope

- The migration the health message advises
  (`migration/add_source_url_display_name.sql`). Once the network and URL are
  correct the schema check reaches PostgREST and returns `PGRST205 — Could not
  find the table 'public.archon_sources'`. That is a real but *different*
  blocker and it is deliberately not touched here.
- `pmoves_data`. Not required: `supabase-db` resolves from `pmoves_api`, and the
  failing path is the Supabase REST path, not direct postgres.

## Incidental findings (not fixed in this lane)

- `.claude/hooks/damage-control/.known-road-active` holds `compose:pr:2656`,
  written 2026-08-21. The grant is 22 days old and the PR it cites has merged.
  Because `evaluate_known_road()` consults that file whenever `KNOWN_ROAD` is
  unset, **any** later compose edit by **any** agent is silently granted and
  recorded to the git-tracked `known-roads.jsonl` under that spent reason.
- `pmoves-archon-1` accumulates `[curl] <defunct>` zombies — PID 1 is
  `python -m services.archon.main` with no subreaper and no `init: true`, so
  every healthcheck curl leaks a process table entry.
- The compose comment above the `archon` service says the wrapper under
  `services/archon/` "is dead — see #2217", but that wrapper is PID 1 in the
  running container and is the code that performs the URL rewrite above.

---

## Exact change to apply (blocked on the Known Road, see below)

Three edits, applied identically in **both** defining overlays — the running
container came from the first, and the `agents` profile uses the second:

| file | networks | healthcheck |
|---|---|---|
| `pmoves/docker-compose.yml` | L3832-3839 | L3842-3843 |
| `pmoves/docker-compose.agents.yml` | L382-389 | L392-393 |

### 1. Attach `pmoves_api` (both files)

Add one entry to the service's `networks:` mapping, after `pmoves_external:`:

```yaml
      # Supabase REST/auth live on pmoves_api. Without this the service cannot
      # resolve supabase-kong at all: Errno -2 is membership, not a DNS outage.
      # pmoves_data is deliberately NOT added -- supabase-db resolves from
      # pmoves_api (verified 172.30.1.6) and the failing path is REST.
      pmoves_api:
```

### 2. Point the Supabase base URL at in-cluster Kong (both files)

Add to the service's `environment:` list. The knob exists in
`env.shared.example:131` but ships empty, so the wrapper falls through to
`SUPA_REST_URL`. The `${VAR:-default}` form is required, not a bare value: a
service-level `environment:` entry overrides `env_file`, so a hardcoded value
would silently discard an operator's override -- the same nested-default lesson
already documented for `ANTHROPIC_AUTH_TOKEN` in this file.

```yaml
    # Highest-priority input to services/archon/main.py:_ensure_supabase_env(),
    # which otherwise ranks SUPA_REST_URL (host.docker.internal:54321, the
    # Supabase CLI topology) ABOVE the correct SUPABASE_URL and forces it to a
    # host this container has no extra_hosts mapping for.
    - ARCHON_SUPABASE_BASE_URL=${ARCHON_SUPABASE_BASE_URL:-http://supabase-kong:8000}
```

### 3. Readiness-aware healthcheck (both files)

Replace the `test:` line with:

```yaml
      # READINESS-AWARE HEALTHCHECK. `curl -f` keys on the status code only, and
      # this endpoint answers 200 while its body says ready:false -- so the old
      # check reported `healthy` for nine days while the service was not.
      # Reusable shape for any PMOVES service whose /health carries a status
      # string; copy it rather than writing a new one-off.
      #
      # Deliberately asserts on `status`, NOT on `ready`: the ready field is
      # emitted ONLY in the failure branch (api_routes/knowledge_api.py), so
      # `grep '"ready":true'` would be a check that can never pass.
      # Fail-closed: an unrecognised status word fails, which is correct here.
      test: ["CMD-SHELL", "curl -fsS http://localhost:3090/api/health | grep -qE '\"status\"[[:space:]]*:[[:space:]]*\"(healthy|ok|ready|up)\"'"]
```

## Proof the new healthcheck can fail (and does not always fail)

Four throwaway containers built from Archon's own image ID, each serving one of
the two body shapes the code actually emits, each wired to Docker's real
healthcheck machinery, then torn down:

| body served | old check | new check |
|---|---|---|
| `200` + `"ready":false` (the real failing body) | **healthy**, FailingStreak 0 | **unhealthy**, FailingStreak 5 |
| `200` + `{"status":"healthy"}` (no `ready` field) | healthy | **healthy** |

The old check's own probe log shows `ExitCode=0` on the failing body — the
nine-day blindness reproduced exactly. The bottom-right cell is the negative
control: it proves the new check is not merely always-failing, and specifically
that the healthy body's *absence* of a `ready` field still passes.

Fifth control, no server listening at all: new check → `unhealthy`,
`ExitCode=1`. No regression on a genuinely dead service.

## Proof the env fix works, through the wrapper's own code path

Calling `_ensure_supabase_env()` in-container, then running the exact schema
query the health endpoint runs:

```
WITHOUT fix:  SUPABASE_URL -> http://host.docker.internal:54321
              RESULT: ConnectError [Errno -2] Name or service not known
WITH fix:     SUPABASE_URL -> http://supabase-kong:8000
              GET http://supabase-kong:8000/rest/v1/archon_sources... 404
              RESULT: APIError PGRST205 Could not find the table 'public.archon_sources'
```

The failure mode advances from "cannot resolve a name" to "the table is not
there" — a real application answer over a working connection.

## `ready: true` is NOT reachable in this lane — COULD-NOT-MEASURE

With both fixes in place the blocker becomes `PGRST205`: the `archon_sources`
table does not exist. That is the migration this lane explicitly does not run.
Reporting `ready: true` as achieved would require running it.

## Known Road status — BLOCKED, not skipped

`KNOWN_ROAD` is unset in the delivering session
(`KNOWN_ROAD=[UNSET] CLAUDE_PROJECT_DIR=[/home/pmoves-knuckles/pinokio/api/PMOVES.AI]`),
and hooks are spawned by the client rather than by the agent's shell, so the
agent cannot set it. That leaves the file grant, which holds a spent
`compose:pr:2656`. Verified in a sandboxed `CLAUDE_PROJECT_DIR` (no real trail
written):

```
active grant : 'compose:pr:2656'
domain match : True
verdict      : (True, 'Known Road compose:pr:2656 (recorded to known-roads.jsonl)')
```

The stale grant therefore launders **automatically**, with no cooperation from
the agent: every compose write by every agent is stamped `pr:2656` into the
git-tracked `known-roads.jsonl`. Both write channels are affected — the Write/Edit
hook and the Bash hook both call `evaluate_known_road()`.

The three edits above are consequently specified rather than applied. Applying
them needs exactly one of: the grant file rotated to
`compose:handoff:iacon-archon-network-and-readiness.md`, or `KNOWN_ROAD` set in
the delivering session's environment.

---

## Sweep: how many other healthchecks cannot observe their own failure

Every running container on B850 that reports `healthy` AND whose healthcheck is
status-code-only (no `grep`/`jq`/`awk`/inline-JS body assertion) was re-probed at
the same URL, and its body inspected for a negative readiness marker.

| outcome | count |
|---|---|
| status-code-only HTTP healthcheck, body readable | 19 |
| — of those, body **contradicts** Docker's `healthy` | **1** (`pmoves-archon-1`) |
| body could not be read — **NOT cleared** | 12 |

**The 12 are an instrument limit, not 12 suspects.** The probe shells `curl`
inside the container, and several of these images have no `curl` (their checks use
`wget` or inline `node -e`). For the node-based ones the URL extractor picked up
JavaScript fragments rather than a URL, so those rows are artifacts of the sweep,
not findings:

```
pmoves-cipher-api-1        url=...8105/health',r=>{process.exit(...)}   <- JS, not a URL
pmoves-supabase-meta-1     url=...8080/health',r=>{r.resume();...}      <- JS, not a URL
pmoves-activepieces-app-1  url=...api/v1/flags',r=>process.exit(...)    <- JS, not a URL
pmoves-supabase-pooler-1   code=204                                     <- no body BY DESIGN, cannot lie
pmoves-tensorzero-gateway-1, pmoves-tensorzero-ui-1, pmoves-tensorzero-clickhouse-1,
pmoves-nats-1, pmoves-supabase-storage-1, pmoves-supabase-gotrue-1,
pmoves-mcp-gateway, pmoves-activepieces-worker-1                        <- no curl in image
```

A 204 healthcheck (`supabase-pooler`) is structurally immune to this defect: there
is no body in which to contradict the status code. That is worth noting as the
other valid answer besides a body-aware check.

So: one confirmed instance beyond the one already known, and twelve genuinely
unmeasured. Re-running this sweep with a `wget`/`node` fallback and a URL
extractor that understands inline-JS healthchecks is the follow-up; it is not
done here and the 12 must not be reported as clean.
