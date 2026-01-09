# Python Code Patterns for PMOVES.AI

> Consolidated learnings from CodeRabbit PR reviews. These patterns help avoid common issues caught during code review.

## Edge Case Guards

**Priority: High** | Source: PR #328 main.py:651

- Always check `len(result) > 0` before accessing `result[0]`
- Handle whitespace-only input explicitly with descriptive error
- Return appropriate HTTP 400 response, don't let IndexError propagate

```python
# ✅ Correct
chunks = parse_prosodic(text)
if not chunks:
    raise HTTPException(status_code=400, detail="Empty input")
first_chunk = chunks[0]

# ❌ Wrong - IndexError on empty input
chunks = parse_prosodic(text)
first_chunk = chunks[0]  # Crashes if text was whitespace
```

## Metrics & Observability

**Priority: High** | Source: PR #328 main.py:651, 873

- Increment success metrics AFTER the operation succeeds
- Track metrics for ALL code paths including re-raised exceptions
- Pattern: try → operation → success metrics
- Anti-pattern: metrics → try → operation

```python
# ✅ Correct - metrics after success
try:
    result = await process(data)
    REQUESTS_TOTAL.labels(endpoint="/api", status="200").inc()
    return result
except HTTPException as exc:
    REQUESTS_TOTAL.labels(endpoint="/api", status=str(exc.status_code)).inc()
    raise

# ❌ Wrong - metrics before we know outcome
REQUESTS_TOTAL.labels(endpoint="/api", status="200").inc()
try:
    result = await process(data)  # May fail!
    return result
```

## Loop Indexing

**Priority: Medium** | Source: PR #328 main.py:710, 786

- Use `enumerate(items, start=N)` for position tracking
- Use `zip(a, b, strict=True)` when lengths must match (Python 3.10+)
- Never use `list.index(item)` for position lookup during iteration

```python
# ✅ Correct - explicit index tracking
for i, (chunk, audio) in enumerate(zip(chunks[1:], audio_chunks[1:], strict=True), start=1):
    boundary = chunks[i-1].boundary_after
    result = stitch(result, audio, boundary)

# ❌ Wrong - fragile reverse lookup
for audio in audio_chunks[1:]:
    idx = audio_chunks.index(audio)  # O(n) each iteration, fails on duplicates
    boundary = chunks[idx - 1].boundary_after
```

## Exception Handling

**Priority: Medium** | Source: Ruff B904

- Use `raise NewException(...) from exc` to preserve stack trace
- Use `raise NewException(...) from None` to explicitly suppress context
- Always track metrics before re-raising HTTPException

```python
# ✅ Correct - preserves original traceback
try:
    data = json.loads(raw)
except json.JSONDecodeError as exc:
    raise HTTPException(status_code=400, detail="Invalid JSON") from exc

# ✅ Correct - explicitly suppresses context
try:
    value = cache[key]
except KeyError:
    raise HTTPException(status_code=404, detail="Not found") from None

# ❌ Wrong - loses original traceback (Ruff B904)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    raise HTTPException(status_code=400, detail="Invalid JSON")
```

## Type Hints (Python 3.11+)

**Priority: Low** | Source: PR #328 prosodic_parser.py

Use native generics instead of `typing` module imports:

```python
# ✅ Correct - Python 3.11+ native syntax
def process(items: list[str]) -> dict[str, int]:
    result: tuple[int, ...] = ()
    return {}

# ❌ Wrong - deprecated typing imports
from typing import List, Dict, Tuple
def process(items: List[str]) -> Dict[str, int]:
    result: Tuple[int, ...] = ()
    return {}
```

## Domain-Specific: Prosodic Processing

**Priority: Medium** | Source: PR #328 prosodic_parser.py:122

When forcing boundaries (e.g., breath points), preserve natural boundaries:

```python
# ✅ Correct - only override NONE boundaries
if syllables >= max_before_breath and len(words) >= 3:
    if boundary == BoundaryType.NONE:
        boundary = BoundaryType.BREATH
    should_break = True

# ❌ Wrong - overwrites natural CLAUSE/PHRASE boundaries
if syllables >= max_before_breath:
    boundary = BoundaryType.BREATH  # Loses comma/semicolon info!
    should_break = True
```

## Ruff Rules to Enforce

These rules should fail CI if violated:

| Rule | Description | Example |
|------|-------------|---------|
| B904 | Use `raise...from` in except blocks | `raise X from exc` |
| B905 | Use `strict=True` in zip() | `zip(a, b, strict=True)` |
| B007 | Rename unused loop vars | `for _i, x in enumerate(...)` |
| TRY301 | Avoid bare raise in try | Use explicit exception |
| UP006 | Use native type hints | `list[T]` not `List[T]` |

---

*Last updated: 2025-12-18 from PR #328 CodeRabbit review (19 issues, 4 rounds)*
