# PMOVES.AI Learnings Catalog - PR #606

**Date:** 2026-02-08
**Context:** CI migration, CHIT decoder implementation, CodeRabbit review
**Status:** ✅ **Documented**

---

## Development Process Learnings

### 1. Git Submodule Management

**Issue:** Submodules can get out of sync between branches, causing merge conflicts.

**Learning:**
- Always sync submodules to target branch before creating PRs
- Use `git submodule update --remote --merge` carefully (can cause conflicts)
- Better: `git submodule update --remote --checkout` for direct sync

**Prevention:**
```bash
# Before merge, check submodule differences
git ls-tree HEAD submodule_path
git ls-tree origin/target-branch submodule_path
```

---

### 2. Self-Hosted CI Runners

**Success:** All 16 workflows successfully migrated to self-hosted runners.

**Best Practices:**
- Label runners by purpose: `vps`, `ai-lab`, `gpu`
- Use composite labels: `[self-hosted, ai-lab, gpu]`
- Document runner hardware capabilities

**Watch Out:**
- Some workflows may need specific runners (e.g., GPU for CUDA builds)
- Local-only workflows (like `sync-secrets-local.yml`) will fail on runners

---

### 3. CHIT Decoder Implementation

**Success:** Complete decode pipeline implemented (encode→transmit→decode).

**Technical Decisions:**
- Used `sentence-transformers` for embeddings (not OpenAI)
- Geometry-only mode requires corpus for reconstruction
- Added calibration metrics (KL, JS, Wasserstein)

**Missing:** TAC command `/chit:encode` not yet implemented

---

### 4. CodeRabbit Integration

**Success:** Automated review caught 12 actionable issues.

**Learnings:**
- CodeRabbit catches parameter name mismatches between docs and code
- Type annotations must match actual return values
- Security parameters should reference OWASP guidelines
- Status consistency across multiple docs is critical

**Best Practice:**
- Run CodeRabbit early, iterate on fixes before final review
- Address "critical" issues before merge, document "nitpicks" for later

---

### 5. Documentation Consistency

**Issue:** Multiple docs claimed different statuses for same feature.

**Example:**
- IMPLEMENTATION_STATUS.md: CGP v1.0 = "⏳ Draft"
- CGP_v1.0_SPECIFICATION.md: Status = "Production Ready"

**Prevention:**
- Single source of truth for implementation status
- Cross-reference updates when changing status
- Use `_Last updated` timestamps in governance docs

---

### 6. Type Annotation Quality

**Issue:** `encode_images` declared `-> np.ndarray` but returned `(vecs, paths)`.

**Best Practice:**
```python
# Good
def foo() -> Tuple[ReturnType1, ReturnType2]:
    return result1, result2

# Bad
def foo() -> ReturnType1:  # Hides that tuple is returned
    return result1, result2
```

---

### 7. Security Parameter Defaults

**Issue:** PBKDF2 iterations at 100,000 (below OWASP 2024 recommendation).

**Reference:**
- OWASP 2024: 600,000 iterations for PBKDF2-HMAC-SHA256
- Update specs to reference standards with dates

---

## CI/CD Learnings

### 8. GHCR Image Builds

**CRITICAL ISSUE:** GHCR builds failing consistently - no images found.

**Investigation Required:**
- Verify `GH_PAT_PUBLISH` has `packages:write` scope
- Check if GHCR is enabled for organization
- Review workflow logs on runner

**Alternative:** Docker Hub as fallback

---

### 9. Workflow Trigger Configuration

**Success:** CodeQL correctly triggers only on `main` and `PMOVES.AI-Edition-Hardened`.

**Pattern:**
```yaml
on:
  push:
    branches: [ "main", "PMOVES.AI-Edition-Hardened" ]
  pull_request:
    branches: [ "main", "PMOVES.AI-Edition-Hardened" ]
```

**Note:** Feature branches skip CodeQL (expected behavior, not a bug)

---

## Code Quality Learnings

### 10. Hardcoded Values

**Issue:** `compute_metrics` hardcoded coverage=50, ignored CGP metadata.

**Pattern:**
```python
# Bad
coverage = len(idxs) / 50

# Good
per_const_target = cgp.get("meta", {}).get("per_constellation", 50)
coverage = len(idxs) / per_const_target
```

---

### 11. Missing Return Fields

**Issue:** `geometry_only_decode` didn't include `corpus_idx` in output.

**Impact:** Downstream `compute_metrics` couldn't map back to corpus.

**Prevention:**
- Document all fields returned by functions
- Include all fields needed by consumers
- Write tests that validate output structure

---

### 12. Docstring Example Accuracy

**Issue:** Examples used wrong parameter names (`corpus=` vs `corpus_path=`).

**Best Practice:**
- Test all code examples in documentation
- Use doctest to validate examples automatically
- Keep examples in sync with function signatures

---

## Project-Specific Learnings

### 13. CHIT Geometry Packet Specification

**Success:** CGP v1.0 spec created with all five mathematical pillars.

**Documented:**
1. Dirichlet Distributions (attribution weights)
2. Hyperbolic Geometry (Poincaré disk)
3. Merkle Proofs (integrity verification)
4. Zeta-Inspired Filtering (noise reduction)
5. Swarm Optimization (EvoSwarm consensus)

**Still Missing:**
- Backward compatibility tests (v0.2 → v1.0)
- Validation automation script
- Production field testing reports

---

### 14. NATS GEOMETRY_BUS Integration

**Success:** CHIT packets published via NATS.

**Subjects:**
- `tokenism.geometry.event.v1` - CGP events
- `geometry.packet.encoded.v1` - Encoded packets
- `geometry.packet.decoded.v1` - Decoded content

**Best Practice:**
- Document all subjects in central catalog
- Use versioning (`v1`) for breaking changes

---

## Testing Learnings

### 15. Metrics Computation

**Success:** Implemented KL divergence, JS divergence, Wasserstein-1D.

**Use Case:** Compare reconstructed spectrum to target spectrum.

**Calibration:**
- KL: Asymmetric divergence (target vs empirical)
- JS: Symmetric divergence (more stable)
- W1: Earth Mover's Distance (spatial)

---

### 16. Multi-Modal Decoding

**Success:** CLIP for images, CLAP for audio.

**Pattern:**
```python
# Encode images to embeddings
vecs, valid_paths = encode_images(image_paths, model)

# Decode by geometric matching
results = decode_images(cgp, image_dir, model_name="clip-ViT-B-32")
```

---

## Production Readiness Learnings

### 17. Status Claims vs Evidence

**Issue:** "Production Ready" claimed without validation evidence.

**Required Evidence:**
- Unit tests passing
- Integration tests documented
- Security audit completed
- Performance benchmarks measured

**Template:**
```markdown
## Validation & Testing

- Unit Tests: `pmoves/tests/chit/test_decoder.py` (✅ 95% coverage)
- Integration: `pmoves/tests/fresh_start/test_chit_integration.py`
- Security: `chit_security.py` HMAC-SHA256 verified
- Performance: 1000 packets/second encode, 500 packets/second decode
```

---

### 18. Backward Compatibility

**Issue:** No v0.2 → v1.0 compatibility tests documented.

**Required Tests:**
1. Feed v0.2 packets into v1.0 decoder (should work)
2. Verify optional v1.0 fields have correct defaults
3. Test v1.0 encoder with v0.2 compatibility flag

---

## Action Items for Future

### High Priority
1. **Fix GHCR builds** - Critical blocker for deployment
2. **Implement `/chit:encode` TAC command** - Missing from spec
3. **Add backward compatibility tests** - v0.2 → v1.0

### Medium Priority
4. **Automate validation checks** - Script for production readiness
5. **Refresh ROADMAP.md and NEXT_STEPS.md** - Align with Q1 completions
6. **Centralize env var regex** - Bootstrap script consistency

### Low Priority
7. **Add doctest validation** - Verify docstring examples
8. **Create field testing reports** - Real-world usage data

---

## Meta-Learnings

### About the Review Process

1. **Early code review catches more issues** - CodeRabbit found issues we missed
2. **Documentation consistency matters** - Status conflicts cause confusion
3. **Type safety helps** - Correct annotations prevent bugs
4. **Security standards evolve** - Stay current with OWASP guidelines

### About CI/CD

1. **Self-hosted runners give control** - But require maintenance
2. **Workflow triggers need careful thought** - Feature branches skip some checks
3. **Image builds need monitoring** - GHCR failures went undetected

### About CHIT Implementation

1. **Mathematical foundations are solid** - Five pillars well-defined
2. **Bridge between math and code** - Specs must match implementation
3. **Multi-modal is complex** - Different media types need different handling

---

**Catalog Maintained:** 2026-02-08
**Next Update:** After GHCR fix deployment
**Related Documents:**
- `CI_AUDIT_REPORT_2026-02-08.md`
- `CODERABBIT_REVIEW_606_2026-02-08.md`
- `pmoves-check-investigation.md`
