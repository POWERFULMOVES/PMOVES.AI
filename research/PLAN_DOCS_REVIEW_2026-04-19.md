# Plan Documents Review — 2026-04-19

Review of 3 research/plan documents against actual repo state and recently merged PRs.

---

## Doc: FLEET_INFRASTRUCTURE_ENHANCEMENT_REPORT.md

### Accuracy Issues

| Line | Claim | Actual | Fix |
|------|-------|--------|-----|
| 50 | "6 docker-compose overlay files (base, core, agents, media, ui, workers — totaling 84 service definitions)" | 37 overlay files exist. 84 is only docker-compose.yml. Total across all overlays: 303 service definitions. | Rewrite: "37 docker-compose overlay files; docker-compose.yml alone defines 84 services, 303 total across all overlays" |
| 61 | "pmoves/docs/PMOVES.AIPLANS/ directory is empty" | Directory does not exist at all. | Rewrite: "pmoves/docs/PMOVES.AIPLANS/ does not exist — no infrastructure planning directory has been created" |
| 152 | `graphiti` listed as Data Plane service (KVM4-2) | **RETRACTED** — `pmoves/services/graphiti/` directory exists. Claim was incorrect. | No action needed — graphiti listing is valid |
| 153 | `graph-linker` listed as Data Plane service | **RETRACTED** — `pmoves/services/graph-linker/` directory exists. Claim was incorrect. | No action needed — graph-linker listing is valid |
| 245 | "pmoves-cipher-mcp/ directory contains 4 MCP servers" | Contains 5 subdirectories: cipher_mcp, pmoves_announcer, pmoves_common, pmoves_health, pmoves_registry. pmoves_common is a shared library, so 4 MCP servers + 1 shared lib. | Rewrite: "4 MCP servers (pmoves_health, pmoves_announcer, pmoves_registry, cipher_mcp) plus pmoves_common shared library" |
| 48 | "config.sh fails as root without RUNNER_ALLOW_RUNASROOT=1" | No config.sh found at deploy/runners/vps/ — only install.sh and install-hardened.sh exist. | Specify the actual file (install.sh) or remove the config.sh reference if it no longer exists |
| 593 | Appendix cites "pmoves/docs/PMOVES.AIPLANS/" as source | Directory does not exist. | Remove from appendix source table |

### Already Implemented

| Recommendation | Implemented By | Status |
|---------------|---------------|--------|
| P0-1: Convert VPS runners to systemd services | NOT implemented — deploy/runners/vps/ still has only install.sh and install-hardened.sh, no systemd unit files | Open |
| P0-2: Fix runner install.sh root bug | NOT verified — install.sh exists but root bug not confirmed fixed | Open |
| Sidecar env bootstrap (related to P0-3) | PR #1299 — created deploy/sidecar/sidecar-env.template with identical content to the report's Phase 5.3 sidecar.env | Partially done |
| SPARK TAC tree remediation (P1-4) | NOT implemented — dgx-spark.tac.yaml still contains full GPU-aspirational content (GB10 Grace-Blackwell, Ollama, NIM, NATS mesh) with no CPU-reality overlay | Open |
| PMOVES.AIPLANS creation (P3-3) | NOT implemented — directory still does not exist | Open |
| A2A server wiring | PR #1293 — A2A is referenced in docker-compose.yml agent-zero service definition, but no standalone a2a compose file or dedicated A2A service exists | Partially done |
| Fleet-audit-watcher as systemd | Services-catalog.md (line 57) documents it as a systemd service (`fleet-audit-watcher.service`), but no systemd unit file found in repo | Partially done (documented but not in repo) |

### Stale Content

| Section | Why Stale | Action |
|---------|-----------|--------|
| Line 50: "6 docker-compose overlay files" | 37 overlays now exist. This claim undermines credibility of the entire analysis. | Rewrite with accurate count |
| Line 61: "PMOVES.AIPLANS/ directory is empty" | Directory doesn't exist — "empty" implies it was created but has no content. | Correct to "does not exist" |
| Lines 152-153: graphiti/graph-linker in Data Plane | No service directories exist. These appear to be from PR #1294 planning artifacts. | Remove or mark aspirational |
| Lines 592-606: Appendix source references | PMOVES.AIPLANS reference is invalid. All other references verified correct. | Remove invalid entry |

### Clarity Issues

| Location | Issue | Suggested Fix |
|----------|-------|--------------|
| Line 48 | "config.sh fails as root" — no file path or context for which config.sh | Specify deploy/runners/vps/install.sh if that's the actual file, or remove if obsolete |
| Line 50 | "84 service definitions" ambiguous — is this all overlays or one file? | Specify "docker-compose.yml alone defines 84 services" |
| Section 3.1 tables | Services like `presign`, `render-webhook`, `node-registry`, `model-registry`, `channel-monitor`, `showtime-api` listed with no ports — are these real service directories? | Verify each exists in pmoves/services/ and add (none) or actual port |
| Line 515 | SPARK NATS hub recommendation says "Replaces z890 as NATS hub for VPS fleet" — but no mechanism described for dual-hub architecture or failover | Add detail on how dual-hub would work or note this as a future design question |
| Line 567 | P1-3 says "Deploy MCP registry on SPARK" with effort "Low" — but no MCP server deployment mechanism exists (no Dockerfile, no compose entry for pmoves_registry) | Note that MCP deployment tooling doesn't exist yet, raising actual effort |

### Priority Refinements

1. **Fix the compose overlay count** (line 50) — "6 overlays" vs actual 37 is the single most damaging inaccuracy. It makes the author appear to not have examined the actual codebase.
2. **Remove graphiti/graph-linker from Data Plane table** (lines 152-153) — These services don't exist. Including phantom services in a deployment plan will cause confusion.
3. **Correct PMOVES.AIPLANS from "empty" to "does not exist"** (line 61) — Substantively different situations requiring different remediation.
4. **Fix pmoves-cipher-mcp directory count** (line 245) — "4 MCP servers" is close but imprecise; there are 4 servers + 1 shared lib.
5. **Add a post-PR status header** — The report has no mechanism to track which recommendations have been addressed by subsequent PRs. Add a status column to the Implementation Priority Matrix (Section 8).

---

## Doc: SIDECAR_PROMOTION_PLAN.md

### Accuracy Issues

| Line | Claim | Actual | Fix |
|------|-------|--------|-----|
| 456 | agents.json uses `http://172.17.0.1:11434` for Ollama | The doc recommends `--add-host host.docker.internal:host-gateway` (line 665) but agents.json still uses 172.17.0.1. These are functionally equivalent but inconsistent. | Change agents.json custom_providers to use `http://host.docker.internal:11434` for consistency with the docker run command |
| 363 | `--without-glancer` flag in bootstrap command | Appendix C (line 809) only lists `--with-glancer`. No `--without-glancer` flag is documented. | Verify if this is a valid negation flag; if not, remove it |
| 30-32 | "agents.json: Empty {}", "secrets.env: Empty", "variables.env: Empty" | These files exist in .a0proj/ per project structure. agents.json may have content now (PR #1299 or subsequent changes). | Re-verify current state of these files |
| 171 | Compose agent-zero PORT=8080 | VERIFIED correct in docker-compose.agents.yml | No fix needed |
| 244-251 | Network subnets (pmoves_app 172.30.2.0/24, etc.) | VERIFIED correct in docker-compose.base.yml | No fix needed |
| 695 | `CHIT_PASSPHRASE=dev-local-sidecar-override` in sidecar.env | VERIFIED — matches PMOVES_AI_CONFIG.promptinclude.md and Agent Context Brief Appendix D | No fix needed |

### Already Implemented

| Recommendation | Implemented By | Status |
|---------------|---------------|--------|
| Phase 3: Minimal local dev env vars | PR #1299 — deploy/sidecar/sidecar-env.template contains identical content | Fully superseded |
| Phase 5.3: sidecar.env file content | PR #1299 — template is the canonical version | Fully superseded |
| Phase 5.1: Corrected docker run command | Partially — PR #1299 provides env template but not the full docker run command with hardening flags | Partially done |
| Phase 4: Skills configuration guidance | NOT implemented — no skills wiring changes in recent PRs | Open |
| Phase 2: agents.json profiles | NOT implemented — no agents.json content in PR #1299 | Open |

### Stale Content

| Section | Why Stale | Action |
|---------|-----------|--------|
| Lines 684-724: Phase 5.3 sidecar.env content | Superseded by deploy/sidecar/sidecar-env.template (PR #1299). The template is the canonical source. | Replace with reference: "See deploy/sidecar/sidecar-env.template — canonical sidecar env template (added PR #1299)" |
| Lines 515-586: Phase 3 env var documentation | Largely duplicated by the template. The template is more authoritative. | Condense to a pointer to the template plus explanation of key decisions (why JETSTREAM=false, why standalone) |
| Lines 646-667: Phase 5.1 docker run command | Still valuable as a reference but doesn't reference the template file. | Add `--env-file` reference pointing to deploy/sidecar/sidecar-env.template instead of inline path |

### Clarity Issues

| Location | Issue | Suggested Fix |
|----------|-------|--------------|
| Line 5 | "Do NOT modify any project files except this research document" | Contradicts the entire plan which instructs creating agents.json, env.shared, env.tier-agent, sidecar.env — all project files | Remove or rephrase as "This document is read-only analysis. Implementation steps reference separate operational procedures." |
| Line 436 | "Write to .a0proj/agents.json" | Ambiguous path — inside container this would be /a0/usr/projects/pmoves/.a0proj/agents.json | Specify full container path |
| Line 359 | "cd /home/powerfulmoves/agent-zero/PMOVES-Agent-Zero-SPARK" | Hardcoded absolute path that won't match other deployment targets | Use a variable like `$PMOVES_HOST_DIR` or note this is SPARK-specific |
| Line 449 | `custom_providers` in agents.json — only on Ollama profiles | Agent Zero's agents.json schema for custom_providers may not work per-profile; need to verify this is supported | Add a note that per-profile custom_providers depends on Agent Zero version support |
| Lines 593-603: PMOVES skills table | Lists skills (remotion-render, youtube-upload, etc.) as being at pmoves/skills/ but doesn't verify they exist | Verify pmoves/skills/ contents (4 dirs exist per file tree but names don't match) |

### Priority Refinements

1. **Replace inline sidecar.env with template reference** — PR #1299 made Phase 5.3 redundant. Keeping both creates a drift risk.
2. **Fix the "do not modify" contradiction** (line 5) — This is a logical error that could confuse anyone following the plan.
3. **Verify --without-glancer flag** (line 363) — If invalid, the bootstrap command will fail. Remove or replace with correct flag.
4. **Consistent Ollama URL** — Use host.docker.internal:11434 everywhere (agents.json, docker run, verification checks), not 172.17.0.1.
5. **Re-verify agents.json current state** — The plan was written assuming empty {}; if PR #1299 or manual changes added content, Phase 2 may need updating.

---

## Doc: AGENT_CONTEXT_CONSOLIDATED_BRIEF.md

### Accuracy Issues

| Line | Claim | Actual | Fix |
|------|-------|--------|-----|
| 336 | `docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` | Actual path: `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` (missing pmoves/ prefix) | Fix path in table |
| 337 | `docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` | Actual path: `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` (missing pmoves/ prefix) | Fix path in table |
| 371 | `docs/operations/MODEL_ONBOARDING.md` | Actual path: `pmoves/docs/operations/MODEL_ONBOARDING.md` (missing pmoves/ prefix) | Fix path in table |
| 365 | `pmoves/tests/test_port_audit.py` | PR #1295 moved this to `pmoves/tests/unit/test_port_audit.py`. File no longer exists at old path. | Fix path to pmoves/tests/unit/test_port_audit.py |
| 23 | "BoTZ MCP Gateway at 2091, 8054 (old/phantom)" | docker-compose.yml maps botz-gateway at port 8054:8054. Port 8054 is actively used, not phantom. The 2091 claim may come from services-catalog.md but contradicts the compose definition. | Investigate discrepancy: if compose uses 8054 and catalog says 2091, one is wrong. Do not label 8054 as "phantom" when compose actively maps it. |
| 18 | "TensorZero UI Dashboard at 4000, host-exposed at 3030" | Both TZ gateway (3000) and TZ UI (4000) claim host-exposed 3030 — cannot both be true. Verify actual host port mapping. | Verify which service actually gets host port 3030 in compose |
| 5 | "check services-catalog.md" | Ambiguous — no path given. Actual location: `.claude/context/services-catalog.md` | Add full path: "check `.claude/context/services-catalog.md`" |

### Already Implemented

| Recommendation | Implemented By | Status |
|---------------|---------------|--------|
| CHIT crypto migration P1: Gateway chit.py local canon() | PR #1294 (CHIT crypto P0-P3) — may have addressed this | Verify |
| CHIT crypto migration P2: geometry_decoder.py scrypt | PR #1294 — may have addressed | Verify |
| Test structure: test_port_audit in unit/ | PR #1295 — moved to pmoves/tests/unit/test_port_audit.py | Done (but brief not updated) |
| Sidecar env defaults (Appendix D) | PR #1299 — template matches brief's values | Consistent |

### Stale Content

| Section | Why Stale | Action |
|---------|-----------|--------|
| Lines 393-401 | "Model Onboarding" and "Cross-Node Context Gap" sections | DUPLICATED at lines 407-416. Exact copy-paste error. | Remove duplicate (lines 407-416) |
| Line 365 | test_port_audit.py path | Moved to unit/ by PR #1295 | Update path |
| Lines 336-337, 371 | Wrong file paths (missing pmoves/ prefix) | Paths have always been under pmoves/docs/ | Fix all three paths |
| Line 406 | "CI Audit (2026-04-19) — All 9 PRs merged this session" | Time-sensitive snapshot that will be meaningless within days | Either remove or convert to a dated changelog entry |

### Clarity Issues

| Location | Issue | Suggested Fix |
|----------|-------|--------------|
| Line 5 | "check services-catalog.md" without path | Provide full path: `.claude/context/services-catalog.md` |
| Line 381 | "pmoves-cipher-mcp/cipher_mcp/client.py" — no repo-root-relative path | Use full path: `pmoves-cipher-mcp/cipher_mcp/client.py` (this one is actually correct as-is, but the brief is inconsistent about path format) |
| Line 388 | "Gateway chit.py still has local canon()" — no file path | Specify which gateway and which chit.py file |
| Line 23 | BoTZ port contradiction | This is the most confusing entry in the entire port table. "2091" and "8054 (old/phantom)" need resolution — either services-catalog.md is wrong or compose is wrong. | Add a NOTE explaining the discrepancy and which source is authoritative |
| Line 381-383 | Cipher Memory MCP gap — 3 layers described but no issue tracker reference | Add GitHub issue number if one exists, or note it needs one |

### Priority Refinements

1. **Remove duplicate sections** (lines 407-416) — Copy-paste error that makes the brief look unreviewed.
2. **Fix 3 wrong file paths** (lines 336-337, 371) — Agents following these paths will hit missing files.
3. **Resolve BoTZ port contradiction** (line 23) — Either 2091 or 8054 is correct; labeling 8054 as "phantom" when compose actively uses it is dangerous.
4. **Update test_port_audit.py path** (line 365) — PR #1295 moved it; brief is now incorrect.
5. **Add repo-root prefix to services-catalog.md reference** (line 5) — Agents need the full path to find the file.

---

## Cross-Doc Contradictions

| Topic | Fleet Report | Sidecar Plan | Agent Context Brief | Resolution Needed |
|-------|-------------|-------------|-------------------|------------------|
| BoTZ Gateway port | Line 135: port 8054 (active) | Not mentioned | Line 23: 2091 active, 8054 "old/phantom" | YES — compose.yml maps 8054:8054. Brief's "phantom" label is wrong. |
| Compose overlay count | Line 50: "6 overlays" | Not mentioned | Not mentioned | Fleet report needs correction (37 actual) |
| Ollama URL in agents.json | Not mentioned | Line 456: 172.17.0.1:11434 | Not mentioned | Sidecar plan should use host.docker.internal consistently |
| graphiti service existence | Line 152: listed as Data Plane service | Not mentioned | Line 381: references cipher_mcp client calling graphiti-related endpoints | Fleet report should remove graphiti; no service exists |
| PMOVES.AIPLANS directory | Line 61: "empty" | Not mentioned | Not mentioned | Correct to "does not exist" |
| Sidecar file modification constraint | Not mentioned | Line 5: "do NOT modify any project files" | Not mentioned | Sidecar plan contradicts itself — fix or remove constraint |
| test_port_audit location | Not mentioned | Not mentioned | Line 365: pmoves/tests/test_port_audit.py | Update to pmoves/tests/unit/test_port_audit.py |

---

## Overall Assessment

**FLEET_INFRASTRUCTURE_ENHANCEMENT_REPORT.md** — High value-to-noise ratio for strategic planning (role assignments, memory budgets, VPS tier design are well-reasoned), but undermined by the "6 overlay files" claim which suggests shallow codebase examination. The service classification tables (Section 3.1) are the most useful content but contain phantom services. Fix the accuracy issues and this becomes a strong planning document.

**SIDECAR_PROMOTION_PLAN.md** — Good operational value as a step-by-step guide, but ~40% of its content (Phase 3 + Phase 5.3) is now superseded by PR #1299's template. The self-contradiction on file modification (line 5) and the unverified --without-glancer flag are process risks. Condense the superseded sections into a template reference and this becomes a clean runbook.

**AGENT_CONTEXT_CONSOLIDATED_BRIEF.md** — Highest value of the three as a quick-reference for agents. The port table, forbidden actions, and conventions are genuinely useful. However, the duplicate sections (lines 393-416), 3 wrong file paths, outdated test path, and the BoTZ port contradiction suggest it was not proofread before commit. These are easy fixes with high impact — this doc should be corrected first since agents read it before acting.
