# Handoff — land Z890's merged orchestrator/storage work on the running node (+ env & builder fixes)

**From:** Z890-CLAUDE · **To:** deploy/CI lane (4090-CLAUDE / fork-sync spine) · **Date:** 2026-06-22

## TL;DR

A batch of orchestrator + storage work merged to `main` this session. Most of it **does not reach the running deployment** until the deploy checkout advances to current `main` and the agent-zero image is rebuilt. This note lists exactly what landed, what it needs to actually run, and two environment issues surfaced during the Phase 3 live verify on Z890 (env-loading drift + a builder GHCR 403).

## 1. Merged to `main` (this session)

| Area | PRs | Effect |
|------|-----|--------|
| A0 plugin verify-before-contribute | a0-plugins #8/#9/#10, plugin #2/#3 | `pmoves_notes` conforms to the real A0 API; fork CI resilient |
| A0 wired into the deployment | #1855 (plugin baked into image), #1856 (orchestrator **MCP toolkit**) | agent-zero ships the plugin + `A0_SET_mcp_servers` (docker + supabase + cipher) |
| Supabase currency | #1857 | currency notes; `/auth/v1` is gotrue-upgrade-gated |
| Capability-adaptive standalone | #1859 (spec), #1860 (classifier), #1861 (`up-agents-auto`/`up-core-capable`/`up-core-gpu`) | tier-aware bring-up |
| MinIO unblock | #1862 | repin off the phantom `RELEASE.2025-12-20…` (404) to `RELEASE.2025-09-07T16-13-09Z` in **both** `docker-compose.yml` and `docker-compose.core.yml` |
| JuiceFS migration | #1863 (spec) | durable replacement for EOL MinIO (Z890 lane #10; build pending) |

## 2. What the running node needs (the spine)

These merged changes are **image-** and **checkout-bound**:

1. **Deploy checkout → current `main`.** The running checkout predates the merged `up-agents-auto`/`up-core-capable` targets, the MinIO repin, and the MCP-toolkit compose env. Until it advances, the node still has the old Makefile/compose (and the **phantom MinIO pin → data-tier bring-up fails**).
2. **Rebuild the agent-zero image** (`services/agent-zero/Dockerfile` + `Dockerfile.multiarch`). #1855/#1856 added, at build time: the `pmoves_notes` plugin clone, the **docker CLI** (for the docker MCP), and the pre-installed `@supabase/mcp-server-postgrest`. The running image lacks all three, so `A0_SET_mcp_servers` local commands would be command-not-found until rebuilt/republished (GHCR).
3. **Run the env pipeline** (`make brand-defaults` / secrets funnel) — see §3.

Until 1–3 land, the capability-adaptive bring-up + the A0 MCP toolkit are present in `main` but inert on the node. Phase 3 classifier is verified live (Z890 → `gpu`); the full E2E (run `up-core-capable` + confirm the MCP toolkit connects to `cipher-api:3000` and `supabase-kong` via the new `pmoves_api` route) is gated on the above.

## 3. Env-loading drift (surfaced on Z890)

`make up-data-tier` warned that required vars were blank (`NATS_PASSWORD`, `SUPABASE_URI_ALLOW_LIST`) and emitted stray `$G`/`$P`/`$i` "variable not set" warnings — i.e. `COMPOSE_ENV_FILES` / `env.shared` not fully feeding compose (and a likely unescaped `$` in an env value being interpolated). Result: data-tier containers were created but stuck **`Created`** (couldn't start cleanly). Action: verify `env.shared`/`env.tier-*` presence + the `with-env.sh` sourcing on the deploy checkout, and escape any literal `$` in secret values (`$$`).

## 4. Builder GHCR 403 + runner bounce (surfaced on Z890)

`buildx_buildkit_builder-…` logs show:
```
/moby.buildkit.v1.Control/Solve … failed to push ghcr.io/powerfulmoves/pmoves-health-wger:pmoves-latest:
  unexpected status from HEAD … blobs/sha256:… : 403 Forbidden
```
plus overlay-differ `context canceled` warnings, and both `pmoves-z890-runner-{1,2}` restarted ~mid-session. This looks like a GHCR **push-auth** failure (token/permission), consistent with the stale-token poisoning pattern (see `project_cross_compat_runner_token_poison`). Action: re-check the GHCR PAT/`GITHUB_TOKEN` the builders push with; it blocks image republish (which the agent-zero rebuild in §2 also needs).

## 5. Storage (MinIO → JuiceFS)

- **Now:** #1862 repins MinIO to its last real community tag so the data tier can pull again (interim).
- **Durable:** MinIO Community is EOL/archived (Feb 2026). JuiceFS migration spec merged (#1863) — **Z890 lane #10**, build pending (Task #5). 4090's board listed "Storage migration: JuiceFS"; that should **consume the #1863 spec**, not duplicate it (gate: JuiceFS = Z890).

## 6. No-collision note

Z890's merged work touched: a0-plugins, agent-zero image/compose, supabase notes, capability-adaptive Makefile/classifier, MinIO pin, JuiceFS spec. **No overlap** with the jellyfin-bridge / fork-sync / rotation / TAC arc. The dependency is one-directional: Z890 lands changes in `main`; the deploy spine propagates them to the node.
