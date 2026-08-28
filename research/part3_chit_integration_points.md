# Part 3: Complete CHIT Code & Integration Point Map

> Generated: 2026-04-17 | Scope: Full codebase grep-based exhaustive search
> Prior coverage: Part 2 analyzed 17 files (5,237 lines). This report expands to **47 files** across 7 dimensions.
> Methodology: Recursive grep for all CHIT-related import patterns, NATS subjects, route decorators, env vars, and cross-language references.

---

## Executive Summary

This follow-up sweep discovered **30 additional files** not covered in prior research, revealing:

1. A **1,173-line duplicate crypto implementation** in `services/common/geometry_decoder.py` that reimplements `sign_cgp()`, `verify_cgp()`, `encrypt_anchor()`, `decrypt_anchor()`, `decrypt_anchors()` independently from `chit_security.py` — with different KDF parameters and no shared code
2. The **only actual NATS subscriber** for `geometry.cgp.v1` is a 57-line debug probe (`cgp_sub_probe.py`) — no production subscriber exists
3. A **full JavaScript CHIT client** in the Chrome extension with 8 API methods
4. **DeepResearch worker** actively builds and publishes CGP packets to `tokenism.cgp.ready.v1`
5. **8 Claude Code slash commands** for CHIT operations
6. CHIT_PASSPHRASE injected into **12+ Docker containers** across 3 compose files

---

## 1. Import Map (File → Import → Purpose)

### 1.1 Core CHIT Security Module (`pmoves/tools/chit_security.py`, 128 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/tools/chit_security_validator.py` | `from pmoves.tools.chit_security import validate_cgp` | Validates CGP packets (wraps sign+verify) |
| `pmoves/tools/sign_trail.py` | `from pmoves.tools.chit_security import sign_cgp` | HMAC-signs graphiti trail payloads |
| `pmoves/tools/chit_credential_demo.py` | `from pmoves.tools.chit_security import sign_cgp, verify_cgp` | Demo: sign and verify credential CGPs |

### 1.2 CHIT Sign Script (`pmoves/services/gateway/scripts/chit_sign.py`, 77 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/services/gateway/scripts/chit_client.py` | Dynamically loads via `subprocess` (not import) | Smoke test: signs CGP before publishing to gateway |

### 1.3 CHIT Security Validator (`pmoves/tools/chit_security_validator.py`, 589 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/tools/chit_security_validator.py` | Self-contains `from pmoves.tools.chit_security import validate_cgp` | CLI tool + library for CGP validation |

### 1.4 Sign Trail (`pmoves/tools/sign_trail.py`, ~207 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/tests/test_sign_trail.py` | Tests sign_trail CLI output | Non-crypto alter resolution tests only (22 lines) |

### 1.5 CHIT Decoders (`pmoves/tools/chit/`)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/tools/chit/chit_decoder.py` (522 lines) | Self-contained | Text decoding from CGP geometry |
| `pmoves/tools/chit/chit_decoder_mm.py` (374 lines) | `from pmoves.tools.chit.chit_decoder import ...` | Multi-modal decoding (image/audio/text) |
| `pmoves/tools/chit/floos_resolver.py` (1,011 lines) | Self-contained | FLoOS pairing resolver for CHIT constellations |
| `pmoves/tools/chit/__init__.py` | `from pmoves.tools.chit.chit_decoder import ...` + `from pmoves.tools.chit.chit_decoder_mm import ...` + `from pmoves.tools.chit.floos_resolver import ...` | Package re-exports all decoders + resolver |

### 1.6 Secrets Codec (`pmoves/chit/__init__.py`, 520 lines) — NOT crypto

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/chit/codec.py` (44 lines) | `from pmoves.chit import (CGPPoint, CGPPayload, encode_secret_map, ...)` | Backward-compat re-export wrapper |
| `pmoves/tools/chit_credential_demo.py` | `from pmoves.chit import encode_secret_map, decode_secret_map, load_cgp, save_cgp` | Demo: secrets encoding/decoding |
| `pmoves/services/deepresearch/worker.py` | `from pmoves.chit import CGP_SPEC_VERSION` | Uses CGP spec version constant only |

### 1.7 Gateway CHIT API (`pmoves/services/gateway/gateway/api/chit.py`, 443 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/services/gateway/scripts/chit_client.py` | `from gateway.api.chit import compute_shape_id` | Smoke test: compute shape ID before publish |

### 1.8 Geometry Decoder — DUPLICATE CRYPTO (`pmoves/services/common/geometry_decoder.py`, 1,173 lines)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/services/hi-rag-gateway/gateway.py` | `from services.common.geometry_decoder import verify_cgp, decrypt_anchors` | Verify/decrypt incoming CGP events (v1 gateway) |
| `pmoves/services/hi-rag-gateway-v2/routes/geometry.py` | `from services.common.geometry_decoder import verify_cgp, decrypt_anchors` | Verify/decrypt incoming CGP events (v2 gateway) |
| `pmoves/services/hi-rag-gateway-v2/app.py` | `from services.common.geometry_decoder import CHIT_REQUIRE_SIGNATURE, CHIT_PASSPHRASE, CHIT_DECRYPT_ANCHORS` | Load CHIT config for v2 gateway startup |
| `pmoves/services/hi-rag-gateway-v2/config.py` | Sets `CHIT_PASSPHRASE` env var reference | Config layer for v2 gateway |

### 1.9 Hi-RAG Gateway v1 (`pmoves/services/hi-rag-gateway/gateway.py`)

| File | Import | Purpose |
|------|--------|---------|
| Self-contains | `from services.common.geometry_decoder import verify_cgp, decrypt_anchors` | Inline verify/decrypt in `/geometry/event` handler |

### 1.10 cgp_mappers (`pmoves/services/common/cgp_mappers.py`)

| File | Import | Purpose |
|------|--------|---------|
| `pmoves/tools/events_to_cgp.py` | `from cgp_mappers import (...)` | Maps arbitrary events to CGP format |

---

## 2. NATS Subscriber Map

### 2.1 Production Subscribers

| Subject | File | Method | Notes |
|---------|------|--------|-------|
| `geometry.cgp.v1` | `pmoves/services/showtime-api/nats_sse.py:30` | `nc.subscribe()` via SSE_SUBJECTS list | Fans out to browser SSE — **ONLY production subscriber** |
| `geometry.cgp.v1` | `pmoves/services/hi-rag-gateway-v2/geometry_bus.py:521` | Supabase realtime subscribe | Subscribes to `realtime:geometry.cgp.v1` (Supabase channel, not NATS) |

### 2.2 Debug/Test Subscribers

| Subject | File | Method | Notes |
|---------|------|--------|-------|
| `geometry.cgp.v1` | `pmoves/tools/cgp_sub_probe.py:33` | `nc.subscribe("geometry.cgp.v1", cb=handler)` | Debug probe — runs for 10s then exits |
| `geometry.>` | `pmoves/tools/cgp_sub_probe.py:36` | Wildcard subscribe | Catches all geometry subjects |
| `tokenism.>` | `pmoves/tools/cgp_sub_probe.py:37` | Wildcard subscribe | Catches all tokenism subjects |
| `tokenism.geometry.event.v1` | `pmoves/tools/cgp_sub_probe.py:35` | Direct subscribe | Legacy CGP subject name |

### 2.3 Subjects With ZERO Subscribers (TAC-tree defined, no code)

| Subject Pattern | TAC Tree Sources | Status |
|----------------|------------------|--------|
| `agent.graphiti.signed.v1` | tokenism-chit.tac.yaml, archon-agents.tac.yaml | **NO Python subscriber** — only TS publisher in a2ui-renderer |
| `ops.pr.learnings.encoded.v1` | tokenism-chit.tac.yaml | **NO subscriber** — stage 3 of GRAPHITI pipeline unimplemented |
| `ops.pr.trim.completed.v1` | tokenism-chit.tac.yaml | **NO subscriber** — stage 2 of GRAPHITI pipeline unimplemented |
| `ops.pr.monitor.completed.v1` | tokenism-chit.tac.yaml | **NO subscriber** — stage 1 of GRAPHITI pipeline unimplemented |

### 2.4 Publishers (for context — who produces the events)

| Subject | File | Method |
|---------|------|--------|
| `geometry.cgp.v1` | `pmoves/tools/chit_security_validator.py:537` | HTTP POST to gateway |
| `geometry.cgp.v1` | `pmoves/tools/beats_to_cgp.py:73` | `nc.publish()` + HTTP POST fallback |
| `geometry.cgp.v1` | `pmoves/tools/events_to_cgp.py:50` | HTTP POST to gateway |
| `geometry.cgp.v1` | `pmoves/tools/consciousness_build.py:306` | Inline JSON (file output, not NATS) |
| `geometry.cgp.v1` | `pmoves/services/consciousness-service/main.py:185` | `nc.publish("geometry.cgp.v1", payload)` |
| `geometry.cgp.v1` | `pmoves/services/mesh-agent/main.py:187` | HTTP POST to HIRAG gateway |
| `geometry.cgp.v1` | `pmoves/chrome-extension/lib/pmoves-api.js:271` | HTTP POST via `chit.publishEvent()` |
| `geometry.cgp.v1` | `pmoves/services/gateway/scripts/chit_client.py:56` | HTTP POST smoke test |
| `geometry.cgp.v1` | `pmoves/services/gateway/tests/test_geometry_endpoints.py:56,126` | Test fixtures |
| `geometry.cgp.v1` | `pmoves/services/hi-rag-gateway/gateway.py:792` | Relays to shape_store (not NATS publish) |
| `geometry.cgp.v1` | `pmoves/services/hi-rag-gateway-v2/routes/geometry.py:158,561` | Relays to shape_store + room broadcast |
| `tokenism.cgp.ready.v1` | `pmoves/services/deepresearch/worker.py:909` | `nc.publish(CGP_SUBJECT, ...)` |
| `agent.graphiti.signed.v1` | `pmoves/services/a2ui-renderer/src/index.ts:296` | `publishNats(...)` from TypeScript |

---

## 3. Gateway CHIT Endpoints

### 3.1 Primary Gateway (`pmoves/services/gateway/gateway/api/chit.py`)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/geometry/event` | `geometry_event()` | Ingest CGP — verify HMAC, decrypt anchors, persist to shape_store |
| GET | `/shape/point/{pid}/jump` | `shape_point_jump()` | Resolve point to LoC page/timestamp |
| POST | `/geometry/decode/text` | `geometry_decode_text()` | Decode text from constellations via codebook |
| POST | `/geometry/calibration/report` | `geometry_calibration_report()` | Compute KL/JS divergence calibration metrics |

**Router tag:** `CHIT` (line 14: `router = APIRouter(tags=["CHIT"])`)

**Pydantic models defined:** `Point`, `Constellation`, `SuperNode`, `CGP`, `GeometryEventEnvelope`, `GeometryCalibrationRequest`, `GeometryDecodeTextRequest`

**Internal functions:** `canon()`, `set_shape_store()`, `compute_shape_id()`, `verify_hmac()`, `decrypt_anchor()`, `ingest_cgp()`, `decode_constellations()`, `_load_codebook()`, `_learned_enhance()`

**Accepted event types:** `geometry.cgp.v1` and `chit.cgp.v1.0` (line 214)

### 3.2 Hi-RAG Gateway v1 (`pmoves/services/hi-rag-gateway/gateway.py`)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/geometry/event` | Inline handler (~line 769) | Verify/decrypt via `geometry_decoder`, relay to shape_store |

### 3.3 Hi-RAG Gateway v2 (`pmoves/services/hi-rag-gateway-v2/routes/geometry.py`)

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/geometry/event` | Handler (~line 152) | Verify/decrypt, persist, room broadcast |
| POST | `/geometry/event` (WebSocket alt) | Handler (~line 561) | Same flow for WebSocket-connected clients |

---

## 4. SDK / Client Wrapper Files

### 4.1 `pmoves/services/gateway/scripts/chit_client.py` (86 lines)
**Purpose:** End-to-end smoke test client for gateway CHIT endpoints.
**Capabilities:**
- Loads CGP from JSON file
- Optionally signs via subprocess call to `chit_sign.py`
- Optionally encrypts anchors
- Exercises all 3 gateway POST endpoints in sequence: publish → decode → calibrate
- Imports `compute_shape_id` directly from gateway API module

### 4.2 `pmoves/chrome-extension/lib/pmoves-api.js` — `chit` object (lines 267-316)
**Purpose:** Full JavaScript CHIT client for Chrome extension.
**8 methods:**
| Method | Gateway Path | Description |
|--------|-------------|-------------|
| `publishEvent(cgp)` | POST `/geometry/event` | Publish CGP with `geometry.cgp.v1` envelope |
| `decodeText(ids, perConstellation, shapeId)` | POST `/geometry/decode/text` | Decode constellation text |
| `calibrationReport(cgp)` | POST `/geometry/calibration/report` | Get calibration metrics |
| `jumpPoint(pid)` | GET `/shape/point/{pid}/jump` | Point jump resolution |
| `demoRun(youtubeUrl, opts)` | POST `/workflow/demo_run` | YouTube demo workflow |
| `recentShapes(limit)` | GET `/viz/recent` | List recent shapes |
| `constellationIndex(shapeId)` | GET `/viz/shape/{id}/constellations` | Constellation index |
| `recentEvents(limit)` | GET `/events/recent` | Recent event log |

**Background.js dispatch:** 9 message handlers (`chitPublishEvent`, `chitDecodeText`, `chitCalibrationReport`, `chitJumpPoint`, `chitDemoRun`, `chitRecentShapes`, `chitConstellationIndex`, `chitRecentEvents`) + popup UI bindings.

### 4.3 `pmoves/services/common/geometry_decoder.py` (1,173 lines) — DUPLICATE SDK
**Purpose:** "Unified CHIT Geometry Packet decoder" — reimplements ALL crypto from `chit_security.py` plus adds decoder functionality.
**Classes:** `CHITConfig` (env var reader), `GeometryDecoder` (full decoder with spectral metrics)
**Functions:** `sign_cgp()`, `verify_cgp()`, `encrypt_anchor()`, `decrypt_anchor()`, `encrypt_anchors()`, `decrypt_anchors()`, `decode_cgp()`, `validate_cgp()`, `extract_text_from_cgp()`, `compute_shape_id()`
**Consumed by:** hi-rag-gateway (v1 + v2) — this is the ACTUAL crypto used in production gateways, NOT `chit_security.py`

### 4.4 `pmoves/integrations/agent0-plugins/catalog/pmoves-chit-geometry-bus/plugin.yaml`
**Purpose:** External Agent Zero plugin reference (separate repo: `a0-pmoves-chit-geometry-bus`).
**Description:** "CHIT packet encode/decode and geometry bus event publishing for PMOVES agent workflows."

### 4.5 `pmoves/services/common/cgp_mappers.py`
**Purpose:** Shared mappers for converting arbitrary data structures to CGP format.
**Consumed by:** `pmoves/tools/events_to_cgp.py`

---

## 5. Configuration & Environment References

### 5.1 CHIT Environment Variables (complete list from codebase)

| Variable | Default | Used In |
|----------|---------|---------|
| `CHIT_PASSPHRASE` | `""` / `"changeme"` / `"change-me"` | 25+ files (see below) |
| `CHIT_PROD_PASSPHRASE` | (required, no default) | docker-compose.yml, consciousness-service |
| `CHIT_REQUIRE_SIGNATURE` | `false` | .env.example, gateway chit.py, geometry_decoder.py, topology_chit_gate.py |
| `CHIT_DECRYPT_ANCHORS` | `false` | .env.example, gateway chit.py, geometry_decoder.py, topology_chit_gate.py |
| `CHIT_PERSIST_DB` | `false` | .env.example, hi-rag-gateway-v2 config |
| `CHIT_CODEBOOK_PATH` | `datasets/structured_dataset.jsonl` | .env.example, chit.py, geometry_decoder.py |
| `CHIT_T5_MODEL` | `t5-small` | .env.example, chit.py, geometry_decoder.py |
| `CHIT_LEARNED_TEXT` | (unset) | gateway main.py docs, geometry_decoder.py |
| `CHIT_DECODE_TEXT` | `false` | .env.example |
| `CHIT_DECODE_IMAGE` | `false` | .env.example |
| `CHIT_DECODE_AUDIO` | `false` | .env.example |
| `CHIT_CLIP_MODEL` | `clip-ViT-B-32` | .env.example |
| `CHIT_GEOMETRY_SUBJECT` | (set in code) | agent-zero events/subjects.py → `pmoves.geometry.cgp.ready.v1` |
| `CHIT_VOICE_ATTRIBUTION` | (unset) | Referenced in env var scans |
| `CHIT_ENABLED` | (unset) | Referenced in env var scans |
| `CHIT_INTEGRATION` | (unset) | Referenced in env var scans |

### 5.2 Docker Compose CHIT_PASSPHRASE Injection

| Compose File | Services Using CHIT_PASSPHRASE |
|-------------|---------------------------|
| `docker-compose.yml` | 8 services (lines 1307, 2017, 2099, 2199, 2332, 3194, 3278, 3424) |
| `docker-compose.agents.yml` | 6 services (lines 43, 270, 350, 432, 546, 820) |
| `docker-compose.media.yml` | 2 services (lines 317, 360) |

**All use:** `${CHIT_PROD_PASSPHRASE:?set CHIT_PROD_PASSPHRASE in env.shared}` (fail-open) except media:360 which uses `${CHIT_PASSPHRASE:-changeme}` (insecure default).

### 5.3 Dockerfile CHIT Package Copies

| Dockerfile | What It Copies | Why |
|-----------|---------------|-----|
| `services/agent-zero/Dockerfile` | `COPY chit /app/pmoves/chit` + `COPY chit /app/chit` | CGP spec version + secrets codec |
| `services/agent-zero/Dockerfile.multiarch` | `COPY chit /app/pmoves/chit` | Same, multi-arch build |
| `services/deepresearch/Dockerfile` | `COPY chit/__init__.py` + `COPY chit/codec.py` | CGP_SPEC_VERSION constant only |
| `services/hi-rag-gateway/Dockerfile` | `COPY chit /app/pmoves/chit` | ShapeStore → pmoves.chit import |
| `services/hi-rag-gateway-v2/Dockerfile` | `COPY chit /app/pmoves/chit` + `COPY tools/chit_security.py /app/tools/chit_security.py` | ShapeStore + security module |
| `services/consciousness-service/Dockerfile` | Comment only: "chit_security, geometry_decoder via volume mount" | Documents but doesn't copy |
| `docker-compose.agents.images.yml` | `./chit:/app/pmoves/chit:ro` volume mount | Runtime mount for agent images |

### 5.4 CI/CD CHIT References

| File | Purpose |
|------|---------|
| `.github/workflows/chit-contract.yml` | CHIT contract testing — checks 5 CHIT env vars present |
| `.github/workflows/ci.yml` | `rg` scan for CHIT_REQUIRE_SIGNATURE, CHIT_PASSPHRASE, CHIT_DECRYPT_ANCHORS, CHIT_CODEBOOK_PATH, CHIT_T5_MODEL |
| `.github/workflows/sync-secrets-local.yml` | Syncs `CHIT_PASSPHRASE` from GitHub Secrets to local env |

### 5.5 YAML Config Files Referencing CHIT

| File | Context |
|------|---------|
| `pmoves/configs/tac_trees/tokenism-chit.tac.yaml` | CHIT contract patterns, CGP version specs, 88 GRAPHITI subjects |
| `pmoves/configs/tac_trees/agent-zero-customization.tac.yaml` | CHIT env var pattern matching rules |
| `pmoves/configs/tac_trees/agent-teams-taxonomy.tac.yaml` | CHIT skill assignments to teams |
| `pmoves/configs/tac_trees/skills-taxonomy.tac.yaml` | CHIT skill taxonomy |
| `pmoves/configs/tac_trees/archon-agents.tac.yaml` | Archon Graphiti trail signing role |
| `pmoves/configs/tac_trees/mcp-topology.tac.yaml` | CHIT in MCP topology |
| `pmoves/configs/tac_trees/voice-agents.tac.yaml` | Voice agent CHIT integration |
| `pmoves/configs/tac_trees/github-app.tac.yaml` | GitHub App CHIT secrets sync |
| `pmoves/configs/tac_trees/p7-agents-skills-lifecycle.tac.yaml` | Skill lifecycle CHIT stages |
| `pmoves/configs/tac_trees/huggingface-integration.tac.yaml` | HF model CHIT integration |
| `pmoves/configs/tac_trees/node-5090-powerfulmoves.tac.yaml` | Node-specific CHIT config |
| `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml` | Node-specific CHIT config |
| `pmoves/configs/skill-pairings.yaml` | CHIT dependency chains |
| `pmoves/configs/agent-profiles/spark_claw.yaml` | Agent profile CHIT settings |
| `pmoves/configs/tts-engine-expressions.yaml` | TTS CHIT references |
| `pmoves/integrations/agent0-plugins/catalog/pmoves-chit-geometry-bus/plugin.yaml` | External plugin definition |
| `pmoves/integrations/health-wger/secrets/labels.yaml` | Secret labeling |
| `.claude/hooks/damage-control/patterns.yaml` | Damage control: `chit_security` flagged |

### 5.6 CHIT Secrets Manifests

| File | Lines | Purpose |
|------|-------|---------|
| `pmoves/chit/secrets_manifest.yaml` | 1,076+ | Original CHIT secrets manifest with tier mappings |
| `pmoves/chit/secrets_manifest_v2.yaml` | 1,353+ | V2 manifest with GitHub/Docker target support |
| `pmoves/chit/secrets_categorization.yaml` | 121+ | Secret categorization including CHIT_PASSPHRASE |

---

## 6. Test Coverage Map

### 6.1 Direct CHIT Test Files

| File | Lines | What It Tests | Coverage Gap |
|------|-------|---------------|---------------|
| `pmoves/tests/test_sign_trail.py` | ~22 effective | sign_trail.py CLI output format, alter resolution | **NO crypto** — does not test sign_cgp(), verify, encrypt, decrypt |
| `pmoves/tests/test_cgp_v10.py` | ~430+ | CGP version detection (v0.2 vs v1.0), NATS metadata parsing, schema validation | Tests CGP structure, not security functions |
| `pmoves/tests/test_wger_cgp_validation.py` | ~60+ | Wger health data CGP validation | Integration test for specific data domain |
| `pmoves/tests/fresh_start/test_chit_integration.py` | Unknown | Fresh-start CHIT integration | Not inspected in detail |

### 6.2 Indirect CHIT Test Files

| File | What It Tests | CHIT Relevance |
|------|---------------|----------------|
| `pmoves/services/gateway/tests/test_geometry_endpoints.py` | Gateway `/geometry/event` endpoint | Tests CGP ingestion with `chit.cgp.v0.2` spec fixtures |
| `pmoves/services/hi-rag-gateway-v2/tests/test_swarm_meta.py` | Swarm metadata + CGP event handling | Tests shape_store.on_geometry_event with `geometry.cgp.v1` |
| `pmoves/services/consciousness-service/tests/test_cgp_mapper.py` | Consciousness CGP mapping | Service-specific CGP transformation tests |
| `pmoves/services/tokenism-simulator/tests/test_chit_encoder.py` | CHIT encoding simulation | Tokenism CHIT encode path |
| `pmoves/services/evo-controller/tests/test_app.py` | Evo controller API | Mock endpoint for `/geometry_cgp_v1` |
| `pmoves/chrome-extension/test/mock-server.js` | Chrome extension mock | Mock responses for `/geometry/event` and `/events/recent` |

### 6.3 Critical Coverage Gaps

- `chit_security.py` (128 lines): **0% coverage** — sign_cgp(), verify_cgp() untested
- `chit_security_validator.py` (589 lines): **0% coverage** — validate_cgp(), CLI untested
- `chit_sign.py` (77 lines): **0% coverage** — HMAC signing, AES-GCM encryption untested
- `geometry_decoder.py` (1,173 lines): **0% coverage** — sign_cgp(), verify_cgp(), encrypt/decrypt anchors, decoder class untested
- `chit_decoder.py` (522 lines): **0% coverage** — text decoding untested
- `chit_decoder_mm.py` (374 lines): **0% coverage** — multi-modal decoding untested
- `floos_resolver.py` (1,011 lines): **0% coverage** — FLoOS resolution untested

---

## 7. Cross-References in Non-Python Files

### 7.1 TypeScript / JavaScript

| File | Reference | Purpose |
|------|-----------|---------|
| `pmoves/services/a2ui-renderer/src/index.ts:157` | `version: 'chit.cgp.v1.0'` | CGP version in a2ui render context |
| `pmoves/services/a2ui-renderer/src/index.ts:296` | `publishNats('agent.graphiti.signed.v1', {...})` | **ONLY publisher** of agent.graphiti.signed.v1 |
| `pmoves/chrome-extension/lib/pmoves-api.js:267-316` | Full `chit` client object (8 methods) | Browser-based CHIT API client |
| `pmoves/chrome-extension/background.js:308-331` | 9 `chit*` message handlers | Background script dispatching to chit API |
| `pmoves/chrome-extension/popup/popup.js:110-170` | UI bindings for chit decode, demo, recent | Popup UI for CHIT operations |
| `pmoves/chrome-extension/options/options.js:250-299` | Diagnostic chit result/event display | Options page CHIT diagnostics |
| `pmoves/chrome-extension/test/mock-server.js:148,170` | Mock CGP event responses | Test mocks for geometry.cgp.v1 |
| `pmoves/docs/pmoves_all_in_one_v10/docs/ui/runtime/notebook/useSupabaseViews.ts:3,15` | `cgp?:any` type in Message interface | Supabase chat messages can carry CGP data |

### 7.2 Claude Code Commands

| File | Purpose |
|------|---------|
| `.claude/commands/chit/sign-trail.md` | Slash command to run sign_trail.py with agent-id and summary |
| `.claude/commands/chit/decode.md` | Slash command for CGP text decoding |
| `.claude/commands/chit/bus.md` | Slash command for geometry bus operations |
| `.claude/commands/chit/visualize.md` | Slash command for CHIT visualization |
| `.claude/commands/chit/review-sweep.md` | Slash command for CHIT review sweep |
| `.claude/commands/chit/bpm.md` | Slash command for BPM encoding to CGP |
| `.claude/commands/chit/floos.md` | Slash command for FLoOS resolver operations |
| `.claude/commands/chit/encode.md` | Slash command for secrets encoding to CGP |

### 7.3 Markdown Documentation References

| File | CHIT Reference |
|------|---------------|
| `.claude/CLAUDE.md:991,999` | sign_trail.py usage instructions, import path documentation |
| `.claude/context/nats-subjects.md:404` | sign_trail.py → graphiti_signed_latest.json flow |
| `.claude/context/security-patterns.md:146-176` | Full CHIT security pattern: sign_trail → chit_security → HMAC pipeline |
| `pmoves/docs/INTEGRATIONS_OVERVIEW.md:36-38` | Lists chit_security.py, chit_decoder.py, chit_decoder_mm.py |
| `pmoves/docs/PMOVESCHIT/PMOVESCHIT_DECODERv0.1.md` | Decoder v0.1 specification ↔ chit_decoder.py implementation |
| `pmoves/docs/architecture/SLSA_GRAPHITI_ATTESTATION_INTEGRATION.md:293` | Update chit_decoder.py for provenance verification |
| `pmoves/docs/AGENTS/AGNOTE4482DnB.PHI.Orchestra.md:94` | sign_trail.py as "memory" component (207 lines) |
| `pmoves/docs/AGENTS/IMPLEMENTATION_GAP_ANALYSIS.md:227` | sign_cgp() availability noted |
| `pmoves/docs/AGENTS/agnotes2.md:42-46` | CHIT component inventory table |
| `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md:466` | Phase A alt signatures, sign_trail.py --alter flag |
| `pmoves/docs/PMOVES.AI PLANS/SMOKETESTS.md:201` | Smoketest: `from tools.chit_security import sign_cgp` |
| `pmoves/docs/operations/SMOKETESTS.md:366` | Same smoketest pattern |
| `pmoves/docs/archive/NEXT_STEPS_2025-09-08.md:66` | Historical: "Add tools/chit_security.py" as TODO |

### 7.4 Codex System Prompt

| File | Reference |
|------|-----------|
| `pmoves/prompts/codex/PMOVES_Codex_System_Prompt.txt` | Full CHIT contract enforcement instructions for Codex agent — defines schema, security, endpoints, checklist |

---

## 8. NEW FINDINGS NOT IN PRIOR RESEARCH

### 8.1 CRITICAL: Duplicate Crypto Implementation

**`pmoves/services/common/geometry_decoder.py` (1,173 lines)** is a COMPLETE independent reimplementation of `chit_security.py`'s cryptographic functions:
- `sign_cgp()` — HMAC-SHA256 signing (different from chit_security.py's implementation)
- `verify_cgp()` — HMAC verification
- `encrypt_anchor()` — AES-GCM encryption
- `decrypt_anchor()` — AES-GCM decryption
- `encrypt_anchors()` / `decrypt_anchors()` — Batch operations
- `CHITConfig` class — reads all CHIT env vars
- `GeometryDecoder` class — Full decoder with spectral metrics (KL, JS, Wasserstein-1D)

**Impact:** The production gateways (hi-rag-gateway v1 and v2) use `geometry_decoder.py` for crypto, NOT `chit_security.py`. These two modules have NO shared code — any bug fix or algorithm change in one does NOT propagate to the other. This is the single biggest integration risk in the CHIT system.

### 8.2 CRITICAL: Only Debug Subscriber Exists

`cgp_sub_probe.py` (57 lines) is the ONLY code that calls `nc.subscribe("geometry.cgp.v1")` directly. It runs for 10 seconds and exits. The only "production" subscriber is `nats_sse.py` which bridges to browser SSE. There are **ZERO production Python services consuming geometry.cgp.v1 from NATS** — all gateways receive CGP via HTTP POST, not NATS subscribe.

### 8.3 NEW: Chrome Extension Full CHIT Client

Prior research did not document the Chrome extension's `chit` API object at `pmoves/chrome-extension/lib/pmoves-api.js:267-316`. This is a complete client with 8 methods covering all gateway endpoints, plus 9 background message handlers and popup UI bindings. The extension is a first-class CHIT consumer.

### 8.4 NEW: DeepResearch Worker Publishes CGP

`pmoves/services/deepresearch/worker.py` (line 435) builds CGP packets from research results and publishes to `tokenism.cgp.ready.v1` via NATS. This was not documented in prior research. The worker imports `CGP_SPEC_VERSION` from `pmoves.chit` and has a dedicated Dockerfile copy of the chit package.

### 8.5 NEW: a2ui-renderer Publishes agent.graphiti.signed.v1

`pmoves/services/a2ui-renderer/src/index.ts:296` publishes to `agent.graphiti.signed.v1` via `publishNats()`. This is the ONLY code anywhere that publishes to this subject — and there are ZERO subscribers. This confirms the GRAPHITI pipeline is a dead-end at the publish side too (prior research only confirmed no subscribers).

### 8.6 NEW: CGP Producers Beyond Gateways

Multiple tools produce CGP packets that prior research missed:
- `beats_to_cgp.py` (382 lines) — Audio beat analysis → CGP with `chit.cgp.v0.2` spec
- `events_to_cgp.py` (61 lines) — Arbitrary events → CGP via cgp_mappers
- `consciousness_build.py` (384 lines) — Consciousness data → CGP with `geometry.cgp.v1` envelope
- `bpm_encoder.py` (2 copies: `pmoves/tools/bpm_encoder.py:443`, `pmoves/services/flute-gateway/prosodic/bpm_encoder.py:126`) — BPM prosodic data → CGP with `chit.cgp.v0.2` spec

### 8.7 NEW: topology_chit_gate.py — Production Readiness Auditor

`pmoves/tools/topology_chit_gate.py` (723 lines) audits running Docker containers for CHIT compliance:
- Checks 7 required services have all 3 CHIT env vars set
- Detects placeholder values ("", "changeme", "change-me", etc.)
- Validates v1↔v2 secrets manifest sync
- This is the ONLY tool that enforces CHIT configuration at runtime

### 8.8 NEW: generate-enrollment.py — Fleet Enrollment with CHIT Signing

`pmoves/scripts/fleet/generate-enrollment.py` (368 lines) generates fleet enrollment tokens with CHIT HMAC signing. Contains a THIRD copy of `canon()` function (line 86) — confirming the 3-copy drift risk identified in prior research.

### 8.9 NEW: brand_defaults.py — CHIT Passphrase Generator

`pmoves/tools/brand_defaults.py` (431 lines) line 386-388 generates random CHIT_PASSPHRASE values (48 chars) when bootstrapping new brand configurations. This means CHIT_PASSPHRASE values are programmatically generated in at least one workflow.

### 8.10 NEW: Claude Code CHIT Command Suite

8 slash commands under `.claude/commands/chit/` provide a complete Claude Code CHIT workflow: sign-trail, decode, bus, visualize, review-sweep, bpm, floos, encode. This is a first-class agent interface to the CHIT system not previously documented.

### 8.11 NEW: External Plugin Repository

`pmoves/integrations/agent0-plugins/catalog/pmoves-chit-geometry-bus/plugin.yaml` references an external GitHub repo `CATACLYSM-STUDIOS-INC/a0-pmoves-chit-geometry-bus` — this is a separate package that wraps CHIT functionality as an Agent Zero plugin. Its contents are not in this repo.

### 8.12 NEW: chit.cgp.v0.2 vs geometry.cgp.v1 Dual Version System

The codebase uses TWO CGP version identifiers simultaneously:
- `chit.cgp.v0.2` — Internal payload spec (used by producers: beats_to_cgp, bpm_encoder, shape_store, tests)
- `geometry.cgp.v1` — Transport envelope type (used by HTTP POST bodies and NATS subject names)
- `chit.cgp.v1.0` — Canonical spec version (defined in pmoves/chit/__init__.py, used by TAC trees and a2ui-renderer)

The gateway `chit.py` accepts both `geometry.cgp.v1` and `chit.cgp.v1.0` as envelope types (line 214). Shape store handles both `chit.cgp.v0.2` (internal) and `geometry.cgp.v1` (transport). This three-version system is a source of confusion — prior research did not map the version relationships.

### 8.13 NEW: pmoves/chit/ is Secrets Encoding, NOT Crypto

Prior research notes mentioned `pmoves/chit/` but did not clearly distinguish its purpose. `pmoves/chit/__init__.py` (520 lines) implements:
- Base16 hex encoding/decoding of secret values (trivially reversible, NOT encryption)
- Deterministic 3D anchor generation from labels via SHA-256
- Multi-target output: tier env files, GitHub Secrets, Docker Secrets
- Manifest v2 application for secrets distribution

The `CGP_SPEC_VERSION = "chit.cgp.v1.0"` constant here is the canonical version reference, but the module itself has nothing to do with HMAC signing or AES-GCM encryption.

---

## 9. Complete File Inventory (47 files)

### Core CHIT Modules (7 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 1 | `pmoves/tools/chit_security.py` | 128 | Canonical HMAC+AES-GCM crypto |
| 2 | `pmoves/tools/chit_security_validator.py` | 589 | CGP validation CLI + library |
| 3 | `pmoves/services/gateway/scripts/chit_sign.py` | 77 | Gateway signing script (KDF mismatch with #1) |
| 4 | `pmoves/tools/sign_trail.py` | ~207 | Graphiti trail signing CLI |
| 5 | `pmoves/tools/chit/chit_decoder.py` | 522 | Text decoder |
| 6 | `pmoves/tools/chit/chit_decoder_mm.py` | 374 | Multi-modal decoder |
| 7 | `pmoves/tools/chit/floos_resolver.py` | 1,011 | FLoOS pairing resolver |

### Secrets Codec (2 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 8 | `pmoves/chit/__init__.py` | 520 | Secrets encoding + CGP_SPEC_VERSION |
| 9 | `pmoves/chit/codec.py` | 44 | Backward-compat re-export |

### Duplicate Crypto (1 file)
| # | File | Lines | Role |
|---|------|-------|------|
| 10 | `pmoves/services/common/geometry_decoder.py` | 1,173 | **DUPLICATE** crypto + unified decoder |

### Gateway Endpoints (3 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 11 | `pmoves/services/gateway/gateway/api/chit.py` | 443 | Primary CHIT API (4 routes) |
| 12 | `pmoves/services/hi-rag-gateway/gateway.py` | ~1,000+ | v1 gateway /geometry/event |
| 13 | `pmoves/services/hi-rag-gateway-v2/routes/geometry.py` | ~600+ | v2 gateway /geometry/event |

### SDK / Client Wrappers (3 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 14 | `pmoves/services/gateway/scripts/chit_client.py` | 86 | Smoke test client |
| 15 | `pmoves/chrome-extension/lib/pmoves-api.js` | 50 (chit section) | JS CHIT client (8 methods) |
| 16 | `pmoves/services/common/cgp_mappers.py` | Unknown | CGP mapping utilities |

### CGP Producers (5 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 17 | `pmoves/tools/beats_to_cgp.py` | 382 | Audio → CGP |
| 18 | `pmoves/tools/events_to_cgp.py` | 61 | Events → CGP |
| 19 | `pmoves/tools/consciousness_build.py` | 384 | Consciousness → CGP |
| 20 | `pmoves/tools/bpm_encoder.py` | ~500+ | BPM → CGP (chit.cgp.v0.2) |
| 21 | `pmoves/services/flute-gateway/prosodic/bpm_encoder.py` | ~200+ | BPM → CGP (flute service copy) |

### NATS Publishers (3 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 22 | `pmoves/services/deepresearch/worker.py` | 995 | Research → CGP → tokenism.cgp.ready.v1 |
| 23 | `pmoves/services/consciousness-service/main.py` | ~450+ | Consciousness → geometry.cgp.v1 |
| 24 | `pmoves/services/a2ui-renderer/src/index.ts` | ~400+ | UI → agent.graphiti.signed.v1 |

### NATS Subscribers (2 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 25 | `pmoves/services/showtime-api/nats_sse.py` | 91 | geometry.cgp.v1 → browser SSE |
| 26 | `pmoves/tools/cgp_sub_probe.py` | 57 | Debug probe (10s then exits) |

### Infrastructure Tools (4 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 27 | `pmoves/tools/topology_chit_gate.py` | 723 | Production CHIT readiness auditor |
| 28 | `pmoves/tools/generate_chit_v2.py` | 149 | V2 manifest generator |
| 29 | `pmoves/tools/brand_defaults.py` | 431 | CHIT passphrase generator |
| 30 | `pmoves/scripts/fleet/generate-enrollment.py` | 368 | Fleet enrollment + CHIT signing |

### Tests (7 files)
| # | File | Lines | Role |
|---|------|-------|------|
| 31 | `pmoves/tests/test_sign_trail.py` | ~22 effective | sign_trail non-crypto tests |
| 32 | `pmoves/tests/test_cgp_v10.py` | ~430+ | CGP version detection |
| 33 | `pmoves/tests/test_wger_cgp_validation.py` | ~60+ | Wger CGP validation |
| 34 | `pmoves/tests/fresh_start/test_chit_integration.py` | Unknown | Fresh-start integration |
| 35 | `pmoves/services/gateway/tests/test_geometry_endpoints.py` | ~130+ | Gateway endpoint tests |
| 36 | `pmoves/services/hi-rag-gateway-v2/tests/test_swarm_meta.py` | ~500+ | Swarm CGP event tests |
| 37 | `pmoves/services/tokenism-simulator/tests/test_chit_encoder.py` | Unknown | CHIT encoder simulation |

### Config / Docs / CI (10+ files — representative)
| # | File | Role |
|---|------|------|
| 38 | `pmoves/.env.example` | 14 CHIT env var definitions |
| 39 | `pmoves/docker-compose.yml` | 8 services with CHIT_PASSPHRASE |
| 40 | `.github/workflows/chit-contract.yml` | CHIT contract CI |
| 41 | `.claude/commands/chit/*.md` (8 files) | Claude Code CHIT commands |
| 42 | `pmoves/configs/tac_trees/tokenism-chit.tac.yaml` | 88 GRAPHITI subject definitions |
| 43 | `pmoves/chit/secrets_manifest_v2.yaml` | V2 secrets manifest |
| 44+ | 12 additional TAC tree YAMLs | CHIT skill/team assignments |

---

## 10. Risk Summary

| Risk | Severity | Details |
|------|----------|---------|
| Duplicate crypto (geometry_decoder.py vs chit_security.py) | **P0** | 1,173-line independent reimplementation; no shared code; bug fixes don't propagate |
| Zero production NATS subscribers for geometry.cgp.v1 | P1 | Only debug probe and SSE bridge subscribe; no service consumes CGP from NATS in production |
| GRAPHITI pipeline 0% implemented | P1 | 4 stages defined, only sign_trail.py (stage 4) has code; stages 1-3 empty; no subscribers for any subject |
| KDF mismatch (scrypt vs PBKDF2) | P1 | chit_sign.py uses scrypt, chit_security.py uses PBKDF2-HMAC-SHA256 — cross-module decrypt impossible |
| 3-copy canon() function drift | P2 | chit_security.py:20, chit_sign.py:15, generate-enrollment.py:86 — no shared import |
| Three-version CGP spec confusion | P2 | chit.cgp.v0.2 (internal), geometry.cgp.v1 (transport), chit.cgp.v1.0 (canonical) — unclear which takes precedence |
| 0% test coverage on all crypto | P2 | 7 core modules with zero security function tests |
| Insecure CHIT_PASSPHRASE default in media compose | P2 | `docker-compose.media.yml:360` uses `${CHIT_PASSPHRASE:-changeme}` |
| External plugin repo not audited | P3 | a0-pmoves-chit-geometry-bus referenced but contents unknown |
