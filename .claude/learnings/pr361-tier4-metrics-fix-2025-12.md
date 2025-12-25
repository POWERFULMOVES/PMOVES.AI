# PR #361 Tier 4 Metrics Fix - Learnings

**Date:** 2025-12-25
**PR:** #361 - feat: add Prometheus metrics to Tier 4 services
**Issue:** CRITICAL - Merged with undefined Prometheus metrics

---

## Problem

The PR changed code from using a simple dictionary for metrics:
```python
_metrics["messages_received"] += 1
```

To using Prometheus client metrics:
```python
messages_received.labels(SESSION_CONTEXT_SUBJECT).inc()
```

But **NEVER DEFINED** the `messages_received`, `messages_failed`, `kb_upserts_published`, or `messages_processed` Counter objects.

## Root Cause

The pattern "Import → Use" was followed but "Define" was skipped:

```python
# Import
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

# ... code ...

# Use (BUT NOT DEFINED!)
messages_received.labels(SESSION_CONTEXT_SUBJECT).inc()  # NameError!
```

## What CodeRabbit Caught

CodeRabbit's review (via Ruff F821) identified:
- **CRITICAL:** Missing Prometheus metric definitions (lines 20-43)
- **CRITICAL:** Missing histogram timing instrumentation (lines 218-277)
- **MEDIUM:** Remove unused `_metrics` dictionary (lines 38-43)

## Impact

When `session-context-worker` processes its first NATS message, it will crash with:
```text
NameError: name 'messages_received' is not defined
```

## Correct Pattern

**Import → Define → Use:**

```python
# 1. Import
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

# 2. Define (BEFORE use!)
messages_received = Counter(
    'service_messages_received_total',
    'Total number of messages received',
    ['subject']
)
processing_duration = Histogram(
    'service_processing_duration_seconds',
    'Time spent processing messages',
    ['context_type']
)

# 3. Use
async def handler(msg):
    messages_received.labels(subject).inc()
    start_time = time.time()
    try:
        # ... do work ...
        processing_duration.labels(context_type).observe(time.time() - start_time)
    except Exception:
        processing_duration.labels("error").observe(time.time() - start_time)
```

## Lessons Learned

1. **ALWAYS review ALL CodeRabbit comments before merging** - Even if CI passes
2. **F821 (undefined name) is a CRITICAL error** - Never merge with F821
3. **Follow the complete pattern** - Import → Define → Use, not Import → Use
4. **Test imports locally** - `python3 -m py_compile` catches undefined names at import time
5. **Remove dead code** - The old `_metrics` dictionary should have been removed

## Testing Checklist

Before merging PR with Prometheus metrics:

- [ ] All metrics defined before first use
- [ ] `python3 -m py_compile` passes
- [ ] Import test: `python3 -c "from prometheus_client import Counter, Histogram"`
- [ ] Metrics endpoint returns valid Prometheus format: `curl http://localhost:XXXX/metrics`
- [ ] All CodeRabbit comments addressed

## Related Files

- `pmoves/services/session-context-worker/main.py` - Fixed
- `pmoves/services/messaging-gateway/main.py` - Already correct in merge
