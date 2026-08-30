# CHIT Integration Verification Audit

**Date:** 2026-04-17  
**Scope:** Verify 'Full' CHIT integration claims in PMOVES Hardening Tracker v4.0  
**Method:** Grep-based code audit of `sign_cgp`, `verify_cgp`, `chit_security`, `chit_security_validator` across all service directories  
**Standard:** Only actual code call sites count. Documentation, comments, and CGP packet construction without signing do not qualify.

---

## Executive Summary

Of the 5 services claimed as 'Full' CHIT integration in the hardening tracker, only **1 (Hi-RAG v2)** has an actual call to the canonical `verify_cgp()` from `chit_security.py`. The Gateway has a duplicate inline crypto implementation that does not use the canonical module. Tokenism Simulator, Neo4j Mind Map, and Agent Zero have **zero** sign_cgp or verify_cgp calls in their service code. Additionally, the tracker itself acknowledges under Production Readiness Blockers that "CHIT Security Disabled (passphrase/signatures)" is a CRITICAL unresolved item.

---

## Findings Table

| Service | Tracker Claims | Actual sign_cgp calls | Actual verify_cgp calls | Verdict |
|---------|---------------|----------------------|------------------------|---------|
| Tokenism Simulator | Full | 0 | 0 | **REFUTED** |
| Hi-RAG v2 | Full | 0 | 1 (routes/geometry.py:154) | **VERIFIED** |
| Gateway | Full | 0 | 0 (has duplicate verify_hmac() inline) | **PARTIAL** |
| Neo4j Mind Map | Full | 0 | 0 | **REFUTED** |
| Agent Zero | Full | 0 | 0 | **REFUTED** |

---

## Per-Service Detailed Analysis

### 1. Tokenism Simulator -- REFUTED

**Service directory:** `pmoves/services/tokenism-simulator/`

**Files examined:**
- `services/chit_encoder.py` (212 lines) -- Contains CHITEncoder class
- `api/simulation.py`, `services/simulation_engine.py`, `app.py`, `config/*.py`
- `tests/test_chit_encoder.py`

**Findings:**
- `chit_encoder.py` constructs CGP packet data structures (CGPPacket objects) with geometry fields (hyperbolic coordinates, edges, etc.)
- It does **NOT** call `sign_cgp()` or `verify_cgp()` at any point
- It does **NOT** import from `chit_security`, `chit_security_validator`, or `services.common` CHIT modules
- The encoder produces unsigned CGP packets that are published directly to the geometry bus without signature
- `test_chit_encoder.py` tests packet construction, not signing

**Conclusion:** Tokenism Simulator produces CGP packets but never signs them. This is CGP *construction*, not CHIT *security integration*.

---

### 2. Hi-RAG v2 -- VERIFIED

**Service directory:** `pmoves/services/hi-rag-gateway-v2/`

**Call site found:**
```
pmoves/services/hi-rag-gateway-v2/routes/geometry.py:148:  from tools.chit_security import verify_cgp, decrypt_anchors
pmoves/services/hi-rag-gateway-v2/routes/geometry.py:154:  if not verify_cgp(payload, CHIT_PASSPHRASE):
```

**Context (lines 143-160):** The verify_cgp call is guarded by `CHIT_REQUIRE_SIGNATURE` env var. If enabled, it imports verify_cgp and decrypt_anchors from the canonical chit_security module, checks CHIT_PASSPHRASE is set, verifies the CGP signature, and optionally decrypts anchors. On failure it raises HTTP 401.

**Caveats:**
- Guarded by `CHIT_REQUIRE_SIGNATURE` environment variable (defaults to "false" per tracker own blocker note)
- No `sign_cgp()` call (service is a verifier/consumer, which is architecturally appropriate)
- This is the **only** 'Full' service that actually imports and calls the canonical `chit_security.verify_cgp()`

**Conclusion:** VERIFIED -- actual canonical verify_cgp call exists, but effectively disabled by default configuration.

---

### 3. Gateway -- PARTIAL

**Service directory:** `pmoves/services/gateway/`

**Files examined:**
- `gateway/api/chit.py` (280+ lines) -- Main CHIT API endpoint
- `scripts/chit_sign.py` (77 lines) -- Standalone signing script

**Findings:**
- `gateway/api/chit.py` defines its OWN `verify_hmac()` function with inline HMAC-SHA256 -- does NOT import from chit_security.py
- `scripts/chit_sign.py` defines its OWN `hmac_sign()` function -- separate duplicate implementation
- **Neither file imports** `sign_cgp`, `verify_cgp`, `chit_security`, or `chit_security_validator`
- Gateway uses its own `canon()` function (different from chit_security.py canon())
- Gateway anchor decryption uses PBKDF2HMAC (600K iterations) while chit_sign.py uses scrypt -- **mutually incompatible** (confirmed in prior crypto audit)

**Why PARTIAL not VERIFIED:**
- The gateway performs HMAC verification and AES-GCM anchor decryption, which is CHIT-like security
- However, it does NOT use the canonical `chit_security.py` module -- it has a **duplicate implementation**
- Duplicate crypto implementations create signature drift risk (different canon() functions, different KDFs in signing vs decryption scripts)
- No call to the actual `sign_cgp()` or `verify_cgp()` functions from the canonical module

**Conclusion:** PARTIAL -- has inline crypto that performs similar operations but does not integrate with the canonical chit_security module.

---

### 4. Neo4j Mind Map -- REFUTED

**Possible service directories searched:**
- `PMOVES-Neo4j/` (submodule) -- **zero** matches for any CHIT term
- `pmoves/services/graph-linker/` (contains neo4j_client.py) -- **zero** matches
- `pmoves/neo4j/` (data/scripts directory) -- not a service
- No `pmoves/services/neo4j*` directory exists

**Findings:**
- No service directory for "Neo4j Mind Map" exists in the services tree
- The PMOVES-Neo4j submodule contains no Python files with CHIT references
- The graph-linker service (which has the Neo4j client) has no CHIT integration
- Neo4j is used as a data store by other services but none constitutes "Neo4j Mind Map" having CHIT integration

**Conclusion:** REFUTED -- no service code, no CHIT calls, no integration of any kind.

---

### 5. Agent Zero -- REFUTED

**Service directory:** `pmoves/services/agent-zero/`

**Files examined:**
- `main.py`, `mcp_server.py`, `python/checkpointing.py`
- `python/events/subjects.py`, `python/gateway/*.py`

**Findings:**
- `mcp_server.py:20` imports `CGP_SPEC_VERSION` from `pmoves.chit` (a version constant string only)
- `mcp_server.py:66-104` defines HTTP client functions that POST CGP data **to the gateway**:
  - `geometry_publish_cgp()` -> POST to `{GATEWAY_URL}/geometry/event`
  - `geometry_decode_text()` -> POST to `{GATEWAY_URL}/geometry/decode/text`
  - `geometry_calibration_report()` -> POST to `{GATEWAY_URL}/geometry/calibration/report`
- Agent Zero is a CHIT **consumer via HTTP proxy** -- it sends unsigned CGP payloads to the gateway and relies on the gateway to verify
- No `sign_cgp()` or `verify_cgp()` call anywhere in the service
- No import of `chit_security` or `chit_security_validator`
- Imports from `services.common` are limited to: bootstrap, env, config, tensorzero, forms, nats_service_listener, service_registry -- none include CHIT functions

**Conclusion:** REFUTED -- Agent Zero sends CGP data to the gateway over HTTP but performs no local CHIT signing or verification. It is a CHIT protocol consumer, not a CHIT security integrant.

---

## Additional Finding: CHIT Security is Globally Disabled

The hardening tracker itself states under "Remaining Configuration Blockers":

> **CHIT Security Disabled (passphrase/signatures)** -- CRITICAL -- Requires configuration

This means that even the one VERIFIED service (Hi-RAG v2) has its `verify_cgp()` call gated behind `CHIT_REQUIRE_SIGNATURE=false` by default, making it a no-op in practice. The Gateway verify_hmac() is similarly gated behind the same env var.

---

## Raw Grep Output (Appendix)

### sign_cgp call sites (all directories)

```
pmoves/tools/chit_security.py:24:def sign_cgp(cgp: Dict[str, Any], passphrase: str, kid: str | None = None) -> Dict[str, Any]:
pmoves/tools/chit_security.py:92:    return sign_cgp(doc, passphrase, kid=kid)
pmoves/tools/chit_security.py:124:    "sign_cgp",
pmoves/tools/chit_credential_demo.py:83:        from pmoves.tools.chit_security import sign_cgp
pmoves/tools/chit_credential_demo.py:84:        cgp = sign_cgp(cgp, args.passphrase)
pmoves/tools/sign_trail.py:33:from tools.chit_security import sign_cgp  # noqa: E402
pmoves/tools/sign_trail.py:178:        payload = sign_cgp(payload, passphrase)
pmoves/services/common/__init__.py:61:        sign_cgp,
pmoves/services/common/__init__.py:85:        "sign_cgp",
pmoves/services/common/geometry_decoder.py:183:def sign_cgp(
pmoves/services/common/geometry_decoder.py:503:    return sign_cgp(doc, passphrase, kid)
pmoves/services/common/geometry_decoder.py:1159:    "sign_cgp",
pmoves/services/common/chit_lanes.py:51:    sign_cgp,
pmoves/services/consciousness-service/chr_algorithm.py:42:def sign_cgp(cgp: Dict[str, Any], passphrase: str, kid: Optional[str] = None) -> Dict[str, Any]:
pmoves/services/consciousness-service/chr_algorithm.py:428:    return sign_cgp(cgp, passphrase=passphrase)
```

### verify_cgp call sites (all directories)

```
pmoves/tools/chit_security_validator.py:44:    from pmoves.tools.chit_security import verify_cgp, decrypt_anchors
pmoves/tools/chit_security_validator.py:347:                    if not verify_cgp(cgp, self.passphrase):
pmoves/tools/chit_security.py:35:def verify_cgp(cgp: Dict[str, Any], passphrase: str) -> bool:
pmoves/tools/chit_security.py:125:    "verify_cgp",
pmoves/tools/chit_credential_demo.py:104:            from pmoves.tools.chit_security import verify_cgp
pmoves/tools/chit_credential_demo.py:105:            if verify_cgp(cgp, args.passphrase):
pmoves/services/common/__init__.py:62:        verify_cgp,
pmoves/services/common/__init__.py:86:        "verify_cgp",
pmoves/services/common/geometry_decoder.py:242:def verify_cgp(
pmoves/services/common/geometry_decoder.py:676:            signature_valid = verify_cgp(cgp_data, self._get_passphrase())
pmoves/services/common/geometry_decoder.py:1160:    "verify_cgp",
pmoves/services/hi-rag-gateway/gateway.py:780:                from tools.chit_security import verify_cgp, decrypt_anchors
pmoves/services/hi-rag-gateway/gateway.py:785:            if not verify_cgp(payload, CHIT_PASSPHRASE):
pmoves/services/hi-rag-gateway-v2/routes/geometry.py:148:            from tools.chit_security import verify_cgp, decrypt_anchors
pmoves/services/hi-rag-gateway-v2/routes/geometry.py:154:        if not verify_cgp(payload, CHIT_PASSPHRASE):
```

### chit_security imports (all directories)

```
pmoves/tools/chit_security_validator.py:44:    from pmoves.tools.chit_security import verify_cgp, decrypt_anchors
pmoves/tools/chit_credential_demo.py:83:        from pmoves.tools.chit_security import sign_cgp
pmoves/tools/chit_credential_demo.py:104:            from pmoves.tools.chit_security import verify_cgp
pmoves/services/hi-rag-gateway/gateway.py:780:                from tools.chit_security import verify_cgp, decrypt_anchors
pmoves/services/hi-rag-gateway-v2/routes/geometry.py:148:            from tools.chit_security import verify_cgp, decrypt_anchors
```

### chit_security_validator imports (all directories)

```
pmoves/tools/chit_security_validator.py:22:    from pmoves.tools.chit_security_validator import validate_cgp, CGPValidationError
pmoves/tools/chit_security_validator.py:446:        from pmoves.tools.chit_security_validator import GeometryEventValidator
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Services claimed "Full" | 5 |
| Services VERIFIED | 1 (Hi-RAG v2) |
| Services PARTIAL | 1 (Gateway -- duplicate impl) |
| Services REFUTED | 3 (Tokenism, Neo4j Mind Map, Agent Zero) |
| Total sign_cgp call sites (canonical module) | 2 (demo script, sign_trail.py) |
| Total verify_cgp call sites (canonical module) | 4 (validator, demo, hi-rag-gateway v1, hi-rag-gateway v2) |
| sign_cgp/verify_cgp calls in "Full" service dirs | 1 (hi-rag-gateway-v2 verify_cgp) |
| Duplicate sign_cgp definitions | 2 (consciousness-service, services/common/geometry_decoder) |
| Duplicate verify_hmac implementations | 1 (gateway/api/chit.py) |
| Duplicate canon() functions | 3 (chit_security.py, chit_sign.py, generate-enrollment.py) |

---

**Audit conclusion:** The "Full" CHIT integration claim for 5 services is accurate for 1 service (Hi-RAG v2), partially accurate for 1 (Gateway uses duplicate crypto), and false for 3 (Tokenism Simulator, Neo4j Mind Map, Agent Zero). The tracker should be corrected to reflect actual integration status. The CRITICAL blocker noting CHIT security is disabled further undermines the practical value of even the one verified integration.
