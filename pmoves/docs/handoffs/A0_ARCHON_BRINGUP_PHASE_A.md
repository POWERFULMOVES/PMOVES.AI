# A0 + Archon bring-up — Phase A (diagnose, build, dry-run)

Lane: `chore/a0-archon-sync-bringup` (B850-CLAUDE / Knuckles). Operator-approved 2026-09-28.
Phase A: no live container create/recreate/stop/rm. Phase B needs operator approval.

Sources: origin/main `b21c60b3d`; gitlinks PMOVES-Archon `8d135dab`, PMOVES-Agent-Zero `3290759a`
(both equal to their fork branch heads at measurement time: Archon `PMOVES.AI-Edition-Hardened`,
A0 `PMOVES.AI-Edition-v2.13` and `-Hardened`).

## 1. Archon unhealthy — root cause (measured 2026-09-28)

`pmoves-archon-1` (project `pmoves`, service `archon`) is running the **retired Python wrapper**,
not Archon 0.6.0:

| Evidence | Value |
|---|---|
| Container cmd | `python -m services.archon.main` (0.6.0 is a bun/TS image with `docker-entrypoint.sh`) |
| Image | `06727ac67412`, untagged, created 2026-07-29 — two months before #3171; not built from `8d135dab` |
| Container created | 2026-09-15 (after #3038 landed the readiness-aware healthcheck), last started 2026-09-23 |
| `/api/health` body (in-container) | HTTP 200, `"status":"migration_required"`, `ready:false`, PGRST205 `public.archon_sources` not in schema cache |
| Healthcheck | #3038's status-word grep — it correctly FAILS on `migration_required` |
| Log volume | ~100k lines, dominated by a `GET /rest/v1/archon_sources` 404 poll loop |

So the healthcheck is telling the truth: the old Python knowledge-api wants a Supabase table
(`archon_sources`) that the 0.6.0 world never creates. **This is not the earlier network-membership
defect** — the container is on `pmoves_api/app/bus`, and `GET /rest/v1/archon_settings` via
`supabase-kong:8000` returns 200 from inside it.

The compose `archon` service (first-class 0.6.0 since #2259, build context `../PMOVES-Archon`) is
correct; the container was recreated from a stale local image and never rebuilt.

### Secondary: no host ports, and 8091 is taken

- HostConfig binds `127.0.0.1:{3090,3737,8091}->3090`, but `NetworkSettings.Ports` is null, so host
  `:3090` gives no answer. Archon and `pmoves-mcp-gateway` both started at 2026-09-23 12:16:30.
- `pmoves-mcp-gateway` holds host `0.0.0.0:8091`. Its compose now defaults to host 8189
  (`docker-compose.mcp-gateway.yml:129-133` documents exactly this collision); the running container
  predates that. **A plain recreate of `archon` will fail "port is already allocated" on 8091.**
  Phase B must override `ARCHON_API_PORT` (8092 measured free) or recreate the gateway first.

## 2. Agent Zero absence

No `agent-zero` container exists (running or exited) and no `pmoves-agent-zero` image existed before
this lane: A0 was **never built or started on B850**. Owning targets: `up-agents-stack` / `up-agents`
(`$(DC) ... up -d --build ... agent-zero ...`). Its `depends_on` closure is `nats` (healthy),
`nats-init` and `tensorzero-gateway` — **neither of the latter two exists on this node**, and
tensorzero-gateway in turn pulls clickhouse. A0 started with `--no-deps` will boot, but its LLM path
(`TENSORZERO_BASE_URL`) has no gateway behind it until TensorZero is brought up (separate decision).

## 3. Reproducibility gap (needs a road, not taken)

`pmoves/services/agent-zero/Dockerfile` clones `--branch PMOVES.AI-Edition-v2.13` (a moving branch
head), not the recorded gitlink. Today head == gitlink, so the build is faithful, but nothing
asserts it. Fix shape: an `AGENT_ZERO_SHA` build-arg checked against `git rev-parse HEAD` after the
clone. The file is protected (`readOnlyPaths <- **/Dockerfile`); road = `KNOWN_ROAD=dockerfile:<reason>`.
Not minted — operator decision.

Archon has the same class of gap in reverse: compose builds whatever is on disk in `../PMOVES-Archon`
(no `cipher-build-pin-check` equivalent). The root checkout's Archon worktree sits on the pin but
carries ~500 MB of untracked dirs (`external/`, `pmoves_multi_agent_pro_pack/`) that enter the
`COPY . .` web-build stage context (not the final image).

## 4. Builds (from this worktree: origin/main b21c60b3d + pins)

| Image | Id | Source |
|---|---|---|
| `ghcr.io/powerfulmoves/pmoves-archon:b850-8d135dab` | `b521cbb347d8` | `PMOVES-Archon@8d135dab` (clean submodule checkout), `--build-arg USE_LOCAL_VENDOR=1` as in the submodule overlay |
| `pmoves-agent-zero:b850-3290759a` = `:latest` | `463bc2a05097` | `pmoves/services/agent-zero/Dockerfile`, context `pmoves/`; clone of `PMOVES.AI-Edition-v2.13` whose head was `3290759a` (ls-remote before and after) |
| `ghcr.io/powerfulmoves/pmoves-archon:rollback-py-20260729` | `06727ac67412` | tag only — preserves the running Python image so it cannot be pruned once dangling |

Native health: `packages/server/src/routes/api.ts` `/api/health` returns JSON `status: 'ok'`, which the
compose healthcheck's status-word grep accepts. Entrypoint `docker-entrypoint.sh` -> `bun run start`.

## 5. Dry-run (root checkout compose, CIPHER_API_TOKEN unset)

Scoped (`--no-deps --no-build --pull never`, `ARCHON_IMAGE=...:b850-8d135dab ARCHON_API_PORT=8092`):

```
 Container pmoves-agent-zero-1 Creating
 Container pmoves-archon-1 Recreate
 Container pmoves-agent-zero-1 Created
 Container pmoves-archon-1 Recreated
 Container ae2caf9b06e4_pmoves-archon-1 Starting / Started
 Container pmoves-agent-zero-1 Starting / Started
```

Unscoped closure (informational): additionally **recreates `pmoves-archon-postgres`** and creates
`nats-init`, `tensorzero-gateway`, `tensorzero-clickhouse`. No `supabase-*` in either plan.

`make up-a0-archon-scoped [DRY_RUN=1]` (added in this branch) is that scoped line as a Known Road.
