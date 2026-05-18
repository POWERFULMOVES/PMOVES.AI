# MISSING-LINC Findings Ledger

**Detective:** z890-claude (Z890 node)
**Date opened:** 2026-05-17
**Skill:** `.kilocode/skills/missing-linc/SKILL.md`
**Status:** Live tracker — append new findings, mark resolved with PR link.

> Phase 1.5 manual ledger pending Phase 2 KiloCode UI (`/missing:check`, `/missing:fix-plan`, `/missing:apply`). Findings here will migrate to NATS `pmoves.topology.audit.v1` once the script wrapper lands.

---

## P0 — Critical (blocks operator workflows)

### MLF-001 — `make diag-z890` calls removed `container-agent` endpoint

**Severity:** P0
**Category:** doc-vs-code drift after dedup commit
**Discovered:** 2026-05-17 by z890-claude
**Symptom:** `make -C pmoves diag-z890` exits 1 with `Expecting value: line 1 column 1 (char 0)`.
**Root cause:** Target at `pmoves/Makefile:3113-3114` curls `http://127.0.0.1:8111/diagnostic | python -m json.tool`. The container-agent block was deduped out of `pmoves/docker-compose.z890.yml` (matches upstream commit `15fb93b0`); nothing is listening on 8111. Empty body → `json.tool` raises ParseError.
**Fix options:**
- (A) Restore container-agent service on Z890 if diagnostics still needed
- (B) Rewrite target to query `pmoves-nats-1` health/`/varz` + `docker inspect` for service statuses
- (C) Mark target deprecated, point operators to `make ps-z890` or `docker ps`
**Recommendation:** (B) — keep the diagnostic surface, source it from extant containers.
**Fixable status:** Manual (requires Makefile + design decision on diag source).

### MLF-002 — `secrets-audit` blocks funnel with 9 errors + 9 warnings

**Severity:** P0 (blocks `make secrets-funnel` clean exit)
**Category:** secret hardening + worktree hygiene + cross-service env helper compliance
**Discovered:** 2026-05-17 — DARKXSIDE ran funnel, "completed with many errors"
**Root causes (3 chains):**

1. **5 stale worktrees still hold legacy CHIT path** (`pmoves/data/chit/env.cgp.json` migration not applied):
   - `.worktrees/hook-bypass/pmoves/tools/secrets_hardening_audit.py`
   - `.worktrees/socials-launch-copy/pmoves/tools/secrets_hardening_audit.py`
   - `.worktrees/unfcu-proposal-skeleton/pmoves/tools/secrets_hardening_audit.py`
   - `.worktrees/website-landing-page/pmoves/tools/secrets_hardening_audit.py`
   - `.worktrees/win-claw-operator/pmoves/tools/secrets_hardening_audit.py`

2. **4 services still call `os.getenv` directly on secret keys** instead of `services.common.env` (file-secret support):
   - `pmoves/services/gateway/gateway/api/chit.py` — `CHIT_PASSPHRASE`
   - `pmoves/services/gateway/scripts/chit_sign.py` — `CHIT_PASSPHRASE`
   - `pmoves/services/flute-gateway/chit_signing.py` — `CHIT_PASSPHRASE`
   - `pmoves/services/flute-gateway/persona_selector.py` — `SUPABASE_KEY`

3. **Real placeholder + drift across all 6 tier files:**
   - `env.tier-data` + `env.tier-supabase`: `POSTGRES_PASSWORD = PLACEHOLDER_DB_PASSWORD_HERE_G...` ← **DB password not set!**
   - `env.tier-supabase`: `SUPABASE_DB_PASSWORD = PLACEHOLDER_DB_PASSWORD_HERE_G...`
   - 12 keys in `env.tier-data.example` missing from runtime (`MINIO_ROOT_PASSWORD`, `MINIO_ROOT_USER`, `NEO4J_AUTH`, `NEO4J_PASSWORD`, `POSTGRES_DB`, …)
   - 7 keys in `env.tier-supabase.example` missing (`ANON_KEY`, `JWT_SECRET`, `SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_DB_POOLER_ENABLED`, …)
   - 19 keys in `env.tier-api.example` missing (`ALLOWED_BUCKETS`, `AWS_DEFAULT_REGION`, `EVAL_HTTP_PORT`, `HIRAG_URL`, `MEILI_MASTER_KEY`, …)
   - 10 keys in `env.tier-llm.example` missing (`DASHSCOPE_API_KEY`, `MOONSHOT_API_KEY`, `NGC_API_KEY`, `NIM_HOST_PORT`, `OLLAMA_URL`, …)
   - 22 keys in `env.tier-media.example` missing
   - 20 keys in `env.tier-agent.example` missing

**Fix sequencing:**
1. **Prune the 5 stale worktrees** (or rebase them onto current main so they pick up the migrated path). Per memory `feedback_check_worktree_before_remove.md`, **git status each first** — multiple agents may have uncommitted work.
2. **Migrate the 4 services** to `services.common.env` — single-PR refactor, atomic.
3. **POSTGRES_PASSWORD placeholder** — write real value to `env.shared` upstream, re-run `make secrets-funnel`. This is the most urgent: services depending on Postgres are running with the placeholder.
4. **Add the missing tier keys to `pmoves/chit/secrets_manifest_v2.yaml`** — once added, funnel will regenerate them. Bulk one-PR job.
**Fixable status:** Manual (requires operator decision on stale worktree fate + real DB password).

---

## P1 — High (workflow degradation, no immediate failure)

### MLF-003 — `make health-quick` referenced in SITREP, doesn't exist in Makefile

**Severity:** P1
**Category:** doc-vs-code drift
**Discovered:** 2026-05-17 by z890-claude
**Symptom:** SITREP doc instructs `make -C pmoves health-quick`. Make returns `No rule to make target 'health-quick'. Stop.`
**Root cause:** `pmoves/docs/AGENTS/AGNOTE4482_SITREP.md:53` references a target never written. Actual health targets in Makefile: `health-dormant` (line 990), `health-summary` (line 1124). SITREP last refreshed 2026-04-01; target was likely renamed or never landed.
**Fix:** Either (a) add `health-quick` as alias for `health-summary` in `pmoves/Makefile`, or (b) update SITREP to point at `health-summary`. Either way, one-line PR.
**Recommendation:** (a) — `health-quick` is the better operator-facing name; alias both directions.
**Fixable status:** Auto-fixable (single-line Makefile alias + SITREP backlink).

---

### MLF-004 — TensorZero gateway logging ClickHouse "No count result returned" on every observability poll

**Severity:** P1
**Category:** observability backend deserialization
**Discovered:** 2026-05-17 by z890-claude (live tail of `pmoves-tensorzero-gateway-1`)
**Symptom:** Repeated ERROR-level log entries:
```
GET /internal/workflow_evaluations/projects/count
  → "Error deserializing ClickHouse response: No count result returned from database"
GET /internal/evaluations/runs/count → same
GET /internal/workflow_evaluations/runs/count → same
GET /internal/episodes/bounds → "EOF while parsing a value at line 1 column 0"
```
**Root cause hypothesis:** TensorZero UI polls observability endpoints; ClickHouse tables exist but return empty/null results. Gateway code path expects at least a count row. Likely a TZ-side bug (or schema migration missed) — gateway should handle "no rows" gracefully, not raise deserialize error.
**Impact:** Logs are noisy. Core inference path (POST `/v1/chat/completions`) appears unaffected (gateway returns HTTP 200 on `/health`). UI observability features may render blank.
**Fix options:**
- (A) Check PMOVES-tensorzero submodule for a fix in upstream `tensorflow-ai/tensorzero`
- (B) Initialize ClickHouse with seed rows so counts return 0 instead of empty
- (C) File upstream issue at TensorZero repo
**Fixable status:** Manual (needs TZ submodule investigation).

---

### MLF-006 — `pmoves-ai-lab-runner` offline + missing per-node sub-label

**Severity:** P1
**Category:** runner topology drift after hardware expansion
**Discovered:** 2026-05-18 by z890-claude (`gh api repos/POWERFULMOVES/PMOVES.AI/actions/runners`)
**Symptom:** `pmoves-ai-lab-runner` shows `status: offline`. Labels: `self-hosted, Linux, X64, ai-lab, gpu` — **no per-node sub-label** (e.g. `z890`). Workflow `sync-secrets-local.yml` resolves `[self-hosted, ai-lab]` → routes 100% to `pmoves-spark-ailab` (online). CHIT bundle never reaches Z890.
**Root cause:** This runner predates the current fleet (SPARK, 5090, B850, 3 KVMs). Before that expansion, "the" ai-lab runner was singular and equivalent to Z890. Now with multiple capable nodes, ai-lab is a class of nodes, not one node — needs per-node sub-labels to route correctly.
**Fix sequencing:**
1. **Decision needed:** revive the existing runner on Z890 (Linux/WSL2) OR retire it and adopt Pattern B (artifact upload + per-node pull, see `SECRETS_DISTRIBUTION_PATTERNS.md`) for Z890's Windows-native future.
2. If revive: bring runner online, add `z890` label via `POST /repos/{owner}/{repo}/actions/runners/{runner_id}/labels` or the runner config UI. The matrix workflow change in `feat/sync-secrets-matrix-multi-node` already expects this sub-label.
3. If retire: delete the offline runner record + update `sync-secrets-local.yml` matrix default to drop `z890` until Pattern B lands.
**Authorization signal (2026-05-18, DARKXSIDE):**
> "yes to option A and review B as method for new nodes when new hardware added"

→ Pattern A (matrix) committed in `feat/sync-secrets-matrix-multi-node`; Pattern B documented in `SECRETS_DISTRIBUTION_PATTERNS.md` as the new-node enrollment path. MLF-006 resolves when the operator picks revive-or-retire for the offline Z890 runner.
**Fixable status:** Manual (operator decision on runner fate + label edit).

---

## P2 — Warn-only (housekeeping)

### MLF-005 — MINIMAX_API_KEY set to `local-disabled` placeholder, not real key

**Severity:** P2 (expected state when secret not configured)
**Category:** secret pipeline confirmation
**Discovered:** 2026-05-17 by z890-claude (`docker exec pmoves-tensorzero-gateway-1 env | grep MINIMAX`)
**Symptom:** `MINIMAX_API_KEY=local-disabled` — same for `OPENROUTER_API_KEY`, `MOONSHOT_API_KEY`.
**Root cause:** `make secrets-funnel` ran successfully but no `MINIMAX_API_KEY` exists in GitHub Secrets, so the cascade wrote the disable marker. This is correct behavior — not a bug.
**Fix (operator action):**
```powershell
gh secret set MINIMAX_API_KEY --repo POWERFULMOVES/PMOVES.AI
make -C pmoves secrets-funnel
make -C pmoves up-tensorzero
```
**Fixable status:** Operator-only (cannot proxy through z890-claude due to zeroAccessPaths on env files + `gh secret set` requires operator's authenticated session).

---

---

## Resolution Log

*(append PR # + commit SHA when each finding lands)*

| Finding | Status | PR | Resolved by | Date |
|---------|--------|-----|-------------|------|
| MLF-001 | OPEN | — | — | — |
| MLF-002 | OPEN | — | — | — |
| MLF-003 | OPEN | — | — | — |

---

## Detective Notes

Per DARKXSIDE 2026-05-17: "now that is some MISSING-LINCKZZzz CHIT insight" — confirms these patterns (broken automation, doc-vs-code drift, blocked workflows from stale state) are exactly the gap-finding the skill is meant to catch. Phase 2 KiloCode UI will surface these in real-time; for now the ledger is the audit trail.
