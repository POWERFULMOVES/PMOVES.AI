# CHIT Crypto Mismatch — Git Forensics Root Cause Analysis
Generated: 2026-04-17

## Executive Summary
**Root cause: Independent authorship from birth, NOT divergence over time.** Two files written by different authors 12 days apart, each with their own crypto from line 1. CGP v1.0 spec canonically designates chit_security.py. chit_sign.py is an orphan.

## File Birth Timeline
| File | Born | Author | KDF | Format |
|------|------|--------|-----|--------|
| chit_security.py | 2025-09-08 | PMOVES Bot | PBKDF2 | Binary float32 |
| chit_sign.py | 2025-09-20 | POWERFULMOVES | scrypt | JSON |
| chit_security_validator.py | ~2025-09-08 | PMOVES Bot | imports chit_security | imports chit_security |
| sign_trail.py | 2026-03-01 | POWERFULMOVES | none (delegates) | none (delegates) |
| chit/__init__.py | ~2025-09-08 | PMOVES Bot | none (base16) | base16 hex |

## Smoking Gun
sign_trail.py (same author as chit_sign.py) docstring: 'Never contains its own crypto — chit_security is the single source of truth'

## CGP v1.0 Spec
All 3 code examples import from pmoves.tools.chit_security. Zero mentions of chit_sign.py.

## PR #984
Fixed gateway/api/chit.py KDF but missed chit_sign.py AND plaintext format mismatch.

## Three Independent Tracks
1. chit_security.py (CANONICAL per spec) — PBKDF2 + AES-256-GCM + binary float32
2. chit_sign.py (ORPHAN, now refactored) — was scrypt + JSON, now delegates to chit_security
3. chit/__init__.py (NOT ENCRYPTION) — base16 hex encoding only

## Resolution Status
- P0: chit_sign.py refactored to delegate to chit_security.py ✅
- P0: gateway/api/chit.py format fixed (_unpack_floats) ✅
- P0: fail-closed on ImportError ✅
- P0: shared canon() extracted to chit_common.py ✅
- P0: changeme defaults removed ✅
- P0: CHIT_PASSPHRASE required ✅
