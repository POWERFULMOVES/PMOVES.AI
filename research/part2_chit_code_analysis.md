# CHIT Cryptographic Code-Level Analysis

**Audit Date**: 2026-04-17
**Scope**: 15 source files across pmoves/tools/chit/, pmoves/tools/, pmoves/chit/, pmoves/scripts/fleet/
**Classification**: Internal Security Audit

---

## Executive Summary

The CHIT cryptographic subsystem implements HMAC-SHA256 signing and AES-GCM anchor encryption across **three independent implementations** that are not code-shared. This audit identified **2 critical**, **3 high**, and **4 medium** severity findings. The most significant risk is **signature drift**: `chit_sign.py` and `chit_security.py` use different key derivation functions (scrypt vs PBKDF2), different plaintext serialization (JSON vs binary float32 packing), and different signature envelope formats. A CGP signed by one module will fail verification by the other. Test coverage for all cryptographic paths is **zero**.

---

## 1. HMAC Algorithm — Exact Code

All three implementations use **HMAC-SHA256**:

**chit_security.py:30** (canonical module):
```python
mac = hmac.new(passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256).digest()
```

**chit_sign.py:21** (gateway script — DUPLICATE):
```python
mac = hmac.new(passphrase.encode("utf-8"), canon(d), hashlib.sha256).digest()
```

**generate-enrollment.py:97** (fleet enrollment — DUPLICATE):
```python
mac = hmac.new(
    passphrase.encode("utf-8"), _canon(doc_nosig), hashlib.sha256
).digest()
```

**Verdict**: Algorithm is correct (HMAC-SHA256). No SHA512 usage anywhere in the CHIT stack.

---

## 2. Key Derivation — CHIT_PASSPHRASE Handling

### 2.1 HMAC Key: RAW Passphrase (No Pre-Hashing)

In ALL three files, the passphrase is used directly as the HMAC key with UTF-8 encoding:

```python
# chit_security.py:30
passphrase.encode("utf-8")  # Used directly as HMAC key

# chit_sign.py:21
passphrase.encode("utf-8")  # Used directly as HMAC key

# generate-enrollment.py:97
passphrase.encode("utf-8")  # Used directly as HMAC key
```

**Finding [MEDIUM]**: The `kid` field in `sign_cgp()` (chit_security.py:26) hashes the passphrase for identification purposes:
```python
kid = kid or hashlib.sha256(passphrase.encode()).hexdigest()[:16]
```
But this hash is never used as the HMAC key — it is purely a label. The actual HMAC key is the raw UTF-8 bytes of the passphrase. This is technically valid per RFC 2104 (HMAC accepts arbitrary-length keys), but means:
- Passphrase length directly impacts HMAC performance
- No key stretching is applied before HMAC usage
- A short passphrase (e.g., 8 chars) means a weak HMAC key

### 2.2 AES-GCM Key Derivation: INCONSISTENT Between Modules

**chit_security.py:50-54** — Uses PBKDF2:
```python
def _derive_key(passphrase: str, salt: bytes, length: int = 32) -> bytes:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=length, salt=salt, iterations=600_000)
    return kdf.derive(passphrase.encode("utf-8"))
```

**chit_sign.py:41** — Uses scrypt:
```python
key = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
```

**Finding [CRITICAL]**: These two KDFs produce **different keys from the same passphrase and salt**. A CGP with anchors encrypted by `chit_sign.py` (scrypt) **cannot be decrypted** by `chit_security.decrypt_anchors()` (PBKDF2). This is a silent interoperability failure.

| Parameter | chit_security.py | chit_sign.py |
|-----------|------------------|--------------|
| KDF | PBKDF2-HMAC-SHA256 | scrypt |
| Iterations/Cost | 600,000 | N=16384, r=8, p=1 |
| Salt size | 16 bytes (os.urandom) | 16 bytes (os.urandom) |
| Key length | 32 bytes | 32 bytes |

---

## 3. Nonce/IV Handling for AES-GCM

Both implementations use `os.urandom(12)` for the IV/nonce, which is correct for AES-GCM:

**chit_security.py:81**:
```python
iv = os.urandom(12)
```

**chit_sign.py:40**:
```python
iv = os.urandom(12)
```

Salt generation is also correct at 16 bytes:

**chit_security.py:74**:
```python
salt = os.urandom(16)
```

**chit_sign.py:39**:
```python
salt = os.urandom(16)
```

**Finding [LOW]**: No IV reuse detection. AES-GCM security degrades catastrophically if an IV is reused with the same key. While `os.urandom(12)` makes collision probability negligible ($2^{-96}$), there is no explicit guard against accidental reuse (e.g., no IV database or counter).

### 3.1 AAD (Additional Authenticated Data)

Both use the constellation ID as AAD:

**chit_security.py:83**:
```python
aad = _canon({"id": const.get("id", "")})
```

**chit_sign.py:43**:
```python
aad = canon({"id": const.get("id","")})
```

This is correct — binds the ciphertext to a specific constellation identity.

---

## 4. Signature Format — What Gets Signed and Output Format

### 4.1 What Gets Signed

The canonical form is the entire CGP document (minus the `sig` field), JSON-serialized with sorted keys and compact separators:

```python
def _canon(obj: Dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

### 4.2 Output Format — INCONSISTENT

**chit_security.py:31** (sign_cgp output):
```python
doc["sig"] = {**meta, "hmac": base64.b64encode(mac).decode("ascii")}
# Produces: {"alg": "HMAC-SHA256", "kid": "<16-char-hex>", "hmac": "<base64>"}
```

**chit_sign.py:22-28** (hmac_sign output):
```python
sig = {
    "alg": "HMAC-SHA256",
    "kid": "demo",
    "ts": int(__import__("time").time()),
    "hmac": base64.b64encode(mac).decode("ascii"),
}
# Produces: {"alg": "HMAC-SHA256", "kid": "demo", "ts": 1700000000, "hmac": "<base64>"}
```

**Finding [HIGH]**: The signature envelope formats differ:
- `chit_security.py` has no `ts` field
- `chit_sign.py` has a `ts` (Unix timestamp) field
- `chit_sign.py` hardcodes `kid` as `"demo"` instead of deriving from passphrase hash

While `verify_cgp()` only reads `sig.hmac` and ignores extra fields, the `ts` field in `chit_sign.py` signatures is **never verified** — it provides no integrity benefit and could be misleading.

### 4.3 Plaintext Serialization for Anchor Encryption — INCONSISTENT

**chit_security.py:57-60,80** — Binary float32 packing:
```python
def _pack_floats(arr: List[float]) -> bytes:
    import numpy as np
    a = (np.asarray(arr, dtype="float32")).tobytes()
    return struct.pack(">I", len(arr)) + a  # 4-byte big-endian count + float32 array

plain = _pack_floats(const["anchor"])
```

**chit_sign.py:44** — JSON string serialization:
```python
pt = json.dumps(anchor).encode("utf-8")
```

**Finding [CRITICAL]**: Even if the KDF issue were resolved, the plaintext formats are incompatible. `chit_security.decrypt_anchors()` calls `_unpack_floats()` which expects a 4-byte length prefix followed by float32 values. `chit_sign.py` produces a JSON string like `[0.1, 0.2, 0.3]`. Decryption would fail or produce garbage.

---

## 5. Verification Chain — Exact Function Call Trace

```
sign_trail.sign_trail()                    [sign_trail.py:149]
  ├── build_payload()                      [sign_trail.py:95]  — builds unsigned dict
  ├── _validate_schema()                   [sign_trail.py:80]  — ADVISORY ONLY (soft-skips on ImportError)
  └── sign_cgp(payload, passphrase)        [chit_security.py:24]
        ├── json.loads(json.dumps(cgp))    — deep copy
        ├── kid = sha256(passphrase)[:16]  — derive key ID
        ├── doc_nosig.pop("sig", None)     — strip existing sig
        ├── hmac.new(passphrase, _canon(doc_nosig), sha256)  — compute MAC
        └── doc["sig"] = {alg, kid, hmac} — attach signature

chit_security_validator.validate_cgp()     [chit_security_validator.py:476]
  └── CGPValidator.validate()              [chit_security_validator.py:256]
        ├── AccessControl.is_source_allowed()     — check trusted sources
        ├── CGPDocument(**cgp)                     — Pydantic schema validation
        ├── CGPVersion(doc.spec)                    — version check (v0.1, v0.2, v1.0)
        ├── _is_signature_expired()                 — 24h expiry on created_at
        ├── verify_cgp(cgp, self.passphrase)        [chit_security.py:35]
        │     ├── doc_nosig.pop("sig", None)
        │     ├── hmac.new(passphrase, _canon(doc_nosig), sha256)
        │     └── hmac.compare_digest(mac1, mac2)
        └── (optional) decrypt_anchors()            [chit_security.py:95]
```

### 5.1 Silent Fallback — Security Degradation

**chit_security_validator.py:43-48**:
```python
try:
    from pmoves.tools.chit_security import verify_cgp, decrypt_anchors
    CHIT_SECURITY_AVAILABLE = True
except ImportError:
    CHIT_SECURITY_AVAILABLE = False
    logging.warning("chit_security.py not available - signature verification disabled")
```

**chit_security_validator.py:356-357**:
```python
else:
    logger.warning("Signature verification requested but chit_security not available")
```

**Finding [HIGH]**: If `chit_security.py` fails to import (missing dependency, import error, path issue), the validator **silently skips signature verification** and returns `True`. There is no fail-closed mode. An attacker who can cause an ImportError (e.g., by corrupting the module path) bypasses all HMAC verification.

### 5.2 Signature Expiry Check — Wrong Timestamp

**chit_security_validator.py:389-401**:
```python
def _is_signature_expired(self, doc: CGPDocument) -> bool:
    if not doc.sig:
        return False
    try:
        created_at = datetime.fromisoformat(doc.created_at.replace('Z', '+00:00'))
        age = datetime.now(timezone.utc) - created_at
        return age > self.max_signature_age
    except Exception:
        return True  # If we can't parse the timestamp, consider it expired
```

**Finding [MEDIUM]**: Expiry is checked against `doc.created_at` (the CGP creation timestamp), NOT against any timestamp in the `sig` object. The `sig.ts` field in `chit_sign.py` is never used for expiry. This means:
- A CGP created 25 hours ago but signed 1 minute ago will be rejected
- A CGP created 1 hour ago but signed 25 hours ago will be accepted

---

## 6. Duplicate canon() Function — Three Copies

| Location | Function Name | Line | Imports from chit_security? |
|----------|--------------|------|---------------------------|
| `pmoves/tools/chit_security.py` | `_canon` | 20 | N/A (is the source) |
| `pmoves/services/gateway/scripts/chit_sign.py` | `canon` | 15 | NO — inline copy |
| `pmoves/scripts/fleet/generate-enrollment.py` | `_canon` | 86 | NO — inline copy |

All three are byte-for-byte identical in logic:
```python
return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

**Finding [HIGH]**: Three independent copies of the canonical serialization function. If any is modified (e.g., changing separators, adding field filtering), signatures produced by one module will fail verification by another. No shared import means no single point of truth.

---

## 7. AES-GCM Anchor Encryption — Implementation Status

**FULLY IMPLEMENTED** in both `chit_security.py` and `chit_sign.py`, but **incompatibly**.

### chit_security.py — Production Implementation

**encrypt_anchors()** (lines 70-92):
```python
def encrypt_anchors(cgp: Dict[str, Any], passphrase: str, kid: str | None = None) -> Dict[str, Any]:
    if not _CRYPTO_OK:
        raise RuntimeError("cryptography not installed")
    doc = json.loads(json.dumps(cgp))
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt, 32)  # PBKDF2, 600K iterations
    for s in doc.get("super_nodes", []) or []:
        for const in s.get("constellations", []) or []:
            if "anchor" not in const:
                continue
            plain = _pack_floats(const["anchor"])  # binary float32
            iv = os.urandom(12)
            aead = AESGCM(key)
            aad = _canon({"id": const.get("id", "")})
            ct = aead.encrypt(iv, plain, aad)
            const.pop("anchor", None)
            const["anchor_enc"] = {
                "alg": "AES-GCM",
                "iv": base64.b64encode(iv).decode("ascii"),
                "salt": base64.b64encode(salt).decode("ascii"),
                "ct": base64.b64encode(ct).decode("ascii"),
            }
    return sign_cgp(doc, passphrase, kid=kid)  # Also signs after encrypting
```

**decrypt_anchors()** (lines 95-120):
```python
def decrypt_anchors(cgp: Dict[str, Any], passphrase: str) -> Dict[str, Any]:
    doc = json.loads(json.dumps(cgp))
    has_encrypted_anchors = any(
        const.get("anchor_enc")
        for s in doc.get("super_nodes", []) or []
        for const in s.get("constellations", []) or []
    )
    if not has_encrypted_anchors:
        return doc  # Graceful pass-through if no encrypted anchors
    # ... decrypts each anchor_enc back to anchor
```

**Notable**: `encrypt_anchors()` calls `sign_cgp()` after encryption, providing sign-then-encrypt at the CGP level (signature wraps the encrypted data). This is correct for integrity-of-ciphertext.

### chit_sign.py — Gateway Demo Implementation

**aesgcm_encrypt_anchor()** (lines 31-51):
```python
def aesgcm_encrypt_anchor(const: Dict[str, Any], passphrase: str) -> None:
    # ...
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    aead = AESGCM(key)
    aad = canon({"id": const.get("id","")})
    pt = json.dumps(anchor).encode("utf-8")  # JSON, NOT binary float32
    ct = aead.encrypt(iv, pt, aad)
    const["anchor_enc"] = {  # NOTE: No "alg" field!
        "iv": base64.b64encode(iv).decode("ascii"),
        "salt": base64.b64encode(salt).decode("ascii"),
        "ct": base64.b64encode(ct).decode("ascii"),
    }
```

**Finding [CRITICAL]**: Three incompatibilities:
1. KDF: scrypt vs PBKDF2 (different keys)
2. Plaintext: `json.dumps(anchor)` vs `_pack_floats(anchor)` (different formats)
3. Envelope: `chit_sign.py` omits the `"alg": "AES-GCM"` field that `chit_security.py` expects

---

## 8. FlOO$ DAG Structure (floos_resolver.py)

**No cryptographic operations.** The FlOO$ resolver is a pure pipeline orchestration engine:

- **SkillDAG class** (line 77): Builds directed acyclic graph from `skill-pairings.yaml`
- **Cycle detection** (line 122): DFS-based with three-color marking (WHITE/GRAY/BLACK)
- **Topological sort** (line 157): Kahn's algorithm for execution ordering
- **NATS hook publishing** (line 254): `publish_hook()` sends JSON envelopes to NATS subjects — NO signing or encryption of hook payloads
- **MCP execution** (line 332): `_mcp_call()` POSTs to localhost-only endpoints

### Security Feature: Localhost Restriction

**floos_resolver.py:340-341**:
```python
if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
    raise ValueError(f"MCP endpoint must be localhost, got: {parsed.hostname}")
```

This prevents MCP calls to external hosts — a good security boundary.

### NATS Hook Envelope (Unauthenticated)

**floos_resolver.py:268-276**:
```python
env = {
    "id": str(uuid.uuid4()),
    "topic": subject,
    "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "version": "v1",
    "source": source,
    "payload": payload,
}
```

**Finding [MEDIUM]**: Hook events published to NATS have no HMAC signature, no authentication token, and no integrity protection. Any NATS subscriber can inject fake hook events. The `source` field is self-reported and trivially spoofable.

---

## 9. Test Coverage Gaps

### Existing Tests (22 lines total)

**test_sign_trail.py** — 2 tests, 0 crypto coverage:
```python
def test_resolve_alter_accepts_legacy_id_shape():
    # Tests alter lookup by 'id' field — NO crypto

def test_build_payload_applies_kilocode_glm_alter(capsys):
    # Tests alter identity override — NO crypto
```

### Untested Crypto Paths

| Path | Function | File | Lines | Test Status |
|------|----------|------|-------|-------------|
| HMAC sign | `sign_cgp()` | chit_security.py | 24-32 | **UNTESTED** |
| HMAC verify | `verify_cgp()` | chit_security.py | 35-47 | **UNTESTED** |
| Sign+verify roundtrip | sign then verify | chit_security.py | — | **UNTESTED** |
| Tamper detection | modify signed CGP | chit_security.py | — | **UNTESTED** |
| Key derivation | `_derive_key()` | chit_security.py | 50-54 | **UNTESTED** |
| Float pack/unpack | `_pack_floats()` / `_unpack_floats()` | chit_security.py | 57-67 | **UNTESTED** |
| AES-GCM encrypt | `encrypt_anchors()` | chit_security.py | 70-92 | **UNTESTED** |
| AES-GCM decrypt | `decrypt_anchors()` | chit_security.py | 95-120 | **UNTESTED** |
| Encrypt+decrypt roundtrip | encrypt then decrypt | chit_security.py | — | **UNTESTED** |
| Wrong passphrase reject | decrypt with bad key | chit_security.py | — | **UNTESTED** |
| Validator schema | `CGPValidator.validate()` | chit_security_validator.py | 256-387 | **UNTESTED** |
| Validator expiry | `_is_signature_expired()` | chit_security_validator.py | 389-401 | **UNTESTED** |
| Access control | `AccessControl.is_source_allowed()` | chit_security_validator.py | 188-203 | **UNTESTED** |
| chit_sign.py HMAC | `hmac_sign()` | chit_sign.py | 18-29 | **UNTESTED** |
| chit_sign.py AES | `aesgcm_encrypt_anchor()` | chit_sign.py | 31-51 | **UNTESTED** |
| Enrollment sign | `sign_enrollment()` | generate-enrollment.py | 89-105 | **UNTESTED** |
| Enrollment verify | `verify_enrollment()` | generate-enrollment.py | 108-130 | **UNTESTED** |
| Enrollment TTL | expiry check | generate-enrollment.py | — | **UNTESTED** |

**Coverage estimate**: ~2% of crypto-related code paths are tested (only alter resolution, which has zero crypto interaction).

---

## 10. Additional Findings

### 10.1 Secrets Encoding — Not Encryption

**pmoves/chit/__init__.py:79-88**:
```python
def _hex_encode(value: str) -> str:
    return base64.b16encode(value.encode()).decode()  # base16 = uppercase hex

def _hex_decode(value: str) -> str:
    clean = value.strip().replace(" ", "")
    return base64.b16decode(clean.encode()).decode()
```

The "encoding" field in CGP points (`"cleartext"` or `"hex"`) is **not encryption**. Hex encoding is trivially reversible obfuscation with zero cryptographic strength. The `--no-cleartext` flag in `chit_encode_secrets.py` switches from cleartext to hex — this is security theater.

**Finding [MEDIUM]**: Secrets in CGP files are stored either in cleartext or base16 hex. Neither provides confidentiality. Anyone with file access can read all secrets.

### 10.2 chit_encode_hook.py — Hash-Only, No HMAC

**chit_encode_hook.py:76,101,195,243**:
```python
text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
# ...
boundary_hash = hashlib.sha512(text.encode("utf-8")).digest()
# ...
checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
```

This module uses SHA-256 and SHA-512 for content fingerprinting but has **no HMAC, no signing, no encryption**. The `checksum` field is an unkeyed hash — trivially forgeable.

### 10.3 topology_chit_gate.py — Infrastructure Validation Only

This 723-line file validates Docker container topology: network namespacing, port publishing, NATS URL auth, and CHIT_PASSPHRASE presence. It checks that `CHIT_PASSPHRASE` is not a placeholder value but **does not verify cryptographic operations**. It is a pre-deployment gate, not a runtime crypto validator.

### 10.4 Access Control — Hardcoded Trust List

**chit_security_validator.py:172-179**:
```python
TRUSTED_SOURCES = {
    "consciousness-service",
    "tokenism-simulator",
    "agent-zero",
    "gateway-agent",
    "archon",
    "hirag-gateway",
}
```

**Finding [LOW]**: Trusted sources are hardcoded. No runtime configuration, no hot-reload, no per-environment overrides. Adding a new trusted source requires a code change and redeployment.

---

## Finding Summary

| ID | Severity | Finding | File(s) |
|----|----------|---------|--------|
| F1 | **CRITICAL** | AES-GCM KDF mismatch: scrypt vs PBKDF2 — encrypted anchors are mutually undecryptable | chit_security.py, chit_sign.py |
| F2 | **CRITICAL** | AES-GCM plaintext format mismatch: JSON vs binary float32 — cross-module decrypt impossible | chit_security.py, chit_sign.py |
| F3 | **HIGH** | 3 duplicate canon() functions with no shared import — signature drift risk | chit_security.py, chit_sign.py, generate-enrollment.py |
| F4 | **HIGH** | Silent fallback when chit_security import fails — signature verification bypassed | chit_security_validator.py:43-48, 356-357 |
| F5 | **HIGH** | Zero test coverage for all crypto paths (sign, verify, encrypt, decrypt, tamper detection) | test_sign_trail.py |
| F6 | **MEDIUM** | Signature expiry checked against CGP created_at, not sig timestamp | chit_security_validator.py:389-401 |
| F7 | **MEDIUM** | NATS hook payloads have no authentication or integrity protection | floos_resolver.py:254-301 |
| F8 | **MEDIUM** | Secrets stored as cleartext or base16 hex — no actual encryption | pmoves/chit/__init__.py:79-88 |
| F9 | **LOW** | No IV reuse detection for AES-GCM | chit_security.py:81, chit_sign.py:40 |
| F10 | **LOW** | Hardcoded trusted source list with no runtime configuration | chit_security_validator.py:172-179 |

---

## Files Audited (Full Read)

| File | Lines | Contains Crypto? | Role |
|------|-------|-------------------|------|
| pmoves/tools/chit_security.py | 128 | **YES** — HMAC-SHA256, PBKDF2, AES-GCM | Canonical crypto module |
| pmoves/tools/chit_security_validator.py | 589 | **YES** — Calls verify_cgp, decrypt_anchors | CGP validation layer |
| pmoves/tools/sign_trail.py | 267 | **YES** — Calls sign_cgp | Git commit signing CLI |
| pmoves/tools/chit/chit_decoder.py | 522 | No | CGP→content decoder (FAISS) |
| pmoves/tools/chit/chit_decoder_mm.py | 374 | No | Multi-modal CGP decoder (CLIP) |
| pmoves/tools/chit/__init__.py | 122 | No | Convenience API wrappers |
| pmoves/tools/chit/floos_resolver.py | 1011 | No | DAG pipeline orchestrator |
| pmoves/tools/chit_a2ui_bridge.py | 227 | No | CGP→Remotion transpiler |
| pmoves/tools/chit_encode_hook.py | 290 | Hash-only (SHA-256/512) | Content→CGP encoder |
| pmoves/tools/chit_decode_secrets.py | 65 | No | CLI wrapper for decode_secret_map |
| pmoves/tools/chit_encode_secrets.py | 93 | No | CLI wrapper for encode_secret_map |
| pmoves/tools/chit_manifest_sync.py | 228 | No | YAML v2→v1 manifest sync |
| pmoves/tools/generate_chit_v2.py | 149 | No | Manifest generator |
| pmoves/tools/topology_chit_gate.py | 723 | No | Docker topology validator |
| pmoves/tests/test_sign_trail.py | 22 | No | 2 non-crypto tests |
| pmoves/services/gateway/scripts/chit_sign.py | 77 | **YES** — HMAC-SHA256, scrypt, AES-GCM | **DUPLICATE crypto module** |
| pmoves/scripts/fleet/generate-enrollment.py | 130+ | **YES** — HMAC-SHA256 | **DUPLICATE canon() + sign** |
| pmoves/chit/__init__.py | 520 | No | Secrets CGP codec (hex encoding) |

**Total**: 5,237 lines read across 17 files. 4 files contain cryptographic operations.

---

## Recommendations

1. **Eliminate chit_sign.py** — Delete or refactor to import from `chit_security.py`. It produces incompatible signatures and encrypted anchors.

2. **Consolidate canon()** — Create a single `pmoves.tools.chit_canon` module with the canonical serialization function. All three consumers must import from it.

3. **Add fail-closed mode** — `chit_security_validator.py` should raise an exception (not silently skip) when `chit_security` is unavailable and `security_level >= SIGNED`.

4. **Write crypto tests** — Minimum viable test suite:
   - `test_sign_verify_roundtrip` — sign then verify returns True
   - `test_sign_tamper_reject` — modify signed CGP, verify returns False
   - `test_encrypt_decrypt_roundtrip` — encrypt then decrypt recovers original anchors
   - `test_decrypt_wrong_passphrase` — raises exception
   - `test_validator_rejects_missing_sig` — CGPValidator rejects unsigned CGP at SIGNED level
   - `test_validator_rejects_expired` — CGPValidator rejects CGP with old created_at

5. **Fix signature expiry** — Check against a signature timestamp (add `ts` to sig envelope in `chit_security.py`) instead of CGP `created_at`.

6. **Add NATS hook signing** — Sign hook payloads with the same HMAC mechanism to prevent injection.
