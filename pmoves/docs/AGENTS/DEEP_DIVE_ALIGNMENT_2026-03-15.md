# Deep-Dive Alignment Analysis — 2026-03-15

> Cross-submodule alignment findings from TAC tree deep-dive covering 6 target submodules: Agent Zero, autoresearch, ClawZ, a0-plugins, Cipher Memory, and BoTZ (update).

## 1. Service Overlap Analysis

### 1.1 Honcho Plugin vs Cipher Memory

| Dimension | Honcho (a0-plugin) | Cipher Memory (8105) |
|-----------|-------------------|---------------------|
| Backend | External service | Neo4j + optional Qdrant |
| Transport | Agent Zero runtime | HTTP API + MCP (stdio) |
| Persistence | Session-scoped | Knowledge-graph persistent |
| Categories | Generic key-value | 6 structured categories + 3 resilience categories |
| PMOVES integration | None | Full — resilience backbone for all agents |
| **Recommendation** | Gap-fill only | **Preferred** — native, MCP-integrated, Neo4j-backed |

### 1.2 YouTube Transcriber Plugin vs PMOVES.YT

| Dimension | `youtube_transcribe` (a0-plugin) | PMOVES.YT (8077) |
|-----------|-------------------------------|-------------------|
| Capabilities | Basic transcript fetch | Full pipeline: download → transcribe → index |
| Storage | In-memory | MinIO object storage |
| Events | None | NATS (`ingest.file.added.v1`, `ingest.transcript.ready.v1`) |
| Downstream | Agent Zero only | Extract Worker → Qdrant + Meilisearch + Discord |
| **Recommendation** | Light/quick use | **Preferred** — full pipeline with event-driven consumers |

### 1.3 ClawZ DM Security vs BoTZ auth.py

| Dimension | ClawZ | BoTZ |
|-----------|-------|------|
| Auth model | DM pairing + bootstrap tokens per channel | JWT verification (fail-closed since `auth.py:63-67` fix) |
| Scope | Per-channel, per-user | API-wide |
| Risk | Token lifecycle management across 25+ platforms | P1 fail-open vulnerability |
| **Alignment need** | Different security domains | Need shared auth strategy for when ClawZ delegates to BoTZ skills |

### 1.4 langfuse_observability Plugin vs TensorZero

| Dimension | langfuse (a0-plugin) | TensorZero (3030) |
|-----------|---------------------|-------------------|
| Scope | LLM observability only | Full model gateway + ClickHouse metrics |
| Integration | Agent Zero plugin | Platform-wide gateway |
| **Recommendation** | Redundant | **Preferred** — unified observability through TensorZero |

---

## 2. Integration Gaps

### 2.1 Agent Zero ↔ autoresearch: No Orchestration Path

**Current state:** autoresearch runs as a standalone CLI tool on a GPU host. There is no mechanism for Agent Zero to delegate experiment runs, monitor progress, or collect results.

**Impact:** Manual GPU host management required. Experiment results are siloed on the GPU host.

**Proposed solution:** Add NATS publishing to autoresearch (`research.autoresearch.experiment.v1`, `research.autoresearch.result.v1`) and an Agent Zero task handler that can trigger experiments via SSH/NATS.

> **Note:** When implemented, the new subjects (`research.autoresearch.experiment.v1`, `research.autoresearch.result.v1`, `openclaw.message.received.v1`, `openclaw.channel.connected.v1`, `cipher.memory.stored.v1`, `cipher.memory.searched.v1`) must be added to `.claude/context/nats-subjects.md` and `.claude/context/services-catalog.md`.

### 2.2 ClawZ ↔ NATS: Silent 25+ Channels

**Current state:** ClawZ handles messages from 25+ platforms but publishes no events to the NATS bus. This means the entire messaging layer is invisible to event-driven services (Publisher-Discord, observability, Hi-RAG).

**Impact:** No cross-platform message analytics, no event-driven responses to inbound messages, no Cipher Memory persistence of conversations.

**Proposed solution:** Add NATS adapter publishing `openclaw.message.received.v1` and `openclaw.channel.connected.v1` events.

### 2.3 Cipher ↔ NATS: HTTP-Only, Event-Invisible

**Current state:** Cipher Memory operates as an HTTP-only service. Memory store/search operations are invisible to the NATS event bus, meaning no other service can react to memory events.

**Impact:** Cannot trigger downstream actions when agents checkpoint (e.g., notify Grafana, update Graphiti trail, alert on unusual patterns).

**Proposed solution:** Publish `cipher.memory.stored.v1` and `cipher.memory.searched.v1` to NATS after each operation.

### 2.4 a0-plugins ↔ BoTZ: Dual Ecosystems

**Current state:** Two parallel ecosystems exist for extending Agent Zero capabilities:
- **a0-plugins:** Community-driven, 13 plugins, CI-validated, file-based index
- **BoTZ Skills:** PMOVES-native, 100+ MCP tools, NATS-integrated, Supabase-backed

**Impact:** Confusion about which is canonical. 4 plugins duplicate PMOVES native services.

**Proposed solution:** Establish clear boundary — a0-plugins for community/external contributions; BoTZ for PMOVES-native, production-grade capabilities. Document overlap in a0-plugins TAC tree (done).

---

## 3. Enhancement Proposals

### E1: NATS Publishing for Cipher Memory

**Priority:** P3 (Medium-term)
**Subjects:** `cipher.memory.stored.v1`, `cipher.memory.searched.v1`
**Benefit:** Enable event-driven observability of agent checkpointing patterns. Allow Grafana dashboards to track memory usage. Enable Graphiti trail correlation.
**Effort:** Small — add NATS client to Cipher Memory Node.js service, publish after each API call.

### E2: ClawZ NATS Adapter for Channel Events

**Priority:** P3 (Medium-term)
**Subjects:** `openclaw.message.received.v1`, `openclaw.message.sent.v1`, `openclaw.channel.connected.v1`
**Benefit:** Route inbound chat messages to Agent Zero for task delegation. Enable cross-channel analytics. Feed conversations to Hi-RAG for knowledge indexing.
**Effort:** Medium — create NATS client in ClawZ's Node.js runtime, publish on message events.

### E3: autoresearch → AgentGym RL Bridge

**Priority:** P4 (Long-term)
**Subjects:** `research.autoresearch.result.v1`
**Benefit:** Feed experiment results (val_bpb improvements, architecture mutations) into AgentGym RL for training pipeline continuity. Creates a closed loop: autoresearch finds better architectures → AgentGym trains agents with those architectures → agents improve at research.
**Effort:** Medium — define result schema, add NATS publishing, create AgentGym subscriber.

### E4: CHIT Attribution for ClawZ Message Routing

**Priority:** P4 (Long-term)
**Benefit:** Track which channel delivered a message, which agent processed it, and what the outcome was. Enables per-channel performance analytics and agent attribution.
**Effort:** Medium — integrate CGP packet generation into ClawZ message routing pipeline.

### E5: Plugin Deduplication Strategy

**Priority:** P2 (Short-term)
**Action:** Document in a0-plugins README that PMOVES native services are preferred for overlapping capabilities. Add "PMOVES Alternative" field to plugin index.yaml schema for plugins that overlap.
**Affected plugins:** `honcho` → Cipher, `youtube_transcribe` → PMOVES.YT (YouTube), `langfuse_observability` → TensorZero, `discord` → Publisher-Discord.

---

## 4. Production Readiness Summary

| Service | /healthz | /metrics | Auth | NATS | Docker | CHIT | Overall |
|---------|----------|----------|------|------|--------|------|---------|
| **Agent Zero** | GREEN | GREEN | Partial | Active (2 subjects) | GREEN | Full (5/5 toggles) | **Mega** |
| **BoTZ** | Partial | Yes | P1 **fixed** (fail-closed) | Active (5 subjects) | Yes | Partial | Stage 1 |
| **Cipher** | GREEN (`/health`) | MISSING | MISSING | MISSING | Partial | None | Base |
| **ClawZ** | GREEN | Optional (OTEL) | Partial (DM pairing) | MISSING | Partial | None | Pre-Stage |
| **autoresearch** | N/A (CLI) | N/A | N/A | MISSING | N/A (GPU host) | None | Pre-Stage |
| **a0-plugins** | N/A (index) | N/A | N/A (GitHub CI) | N/A | N/A | None | Base |

### Key Findings

1. **Agent Zero is the most mature** — Mega evolution, all 5 CHIT toggles, full healthz/metrics, resilience backbone via Cipher
2. **Cipher is critical but under-hardened** — serves as resilience backbone for all agents but lacks auth, metrics, and NATS presence
3. **ClawZ and autoresearch are Pre-Stage** — both need foundational work before PMOVES production integration
4. **a0-plugins overlap problem** — 4 of 13 plugins duplicate PMOVES native services, needs deduplication strategy
5. ~~**BoTZ auth vulnerability remains P1**~~ — **Fixed**: `auth.py:63-67` now raises HTTPException 500 (fail-closed)

---

## 5. Recommended Priority Order

1. ~~**P1:** Fix BoTZ JWT fail-open (`auth.py:59`)~~ → **Fixed**
2. ~~**P1:** Fix Cipher `CIPHER_URL` default mismatch~~ → **Fixed** (main compose + gateway-agent + VPS override aligned to `cipher-api:8105`; note: library defaults in submodule code may still differ — verify per-service fallback values)
3. **P2:** Add Cipher API authentication
4. **P2:** Add ClawZ Prometheus `/metrics` endpoint
5. **P2:** Document plugin deduplication strategy (E5)
6. **P3:** Add Cipher NATS publishing (E1)
7. **P3:** Add ClawZ NATS adapter (E2)
8. **P3:** Add autoresearch NATS publishing
9. **P4:** autoresearch → AgentGym bridge (E3)
10. **P4:** ClawZ CHIT attribution (E4)

---

## TAC Trees Created/Updated

| TAC File | Action | Status |
|----------|--------|--------|
| `TAC_AGENT_ZERO.md` | Created | Complete |
| `TAC_AUTORESEARCH.md` | Created | Complete |
| `TAC_CLAWZ.md` | Created | Complete |
| `TAC_A0_PLUGINS.md` | Created | Complete |
| `TAC_CIPHER.md` | Created | Complete |
| `TAC_BOTZ.md` | Updated (deep-dive findings) | Complete |
| `TAC_INTEGRATION_TOPOLOGY.md` | Updated (v2.0 — 13 TAC trees) | Complete |

## Registry Updates

| Entry | Action | Status |
|-------|--------|--------|
| `autoresearch` | Added with topology | Complete |
| `clawz` | Added with topology | Complete |
| `a0_plugins` | Added with topology | Complete |
| `agent_zero` | Added `chit_integration`, `topology` | Complete |
| `cipher_memory` | Added `chit_integration`, `topology` | Complete |
| `botz_gateway` | Added `chit_integration`, `topology` | Complete |

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-DEEP-DIVE-ALIGNMENT::2026-03-15 -->
