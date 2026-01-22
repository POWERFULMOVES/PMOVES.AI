# Prometheus Registry Double-Registration

**Date:** 2025-12-22
**Source:** PR #345 CodeRabbit review

## Issue

Direct access to `REGISTRY._names_to_collectors` is fragile:
1. Private API may change across prometheus_client versions
2. No type validation if metric with same name but different type exists
3. No labelnames validation

## Pattern

**Use try/except with type validation instead of direct private API access:**

```python
from prometheus_client import Counter, REGISTRY

def _get_or_create_counter(name: str, description: str, labelnames: tuple) -> Counter:
    """Get existing counter or create new one (safe for module reimport via -m flag)."""
    try:
        return Counter(name, description, labelnames=labelnames)
    except ValueError as e:
        if "Duplicated timeseries" in str(e):
            # Metric already exists; retrieve and validate type
            existing = REGISTRY._names_to_collectors.get(name)
            if existing is not None and isinstance(existing, Counter):
                return existing
            raise TypeError(
                f"Metric '{name}' exists but is {type(existing).__name__}, not Counter"
            ) from e
        raise
```

## Why This Matters

The `python -m` flag can cause double module import, registering metrics twice.
This helper safely handles the duplicate registration case while validating types.

## Anti-Pattern

```python
# Bad - no type validation, silent bugs if metric type differs
if name in REGISTRY._names_to_collectors:
    return REGISTRY._names_to_collectors[name]
return Counter(name, description, labelnames=labelnames)
```

## Related

- prometheus_client library documentation
- Python `-m` flag double-import behavior
