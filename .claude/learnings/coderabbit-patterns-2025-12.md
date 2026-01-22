# PMOVES.AI CodeRabbit Patterns - December 2025

**Date:** 2025-12-22
**Source:** Consolidated learnings from PRs #337-#345
**Purpose:** Quick reference for PMOVES development best practices

---

## Quick Reference Table

| Category | Pattern | Do | Don't |
|----------|---------|-----|-------|
| Docker | USER directive | Let entrypoint drop privileges | Set USER before entrypoint that needs root |
| Docker | Hostnames | Use lowercase (`pmoves.ai`) | Mixed case (`PMOVES.AI`) |
| Docker | PYTHONPATH | Set explicitly in Dockerfile | Assume imports will work |
| Python | Exceptions | `logging.exception()` | `logging.error(str(e))` |
| Python | Catches | Specific exceptions | Blind `except Exception` |
| Python | __all__ | Alphabetical order | Random order |
| Python | Loop vars | Prefix unused with `_` | Leave unused vars unnamed |
| Python | Dataclass | `@dataclass(frozen=True)` for immutables | NamedTuple with validation |
| Security | torch.load | `weights_only=True` | Default (arbitrary code exec) |
| Metrics | Prometheus | Module-level cache | Direct Counter() at import |
| Markdown | Code blocks | Include language specifier | Bare triple backticks |
| Markdown | Tables | Blank lines before/after | Inline with text |

---

## 1. Docker Best Practices

### Privilege Dropping

```dockerfile
# Entrypoint handles privilege drop
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 pmoves
COPY entrypoint.sh /entrypoint.sh
# NO USER directive - entrypoint uses su
ENTRYPOINT ["/entrypoint.sh"]
```

### PYTHONPATH for Shared Modules

```dockerfile
ENV PYTHONPATH=/app:$PYTHONPATH
COPY services/common /app/services/common
COPY services/myservice /app
```

### Consistent Hostnames

```yaml
# Always lowercase for DNS names
- SUPABASE_URL=http://supabase_kong_pmoves.ai:8000
```

---

## 2. Python Exception Handling

### Use logging.exception()

```python
try:
    result = risky_operation()
except SpecificError:
    logging.exception("Operation failed")  # Full stack trace
    raise
```

### Catch Specific Exceptions

```python
# Ordered from specific to general
try:
    data = fetch_data(url)
except ConnectionError:
    logging.warning("Connection failed, using cache")
    data = get_cached()
except ValidationError as e:
    logging.error("Invalid data: %s", e.message)
    raise
except Exception:
    logging.exception("Unexpected error")
    raise
```

---

## 3. Python Code Style

### __all__ Exports (Alphabetical)

```python
__all__ = [
    "APIRouter",
    "FastAPI",
    "HTTPException",
    "Request",
    "Response",
]
```

### Unused Loop Variables

```python
for _item in items:  # Underscore prefix for unused
    counter += 1
```

### Frozen Dataclass Over NamedTuple

```python
@dataclass(frozen=True)
class Config:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("value must be non-negative")
```

---

## 4. Prometheus Metrics

### Safe Registration Pattern

```python
_METRIC_CACHE: dict[str, Counter] = {}

def _get_or_create_counter(name: str, description: str, labels: tuple) -> Counter:
    if name in _METRIC_CACHE:
        return _METRIC_CACHE[name]
    try:
        counter = Counter(name, description, labelnames=labels)
        _METRIC_CACHE[name] = counter
        return counter
    except ValueError:
        logging.exception("Metric registration failed")
        raise
```

---

## 5. Security Patterns

### PyTorch Model Loading

```python
# Always use weights_only=True
state_dict = torch.load("model.pt", weights_only=True)
model.load_state_dict(state_dict)
```

### Non-Root Container Execution

```dockerfile
# Standard UID/GID for PMOVES
RUN groupadd -r pmoves --gid=65532 && \
    useradd -r -g pmoves --uid=65532 pmoves
# Application runs as pmoves, not root
```

---

## 6. Documentation Standards

### Code Blocks with Language

````markdown
```bash
curl http://localhost:8080/healthz
```

```python
import torch
model = torch.load("model.pt", weights_only=True)
```

```yaml
services:
  myservice:
    image: pmoves/myservice:latest
```
````

### Tables with Spacing

```markdown
Some context paragraph.

| Column | Description |
|--------|-------------|
| A      | First item  |
| B      | Second item |

Following paragraph.
```

---

## 7. GPU Orchestration

### VRAM Estimation

```yaml
# gpu-models.yaml
models:
  ollama:
    gemma3:12b:
      vram_mb: 8192
      quantization: q4_k_m
```

### Idle Model Cleanup

```python
# Unload models idle > 5 minutes
idle_timeout = timedelta(minutes=5)
for model in loaded_models:
    if model.last_used < datetime.now() - idle_timeout:
        unload(model)
```

---

## 8. Service Health Patterns

### Standard Health Endpoint

```python
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "myservice"}
```

### Metrics Endpoint

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## Ruff Codes Reference

| Code | Category | Description |
|------|----------|-------------|
| BLE001 | Exception | Blind exception catch |
| TRY300 | Exception | Try-except inside loop |
| TRY400 | Exception | logging.error with exception |
| B007 | Style | Unused loop variable |
| RUF022 | Style | __all__ not sorted |
| S104 | Security | Binding to 0.0.0.0 |

---

## Related Documents

- [PR #345 Learnings](pr345-phase2-hardening-2025-12.md) - Docker, Prometheus, DNS
- [PR #344 Learnings](pr344-pytorch-security-2025-12.md) - PyTorch CVE, CUDA
- [PR #337 Learnings](pr337-gpu-orchestrator-2025-12.md) - GPU, exceptions

---

## Tags

`best-practices` `docker` `python` `security` `prometheus` `gpu` `documentation`
