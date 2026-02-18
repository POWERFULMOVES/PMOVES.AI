# CodeRabbit Review Findings - PR #606

**Date:** 2026-02-09 00:43 UTC
**Reviewer:** CodeRabbit AI
**Status:** 12 actionable comments posted

---

## Summary

**Overall Assessment:** ⚠️ **Needs attention before merge**

CodeRabbit identified:
- **12 actionable comments** (code fixes needed)
- **3 nitpick comments** (optional improvements)
- **3 outside-diff comments** (documentation issues)

---

## Critical Issues (Action Required)

### 1. CGP v1.0 Specification - Validation Evidence Missing

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Lines:** 1-874

**Issue:** Document claims "Production Ready" but lacks validation evidence

**Fix Required:**
- Add "Validation & Testing" section with test artifacts
- Reference unit/integration tests in `pmoves/tests/chit/`
- Document NATS GEOMETRY_BUS integration tests
- Include security audit results for HMAC-SHA256/AES-GCM
- Add performance benchmarks for encoding/decoding

**Alternative:** Change status to "Release Candidate" until validation complete

---

### 2. Incorrect Parameter Name in Examples

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Lines:** 451-468

**Issue:** Example uses `corpus=` instead of `corpus_path=`

**Fix:**
```diff
- decode_cgp(..., corpus="corpus.jsonl", mode="geometry")
+ decode_cgp(..., corpus_path="corpus.jsonl", mode="geometry")
```

---

### 3. Missing CLI Commands Documented

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Lines:** 742-762

**Issue:** Spec lists `/chit:encode` and `chit_security` CLI that don't exist

**Fix Required:** Either:
1. Implement the missing CLIs, OR
2. Remove them from specification

---

### 4. Missing Backward Compatibility Tests

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Lines:** 770-784

**Issue:** No v0.2→v1.0 compatibility tests documented

**Fix Required:** Add tests that:
- Feed v0.2 packets into v1.0 decoder
- Assert optional v1.0 fields have correct defaults
- Test v1.0 encoder with v0.2 compatibility flag

---

### 5. Incorrect Import References

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Lines:** 339-404

**Issue:** Examples reference unimplemented classes:
- `ConstellationHarvest` (not under pmoves.tools.chr)
- `ZetaSpectralFilter` (should be ZetaInspiredFilter)
- `build_cgp` (unified API doesn't exist)

**Fix Required:** Mark examples as "planned/unimplemented" or correct references

---

### 6. Weak PBKDF2 Iteration Count

**File:** `pmoves/docs/PMOVESCHIT/CGP_v1.0_SPECIFICATION.md`
**Line:** 573

**Issue:** 100,000 iterations is below OWASP recommendation (600,000)

**Fix:**
```diff
- PBKDF2-HMAC-SHA256 with 100,000 iterations
+ PBKDF2-HMAC-SHA256 with 600,000 iterations
```

---

### 7. Implement CGP v1.0 in Roadmap

**File:** `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md`
**Lines:** 229-238

**Issue:** Q2 2026 still has "CGP v1.0 specification" as todo

**Fix:** Move to Q1 2026 with checkmark, mark complete

---

### 8. Wrong Parameter in Docstring Examples

**File:** `pmoves/tools/chit/__init__.py`
**Lines:** 9-12

**Issue:** Docstrings use `corpus=` instead of `corpus_path=`

**Fix:** Update examples to match function signatures

---

### 9. Missing Return Type Documentation

**File:** `pmoves/tools/chit/chit_decoder_mm.py`
**Lines:** 95-124

**Issue:** `encode_images` returns tuple but declares `np.ndarray`

**Fix:**
```diff
- def encode_images(...) -> np.ndarray:
+ def encode_images(...) -> Tuple[np.ndarray, List[str]]:
```

---

### 10. Hardcoded Coverage Value

**File:** `pmoves/tools/chit/chit_decoder.py`
**Lines:** 307-370

**Issue:** `compute_metrics` hardcodes coverage=50, ignores CGP metadata

**Fix:** Read from `cgp.meta.per_constellation`

---

### 11. Missing corpus_idx in Decoded Items

**File:** `pmoves/tools/chit/chit_decoder.py`
**Lines:** 260-268

**Issue:** `geometry_only_decode` doesn't include `corpus_idx` in output

**Fix:** Add `"corpus_idx": i` to each decoded item

---

## Documentation Issues

### 12. Executive Summary Conflict

**File:** `pmoves/docs/PRODUCTION_READINESS_AUDIT_2026-02-07.md`
**Lines:** 10-20

**Issue:** Summary says "production-ready" but validation checks show "in progress"

**Fix:** Align summary to reflect actual status

---

### 13. CGP v1.0 Status Inconsistency

**File:** `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md`
**Lines:** 99-103

**Issue:** Table shows CGP v1.0 as "⏳ Draft" but spec says "Production Ready"

**Fix:** Update table to match spec status

---

### 14. Outdated Roadmap Documents

**File:** `pmoves/docs/PMOVESCHIT/IMPLEMENTATION_STATUS.md`
**Lines:** 3-247

**Issue:** ROADMAP.md and NEXT_STEPS.md not updated for Q1 2026 completions

**Fix:** Refresh both files with current sprint progress

---

## Nitpicks (Optional)

1. **Bootstrap Script Regex Centralization** (`scripts/bootstrap_credentials.sh:629`)
   - Define single `ENV_VAR_RE` regex for consistency

2. **Documentation Cross-References** (`IMPLEMENTATION_STATUS.md:158-162`)
   - Update decoder status from "Spec only" to "Complete"

3. **Automated Validation Checklist** (`CGP_v1.0_SPECIFICATION.md:787-797`)
   - Consider implementing validation script for production checks

---

## Recommended Action Plan

### Before Merge (Critical)
1. Fix parameter names in examples (#2, #8)
2. Add missing corpus_idx (#11)
3. Fix hardcoded coverage (#10)
4. Update return type docs (#9)
5. Update PBKDF2 to 600k iterations (#6)
6. Align status inconsistencies (#12, #13, #7)

### Post-Merge (Technical Debt)
1. Implement missing CLIs or remove from spec (#3)
2. Add validation section to CGP spec (#1)
3. Add backward compatibility tests (#4)
4. Correct import references or mark as planned (#5)
5. Refresh ROADMAP.md and NEXT_STEPS.md (#14)

### Code Quality Improvements
1. Centralize env var regex (#1 nitpick)
2. Update documentation cross-references (#2 nitpick)
3. Consider automated validation script (#3 nitpick)

---

**Learnings for Future:**

1. **Status Consistency:** Ensure all documentation files agree on implementation status
2. **Example Code:** All code examples in specs should be tested
3. **Security Parameters:** Use OWASP recommendations for crypto parameters
4. **Type Annotations:** Return types must match actual implementation
5. **Documentation Updates:** Refresh roadmap docs when milestones complete
