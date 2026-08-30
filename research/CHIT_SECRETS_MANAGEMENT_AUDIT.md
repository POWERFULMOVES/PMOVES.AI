# CHIT Secrets Management & Tooling Audit — Full Scope

**Date:** 2026-04-17
**Auditor:** Security Auditor (Agent Zero)
**Scope:** All CHIT tooling — manifests, API specs, contract checks, secrets management, integration verification, GRAPHITI signatures
**Prior Research:** part2_chit_code_analysis.md (3 critical crypto bugs, 17 files)
**Classification:** CONFIDENTIAL — Security Audit

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **P0 — Block Release** | 9 | Encryption fraud, silent bypass, false audit claims, SSH key in env, hardcoded creds, doc lies |
| **P1 — Fix Before Release** | 9 | KDF/format mismatch, duplicate canon(), zero crypto tests, key reuse, secret tier leakage |
| **P2 — Current Sprint** | 7 | Missing vault, structural-only CI, weak defaults, incomplete schema, 111 unauthed NATS refs |
| **P3 — Next Sprint** | 4 | Documentation drift, missing OpenAPI, YAML lint gaps, SSH key categorization |

**Overall Assessment:** CHIT presents itself as an encryption/signing system ("AES-256 encryption", "HMAC-SHA256 signatures"). In reality, the secrets codec (`pmoves/chit/__init__.py`) is base16 hex encoding — trivially reversible, NOT encryption. The crypto module (`chit_security.py`) has 3 critical implementation bugs making it non-functional for cross-module use. Contract enforcement is structural-only (ripgrep for keywords, not crypto verification). The hardening tracker falsely claims 5 services have "Full" CHIT integration when zero services actually call `sign_cgp()` or `verify_cgp()`. GRAPHITI "signatures" are plaintext attribution strings, not cryptographic signatures.

---

## Findings

### SECTION 1: CHIT Manifest and API Spec

#### [P0] F-01: `signature.v1.schema.json` Has Zero Cryptographic Fields
- **Location:** `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json:1-95`
- **Description:** Schema titled "Agent Graphiti Signature" requires `agent_id`, `glyph`, `color`, `phase`, `timestamp`, `summary` — but contains NO fields for `signature_hash`, `public_key`, `algorithm`, `key_id`, or any cryptographic proof. It is an **attribution format**, not a signature format.
- **Impact:** Any system validating against this schema accepts forged attribution blocks. An attacker sets any `agent_id` with any `summary` and passes validation.
- **PoC:** `echo '{"agent_id":"attacker","glyph":"\u26a1","color":"#FF0000","phase":"Phase H","timestamp":"2026-04-17T00:00:00Z","summary":"pwned"}'` passes schema validation.
- **Recommendation:** Add required fields: `signature_algorithm` (enum), `signature_hash` (base64), `signing_key_id`, `payload_hash`. Validate HMAC/Ed25519 signature over canonical JSON.

#### [P1] F-02: No CHIT OpenAPI/Swagger Specification Exists
- **Location:** `pmoves/contracts/` (50+ schema files, zero CHIT API specs)
- **Description:** Searched `openapi`, `swagger`, `api_spec` near `chit/contracts/` — zero results. `CHIT_GATEWAY_API.md` is Markdown, not machine-validatable OpenAPI. 50+ NATS event schemas exist but NO CHIT endpoint request/response schemas.
- **Impact:** No automated contract testing for CHIT API endpoints. Breaking changes undetected.
- **Recommendation:** Create `pmoves/contracts/schemas/chit/geometry-event.v1.schema.json` etc. Generate OpenAPI from FastAPI app. Add to CI.

#### [P2] F-03: secrets_manifest_v2.yaml Has No Integrity Check
- **Location:** `pmoves/chit/secrets_manifest_v2.yaml:1-3`
- **Description:** Manifest has `version: 2`, `tier_layout: true`, `github_sync: true`, `docker_secrets: true` but NO `checksum`, `signature`, or `hash` field. Anyone with repo write access can modify entries undetected.
- **Impact:** Manifest tampering routes secrets to unauthorized targets or removes `required` flags.
- **Recommendation:** Add `manifest_hash: sha256:...` field. Verify in `apply_manifest_v2()` before processing.

#### [P3] F-04: Manifest V1 and V2 Coexist Without Migration Path
- **Location:** `pmoves/chit/secrets_manifest.yaml` (V1, 80 entries), `pmoves/chit/secrets_manifest_v2.yaml` (V2, 100+ entries)
- **Description:** Both reference same `cgp_file: pmoves/data/chit/env.cgp.json`. V2 adds `github_secret`/`docker_secret` targets. No migration script, no deprecation notice.
- **Recommendation:** Delete V1. Add deprecation comment. Validate V2 superset of V1 in CI.

---

### SECTION 2: CHIT Contract Checks

#### [P0] F-05: `chit-contract.yml` Is Structural-Only — Never Verifies Crypto
- **Location:** `.github/workflows/chit-contract.yml:40-90`
- **Description:** CI uses ripgrep to check: SQL table defs exist, FastAPI decorator patterns match, `geometry.cgp.v1` string appears, env var names appear. **It NEVER**: calls `sign_cgp()`, calls `verify_cgp()`, checks HMAC output, checks AES-GCM round-trip, validates KDF params, or runs crypto tests.
- **Impact:** Code passes all CHIT contract checks with completely broken crypto. Changing `PBKDF2_HMAC_SHA256_ITERATIONS = 1` passes CI.
- **PoC:** Modify KDF iterations to 1 in `chit_security.py` — `chit-contract.yml` passes because it only checks the string `CHIT_PASSPHRASE` exists.
- **Recommendation:** Add `crypto-verify` job: sign+verify round-trip, encrypt+decrypt round-trip, tampered payload rejection, run with `CHIT_REQUIRE_SIGNATURE=true`. Gate PR merge.

#### [P0] F-06: `pre-tool.sh` Has Zero CHIT Enforcement
- **Location:** `.claude/hooks/pre-tool.sh:12-24`
- **Description:** Blocks 11 patterns (`rm -rf /`, `DROP DATABASE`, etc.) but NO CHIT checks. Does not verify unsigned CGP payloads, missing signatures, unencrypted anchors, or CHIT_PASSPHRASE presence.
- **Impact:** AI agents generate/process unsigned CGP payloads without hook intervention.
- **Recommendation:** Add CHIT validation: reject CGP payloads with `"sig": null` or missing signature fields.

#### [P0] F-07: `chit_security_validator.py` Silently Bypasses Signature Verification
- **Location:** `pmoves/tools/chit_security_validator.py:42-48`
- **Description:** `try: from pmoves.tools.chit_security import verify_cgp, decrypt_anchors` with `except ImportError: verify_cgp = None`. When `verify_cgp` is `None`, validator SKIPS signature checks — no error, no warning, no logging.
- **Impact:** Complete bypass of signature verification. Any malformed/tampered/unsigned payload passes.
- **PoC:** `PYTHONPATH=/dev/null python -c "from pmoves.tools.chit_security_validator import validate_cgp"` — if import fails, validator silently degrades.
- **Recommendation:** Fail-closed: `except ImportError as e: raise RuntimeError(f"CHIT security module unavailable: {e}") from e`.

#### [P1] F-08: `CHIT_REQUIRE_SIGNATURE` Defaults `true` But Enforcement Is Illusory
- **Location:** `pmoves/docker-compose.agents.yml:41,268,348,430,544,818`
- **Description:** Six agent services set `CHIT_REQUIRE_SIGNATURE=${CHIT_PROD_REQUIRE_SIGNATURE:-true}`. Actual enforcement depends on `chit_security_validator.py` which silently degrades (F-07). The env var is READ but its effect is NULL when validator cannot import `verify_cgp`.
- **Impact:** Operators believe signatures enforced (`true` default) but they are not. False sense of security.
- **Recommendation:** Fix F-07. Add startup check: verify `verify_cgp is not None` when `CHIT_REQUIRE_SIGNATURE=true`, exit with error if unavailable.

#### [P2] F-09: `validate_cgp.py` in health-wger Is Schema-Only, Not Crypto
- **Location:** `pmoves/integrations/health-wger/tools/validate_cgp.py:41`
- **Description:** `validate_cgp()` validates JSON schema (required fields, types, enums) but NOT HMAC signatures or anchor decryption. Tests only cover schema validation.
- **Impact:** Valid-schema but invalid-signature payloads accepted.
- **Recommendation:** Add crypto validation after schema check. Call `verify_cgp()` when `CHIT_REQUIRE_SIGNATURE=true`.

---

### SECTION 3: Secrets Management Integration

#### [P0] F-10: `chit/__init__.py` Is Base16 Hex Encoding — NOT Encryption
- **Location:** `pmoves/chit/__init__.py:72-78`
- **Description:** `_hex_encode()` uses `base64.b16encode(value.encode()).decode()`. `_hex_decode()` uses `base64.b16decode()`. Trivially reversible — NOT encryption. Default `include_cleartext=True` (line 95) stores **plaintext** in CGP payloads. CodeQL suppression at line 49 says "CGP by-design encodes secrets" — deliberate suppression of a correct alert.
- **Impact:** Anyone with `env.cgp.json` or any CGP file trivially decodes ALL 100+ secrets (API keys, DB passwords, JWT secrets, SSH keys).
- **PoC:** `python -c "import base64; print(base64.b16decode('414243'.encode()).decode())"` -> `ABC`. No passphrase, no key, no algorithm.
- **Recommendation:** Either (A) remove encryption claims and document as obfuscation-only, or (B) implement actual encryption (AES-256-GCM with per-secret IVs, KDF from CHIT_PASSPHRASE). Remove CodeQL suppression until real encryption exists.

#### [P0] F-11: `sync_common_credentials()` Hardcodes `POSTGRES_PASSWORD=changeme`
- **Location:** `pmoves/chit/__init__.py:219-230`
- **Description:** Injects defaults into 6 tier env files: `POSTGRES_PASSWORD: changeme`, `MINIO_SECRET_KEY: minioadmin`, `NEO4J_PASSWORD: changeme`, `PGRST_DB_URI: postgres://pmoves:changeme@postgres:5432/pmoves`. `apply_manifest_v2()` calls this unconditionally (line 306).
- **Impact:** Every `apply_manifest_v2()` call injects weak defaults if tier files do not exist. `PGRST_DB_URI` contains password in connection string.
- **PoC:** Delete `env.tier-data`, run `apply_manifest_v2()` — recreated with `POSTGRES_PASSWORD=changeme`.
- **Recommendation:** Remove hardcoded defaults. Never write passwords from code. Use `.gitignore`d template files for local dev.

#### [P0] F-12: SSH Private Key Stored as Environment Variable
- **Location:** `pmoves/chit/secrets_manifest_v2.yaml` (entry `hostinger_ssh_private_key`), `pmoves/chit/secrets_categorization.yaml:48`
- **Description:** `HOSTINGER_SSH_PRIVATE_KEY` stored in: (1) `env.cgp.json` (cleartext CGP), (2) `.env.generated`, (3) `env.tier-agent`, (4) GitHub Secrets, (5) Docker Secrets file. SSH keys in env vars violate best practices — contain newlines, prone to shell escaping, logged by process managers.
- **Impact:** SSH key exposure in logs, process listings, `docker inspect`, GitHub Secrets UI, env var dumps.
- **Recommendation:** Use SSH agent forwarding or file-based Docker secrets. Remove from CGP manifest. Store only public key in env.

#### [P0] F-13: CHIT Documentation Falsely Claims AES-256 Encryption
- **Location:** `pmoves/docs/operations/ENVIRONMENT_SETUP.md:86` ("CHIT encryption passphrase"), `pmoves/docs/PMOVESCHIT/CHIT_GATEWAY_API.md:63` ("AES-GCM anchor encryption"), `pmoves/docs/operations/SMOKETESTS.md:430` ("AES-GCM encrypt constellation anchors"), `pmoves/chit/codec.py:1` ("encoding/decoding of environment secrets")
- **Description:** Multiple docs claim "AES-256 encryption" for secrets. Actual implementation uses base16 hex encoding. AES-GCM exists ONLY in `chit_security.py` for anchor vectors (3D float arrays), NOT for secret values. CODEX system prompt lists "Add HMAC sign/verify" and "Add AES-GCM encrypt/decrypt" as CHECKLIST ITEMS (design goals), not existing features.
- **Impact:** Operators believe secrets encrypted at rest when trivially reversible. Documentation security lie.
- **Recommendation:** Correct ALL docs: (1) Secret values: base16 hex encoding (obfuscation, not encryption), (2) Anchor vectors: AES-GCM (when chit_security.py works). Add "Security Limitations" section.

#### [P1] F-14: CHIT_PASSPHRASE Used for Both Signing AND Encryption (Key Separation Violation)
- **Location:** `pmoves/tools/chit_security.py` (sign_cgp + encrypt_anchors), `pmoves/chit/secrets_manifest_v2.yaml` (entry `chit_passphrase`)
- **Description:** Single passphrase for: (1) HMAC-SHA256 signing key, (2) KDF input for AES-GCM anchor encryption, (3) enrollment token signing. NIST SP 800-57 requires key separation.
- **Impact:** Passphrase compromise for signing breaks anchor encryption and vice versa.
- **Recommendation:** Derive separate keys: `signing_key = HKDF(passphrase, info=b"chit-sign-v1")`, `encryption_key = HKDF(passphrase, info=b"chit-encrypt-v1")`.

#### [P1] F-15: CHIT_PASSPHRASE Mapped to Both Dev and Prod Aliases
- **Location:** `pmoves/chit/secrets_manifest_v2.yaml:664-676`
- **Description:** Entry `chit_passphrase` maps single CGP source `CHIT_PASSPHRASE` to BOTH `CHIT_PASSPHRASE` and `CHIT_PROD_PASSPHRASE`. Comment: "Routes CHIT_PASSPHRASE to both the dev name and the production alias." Dev and prod use SAME passphrase.
- **Impact:** Dev compromise immediately exposes prod passphrase. No environment key separation.
- **Recommendation:** Separate `CHIT_DEV_PASSPHRASE` and `CHIT_PROD_PASSPHRASE` as distinct CGP entries.

#### [P1] F-16: Secrets Replicated to 5 Locations Per Entry
- **Location:** `pmoves/chit/secrets_manifest_v2.yaml` (all V2 entries)
- **Description:** Each secret has up to 5 copies: (1) `env.cgp.json` (source), (2) `.env.generated`, (3) `env.tier-*`, (4) GitHub Secrets, (5) Docker Secrets file. No atomic rotation mechanism.
- **Impact:** Manual rotation across 5 locations. Missed location = stale credentials. Attack surface explosion.
- **Recommendation:** Single source of truth (vault or encrypted CGP). Derive all targets atomically. Add `last_rotated` timestamp.

#### [P1] F-17: SUPABASE_JWT_SECRET Accessible From Agent Tier
- **Location:** `pmoves/chit/secrets_manifest_v2.yaml` (entries `supabase_jwt_secret` tier:api, `supabase_realtime_secret` tier:agent)
- **Description:** `SUPABASE_REALTIME_SECRET` aliases `SUPABASE_JWT_SECRET` and is scoped to `tier: agent`. Same JWT signing secret in two tiers means agent services can forge JWT tokens.
- **Impact:** Agent tier services can forge JWTs. Violates least-privilege tier isolation.
- **Recommendation:** Remove `SUPABASE_REALTIME_SECRET` from agent tier. Realtime uses `SUPABASE_ANON_KEY` only.

#### [P2] F-18: No Vault Integration Exists
- **Location:** Entire codebase — searched `vault`, `hashicorp`, `aws_secrets`, `secrets_manager`, `azure_key_vault`
- **Description:** Zero vault integration. All secrets flow from single JSON file (`env.cgp.json`) through Python to env files to GitHub Secrets to Docker Secrets. No HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager.
- **Impact:** No centralized rotation, no access auditing, no dynamic secrets, no versioning. `env.cgp.json` compromise exposes all 100+ secrets.
- **Recommendation:** Evaluate HashiCorp Vault. Implement vault agent sidecar injection. Migrate CGP to vault transit encryption.

#### [P2] F-19: `env.cgp.json` Is Single Point of Failure
- **Location:** `pmoves/chit/secrets_manifest.yaml:3`, `pmoves/chit/secrets_manifest_v2.yaml:5`
- **Description:** Both manifests point to single CGP file for ALL secrets. No redundancy, no backup, no integrity verification.
- **Impact:** Single `rm` or corruption loses all secret mappings.
- **Recommendation:** Add integrity hash. Store backup in vault. Add CI validation check.

---

### SECTION 4: CHIT Integration Coverage Verification

#### [P0] F-20: Hardening Tracker Falsely Claims 5 Services Have "Full" CHIT Integration
- **Location:** `docs/hardening/PMOVES-hardening-tracker.md:234-240`
- **Description:** Tracker: "**Full** | 5 | Tokenism Simulator, Hi-RAG v2, Gateway, Neo4j Mind Map, Agent Zero". Grepped `sign_cgp|verify_cgp|chit_security` across ALL 5 directories — **zero results**:
  - `pmoves/services/tokenism-simulator/` — imports `CHITEncoder` (geometry encoding, NOT signing)
  - `pmoves/services/hi-rag/` — zero chit_security references
  - `pmoves/services/gateway/` — has `chit_sign.py` (duplicate crypto) but NO service code calls it
  - `pmoves/services/neo4j-mind-map/` — zero chit references
  - `pmoves/services/agent-zero/` — imports `CGP_SPEC_VERSION` string constant only
- **Impact:** Security document operators rely on for release decisions contains false claims. False security posture.
- **PoC:** `grep -rn 'sign_cgp\|verify_cgp\|chit_security' pmoves/services/tokenism-simulator/ pmoves/services/hi-rag/ pmoves/services/gateway/ pmoves/services/neo4j-mind-map/ pmoves/services/agent-zero/ --include='*.py'` -> empty output.
- **Recommendation:** Change all 5 to "None" or "Partial". Define objective "Full" criteria (must call `sign_cgp()` on publish, `verify_cgp()` on ingest). Re-audit all 26 services.

#### [P1] F-21: `generate-enrollment.py` Issues Unsigned Tokens With Warning Only
- **Location:** `pmoves/scripts/fleet/generate-enrollment.py:245-246`
- **Description:** When `CHIT_PASSPHRASE` not set: `"WARNING: CHIT_PASSPHRASE not set — token issued UNSIGNED."` to stderr, then **continues and produces valid token**.
- **Impact:** Production deployments run without CHIT signing. Warning to stderr often unmonitored.
- **Recommendation:** `sys.exit(1)` when `CHIT_PASSPHRASE` missing. Make signing mandatory.

---

### SECTION 5: GRAPHITI Signature Review

#### [P0] F-22: GRAPHITI "Signatures" Are Plaintext Attribution — Not Cryptographic
- **Location:** `pmoves/docs/AGENTS/GRAPHITI_SIG_REVIEW_2026-02-21.md:47-50`
- **Description:** "Signature" section: `ACK::CODEX-GPT5::PHI-4482-REVIEW::2026-02-21`. Plaintext string — no HMAC, no hash, no key, no algorithm. Anyone writes `ACK::powerfulmoves::anything::any-date` and it looks identical.
- **Impact:** GRAPHITI signatures provide ZERO integrity guarantee. Decorative, not functional. `signature.v1.schema.json` (F-01) validates format but not authenticity.
- **PoC:** `echo 'Signature: ACK::FAKE::FORGED::2099-01-01'` — indistinguishable from real GRAPHITI signature.
- **Recommendation:** Replace with HMAC-SHA256 over canonical JSON. Include `signature_hash` and `signing_key_id` in schema.

#### [P0] F-23: GRAPHITI "Safe Traversal Protocol" Has No Enforcement Mechanism
- **Location:** `pmoves/docs/AGENTS/GRAPHITI_SIG_REVIEW_2026-02-21.md:38-44`
- **Description:** 5-step protocol ("Read AGNOTE4482PHI.t1.md", "Claim one branch lane only", "Post Graphiti signature before release") — procedural guidelines with NO technical enforcement. No lock files, no branch protection, no CI checks, no mutex.
- **Impact:** Multiple agents edit same branch simultaneously. "Post signature before release" unenforceable.
- **Recommendation:** Git branch locks, pre-push hooks verifying GRAPHITI signature presence, CI rejecting unsigned commits.

#### [P2] F-24: `AGENT_TRAIL.md` Contains Unverified GRAPHITI Blocks
- **Location:** `pmoves/docs/AGENT_TRAIL.md` (per GRAPHITI_SIG_REVIEW reference)
- **Description:** Review: "contains signed Graphiti blocks from `powerfulmoves` and `claude-opus`. No unsigned handoff payloads." Since signatures are plaintext (F-22), cannot verify these are from those agents.
- **Impact:** Trail integrity unauditable. Attribution claims unprovable.
- **Recommendation:** Migrate to cryptographic signatures before adding trail entries.

---

### SECTION 6: Additional CHIT Code and Integration Points

#### [P1] F-25: Three Duplicate `canon()` Functions Across Codebase
- **Location:** `pmoves/tools/chit_security.py:20`, `pmoves/services/gateway/scripts/chit_sign.py:15`, `pmoves/scripts/fleet/generate-enrollment.py:86`
- **Description:** Three independent `canon()` implementations — canonical JSON for HMAC input. No shared import. Any implementation difference makes cross-module signatures incompatible.
- **Impact:** Cross-module signature verification fails silently or produces different HMACs.
- **Recommendation:** Extract to `pmoves/tools/chit_common.py`. All modules import from there. Test `canon()` output identical across call sites.

#### [P1] F-26: KDF Mismatch Between Signing and Encryption Modules
- **Location:** `pmoves/services/gateway/scripts/chit_sign.py` (scrypt), `pmoves/tools/chit_security.py` (PBKDF2-HMAC-SHA256, 600K iterations)
- **Description:** `chit_sign.py`: `scrypt(passphrase, salt, N=2**14, r=8, p=1)`. `chit_security.py`: `PBKDF2(passphrase, salt, 600000, SHA256)`. Completely different keys from same passphrase. Cross-module anchor encrypt/decrypt fundamentally broken.
- **Impact:** Data encrypted by `chit_sign.py` undecryptable by `chit_security.py` and vice versa.
- **Recommendation:** Unify to PBKDF2-HMAC-SHA256. Remove scrypt path from `chit_sign.py`.

#### [P1] F-27: Serialization Format Mismatch Between Modules
- **Location:** `pmoves/services/gateway/scripts/chit_sign.py` (JSON `json.dumps()`), `pmoves/tools/chit_security.py` (binary `numpy.packbits()` / float32)
- **Description:** `chit_sign.py` serializes anchors as JSON strings. `chit_security.py` packs as binary float32 via numpy. Even with unified KDF, cross-module decrypt produces garbage.
- **Impact:** Double-break on top of KDF mismatch.
- **Recommendation:** Unify to JSON serialization. Remove binary numpy path.

#### [P1] F-28: Zero Test Coverage for ALL Crypto Paths
- **Location:** `pmoves/tests/test_sign_trail.py` (22 lines, non-crypto), `pmoves/tests/fresh_start/test_chit_integration.py` (CGP encoding only)
- **Description:** 18 crypto paths: sign_cgp, verify_cgp, encrypt_anchors, decrypt_anchors, tamper detection, key derivation (x2), canon (x3). ZERO tests cover any. Crypto test coverage: **0%**.
- **Impact:** Any crypto bug (like KDF/format mismatches) undetected by CI.
- **Recommendation:** Add `test_chit_crypto.py`: sign+verify round-trip, encrypt+decrypt round-trip, tampered rejection, invalid passphrase rejection, cross-module compatibility. Target: 90%+ branch coverage.

#### [P2] F-29: 111 Unauthenticated NATS References Persist
- **Location:** Per AGENT_TRAIL.md drift note, confirmed by grep
- **Description:** 111 references to `nats://nats:pmoves@nats:4222` — shared password across ALL services, no per-service credentials, no TLS, no mutual auth.
- **Impact:** Single service compromise exposes NATS password, granting access to all subjects.
- **Recommendation:** Implement per-service NATS credentials via nsc/nkeys. Enable TLS.

#### [P2] F-30: Tokenism CHITEncoder Is Geometry-Only, Not Security
- **Location:** `pmoves/services/tokenism-simulator/services/__init__.py:9`
- **Description:** `CHITEncoder` encodes data into CHIT geometry format (3D vectors, constellations). Does NOT sign or encrypt. Hardening tracker counts as "Full" (refuted in F-20).
- **Impact:** Tokenism produces unsigned, unencrypted CGP geometry. Downstream consumers cannot verify authenticity.
- **Recommendation:** Add `sign_cgp()` after geometry encoding. Require `CHIT_PASSPHRASE` in Tokenism env.

#### [P2] F-31: 88 GRAPHITI NATS Subjects Defined, ZERO Have Subscribing Code
- **Location:** Per TAC tree analysis (part1_tac_trees_analysis.md)
- **Description:** 88 NATS subjects defined across 7 TAC tree YAML configs. Zero services subscribe. Pipeline 80% planned — only `sign_trail.py` has code.
- **Impact:** GRAPHITI events consumed by no one. Dead letter queues fill. Pipeline non-functional.
- **Recommendation:** Implement subscribers or remove subject definitions. Update docs to reflect actual status.

#### [P3] F-32: `secrets_categorization.yaml` Lists SSH Key as Environment-Scoped
- **Location:** `pmoves/chit/secrets_categorization.yaml:48`
- **Description:** `HOSTINGER_SSH_PRIVATE_KEY` under `environment_secrets` (different per Dev/Prod). SSH keys are identity-based, not environment-based.
- **Recommendation:** Move to repository_secrets or remove from manifest. Use SSH agent.

#### [P3] F-33: CHIT_GATEWAY_API.md Describes Features That Don not Work
- **Location:** `pmoves/docs/PMOVESCHIT/CHIT_GATEWAY_API.md:62-63`
- **Description:** Documents "HMAC-SHA256 signatures" and "AES-GCM anchor encryption" as gateway features. KDF mismatch (F-26) and format mismatch (F-27) make cross-module use broken. No limitations documented.
- **Recommendation:** Add "Known Limitations" section. Mark cross-module encryption as "not currently functional".

---

## Prior Findings (Still Open)

| ID | Severity | Finding | Maps To |
|----|----------|---------|---------|
| P2-F1 | P1 | KDF mismatch: scrypt vs PBKDF2 | F-26 |
| P2-F2 | P1 | Format mismatch: JSON vs numpy binary | F-27 |
| P2-F3 | P1 | Duplicate canon() (3 copies) | F-25 |
| P2-F4 | P0 | Silent skip on ImportError | F-07 |
| P2-F5 | P1 | Zero crypto test coverage | F-28 |

---

## Positive Observations

1. **Tier-based network isolation** (5 tiers: data, api, app, bus, monitoring) — well-designed Docker architecture.
2. **Hardening anchors** (`x-tier-*-hardened-ro`) — consistent cap_drop:ALL, read_only, no-new-privileges across 29+ services.
3. **CodeQL integration** — caught and fixed 19 high-severity alerts including clear-text-logging and path-injection.
4. **chit-contract.yml exists** — structural CI is the right intent, needs crypto verification added.
5. **V2 manifest tier scoping** — architecturally sound secret categorization (agent, llm, data, media, api, worker).
6. **`apply_manifest_v2()` error handling** — proper YAML parsing and structure validation.
7. **Docker hardening scorecard** — 100% non-root, 100% cap drop, 100% read-only. CHIT integration section is the exception.

---

## Recommendations

### Immediate (Block Release)
1. **F-07**: Fail-closed on ImportError in `chit_security_validator.py` — prevents silent bypass of ALL signature verification.
2. **F-20**: Correct hardening tracker CHIT integration claims — false security posture is itself a risk.
3. **F-11**: Remove hardcoded `changeme`/`minioadmin` defaults from `sync_common_credentials()`.
4. **F-21**: Exit with error when `CHIT_PASSPHRASE` missing in `generate-enrollment.py`.

### Short-Term (This Sprint)
5. Unify crypto: extract shared `canon()` (F-25), unify KDF to PBKDF2 (F-26), unify serialization to JSON (F-27).
6. Add crypto tests (F-28): sign+verify, encrypt+decrypt, tamper rejection — 90%+ branch coverage.
7. Enhance `chit-contract.yml` (F-05): add crypto round-trip verification job.
8. Fix F-12: remove SSH private key from env var manifest. Use file-based secrets.
9. Correct documentation (F-13, F-33): remove false AES-256 claims. Document actual security properties.

### Medium-Term (Next Sprint)
10. Implement real encryption for CGP secret values (F-10) or remove encryption claims.
11. Separate dev/prod passphrases (F-15) and signing/encryption keys (F-14).
12. Add CHIT enforcement to `pre-tool.sh` (F-06).
13. Evaluate vault integration (F-18) for centralized secret management.
14. Make GRAPHITI signatures cryptographic (F-22) with HMAC-SHA256.

### Long-Term
15. Create CHIT OpenAPI spec (F-02) for automated contract testing.
16. Implement per-service NATS credentials (F-29) via nsc/nkeys.
17. Build GRAPHITI subscriber code (F-31) or remove 88 dead subject definitions.
18. Add manifest integrity checks (F-03) with SHA-256 hash verification.

---

## Files Audited

| File | Lines | Relevance |
|------|-------|-----------|
| `pmoves/chit/__init__.py` | 310 | Core secrets codec — base16, NOT encryption |
| `pmoves/chit/codec.py` | 36 | Backward-compat wrapper |
| `pmoves/chit/secrets_manifest.yaml` | 350 | V1 manifest — 80 entries |
| `pmoves/chit/secrets_manifest_v2.yaml` | 730 | V2 manifest — 100+ entries, 4-target replication |
| `pmoves/chit/secrets_categorization.yaml` | 120 | GitHub Secrets scoping |
| `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` | 95 | Attribution format, NOT signature |
| `pmoves/tools/chit_security.py` | 128 | Canonical crypto (HMAC + AES-GCM) |
| `pmoves/tools/chit_security_validator.py` | 589 | Validator — silent fail on ImportError |
| `pmoves/services/gateway/scripts/chit_sign.py` | 77 | Duplicate crypto (scrypt + JSON) |
| `pmoves/scripts/fleet/generate-enrollment.py` | 310 | Enrollment — unsigned token warning |
| `.github/workflows/chit-contract.yml` | 90 | Structural-only CI checks |
| `.claude/hooks/pre-tool.sh` | 75 | No CHIT enforcement |
| `docs/hardening/PMOVES-hardening-tracker.md` | 314 | False "Full" integration claims |
| `pmoves/docs/AGENTS/GRAPHITI_SIG_REVIEW_2026-02-21.md` | 50 | Plaintext "signatures" |
| `pmoves/docker-compose.agents.yml` | 850 | CHIT env var injection (6 services) |
| `pmoves/docs/PMOVESCHIT/CHIT_GATEWAY_API.md` | 133 | Describes broken features as working |
| `pmoves/docs/operations/ENVIRONMENT_SETUP.md` | 220 | False "encryption passphrase" claim |
| `pmoves/prompts/codex/PMOVES_Codex_System_Prompt.txt` | 80 | Design checklist, not implementation guarantee |
| `pmoves/services/tokenism-simulator/services/__init__.py` | 12 | CHITEncoder import only |

**Total:** 19 files, ~4,249 lines read. Combined with prior audit: 36 files, ~9,486 lines.

---

*End of audit. All findings require acknowledgment and remediation tracking before next release.*
