# Security Audit Report — PR #1275

**Title:** fix(security): CHIT crypto — fail-closed, unify KDF, remove orphan track, remove hardcoded creds  
**Branch:** `fix/chit-crypto-p0` → `main`  
**Auditor:** Security Auditor (Agent Zero)  
**Date:** 2026-04-18  
**Scope:** 9 files, +943/-130 lines  

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0     |
| High     | 1     |
| Medium   | 2     |
| Low      | 2     |
| Info     | 0     |

**Verdict: MERGE WITH FIX** — The PR delivers substantial security improvements (fail-closed behavior, KDF unification for in-scope modules, key separation, credential hardening). One High finding in the partially-touched gateway file should be addressed before or immediately after merge.

---

## Findings

### [HIGH] Gateway `chit.py` retains hardcoded credential fallback `"change-me"`

- **Location:** `pmoves/services/gateway/gateway/api/chit.py:19`
- **Description:** `CHIT_PASSPHRASE = get_secret("CHIT_PASSPHRASE", "change-me")` provides a known default when the env var is unset. This file IS touched by this PR (adds `_unpack_floats` import at line 13), making the remaining hardcoded fallback an in-scope gap.
- **Impact:** If `CHIT_PASSPHRASE` is not set in a deployment, all HMAC signature verification in the gateway uses the known string `"change-me"`. An attacker who knows this default can forge valid CGP signatures that pass gateway verification, bypassing integrity guarantees entirely.
- **Proof of concept:**
  1. Deploy gateway without `CHIT_PASSPHRASE` env var set
  2. Craft a malicious CGP payload
  3. Sign it with `"change-me"` as the HMAC key
  4. Submit to gateway — signature verification passes
- **Recommendation:** Replace the fallback with a fail-closed pattern:
  ```python
  CHIT_PASSPHRASE = get_secret("CHIT_PASSPHRASE")
  if not CHIT_PASSPHRASE:
      raise RuntimeError(
          "CHIT_PASSPHRASE env var is required — refusing to start with no signing key"
      )
  ```
  This aligns with the fail-closed pattern the PR correctly applies to `chit_security_validator.py` and `generate-enrollment.py`.

---

### [MEDIUM] Gateway `chit.py` retains orphan `canon()` and `verify_hmac()` — partial unification

- **Location:** `pmoves/services/gateway/gateway/api/chit.py:38-39`, `:53-62`
- **Description:** Despite this PR touching the file to add `_unpack_floats`, the gateway still defines its own `canon()` function and `verify_hmac()` that directly uses `CHIT_PASSPHRASE` (the module-level variable with the hardcoded fallback). It does not delegate to `chit_security.verify_cgp()`. The PR's stated goal is "unify KDF" — this file remains outside the unified path.
- **Impact:** Two independent HMAC verification code paths exist for CGPs: one via `chit_security.verify_cgp()` (used by validator, enrollment) and one via gateway's `verify_hmac()`. If a future change fixes a bug in one path but not the other, it creates a verification inconsistency. The gateway path also bypasses the new key separation (`CHIT_SIGNING_KEY` vs `CHIT_PASSPHRASE`).
- **Recommendation:** In a follow-up PR (tracked as known incomplete migration), replace `verify_hmac()` with a call to `chit_security.verify_cgp()` and remove the local `canon()`. Import `canon` from `chit_common` if needed for `compute_shape_id()`. This should be tracked as P1 in the migration backlog.

---

### [MEDIUM] Insecure credential defaults still reachable via `sync_common_credentials` fallback

- **Location:** `pmoves/chit/__init__.py:362-385`
- **Description:** The PR correctly removes the unconditional hardcoded defaults (`changeme`, `minioadmin`) and replaces them with a three-tier fallback: (1) explicit `common_creds` param, (2) `os.environ` lookup, (3) insecure defaults with `DeprecationWarning`. The warning is thorough (includes caller stack frame), but the insecure defaults are still **written to tier env files** — not just warned about.
- **Impact:** If `sync_common_credentials()` is called without `common_creds` and env vars are missing, production tier files get populated with `changeme`/`minioadmin` credentials. A deprecation warning in logs may not be noticed in automated pipelines. The `apply_manifest_v2()` path correctly passes decoded secrets, but any other caller hitting the fallback path silently writes weak creds.
- **Recommendation:** Consider raising `RuntimeError` instead of writing insecure defaults, or at minimum make the fallback opt-in via an explicit `allow_insecure=True` parameter. If backward compatibility requires the fallback, add a CI check that fails on `DeprecationWarning` from this function.

---

### [LOW] Pre-tool hook is a soft gate (warn-only, non-blocking)

- **Location:** `.claude/hooks/pre-tool.sh:69-96`
- **Description:** The hook warns when CHIT-protected files are modified without `chit-acknowledge`, but exits `0` regardless. A tool or agent that ignores stderr proceeds with the modification.
- **Impact:** Low — this is a defense-in-depth measure for Claude Code sessions, not a security boundary. An attacker with tool execution access already has file write access.
- **Recommendation:** Acceptable as-is for a soft guard. If stronger enforcement is desired later, change to `exit 1` when `CHIT_PASSPHRASE` is set and `chit-acknowledge` is absent.

---

### [LOW] Test file mocks `httpx` at module level before imports

- **Location:** `pmoves/tests/test_chit_security.py:12-13`
- **Description:** `sys.modules["httpx"] = MagicMock()` is set before importing `chit_security_validator`. This masks any real import issues with httpx (e.g., version incompatibility, missing transitive dependency).
- **Impact:** Low — the validator's httpx usage is for optional audit logging, not crypto. The mock is pragmatic for unit testing.
- **Recommendation:** Acceptable. Consider using `unittest.mock.patch` in individual tests that hit the audit path for more targeted mocking.

---

## Positive Observations

1. **Fail-closed on validator import:** `chit_security_validator.py` now raises `RuntimeError` on import failure instead of setting `CHIT_SECURITY_AVAILABLE = False` and silently disabling verification. This is the single most important fix in the PR.

2. **Fail-closed on enrollment signing:** `generate-enrollment.py` now calls `sys.exit(1)` when `CHIT_PASSPHRASE` is unset, refusing to issue unsigned tokens. Previously it warned and continued.

3. **KDF unification (in-scope modules):** `chit_sign.py` no longer uses its own `scrypt(n=2^14)` implementation. All crypto now delegates to `chit_security.py` which uses `PBKDF2HMAC(SHA256, 600_000 iterations)`. The 600K iteration count meets OWASP 2023 recommendations.

4. **Key separation:** New `_get_signing_key()` / `_get_encryption_key()` functions with `CHIT_SIGNING_KEY` / `CHIT_ENCRYPTION_KEY` env vars, falling back to `CHIT_PASSPHRASE` with a warning. This follows the principle of using distinct keys for distinct crypto purposes.

5. **Single source of truth for `canon()`:** New `chit_common.py` with the canonical serialization function. `chit_sign.py` and `generate-enrollment.py` now import from there instead of defining their own copies.

6. **Credential hardening in `chit/__init__.py`:** `sync_common_credentials()` no longer unconditionally injects `changeme`/`minioadmin`. The three-tier fallback with caller identification in the warning is well-designed.

7. **Deprecation warnings on hex encode/decode:** `_hex_encode()` and `_hex_decode()` now emit `DeprecationWarning` with clear messaging that base16 is NOT encryption. The module docstring also states this explicitly.

8. **`apply_manifest_v2()` fixed:** Now passes decoded CGP secrets to `sync_common_credentials()` instead of calling it without args, eliminating the chicken-and-egg problem.

9. **Gateway anchor decryption fixed:** `chit.py:decrypt_anchor()` now uses `_unpack_floats()` (binary float32 unpacking) instead of `json.loads()`, matching the encryption format from `chit_security.encrypt_anchors()`. Previously this would have failed at runtime.

10. **Comprehensive test coverage:** 664 lines of tests covering signing, verification, encryption/decryption round-trips, key separation, edge cases (unicode, deeply nested, empty, large payloads), and validator behavior including expiration checks.

11. **Immutable input pattern:** `sign_cgp()` and `encrypt_anchors()` deep-copy input before modification, verified by tests.

---

## Recommendations

### Before Merge (required)
- **[H1]** Fix gateway `chit.py:19` — remove `"change-me"` fallback, fail-closed like the validator. This is a one-line change.

### Immediately After Merge (P1 follow-up)
- **[M1]** File a tracking issue for gateway `chit.py` full migration: replace local `canon()` and `verify_hmac()` with `chit_security` / `chit_common` imports. This is acknowledged as known incomplete work.
- **[M2]** Consider hardening `sync_common_credentials()` fallback to error rather than write insecure defaults.

### Future (P2)
- Migrate `geometry_decoder.py` crypto to delegate to `chit_security` (known incomplete, out of scope for this PR).
- Evaluate `helpers/crypto.py` — separate `hash_data()`/`verify_data()` HMAC utility may or may not be related to CHIT.
- Consider making the pre-tool hook blocking when `CHIT_PASSPHRASE` is set.

---

## Crypto Parameter Review

| Parameter | Value | Assessment |
|-----------|-------|------------|
| KDF | PBKDF2-HMAC-SHA256 | Standard, well-reviewed |
| Iterations | 600,000 | Meets OWASP 2023 (>=600K for SHA-256) |
| Salt | 16 bytes, `os.urandom` | Cryptographically random per encryption |
| Key length | 32 bytes (256 bits) | Adequate for AES-256 |
| Cipher | AES-GCM | Authenticated encryption |
| IV/Nonce | 12 bytes, `os.urandom` | Standard GCM nonce size, random per operation |
| AAD | `canon({"id": constellation_id})` | Binds ciphertext to constellation identity |
| HMAC | HMAC-SHA256 | Standard MAC, constant-time comparison via `hmac.compare_digest` |
| Float packing | `struct.pack(">I", count) + float32.tobytes()` | Deterministic, binary format (no JSON ambiguity) |

**Note:** The removed `chit_sign.py` used `scrypt(n=2^14, r=8, p=1)` which is also secure but different from the canonical PBKDF2. Unifying to PBKDF2 eliminates KDF inconsistency within the in-scope modules.

---

## Cross-Reference with Prior Audits

This PR directly addresses the following findings from the CHIT Secrets Management Audit (2026-04-17):

| Prior Finding | Status | Notes |
|---------------|--------|-------|
| F-07: Validator silently skips on ImportError | **FIXED** | Now raises RuntimeError — fail-closed |
| F-11: sync_common_credentials injects changeme | **PARTIALLY FIXED** | Three-tier fallback with warning; insecure defaults still reachable |
| F-10: chit/__init__.py is base16 not encryption | **MITIGATED** | DeprecationWarning + explicit docstring; base16 still functional |
| F-04 (part2): Duplicate canon() across 3 files | **PARTIALLY FIXED** | chit_common.py created, chit_sign.py and generate-enrollment.py migrated; gateway and geometry_decoder still have their own |
| F-01 (part2): KDF mismatch scrypt vs PBKDF2 | **PARTIALLY FIXED** | chit_sign.py unified; geometry_decoder still uses scrypt |
| F-05 (part2): Zero test coverage for crypto | **FIXED** | 664 lines of tests added |

---

## Verdict

**MERGE WITH FIX**

The PR delivers on its core promises for the in-scope modules: fail-closed behavior, KDF unification, orphan crypto removal from `chit_sign.py` and `generate-enrollment.py`, and credential hardening. The test suite is thorough.

The one blocking concern is the gateway `"change-me"` hardcoded fallback on a file this PR partially modifies. Fixing that single line before merge closes the most exploitable gap. The remaining gateway unification (`canon()`/`verify_hmac()`) and `geometry_decoder.py` migration are acknowledged follow-up work.
