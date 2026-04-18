# PMOVES.AI Security, Finance & Provenance Deep Research Report

> **Date:** 2026-04-17 | **Scope:** 10 research domains | **Methodology:** Source code analysis, TAC tree audit, cross-reference matrix

---

## Executive Summary

PMOVES.AI implements a multi-layered security, finance, and provenance architecture spanning CHIT HMAC signing, CGP geometry encoding, FlOO$ pipeline orchestration, E2B sandboxed execution, and a custom token economy. However, **the majority of security-critical submodules are uninitialized**, test coverage for cryptographic code is critically low (~5%), and the provenance model uses symmetric-key HMAC rather than industry-standard SLSA/GPG signing. The cipher-mcp component is a knowledge-graph memory bridge, not an encryption service as its name might suggest.

**Key Metrics:**

| Metric | Value |
|--------|-------|
| Submodules researched | 10 |
| Uninitialized (empty) | 2 (PMOVES-Wealth, ToKenism-Multi) |
| Initialized but pre-stage | 2 (E2B Danger-Room, E2B Danger-Room-Desktop) |
| In-tree (cloned) | 1 (pmoves-cipher-mcp) |
| GRAPHITI TAC trees analyzed | 7 (6 requested + pinokio-p7 bonus) |
| NATS subjects cataloged | 70+ |
| Open security alerts (E2B) | 154 (57 P1 + 16 P2 + 81 Dependabot) |
| Crypto test coverage | ~5% sign_trail, 0% chit_security, 0% validator |

---

## 1. PMOVES-Wealth — Wealth/Finance Management

### Submodule Status

| Property | Value |
|----------|-------|
| Path | `PMOVES-Wealth/` |
| Initialized | **No** — empty directory, no `.git` pointer |
| `.gitmodules` entry | Yes — `https://github.com/POWERFULMOVES/PMOVES-Wealth.git` |
| In-tree integration | None (directory is empty) |
| Docker references | None |
| NATS subjects | 0 direct (planned: `finance.*` subjects in agent-teams taxonomy) |
| TensorZero configs | None |

### Agent Team Placement

Per `agent-teams-taxonomy.tac.yaml`, **Wealth** is assigned to **Team 11: Life Integration** (2 agents: wealth, health). Node affinity: z890. Compute: CPU-only.

### Planned NATS Subjects (from TAC tree)

| Subject | Status | Purpose |
|---------|--------|---------|
| `finance.transactions.ingested.v1` | Planned | Transaction import events |
| `finance.budget.alert.v1` | Planned | Budget threshold alerts |
| `finance.monthly.summary.v1` | Planned | Monthly finance summary |
| `finance.transactions.synced.v1` | Active | n8n sync completion |

### Skill Pairing

Participates in **finance-sync** chain: `n8n-finance-sync` → `finance-monthly-cgp` (NATS: `skills.pipeline.finance-sync.v1`). Tokenism encodes monthly financial data as CGP packets.

### Assessment

Wealth management is entirely pre-stage. No code is available for review. The architecture envisions Firefly III integration with n8n workflow automation and CHIT CGP encoding of financial summaries, but none of this is implemented.

---

## 2. ToKenism-Multi — CHIT Contracts & Stablecoin Validation

### Submodule Status

| Property | Value |
|----------|-------|
| Path | `PMOVES-ToKenism-Multi/` |
| Initialized | **No** — empty directory, no `.git` pointer |
| `.gitmodules` entry | Yes — `https://github.com/POWERFULMOVES/PMOVES-ToKenism-Multi.git` |
| In-tree integration | Extensive references despite being empty |

### What Should Be There (from cross-references)

The submodule should contain:
- `integrations/contracts/chit/` — 9 TypeScript CHIT contract modules (CGP encoding/decoding/attribution)
- `integrations/projections/calibration-engine.ts` — Projection calibration
- Tokenism Simulator (port 8103, Docker service `tokenism-simulator`)
- Tokenism UI (Next.js frontend)
- CHIT Geometry Bus integration code
- NATS geometry bus publishers/subscribers

### In-Tree CHIT Code (pmoves/tools/chit/)

Since the submodule is empty, all CHIT decode logic lives in-tree:

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 3.5K | Package entry: `decode_cgp()`, `decode_images()` convenience functions |
| `chit_decoder.py` | 18.0K | Core CGP decoder: exact (lossless) + geometry-only (lossy/retrieval) modes. 11 functions. Uses numpy, pandas, faiss (optional), SentenceTransformers (optional) |
| `chit_decoder_mm.py` | 11.2K | Multi-modal decoder: images via CLIP, audio via CLAP (stub — NotImplementedError). 7 functions |
| `floos_resolver.py` | 33.4K | FlOO$ runtime engine: DAG-based skill dependency resolver with NATS hook publishing and MCP execution. 3 classes (SkillDAG, StepResult, PipelineResult), 20 functions |

### CHIT Decoder Architecture

```
CGP JSON Input
  ├── exact_decode() → lossless text/base64 extraction from CGP points
  ├── geometry_only_decode() → lossy retrieval via spectral histogram matching
  │     ├── empirical_spectrum() → bin projection values into histogram
  │     ├── faiss IndexFlatIP → cosine similarity search against corpus embeddings
  │     └── compute_metrics() → KL divergence, JS divergence, Wasserstein-1, coverage
  └── decode_images() → CLIP-based image constellation matching (Gaussian kernel selection)
```

### FlOO$ Pipeline Engine (floos_resolver.py)

FlOO$ is the orchestration layer connecting CHIT to the broader PMOVES ecosystem:

- **SkillDAG class**: Builds directed acyclic graph from `skill-pairings.yaml`, detects cycles, topological sort
- **NATS integration**: Publishes step completion/error events with PMOVES envelope format (id, topic, ts, version, source, payload, correlation_id). Default URL: `nats://nats:pmoves@nats:4222`
- **MCP execution**: Synchronous HTTP POST to localhost MCP endpoints for step execution
- **Health checking**: TCP port reachability + HTTP health endpoint validation
- **CLI**: 5 subcommands — `resolve`, `validate`, `status`, `hooks`, `run`
- **TensorZero reference**: Lists `tensorzero` as known container name for TCP health checks (no API calls)

### NATS Subjects in CHIT Code

| Subject | Direction | Context |
|---------|-----------|---------|
| `skills.pipeline.*.v1` | Publish | Pipeline completion events (from pairing config) |
| `skills.step.*.done.v1` | Publish | Step completion hooks |
| `geometry.packet.encoded.v1` | Publish | CGP packet encoded (from skills-taxonomy TAC) |
| `geometry.cgp.v1` | Pub/Sub | CGP transport subject |
| `tokenism.cgp.ready.v1` | Publish | CGP readiness signal |
| `tokenism.simulation.result.v1` | Publish | Simulation results |

### Gaps

- `load_cgp()` and `centers_from_minmax()` duplicated between chit_decoder.py and chit_decoder_mm.py — extract to shared `_utils.py`
- `decode_audio()` raises NotImplementedError — blocked on CLAP library
- FlOO$ has no direct import of CHIT decoders — invokes through MCP endpoints (planned integration)
- No Docker containerization of CHIT tools

---

## 3. GRAPHITI Protocol — TAC Tree Analysis

### TAC Tree Inventory

All 7 TAC trees found at `pmoves/configs/tac_trees/`:

| TAC Tree | Version | Focus | Status |
| `tokenism-chit.tac.yaml` | 1.0.0 | CHIT CGP encoding, NATS geometry bus, TypeScript module health | 4 phases, 8 checks |
| `training-pipeline.tac.yaml` | 1.0.0 | Unsloth + TensorZero fine-tuning (3 phases: Embed/Walk/Run) | 4 phases, 20+ tasks, all `planned` |
| `archon-agents.tac.yaml` | 1.0.0 | Archon Supabase prompts, Agent Zero MCP, TensorZero functions | 4 phases, 8 checks |
| `skills-taxonomy.tac.yaml` | 1.0.0 | 119 skills across 36 domains with NATS/pairing mapping | Audit: 118/118 mapped, 9 pairings |
| `p7-agents-skills-lifecycle.tac.yaml` | 1.0.0 | Agent registration, SKILL.md discovery, model assignment, VRAM budget | 7 phases, mixed done/planned |
| `agent-teams-taxonomy.tac.yaml` | 1.0.0 | 62 agents across 11 teams with NATS/compute/pairing cross-refs | 11 teams, 70+ NATS subjects |
| `pinokio-p7.tac.yaml` | — | P7 platform phases (not requested, discovered) | Not analyzed in depth |

### GRAPHITI in tokenism-chit TAC Tree

The tokenism-chit TAC defines 4 audit phases:

1. **Submodule & Modules** — Verify `PMOVES-ToKenism-Multi/package.json` exists (FAILS: submodule empty) and `integrations/contracts/chit/` directory exists (FAILS: submodule empty)
2. **NATS Geometry Bus** — Grep for `geometry.cgp` and `tokenism.simulation` subjects in submodule code (FAILS: submodule empty)
3. **Environment & Docker** — Check for `export` syntax in env files (Docker-incompatible), verify Docker Compose service definitions for `tokenism-simulator` and `tokenism-ui`
4. **Skill Pairing Integration** — Verify 3+ references in skill-pairings.yaml, check CGP schema version alignment (`chit.cgp.v1.0` canonical)

**Result:** Phases 1-2 cannot pass until submodule is cloned. Phase 3-4 can be partially verified against in-tree config.

### GRAPHITI in training-pipeline TAC Tree

Three-phase training pipeline with GRAPHITI annotations:

| Phase | Name | Model | VRAM | GRAPHITI Relevance |
|-------|------|-------|------|-------------------|
| 1 (Crawl) | Embedding fine-tuning | Qwen3-4b | ~16GB | Training data includes "CHIT/CGP packet examples (AGNOTE4482)" and “TAC tree definitions (29 trees)” |
| 2 (Walk) | Agentic model training | Qwen2.5-7B | ~20GB | Training data includes “Known Roads make targets” and “MCP tool invocation patterns” |
| 3 (Run) | Voice adaptation | Fish S2 Pro / F5-TTS | ~24GB | PMOVES vocabulary pronunciation (CHIT, CGP, Tokenism) |

**NATS subjects defined:** `training.job.started.v1`, `training.job.completed.v1`, `training.job.failed.v1`, `training.eval.result.v1`, `training.model.published.v1`, `training.model.deployed.v1`

**All tasks status: `planned`** — no training has been executed.

### GRAPHITI in archon-agents TAC Tree

Archon is the primary GRAPHITI trail consumer:
- `archon_work_orders` function in TensorZero for autonomous workflow execution
- `archon_code_review` function for PR review (used in pr-monitor-graphiti-chit pairing)
- Step 4 of pr-monitor-graphiti-chit chain: `graphiti-trail-sync` (agent: archon, NATS: `agent.graphiti.signed.v1`)

### GRAPHITI in skills-taxonomy TAC Tree

CHIT domain has 8 skills, 2 of which directly involve GRAPHITI:

| Skill | Command | GRAPHITI Role |
|-------|---------|---------------|
| `sign-trail` | `/chit:sign-trail` | Sign Graphiti trail entry with CHIT HMAC, publish `agent.graphiti.signed.v1` |
| `review-sweep` | `/chit:review-sweep` | Encode PR learnings as CGP packet for Graphiti, publish `ops.pr.learnings.encoded.v1` |

### GRAPHITI in p7-agents-skills-lifecycle TAC Tree

Agent onboarding step 7: "Sign Graphiti trail entry for attribution" — every new agent must produce a signed trail entry.

### GRAPHITI in agent-teams-taxonomy TAC Tree

- **Team Orchestration** owns `agent.graphiti.signed.v1` (BoTZ gateway publisher)
- **Team External** owns `agent.graphiti.signed.v1` (shared with orchestration)
- **pr-monitor-graphiti-chit** pairing: codex → claude-opus → tokenism → archon (4-step chain)

---

## 4. PMOVES-cipher-mcp — Cipher Memory Bridge

### Clarification: NOT an Encryption Service

Despite the name, `pmoves-cipher-mcp` does **not** implement encryption or signing. It is a **Cipher Memory knowledge-graph bridge** for Claude Code CLI integration via the Model Context Protocol (MCP). The actual encryption lives in `pmoves/tools/chit_security.py` (HMAC-SHA256, AES-GCM).

### Submodule Status

| Property | Value |
|----------|-------|
| Path | `pmoves-cipher-mcp/` |
| Initialized | **Yes** — full file tree present |
| In-tree duplicate | No — this IS the in-tree version |
| Docker references | None found |
| TensorZero configs | None |

### Architecture

```
main.py (entry point)
  ├── _health_loop() → pmoves_health.health_check() every 60s
  ├── _announce_once() → pmoves_announcer.announce_service() (NATS)
  └── mcp_main() → cipher_mcp.server (blocking, stdio transport)

cipher_mcp/
  ├── server.py    → MCP stdio server (pmoves-cipher, v0.1.0)
  ├── tools.py     → 4 MCP tool definitions + handlers
│   ├── pmoves_cipher_store          → Store memory with categories/tags
│   ├── pmoves_cipher_search         → Semantic search (Qdrant-backed)
│   ├── pmoves_cipher_store_reasoning → Store chain-of-thought traces
│   └── pmoves_cipher_reasoning_patterns → Search past reasoning patterns
  ├── client.py    → HTTP client for Cipher Memory Node.js service
  丨   ├── CipherClient → httpx async client, Bearer token auth (CIPHER_API_TOKEN)
  丨   └── MemoryItem  → dataclass: id, content, category, tags, embedding_id
  └── nats_events.py → Fire-and-forget NATS event publishing
```

### 5 Service Directories

| Service | File | Purpose |
|---------|------|---------|
| `pmoves_health/` | `__init__.py` | Health check function (returns status dict) |
| `pmoves_announcer/` | `__init__.py` | NATS service announcement (best-effort) |
| `pmoves_common/` | `__init__.py` | Shared utilities |
| `pmoves_registry/` | `__init__.py` | Service discovery (get_cipher_url, get_nats_url) |
| `cipher_mcp/` | 5 files | Core MCP server + tools + client + events |

### Memory Categories

| Category | Purpose |
|----------|---------|
| `code_pattern` | Reusable code patterns and conventions |
| `decision` | Architectural decisions and rationale |
| `context` | Project-specific context (default) |
| `submodule` | Submodule knowledge and configuration |
| `architecture` | System patterns and design |
| `reasoning` | Chain-of-thought reasoning traces |

### NATS Subjects

| Subject | Trigger | Payload |
|---------|---------|---------|
| `cipher.memory.stored.v1` | Memory stored | memory_id, category, tags, timestamp |
| `cipher.memory.searched.v1` | Memory searched | query, result_count, category, timestamp |
| `cipher.reasoning.stored.v1` | Reasoning stored | reasoning_id, question (truncated), timestamp |

### Auth Model

- **Cipher Memory service**: Bearer token via `CIPHER_API_TOKEN` env var
- **NATS**: Credentials from `pmoves_registry.get_nats_url()` or `NATS_URL` env var
- **No encryption in transit**: Plain HTTP to Cipher Memory service (assumed internal network)

### Skills Taxonomy Mapping

Cipher has 3 skills in the skills-taxonomy TAC: `/cipher:store` (mcp_tool: pmoves_cipher_store), `/cipher:search` (mcp_tool: pmoves_cipher_search), `/cipher:reasoning` (mcp_tools: store_reasoning + reasoning_patterns).

---

## 5. Provenance Signing — sign_trail.py

### Signing Algorithm: CHIT HMAC-SHA256

**NOT GPG. NOT SLSA. NOT GitHub provenance levels.**

The system implements a custom symmetric-key HMAC scheme:

```
build_payload() → sign_cgp(payload, passphrase)
  ├── Canonicalize JSON (sort_keys, compact separators)
  ├── Derive kid = SHA256(passphrase)[:16]
  ├── Compute HMAC-SHA256(passphrase, canonical_bytes)
  └── Attach sig: {alg: "HMAC-SHA256", kid: "...", hmac: "<base64>"}
```

### Crypto Stack (chit_security.py — 128 lines)

| Function | Algorithm | Purpose |
|----------|-----------|---------|
| `sign_cgp()` | HMAC-SHA256 | Sign CGP payload with passphrase |
| `verify_cgp()` | HMAC-SHA256 + compare_digest | Verify signature integrity |
| `encrypt_anchors()` | AES-256-GCM + PBKDF2 (600k iterations) | Encrypt embedding vector anchors |
| `decrypt_anchors()` | AES-256-GCM | Decrypt anchors for decode |

### GitHub Provenance Level Comparison

| Level | Implemented | Gap |
|-------|-------------|-----|
| GitHub commit signing (GPG) | No | No GPG keys, no `git commit -S` |
| SLSA Level 1 (attestation) | No | No provenance generation |
| SLSA Level 2 (hosted build) | No | No build provenance linking |
| SLSA Level 3 (non-falsifiable) | No | No hardening against build platform compromise |
| CHIT HMAC | Yes | Symmetric key only — weaker than any GPG level |

### Key Management

| Aspect | Implementation |
|--------|----------------|
| Key type | Symmetric passphrase (`CHIT_PASSPHRASE` env var) |
| Key derivation | None for HMAC; PBKDF2-SHA256 600k for AES-GCM |
| Key ID | `SHA256(passphrase)[:16]` |
| Key rotation | Not implemented |
| Key distribution | Out of scope — all verifiers share same passphrase |

### Alter System

Agents can have multiple visual identities (alters) for different operational modes. Example: `kilocode` → `kilocode-glm` alter (same glyph/color, different accent, bound to 5090 GPU node). Resolved by name, id, or display_name.

### Verification Chain

```
sign_trail.py (sign)
  → chit_security.verify_cgp() (crypto verify)
  → chit_security_validator.validate_cgp() (schema + signature + anchor decrypt + expiry + access control + audit)
  → NATS: agent.graphiti.signed.v1 (publish)
```

### Duplicate Code Risk

`pmoves/services/gateway/scripts/chit_sign.py` has its own `canon()` function that does NOT import from `chit_security.py`. Two independent canonical JSON implementations create drift risk.

---

## 6. Test Coverage — test_sign_trail.py

### Current State: 22 lines, 2 tests

| Test | Covers |
|------|--------|
| `test_resolve_alter_accepts_legacy_id_shape` | Alter lookup by `id` field |
| `test_build_payload_applies_kilocode_glm_alter` | Alter applied to payload |

### Coverage Gap Analysis

| Area | Tested | Severity |
|------|--------|----------|
| `sign_trail()` with passphrase (signed payload) | No | **P0** |
| `sign_trail()` without passphrase (unsigned path) | No | **P0** |
| `sign_cgp()` / `verify_cgp()` round-trip | No | **P0** |
| `verify_cgp()` with tampered payload | No | **P0** |
| `encrypt_anchors()` / `decrypt_anchors()` round-trip | No | **P0** |
| Schema validation | No | P1 |
| CLI arg parsing | No | P1 |
| `chit_security_validator.py` | No | **P0** (entire file untested) |

**Estimated coverage: ~5% of sign_trail.py, 0% of chit_security.py, 0% of chit_security_validator.py**

Test files per module: sign_trail.py has 1 test file (2 tests). chit_security.py has **0**. chit_security_validator.py has **0**.

---

## 7. Stablecoin & Token Code

### Food-USD Stablecoin (Project-Specific)

No USDC, USDT, DAI, or external stablecoin references exist. PMOVES uses project-specific stablecoins:

| Token | Type | Purpose |
|-------|------|---------|
| Food-USD | Stablecoin (USD-pegged) | Cooperative group purchase transactions |
| Energy-USD | Stablecoin (USD-pegged) | Energy transactions |
| Health-USD | Stablecoin (USD-pegged) | Health data transactions |
| Ride-USD | Stablecoin (USD-pegged) | Transportation transactions |
| E-USD | Stablecoin (USD-pegged) | General ecosystem token |
| U-Credits | Pegged to real-world goods | Utility credits |
| GroToken | ERC-20 governance token | DAO voting, rewards |

### Solidity Contracts (pmoves/contracts/solidity/contracts/)

| Contract | Standard | Purpose |
|----------|----------|---------|
| `FoodUSD.sol` | ERC-20 (OpenZeppelin 5.x) | Mintable/burnable stablecoin |
| `GroToken.sol` | ERC-20 (OpenZeppelin 5.x) | Governance + reward token, Ownable |
| `GroVault.sol` | IERC20 consumer | Staking vault with time-weighted rewards |
| `GroupPurchase.sol` | IERC20 consumer | Group purchase pooling (escrows FoodUSD) |
| `CoopGovernor.sol` | — | Quadratic voting DAO governance |

**Stack:** Solidity 0.8.24, OpenZeppelin 5.x, Hardhat tests. Prototype-grade — no audit, no multi-sig treasury, no mainnet config.

### Tokenomics Status

80+ references in CATACLYSM_STUDIOS_INC design documents (L1-L4 layers). **Zero Python backend code** implements token balance tracking, economy simulation, or contract interaction. Entirely design-phase.

---

## 8. PMOVES-DANGER-ROOM — Security Testing

### Submodule Status

| Submodule | Commit | Status |
|-----------|--------|--------|
| PMOVES-E2B-Danger-Room | `bc8eafe` | **Initialized**, validated clean |
| PMOVES-E2B-Danger-Room-Desktop | `a6b79c2` | **Initialized**, validated clean |
| PMOVES-Danger-infra | Terraform/Makefiles | Referenced, not at top level |

### Sandbox Security Model

- **Isolation:** Firecracker microVMs (kernel-level via KVM)
- **Network:** Namespaces prevent cross-sandbox communication
- **Resources:** cgroups — 2 CPU cores, 2GB RAM, 3600s max duration
- **Auth:** JWT Bearer (E2B_API_KEY), Service Role Keys, Desktop Auth Tokens
- **Data:** Ephemeral — no persistent storage, artifacts to MinIO

### Agent Team: Sandbox & Execution (8 agents)

`e2b_danger_room`, `e2b_desktop`, `e2b_spells`, `danger_infra`, `surf`, `agentgym`, `agentgym_rl`, `pmoves_e2b_mcp_server`

### Security Alert Backlog

| Repo | P1 | P2 | Dependabot | Total |
|------|-----|-----|------------|-------|
| PMOVES-E2B-Danger-Room | 28 | 6 | 39 | 73 |
| PMOVES-E2B-Danger-Room-Desktop | 18 | 3 | 21 | 42 |
| PMOVES-Danger-infra | 4 | 2 | 7 | 13 |
| pmoves-e2b-mcp-server | 7 | 5 | 14 | 26 |
| **Total** | **57** | **16** | **81** | **154** |

### danger_room_xmen_desktop.py

Demo script connecting NATS → Flute Gateway → Hyperdimensions CGP visualizer. Maps 5 PMOVES agents to X-Men personas. Publishes to `geometry.visualization.request.v1`. **No auth tokens** — acceptable for demo only.

### Docker Security

| Service | Dockerfile | Security Features |
|---------|-----------|-------------------|
| E2B MCP Server | `pmoves/docker/e2b-mcp-server/Dockerfile` | Non-root (UID 65532), multi-stage, healthcheck |
| E2B Surf | `pmoves/docker/e2b-surf/Dockerfile` | Non-root (UID 65532), multi-stage, healthcheck |

### NATS Gap

`pmoves/nats/config/external.conf` contains **zero E2B-specific subject definitions**. E2B subjects are documented in the integration guide but not codified in NATS config.

### Production Status

Both Danger-Room submodules at **P6 priority**, status `pending`, requiring S+C+R1 gates. No estimated completion.

---

## 9. SECURITY.md & CLAUDE.md — Policy Analysis

### SECURITY.md

**Status: Non-functional.** Default GitHub security policy template with:
- Generic version table (5.1.x, 5.0.x, 4.0.x) — not PMOVES versions
- Placeholder vulnerability reporting text
- **Zero references** to PMOVES security controls

Missing content: CHIT encryption handling, E2B sandbox boundaries, Tailscale ACL review, Firecracker security model, Dependabot/CodeQL triage SLAs, branch protection for hardened branches.

### CLAUDE.md

**Status: Pinokio leftover.** ~400-line Pinokio launcher development guide with Windows-specific paths (`D:\pinokio\prototype\`). No PMOVES security or operational guidance.

### Pre-Tool Hook Security Gate

Found in `.claude/hooks/pre-tool.sh` — blocks 11 dangerous patterns (`rm -rf /`, `DROP DATABASE`, `docker system prune -a`, etc.). Warns on writes to `/etc/` and overly permissive chmod. This is the only active security enforcement found in policy files.

---

## 10. Cross-Reference Matrix

### NATS Subjects by Domain

| Domain | Count | Key Subjects |
|--------|-------|-------------|
| Evolution & CHIT | 18 | `geometry.*`, `tokenism.*`, `mesh.gpu.*`, `model.*` |
| Automation | 8 | `ingest.*`, `health.*`, `finance.*` (subscriptions) |
| Life Integration | 8 | `health.*`, `finance.*` (mostly planned) |
| Orchestration | 7 | `supaserch.*`, `agent.*`, `botz.mcp.*` |
| Research | 7 | `research.*`, `cipher.*`, `ingest.file.*` |
| Media & Voice | 7 | `ingest.transcript.*`, `tokenism.geometry.*`, `voice.*` |
| Training | 6 | `training.job.*`, `training.eval.*`, `training.model.*` |
| External | 7 | `claude.code.*`, `ops.pr.*`, `agent.graphiti.*` |
| Infrastructure | 5 | `mesh.node.*`, `vpn.*` |
| UI | 5 | `remote.session.*`, `openclaw.*` |
| Data & Storage | 3 | `mesh.node.*`, `test.*`, `dev.*` (NATS owns the bus) |
| Sandbox | 3 | `agentgym.*` |
| Cipher MCP | 3 | `cipher.memory.*`, `cipher.reasoning.*` |

### TensorZero Integration Points

| Component | Function | Status |
|-----------|----------|--------|
| Archon work orders | `archon_work_orders` | Defined in tensorzero.toml |
| Archon code review | `archon_code_review` | Defined, used in pr-monitor pairing |
| Training pipeline | Model registration post-publish | Planned |
| FlOO$ resolver | TCP health check only | No API calls |
| E2B naming collision | `gemma_3n_e2b_edge` = "Effective 2B params", NOT sandbox | Confusing naming |

### Docker Integration

| Component | Dockerfile | Branch | Security |
|-----------|-----------|--------|----------|
| cipher-mcp | None (runs via `uv run`) | N/A | No containerization |
| CHIT tools | None | N/A | No containerization |
| E2B MCP Server | `pmoves/docker/e2b-mcp-server/` | Hardened | Non-root, multi-stage |
| E2B Surf | `pmoves/docker/e2b-surf/` | Hardened | Non-root, multi-stage |
| Tokenism Simulator | Inline in compose | Hardened | Resource-limited (heavy/aiml class) |

---

## Critical Findings

### P0 — Immediate Action Required

| # | Finding | Impact | Remediation |
|---|---------|--------|-------------|
| 1 | **Crypto test coverage ~5%** — 2 tests for 595+ lines of security code | Undetected bugs in HMAC signing, AES encryption, CGP validation could compromise integrity chain | Write P0 tests: sign/verify round-trip, tamper detection, encrypt/decrypt round-trip, validator schema checks |
| 2 | **SECURITY.md is non-functional** — default GitHub template | No security policy for contributors, auditors, or automated tools | Rewrite with PMOVES-specific controls: CHIT encryption, E2B boundaries, Tailscale ACLs, Dependabot SLAs |
| 3 | **Duplicate `canon()` function** — `chit_sign.py` vs `chit_security.py` | Signature incompatibility if either changes independently | Delete `chit_sign.py` copy, import from `chit_security._canon()` |
| 4 | **No key rotation mechanism** — single passphrase for all CHIT signing | Compromised passphrase = full integrity chain compromise | Implement key versioning, rotation protocol, multiple key support |

### P1 — High Priority

| # | Finding | Impact | Remediation |
|---|---------|--------|-------------|
| 5 | **PMOVES-Wealth submodule not cloned** | Cannot review financial management code | `git submodule update --init PMOVES-Wealth` |
| 6 | **PMOVES-ToKenism-Multi submodule not cloned** | Cannot audit TypeScript CHIT modules, Geometry Bus, Tokenism Simulator | `git submodule update --init PMOVES-ToKenism-Multi` |
| 7 | **154 open E2B security alerts** (57 P1) | Known vulnerabilities in sandbox infrastructure | Triage P1 alerts, patch critical CVEs, update Dependabot config |
| 8 | **NATS E2B subjects not in config** | Subjects documented but not enforced | Add E2B subjects to `pmoves/nats/config/external.conf` |
| 9 | **CLAUDE.md is Pinokio leftover** | Agents may follow wrong operational guidance | Replace with PMOVES-specific agent instructions or remove |
| 10 | **Audio decode is a stub** — NotImplementedError | Multi-modal CHIT pipeline incomplete | Implement CLAP integration or document as future work |

### P2 — Medium Priority

| # | Finding | Impact | Remediation |
|---|---------|--------|-------------|
| 11 | CHIT decoder utility duplication | Maintenance burden, drift risk | Extract shared functions to `_utils.py` |
| 12 | cipher-mcp has no Docker containerization | Inconsistent with other services | Add Dockerfile with non-root, multi-stage build |
| 13 | TensorZero E2B naming collision | Confusing cross-references | Rename models to avoid `e2b` prefix |
| 14 | Solidity contracts are prototype-grade | No audit, no mainnet config | Plan professional audit before pilot deployment |
| 15 | Training pipeline entirely `planned` | No fine-tuned models available | Execute Phase 1 (embedding fine-tuning) as first milestone |

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    PMOVES.AI Security Architecture              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PROVENANCE        FINANCE           SECURITY TESTING           │
│  ┌──────────┐     ┌──────────┐      ┌──────────────────┐        │
│  │sign_trail│     │FoodUSD   │      │E2B Danger-Room   │        │
│  │(HMAC-SHA)│     │GroToken  │      │(Firecracker µVM) │        │
│  └────┬─────┘     │GroVault  │      └────────┬─────────┘        │
│       │           │GroupPurch│               │                  │
│  ┌────▼─────┐     └────┬─────┘      ┌────────▼─────────┐        │
│  │chit_sec  │          │            │E2B Desktop       │        │
│  │(HMAC+AES)│          │            │(NoVNC GUI)       │        │
│  └────┬─────┘          │            └────────┬─────────┘        │
│       │           ┌────▼─────┐               │                  │
│  ┌────▼─────────┐ │n8n sync  │               │                  │
│  │chit_sec_val  │ │pipelines │               │                  │
│  │(validator)   │ └────┬─────┘               │                  │
│  └────┬─────────┘      │                     │                  │
│       │           ┌────▼─────┐               │                  │
│       │           │FlOO$    │               │                  │
│       │           │(DAG exec)│               │                  │
│       │           └────┬─────┘               │                  │
│       │                │                     │                  │
│  ┌────▼────────────────▼─────────────────────▼─────┐          │
│  │              NATS Message Bus                     │          │
│  │  70+ subjects across 12 domains                   │          │
│  │  agent.graphiti.signed.v1  (provenance)           │          │
│  │  cipher.memory.*.v1        (knowledge)            │          │
│  │  geometry.cgp.v1           (CHIT transport)       │          │
│  │  training.job.*.v1         (ML pipeline)          │          │
│  │  finance.*.v1              (wealth — planned)     │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                 │
│  KNOWLEDGE GRAPH         CHIT DECODE          LLM GATEWAY      │
│  ┌──────────┐          ┌──────────┐         ┌──────────┐       │
│  │cipher-mcp│          │chit_dec  │         │TensorZero│       │
│  │(MCP bridge│          │chit_dec_mm│        │(port 3030)│       │
│  │ → Neo4j) │          │floos_res │         │          │       │
│  └──────────┘          └──────────┘         └──────────┘       │
│                                                                 │
│  GRAPHITI TAC TREES: 7 trees, 119 skills, 62 agents, 11 teams  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Research Methodology

- **Source code analysis**: Direct file reads of all Python, YAML, JSON, Solidity, and Markdown files
- **TAC tree audit**: Full read of all 7 TAC trees with phase/status extraction
- **Submodule validation**: Directory listing, `.git` pointer check, `.gitmodules` cross-reference
- **NATS subject cataloging**: Grep across TAC trees, config files, and source code
- **Cross-reference matrix**: Docker, NATS, TensorZero references checked per component
- **Stablecoin scan**: Keyword search for USDC, USDT, DAI, stablecoin, ERC-20 across entire repo

---
*Report generated by Agent Zero Deep Research mode. All findings grounded in source code analysis.*
