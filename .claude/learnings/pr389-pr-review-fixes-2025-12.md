# PR #389 Review Learnings

**Date**: 2025-12-31
**PR**: fix(a2ui-bridge): fix critical bugs, add testing, integrate Tokenism simulator
**Scope**: A2UI NATS Bridge, Tokenism Simulator, datetime migration

---

## 1. datetime.utcnow() Migration Pattern

### The Problem
- `datetime.utcnow()` is **deprecated in Python 3.12+**
- Returns *naive* datetime (no `tzinfo`) → causes bugs
- Breaks equality/comparison with timezone-aware datetimes
- ISO serialization inconsistent (missing `+00:00` suffix)

### The Fix
```python
# OLD (deprecated, naive datetime)
from datetime import datetime
now = datetime.utcnow()  # ❌ No timezone info

# NEW (timezone-aware)
from datetime import datetime, timezone
now = datetime.now(timezone.utc)  # ✅ Explicit UTC tzinfo
```

### Files Migrated (41 occurrences across 21 files)
- `pmoves/services/agent_zero/controller.py`
- `pmoves/services/botz-gateway/main.py` (7 occurrences)
- `pmoves/services/comfy-watcher/watcher.py`
- `pmoves/services/common/cgp_mappers.py`
- `pmoves/services/common/events.py`
- `pmoves/services/consciousness-service/cgp_mapper.py`
- `pmoves/services/consciousness-service/persona_gate.py`
- `pmoves/services/pdf-ingest/app.py`
- `pmoves/services/pmoves-yt/yt.py` (3 occurrences)
- `pmoves/services/publisher/publisher.py`
- `pmoves/services/retrieval-eval/eval_utils.py`
- `pmoves/services/session-context-worker/main.py` (3 occurrences)
- `pmoves/services/session-context-worker/test_transform.py` (3 occurrences)
- `pmoves/services/tensorzero-config-api/logging.py` (5 occurrences)
- `pmoves/integrations/archon/python/src/server/api_routes/*.py` (8 occurrences)
- `pmoves/scripts/bootstrap_env.py`
- `pmoves/tools/consciousness_build.py`
- `pmoves/tools/consciousness_harvester.py` (4 occurrences)
- `pmoves/tools/mini_cli.py`

### Impact
- ✅ Python 3.12+ compatibility
- ✅ Consistent ISO 8601 serialization across codebase
- ✅ Proper datetime equality/comparison behavior
- ✅ Better integration with NATS/JSON timestamp formats

---

## 2. Error Handling: Raise Exceptions vs Return False

### The Problem
Silent failures (returning `False`) allow bugs to hide and make failures ignorable:

```python
# BAD - Caller can ignore failure
async def publish_event(data):
    try:
        await nats.publish(subject, data)
        return True
    except Exception as e:
        logger.error(f"Failed: {e}")
        return False  # ❌ Callers often ignore this

# Caller ignores failure
result = await publish_event(data)  # Returns False, nothing happens
# Bug: event lost but code continues
```

### The Fix
Raise specific exceptions to force caller acknowledgment:

```python
# GOOD - Caller must handle failure
async def publish_event(data) -> None:
    """Publish event to NATS.

    Raises:
        ConnectionError: If NATS is not connected
        RuntimeError: If publish fails
    """
    if nc is None:
        raise ConnectionError("NATS not connected")

    try:
        await nc.publish(subject, data)
    except Exception as e:
        logger.error(f"Failed to publish: {e}")
        raise RuntimeError(f"NATS publish failed: {e}") from e

# Caller must handle or propagate
try:
    await publish_event(data)
except (ConnectionError, RuntimeError) as e:
    # Explicitly handle or fail fast
    raise HTTPException(status_code=503, detail=str(e))
```

### Pattern Applied To
- `pmoves/services/a2ui-nats-bridge/bridge.py::publish_a2ui_event()`
- `pmoves/services/tokenism-simulator/config/nats.py::NATSClient.connect()`
- `pmoves/services/tokenism-simulator/config/tensorzero.py::chat_completion()`

### Custom Exception Hierarchy
```python
# Base exception for TensorZero failures
class TensorZeroError(Exception):
    """Base exception for TensorZero failures."""
    pass

# Specific exception types
class TensorZeroHTTPError(TensorZeroError):
    def __init__(self, status_code: int, response_text: str):
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f"HTTP {status_code}: {response_text}")

class TensorZeroTimeoutError(TensorZeroError):
    """Timeout waiting for TensorZero."""
    pass
```

---

## 3. FastAPI Lifespan Pattern

### The Problem (Deprecated)
```python
# DEPRECATED - @app.on_event removed in FastAPI 0.100+
app = FastAPI()

@app.on_event("startup")
async def startup():
    await connect_nats()

@app.on_event("shutdown")
async def shutdown():
    await nats.close()
```

### The Fix (Modern)
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    await connect_nats()
    yield
    # Shutdown
    if nc:
        await nc.close()

app = FastAPI(
    title="Service Name",
    description="Description",
    version="1.0.0",
    lifespan=lifespan  # Pass lifespan context manager
)
```

### Pattern Applied To
- `pmoves/services/a2ui-nats-bridge/bridge.py`

### Benefits
- ✅ Explicit startup/shutdown ordering
- ✅ Type-safe (IDE autocomplete)
- ✅ Cleanup guaranteed by context manager protocol
- ✅ Compatible with FastAPI 0.100+

---

## 4. Security: No Hardcoded Secrets

### The Problem
```python
# BAD - Predictable default secret
SECRET_KEY = os.getenv('SECRET_KEY', 'pmoves-tokenism-secret')
```

### The Fix
```python
import secrets

# GOOD - Auto-generated secure random key with warning
SECRET_KEY = os.getenv('SECRET_KEY') or secrets.token_hex(32)
if not os.getenv('SECRET_KEY'):
    logger.warning(
        "Using auto-generated SECRET_KEY - set explicitly for production. "
        "This key will change on restart, invalidating existing sessions."
    )
```

### Pattern Applied To
- `pmoves/services/tokenism-simulator/config/__init__.py`

---

## 5. Security: Restrict CORS Origins

### The Problem
```python
# BAD - Allows any origin
CORS(app, resources={r"/*": {"origins": "*"}})
```

### The Fix
```python
# GOOD - Configurable allowlist
allowed_origins = os.getenv(
    'ALLOWED_ORIGINS',
    'http://localhost:3000,http://localhost:8080,http://localhost:4000'
).split(',')
CORS(app, resources={r"/*": {"origins": allowed_origins}})
```

### Pattern Applied To
- `pmoves/services/tokenism-simulator/app.py`

---

## 6. Configuration: Relative Path Resolution

### The Problem
```python
# BAD - Hardcoded absolute path
load_dotenv('/home/pmoves/PMOVES.AI/pmoves/env.shared')
```

### The Fix
```python
from pathlib import Path

# GOOD - Resolves relative to current file
env_path = Path(__file__).resolve().parents[2] / "pmoves" / "env.shared"
if env_path.exists():
    load_dotenv(env_path)
else:
    logger.warning(f"Environment file not found: {env_path}")
```

### Pattern Applied To
- `pmoves/services/tokenism-simulator/config/__init__.py`

---

## CodeRabbit Nitpicks (Future Improvements)

### 1. Document Error ID Immutability
```diff
 /**
  * Error ID constants for log aggregation (Loki).
  * Each unique error type gets a stable ID for tracking and alerting.
+ *
+ * IMPORTANT: Once an error ID is in use, its value should never be changed
+ * to preserve historical tracking and alert continuity in Loki.
  *
  * Usage: logError(message, error, 'error', { errorId: ErrorIds.* })
  */
```

### 2. Top-Level Error ID in Structured Logs
Extract `errorId` as top-level field for better Loki queryability:
```typescript
interface StructuredLogEntry {
  timestamp: string;
  level: ErrorSeverity;
  message: string;
  error?: { name: string; message: string; stack?: string; };
  errorId?: ErrorId;  // Top-level for easier filtering
  component?: string;
  action?: string;
  context?: Record<string, unknown>;
}
```

### 3. Use Helper Function Consistently
Instead of inline message construction:
```typescript
// Use this
const message = getErrorMessage(response.status);

// Instead of this
const message = `HTTP ${response.status}: Failed to fetch`;
```

---

## Testing Patterns

### WebSocket Testing
Direct WebSocket testing is complex. For unit tests, verify:
- Route is registered (`app.routes`)
- Handler is a WebSocket route (`route.websocket`)
- Event type validation

### CHIT Encoding Round-Trip Tests
```python
def test_encode_decode_roundtrip():
    """Test CGP packet survives encode/decode cycle."""
    original = CGPPacket(cgp_version="1.0", packet_type="simulation_result", ...)
    encoder = CHITEncoder()
    json_str = encoder.to_json(original)
    decoded = encoder.from_json(json_str)
    assert decoded.cgp_version == original.cgp_version
```

---

## Summary Checklist

- [x] **datetime.utcnow()** → `datetime.now(timezone.utc)` (41 occurrences)
- [x] **Error handling** → Raise exceptions instead of returning False
- [x] **FastAPI lifespan** → `@asynccontextmanager` pattern
- [x] **Secret generation** → `secrets.token_hex(32)` with warning
- [x] **CORS restriction** → Configurable allowlist
- [x] **Path resolution** → `Path(__file__).resolve().parents[N]`
- [x] **Docstring coverage** → ≥80% on new code
- [x] **Tests** → Unit + integration + smoke tests

---

## References

- PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/389
- Archon API Naming: `pmoves/integrations/archon/PRPs/ai_docs/API_NAMING_CONVENTIONS.md`
- Archon Query Patterns: `pmoves/integrations/archon/PRPs/ai_docs/QUERY_PATTERNS.md`
- Archon Architecture: `pmoves/integrations/archon/PRPs/ai_docs/ARCHITECTURE.md`
