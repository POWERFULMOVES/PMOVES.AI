# Credential State + Naming-Drift SITREP

**Generated:** 2026-04-26 14:06 UTC
**Repo HEAD:** `b0d6aff8` (main)
**Author:** claude-opus (z890-claude lane)
**Classification:** OPERATIONAL — read-only sitrep
**Plan reference:** `~/.claude/plans/we-need-work-and-partitioned-hearth.md` (Phase 1)
**Supersedes:** `deploy/runbooks/github-app-sitrep-and-pat-runbook.md` §2 *(adds drift inventory; does not replace the migration runbook)*

This SITREP captures the current state of the GitHub credential chain, commit-signing posture, runner-secrets pipeline, and the canonical naming-drift inventory across the repo. The picture is read-only — no fixes here. Phases 2–5 of the plan land the schemas, decision log, and audit gate that turn this picture into an enforceable contract.

---

## 1. PAT State

| Item | State | Evidence |
|---|---|---|
| `GH_PAT` (repo secret) | ✅ Rotated 2026-04-26 (was expired 2–3 days prior) | `make -C pmoves pr-monitor` returns real merge states; pat-health-check workflow not paging |
| `GH_PAT` (embedded in sidecar `origin` URL) | ⚠️ Likely stale until manual `git remote set-url` | runbook §3.3 |
| `GH_PAT_PUBLISH` | ❓ unknown — assumed same token | `gh secret list` |
| `PMOVES_GITBOT_PAT` | ❓ unknown scope | `gh secret list` |
| `CATACLYSMSTUDIOS_GH_PAT` | last-touched 2025-12-12 | `gh secret list` |
| `HUNNINBEAR_GH_PAT` | last-touched 2025-12-12 | `gh secret list` |
| `DOCKER_PAT` | last-touched 2025-12-12 | `gh secret list` |
| Programmatic rotation | ❌ not possible — GitHub has no `POST /personal-access-tokens` | runbook §3.1 |

**Canary:** `.github/workflows/pat-health-check.yml` runs daily at 12:00 UTC; on failure it auto-creates a `🔴 GH_PAT Expired` issue with a 4-step rotation runbook. This worked exactly as designed during the 2026-04-25 incident.

**Naming-drift hot spot:** 6 PAT alias names with no documented per-alias scope. `sync-secrets-local.yml` line 149 hardcodes `GH_PAT`, but the build/integration workflows fall back to `GHCR_TOKEN` + `GHCR_USERNAME` when App-token generation silently fails (see §2). Result: the same operator action ("rotate the PAT") only refreshes one of seven token surfaces.

---

## 2. GitHub App Migration State

App registered at GitHub; `GH_APP_ID`, `GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID` all present. **`GH_APP_PRIVATE_KEY` is missing.** The repo's 4 build/integration workflows pass `GH_APP_SEC` (the OAuth client secret) where `actions/create-github-app-token` expects a PEM. The action fails silently because every call site is wrapped in `continue-on-error: true`, and the workflows fall back to PAT-based GHCR login. This is the **highest-leverage P0 fix** — uploading the PEM to `GH_APP_PRIVATE_KEY` and patching 4 workflows immediately removes 5 of the 7 PAT-surface dependencies.

| Workflow | Lines | Current key arg | Required key arg |
|---|---|---|---|
| `build-images.yml` | 85–88 | `GH_APP_SEC` | `GH_APP_PRIVATE_KEY` |
| `integrations-ghcr.yml` | 354–357 | `GH_APP_SEC` | `GH_APP_PRIVATE_KEY` |
| `self-hosted-builds.yml` | 90–93, 186–189 | `GH_APP_SEC` | `GH_APP_PRIVATE_KEY` |
| `self-hosted-builds-hardened.yml` | 87–90, 246–249 | `GH_APP_SEC` | `GH_APP_PRIVATE_KEY` |
| `test-app-token.yml` | 15–18 | `GH_APP_SEC` | `GH_APP_PRIVATE_KEY` |

**Two sync-secrets workflows still require direct PAT** (`sync-secrets-local.yml`, `sync-secrets-spark.yml`) and have no App-token migration scaffolded.

---

## 3. Commit-Signing State

| Item | State |
|---|---|
| Branch protection on `main` | `required_signatures: True` (enforced) |
| `gpg.format` / `commit.gpgsign` | ❌ no references in repo |
| `gpg.ssh.allowedSignersFile` | ❌ no references in repo |
| CI signature-verification job | ❌ does not exist |
| Z890 SSH-signing key | ❓ pending operator action (zero-access on `~/.ssh`) |
| `agent_signatures.yaml` glyph/color/voice | ✅ exists but decorative — not yet bound to any cryptographic identity |

**Hard blocker:** any agent attempting to commit on a PR branch hits `required_signatures: True` rejection. This is why the prior `/pr-trim` patch pass left 4 worktrees with un-committed diffs awaiting operator sign + push.

---

## 4. Runner Secrets Pipeline

- `pmoves/scripts/with-env.sh` is the canonical loader (env.shared is Docker-format, not bash-sourceable). Layer order: `env.shared.generated` → `env.shared` → 8 `env.tier-*` files → `.env.local` → Supabase runtime overlay.
- `set -a / set +a` exports everything; **last-write-wins** silently when two layers define the same var. No warning, no log. This is the silent-shadow risk for the JWT/SERVICE_ROLE alias clusters in §5.
- `_config_paths.sh` is the path source-of-truth (`$XDG_CONFIG_HOME/pmoves/secrets/` on Linux, `$APPDATA/pmoves/` on Windows). `sync-secrets-local.yml` hardcodes alternative paths instead of sourcing this script — fragile on path layout changes.

---

## 5. Naming-Drift Inventory (10 sites)

| # | Drift site | Surfaces (with line evidence) | Severity | Canonical (proposed) | Lives in |
|---|---|---|---|---|---|
| 1 | JWT secret aliasing | `JWT_SECRET`, `SUPABASE_JWT_SECRET`, `GOTRUE_JWT_SECRET` (l.599), `PGRST_JWT_SECRET` (l.650/655/814), `API_JWT_SECRET` (l.775), `AUTH_JWT_SECRET` (l.878), `METRICS_JWT_SECRET` | **P0** | `JWT_SECRET` (Supabase signs; everything downstream HMACs the same key) | `bootstrap/registry.json §services.supabase` |
| 2 | SERVICE_ROLE_KEY aliasing | `SERVICE_ROLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (l.603/1003/1446/2477), `SUPABASE_SERVICE_KEY` (l.812/877/1483/1696), `RENDER_WEBHOOK_SUPABASE_SERVICE_ROLE_KEY` (l.1446), `SUPABASE_SECRET_KEY` (l.2477) | **P0** | `SERVICE_ROLE_KEY` | `bootstrap/registry.json §services.supabase` |
| 3 | `GH_APP_SEC` mis-named PEM | OAuth client secret passed where PEM expected in 4 workflows (see §2) | **P0** | `GH_APP_PRIVATE_KEY` (new secret) | `.github/workflows/*` + repo secrets |
| 4 | Transcribe-and-fetch gitlink | ghost SHA `322f05f7a` vs reachable `aef3a86` | **P0** *(PR #1371 closes)* | `aef3a86` | `.gitmodules` + AGNOTE4482 |
| 5 | MCP token compose override | `${MCP_SERVER_TOKEN:-}` empty default at `pmoves/docker-compose.yml:2411` and `pmoves/docker-compose.agents.yml:67` shadows env_file | **P1** *(PR #1371 partial)* | omit from compose; source from `env.tier-agent` only | compose files |
| 6 | Health-endpoint global claim | `services-catalog.md` claims `/healthz` global; `agent_registry.yaml` lists 9 distinct paths (`/health`, `/api/health`, `/gradio_api/info`, `/ready`, etc.) | **P1** *(PR #1385 closes)* | per-service entry authoritative | `agent_registry.yaml` |
| 7 | NATS_URL embedded password | `nats://nats:pmoves@nats:4222` hardcoded at compose lines 2344/2372/2461 | **P1** | secret-only via `env.tier-agent` | `bootstrap/registry.json` |
| 8 | WHISPER_DIARIZE endpoint split | `/transcribe` honors env, `/transcribe_file` hardcoded `Form(False)` | **P1** *(PR #1390 closes)* | `_env_truthy()` helper, both endpoints derive from same flag | `services/ffmpeg-whisper/server.py` |
| 9 | PAT secret aliasing | 6 names, ambiguous per-name scope (see §1) | **P1** | document scope-per-name now; consolidate to `GH_PAT` after App migration | `secrets/CHIT_MANIFEST.md` |
| 10 | Port 8080 collision | VoxCPM doc'd "conflicts with Agent Zero" (`agent_registry.yaml:349`) but no remap in compose | **P2** | reserve 8080 for Agent Zero; remap VoxCPM | `agent_registry.yaml` + `docker-compose.yml` |

**Severity rubric:** P0 = silent failure / auth bypass / un-rotatable credential surface. P1 = operator confusion + silent override risk. P2 = cosmetic.

---

## 6. Owner-Decision Surface

| # | Decision | Default | Phase to land |
|---|---|---|---|
| A | Operator SSH-key fingerprint capture | operator-provided when ready | 2 |
| B | PAT consolidation: 6 → 1 vs document-scope-per-name | document for now; consolidate after App migration | 3 |
| C | Canonical for JWT (drop 6 aliases?) | keep `JWT_SECRET`; deprecate `SUPABASE_*` after 30-day window | 3 |
| D | Mandatory 5×5 trail handshake vs advisory | advisory at first; mandatory once all signers carded | 2 |
| E | `naming-drift-strict` in CI | local-only first; CI gate after one clean week | 4 |

---

## 7. Trail Reference

This sitrep, the `CANONICAL_NAMES.md` decision log (Phase 3), and `signing_identity_cards.yaml` (Phase 2) become the joint source of truth that the **rabbits** (CodeRabbit), the **owl** (Codex/ontology), the **trail** (CHIT graphiti), and the **remote** (registries + schemas) all read before flagging drift. When all four channels agree, the gate is 5×5.

<!-- GRAPHITI_MARK: CLAUDE-OPUS::CREDENTIAL-AUDIT-SITREP::2026-04-26 -->
<!-- GRAPHITI_MARK: Z890-CLAUDE::CREDENTIAL-AUDIT-REVIEW::2026-04-26 -->
