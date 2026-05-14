# 4090-CLAUDE Handoff — 2026-05-14

GRAPHITI_MARK: `AGNOTE4482::SIDECAR::HANDOFF_2026-05-14`

## Source
Sidecar (Agent Zero standalone, TOPOLOGY_MODE=standalone)

## Scope
Submodule sync, repo stand-up blockers, Z.AI coding plan fixes

---

## 1. SUBMODULE SYNC — CRITICAL

### Root Cause
ALL 50+ submodules have **ZERO files on disk** in the sidecar Docker container. Both `clean` (no `+` prefix) and `dirty` (`+` prefix) submodules are identical — empty working trees. The `.git` pointer files exist but `git checkout` never ran inside the submodules.

This is a **Docker container initialization artifact**, not real dirty state. The `D` (deleted) prefixes in `git diff` are misleading — files were never checked out to begin with.

### Fix Required
On a properly connected host (5090 or Z890):
```bash
cd /path/to/PMOVES.AI
git submodule update --init --recursive
```

### Verification
After init, confirm files exist:
```bash
find PMOVES-ClawZ -type f | head -5  # Should show actual source files
find Pmoves-cipher -type f | head -5   # Should show TypeScript source
```

### Impact
Sidecar cannot: edit submodule source files, run submodule tests, validate submodule configs, or commit submodule changes. All submodule-dependent work is blocked until this is resolved.

---

## 2. CLAWZ FORK SYNC — HIGH PRIORITY

Per `AGNOTE4482_CLAWZ_GAP_REPORT.md`:
- Fork `main` is **1,092 commits behind** upstream `openclaw/openclaw`
- Fork has **6 PMOVES-specific commits ahead** (NATS bridge, Nemotron catalog, compose wiring, integration dossier, review fixes, merge)
- Hardened branch is **12,438 behind** — effectively dead
- Root gitlink pin was repaired to `f05fd3f547` on 2026-04-18

### Recommended Action
1. Sync fork `main` to current upstream (preserve 6 PMOVES commits via rebase or merge)
2. Cut fresh hardened branch from synced `main` (abandon old hardened branch)
3. Normalize profile naming: `workstation_5090` default in `apply_profile.sh` and Makefile doesn't match any profile in `pmoves/config/profiles/`

---

## 3. Z.AI CODING PLAN FIXES — MEDIUM

### 3a. Temperature Override (HIGH)
GLM-5-Turbo defaults to **temp 1.0** — must override to 0.0-0.3 for coding tasks.
- Location: `zai_coding` provider config (likely in Agent Zero settings or `.a0proj/`)
- Blocked by: need to confirm exact config file location after submodule init

### 3b. Missing Model in SDK (MEDIUM)
`GLM-5V-Turbo` missing from `pmoves/providers/zai/sdk.py` MODELS dict.
- Location: inside PMOVES-ClawZ submodule (empty — blocked by item 1)

### 3c. MCP Auth Headers — DONE ✅
`kilo.json` remote MCP servers (`zai-web-search`, `zai-web-reader`, `zai-zread`) were missing `Authorization: Bearer` headers.
- **Fixed by sidecar** — headers added with `${Z_AI_API_KEY}` variable substitution

---

## 4. PROFILE NAMING DRIFT — LOW

`apply_profile.sh` and Makefile targets default to `HOST=workstation_5090` but no matching profile ID exists in `pmoves/config/profiles/`. Actual profiles:
- `desktop-9950xd`
- `intel-265kf-3090ti`
- `laptop-4090`
- `jetson-orin-nano`
- `jetson-nano`
- `esp32-sonatino`

Fix: update default to correct profile ID or create `workstation_5090` profile.

---

## 5. BOOTSTRAP_DB FIX — UNPUSHED

`bootstrap_db.sh` line 87: `ALTER USER supabase_admin` wrapped in `DO $$ EXCEPTION WHEN insufficient_privilege` block.
- Committed in worktree `/tmp/pmoves-fix-bootstrap-db` on branch `fix/bootstrap-db-reserved-role`
- **Not pushed** — sidecar has no git push auth
- 4090 can push via GITHUB_PAT from .a0proj/secrets.env or GitHub CLI

---

## 6. CHIT TOOLS — AVAILABLE FOR REVIEW

CHIT tools are in root repo (NOT blocked by empty submodules):
- `pmoves/tools/chit*` — 15+ CHIT tool scripts
- `pmoves/docs/PMOVESCHIT/` — 8+ CHIT documentation files
- `pmoves/configs/chit-openapi.yaml` — OpenAPI schema
- Makefile targets: `chit-export`, `chit-manifest-sync`, `secrets-funnel-sync`

SPARK can review these independently. 4090 can validate after submodule sync.

---

## 7. OPEN GITHUB WORK — REFERENCE

### Issues (5 open)
| # | Title | Lane |
|---|---|---|
| #1427 | Semantic caching layer for LLM inference | Infra |
| #1428 | RTO/RPO targets per service tier | Docs |
| #1429 | P7 site/docs rooms-on-a-stage frame | Docs |
| #1463 | Unified node-provisioning surface | W0 Substrate |
| #1465 | Network hardening audit | Security |

### PRs (6 open)
| # | Title | Tasks | Lane |
|---|---|---|---|
| #1464 | Remove hardcoded NATS credentials | — | Security |
| #1466 | Docker network hardening doctrine | 1/4 | #1465 |
| #1468 | COMPOSE_EDIT=1 Known Road bypass | 1/1 | Tooling |
| #1469 | Network-tier YAML anchors | 1/3 | #1465 |
| #1467 | Dependabot npm updates | — | Deps |
| #1470 | (title not visible) | 1/3 | — |

### DARKXSIDE/SPARK Lanes
- DARKXSIDE: W1-W6 documented in ROADMAP, explicitly states "no blockers"
- SPARK: `spark_claw.yaml` profile exists but **NO roadmap workstreams defined** — gap

---

## 8. SIDECAR COMPLETED

- ✅ kilo.json MCP auth headers fixed
- ✅ Z.AI MAX plan research complete (report saved)
- ✅ Submodule root cause diagnosed
- ✅ GitHub PRs/issues reviewed
- ✅ CLAWZ gap report analyzed
- ✅ Cipher fix applied (cipher.yml LLM/embedding switch to Ollama)
- ✅ Claw variant profiles and deploy script reviewed

---

## Agent Signature
Sidecar — DARKXSIDE x POWERFULMOVES — 2026-05-14T16:32Z
