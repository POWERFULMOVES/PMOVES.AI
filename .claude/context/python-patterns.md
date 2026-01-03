# Python Code Patterns for PMOVES.AI

> Consolidated learnings from CodeRabbit PR reviews. These patterns help avoid common issues caught during code review.

## HTTP Method Semantics

**Priority: Critical** | Source: PR #385 github-runner-ctl client.py

Different HTTP methods return different status codes and body formats. Always handle these correctly:

| Method | Success Status | Body | Return Value |
|--------|----------------|------|--------------|
| GET | 200 OK | JSON | `Dict[str, Any]` |
| POST | 201 Created | JSON | `Dict[str, Any]` |
| PUT | 200 OK | JSON | `Dict[str, Any]` |
| DELETE | 204 No Content | **Empty** | `None` |

```python
# ✅ Correct - handle 204 No Content
async def _request(self, method: str, path: str, **kwargs) -> Optional[Dict[str, Any]]:
    response = await client.request(method, path, **kwargs)

    # Track metrics BEFORE status checks
    status = str(response.status_code)
    REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()

    # Handle 204 No Content (DELETE responses)
    if response.status_code == 204:
        return None

    response.raise_for_status()
    return response.json()

# ❌ Wrong - JSONDecodeError on DELETE
async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
    response = await client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()  # Crashes on 204 No Content!
```

## Metrics Hygiene

**Priority: High** | Source: PR #385 github-runner-ctl client.py

Follow these rules for Prometheus metrics:

1. **Increment exactly once** per request
2. **Increment AFTER determining final status**
3. **Never increment in both try AND except blocks**
4. **Use `logger.exception`** instead of `logger.error` for stack traces

```python
# ✅ Correct - single increment, final status
try:
    response = await client.request(method, path, **kwargs)
    status = str(response.status_code)
    REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()
    response.raise_for_status()
    if response.status_code == 204:
        return None
    return response.json()
except httpx.HTTPStatusError as e:
    REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(e.response.status_code)).inc()
    logger.exception(f"API error: {e.response.status_code} {path}")
    raise
except httpx.RequestError as e:
    REQUESTS_TOTAL.labels(endpoint=endpoint, status="network_error").inc()
    logger.exception(f"Request failed: {path}")
    raise

# ❌ Wrong - double increment on errors
REQUESTS_TOTAL.labels(endpoint=endpoint, status="200").inc()  # ✗ Premature!
try:
    response = await client.request(method, path, **kwargs)
    return response.json()
except Exception:
    REQUESTS_TOTAL.labels(endpoint=endpoint, status="error").inc()  # ✗ Double count!
    raise
```

## Query Parameter Consistency

**Priority: Medium** | Source: PR #385 github-runner-ctl client.py

Always use the `params` dict for query parameters, never embed them in the URL path:

```python
# ✅ Correct - all params in dict
path = "/user/repos"
params = {"type": "owner", "per_page": 30}
return await self._request("GET", path, params=params)

# ❌ Wrong - split query params
path = "/user/repos?type=owner"  # ✗ Harder to maintain
params = {"per_page": 30}
return await self._request("GET", path, params=params)
```

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

*Last updated: 2025-12-30 from PR #385 (HTTP semantics, metrics hygiene)*
