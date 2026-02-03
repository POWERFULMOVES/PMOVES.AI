# PR #337: GPU Orchestrator - VRAM Management for RTX 5090

**Date:** 2025-12-22
**PR:** #337 (feat(gpu): Dynamic VRAM management for RTX 5090)
**Source:** CodeRabbit review, linting findings

---

## 1. Exception Handling Best Practices

### Pattern: Use logging.exception() Not logging.error()

```python
# BAD: Loses stack trace
try:
    model = load_model(model_id)
except Exception as e:
    logging.error(f"Failed to load model: {e}")  # No stack trace!

# GOOD: Captures full stack trace automatically
try:
    model = load_model(model_id)
except Exception:
    logging.exception("Failed to load model")  # Stack trace included
```

### Pattern: Avoid Blind Exception Catches

```python
# BAD: Catches everything, hides bugs
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure!

# BETTER: Catch specific exceptions
try:
    result = risky_operation()
except ConnectionError:
    logging.warning("Connection failed, retrying...")
    result = retry_operation()
except ValidationError as e:
    logging.error("Validation failed: %s", e)
    raise
except Exception:
    logging.exception("Unexpected error in risky_operation")
    raise  # Re-raise unexpected errors
```

### Ruff Codes

| Code | Issue | Fix |
|------|-------|-----|
| BLE001 | Blind exception catch | Catch specific exceptions |
| TRY300 | Try-except inside loop | Move try-except outside or use helper |
| TRY400 | logging.error with exception | Use logging.exception() |

---

## 2. __all__ Export Ordering

### Pattern: Alphabetical Sorting

```python
# BAD: Random order
__all__ = [
    "FastAPI",
    "APIRouter",
    "HTTPException",
]

# GOOD: Alphabetically sorted (Ruff RUF022)
__all__ = [
    "APIRouter",
    "FastAPI",
    "HTTPException",
]
```

### Why It Matters

- Consistent ordering across the codebase
- Easier to spot missing exports
- Reduces merge conflicts
- Standard Python convention

---

## 3. Unused Loop Variables

### Pattern: Underscore Prefix

```python
# BAD: Unused variable without underscore (Ruff B007)
for model_key in model_keys:
    process_all_models()  # model_key not used

# GOOD: Underscore indicates intentionally unused
for _model_key in model_keys:
    process_all_models()

# ALSO GOOD: Use enumerate index if needed
for i, _ in enumerate(model_keys):
    print(f"Processing model {i}")
```

---

## 4. GPU Service Architecture

### VRAM Tracking Pattern

```python
from dataclasses import dataclass
from typing import Optional
import pynvml


@dataclass
class VRAMStatus:
    """Real-time VRAM status from pynvml."""
    total_mb: int
    used_mb: int
    free_mb: int
    utilization_pct: float
    temperature_c: int

    @property
    def available_for_models(self) -> int:
        """VRAM available minus safety margin (2GB)."""
        return max(0, self.free_mb - 2048)


class VRAMTracker:
    """Track VRAM usage with process-to-container mapping."""

    def __init__(self):
        pynvml.nvmlInit()
        self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)

    def get_status(self) -> VRAMStatus:
        info = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
        temp = pynvml.nvmlDeviceGetTemperature(
            self._handle, pynvml.NVML_TEMPERATURE_GPU
        )
        return VRAMStatus(
            total_mb=info.total // (1024 * 1024),
            used_mb=info.used // (1024 * 1024),
            free_mb=info.free // (1024 * 1024),
            utilization_pct=util.gpu,
            temperature_c=temp,
        )
```

### Model Lifecycle Pattern

```python
from datetime import datetime, timedelta
from typing import Dict


@dataclass
class LoadedModel:
    """Tracks a loaded model's lifecycle."""
    provider: str  # ollama, vllm, tts
    model_id: str
    loaded_at: datetime
    last_used: datetime
    estimated_vram_mb: int


class ModelLifecycleManager:
    """Manage model loading with idle timeout."""

    def __init__(self, idle_timeout_minutes: int = 5):
        self._models: Dict[str, LoadedModel] = {}
        self._idle_timeout = timedelta(minutes=idle_timeout_minutes)

    def get_idle_models(self) -> list[LoadedModel]:
        """Get models that have been idle longer than timeout."""
        cutoff = datetime.now() - self._idle_timeout
        return [
            m for m in self._models.values()
            if m.last_used < cutoff
        ]

    def optimize(self) -> list[str]:
        """Unload idle models to free VRAM."""
        unloaded = []
        for model in self.get_idle_models():
            self._unload(model)
            unloaded.append(f"{model.provider}/{model.model_id}")
        return unloaded
```

---

## 5. Hardware Profile Configuration

### Pattern: YAML Model Registry

```yaml
# pmoves/config/gpu-models.yaml
models:
  ollama:
    gemma3:12b:
      vram_mb: 8192
      context_window: 8192
      quantization: q4_k_m
    qwen3-embedding:8b:
      vram_mb: 4700
      type: embedding

  vllm:
    qwen2.5:32b-instruct-q4_K_M:
      vram_mb: 18432
      context_window: 65536

  tts:
    kokoro:
      vram_mb: 1024
      type: synthesis
```

### Hardware Profiles

```yaml
# .claude/context/hardware-profiles.md
profiles:
  rtx5090:
    vram_gb: 32
    cuda_compute: 12.0
    recommended_batch_size: 16
    max_concurrent_models: 4

  rtx4090:
    vram_gb: 24
    cuda_compute: 8.9
    recommended_batch_size: 8
    max_concurrent_models: 3
```

---

## 6. NATS Event Subjects

### GPU Mesh Events

```python
# Subject patterns for GPU orchestration
SUBJECTS = {
    "status": "mesh.gpu.status.v1",
    "model_loaded": "mesh.gpu.model.loaded.v1",
    "model_unloaded": "mesh.gpu.model.unloaded.v1",
    "vram_alert": "mesh.gpu.vram.alert.v1",
}

# Example event payload
{
    "event": "model_loaded",
    "timestamp": "2025-12-22T10:00:00Z",
    "provider": "ollama",
    "model_id": "gemma3:12b",
    "vram_used_mb": 8192,
    "vram_remaining_mb": 23808,
}
```

---

## 7. Documentation Standards

### Code Block Language Specifiers

```markdown
<!-- BAD: No language -->
```
/model:load ollama/gemma3:12b
```

<!-- GOOD: With language specifier -->
```bash
/model:load ollama/gemma3:12b
```
```

### Table Formatting

```markdown
<!-- BAD: No blank lines -->
Some text
| Col1 | Col2 |
|------|------|
| A    | B    |
More text

<!-- GOOD: Blank lines around table -->
Some text

| Col1 | Col2 |
|------|------|
| A    | B    |

More text
```

---

## Related Files

| Path | Purpose |
|------|---------|
| `pmoves/services/gpu-orchestrator/` | FastAPI service (~800 lines) |
| `pmoves/config/gpu-models.yaml` | Model VRAM registry |
| `pmoves/docker/cuda-base/Dockerfile` | Shared CUDA 12.8.1 base |
| `.claude/commands/gpu/` | TAC commands |
| `.claude/context/hardware-profiles.md` | GPU fleet docs |

---

## Tags

`gpu` `vram` `orchestration` `pynvml` `exception-handling` `logging` `rtx5090`
