# Research Batch Audit — May 2026

> **Generated:** 2026-05-15
> **Scope:** 66 files in `/a0/usr/projects/pmoves/research/`
> **Purpose:** Extract actionable items from research corpus, classify status, prioritize remaining work
> **Context:** Signoff 35/36 complete; PRs #1433, #1435, #1462, #1474, #1475, #1476 merged/approved

---

## Executive Summary

Of the 66 research files audited:

| Classification | Count | Description |
|---|---:|---|
| **ACTIONABLE NOW** | 14 | Has concrete tasks not yet completed |
| **IMPLEMENTED / DONE** | 8 | Findings were acted on via PRs or manual fixes |
| **REFERENCE ONLY** | 30 | Background knowledge, no action items |
| **STALE / SUPERSEDED** | 14 | Outdated or superseded by newer work |

**Critical remaining action items:** 2 operator token rotations (F-02, F-05), 1 P0 crypto consolidation (geometry_decoder.py), fleet infra deployment (5 P0-P1 items), and 8 doc fixes from ISSUE_AGNOTE4482.

---

## ACTIONABLE NOW — Full Detail

### A1. Supply Chain Token Rotation (F-02, F-05)

| Field | Value |
|---|---|
| **Source** | `SUPPLY_CHAIN_HARDENING_PLAN_2026-05-14.md`, `TANSTACK_SUPPLY_CHAIN_AUDIT_2026-05-14.md` |
| **Priority** | **P0 — CRITICAL** |
| **Effort** | 30 min (operator manual action) |
| **Dependencies** | Operator (DARKXSIDE) GitHub access |
| **Status** | 6/8 findings patched; F-02 and F-05 are operator-only |

**F-02: Rotate PERSONAL_ACCESS_TOKEN**
- Rotate `PERSONAL_ACCESS_TOKEN` in GitHub Secrets for PMOVES-crush
- Replace with fine-grained PAT scoped to crush repo only, or use `GITHUB_TOKEN`

**F-05: Rotate NPM Tokens**
- Rotate `NPM_TOKEN` and `POSTMAN_NPM_TOKEN` in GitHub Secrets
- Scope publish workflows to `release: published` trigger only

---

### A2. CHIT Crypto Consolidation — geometry_decoder.py

| Field | Value |
|---|---|
| **Source** | `part3_chit_integration_points.md`, `part2_chit_code_analysis.md`, `GRAPHITI_CIPHER_DEEP_RESEARCH_REPORT.md` |
| **Priority** | **P0 — CRITICAL** |
| **Effort** | 8-12 hrs |
| **Dependencies** | None (can proceed now) |
| **Status** | Open — 1,173-line duplicate crypto implementation still present |

**What to do:**
1. Refactor `pmoves/services/common/geometry_decoder.py` to import `sign_cgp`, `verify_cgp`, `encrypt_anchor`, `decrypt_anchor` from canonical `pmoves/tools/chit_security.py` instead of reimplementing them
2. Delete `chit_sign.py` or refactor to thin wrapper importing from `chit_security.py`
3. Consolidate 3 duplicate `canon()` functions into a single `pmoves/tools/chit_canon` module
4. Add fail-closed mode to `chit_security_validator.py` — raise exception (not silently skip) when `chit_security` is unavailable and `security_level >= SIGNED`
5. Write crypto unit tests for all canonical functions

---

### A3. CHIT Integration Gap — 3 Services REFUTED

| Field | Value |
|---|---|
| **Source** | `chit_integration_verification.md` |
| **Priority** | **P1** |
| **Effort** | 16-24 hrs (across 3 services) |
| **Dependencies** | A2 (crypto consolidation) should complete first |

**What to do:**
- Tokenism Simulator — zero `sign_cgp`/`verify_cgp` calls. Wire up canonical CHIT.
- Neo4j Mind Map — zero `sign_cgp`/`verify_cgp` calls. Wire up canonical CHIT.
- Agent Zero — zero `sign_cgp`/`verify_cgp` calls. Wire up canonical CHIT.
- Gateway — replace duplicate inline `verify_hmac()` with canonical import.
- Update hardening tracker to reflect actual integration status (1 VERIFIED, 1 PARTIAL, 3 REFUTED).

---

### A4. Fleet Infrastructure Deployment

| Field | Value |
|---|---|
| **Source** | `FLEET_INFRASTRUCTURE_ENHANCEMENT_REPORT.md` |
| **Priority** | **P0-P1** |
| **Effort** | 20-40 hrs total across all items |
| **Dependencies** | VPS node access, Tailscale connectivity |

| # | Action | Priority | Effort | Status |
|---|--------|----------|--------|--------|
| P0-1 | Convert VPS runners to systemd services | P0 | 2hr | Open |
| P0-2 | Fix runner install.sh root bug | P0 | 1hr | Open |
| P0-3 | Create per-node docker-compose overlays | P0 | 8hr | Open |
| P0-4 | Deploy KVM4-1 as API Gateway | P0 | 4hr | Open |
| P1-1 | Deploy KVM4-2 as Data Plane | P1 | 8hr | Open |
| P1-2 | Deploy KVM2 as Observability | P1 | 4hr | Open |
| P1-3 | Deploy MCP registry on SPARK | P1 | 2hr | Open |
| P1-4 | Remap SPARK TAC tree to actual role | P1 | 1hr | Partially addressed |

---

### A5. Doc Gaps from ISSUE_AGNOTE4482

| Field | Value |
|---|---|
| **Source** | `ISSUE_AGNOTE4482_DOC_GAPS.md` |
| **Priority** | **P1-P2** |
| **Effort** | 4-6 hrs |
| **Dependencies** | None |

**Files to update:**

- [ ] `research/LONGBOW_COMPARATIVE_ANALYSIS.md` — patch lines 18, 245 (stale signoff figures seeding CHIT intrusions)
- [ ] `pmoves/docs/PMOVESCHIT/LIVING_TEMPLATE_AGENT_TAXONOMY.md` — update hardcoded `K: 59` to 76 agents, regenerate CGP samples
- [ ] `pmoves/docs/AGENTS/IMPLEMENTATION_GAP_ANALYSIS.md` — add deprecation header (references dead branch `PMOVES.AI-Edition-Hardened`)
- [ ] `pmoves/docs/context/FLUTE_VISION_MULTIMODAL.md` — resolve/remove broken internal refs (`internal:PMOVESSHIFTEST`)
- [ ] `pmoves/docs/AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md` — update BoTZ refs (archived 2026-04-19)
- [ ] `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md` — refresh for MOF convergence
- [ ] `pmoves/docs/AGENTS/agent_vision_notes.md` — populate or delete 3-line stub
- [ ] New: `pmoves/docs/intelligence/SPARK_MODEL_STRATEGY.md` — model deployment strategy for DGX Spark

---

### A6. PMOVES.YT Service Fix

| Field | Value |
|---|---|
| **Source** | `MEDIA_VOICE_UX_SUBMODULES_REPORT.md` |
| **Priority** | **P0** |
| **Effort** | 4-6 hrs |
| **Dependencies** | git submodule update --init PMOVES.YT (needs SPARK or network-accessible host) |

**What to do:**
1. `git submodule update --init PMOVES.YT` — clone the submodule
2. Rewrite `main.py` — remove 22-line `exec()` shim, implement proper service entry point
3. Define YouTube API credentials in `secrets/`
4. Add NATS integration for pipeline events

---

### A7. Voice Pipeline Gaps

| Field | Value |
|---|---|
| **Source** | `MEDIA_VOICE_UX_SUBMODULES_REPORT.md` |
| **Priority** | **P1** |
| **Effort** | 8-12 hrs |
| **Dependencies** | JetStream enabled (compose stack) |

**What to do:**
1. Migrate voice relay to JetStream — change NATS connection from Core to JetStream for all voice subjects
2. Implement 7 missing NATS voice subjects (publishers in Flute/Whisper, subscribers in downstream)
3. Add TensorZero clients to Flute-Gateway, Voice-Relay, FFmpeg-Whisper
4. Dockerize Pinokio TTS Studio — move from Pinokio-managed to `pmoves/services/tts-studio/`

---

### A8. YouTube Signals — Model Integration Actions

| Field | Value |
|---|---|
| **Source** | `YOUTUBE_SIGNALS_ANALYSIS.md` |
| **Priority** | **P1-P2** |
| **Effort** | 6-8 hrs |
| **Dependencies** | DGX Spark Ollama access |

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Create model suit YAML profiles for GLM-5.1, Qwen3.6, Gemma4, Nemotron-3 | 2hr | Foundation |
| 2 | Configure Ollama on DGX Spark: NGL=999, num_batch=4096, ubatch=1024 | 30min | Performance |
| 3 | Pull Nemotron-3 Super via Ollama on Spark, validate KV cache fit | 1hr | NVIDIA-optimized |
| 4 | Test Gemma4 Dense Q4 on Spark | 30min | Throughput validation |
| 5 | Wire NVIDIA API endpoint as cloud fallback in Agent Zero | 30min | Cloud access |
| 6 | Evaluate NemoClaw as ClaWZ replacement on Spark | 2hr | Migration path |
| 7 | Draft PMOVES_MODEL_INTEGRATION_FRAMEWORK.md canonical reference | 2hr | Documentation |

---

### A9. Secrets Pipeline Post-CHIT Fixes — Residual Defaults

| Field | Value |
|---|---|
| **Source** | `SECRETS_PIPELINE_AUDIT_POST_CHIT_FIXES.md` |
| **Priority** | **P1-P2** |
| **Effort** | 4-6 hrs |
| **Dependencies** | None |

**What to do:**
1. Audit 6 files with potentially stale `changeme`/`minioadmin` defaults (brand_defaults.py, print_credentials.sh, backup-neo4j.sh, docker-compose.apps.yml, docker-compose.media.yml, docker-compose.yml)
2. Update CI workflows to include CHIT_SIGNING_KEY/CHIT_ENCRYPTION_KEY (sync-secrets-local.yml, ci.yml)
3. Update 30+ documentation files referencing old CHIT patterns

---

### A10. Supply Chain — Lane B & C Code Fixes

| Field | Value |
|---|---|
| **Source** | `SUPPLY_CHAIN_HARDENING_PLAN_2026-05-14.md` |
| **Priority** | **P1** |
| **Effort** | 2-3 hrs |
| **Dependencies** | PR merge by operator |

**What to do (fixes pushed to branches, pending PR merge):**
- F-03: `actions/cache@v3` → `@v4` in BoTZ integration-tests.yml (6 instances)
- F-04: `secrets: inherit` → explicit passing in tensorzero, supabase, Headscale workflows
- F-07: Pin MCP `@latest` deps to exact semver in `.claude/mcp.json`
- F-08: Add author association guard to `claude-code-review.yml`

---

### A11. GRAPHITI Pipeline — 0% Implemented

| Field | Value |
|---|---|
| **Source** | `part3_chit_integration_points.md`, `part1_tac_trees_analysis.md` |
| **Priority** | **P2** |
| **Effort** | 40-80 hrs (full pipeline)
| **Dependencies** | A2 (CHIT crypto consolidation) |

**What to do:**
- 4 GRAPHITI stages defined, only sign_trail.py (stage 4) has code
- Stages 1-3 are empty
- No production subscribers for any NATS subject
- Zero production `geometry.cgp.v1` consumers (only debug probe and SSE bridge)

---

### A12. Agents Docs Audit — 93 Files Needing Action

| Field | Value |
|---|---|
| **Source** | `AGENTS_DOCS_AUDIT_2026-04-19.md` |
| **Priority** | **P2** |
| **Effort** | 20-40 hrs |
| **Dependencies** | None |

**Breakdown:**
- 37 stale docs → archive or delete
- 26 stale stubs → populate or remove
- 18 needs-update → refresh to current stack
- 2 superseded → add deprecation headers
- 10 current → no action

---

### A13. GB10 LLM Inference — DGX Spark Configuration

| Field | Value |
|---|---|
| **Source** | `GB10_LLM_INFERENCE_RESEARCH_5SEARCH.md` |
| **Priority** | **P2** |
| **Effort** | 4 hrs |
| **Dependencies** | DGX Spark access |

**What to do:**
- Configure quantization strategy per model (Q8_0 for max quality, Q4_K_M for multi-model, F16 for fine-tuning)
- Set up Ollama with optimal parameters for GB10 Grace-Blackwell
- Validate 128GB HBM3e fits target model suite

---

### A14. Sidecar Promotion — DGX Spark Deployment

| Field | Value |
|---|---|
| **Source** | `SIDECAR_PROMOTION_PLAN.md` |
| **Priority** | **P2** |
| **Effort** | 4-8 hrs |
| **Dependencies** | DGX Spark physical access, Tailscale networking |

**What to do:**
1. Create `sidecar.env` on host with TOPOLOGY_MODE=standalone
2. Run `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults --service agent-zero`
3. Run `python3 -m pmoves.tools.mini_cli profile_detect` then `profile_apply`
4. Run `python3 -m pmoves.tools.mini_cli credentials_fetch`
5. Create data directories (memory, knowledge, instruments, logs, runtime)
6. Start container, validate CHIT connectivity

---

---

## IMPLEMENTED / DONE

| # | File | What Was Done | PR/Action |
|---|------|---------------|----------|
| D1 | `AGENT_ZERO_FORK_SYNC_LOG.md` | Fork synced from v1.9 (604 commits behind) to v1.14. All 34 PMOVES overlay files preserved. 3 CVEs closed. 7/7 validation checks passed. | Completed 2026-04-25 |
| D2 | `AGENT_ZERO_FORK_SYNC_AUDIT.md` | Audit triggered the sync execution. Fresh Overlay strategy (Option A) completed successfully. | Sync completed per D1 |
| D3 | `CHIT_GIT_FORENSICS_ROOT_CAUSE.md` | Root cause identified: `chit_sign.py` is an orphan, `chit_security.py` is canonical. Informs A2 consolidation task. | Analysis complete; deletion pending A2 |
| D4 | `MEILISEARCH_PIPELINE_DAMAGE_REPORT.md` | Pipeline funnel alignment verified. Circuit breaker principle extracted into `CIRCUIT_BREAKER_PRINCIPLE.promptinclude.md`. | Adopted as project principle |
| D5 | `TANSTACK_SUPPLY_CHAIN_AUDIT_2026-05-14.md` | 6/8 findings patched (F-01, F-03, F-04, F-06, F-07, F-08). F-02 and F-05 remain as operator actions. | 6/8 done; F-02/F-05 in A1 |
| D6 | `SUPPLY_CHAIN_HARDENING_PLAN_2026-05-14.md` | Lane A (F-01, F-06) and Lane B/C code fixes pushed to branches. F-06 CLA permissions reduced. | Pending PR merge (A10) |
| D7 | `AGENT_ZERO_V113_REVIEW.md` | Comprehensive v1.9→v1.13 delta documented. Informed fork sync strategy. Fork now at v1.14. | Superseded by successful sync |
| D8 | `CONCH_TRIAGE.md` | All tracked transcripts analyzed. T1/T2 batch completed. Progress checkboxes all marked done. | Completed |

---

## REFERENCE ONLY

These files contain background knowledge, API references, or analysis with no explicit action items.

### Group 3: YouTube / Media / Competitive

| # | File | Content | Notes |
|---|------|---------|-------|
| R1 | `CATALOG_STUDIOS_AI_PLAYLIST_ANALYSIS.md` | AI playlist curation analysis | 30-40% AI-relevant signal; informs BoTZ filtering requirements |
| R2 | `PLAYLIST_BATCH_ANALYSIS.md` | 500-video batch analysis | 28 videos with MOF relevance scored |
| R3 | `FRESH_VIDEO_ANALYSIS.md` | Angry Astronaut UFO tracking | No PMOVES action items |
| R4 | `DEEP_TRANSCRIPT_ANALYSIS.md` | Physics/biology research corpus analysis | 27 quotes, 36 mechanisms, 10 theses for MOF mapping |
| R5 | `ARCHON_COMPARATIVE_ANALYSIS.md` | Archon vs PMOVES architectural comparison | Archon is RAG knowledge system, not CHIT competitor |
| R6 | `ARCHON_ROADMAP_MAY2026_ANALYSIS.md` | Archon competitive intelligence | 40% silent failure rate is their vulnerability |
| R7 | `LONGBOW_COMPARATIVE_ANALYSIS.md` | PMOVES vs Longbow comparison | Complementary, not competitive. **Contains stale signoff data** — fix per A5 |
| R8 | `PMOVES-Creator_Deep_Research_Report.md` | Creator rendering engine analysis | 57 architectures, DGX Spark fit EXCELLENT |
| R9 | `CATACLYSM_STUDIOS_RESEARCH_REPORT.md` | Cataclysm Studios org knowledge base | 130+ files, trademark entity documentation |
| R10 | `MOF_META_AGENT_VIDEO_ANALYSIS.md` | Squeeze film levitation physics analogy | Foundational MOF physics mapping |

### Group 4: Telegram API Reference

| # | File | Content |
|---|------|---------|
| R11 | `telegram_bot_api_business_accounts_reference.md` | Business bot API complete reference |
| R12 | `telegram_bot_api_gifts_reference.md` | Gifts API methods and types |
| R13 | `telegram_bot_api_star_payments_xtr_reference.md` | XTR/Stars payment API reference |
| R14 | `telegram_bot_api_stories_business_verified_unified_reference.md` | Stories, verified bots unified reference |
| R15 | `telegram_bot_api_stories_complete.md` | Raw stories API extraction |
| R16 | `telegram_bot_api_stories_reference.md` | Stories exhaustive technical reference |
| R17 | `telegram_premium_research_2025_2026.md` | Premium subscription pricing and features |

### Group 5: Docs / Planning / Other

| # | File | Content |
|---|------|---------|
| R18 | `AGENT_CONTEXT_CONSOLIDATED_BRIEF.md` | Agent Zero context brief (standalone vs docked modes) |
| R19 | `A2UI_EVALUATION_REPORT.md` | A2UI framework evaluation for CHIT/GEOMETRY BUS visualization |
| R20 | `CORE_INFRA_SUBMODULES_REPORT.md` | 10 core infra submodules status (all uncloned) |
| R21 | `AI_ML_PIPELINE_SUBMODULES_REPORT.md` | 9 AI/ML submodules status (all uncloned) |
| R22 | `KVM_HOSTINGER_NETWORK_REPORT.md` | 3-node Hostinger VPS + Tailscale architecture documentation |
| R23 | `PLAN_DOCS_REVIEW_2026-04-19.md` | Plan docs quality review with specific recommendations per file |
| R24 | `part1_tac_trees_analysis.md` | GRAPHITI TAC trees structured analysis |

### Group 6: Science / Transcripts

| # | File | Content |
|---|------|---------|
| R25 | `analyses/T1_Datacenter_Acoustics_Deep_Analysis.md` | Acoustic wave mechanisms in datacenters |
| R26 | `analyses/T1_Hameroff_Deep_Analysis.md` | Microtubule fractal time crystal analysis (Floquet-driven, not self-sustaining) |
| R27 | `analyses/T1_Levin_Deep_Analysis.md` | Bioelectric collective intelligence (revised 8/10, 9 mechanisms mapped) |
| R28 | `analyses/T1_McQueen_Quantum_Critique_Deep_Analysis.md` | Quantum consciousness critique (Φ-as-structure insight) |
| R29 | `analyses/T1_Tuszynski_Deep_Analysis.md` | Acoustic waves on microtubules (structural failure ≠ conformational change) |
| R30 | `analyses/T2_Kauffman_Deep_Analysis.md` | Non-locality as fundamental (no space) |
| R31 | `analyses/T2_MIT_Deep_Analysis.md` | Multi-modal oscillation diagnosis (6/10 MOF relevance) |
| R32 | `analyses/T2_Palmer_Deep_Analysis.md` | Fractal universe QM (Palmer AGAINST non-locality, not for it) |
| R33 | `transcripts/T1_Hameroff_Fractal_Time_Crystals.md` | Full transcript (91KB) |
| R34 | `transcripts/T1_Levin_Bioelectric_Collective_Intelligence.md` | Full transcript (78KB) |
| R35 | `transcripts/T1_Tuszynski_Acoustic_Waves_Microtubules.md` | Full transcript (61KB) |
| R36 | `transcripts/T2_MIT_MultiModal_Oscillations.md` | Full transcript (35KB) |
| R37 | `transcripts/T2_Palmer_NonLocality_Fractal_Universe.md` | Full transcript (106KB) |

---

## STALE / SUPERSEDED

| # | File | Reason |
|---|------|--------|
| S1 | `CHIT_SECRETS_MANAGEMENT_AUDIT.md` | 29 findings from pre-fix era. P0s (encryption fraud, silent bypass, SSH key in env) were addressed by PR #1275. Audit is historical reference only. |
| S2 | `chit_integration_verification.md` | Verification snapshot from pre-fix era. Tracker claims corrected. Referenced by A3 for remaining gaps. |
| S3 | `SECURITY_FINANCE_PROVENANCE_REPORT.md` | Broad security audit. Most findings addressed by supply chain hardening and CHIT fixes. Superseded by TANSTACK audit. |
| S4 | `GRAPHITI_CIPHER_DEEP_RESEARCH_REPORT.md` | Found same bugs as CHIT_SECRETS_MANAGEMENT_AUDIT. Historical. Crypto consolidation tracked in A2. |
| S5 | `_tmp_graphiti_cipher.md` | Working draft, superseded by GRAPHITI_CIPHER_DEEP_RESEARCH_REPORT and part1-3 analysis series. |
| S6 | `part2_chit_code_analysis.md` | Code analysis that identified chit_sign.py/chit_security.py divergence. Informed A2 task. Analysis complete. |
| S7 | `actions-create-github-app-token-raw-research.md` | Raw research dump. Synthesized into topic3. |
| S8 | `topic1_slsa_provenance_github_apps.md` | SLSA provenance reference. No PMOVES-specific actions — background knowledge for future SLSA adoption. |
| S9 | `topic2_pat_rotation_automation.md` | PAT rotation research. Confirms GitHub has NO programmatic PAT creation API. Informs F-02 approach in A1. |
| S10 | `topic3_create_github_app_token.md` | Complete technical reference for actions/create-github-app-token. Used for supply chain fixes. |
| S11 | `topic4_github_pages_deployment_via_app.md` | GitHub Pages deployment via App tokens. No current PMOVES Pages deployment. |
| S12 | `topic5_self_hosted_runner_registration_app_tokens.md` | Self-hosted runner registration research. Informs fleet deployment but no immediate action. |
| S13 | `AGENTS_DOCS_AUDIT_2026-04-19.md` | Audit results captured in A12. Document itself is reference; actions extracted. |
| S14 | `ISSUE_AGNOTE4482_DOC_GAPS.md` | Gap analysis. Actions extracted into A5. Document serves as checklist. |

---

## Priority Summary — Top 10 Action Items

| Rank | Item | Priority | Effort | Source |
|------|------|----------|--------|--------|
| 1 | Rotate PAT + NPM tokens (F-02, F-05) | **P0** | 30min | A1 |
| 2 | Consolidate geometry_decoder.py crypto | **P0** | 8-12hr | A2 |
| 3 | Fix PMOVES.YT service (exec shim, credentials) | **P0** | 4-6hr | A6 |
| 4 | VPS runner systemd + root bug fix | **P0** | 3hr | A4 |
| 5 | Deploy KVM4-1 as API Gateway | **P0** | 4hr | A4 |
| 6 | Wire CHIT into 3 REFUTED services | **P1** | 16-24hr | A3 |
| 7 | Patch 8 doc files from AGNOTE4482 gaps | **P1** | 4-6hr | A5 |
| 8 | Configure Ollama + model suite on DGX Spark | **P1** | 4hr | A8 |
| 9 | Voice pipeline JetStream migration | **P1** | 8-12hr | A7 |
| 10 | Merge supply chain Lane B/C PRs (F-03, F-04, F-07, F-08) | **P1** | 2-3hr | A10 |

---

## Dependency Graph

```
A1 (token rotation) ──────────── no deps, operator-only
A2 (crypto consolidation) ────── no deps, blocks A3, A11
A3 (CHIT integration) ────────── blocked by A2
A4 (fleet infra) ─────────────── needs VPS access + Tailscale
A5 (doc fixes) ───────────────── no deps
A6 (PMOVES.YT) ──────────────── needs submodule clone (SPARK/host)
A7 (voice pipeline) ──────────── needs JetStream (compose stack)
A8 (model integration) ───────── needs DGX Spark Ollama access
A9 (secrets residuals) ───────── no deps
A10 (supply chain PRs) ────────── needs operator PR merge
A11 (GRAPHITI pipeline) ──────── blocked by A2, large effort
A12 (agents docs) ────────────── no deps, large effort
A13 (GB10 config) ────────────── needs DGX Spark access
A14 (sidecar promotion) ──────── needs DGX Spark physical access
```

---

## Unblocking Path

**Immediate (this session):**
1. Operator: Rotate PAT + NPM tokens (A1, 30 min)
2. Delegate: Start A2 crypto consolidation (blocks A3, A11)
3. Delegate: Start A5 doc fixes (no deps)

**This Week:**
4. Merge supply chain PRs (A10)
5. Clone PMOVES.YT and fix service (A6)
6. Begin fleet infra P0 items (A4)

**Next Sprint:**
7. CHIT integration for 3 services (A3)
8. Voice pipeline JetStream migration (A7)
9. Model suite configuration on Spark (A8, A13)

---

*End of Research Batch Audit. Generated by Agent Zero Deep Research, 2026-05-15.*
