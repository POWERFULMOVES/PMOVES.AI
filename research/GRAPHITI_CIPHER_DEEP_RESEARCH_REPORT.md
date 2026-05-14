# GRAPHITI TAC Trees, CHIT Crypto, Cipher MCP & ToKenism — Deep Research Report

**Date**: 2026-04-17
**Auditor**: Agent Zero Deep Research (GLM-5-Turbo)
**Scope**: Code-level analysis of GRAPHITI provenance, CHIT cryptographic implementation, Cipher MCP bridge, and ToKenism-Multi token contracts
**Classification**: Internal Security & Architecture Audit

---

## Executive Summary

This report delivers a code-level deep dive into four interconnected PMOVES.AI subsystems: GRAPHITI TAC tree orchestration, CHIT cryptographic signing/encryption, Cipher MCP knowledge-graph bridge, and ToKenism-Multi token contracts.

**Critical findings:**

1. **CHIT crypto has 2 CRITICAL bugs**: `chit_sign.py` (gateway) and `chit_security.py` (canonical) use incompatible KDFs (scrypt vs PBKDF2) and incompatible plaintext formats (JSON vs binary float32) for AES-GCM anchor encryption. Cross-module decryption is impossible — a silent interoperability failure.

2. **Zero crypto test coverage**: All 18 cryptographic code paths (sign, verify, encrypt, decrypt, tamper detection, key derivation) are untested. Only 22 lines of tests exist, covering non-crypto alter resolution.

3. **Cipher MCP is NOT encryption**: Despite the name, `pmoves-cipher-mcp` is a Claude Code CLI bridge to a Neo4j/pgvector knowledge-graph service. Zero cryptographic operations in the codebase.

4. **TAC tree GRAPHITI flows are mostly planned**: The pr-monitor-graphiti-chit pipeline (codex→claude-opus→tokenism→archon) is fully specified across 6 TAC trees with 88 NATS subjects, but only `sign_trail.py` has working code. The 4-step pipeline has no end-to-end implementation.

5. **ToKenism-Multi submodule is empty**: Cannot analyze the 9 TypeScript CHIT contract modules or 8 ERC-20 token implementations. Available evidence comes from a code review dated 2026-03-01.

6. **Submodule size claims are inaccurate**: `chit_decoder.py` is 522 lines (not 18K), `floos_resolver.py` is 1,011 lines (not 33K). The `chit_sign.py` file exists at `pmoves/services/gateway/scripts/chit_sign.py` (77 lines), not in `pmoves/tools/chit/`.

---

## Table of Contents

1. [Part 1: GRAPHITI TAC Trees Deep Dive](#part-1-graphiti-tac-trees-deep-dive)
2. [Part 2: CHIT Implementation Deep Dive](#part-2-chit-implementation-deep-dive)
3. [Part 3: Cipher MCP Deep Dive](#part-3-cipher-mcp-deep-dive)
4. [Part 4: ToKenism-Multi Deep Dive](#part-4-tokenism-multi-deep-dive)
5. [Part 5: Cross-Reference Analysis](#part-5-cross-reference-analysis)
6. [Consolidated Findings](#consolidated-findings)
7. [Recommendations](#recommendations)

---

## Part 1: GRAPHITI TAC Trees Deep Dive

### 1.1 Scope & Methodology

Read all 6 GRAPHITI-referencing TAC trees (3,081 total lines). No dedicated `pr-monitor-graphiti-chit.tac.yaml` file exists — this pipeline is distributed across 4 trees.

**Files analyzed:**
- `tokenism-chit.tac.yaml` — CHIT encoding, FlOO$ pipeline, attribution
- `training-pipeline.tac.yaml` — Agent training lifecycle (entirely `planned`)
- `archon-agents.tac.yaml` — Archon orchestration, Graphiti trail signing
- `skills-taxonomy.tac.yaml` — Skill definitions including CHIT/GRAPHITI skills
- `p7-agents-skills-lifecycle.tac.yaml` — Skill lifecycle management
- `agent-teams-taxonomy.tac.yaml` — Team structure, pr-monitor-graphiti-chit pipeline

### 1.2 pr-monitor-graphiti-chit Pipeline (End-to-End)

The GRAPHITI trail is the final step in a 4-stage PR review pipeline traced across 4 TAC trees:

```
Stage 1: codex [/pr-monitor]
  → NATS: ops.pr.monitor.completed.v1
  → Output: pr_monitor_report

Stage 2: claude-opus [/pr-trim]
  → NATS: ops.pr.trim.completed.v1
  → Output: trimmed_pr_report

Stage 3: tokenism [/chit:review-sweep]
  → NATS: ops.pr.learnings.encoded.v1
  → Output: pr_learnings_packet (CHIT CGP)

Stage 4: archon [/chit:sign-trail]
  → NATS: agent.graphiti.signed.v1
  → Output: graphiti_handoff (signed Graphiti payload)
```

**Implementation status**: Stage 4 (`sign_trail.py`) has working code. Stages 1-3 have TAC tree definitions but no corresponding implementation files were found in the codebase.

### 1.3 NATS Subject Catalog (88 Unique Subjects)

Full per-tree extraction with all 88 subjects, 14 CHIT/GRAPHITI skills, agent responsibility matrix, and phase definitions is available in `research/part1_tac_trees_analysis.md` (874 lines).

Key GRAPHITI-related subjects:

| Subject | Direction | Owner |
|---------|-----------|-------|
| `agent.graphiti.signed.v1` | Publish | archon |
| `ops.pr.monitor.completed.v1` | Publish | codex |
| `ops.pr.trim.completed.v1` | Publish | claude-opus |
| `ops.pr.learnings.encoded.v1` | Publish | tokenism |
| `ops.pr.monitor.failed.v1` | Publish | codex |
| `tokenism.attribution.recorded.v1` | Publish | tokenism |
| `tokenism.cgp.ready.v1` | Publish | tokenism |
| `cipher.memory.stored.v1` | Publish | cipher-mcp |
| `cipher.memory.searched.v1` | Publish | cipher-mcp |
| `cipher.reasoning.stored.v1` | Publish | cipher-mcp |

### 1.4 Key TAC Tree Statistics

| Metric | Value |
|--------|-------|
| Total GRAPHITI-referencing TAC trees | 6 (no dedicated pr-monitor-graphiti-chit file) |
| Unique NATS subjects | 88 |
| GRAPHITI-direct subjects | 1 (`agent.graphiti.signed.v1`) |
| CHIT/GRAPHITI skills | 14 across 4 domains |
| Agents with GRAPHITI responsibilities | 8 (codex, claude-opus, tokenism, archon, crush, cline, kilocode, powerfulmoves) |
| Teams owning GRAPHITI flow | Evolution & CHIT (18 subjects), Orchestration (12 subjects) |
| GRAPHITI_MARK comments | 0 (none found in any TAC tree) |
| Training pipeline status | 100% `planned` |

### 1.5 CGP Schema Version Drift

Three incompatible CGP version identifiers in use:

| Version | Used By | Context |
|---------|---------|--------|
| `geometry.cgp.v1` | Hi-RAG, Gateway CHIT API | Transport layer |
| `chit.cgp.v0.2` | TypeScript CGP generator, Consciousness Service | Payload layer |
| `chit.cgp.v1.0` | chit_security_validator.py | Canonical validation |

No version negotiation or migration path exists between these identifiers.

---

## Part 2: CHIT Implementation Deep Dive

### 2.1 Scope & Corrections

**IMPORTANT**: The original task specification contained inaccurate file sizes. Actual measurements:

| File | Claimed Size | Actual Size | Location |
|------|-------------|-------------|----------|
| `chit_decoder.py` | 18K lines | **522 lines** | `pmoves/tools/chit/chit_decoder.py` |
| `floos_resolver.py` | 33K lines | **1,011 lines** | `pmoves/tools/chit/floos_resolver.py` |
| `chit_sign.py` | Listed as existing | **77 lines** | `pmoves/services/gateway/scripts/chit_sign.py` (NOT in `pmoves/tools/chit/`) |
| `chit_security.py` | 128 lines | **128 lines** | `pmoves/tools/chit_security.py` (NOT in `pmoves/tools/chit/`) |
| `chit_security_validator.py` | ~200 lines | **589 lines** | `pmoves/tools/chit_security_validator.py` (NOT in `pmoves/tools/chit/`) |

17 files read (5,237 total lines). 4 files contain cryptographic operations.

Full code-level analysis available in `research/part2_chit_code_analysis.md` (550 lines).

### 2.2 HMAC Algorithm — Exact Implementation

All implementations use **HMAC-SHA256**:

```python
# chit_security.py:30 (canonical)
mac = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()

# chit_sign.py:21 (gateway duplicate)
mac = hmac.new(passphrase.encode("utf-8"), canon(d), hashlib.sha256).digest()

# generate-enrollment.py:97 (fleet duplicate)
mac = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
```

**No SHA512 usage** anywhere in the CHIT stack.

### 2.3 CHIT_PASSPHRASE Usage — RAW, Not Pre-Hashed

The passphrase is used **directly as HMAC key** with UTF-8 encoding in all three files:

```python
passphrase.encode("utf-8")  # Raw bytes, no hashing, no stretching
```

The `kid` field hashes the passphrase for identification only:
```python
kid = hashlib.sha256(passphrase.encode()).hexdigest()[:16]  # Label only, NOT used as key
```

**Implications:**
- Short passphrases (e.g., 8 chars) = weak HMAC key
- No PBKDF2/scrypt stretching before HMAC usage
- Valid per RFC 2104 but below modern security standards

### 2.4 CRITICAL: AES-GCM Key Derivation Incompatibility

| Parameter | chit_security.py (canonical) | chit_sign.py (gateway) |
|-----------|------------------------------|------------------------|
| KDF | **PBKDF2-HMAC-SHA256** | **scrypt** |
| Iterations/Cost | 600,000 | N=16384, r=8, p=1 |
| Salt | `os.urandom(16)` | `os.urandom(16)` |
| Key length | 32 bytes | 32 bytes |
| Plaintext format | **Binary float32** (numpy) | **JSON string** |
| Envelope format | Includes `"alg": "AES-GCM"` | **Missing `"alg"` field** |

**Impact**: A CGP with anchors encrypted by `chit_sign.py` **cannot be decrypted** by `chit_security.decrypt_anchors()`. Even if KDFs were aligned, the plaintext formats are incompatible (JSON array vs 4-byte-length-prefixed float32 binary). This is a silent interoperability failure — no error is raised until decryption is attempted.

### 2.5 CRITICAL: Duplicate canon() Function — Three Copies

| Location | Function | Line |
|----------|----------|------|
| `pmoves/tools/chit_security.py` | `_canon` | 20 |
| `pmoves/services/gateway/scripts/chit_sign.py` | `canon` | 15 |
| `pmoves/scripts/fleet/generate-enrollment.py` | `_canon` | 86 |

All three are logically identical but **independently copy-pasted** — no shared import. If any is modified, signatures produced by one module will fail verification by another.

### 2.6 Signature Format

**Canonical (chit_security.py):**
```json
{"alg": "HMAC-SHA256", "kid": "<sha256(passphrase)[:16]>", "hmac": "<base64>"}
```

**Gateway (chit_sign.py):**
```json
{"alg": "HMAC-SHA256", "kid": "demo", "ts": 1700000000, "hmac": "<base64>"}
```

Differences: gateway hardcodes `kid` as `"demo"` (not derived from passphrase) and adds an unverified `ts` timestamp field.

### 2.7 Verification Chain — Full Trace

```
sign_trail.sign_trail()                    [sign_trail.py:149]
  ├── build_payload()                      [sign_trail.py:95]
  ├── _validate_schema()                   [sign_trail.py:80]  — ADVISORY ONLY
  └── sign_cgp(payload, passphrase)        [chit_security.py:24]
        ├── kid = sha256(passphrase)[:16]
        ├── doc_nosig.pop("sig", None)
        ├── hmac.new(passphrase, _canon(doc_nosig), sha256)
        └── doc["sig"] = {alg, kid, hmac}

chit_security_validator.validate_cgp()     [chit_security_validator.py:476]
  └── CGPValidator.validate()              [chit_security_validator.py:256]
        ├── AccessControl.is_source_allowed()     — hardcoded trust list
        ├── CGPDocument(**cgp)                     — Pydantic validation
        ├── CGPVersion(doc.spec)                    — v0.1, v0.2, v1.0
        ├── _is_signature_expired()                 — 24h on created_at (WRONG timestamp)
        ├── verify_cgp(cgp, self.passphrase)        [chit_security.py:35]
        │     ├── hmac.compare_digest(expected, actual)  — constant-time
        │     └── Returns False on mismatch
        └── (optional) decrypt_anchors()            [chit_security.py:95]
```

### 2.8 Security: Silent Fallback

```python
# chit_security_validator.py:43-48
try:
    from pmoves.tools.chit_security import verify_cgp, decrypt_anchors
    CHIT_SECURITY_AVAILABLE = True
except ImportError:
    CHIT_SECURITY_AVAILABLE = False
    logging.warning("chit_security.py not available - signature verification disabled")
```

If import fails, signature verification is **silently skipped** — returns `True`. No fail-closed mode exists.

### 2.9 FlOO$ DAG (floos_resolver.py — 1,011 Lines)

The FlOO$ resolver is a **pure pipeline orchestration engine** with NO cryptographic operations:
- `SkillDAG` class: Builds DAG from `skill-pairings.yaml`
- Cycle detection: DFS three-color marking
- Topological sort: Kahn algorithm
- NATS hook publishing: **Unauthenticated** JSON envelopes (no HMAC, no auth token)
- MCP execution: Restricted to `localhost`/`127.0.0.1`/`::1` only (good security boundary)

### 2.10 Test Coverage

**22 lines total, 2 tests, 0 crypto coverage:**

| Path | Status |
|------|--------|
| HMAC sign/verify roundtrip | UNTESTED |
| Tamper detection | UNTESTED |
| AES-GCM encrypt/decrypt roundtrip | UNTESTED |
| Wrong passphrase rejection | UNTESTED |
| Key derivation | UNTESTED |
| Float pack/unpack | UNTESTED |
| Validator schema check | UNTESTED |
| Signature expiry | UNTESTED |
| Access control | UNTESTED |

**Estimated coverage: ~2% of crypto-related code paths.**

### 2.11 Finding Summary

| ID | Severity | Finding | File(s) |
|----|----------|---------|--------|
| F1 | CRITICAL | AES-GCM KDF mismatch: scrypt vs PBKDF2 | chit_security.py, chit_sign.py |
| F2 | CRITICAL | AES-GCM plaintext mismatch: JSON vs binary float32 | chit_security.py, chit_sign.py |
| F3 | HIGH | 3 duplicate canon() functions, no shared import | chit_security.py, chit_sign.py, generate-enrollment.py |
| F4 | HIGH | Silent fallback disables signature verification | chit_security_validator.py:43-48 |
| F5 | HIGH | Zero test coverage for all crypto paths | test_sign_trail.py |
| F6 | MEDIUM | Signature expiry checked against CGP created_at, not sig timestamp | chit_security_validator.py:389-401 |
| F7 | MEDIUM | NATS hook payloads have no authentication | floos_resolver.py:254-301 |
| F8 | MEDIUM | Secrets stored as cleartext or base16 hex | pmoves/chit/__init__.py:79-88 |
| F9 | LOW | No IV reuse detection for AES-GCM | chit_security.py:81, chit_sign.py:40 |
| F10 | LOW | Hardcoded trusted source list | chit_security_validator.py:172-179 |

---

## Part 3: Cipher MCP Deep Dive

### 3.1 Architecture

```
Claude Code CLI ──stdio/MCP──► pmoves-cipher-mcp (Python) ──HTTP──► cipher-api (Node.js/Neo4j) @ :8105
```

**CRITICAL FINDING**: `pmoves-cipher-mcp` contains **ZERO cryptography**. No encrypt, decrypt, sign, hmac, sha, aes, or rsa references in any file. The name "Cipher" is metaphorical — it is a knowledge-graph memory service.

### 3.2 In-Tree Code (NOT a Submodule)

`pmoves-cipher-mcp/` is tracked as a regular directory (tree object in git index), NOT a git submodule. 13 files total:

| File | Lines | Role |
|------|-------|------|
| `cipher_mcp/server.py` | 87 | MCP stdio server (Claude Code integration) |
| `cipher_mcp/client.py` | 197 | HTTP client to cipher-api |
| `cipher_mcp/tools.py` | 280 | 4 MCP tool definitions + handlers |
| `cipher_mcp/nats_events.py` | 73 | Fire-and-forget NATS event publisher |
| `cipher_mcp/__init__.py` | 25 | Package metadata |
| `pmoves_registry/__init__.py` | — | Service URL resolution |
| `pmoves_announcer/__init__.py` | — | NATS publishing pattern |
| `pmoves_health/__init__.py` | — | Health check pattern |
| `pyproject.toml` | — | Dependencies: mcp, httpx, nats-py |

### 3.3 The 4 MCP Tools

| Tool Name | Function | NATS Event |
|-----------|----------|------------|
| `pmoves_cipher_store` | Store knowledge with category/tags | `cipher.memory.stored.v1` |
| `pmoves_cipher_search` | Semantic search via pgvector | `cipher.memory.searched.v1` |
| `pmoves_cipher_store_reasoning` | Store Q+reasoning+result traces | `cipher.reasoning.stored.v1` |
| `pmoves_cipher_reasoning_patterns` | Search past reasoning traces | **NONE** (missing) |

**Bug**: `pmoves_cipher_reasoning_patterns` does not emit a NATS event unlike the other 3 tools.

### 3.4 Auth Implementation

```python
# client.py:41-44
self._token = os.getenv("CIPHER_API_TOKEN", "")

def _get_headers(self) -> dict:
    if self._token:
        return {"Authorization": f"Bearer {self._token}"}
    return {}
```

Simple Bearer token from `CIPHER_API_TOKEN` env var. If unset, requests proceed **without authentication**. No token validation, no expiry, no rotation.

### 3.5 NATS Integration

3 subjects defined in `nats_events.py`:

| Subject | Trigger |
|---------|---------|
| `cipher.memory.stored.v1` | Memory stored successfully |
| `cipher.memory.searched.v1` | Search completed |
| `cipher.reasoning.stored.v1` | Reasoning trace stored |

All are fire-and-forget (connect, publish, flush, close). Failures log to stderr but never raise exceptions.

### 3.6 Backend: @byterover/cipher (npm)

The actual cipher-api service is the npm package `@byterover/cipher` running in Node.js:

```dockerfile
FROM node:20-alpine
RUN npm i -g @byterover/cipher
CMD ["sh", "-lc", "cipher --mode mcp --transport http --port 8765"]
```

**Two separate cipher services exist** (from audit 2026-02-19):
- `cipher-api` (:8105) — Node.js/Neo4j, the canonical PMOVES cipher memory
- `pmoves-botz-cipher` (:8000) — Referenced in docker-compose but **undefined** (dangling reference)

### 3.7 Storage Backend

Pgvector-backed with Qwen3-Embedding-4B (Ollama, HuggingFace, nomic fallback chain):

```sql
-- Core tables: sessions, messages, memory, embeddings, event_log
-- Embeddings: VECTOR(1536) with ivfflat index (lists=200)
-- Search: pmoves_core.embed_search_l2(query_vec, k, probes)
-- Upsert: pmoves_core.upsert_embedding(object_type, object_id, content, embedding)
```

No Meilisearch integration by default. No Qdrant integration despite `QDRANT_URL` env var.

### 3.8 Known Issues (from 2026-02-19 Audit)

| ID | Severity | Issue |
|----|----------|-------|
| P1 | HIGH | `pmoves-botz-cipher:8000` dangling reference in gateway-agent env |
| P2 | MEDIUM | `pmoves-cipher-mcp/` not a submodule (cannot be independently versioned) |
| P3 | LOW | Missing `.gitignore` (`.venv/` and `__pycache__/` potentially tracked) |

---

## Part 4: ToKenism-Multi Deep Dive

### 4.1 Submodule Status: EMPTY

`PMOVES-ToKenism-Multi/` contains only a `.git` directory — no source files. The submodule is initialized at commit `be883747f829` on branch `PMOVES.AI-Edition-Hardened`, but the working tree was not populated.

**Cannot perform source-code analysis of:**
- 9 TypeScript CHIT contract modules
- 8 ERC-20 token implementations (FoodUSD, EnergyUSD, HealthUSD, RideUSD, GroToken, GroVault, GroupPurchase, CoopGovernor)
- OpenZeppelin version and Solidity version
- CHIT HMAC integration in smart contracts
- Audit reports or test coverage

### 4.2 Evidence from Code Review (2026-03-01)

A comprehensive code review was performed on PRs #44 and #45:

**Architecture:**
- TypeScript NATS client with CHIT contract subjects: `tokenism.attribution.recorded.v1`, `tokenism.cgp.ready.v1`
- Hardhat CI with `working-directory: contracts/solidity`
- Docker with non-root `appuser` (UID 1000)
- Flask backend with `os.urandom` SECRET_KEY and CORS locked to explicit origins

**Security findings:**

| ID | Severity | Finding |
|----|----------|--------|
| P1-1 | CRITICAL | TypeScript NATS client unauthenticated fallback: `nats://localhost:4222` when NATS_URL unset |
| P1-2 | HIGH | `minioadmin/minioadmin` default credentials in 3 tier env files |
| P2-1 | MEDIUM | ServiceTier local fallback missing `ui` tier in 2 files |
| P2-2 | MEDIUM | Runtime `pip install gunicorn` in Docker entrypoint (supply-chain gap) |
| P2-3 | MEDIUM | Gunicorn bound to `0.0.0.0` instead of `127.0.0.1` |

**Positive findings:**
- CHIT contract subjects match canonical NATS catalog
- Firefly auth is fail-closed (raises on empty token)
- Rate limiting on simulation endpoint (10 req/60s per-IP)
- Export syntax fully removed from env files

### 4.3 Five Mathematical Pillars (from CHIT Implementation Audit 2026-02-08)

All five pillars are implemented in TypeScript (NOT Python):

| Pillar | File | Lines | Status |
|--------|------|-------|--------|
| Dirichlet Distributions | `dirichlet-weights.ts` | 338 | IMPLEMENTED |
| Hyperbolic Geometry | `hyperbolic-encoder.ts` | 395 | IMPLEMENTED |
| Merkle Proofs | `shape-attribution.ts` | 621 | IMPLEMENTED |
| Zeta Spectral Filtering | `zeta-filter.ts` | 387 | IMPLEMENTED |
| Swarm Optimization | `swarm-attribution.ts` | 550 | IMPLEMENTED |

**Python implementations**: NONE. All math is TypeScript-only.

---

## Part 5: Cross-Reference Analysis

### 5.1 TAC Tree GRAPHITI Flows vs Actual Code

| TAC Tree Flow | NATS Subject | Code Implementation | Status |
|---------------|--------------|-------------------|--------|
| codex to pr-monitor | `ops.pr.monitor.completed.v1` | No implementation found | **PLANNED ONLY** |
| claude-opus to pr-trim | `ops.pr.trim.completed.v1` | No implementation found | **PLANNED ONLY** |
| tokenism to chit:review-sweep | `ops.pr.learnings.encoded.v1` | No implementation found | **PLANNED ONLY** |
| archon to chit:sign-trail | `agent.graphiti.signed.v1` | `sign_trail.py` (267 lines) | **PARTIAL** (signs but does not subscribe to upstream) |
| cipher memory store | `cipher.memory.stored.v1` | `pmoves-cipher-mcp/tools.py` | **WORKING** |
| cipher memory search | `cipher.memory.searched.v1` | `pmoves-cipher-mcp/tools.py` | **WORKING** |
| cipher reasoning store | `cipher.reasoning.stored.v1` | `pmoves-cipher-mcp/tools.py` | **WORKING** |
| FlOO$ DAG resolution | Various `floos.*` subjects | `floos_resolver.py` (1,011 lines) | **WORKING** (unauthenticated hooks) |

**Verdict**: 3 of 4 GRAPHITI pipeline stages have no code. Only the final signing stage exists, but operates standalone.

### 5.2 TAC Tree Subjects: Working vs Planned

| Category | Total Subjects | Working Code | Planned Only |
|----------|---------------|--------------|-------------|
| GRAPHITI-direct | 1 | 0 | 1 |
| PR monitor pipeline | 6 | 0 | 6 |
| CHIT encoding | 15+ | Partial (encoder/decoder only) | Most |
| Cipher memory | 3 | 3 | 0 |
| FlOO$ DAG | 10+ | Yes (unauthenticated) | 0 |
| Training pipeline | 20+ | 0 | 20+ |
| Agent lifecycle | 15+ | Partial (sign_trail only) | Most |

**Approximate**: ~20% of defined NATS subjects have corresponding working code.

### 5.3 Gap Analysis: TAC Tree Design vs Implementation

**Gap 1: Pipeline Orchestration**
TAC trees define a 4-stage pipeline with NATS-driven handoffs. No pipeline orchestrator exists that subscribes to upstream subjects and triggers downstream stages. `sign_trail.py` is a CLI tool, not a NATS subscriber.

**Gap 2: CHIT Encoding in Pipeline Context**
TAC tree stage 3 (tokenism) is supposed to encode PR learnings as CHIT CGPs. `chit_encoder_hook.py` exists but is a content-to-CGP encoder, not a PR-learning-to-CGP encoder. No code maps `pr_monitor_report` to `chit.cgp.v0.2` format.

**Gap 3: GRAPHITI Trail as Pipeline Output**
TAC trees specify `agent.graphiti.signed.v1` as pipeline output. `sign_trail.py` can produce signed payloads but only via CLI invocation. No auto-signing on NATS message receipt (PostToolUse hook mentioned in protocol but not found in code).

**Gap 4: Cipher to GRAPHITI Integration**
TAC trees do not define cipher-memory subjects in GRAPHITI context. Cipher MCP operates independently with its own 3 NATS subjects. No bridge between cipher memory storage and GRAPHITI trail signing.

**Gap 5: FlOO$ DAG to CHIT Skills**
TAC trees define 14 CHIT/GRAPHITI skills with pairings. `floos_resolver.py` builds DAGs from `skill-pairings.yaml` but publishes hooks unauthenticated. No code verifies CHIT skill execution produced valid CGP output.

### 5.4 Is the pr-monitor-graphiti-chit Flow Implemented?

```
codex[/pr-monitor] -> claude-opus[/pr-trim] -> tokenism[/chit:review-sweep] -> archon[/chit:sign-trail]
```

**Answer: NO.** Individual components exist but are not wired together:

| Component | Exists? | Wired to Pipeline? |
|-----------|---------|-------------------|
| codex PR monitor | Unknown (submodule empty) | No |
| claude-opus PR trim | Not found | No |
| tokenism CHIT review-sweep | Not found | No |
| archon sign-trail | `sign_trail.py` | No (CLI-only, no NATS subscribe) |
| NATS subscription chain | No code subscribes to upstream | No |
| End-to-end test | None | No |

### 5.5 GRAPHITI Protocol Reference vs Implementation

| Protocol Feature | Documented | Implemented |
|-----------------|------------|-------------|
| HMAC-SHA256 signing | Yes | Yes (`chit_security.py`) |
| 8-agent registry | Yes | Yes (`agent_signatures.yaml`) |
| Handoff protocol | Yes | In payload format but not consumed |
| CGP attribution extension | Yes | In payload format but not validated |
| Schema validation (advisory) | Yes | Yes (soft-skips on ImportError) |
| NATS emission to `agent.graphiti.signed.v1` | Yes | No (CLI stdout only) |
| PostToolUse auto-sign hook | Yes | **Not found in codebase** |
| Skill pairing integration | Yes | Partial (FlOO$ DAG exists) |
| Development mode | Yes | Not found |
| Constant-time HMAC comparison | Yes | Yes (`hmac.compare_digest`) |

---

## Consolidated Findings

### CRITICAL (Immediate Action Required)

| ID | Finding | Impact |
|----|---------|--------|
| C1 | AES-GCM KDF mismatch (scrypt vs PBKDF2) in chit_sign.py vs chit_security.py | Cross-module decryption impossible — silent data loss |
| C2 | AES-GCM plaintext format mismatch (JSON vs binary float32) | Cross-module decryption produces garbage even if KDF fixed |
| C3 | Silent signature verification bypass when chit_security import fails | Any ImportError disables all HMAC verification |

### HIGH

| ID | Finding | Impact |
|----|---------|--------|
| H1 | 3 duplicate canon() functions with no shared import | Signature drift risk on any modification |
| H2 | Zero test coverage for all 18 crypto code paths | No regression protection for security-critical code |
| H3 | TypeScript NATS client unauthenticated fallback (ToKenism) | Silent auth bypass when NATS_URL unset |
| H4 | Signature envelope format mismatch (ts field, hardcoded kid) | chit_sign.py signatures are non-standard |

### MEDIUM

| ID | Finding | Impact |
|----|---------|--------|
| M1 | NATS hook payloads in FlOO$ have no authentication | Any NATS subscriber can inject fake pipeline events |
| M2 | Secrets stored as cleartext or base16 hex in CGP files | Zero confidentiality for secrets in CGP format |
| M3 | Signature expiry checked against CGP created_at, not sig timestamp | Wrong-window accept/reject decisions |
| M4 | CGP schema version drift (3 incompatible identifiers) | No version negotiation between services |
| M5 | 80% of TAC tree NATS subjects have no code | Design-implementation gap creates false operational confidence |
| M6 | `minioadmin` default credentials in 3 ToKenism env files | Known credential exposure |
| M7 | `pmoves-cipher-mcp/` not a submodule | Cannot be independently versioned or CI-tested |

### LOW

| ID | Finding | Impact |
|----|---------|--------|
| L1 | No IV reuse detection for AES-GCM | Negligible with os.urandom(12) but no defense-in-depth |
| L2 | Hardcoded trusted source list in validator | Requires code change to add sources |
| L3 | Missing `.gitignore` in pmoves-cipher-mcp | Potential tracking of venv/cache files |

---

## Recommendations

### Priority 1: Fix Crypto Interoperability (Week 1)

1. **Delete `chit_sign.py`** or refactor to import from `chit_security.py`. It produces incompatible signatures and encrypted anchors.
2. **Consolidate `canon()`** into a single `pmoves.tools.chit_canon` module. All consumers must import from it.
3. **Add fail-closed mode** to `chit_security_validator.py`: raise exception when `chit_security` unavailable and `security_level >= SIGNED`.

### Priority 2: Add Crypto Tests (Week 1-2)

Minimum viable test suite (6 tests):
- `test_sign_verify_roundtrip` — sign then verify returns True
- `test_sign_tamper_reject` — modify signed CGP, verify returns False
- `test_encrypt_decrypt_roundtrip` — encrypt then decrypt recovers original anchors
- `test_decrypt_wrong_passphrase` — raises exception
- `test_validator_rejects_missing_sig` — CGPValidator rejects unsigned CGP at SIGNED level
- `test_validator_rejects_expired` — CGPValidator rejects CGP with old created_at

### Priority 3: Wire GRAPHITI Pipeline (Week 2-3)

1. Create a NATS subscriber service that listens to `ops.pr.learnings.encoded.v1` and triggers `sign_trail.py`
2. Implement stages 1-3 of the pr-monitor-graphiti-chit pipeline (or explicitly mark as future work)
3. Add end-to-end integration test for the 4-stage pipeline

### Priority 4: Harden Cipher MCP (Week 3)

1. Fix dangling `pmoves-botz-cipher:8000` reference to `cipher-api:8105`
2. Add auth requirement — fail closed when `CIPHER_API_TOKEN` is unset
3. Add missing NATS event for `pmoves_cipher_reasoning_patterns` tool
4. Convert to proper git submodule

### Priority 5: Populate Empty Submodules (Week 4)

```bash
git submodule update --init PMOVES-ToKenism-Multi
git submodule update --init Pmoves-cipher
```

Then re-audit ToKenism smart contracts and cipher-api Node.js service.

### Priority 6: Align TAC Trees with Reality (Ongoing)

1. Add `status: implemented` / `status: planned` to every NATS subject in TAC trees
2. Resolve CGP schema version drift — pick one canonical version
3. Remove or mark GRAPHITI_MARK references if they do not exist

---

## Appendix A: File Inventory

### CHIT Crypto Files (4 files with crypto)

| File | Lines | Crypto Operations |
|------|-------|------------------|
| `pmoves/tools/chit_security.py` | 128 | HMAC-SHA256, PBKDF2, AES-GCM |
| `pmoves/services/gateway/scripts/chit_sign.py` | 77 | HMAC-SHA256, scrypt, AES-GCM (INCOMPATIBLE) |
| `pmoves/tools/chit_security_validator.py` | 589 | Calls verify_cgp, decrypt_anchors |
| `pmoves/scripts/fleet/generate-enrollment.py` | 130+ | HMAC-SHA256 (duplicate canon) |

### CHIT Non-Crypto Files

| File | Lines | Role |
|------|-------|------|
| `pmoves/tools/chit/chit_decoder.py` | 522 | CGP to content decoder (FAISS) |
| `pmoves/tools/chit/chit_decoder_mm.py` | 374 | Multi-modal CGP decoder (CLIP) |
| `pmoves/tools/chit/__init__.py` | 122 | Convenience API wrappers |
| `pmoves/tools/chit/floos_resolver.py` | 1,011 | DAG pipeline orchestrator |
| `pmoves/tools/sign_trail.py` | 267 | Git commit signing CLI |
| `pmoves/tools/chit_encode_hook.py` | 290 | Content to CGP encoder (SHA-256/512 fingerprinting only) |
| `pmoves/tools/chit_a2ui_bridge.py` | 227 | CGP to Remotion transpiler |
| `pmoves/tools/topology_chit_gate.py` | 723 | Docker topology validator |
| `pmoves/tests/test_sign_trail.py` | 22 | 2 non-crypto tests |

### Cipher MCP Files

| File | Lines | Role |
|------|-------|------|
| `pmoves-cipher-mcp/cipher_mcp/server.py` | 87 | MCP stdio server |
| `pmoves-cipher-mcp/cipher_mcp/client.py` | 197 | HTTP client to cipher-api |
| `pmoves-cipher-mcp/cipher_mcp/tools.py` | 280 | 4 MCP tool definitions |
| `pmoves-cipher-mcp/cipher_mcp/nats_events.py` | 73 | NATS event publisher |

### GRAPHITI Protocol & TAC Trees

| File | Lines | Role |
|------|-------|------|
| `pmoves/docs/GRAPHITI_PROTOCOL_REFERENCE.md` | ~400 | Full protocol spec |
| `pmoves/docs/GRAPHITI_AGENT_REGISTRY.md` | — | 8-agent visual identity registry |
| `pmoves/docs/PMOVESCHIT/CHIT_IMPLEMENTATION_AUDIT_2026-02-08.md` | ~500 | Implementation completeness audit |
| 6 TAC tree YAML files | 3,081 | Operational specifications |

### Empty Submodules (No Source Available)

- `Pmoves-cipher/` — Only `.git` (cipher-api Node.js service)
- `PMOVES-ToKenism-Multi/` — Only `.git` (9 TS modules + 8 Solidity contracts)

---

## Appendix B: GRAPHITI Agent Registry (8 Agents)

| Agent | Glyph | Color | Voice | Primary Domains |
|-------|-------|-------|-------|----------------|
| claude-opus | ◆ | #7C3AED | analytical | security-audit, architecture, cross-repo-orchestration |
| kilocode | ▲ | #059669 | architectural | feature-impl, mcp-integration, vs-code |
| codex | ■ | #2563EB | terse | rapid-prototyping, code-gen, cipher-memory |
| gemini | ★ | #D97706 | strategic | planning, research, synthesis |
| cline | ● | #DC2626 | conversational | rapid-iteration, chat-impl, frontend |
| powerfulmoves | ⚡ | #F59E0B | directive | vision, doctrine, final-authority |
| crush | ◇ | #0EA5E9 | companion | terminal-gateway, pair-programming, onboarding |
| darkxside | ✦ | #E11D48 | witness | cocreation, witness, prosodic-flow |

---

## Appendix C: CGP Schema Versions

| Version String | Used By | Format |
|---------------|---------|--------|
| `chit.cgp.v0.1` | TypeScript CGP generator | Basic super_nodes/constellations/points |
| `chit.cgp.v0.2` | TypeScript CGP generator | v0.1 + attribution (Dirichlet, Merkle) + hyperbolic encoding |
| `chit.cgp.v1.0` | chit_security_validator.py | Validation target |
| `geometry.cgp.v1` | Hi-RAG, Gateway CHIT API | Transport layer identifier |
| `cgp.v1` | Consciousness Service cgp_mapper.py | **NON-STANDARD** — inconsistent with all others |

---
*End of report. Generated by Agent Zero Deep Research on 2026-04-17 using GLM-5-Turbo.*
