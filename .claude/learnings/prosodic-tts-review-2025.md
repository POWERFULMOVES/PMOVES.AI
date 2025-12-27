# CodeRabbit Review Learnings: Prosodic TTS (December 2025)

**Review Period:** December 18, 2025
**PR Reviewed:** #328 (Prosodic Sidecar TTS)
**Commit:** 37d8e0ce (Review Fixes)
**Reviewer:** CodeRabbit AI

## Executive Summary

This document captures key learnings from CodeRabbit's review of the prosodic TTS feature in flute-gateway. The reviews identified patterns for code safety, Python modernization, and endpoint security that should inform future backend development.

---

## Key Patterns

### 1. Never Use list.index() with NumPy Arrays

**Issue:** Using `list.index(numpy_array)` to find array positions is fragile and unreliable.

```python
# ❌ WRONG - numpy arrays don't work reliably with list.index()
audio_chunks = [first_audio]
for chunk in chunks[1:]:
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    audio_chunks.append(audio)
    # This fails because numpy array equality is element-wise
    boundaries.append(chunks[audio_chunks.index(audio) - 1].boundary_after)
```

**Why it fails:**
- `list.index()` uses `==` comparison
- NumPy arrays return element-wise boolean arrays on `==`, not scalar `True/False`
- This causes `ValueError` or incorrect results depending on Python version

**Fix:** Use `enumerate()` to track indices explicitly:

```python
# ✅ CORRECT - track index with enumerate
for chunk_idx, chunk in enumerate(chunks[1:], start=1):
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    audio_chunks.append(audio)
    boundaries.append(chunks[chunk_idx - 1].boundary_after)
```

**Lesson:** When iterating and building parallel lists, use `enumerate()` for explicit index tracking instead of searching with `index()`.

---

### 2. Authentication Consistency for Related Endpoints

**Issue:** New endpoints must match the authentication pattern of related endpoints.

```python
# ❌ INCONSISTENT - analyze has no auth but synthesize does
@app.post("/v1/voice/analyze/prosodic")
async def analyze_prosodic(request):  # No auth!
    ...

@app.post("/v1/voice/synthesize/prosodic", dependencies=[Depends(verify_api_key)])
async def synthesize_prosodic(request):  # Has auth
    ...
```

**Fix:** Add authentication to all related endpoints:

```python
# ✅ CONSISTENT - both endpoints require auth
@app.post("/v1/voice/analyze/prosodic", dependencies=[Depends(verify_api_key)])
async def analyze_prosodic(request):
    ...

@app.post("/v1/voice/synthesize/prosodic", dependencies=[Depends(verify_api_key)])
async def synthesize_prosodic(request):
    ...
```

**Lesson:** When adding new API endpoints, check if similar endpoints use authentication and match the pattern. An analysis endpoint that reveals internal chunking structure should require auth just like the synthesis endpoint.

---

### 3. Exception Chaining (Ruff B904)

**Issue:** Catching an exception and raising a new one without chaining loses the original traceback.

```python
# ❌ WRONG - original exception lost
except Exception:
    logger.exception("Prosodic TTS synthesis failed")
    raise HTTPException(status_code=500, detail="Prosodic TTS synthesis failed")
```

**Fix options:**

```python
# Option A: Chain with original exception (preserves traceback in logs)
except Exception as exc:
    logger.exception("Prosodic TTS synthesis failed")
    raise HTTPException(status_code=500, detail="Prosodic TTS synthesis failed") from exc

# Option B: Explicitly suppress (already logged, don't chain)
except Exception:
    logger.exception("Prosodic TTS synthesis failed")
    raise HTTPException(status_code=500, detail="Prosodic TTS synthesis failed") from None
```

**Lesson:** Use `from exc` to chain or `from None` to explicitly suppress. The linter (B904) flags bare raises in except blocks. Since we already log the exception, `from None` is appropriate here.

---

### 4. Code-Comment Consistency in Heuristics

**Issue:** Comments documenting behavior must match the actual code implementation.

```python
# ❌ INCONSISTENT - comment says -ne but code checks only "lr"
# Don't subtract for words ending in -le, -re, -ne where e is pronounced
if len(word) >= 2 and word[-2] not in "lr":  # Missing 'n'!
    count -= 1
```

**Fix:**

```python
# ✅ CONSISTENT - code matches comment
# Don't subtract for words ending in -le, -re, -ne where e is pronounced
if len(word) >= 2 and word[-2] not in "lrn":  # Includes 'n'
    count -= 1
```

**Lesson:** When documenting heuristics with examples, verify the code actually handles all documented cases. Reviewers will check comment-code consistency.

---

### 5. Remove Dead Code

**Issue:** Code that can never execute creates confusion and maintenance burden.

```python
# ❌ DEAD CODE - ellipsis "..." ends with ".", so line 52 always matches first
if re.search(r"[.!?]$", word):  # Line 52 - matches "..."
    return BoundaryType.SENTENCE

if word.endswith("..."):  # Line 56 - NEVER REACHED
    return BoundaryType.SENTENCE
```

**Fix:** Remove unreachable code and document why:

```python
# ✅ CLEAN - explain in comment, remove dead code
# Note: This also handles ellipsis (...) since it ends with '.'
if re.search(r"[.!?]$", word):
    return BoundaryType.SENTENCE
# Removed: ellipsis check (covered by sentence regex)
```

**Lesson:** Test your regex patterns to ensure they don't shadow subsequent checks. CodeRabbit flags unreachable code paths.

---

### 6. Python 3.11+ Type Hints

**Issue:** Using `List` from `typing` module is deprecated in Python 3.11+.

```python
# ❌ OLD STYLE (Python 3.9 compatibility)
from typing import List
def parse_prosodic(...) -> List[ProsodicChunk]:
    chunks: List[ProsodicChunk] = []
```

**Fix:** Use builtin `list[]` syntax:

```python
# ✅ MODERN STYLE (Python 3.11+)
def parse_prosodic(...) -> list[ProsodicChunk]:
    chunks: list[ProsodicChunk] = []
```

**Lesson:** For Python 3.11+ codebases, use builtin generics (`list[]`, `dict[]`, `set[]`) instead of importing from `typing`.

---

### 7. Unused Loop Variables (Ruff B007)

**Issue:** Loop variables that are never used should be prefixed with `_` or removed.

```python
# ❌ WARNING - 'i' is never used
for i, (chunk, boundary) in enumerate(zip(audio_chunks[1:], boundaries)):
    result = prosodic_stitch(result, chunk, boundary, ...)
```

**Fix:** Remove enumerate if index not needed:

```python
# ✅ CLEAN - no unused variable
for chunk, boundary in zip(audio_chunks[1:], boundaries, strict=True):
    result = prosodic_stitch(result, chunk, boundary, ...)
```

**Lesson:** If you don't need the index, don't use `enumerate()`. Also add `strict=True` to `zip()` for safety (Ruff B905).

---

### 8. Remove Redundant Imports

**Issue:** Local imports that shadow module-level imports create confusion.

```python
# At top of file
import wave  # Module-level import

# In function body - REDUNDANT
async def synthesize_prosodic(...):
    import wave  # ❌ Already imported at module level!
    with io.BytesIO(first_wav) as buf:
        with wave.open(buf, "rb") as wf:
            ...
```

**Fix:** Remove the redundant local import.

**Lesson:** After refactoring, scan for redundant imports. IDEs and linters like Ruff can catch these automatically.

---

## Checklist for Future Backend PRs

### NumPy/Array Safety
- [ ] Never use `list.index(numpy_array)` - use `enumerate()` instead
- [ ] Use explicit index tracking for parallel list construction

### Authentication
- [ ] New endpoints match auth pattern of related endpoints
- [ ] Analysis/debug endpoints have same auth as production endpoints

### Code Quality
- [ ] Exception chaining uses `from exc` or `from None` (B904)
- [ ] Comments match actual code behavior
- [ ] Dead code removed (unreachable branches)
- [ ] No redundant imports (local shadowing module-level)
- [ ] No unused loop variables (prefix with `_` or remove)

### Python Modernization (3.11+)
- [ ] Use `list[]` not `List[]` from typing
- [ ] Use `dict[]` not `Dict[]`
- [ ] Add `strict=True` to `zip()` when lengths must match (B905)

### Testing
- [ ] Syntax validation with `python3 -m py_compile`
- [ ] Service health checks pass

---

## Files Modified

| File | Changes |
|------|---------|
| `main.py` | Auth, boundary tracking x2, exception chaining, redundant import |
| `syllable_counter.py` | Silent-e heuristic consistency |
| `audio_processor.py` | Unused loop variable, strict zip |
| `boundary_detector.py` | Dead code removal |
| `prosodic_parser.py` | Modern type hints |

---

*Document Generated: December 18, 2025*
*PR: #328*
