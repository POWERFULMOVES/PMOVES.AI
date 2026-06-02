# A2: CHIT Crypto Consolidation Log
Date: 2026-05-15

## Summary
Consolidated duplicate CHIT crypto implementations across 3 files.

## Changes

### geometry_decoder.py
- Replaced inline `_pack_floats`/`_unpack_floats` with safety wrappers delegating to `chit_security`
- Added deprecation comments to divergent `sign_cgp`/`verify_cgp`
- Kept `encrypt_anchor`/`decrypt_anchor` (unique single-anchor versions)
- Kept `encrypt_anchors`/`decrypt_anchors` (uses local single-anchor versions)
- Lines removed: ~30 (duplicate numpy/struct code)

### gateway/chit.py
- Replaced duplicate `canon()` with import from `pmoves.tools.chit_common`
- Fixed undefined `kdf` bug at line 82 — added PBKDF2HMAC instantiation

### chit_security_validator.py
- Added fail-closed else clause: when security_level is SIGNED/STRICT and no key available, returns error instead of silently passing

## What Was NOT Changed
- `chit_security.py` — canonical module, untouched
- `chit_common.py` — canonical canon(), untouched
- `sign_cgp`/`verify_cgp` in geometry_decoder — kept due to divergent behavior (blake2b kid + ts field)

## Test Results

```
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0 -- /opt/venv/bin/python
cachedir: .pytest_cache
rootdir: /a0/usr/projects/pmoves/pmoves
configfile: pyproject.toml
plugins: anyio-4.13.0, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False
collected 12 items

pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_pack_floats_matches PASSED [  8%]
pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_unpack_floats_matches PASSED [ 16%]
pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_roundtrip_pack_unpack PASSED [ 25%]
pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_safety_limit_pack PASSED [ 33%]
pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_safety_limit_unpack_count PASSED [ 41%]
pmoves/tests/test_chit_crypto_consolidation.py::TestPackUnpackParity::test_safety_limit_unpack_small_buffer PASSED [ 50%]
pmoves/tests/test_chit_crypto_consolidation.py::TestGatewayCanonImport::test_imports_canonical_canon PASSED [ 58%]
pmoves/tests/test_chit_crypto_consolidation.py::TestGatewayCanonImport::test_canon_output_matches PASSED [ 66%]
pmoves/tests/test_chit_crypto_consolidation.py::TestValidatorFailClosed::test_fails_when_no_key_signed PASSED [ 75%]
pmoves/tests/test_chit_crypto_consolidation.py::TestValidatorFailClosed::test_fails_when_no_key_strict PASSED [ 83%]
pmoves/tests/test_chit_crypto_consolidation.py::TestGeometryDecoderSignVerify::test_sign_verify_roundtrip PASSED [ 91%]
pmoves/tests/test_chit_crypto_consolidation.py::TestGeometryDecoderSignVerify::test_verify_tampered_fails PASSED [100%]

============================== 12 passed in 0.05s ==============================
```

## Test Adjustments
The original test template required two fixes to match the actual codebase:
1. **Source name**: Changed `source="trusted"` to `source="agent-zero"` — the validator's AccessControl only allows specific TRUSTED_SOURCES
2. **CGP schema**: Added required Pydantic fields (`summary`, super_node `id`/`label`/`summary`/`x`/`y`/`r`, constellation `summary`) and used `datetime.now()` for `created_at` to avoid the 24-hour expiration check
3. Both adjustments maintain the original test intent — validating fail-closed behavior when no signing key is available
