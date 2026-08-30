# PR #1415 Code Review

**PR:** feat(p7): SPARK provenance pipeline + space-agent NATS + A2UI Pretext
**Branch:** feature/launch-readiness-stage-0 → main
**Size:** 7,594 additions / 113 deletions in 68 files
**Reviewer:** Code Reviewer (Agent Zero)
**Date:** 2026-05-01

---

## Review Summary

**Verdict:** REQUEST CHANGES

**Overview:** Stage-0 foundational work introducing a content provenance pipeline (shape → attest → gate), NATS streaming between services, A2UI provenance renderer, signing identity cards, and extensive documentation. The pipeline design is sound and the contract-first approach is strong, but a critical supply-chain risk in module-level code execution, unauthenticated endpoints, and hardcoded credential defaults block merge.

---

## Critical Issues

### C1: Supply-Chain Code Execution via Module-Level Dynamic Import
- **File:** `pmoves/services/content-provenance-gate/main.py:6117-6135`
- **OWASP:** A08:2021 (Software and Data Integrity Failures)
- `chit_encode_content = _load_chit_encode_content()` executes at import time. Uses `importlib.util.spec_from_file_location()` + `spec.loader.exec_module()` to load an arbitrary Python file discovered by walking `Path(__file__).resolve().parents[N]`. No integrity check on the loaded file. Executes before any application security controls.
- **Impact:** Attacker who writes `chit_encode_hook.py` to any parent directory achieves arbitrary code execution at process start.
- **Fix:** (a) Move to a called function with pinned exact path, or (b) add file hash verification before loading, or (c) import as a proper Python package with path controlled by validated env var.

---

## High Issues

### H1: Unauthenticated Endpoints Expose Pipeline + Metrics
- **File:** `pmoves/services/content-provenance-gate/main.py:6593-6628`
- **OWASP:** A01:2021 (Broken Access Control)
- `/metrics`, `/v1/preview/raw`, `/v1/evaluate` have zero auth. `/metrics` leaks operational intelligence (request rates, NATS status, queue depths). `/v1/preview/raw` runs the full CPU-intensive pipeline — trivially DoS-able. Compare to hi-rag-gateway-v2 which correctly uses `Depends(require_tailscale)` on provenance endpoints.
- **Fix:** Add auth middleware to all three. At minimum restrict `/metrics` to internal network.

### H2: Hardcoded Credentials in Defaults
- **Files:** `content-provenance-gate/main.py:6039`, `channel-monitor/main.py:5541,5538`
- **OWASP:** A02:2021 + A05:2021
- `nats://nats:pmoves@nats:4222` appears in two new files. `postgresql://postgres:postgres@supabase-db:5432/postgres` in channel-monitor. Passwords `pmoves` and `postgres:postgres` are now permanently in git history.
- **Fix:** Remove defaults entirely — use `os.environ["NATS_URL"]` (raise if missing). Rotate both passwords immediately. Add pre-commit hook to prevent recurrence.

### H3: No Input Validation on POST Endpoints
- **File:** `content-provenance-gate/main.py:6617-6628`
- **OWASP:** A03:2021 + A04:2021
- Both `/v1/preview/raw` and `/v1/evaluate` accept `Dict[str, Any]` with no schema validation. No size limit, no type enforcement, no required field checks. `str(payload.get("text", ""))` will stringify arbitrary nested dicts creating enormous strings for the tokenizer.
- **Fix:** Define Pydantic models with `max_length` constraints. Cap `_parse_message_body` to ~1MB before `json.loads`.

### H4: Feature Flags Default to ENABLED
- **Files:** `channel-monitor/main.py:5543-5545`, `ffmpeg-whisper/server.py`
- `CHANNEL_MONITOR_CONTENT_RAW_PUBLISH` and `FFW_CONTENT_RAW_PUBLISH` default to `"true"`. New deployments automatically publish unvalidated Discord messages to `content.raw.v1` — bypassing front-door validation.
- **Fix:** Default both to `"false"`. Require explicit opt-in.

### H5: PR Size — 7.5× Recommended Limit
- 7,594 additions across 68 files. The skill's threshold is ~1,000 lines. This PR contains at minimum 4 independent concerns: (1) content-provenance-gate service, (2) hi-rag-gateway-v2 provenance integration, (3) a2ui-renderer provenance composition, (4) signing identity cards + audit tooling.
- **Fix:** For future PRs, split by service boundary. Not blocking this specific PR given stage-0 context, but flagging for process improvement.

---

## Medium Issues

### M1: Dockerfile Missing Container Hardening
- **File:** `content-provenance-gate/Dockerfile`
- Has `USER pmoves:pmoves` (good) but missing `cap_drop ALL`, `no-new-privileges`, read-only root filesystem.
- **Fix:** Add hardening directives in compose/K8s manifest.

### M2: StaticFiles Mount Exposes Full Directory
- **File:** `hi-rag-gateway-v2/app.py:6902-6908`
- `StaticFiles(directory=str(_hyperdimensions_dir), html=True)` mounts entire repo directory. Source maps, config files, dev artifacts potentially exposed.
- **Fix:** Mount a specific `dist/` or `build/` subdirectory. Add auth dependency.

### M3: Zero Rate Limiting on New Endpoints
- **File:** `content-provenance-gate/main.py` (entire service)
- `/v1/preview/raw` does tokenization + TF scoring + Merkle tree — CPU-intensive. No rate limiter, no request body size middleware. a2ui-renderer correctly uses `renderLimiter`.
- **Fix:** Add slowapi or equivalent with ~10/minute limit. Add 512KB body cap.

### M4: Duplicated Stopword Lists Across 4 Files
- `content-provenance-gate/main.py:6060-6090`, `channel-monitor/monitor.py:5667-5672`, `hi-rag-gateway-v2/provenance_geometry.py:7186+`, and likely more.
- **Fix:** Extract to `pmoves/services/common/text.py` or similar.

### M5: Duplicated `_compact()` Function
- `hi-rag-gateway-v2/provenance_ingest.py:7688-7701` and `channel-monitor/monitor.py:5689-5693` have identical implementations.
- **Fix:** Move to common utilities.

### M6: Hardcoded agent_id 'darkxside' in a2ui-renderer
- **File:** `a2ui-renderer/src/index.ts:4165,4181`
- All provenance renders attributed to 'darkxside' regardless of requester. Corrupts graphiti attribution trail.
- **Fix:** Read from env var or authenticated request context.

### M7: Channel-Monitor NATS Client Has No Reconnection
- **File:** `channel-monitor/main.py:5588-5593`
- Connects once in lifespan, no resilience loop. Compare to content-provenance-gate which has exponential backoff reconnection. If NATS bounces, channel-monitor silently stops publishing.
- **Fix:** Add reconnection loop or at least log-level degradation when publish fails.

### M8: CHANNEL_MONITOR_SECRET Warning-Only Enforcement
- **File:** `channel-monitor/main.py:5546-5548`
- Missing secret logs warning but doesn't abort startup. Protected endpoints silently become unprotected.
- **Fix:** Fail fast in production mode.

---

## Low / Nitpick Issues

### L1: `jsonschema` in requirements.in but Never Imported
- **File:** `content-provenance-gate/requirements.in:6644`
- `jsonschema>=4.0.0` listed but no `import jsonschema` found in main.py.
- **Fix:** Remove if unused, or add contract validation.

### L2: Tests Don't Cover NATS Message Handler Paths
- **File:** `tests/services/test_content_provenance_gate.py`
- Tests only cover the HTTP preview endpoint. `_handle_raw`, `_handle_shaped`, `_handle_attested` message handlers have no test coverage.
- **Fix:** Add unit tests for message handlers with mocked NATS client.

### L3: Tests Don't Cover Edge Cases
- No tests for: empty text, missing fields, oversized payloads, non-string types in favorite_words/aliases.
- **Fix:** Add parameterized edge-case tests.

### L4: `provenance_geometry.py` Stopword List is Largest (4th Copy)
- ~50+ stopwords vs ~30 in other copies. Inconsistency risks different shaping results across services.
- **Fix:** Single source of truth (see M4).

---

## What's Done Well

- **Contract-first design:** JSON Schema contracts for all 5 provenance subjects (raw, shaped, attested, accepted, rejected) before implementation. This is the right order.
- **Non-root Docker:** `USER pmoves:pmoves` with dedicated group, pinned base image with SHA256 digest, `PYTHONDONTWRITEBYTECODE=1`.
- **NATS stream config:** Clean single-stream design, limits-based retention, explicit ack, max 5 deliveries. Well-documented.
- **Merkle tree:** Cryptographically clean implementation — no injection surfaces, pure SHA256 over hex strings.
- **Prometheus observability:** Counters for received/published/failed by subject, histograms for processing duration. Proper `_labels()` usage.
- **Resilience pattern:** Exponential backoff NATS reconnection in content-provenance-gate with proper cleanup on cancel.
- **Hi-RAG provenance routes:** Correctly use `Depends(require_admin_tailscale)` auth + Pydantic models. Good pattern the gate service should follow.
- **Signing identity cards:** Well-documented YAML with clear advisory-mode semantics. sign_trail.py correctly refuses to pick when multiple active cards exist for one agent_id.
- **Audit tooling:** `audit_naming_drift.py` is read-only, comprehensive, and has good test coverage including strict-mode failure expectations.
- **Workflow responsibility:** Triggers disabled with clear re-enable criteria. Manual dispatch only.
- **Envelope correlation:** NATS publish properly threads correlation_id and parent_id through the event envelope.

---

## Verification Story

- **Tests reviewed:** Yes
  - content-provenance-gate: 3 tests (happy path acceptance, noise rejection, contract schema validation). Covers the core pipeline but misses NATS handlers and edge cases.
  - audit_naming_drift: 8 tests (report generation, strict mode, JSON mode, card counts, PEM count, unit tests for parsers/regex). Good coverage.
  - hi-rag provenance_geometry: Tests exist but not fully read — confirmed present.
  - channel-monitor: Test file exists (`tests/test_monitor.py`) but changes not reviewed in detail.
- **Build verified:** No — cannot execute Docker builds in this environment.
- **Security checked:** Yes — dedicated security-auditor subordinate confirmed all findings. No injection vectors in Merkle tree or semantic scoring. SSRF unlikely in a2ui-renderer based on surface analysis (internal URLs only).

---

## Required Before Merge

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| C1 | Refactor module-level `_load_chit_encode_content()` | Critical | Small |
| H1 | Add auth to `/metrics`, `/v1/preview/raw`, `/v1/evaluate` | High | Small |
| H2 | Remove hardcoded credential defaults | High | Small |
| H3 | Add Pydantic models + size caps to POST endpoints | High | Medium |
| H4 | Default feature flags to `false` | High | Trivial |

## Recommended Before Merge

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| M1 | Dockerfile hardening directives | Medium | Small |
| M3 | Rate limiting on gate endpoints | Medium | Small |
| M6 | Configurable agent_id in a2ui-renderer | Medium | Trivial |

## Deferred (Next Sprint)

| # | Finding | Severity |
|---|---------|----------|
| M2 | StaticFiles mount scope restriction | Medium |
| M4 | Deduplicate stopword lists | Medium |
| M5 | Deduplicate `_compact()` | Medium |
| M7 | Channel-monitor NATS reconnection | Medium |
| M8 | CHANNEL_MONITOR_SECRET fail-fast | Medium |
| L1-L4 | All low/nit findings | Low |
| H5 | PR size process improvement | High (process) |
