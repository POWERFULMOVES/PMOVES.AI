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

## 6. Phase A2 — follow upstream releases (operator redirect, 2026-09-28)

Operator intent: images follow upstream releases; pinning a harness is a fool's errand. Target at the
time of writing: Archon upstream `v0.11.1` (2026-09-25), Agent Zero upstream `v2.13` (2026-09-23).

### Design (implemented in `pmoves/Makefile` + `pmoves/tools/upstream_release_track.py`)

1. **Resolve** `gh api repos/<upstream>/releases/latest` -> tag -> commit; compare it with the fork's
   `PMOVES.AI-Edition-Hardened` head. Exit 0 = hardened contains the release, 1 = it does not (sync
   the fork first), 3 = could not measure. Every emitted value is pattern-validated (targets eval it).
2. **Build** (`archon-build-latest`) from the fork commit that contains the release, via a git
   build context at the exact sha (no local submodule state involved). Tag
   `<version>-pmoves.<sha8>`, labels carry release tag/sha and fork sha. Refuses on exit 1.
3. **Gate** (`archon-promote-current IMAGE=...`): throwaway container, `--network none`, no ports, no
   volumes; `/api/health` must report JSON `status: ok`. Pass -> retag `:current`. Fail -> `:current`
   untouched, logs printed, non-zero exit. `archon-release-latest` chains resolve -> build -> gate.
4. **A0**: `a0-release-resolve` (resolver side). Build side road-gated, see below.

### Fork sync result: BLOCKED (not merged, nothing pushed to the fork)

- Hardened `8d135dab` is `diverged` from `v0.11.1`: the fork tracks upstream `dev` lineage (57 behind
  dev, 59 PMOVES commits ahead) while release tags sit on upstream `main` (squash line). Merging the tag
  directly = 193 conflicts (the same code arriving by two histories) — wrong road.
- Right road: merge upstream `dev` at `3d8e4e90` (upstream's own "Merge branch 'main' into dev",
  2026-09-25 — the first dev commit whose history contains `v0.11.1`; 53 commits). 4 conflicts:

| File | Nature | Proposed resolution |
|---|---|---|
| `bun.lock` | lock drift (claude-agent-sdk 0.3.251 -> 0.3.282, pi-* 0.84 -> 0.87, ...) | regenerate `bun install --lockfile-only`; keep fork overrides (e.g. `axios ^1.17.0`) |
| `packages/core/src/db/bundled-schema.generated.ts` | generated | regenerate from the auto-merged `migrations/000_combined.sql` |
| `packages/isolation/src/pr-state.ts` | **SECURITY**: fork CodeQL fix `isGitHubRemote()` (host parse, not substring; c1c3b22b) vs upstream `PrLookup` refactor | keep BOTH: upstream types + fork `isGitHubRemote`; the auto-merged call site already uses `isGitHubRemote` |
| `packages/isolation/src/providers/worktree.ts` | fork deleted orphaned `applyGitIdentity` (90ea8372); upstream re-added a caller | take upstream side including the method |

The scripted resolution was refused by the harness safety classifier as a possible security
weakening (pr-state.ts is the hardening). Per the brief, stopped here: **a human resolves pr-state.ts**,
then the remaining three are mechanical.

### Persistence outside argv (road-gated / operator-owned)

- `ARCHON_API_PORT=8092` exists only because the running `pmoves-mcp-gateway` predates its move to
  host 8189. The durable fix is to recreate the gateway from current compose (separate approval); Archon's
  default 8091 then needs no override. Node-local alternative: `.env.local` (operator-written; it only
  enters compose when `SUPABASE_RUNTIME!=compose` or `INCLUDE_ENV_LOCAL_IN_COMPOSE=1`).
- Image channel: compose `archon.image` defaults to `…:pmoves-latest`, and `env.shared.example:129`
  sets the same explicitly (so the generated env file overrides any compose default). Moving to
  `…:current` needs (a) compose — `KNOWN_ROAD=compose:<reason>`, not minted — and (b) the example +
  secrets-funnel regen. Only safe fleet-wide once CI also publishes a gated `:current` to GHCR
  (otherwise nodes without a local `:current` fail to pull).
- A0 release-exact build: `services/agent-zero/Dockerfile` clones a named branch; needs
  `AGENT_ZERO_SHA` build arg + post-clone `git rev-parse HEAD` assertion — `KNOWN_ROAD=dockerfile:<reason>`,
  not minted.

### Automation (proposed, not implemented)

`.github/workflows/` is delete-protected only, but automation must wait for the manual Archon sync.
Shape: a scheduled + `repository_dispatch` workflow runs the resolver per component; exit 1 -> dispatch
`fork-sync.yml` for that fork (or open an issue when it conflicts); exit 0 and no GHCR image for that
version -> dispatch `integrations-ghcr.yml` for the component with a version tag, then smoke and
publish `:current`. `integrations-ghcr.matrix.json` builds archon from the branch name today, not
the resolved sha — that entry would take the resolver's `FORK_SHA`. `agent-zero-upstream-check.yml`
already watches A0 upstream daily and is the natural host for the A0 half.

## 7. Closing the "ARCHON_IMAGE only in argv" gap (operator, 2026-09-28)

Landed on this branch:
- `.github/workflows/archon-release-track.yml`: runs on a schedule, on `workflow_dispatch` (with a `dry_run` option) and on `repository_dispatch: archon-upstream-release`.
  - It runs the resolver first.
  - rc 1: opens or updates an issue. fork-sync has no per-fork selector, and its `ahead_max=20` guard skips this fork as MANUAL, so fork-sync cannot do the sync.
  - rc 3: the job fails.
  - rc 0: builds `<version>-pmoves.<sha8>` for amd64 and arm64 from the exact resolved fork sha, pushes it, and then runs `pmoves/tools/archon_release_channel.sh promote` (the node gate) on the amd64 variant. Only after the gate passes does it copy the manifest to `:current`. On failure, `:current` is untouched and the job fails.
- `integrations-ghcr`: the archon matrix entry has `"resolve": "archon"`, so the build job checks out the resolver's `FORK_SHA` instead of the branch name. This is the `:pmoves-latest` lane.
- `pmoves/env.shared.example`: `ARCHON_IMAGE=ghcr.io/powerfulmoves/pmoves-archon:current`, with a comment that pinning a sha is for rollback only.

Waiting on the compose road (`KNOWN_ROAD=compose:<reason>`, grant naming pr:3214). This is the exact patch; it is not applied:

```diff
--- a/pmoves/docker-compose.yml
+++ b/pmoves/docker-compose.yml
@@ -3790,7 +3790,7 @@
     build:
       context: ../PMOVES-Archon
       dockerfile: Dockerfile
-    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:pmoves-latest}
+    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:current}
     # No container_name: keep the compose-default `${PROJECT}-archon-1` name that
     # `wait-agents` and the REST policy probe (Makefile) inspect by that exact name.
     hostname: archon
--- a/pmoves/docker-compose.agents.yml
+++ b/pmoves/docker-compose.agents.yml
@@ -271,7 +271,7 @@
     build:
       context: ../PMOVES-Archon
       dockerfile: Dockerfile
-    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:pmoves-latest}
+    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:current}
     # No container_name: keep the compose-default `${PROJECT}-archon-1` name that
     # `wait-agents` and the REST policy probe (Makefile) inspect by that exact name.
     hostname: archon
--- a/pmoves/docker-compose.agents.images.yml
+++ b/pmoves/docker-compose.agents.images.yml
@@ -9,7 +9,7 @@
       - ./chit:/app/pmoves/chit:ro
   archon:
     build: null
-    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:pmoves-latest}
+    image: ${ARCHON_IMAGE:-ghcr.io/powerfulmoves/pmoves-archon:current}
   deepresearch:
     build: null
   supaserch:
```

**Ordering after merge:** dispatch `archon-release-track.yml` once, so GHCR has `:current` before any node recreates Archon with the new default. Until that run succeeds, a node that pulls `:current` gets "manifest unknown". The fork must also contain the latest release first; until then the workflow's rc-1 path only opens the issue. The interim image stays `:b850-8d135dab` / `:pmoves-latest`.

**Agent Zero:** not a clean fit without the Dockerfile road. Both `services/agent-zero/Dockerfile` and `Dockerfile.multiarch` (which `agent-zero-upstream-check.yml` builds) clone `--branch ${AGENT_ZERO_REF}`, and `git clone --branch` cannot take a sha. The ref JSON the Dockerfile ADDs lives only in the discarded `upstream` stage, so nothing in the final image proves which commit was built.
- Building from the resolved sha needs an `AGENT_ZERO_SHA` build arg plus a `git fetch <sha> && git checkout && test "$(git rev-parse HEAD)" = "$AGENT_ZERO_SHA"` assertion in both Dockerfiles. That is road `KNOWN_ROAD=dockerfile:<reason>`, not minted.
- Everything downstream of that (the `/healthz` gate and `:current`) mirrors the Archon workflow and becomes a copy once the road is open.

## 8. Live bring-up failure mode (measured by the live-step agent, 2026-09-28)

Native Archon 0.10.1 is now up and healthy on Knuckles.
- **First attempt crash-looped.** Recreating the retired Python `pmoves-archon-1` as the native image let compose carry the old container's **named** volume `pmoves_archon-user-home` over the tmpfs that `docker-compose.yml` now declares at `/home/appuser` (archon service, `- type: tmpfs` / `target: /home/appuser`, ~line 3911).
- **What fixed it:** `--force-recreate --renew-anon-volumes`. Afterwards `HostConfig.Mounts` shows the tmpfs at `/home/appuser`, and the service is healthy.
- **Now in git:** `up-a0-archon-scoped` always passes both flags for archon, and recreates agent-zero separately without `-V`. `tests/make/test_up_a0_archon_scoped.py` asserts this through `make -n`.
  - Positive control: the pre-fix Makefile produces 0 `--renew-anon-volumes` lines; the fixed one produces 1.

**Open question: credential delivery (disclosed, not solved).** `/home/appuser` is now an EMPTY tmpfs on every start. So:
- `gh` inside Archon is unauthenticated.
- Any Claude or gh credentials the old `archon-user-home` volume carried are no longer mounted. The volume still exists; nothing mounts it.

Archon's Claude auth comes from environment variables (`CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_AUTH_TOKEN`), so that path is unaffected. Anything that expected state under `~` is not. The owning road for delivering those credentials (secrets funnel into env, versus a dedicated read-only mount) is an operator decision.
