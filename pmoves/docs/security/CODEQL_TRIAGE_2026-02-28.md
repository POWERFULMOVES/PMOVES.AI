# CodeQL Alert Triage Report — 2026-02-28

**Total open alerts:** 43
**Triaged by:** Claude Code CLI (Opus 4.6)
**Scan date:** 2026-02-27 (latest CodeQL run)
**Triage date:** 2026-02-28

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| Critical (fix now) | 4 | External-facing services with exploitable findings |
| High (fix soon) | 6 | Internal services with real but lower-risk findings |
| Medium (track) | 5 | Tools, scripts, CI — accepted risk or needs minor hardening |
| Low / False Positive | 28 | Existing guards are sufficient; CodeQL cannot trace sanitizers |

---

## Critical — Fix Now

These alerts affect services exposed to external traffic where the finding represents a real or partially-real vulnerability.

### Alert #170 — `js/path-injection` — a2ui-renderer path injection via unsanitized `format` query param
- **File:** `pmoves/services/a2ui-renderer/src/index.ts` line 151
- **Rule:** Uncontrolled data used in path expression
- **Context:** `uploadToMinIO(filePath, ...)` receives `outputFile` which is constructed as `path.join(tmpDir, \`render.${format}\`)`. The `format` variable comes directly from `req.query.format` without validation against an allowlist.
- **Existing guards:** None on `format`. The `tmpDir` is from `mkdtempSync` which limits scope, but `format` could contain path separators.
- **Verdict:** REAL — partial path injection possible.
- **Fix:** Add format allowlist at the top of the `/render` handler:
  ```typescript
  const ALLOWED_FORMATS = new Set(['mp4', 'gif', 'webm']);
  if (!ALLOWED_FORMATS.has(format)) {
    return res.status(400).json({ ok: false, error: 'Unsupported format' });
  }
  ```

### Alert #68 — `py/stack-trace-exposure` — Gateway workflow.py leaks exception details
- **File:** `pmoves/services/gateway/gateway/api/workflow.py` line 191
- **Rule:** Information exposure through an exception
- **Context:** Line 162: `playback = {"error": str(exc)}` exposes raw exception strings from the Jellyfin bridge call. This object is included in the `manifest` returned to the client at line 191.
- **Existing guards:** None — `str(exc)` is included verbatim in the HTTP response body.
- **Verdict:** REAL — internal exception details (potentially hostnames, connection errors, stack info) leak to external callers.
- **Fix:** Replace `str(exc)` with a generic message:
  ```python
  playback = {"error": "playback_lookup_failed"}
  ```

### Alerts #171, #172, #173, #174 — `js/missing-rate-limiting` — a2ui-renderer endpoints lack rate limiting
- **Files:** `pmoves/services/a2ui-renderer/src/index.ts` lines 201, 303, 311, 408
- **Rule:** Missing rate limiting on routes performing authorization and file system access
- **Context:** `/render` and `/render/chart` endpoints perform CPU-intensive Remotion rendering + MinIO uploads. Both require `requireAuth` middleware but have no rate limiting.
- **Existing guards:** JWT auth only. No `express-rate-limit` or equivalent.
- **Verdict:** REAL — authenticated users can trigger unbounded rendering workload.
- **Fix:** Add `express-rate-limit` middleware to the `/render` and `/render/chart` endpoints (e.g., 10 requests/minute per IP).

**Critical alert count: 4 unique findings (6 alert numbers: #68, #170, #171, #172, #173, #174)**

---

## High — Fix Soon

These alerts affect internal services with real findings, but the services are not directly exposed to external traffic.

### Alert #60 — `py/stack-trace-exposure` — SupaSerch leaks chained exception
- **File:** `pmoves/services/supaserch/app.py` line 539 (endpoint at line 546)
- **Rule:** Information exposure through an exception
- **Context:** `raise HTTPException(status_code=500, detail="pipeline_error") from exc` — the `from exc` chains the original exception. Depending on the FastAPI error handler configuration, the chained exception traceback may be included in debug responses.
- **Existing guards:** The `detail` string itself is generic ("pipeline_error"), but `from exc` preserves the chain.
- **Verdict:** REAL (low confidence) — FastAPI's default production handler strips chained exceptions, but custom exception handlers may expose them.
- **Fix:** Change to `from None` to suppress exception chaining:
  ```python
  raise HTTPException(status_code=500, detail="pipeline_error") from None
  ```

### Alert #163 — `py/stack-trace-exposure` — showtime-api SSE stream
- **File:** `pmoves/services/showtime-api/app.py` line 189
- **Rule:** Information exposure through an exception
- **Context:** `logger.exception("SSE stream error")` logs the traceback server-side, and the client receives `{"error": "stream interrupted"}` (generic). CodeQL traces the exception flow from the `except` block through the StreamingResponse.
- **Existing guards:** Client-facing error message is generic on line 184.
- **Verdict:** LIKELY FALSE POSITIVE — the client receives only the generic string, not the traceback. The `logger.exception` is server-side only. However, verify that the StreamingResponse generator does not leak exception details if the generator itself raises.
- **Fix (defensive):** Wrap the entire generator in a secondary try/except that yields only the generic error.

### Alert #168 — `py/clear-text-logging-sensitive-data` — flute-gateway logs NATS URL
- **File:** `pmoves/services/flute-gateway/main.py` line 363
- **Rule:** Clear-text logging of sensitive information
- **Context:** `logger.info("Connected to NATS at %s", NATS_URL_REDACTED)` — the variable is `NATS_URL_REDACTED` which uses `_redact_url_password()` to mask the password portion. CodeQL traces from `_build_nats_url()` (which reads `NATS_PASSWORD` secret) through to the logger call, but does not recognize the redaction function.
- **Existing guards:** `_redact_url_password()` replaces the password with `<redacted>` before logging.
- **Verdict:** FALSE POSITIVE — password is redacted before logging. However, the function also logs `NATS_URL` (unredacted) in other paths that CodeQL may be tracing.
- **Fix (defensive):** Audit all `logger.*` calls in the file to ensure none use the unredacted `NATS_URL`. Add a `# nosec` or CodeQL suppression comment at line 363.

### Alerts #82, #150, #151 — `py/stack-trace-exposure` — consciousness-service exception exposure
- **Files:** `pmoves/services/consciousness-service/main.py` lines 138, 158, 175-180
- **Rule:** Information exposure through an exception
- **Context:** All three endpoints (`/cgp/generate`, `/cgp/publish`, `/cgp/batch`) use `raise HTTPException(...) from None` which suppresses exception chaining. The `logger.error(..., exc_info=True)` logs the full traceback server-side only.
- **Existing guards:** `from None` on all three raise statements. Client receives only generic error messages.
- **Verdict:** FALSE POSITIVE — `from None` suppresses the traceback chain. CodeQL is tracing the `exc_info=True` in the logger call but that goes to server logs, not to the HTTP response.
- **Fix:** Add CodeQL suppression comments. No code change needed.

**High alert count: 6 unique findings (alert numbers: #60, #82, #150, #151, #163, #168)**

---

## Medium — Track

These alerts affect developer tools, CI scripts, or non-service code where the risk is accepted or minimal.

### Alert #176 — `py/clear-text-logging-sensitive-data` — chit_credential_demo.py
- **File:** `pmoves/tools/chit_credential_demo.py` line 122
- **Rule:** Clear-text logging of sensitive information
- **Context:** `val = secrets[key]` assigns the decoded secret to a variable, but the next line prints `f"  {key} = ****"` (masked). The `val` variable is never used.
- **Existing guards:** Output is masked on line 122. The `val` variable is dead code.
- **Verdict:** FALSE POSITIVE in practice — the value is never printed or logged. However, the unused variable creates unnecessary taint.
- **Fix:** Remove the unused assignment: change `val = secrets[key]` to just iterate over `sorted(secrets)` without assignment, or use `_` as the variable name.

### Alerts #166, #167 — `py/clear-text-storage-sensitive-data` — Supabase env scripts
- **Files:**
  - `pmoves/scripts/supabase/apply_env_profile.py` line 45
  - `pmoves/scripts/supabase/runtime_env_bridge.py` line 32
- **Rule:** Clear-text storage of sensitive information
- **Context:** Both scripts write environment variable files (`env.*`) to disk. This is their intended purpose — they bridge Supabase runtime config to Docker env files.
- **Existing guards:** Files written to project-local paths. `.gitignore` excludes generated env files.
- **Verdict:** ACCEPTED RISK — by design. These are CI/dev helper scripts that must write secrets to env files for Docker consumption.
- **Fix:** Add CodeQL suppression comments. Document the accepted risk.

### Alert #169 — `actions/missing-workflow-permissions` — integrations-ghcr.yml
- **File:** `.github/workflows/integrations-ghcr.yml` line 65-105 (resolve-matrix job)
- **Rule:** Workflow does not contain permissions
- **Context:** The `resolve-matrix` job lacks an explicit `permissions` block. It only does `actions/checkout@v4` and writes outputs. The `build-publish` job has proper permissions.
- **Existing guards:** The job only reads files and sets outputs. No writes to packages/contents.
- **Verdict:** REAL (low severity) — missing least-privilege declaration.
- **Fix:** Add `permissions: { contents: read }` to the `resolve-matrix` job.

### Alert #165 — `js/tainted-format-string` — Jellyfin AI API gateway
- **File:** `CATACLYSM_STUDIOS_INC/L4-PLATFORM/provisions/docker-stacks/jellyfin-ai/api-gateway/server.js` line 524
- **Rule:** Use of externally-controlled format string
- **Context:** `` console.error(`Error fetching ${service} logs:`, error) `` where `service` comes from `req.params.service`. Template literals in JavaScript are not vulnerable to format string attacks (unlike C's printf). This is a server-side log message only.
- **Existing guards:** Template literal — not a printf-style format string.
- **Verdict:** FALSE POSITIVE — JavaScript template literals do not process format specifiers. The `service` value is interpolated as a string, not interpreted as a format directive.
- **Fix:** None needed. Add suppression comment if desired.

**Medium alert count: 5 unique findings (alert numbers: #165, #166, #167, #169, #176)**

---

## Low / False Positive — 28 Alerts

All alerts below have existing guards that CodeQL cannot trace through custom sanitizer functions. Each has been verified against the source code.

### Alerts #190, #191 — `py/full-ssrf` — Hi-RAG Gateway v1 & v2 image fetch

| Alert | File | Line |
|-------|------|------|
| #191 | `pmoves/services/hi-rag-gateway/gateway.py` | 593 |
| #190 | `pmoves/services/hi-rag-gateway-v2/app.py` | 1371 |

- **Rule:** Full server-side request forgery
- **Context:** Both gateways have `_fetch_remote_image()` which:
  1. Calls `_validate_remote_image_url()` — checks scheme allowlist (http/https only), rejects credentials in URL, validates against `CHIT_IMAGE_FETCH_ALLOWED_HOSTS` allowlist
  2. Resolves DNS once via `socket.getaddrinfo()`
  3. Validates all resolved IPs against private ranges (`is_private`, `is_loopback`, `is_link_local`, `is_multicast`, `is_reserved`, `is_unspecified`)
  4. Connects directly to validated IP via `urllib3` (no second DNS lookup — prevents DNS rebinding)
  5. Sets `redirect=False` — blocks redirect-based SSRF
- **Existing guards:** Comprehensive SSRF defense including DNS rebinding prevention, IP allowlisting, redirect blocking, and host allowlist.
- **Verdict:** FALSE POSITIVE — CodeQL cannot trace through the multi-step validation pipeline.

### Alerts #44, #46, #49, #51, #183, #184, #185, #186, #187, #188, #189 — `py/path-injection` — pmoves-yt file paths (11 alerts)

| Alert | File | Line | Operation |
|-------|------|------|-----------|
| #44 | `pmoves/services/pmoves-yt/yt.py` | 1444 | `shutil.rmtree(vid_dir)` |
| #46 | same | 1529 | `shutil.rmtree(vid_dir)` |
| #49 | same | 1586 | `shutil.rmtree(vid_dir)` |
| #51 | same | 1666 | `shutil.rmtree(vid_dir)` |
| #183 | same | 1434 | `vid_dir = YT_TEMP_ROOT / video_id` |
| #184 | same | 1439 | `open(tmp_path, "wb")` |
| #185 | same | 1460 | `open(thumb_path, "wb")` |
| #186 | same | 1576 | `vid_dir = YT_TEMP_ROOT / video_id` |
| #187 | same | 1581 | `open(tmp_path, "wb")` |
| #188 | same | 1600 | `open(thumb_path, "wb")` |
| #189 | same | 1780 | `archive_path.parent.mkdir()` |

- **Rule:** Uncontrolled data used in path expression
- **Context:** All `video_id` values pass through `_safe_video_id()` which:
  1. Applies `os.path.basename()` to strip directory components
  2. Validates `safe == vid` (rejects any basename != original, catching `/` and `..`)
  3. Matches against `_SAFE_VID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")`
  4. Raises `HTTPException(400)` on any failure

  Alert #189 (archive path) uses `os.path.basename(archive_path_value)` with a fallback to "download-archive.txt" if empty. The result is joined to `YT_ARCHIVE_DIR` (a constant).
- **Existing guards:** `os.path.basename` + strict regex allowlist on all paths.
- **Verdict:** FALSE POSITIVE — CodeQL cannot trace taint through the `_safe_video_id()` sanitizer.

### Alerts #156, #177, #178 — `py/path-injection` — Gateway chit.py codebook paths (3 alerts)

| Alert | File | Line |
|-------|------|------|
| #156 | `pmoves/services/gateway/gateway/api/chit.py` | 254 |
| #177 | same | 261 |
| #178 | same | 263 |

- **Rule:** Uncontrolled data used in path expression
- **Context:** `_load_codebook(codebook_path)` sanitizes `codebook_path` with:
  1. `os.path.basename(codebook_path)` — strips directory components
  2. `_SAFE_FILENAME.match(safe_name)` — validates against `r"^[a-zA-Z0-9_\-]+\.jsonl?$"`
  3. `resolved.is_relative_to(codebook_dir.resolve())` — prevents traversal
- **Existing guards:** Three-layer sanitization (basename + regex + relative-to check).
- **Verdict:** FALSE POSITIVE — code comments explicitly document the CodeQL suppression rationale.

### Alerts #157, #158, #160, #161, #181, #182 — `py/path-injection` — Gateway viz.py shape paths (6 alerts)

| Alert | File | Line |
|-------|------|------|
| #157 | `pmoves/services/gateway/gateway/api/viz.py` | 112 |
| #158 | same | 115 |
| #160 | same | 201 |
| #161 | same | 204 |
| #181 | same | 117 |
| #182 | same | 206 |

- **Rule:** Uncontrolled data used in path expression
- **Context:** `shape_svg()` and `shape_constellations()` sanitize `shape_id` with:
  1. `os.path.basename(shape_id)` — strips directory components
  2. `safe_id != shape_id` check — rejects any input where basename differs from original
  3. `_SAFE_SHAPE_RE.match(safe_id)` — validates against `r"^[a-zA-Z0-9._-]+$"`
  4. `resolved.is_relative_to(DATA_DIR)` — prevents path traversal beyond data directory
- **Existing guards:** Four-layer sanitization with code comments documenting CodeQL rationale.
- **Verdict:** FALSE POSITIVE.

### Alerts #179, #180 — `py/path-injection` — HF MCP server model paths (2 alerts)

| Alert | File | Line |
|-------|------|------|
| #179 | `pmoves/services/hf-mcp-server/main.py` | 548 |
| #180 | same | 656 |

- **Rule:** Uncontrolled data used in path expression
- **Context:** `_safe_model_path(model_id)` sanitizes with:
  1. Rejects `..` in model_id
  2. Validates against `_SAFE_MODEL_RE` regex
  3. Replaces `/` with `--` and validates `os.path.basename(sanitized) == sanitized`
  4. Returns `MODELS_BASE / safe_name` (rooted to constant base dir)
- **Existing guards:** Multi-layer sanitization with path traversal prevention.
- **Verdict:** FALSE POSITIVE.

### Alert #152 — `js/xss-through-dom` — Gateway client.html DOM manipulation
- **File:** `pmoves/services/gateway/web/client.html` line 70
- **Rule:** DOM text reinterpreted as HTML
- **Context:** `a.href = href` where `href` is constructed from `shapeId`. The `shapeId` is validated on line 60 with `/^[0-9a-f]{1,64}$/` (hex-only) and then `encodeURIComponent`'d. The code uses `document.createElement("a")` and `.textContent` (safe DOM API), not `.innerHTML`.
- **Existing guards:** Hex-only regex + encodeURIComponent + safe DOM APIs.
- **Verdict:** FALSE POSITIVE — no HTML injection possible with hex-validated, URL-encoded values assigned via DOM element properties.

### Alert #175 — `js/resource-exhaustion` — serviceHealth.ts timeout
- **File:** `pmoves/ui/lib/serviceHealth.ts` line 56
- **Rule:** Resource exhaustion via user-controlled timer duration
- **Context:** `setTimeout(() => controller.abort(), safeTimeout)` where `safeTimeout` is clamped to `[1000, 60000]` via `Math.min(Math.max(timeout, 1000), 60_000)` on line 54.
- **Existing guards:** Hard bounds at 1-60 seconds.
- **Verdict:** FALSE POSITIVE — timeout is clamped to safe range.

**Low/FP alert count: 28 (alert numbers: #44, #46, #49, #51, #152, #156, #157, #158, #160, #161, #175, #179, #180, #181, #182, #183, #184, #185, #186, #187, #188, #189, #190, #191, #177, #178, #150, #151)**

---

## Recommended Actions

### Immediate (P1 — this sprint)

1. **a2ui-renderer format validation** (#170): Add `ALLOWED_FORMATS` allowlist to `/render` endpoint.
2. **a2ui-renderer rate limiting** (#171-174): Add `express-rate-limit` to `/render` and `/render/chart`.
3. **Gateway workflow.py exception masking** (#68): Replace `str(exc)` with generic error string in playback fallback.

### Soon (P2 — next sprint)

4. **SupaSerch exception chaining** (#60): Change `from exc` to `from None`.
5. **CI workflow permissions** (#169): Add `permissions: { contents: read }` to `resolve-matrix` job.
6. **flute-gateway log audit** (#168): Verify all logger calls use `NATS_URL_REDACTED`, add suppression comment.

### Backlog (P3 — when convenient)

7. **chit_credential_demo.py dead variable** (#176): Remove unused `val = secrets[key]`.
8. **Supabase env scripts** (#166, #167): Add suppression comments documenting accepted risk.
9. **Consciousness-service** (#82, #150, #151): Add suppression comments — `from None` already guards.
10. **showtime-api** (#163): Add secondary try/except in SSE generator for defense in depth.

### No Action Required (suppress when ready)

All 28 Low/FP alerts can be suppressed with CodeQL `# codeql[py/...]` or `// codeql[js/...]` inline comments, or via `.github/codeql-config.yml` path exclusions for the Jellyfin AI gateway (#165) which is in a separate product tree.

---

## CodeQL Suppression Strategy

For the 28 false positives, the recommended approach is to use inline suppression comments that document the rationale:

**Python pattern:**
```python
result = open(path, "r")  # CodeQL: path-injection — sanitized by _safe_video_id (basename + regex allowlist)
```

**JavaScript pattern:**
```javascript
a.href = href; // CodeQL: xss-through-dom — shapeId validated by /^[0-9a-f]{1,64}$/ + encodeURIComponent
```

Many of these comments already exist in the codebase (visible in the code review above). CodeQL does not honor inline comments for suppression — use the GitHub UI's "Dismiss alert" feature with "Used in tests" or "False positive" reason, or configure query exclusions in `.github/codeql-config.yml`.

---

## Appendix: Full Alert Index

| # | Severity | Rule | File | Line | Verdict |
|---|----------|------|------|------|---------|
| 44 | error | py/path-injection | pmoves-yt/yt.py | 1444 | FP — _safe_video_id guard |
| 46 | error | py/path-injection | pmoves-yt/yt.py | 1529 | FP — _safe_video_id guard |
| 49 | error | py/path-injection | pmoves-yt/yt.py | 1586 | FP — _safe_video_id guard |
| 51 | error | py/path-injection | pmoves-yt/yt.py | 1666 | FP — _safe_video_id guard |
| 60 | error | py/stack-trace-exposure | supaserch/app.py | 539 | REAL — `from exc` leaks chain |
| 68 | error | py/stack-trace-exposure | gateway/workflow.py | 191 | REAL — `str(exc)` in response |
| 82 | error | py/stack-trace-exposure | consciousness-service/main.py | 175 | FP — `from None` guards |
| 150 | error | py/stack-trace-exposure | consciousness-service/main.py | 138 | FP — `from None` guards |
| 151 | error | py/stack-trace-exposure | consciousness-service/main.py | 158 | FP — `from None` guards |
| 152 | warning | js/xss-through-dom | gateway/web/client.html | 70 | FP — hex regex + safe DOM APIs |
| 156 | error | py/path-injection | gateway/chit.py | 254 | FP — basename+regex+relative-to |
| 157 | error | py/path-injection | gateway/viz.py | 112 | FP — basename+regex+relative-to |
| 158 | error | py/path-injection | gateway/viz.py | 115 | FP — basename+regex+relative-to |
| 160 | error | py/path-injection | gateway/viz.py | 201 | FP — basename+regex+relative-to |
| 161 | error | py/path-injection | gateway/viz.py | 204 | FP — basename+regex+relative-to |
| 163 | error | py/stack-trace-exposure | showtime-api/app.py | 189 | LIKELY FP — generic client msg |
| 165 | warning | js/tainted-format-string | jellyfin-ai/server.js | 524 | FP — JS template literal |
| 166 | error | py/clear-text-storage | supabase/apply_env_profile.py | 45 | ACCEPTED — by design |
| 167 | error | py/clear-text-storage | supabase/runtime_env_bridge.py | 32 | ACCEPTED — by design |
| 168 | error | py/clear-text-logging | flute-gateway/main.py | 363 | FP — NATS_URL_REDACTED used |
| 169 | warning | actions/missing-perms | integrations-ghcr.yml | 65 | REAL — add permissions block |
| 170 | error | js/path-injection | a2ui-renderer/index.ts | 151 | REAL — format not validated |
| 171 | warning | js/missing-rate-limiting | a2ui-renderer/index.ts | 201 | REAL — no rate limit |
| 172 | warning | js/missing-rate-limiting | a2ui-renderer/index.ts | 201 | REAL — no rate limit |
| 173 | warning | js/missing-rate-limiting | a2ui-renderer/index.ts | 311 | REAL — no rate limit |
| 174 | warning | js/missing-rate-limiting | a2ui-renderer/index.ts | 311 | REAL — no rate limit |
| 175 | warning | js/resource-exhaustion | ui/serviceHealth.ts | 56 | FP — clamped to [1s, 60s] |
| 176 | error | py/clear-text-logging | chit_credential_demo.py | 122 | FP — value masked in output |
| 177 | error | py/path-injection | gateway/chit.py | 261 | FP — basename+regex+relative-to |
| 178 | error | py/path-injection | gateway/chit.py | 263 | FP — basename+regex+relative-to |
| 179 | error | py/path-injection | hf-mcp-server/main.py | 548 | FP — _safe_model_path guard |
| 180 | error | py/path-injection | hf-mcp-server/main.py | 656 | FP — _safe_model_path guard |
| 181 | error | py/path-injection | gateway/viz.py | 117 | FP — basename+regex+relative-to |
| 182 | error | py/path-injection | gateway/viz.py | 206 | FP — basename+regex+relative-to |
| 183 | error | py/path-injection | pmoves-yt/yt.py | 1434 | FP — _safe_video_id guard |
| 184 | error | py/path-injection | pmoves-yt/yt.py | 1439 | FP — _safe_video_id guard |
| 185 | error | py/path-injection | pmoves-yt/yt.py | 1460 | FP — _safe_video_id guard |
| 186 | error | py/path-injection | pmoves-yt/yt.py | 1576 | FP — _safe_video_id guard |
| 187 | error | py/path-injection | pmoves-yt/yt.py | 1581 | FP — _safe_video_id guard |
| 188 | error | py/path-injection | pmoves-yt/yt.py | 1600 | FP — _safe_video_id guard |
| 189 | error | py/path-injection | pmoves-yt/yt.py | 1780 | FP — basename + fallback |
| 190 | error | py/full-ssrf | hi-rag-gateway-v2/app.py | 1371 | FP — full SSRF defense |
| 191 | error | py/full-ssrf | hi-rag-gateway/gateway.py | 593 | FP — full SSRF defense |
