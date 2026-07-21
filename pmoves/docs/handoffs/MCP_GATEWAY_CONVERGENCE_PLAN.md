# MCP Gateway Convergence + Repo Onboarding — Review Plan

**Status:** DRAFT for review (nothing in Phases 1–4 executed yet)
**Author:** 4090-claude · 2026-06-20
**Scope:** unify MCP servers under PMOVES-BoTZ-gateway (Cipher + Hi-RAG + 5 observability MCPs + new MCP submodules), onboard 3 repos to fork-sync/hardening, refresh the local stack from main, remediate P0 leakage.

Related: PR #1849 (serializer fix, merged-pending) · PR #1361 (5 observability MCP servers, **already merged**) · `pmoves/docs/operations/GITHUB_APP.md` · `.claude/skills/fleet-fork-sync` (only on `origin/feat/fleet-fork-sync-skill`).

---

## 0. Current state (verified 2026-06-20)

- **Cipher** healthy in-container (`pmoves-cipher-api-1`, `/health` 200), but host `:8105` unreachable — Docker Desktop isn't publishing ports on the `pmoves_*` networks (kong on `supabase_default` publishes fine). Operator-class WSL2 issue.
- **gateway-agent** (:8100, "orchestrates 100+ MCP tools via Agent Zero") crash-loops on a **stale image** — the `nats_integration` COPY fix is already on `main` (commit `778d90c35`); the deploy checkout is on `fix/ghcr-matrix-paths-gate` (**45 behind main**) which lacks it.
- **BoTZ-gateway** (`PMOVES-BotZ-gateway/`, port 8052, fork of `microsoft/mcp-gateway`): reverse-proxy/control-plane for MCP servers (`POST /adapters`, `/adapters/{name}/mcp`, `/mcp` router). `pmoves_registry/` is a stub — **no Cipher/Hi-RAG/observability adapters registered yet**.
- **5 observability MCP servers exist** (PR #1361): `pmoves/tools/observability/mcp_{grafana,prometheus,loki,jaeger,tensorzero}.py` + `pmoves/docs/OBSERVABILITY_MCP_SERVERS.md`. Not yet fronted by the gateway.

---

## Phase 0 — Full refresh from main (unblocks ports + gateway-agent)

**Goal:** the running stack rebuilds from current `main` so (a) `pmoves_*` networks are recreated → `:8105` publishes, and (b) `gateway-agent` rebuilds with the COPY fix.

**Risk:** the main checkout is on `fix/ghcr-matrix-paths-gate` with substantial uncommitted/working-tree changes (per session-start `git status`). "Update to main" must not lose that work.

**Runbook (operator-confirmed):**
1. Triage main-checkout dirty state: `git -C . status --short`. Decide per file — commit valuable changes to their own branches, stash the rest (`git stash push -m pre-main-refresh`). Do **not** blanket-discard.
2. Update deploy checkout to main: `git fetch origin && git switch main && git pull` (or rebase the ghcr branch later — separate concern).
3. Stack down/up via Known Roads: `make -C pmoves down` then `make -C pmoves secrets-funnel` (now safe — serializer fix prevents the env.tier-agent corruption) then `make -C pmoves up` (rebuilds images incl. gateway-agent + recreates `pmoves_*` networks).
4. Verify: `curl localhost:8105/health` (host reach restored), `docker ps | grep gateway-agent` (no crash-loop), `docker inspect pmoves-cipher-api-1 --format '{{json .NetworkSettings.Ports}}'` (no longer empty).

> If the dirty state is too risky to move, fallback = recreate only the `pmoves_*` networks via down/up on the current checkout (fixes ports) and rebuild gateway-agent from a clean `main` worktree — but compose project-name mismatch makes the single-checkout path cleaner.

---

## Phase 1 — BoTZ-gateway as the unified MCP front (highest unlock)

**Why first (per operator):** botz + gateway-agent unlock 100+ tools + agents; quickest validation path is via MCP skills.

Register one adapter per backend on BoTZ-gateway (`POST http://localhost:8052/adapters`), persisted in `PMOVES-BotZ-gateway/deployment/` (or a boot seed in `pmoves_registry/`) so they survive restart:

| Adapter | Backend | Transport/URL |
|---|---|---|
| `cipher` | Cipher Memory | sse `http://cipher-api:8105/mcp/sse` |
| `hirag` | Hi-RAG v2 via `pmoves-hirag-mcp` bridge | stdio/streamable-http (containerize the bridge) |
| `grafana` / `prometheus` / `loki` / `jaeger` / `tensorzero` | the 5 #1361 servers | stdio (`python -m pmoves.tools.observability.mcp_<name>`) |
| `jcodemunch` | PMOVES-jcodemunch-mcp | per its README |

Then **consolidate client config to a single gateway entry** (keep direct entries as transition fallback, retire after validation — same discipline as `_pmoves-cipher-legacy-python-wrapper` in `.claude/mcp.json`):
- `.claude/mcp.json`: add `pmoves-mcp-gateway` → sse `http://localhost:8052/mcp` (Bearer `${BOTZ_GATEWAY_TOKEN}`).
- `pmoves/docker/pmoves-4090-web/profile.yaml`: replace per-server blocks with the single gateway server.

**Validation:** via MCP skills — list tools through the gateway, round-trip a low-effect tool from each adapter (e.g. cipher store/search, prometheus query, hirag query).

---

## Phase 2 — Onboard 3 repos (BLOCKERS first)

**Blockers (resolve before edits):**
1. `fork-sync.yml` + fleet-fork-sync skill live only on `origin/feat/fleet-fork-sync-skill` → base onboarding edits there or merge it first.
2. `pmoves-hirag-mcp` GitHub repo doesn't exist → `gh repo create POWERFULMOVES/pmoves-hirag-mcp --private --source=pmoves-hirag-mcp --push` first.
3. `pmoves-cipher-mcp` local tree differs from remote (recently modified `pmoves_registry/`+README) → diff & push local-only work to the hardened branch **before** pinning, or it's lost.

**`.gitmodules` (branch decisions):** `pmoves-cipher-mcp` → `PMOVES.AI-Edition-Hardened` (its actual default); `PMOVES-jcodemunch-mcp` → `main`; `pmoves-hirag-mcp` → `PMOVES.AI-Edition-Hardened`.
- Convert `pmoves-cipher-mcp` checked-in tree → submodule: backup, `git rm -r --cached pmoves-cipher-mcp`, move aside, `git submodule add -b PMOVES.AI-Edition-Hardened <url> pmoves-cipher-mcp`, diff/reconcile, commit.
- `git submodule add` the other two.

**Workflow edits:** add `Pmoves-cipher` to `fork-sync.yml` `repositories:` + `FORKS` (`campfirein/byterover-cli|Pmoves-cipher|`, no branch override → tracks `main`). Add all four to `submodule-update-check.yml` `TRACKED_SUBMODULES`. New MCP submodules are PMOVES-original (no upstream) → **only** the gitlink layer, never `fork-sync.yml`'s FORKS.

**Private-repo auth:** PMOVES.AI App is installed org-wide (All repos) so `pmoves-cipher-mcp` is covered at install; CI submodule checkout needs an App token scoped (`repositories:` incl. it) — default `GITHUB_TOKEN` 403s on private submodules. (`GITHUB_APP.md:3-8,14-50,72`.)

---

## Phase 3 — Pmoves-cipher CRITICAL merge (its own effort)

796 ahead / 3096 behind `campfirein/byterover-cli` → trips both auto-merge guards → **manual** merge. Multi-hour, conflict-heavy. **NEVER squash** (severs shared history → every future sync re-conflicts). Clone hardened/main, add upstream, `merge --no-ff`, resolve preserving the 796 PMOVES commits, commit alone, push fresh branch, PR with `--merge`. CI (build + Trivy) is the real gate.

---

## Leakage P0 remediation (task #7 — parallel, mostly operator)

- **Rotate now** (recoverable from history): `JELLYFIN_API_KEY` (tier-media env), `RENDER_WEBHOOK_SHARED_SECRET` (render-webhook `.additions`), Postgres `PGPASSWORD`.
- **Untrack** generated env files (`git rm --cached` — operator; files are zero-access).
- **Code fix (doable now):** replace hardcoded `PGPASSWORD` in `pmoves/data/consciousness/load_supabase_chunks.py:60,76` with env lookup.
- **`.gitignore`:** add `pmoves/env.*.additions`, `pmoves/env.supabase`.
- **Verify** `GH_APP_SEC` (other multi-line PEM-class manifest entry) is newline-safe under the #1849 serializer fix.

---

## Suggested execution order

1. **Phase 0** (full refresh from main) → validates Cipher host-reach + gateway-agent.
2. **Phase 1** (BoTZ-gateway wiring + observability MCPs) → the 100+ tool/agent unlock; validate via MCP skills.
3. **Leakage code fix + .gitignore** (task #7 non-operator parts) → small PR.
4. **Phase 2** (repo onboarding) once blockers cleared.
5. **Phase 3** (Pmoves-cipher CRITICAL merge) as a dedicated effort.

Operator-gated: dirty-checkout triage (P0), secret rotation + untrack (#7), private-repo token scope, the fork-sync base branch.
