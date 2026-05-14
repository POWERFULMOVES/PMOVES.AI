# P1 Fork Sync Audit Report
## PMOVES Agent Zero Hardened Fork vs Upstream

| Field | Value |
|---|---|
| **Report Date** | 2026-04-25 |
| **Priority** | P1 — Highest remediation priority |
| **Fork Repo** | `POWERFULMOVES/PMOVES-Agent-Zero` |
| **Fork Branch** | `PMOVES.AI-Edition-Hardened` |
| **Upstream Repo** | `agent0ai/agent-zero` |
| **Upstream Target** | v1.9 (commit `3fa8481ba252`) |
| **Pin Commit** | `2e000aa304e52ed47ca4d5eb4a9ce64a35c916a2` (2026-03-07) |
| **Upstream Gap** | **604 commits** |
| **Previous Gap** | 502 commits to v1.3 (reported 2026-03-28) |
| **Gap Growth** | +102 commits in ~28 days |

> **⚠️ CHIT Intrusion Detected**: Ladybug graph memories surfaced stale claims of "502 commits behind upstream v1.3" — this data is from the March 28 report and is superseded by the current audit (604 commits vs v1.9). All stale memory references should be purged or updated.

---

## 1. Executive Summary

The PMOVES hardened fork of Agent Zero is **604 commits behind upstream v1.9**, a gap that has grown by 102 commits since the last audit on March 28, 2026. The gap is no longer cosmetic — upstream has executed **3 critical architectural rewrites** (WebSocket, self-update, plugin system) that make simple rebasing high-risk. Of the 34 PMOVES overlay files, **6 will conflict** with upstream changes, 2 at CRITICAL severity. The recommended remediation is a **Fresh Overlay** strategy (Option A), estimated at 8–12 hours of focused engineering work.

### Risk Matrix

| Risk | Severity | Likelihood | Impact |
|---|---|---|---|
| WebSocket architecture breakage | 🔴 Critical | High | Fork becomes non-functional |
| Model provider config incompatibility | 🔴 Critical | High | No LLM connectivity |
| Security patch gap (CVE-2026-4307) | 🟠 High | Confirmed | Path traversal vulnerability open |
| Plugin system incompatibility | 🟠 High | Medium | PMOVES agent profiles broken |
| Dependency conflicts | 🟡 Medium | Medium | Build/runtime failures |
| Doc merge conflicts | 🟢 Low | Low | Cosmetic, easily resolved |

---

## 2. Current State

### 2.1 Pin Commit Anatomy

The fork's pin commit `2e000aa` is a **merge commit** with two parents:

| Parent | Commit | Side | Role |
|---|---|---|---|
| Parent 1 | `2a24c820a8` | PMOVES | Hardened branch tip (pre-merge overlays) |
| Parent 2 | `fa65fa3ddc` | Upstream | Fork point from upstream main |

The upstream gap is measured from `fa65fa3ddc` (Parent 2) to `3fa8481ba252` (upstream v1.9) = **604 commits**.

### 2.2 Gap Trajectory

| Date | Upstream Target | Commit Gap | Growth Rate |
|---|---|---|---|
| 2026-03-28 | v1.3 | 502 commits | — (baseline) |
| 2026-04-25 | v1.9 | 604 commits | ~3.6 commits/day |

At this rate, the gap will exceed **700 commits** within 30 days if unaddressed.

---

## 3. PMOVES Overlay Inventory

### 3.1 Overview

- **Total overlay commits**: 24 (21 pre-merge first-parent + 1 post-merge + PR branch commits)
- **Unique files touched**: 34
- **Conflicting files**: 6 (17.6%)
- **Non-conflicting files**: 28 (82.4%)

### 3.2 Post-Merge Overlay (1 commit)

| # | Commit | Description | Files |
|---|---|---|---|
| 1 | `a583eb8` | feat(config): add MiniMax provider as BoTZ tactical partner | `conf/model_providers.yaml` (+18) |

### 3.3 Pre-Merge First-Parent Line (21 commits)

| # | Commit | Description | Primary Files |
|---|---|---|---|
| 2 | `2a24c82` | fix(security): backport PR #8 hardening | Multiple |
| 3 | `ee1aed4` | docs: add CLAUDE.md with architecture/security posture | `CLAUDE.md` |
| 4 | `4bc9b9a` | audit(dox): align DoX with Hardened + fix canonical patterns (#5) | `.coderabbit.yaml` |
| 5 | `869c021` | Merge PR #7 from fix/phase-d-hardening | — |
| 6 | `088b493` | fix(security): Phase C hardening — NATS auth + non-root containers (#6) | Docker files, env files |
| 7 | `6296dd6` | feat(audit): enable NATS flag + PMOVES audit gate CI | `.github/workflows/pmoves-audit.yml` |
| 8 | `3b01fd4` | docs(codex): add codex operator home | `.codex/README.md` |
| 9 | `a8fac57` | merge: sync upstream agent0ai/agent-zero v0.9.8 | — |
| 10 | `0ff6097` | feat(pmoves-ai): Add PMOVES.AI integration patterns | `PMOVES.AI_INTEGRATION.md` |
| 11 | `d8eb467` | feat(credentials): universal credential bootstrap scripts | `scripts/bootstrap_credentials.sh`, `.ps1` |
| 12 | `9963665` | feat(pmoves-ai): Add PMOVES.AI integration patterns (#2) | `PMOVES.AI_INTEGRATION.md` |
| 13 | `81d791f` | docs(branching): Add branching strategy documentation | `docs/branching-strategy.md` |
| 14 | `0eef070` | fix(persona): silent failures and error handling | Persona files |
| 15 | `ee04a25` | fix(personas): CodeRabbit PR review comments | Persona files |
| 16 | `bfbce6e` | Merge into feat/personas-first-architecture | — |
| 17 | `8b37ad0` | feat: persona-based agent creation with Supabase | `python/api/persona_agent_create.py`, `python/helpers/persona_integration.py`, `tests/test_persona_integration.py`, `agents/pmoves_custom/prompts/agent.system.main.md` |
| 18 | `8642210` | Merge branch agent0ai:main | — |
| 19 | `5cbda82` | feat(tensorzero): TensorZero gateway provider | `conf/model_providers.yaml` (+10) |
| 20 | `a8f3bc8` | feat(monitoring): Prometheus metrics endpoint | `run_ui.py` (+44), `requirements.txt` (+3,-1) |
| 21 | `8d2da27` | Merge branch agent0ai:main | — |
| 22 | `4d99aa1` | chore(security): CODEOWNERS + Dependabot | `.github/CODEOWNERS`, `.github/dependabot.yml` |

### 3.4 Branch Commits from Merged PRs

| Commit | Description |
|---|---|
| `580ddf5` | fix(security/L1): cross-cutting hardening — NATS auth, export strip, cred defaults |
| `3bef994` | fix(security): re-enable path containment + drop root supervisord programs |
| `45b1553` | fix(security): Phase C hardening — NATS auth + non-root containers |
| `3d7b8c2` | fix(review): address CodeRabbit PR #5 feedback |
| `f3e76da` | fix(audit): align DoX with canonical patterns |
| `e59fc32` | feat(docker): port and MCP settings configurable via env vars |
| `702dbbd` | refactor(code-quality): Phase 3 & 4 improvements |
| `0b56dcd` | feat(agents): add pmoves_custom agent profile |

### 3.5 Branch-Tip Commits (NOT on Hardened branch)

> These exist on separate feature branches and are **not included** in the 24-overlay count.

| Branch | Commit | Description |
|---|---|---|
| `feature/agent-zero-nim-provider-rebased` | `f5307d9` | NVIDIA NIM provider → `conf/model_providers.yaml` |
| `feature/agent-zero-nats-contract-docs` | `0443acb` | NATS subject contract documentation |
| `fix/agentzero-review-2026-03-01` | `cf2dc95` | PR #8 merge (a2a canonical path + path containment) |

### 3.6 Additional Files Touched

`python/api/image_get.py`, `python/helpers/settings.py`, `pmoves_announcer/__init__.py`, `pmoves_common/__init__.py`, `pmoves_health/__init__.py`, `pmoves_registry/__init__.py`

---

## 4. Upstream Breaking Changes (604 commits, 940 files)

### 4.1 🔴 CRITICAL — WebSocket Architecture Rewrite

The entire server architecture has been rewritten from a legacy WebSocket system to a new WsHandler/WsManager pattern.

| Commit | Change |
|---|---|
| `1d81f72a` | Backend core rewrite — WsHandler + WsManager + handler migration |
| `af4d5db7` | Frontend adapter for new WebSocket architecture |
| `07f94ef4` | Fix WebSocket CSRF validation failure on Chromium over HTTPS |
| `651deac6` | WebSocket wildcard event support |
| `7eb6d5b1` | WebSocket handler lifecycle optimization |
| `28002047` | WebSocket dynamic endpoints |
| `07b5e056` | **Delete ALL legacy WebSocket system files** |

**PMOVES Impact**: `run_ui.py` (overlay file with +44 Prometheus lines) is heavily modified — the server architecture it targets **no longer exists**. Prometheus endpoints must be reimplemented using the new WsHandler architecture.

### 4.2 🟠 HIGH — Self-Update System Rewrite

| Commit | Change |
|---|---|
| `eafe51a6` | Refactor self-update to use native Git operations instead of file sync |
| `e0dae52b` | Replace file sync with capability detection |
| `261c4d61` | CLI trigger script with major version validation |
| Multiple | Self-update modal/UI refactors |

**PMOVES Impact**: `docker/run/Dockerfile` and `run_A0.sh` have self-update changes that overlap with PMOVES hardening.

### 4.3 🟠 HIGH — Plugin System Overhaul

| Commit | Change |
|---|---|
| `0061b3a5` | Built-in plugin discovery cards |
| `c9eadf40` | Built-in Skills selector plugin |
| `8240edb4` | Plugin Skills guidance for uninstall() |
| `1eb78607` | Remove scan queue, enable parallel plugin scans |
| `2dc6bd54` | Rename marketplace to plugin hub |
| `86dca86f` | Restore legacy, plugins, agent0 profile prompts |
| `f4fd9126` | Restore agent.system.tool.call_sub.py dynamic loader |

**PMOVES Impact**: Agent profile/prompt system changed — `agents/pmoves_custom/prompts/agent.system.main.md` may need updates to conform to new profile prompt conventions.

### 4.4 🟠 HIGH — Model Config/Preset System

| Commit | Change |
|---|---|
| `09a74381` | Data-driven model search + default presets |
| `1b0c57a3` | Refactor model search & reorganize model_providers.yaml |
| `9ff4133d` | Extract reusable model-field component, split store, unify API key lifecycle |
| `25e0ec63` | @extensible decorator on get_api_key() |
| `1f678657` | OpenRouter extra_headers fix |
| `ac5d4385` | OpenRouter extra_headers fix (follow-up) |

**PMOVES Impact**: `conf/model_providers.yaml` has been **completely reorganized** with new schema, category headers, and data-driven search. PMOVES TensorZero (+10 lines) and MiniMax (+18 lines) additions likely use the old YAML structure.

### 4.5 🟡 MEDIUM — Code Execution Tool Extracted to Plugin

| Commit | Change |
|---|---|
| `63651deb` | Extract code execution tool to plugin |

**PMOVES Impact**: `docker/run/fs/exe/run_A0.sh` changed — PMOVES supervisor/path containment logic may conflict.

### 4.6 🟡 MEDIUM — Docker/Container Changes

| Commit | Change |
|---|---|
| `261c4d61` | CLI trigger script for self-update |
| `43a519f5` | Fallback environment variable support in Docker release workflow |
| `75b8085b` | Add unzip to Docker base packages |

**PMOVES Impact**: `docker/run/Dockerfile` has upstream package additions that overlap with PMOVES non-root container hardening.

### 4.7 🟡 MEDIUM — Security Fixes

| Commit | Change | Severity |
|---|---|---|
| `0e3e8a15` | CVE-2026-4307 path traversal fix in `download_work_dir_file` | Critical CVE |
| `30835c2f` | lxml-html-clean 0.3.1→0.4.0 (XSS CWE-79 CVSS 8.4) | High CVE |
| `dfe691d5` | Security floor pins for 6 transitive dependencies | Defense in depth |

**PMOVES Impact**: `requirements.txt` changes conflict with PMOVES additions (prometheus-client). **The fork is currently vulnerable to CVE-2026-4307 and an XSS vector.**

### 4.8 🟡 MEDIUM — UI Server Restructuring

| Commit | Change |
|---|---|
| `b94d4b79` | Comprehensive UI server restructuring |
| `d02dda36` | BIG PYTHON REFACTOR |
| `ab9fc4ee` | Refactor extensions to async/sync API |

**PMOVES Impact**: `run_ui.py` complete rewrite — reinforces CRITICAL WebSocket conflict.

### 4.9 🟢 LOW-MEDIUM — Chat Branching

| Commit | Change |
|---|---|
| `1bd5bc01` | ID-based log↔history linking for precise branch trimming |
| `aafe7f4a` | Fix chat branching not trimming agent history |

### 4.10 🟢 LOW — Telegram Plugin

| Commit | Change |
|---|---|
| `af60a6e2` | Message formatting rewrite, cross-event-loop fixes |
| `83ffa27d` | Add Telegram integration plugin |

---

## 5. Conflict Analysis

### 5.1 Conflicting Files (6 of 34)

| # | File | Severity | PMOVES Change | Upstream Change | Risk |
|---|---|---|---|---|---|
| 1 | `conf/model_providers.yaml` | 🔴 CRITICAL | +28 lines (TensorZero +10, MiniMax +18) | Complete YAML reorganization (schema, categories, data-driven search) | PMOVES additions use old schema — **won't parse** |
| 2 | `run_ui.py` | 🔴 CRITICAL | +44 lines (Prometheus /metrics + /healthz) | Complete WebSocket rewrite (WsHandler/WsManager), server restructuring, async/sync refactor | PMOVES code targets **deleted architecture** |
| 3 | `requirements.txt` | 🟠 HIGH | +3 lines (prometheus-client) | +telegram deps, security pins, file watchdog deps, removed broken extras | Mergeable with careful resolution |
| 4 | `docker/run/Dockerfile` | 🟠 HIGH | Non-root container, NATS auth, path containment, env var configurability | +unzip, self-update CLI trigger | USER directive + path changes vs package additions |
| 5 | `docker/run/fs/exe/run_A0.sh` | 🟡 MEDIUM | Re-enabled path containment, dropped root supervisord programs | System prototype update, code execution tool extraction to plugin | Script structure changes from plugin extraction may break containment |
| 6 | `docs/README.md` | 🟢 LOW | Integration patterns documentation | Install flow, plugin hub rename, a0-setup-cli skill, release notes | Text merge conflicts, easily resolvable |

### 5.2 Non-Conflicting Overlay Files (28 files — safe)

| Category | Files |
|---|---|
| **Documentation** | `CLAUDE.md`, `.coderabbit.yaml`, `.codex/README.md`, `docs/branching-strategy.md`, `PMOVES.AI_INTEGRATION.md` |
| **Docker/Infra** | `docker-compose.pmoves.yml`, `DockerfileLocal`, `docker/run/fs/etc/supervisor/conf.d/supervisord.conf` |
| **Environment** | `envared`, `env.shared`, `env.tier-agent.sh` |
| **GitHub CI** | `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/workflows/pmoves-audit.yml` |
| **Python Modules** | `pmoves_announcer/__init__.py`, `pmoves_common/__init__.py`, `pmoves_health/__init__.py`, `pmoves_registry/__init__.py` |
| **Python API/Helpers** | `python/api/image_get.py`, `python/api/persona_agent_create.py`, `python/helpers/persona_integration.py`, `python/helpers/settings.py` |
| **Scripts** | `scripts/bootstrap_credentials.ps1`, `scripts/bootstrap_credentials.sh` |
| **Tests** | `tests/test_persona_integration.py` |
| **Agent Profiles** | `agents/pmoves_custom/prompts/agent.system.main.md` |
| **Secrets** | `chit/secrets_manifest_v2.yaml` |

> These 28 files can be **cherry-picked cleanly** onto any new upstream base without conflict.

---

## 6. Sync Strategy Recommendations

### Option A: Fresh Overlay ⭐ RECOMMENDED

Create a clean branch from upstream v1.9 and re-apply PMOVES overlays.

| Step | Action | Effort | Risk |
|---|---|---|---|
| 1 | Create new branch from `upstream/v1.9` | 5 min | None |
| 2 | Cherry-pick 28 non-conflicting overlay files | 1–2 hrs | Low |
| 3 | Re-add TensorZero + MiniMax in new YAML schema | 2–3 hrs | Medium (schema learning curve) |
| 4 | Re-add Prometheus endpoints using WsHandler architecture | 3–4 hrs | Medium (architecture study required) |
| 5 | Re-add prometheus-client to requirements.txt | 15 min | Low |
| 6 | Re-apply Docker hardening (non-root, NATS) on new base | 1–2 hrs | Medium |
| 7 | Re-apply path containment on new run_A0.sh structure | 1 hr | Medium |
| 8 | Merge docs/README.md text changes | 30 min | Low |
| 9 | Validate all PMOVES integrations | 2–3 hrs | — |
| 10 | Absorb branch-tip commits (NIM, NATS docs) | 1–2 hrs | Low |
| | **Total** | **8–12 hrs** | **Low-Medium** |

**Advantages:**
- Clean git history — no messy merge commits
- Forces understanding of new upstream architecture
- No risk of subtle context loss from rebase
- Easy to review each overlay re-application
- Branch-tip commits absorbed after base is stable

**Disadvantages:**
- Requires studying new WebSocket architecture before Prometheus re-implementation
- Manual re-implementation of 6 overlays (not automated)

### Option B: Rebase with Manual Resolution

Rebase PMOVES.AI-Edition-Hardened onto upstream/v1.9 and resolve 6 conflicts.

| Step | Action | Effort | Risk |
|---|---|---|---|
| 1 | Rebase 24 overlay commits onto v1.9 | 1 hr | — |
| 2 | Resolve 6 merge conflicts | 4–6 hrs | High |
| 3 | Fix subtle breakage from context loss | 2–4 hrs | High |
| | **Total** | **6–10 hrs** | **High** |

**Advantages:**
- Preserves original commit history and attribution
- Slightly faster if no subtle issues found

**Disadvantages:**
- **High risk of subtle breakage** — rebase replays commits out of their original context
- `run_ui.py` Prometheus additions will almost certainly apply to wrong locations in rewritten file
- `model_providers.yaml` additions will land in wrong schema locations
- Hard to detect architectural mismatches until runtime
- Git blame becomes confusing with rebase artifacts

### Option C: Merge ⛔ NOT RECOMMENDED

Merge upstream/v1.9 into PMOVES.AI-Edition-Hardened.

**Reasons to reject:**
- Creates messy merge commit history
- Extremely difficult to review 604-commit merge
- Pollutes git blame across entire codebase
- Conflicts still require the same manual resolution as Option B
- No advantage over Option A or B

### Recommendation Summary

| Criterion | Option A (Fresh) | Option B (Rebase) | Option C (Merge) |
|---|---|---|---|
| Risk Level | Low-Medium | High | Very High |
| Effort | 8–12 hrs | 6–10 hrs | 8–12 hrs |
| History Quality | Clean (new branch) | Preserved (noisy) | Polluted |
| Reviewability | Excellent | Poor | Terrible |
| CVE Closure Speed | Fast (step 2) | Fast (step 2) | Fast (step 2) |
| **Verdict** | **✅ Recommended** | ⚠️ Acceptable fallback | ❌ Rejected |

---

## 7. Immediate Security Concerns

The 604-commit gap exposes the fork to **known vulnerabilities** that are patched upstream:

| CVE/Issue | Severity | Status | Upstream Fix |
|---|---|---|---|
| CVE-2026-4307 (path traversal in `download_work_dir_file`) | Critical | **OPEN on fork** | `0e3e8a15` |
| XSS via lxml-html-clean (CWE-79, CVSS 8.4) | High | **OPEN on fork** | `30835c2f` |
| 6 transitive dependency vulnerabilities | Medium | **OPEN on fork** | `dfe691d5` |

**Recommendation**: Regardless of sync strategy chosen, backport these 3 security commits immediately as a stopgap before the full sync.

---

## 8. Memory Staleness Advisory

| Stale Claim | Source | Actual Value | Action Required |
|---|---|---|---|
| "502 commits behind upstream v1.3" | Ladybug graph memory (score 0.33) | 604 commits vs v1.9 | Purge or update memory |
| "P1 Agent Zero fork sync — pin 2e000aa vs upstream v1.3+ (502 commits behind)" | Ladybug graph memory (score 0.33) | Same as above | Purge or update memory |
| "pinned 2e000aa Mar 7 vs upstream v1.3+, 502 commits" | Ladybug graph memory (score 0.25) | Same as above | Purge or update memory |

All three recalled memories reference the March 28 gap report data. They should be updated to reflect the current 604-commit / v1.9 figures, or forgotten if the audit report itself serves as the canonical reference going forward.

---

## 9. Post-Sync Validation Checklist

After completing the sync (Option A recommended):

- [ ] Fork boots successfully with new upstream base
- [ ] WebSocket connections establish (new WsHandler architecture)
- [ ] At least one LLM provider responds (Ollama or cloud)
- [ ] TensorZero provider works in new model_providers.yaml schema
- [ ] MiniMax provider works in new model_providers.yaml schema
- [ ] `/metrics` Prometheus endpoint responds with metrics
- [ ] `/healthz` health endpoint responds
- [ ] Non-root container execution verified (`USER` directive)
- [ ] NATS authentication works (when compose stack available)
- [ ] Path containment still active in run_A0.sh
- [ ] PMOVES custom agent profile loads correctly
- [ ] Persona creation API functional (Supabase integration)
- [ ] Credential bootstrap scripts execute
- [ ] CVE-2026-4307 no longer exploitable
- [ ] lxml-html-clean version >= 0.4.0
- [ ] All 28 non-conflicting overlay files present and intact
- [ ] Branch-tip commits (NIM provider, NATS docs) absorbed
- [ ] pmoves-audit.yml CI workflow passes

---

## 10. Appendix: Full File Inventory

### A. Conflicting Files (6)

```
conf/model_providers.yaml        — CRITICAL — PMOVES: +28 lines, Upstream: full reorg
run_ui.py                         — CRITICAL — PMOVES: +44 lines, Upstream: full rewrite
requirements.txt                  — HIGH    — PMOVES: +3 lines, Upstream: +several deps
docker/run/Dockerfile            — HIGH    — PMOVES: hardening, Upstream: +packages
docker/run/fs/exe/run_A0.sh      — MEDIUM  — PMOVES: containment, Upstream: plugin extraction
docs/README.md                    — LOW     — PMOVES: integration docs, Upstream: doc updates
```

### B. Non-Conflicting Files (28)

```
CLAUDE.md
.coderabbit.yaml
.codex/README.md
docker-compose.pmoves.yml
DockerfileLocal
docker/run/fs/etc/supervisor/conf.d/supervisord.conf
docs/branching-strategy.md
envared
env.shared
env.tier-agent.sh
.github/CODEOWNERS
.github/dependabot.yml
.github/workflows/pmoves-audit.yml
PMOVES.AI_INTEGRATION.md
pmoves_announcer/__init__.py
pmoves_common/__init__.py
pmoves_health/__init__.py
pmoves_registry/__init__.py
python/api/image_get.py
python/api/persona_agent_create.py
python/helpers/persona_integration.py
python/helpers/settings.py
scripts/bootstrap_credentials.ps1
scripts/bootstrap_credentials.sh
tests/test_persona_integration.py
agents/pmoves_custom/prompts/agent.system.main.md
chit/secrets_manifest_v2.yaml
```

---

*Report generated: 2026-04-25T00:08Z*
*Author: PMOVES Master Developer (Agent Zero)*
*Classification: Internal — P1 Remediation*
