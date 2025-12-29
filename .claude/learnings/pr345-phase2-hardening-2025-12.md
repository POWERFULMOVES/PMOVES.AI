# PR #345: Phase 2 Hardening, Persistence & Python 3.11+ Fixes

**Date:** 2025-12-22
**PR:** #345 (fix: Phase 2 hardening, persistence, and Python 3.11+ fixes)
**Source:** CodeRabbit review comments

---

## 1. Docker USER Directive Timing

### The Issue

When a Dockerfile sets `USER pmoves` before the entrypoint, but the entrypoint script needs root privileges for operations like `chown` or `su`, the container will fail at runtime.

### Pattern: Entrypoint Privilege Dropping

```dockerfile
# BAD: Sets USER before entrypoint that needs root
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 pmoves
COPY entrypoint.sh /entrypoint.sh
USER pmoves  # <-- This breaks entrypoint.sh if it uses chown/su
ENTRYPOINT ["/entrypoint.sh"]
```

```dockerfile
# GOOD: Let entrypoint handle privilege dropping
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 pmoves
COPY entrypoint.sh /entrypoint.sh
# NOTE: Do NOT set USER here - entrypoint drops to pmoves via su
ENTRYPOINT ["/entrypoint.sh"]
```

### Entrypoint Script Pattern

```bash
#!/usr/bin/env sh
set -e

# Setup that needs root
mkdir -p /data
chown -R pmoves:pmoves /data 2>/dev/null || true

# Drop privileges and exec
exec su -s /bin/sh pmoves -c "exec uvicorn app:app --host 0.0.0.0 --port 8095"
```

### When to Use This Pattern

- Services that write to mounted volumes (need chown on first run)
- Services that need dynamic permission setup
- Any container using named volumes that Docker creates as root

---

## 2. Prometheus Metric Registration (Safe for Module Reimport)

### The Issue

When running Python with `python -m module`, the module may be imported twice, causing `ValueError: Duplicated timeseries in CollectorRegistry`.

### Pattern: Module-Level Cache

```python
from prometheus_client import Counter, REGISTRY

# Module-level cache avoids private registry API access
_METRIC_CACHE: dict[str, Counter] = {}


def _get_or_create_counter(name: str, description: str, labelnames: tuple) -> Counter:
    """Get existing counter or create new one (safe for module reimport).

    Args:
        name: Metric name (must be unique in Prometheus registry).
        description: Human-readable description.
        labelnames: Tuple of label names.

    Returns:
        Counter instance (newly created or cached).
    """
    if name in _METRIC_CACHE:
        return _METRIC_CACHE[name]

    try:
        counter = Counter(name, description, labelnames=labelnames)
        _METRIC_CACHE[name] = counter
        return counter
    except ValueError as e:
        # Already registered - log and try fallback
        logging.warning("Metric %s already registered: %s", name, e)
        if hasattr(REGISTRY, "_names_to_collectors"):
            cached = REGISTRY._names_to_collectors.get(name)
            if cached:
                _METRIC_CACHE[name] = cached
                return cached
        raise


# Usage
REQUEST_COUNTER = _get_or_create_counter(
    "myservice_requests_total",
    "Total requests processed",
    labelnames=("status", "method"),
)
```

### Why This Matters

- Worker processes run via `python -m worker`
- Module gets imported once for parsing, once for execution
- Without this pattern, second import raises ValueError
- Private API `REGISTRY._names_to_collectors` used only as fallback

---

## 3. Docker DNS Hostname Casing

### The Issue

Mixed case hostnames in docker-compose environment variables cause confusion and potential resolution issues.

### Pattern: Always Use Lowercase

```yaml
# BAD: Mixed case
- SUPABASE_URL=http://supabase_kong_PMOVES.AI:8000
- SUPABASE_REALTIME_URL=ws://supabase_kong_PMOVES.AI:8000/realtime/v1

# GOOD: Consistent lowercase (DNS convention)
- SUPABASE_URL=http://supabase_kong_pmoves.ai:8000
- SUPABASE_REALTIME_URL=ws://supabase_kong_pmoves.ai:8000/realtime/v1
```

### Why This Matters

- DNS names are case-insensitive for resolution
- But string comparisons in code are case-sensitive
- Health checks that compare hostnames may fail
- Consistency prevents debugging confusion

---

## 4. NamedTuple to Frozen Dataclass Migration

### The Issue

Python 3.11+ has stricter handling of NamedTuple with `__post_init__` validation.

### Pattern: Use Frozen Dataclass

```python
# BEFORE: NamedTuple (problematic in Python 3.11+)
class PauseConfig(NamedTuple):
    pause_ms: float
    breath_probability: float

    def __post_init__(self):  # This doesn't work reliably
        if self.pause_ms < 0:
            raise ValueError("pause_ms must be non-negative")


# AFTER: Frozen dataclass (Python 3.11+ compatible)
from dataclasses import dataclass


@dataclass(frozen=True)
class PauseConfig:
    """Configuration for prosodic pause behavior."""
    pause_ms: float
    breath_probability: float

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.pause_ms < 0:
            raise ValueError(f"pause_ms must be non-negative, got {self.pause_ms}")
        if not 0.0 <= self.breath_probability <= 1.0:
            raise ValueError(
                f"breath_probability must be in [0.0, 1.0], got {self.breath_probability}"
            )
```

### Benefits

- Full validation support in `__post_init__`
- Immutable by default with `frozen=True`
- Better IDE support and type checking
- Works consistently across Python 3.11+

---

## 5. PYTHONPATH for Multi-Service Projects

### The Issue

Containerized services fail to import shared modules from `services/common/`.

### Pattern: Explicit PYTHONPATH in Dockerfile

```dockerfile
FROM python:3.11-slim

# Set PYTHONPATH to include app root
ENV PYTHONPATH=/app:$PYTHONPATH

WORKDIR /app

# Copy shared modules first (better layer caching)
COPY services/common /app/services/common
COPY services/media-video /app

# Install dependencies
RUN pip install -r requirements.txt

# Now imports like `from services.common.events import envelope` work
```

### Apply To

- media-audio
- media-video
- Any service importing from `services/common/`

---

## Related Commits

| Hash | Description |
|------|-------------|
| `3dc29b9e` | Address PR #345 CodeRabbit review comments |
| `90ec3503` | Archon Supabase connectivity and UI dashboard fixes |
| `eb6d14e4` | Harden notebook-sync and vibevoice-realtime |

---

## Tags

`docker` `prometheus` `python311` `security` `dataclass` `hardening`
