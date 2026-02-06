# Integration Health Checks Implementation Report

**Date:** 2026-01-29
**Author:** Claude Code (Anthropic)
**Task:** Add integration health checks to PMOVES.AI submodules

## Overview

Implemented integration health checks for three PMOVES.AI submodules to detect when external dependencies (TensorZero, NATS, GPU Orchestrator) are unavailable in standalone mode.

## Target Submodules

1. **PMOVES-DoX** - FastAPI-based document intelligence service
2. **PMOVES-BoTZ** - aiohttp-based MCP bridge server
3. **Pmoves-Health-wger** - Django-based workout manager

## Implementation Details

### 1. PMOVES-DoX (FastAPI)

**Files Created:**
- `/home/pmoves/PMOVES.AI/PMOVES-DoX/backend/app/utils/integration_health.py`

**Files Modified:**
- `/home/pmoves/PMOVES.AI/PMOVES-DoX/backend/app/main.py`
  - Updated `/healthz` endpoint to include integration status
  - Added startup logging in `@app.on_event("startup")`

**Health Check Response:**
```json
{
  "status": "healthy" | "degraded",
  "version": "1.0.0",
  "uptime_seconds": 123,
  "integrations": {
    "tensorzero": {
      "healthy": true | false,
      "url": "http://tensorzero-gateway:3030"
    },
    "nats": {
      "healthy": true | false,
      "url": "nats://nats:4222"
    },
    "gpu_orchestrator": {
      "healthy": true | false,
      "url": null | "http://gpu-orchestrator:8080"
    }
  }
}
```

**Status Codes:**
- `200 OK` - Service is running (integrations may be degraded)
- All integrations healthy → `"status": "healthy"`
- Any integration down → `"status": "degraded"`

### 2. PMOVES-BoTZ (aiohttp)

**Files Created:**
- `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/mcp_bridge/utils/__init__.py`
- `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/mcp_bridge/utils/integration_health.py`

**Files Modified:**
- `/home/pmoves/PMOVES.AI/PMOVES-BoTZ/features/mcp_bridge/server.py`
  - Updated `handle_health()` function to include integration status
  - Added startup logging after server starts

**Health Check Response:**
```json
{
  "status": "healthy" | "degraded",
  "server": "pmoves-mcp",
  "version": "0.1.0",
  "tools_count": 20,
  "prometheus_enabled": true,
  "integrations": {
    "tensorzero": {
      "healthy": true | false,
      "url": "http://tensorzero-gateway:3030"
    },
    "nats": {
      "healthy": true | false,
      "url": "nats://nats:4222"
    },
    "gpu_orchestrator": {
      "healthy": true | false,
      "url": null | "http://gpu-orchestrator:8080"
    }
  }
}
```

**Graceful Degradation:**
- If integration health check module fails, returns `"status": "degraded"` with error message

### 3. Pmoves-Health-wger (Django)

**Files Created:**
- `/home/pmoves/PMOVES.AI/Pmoves-Health-wger/wger/utils/integration_health.py`

**Files Modified:**
- `/home/pmoves/PMOVES.AI/Pmoves-Health-wger/wger/observability/views.py`
  - Updated `healthz()` view to include integration status
  - Enhanced to distinguish between core (unhealthy) and integration (degraded) failures
- `/home/pmoves/PMOVES.AI/Pmoves-Health-wger/wger/observability/apps.py`
  - Added `ready()` method for startup logging

**Health Check Response:**
```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "checks": {
    "database": {
      "status": "healthy" | "unhealthy"
    }
  },
  "integrations": {
    "tensorzero": {
      "healthy": true | false,
      "url": "http://tensorzero-gateway:3030"
    },
    "nats": {
      "healthy": true | false,
      "url": "nats://nats:4222"
    },
    "gpu_orchestrator": {
      "healthy": true | false,
      "url": null | "http://gpu-orchestrator:8080"
    }
  }
}
```

**Status Codes:**
- `200 OK` - Service is running (integrations may be degraded)
- `503 Service Unavailable` - Core service failure (e.g., database down)

**Status Values:**
- `"healthy"` - All systems operational
- `"degraded"` - Integrations down but core service functional
- `"unhealthy"` - Core service failure (database, etc.)

## Shared Implementation Pattern

Each `IntegrationHealth` class provides:

1. **`check_tensorzero(timeout=2.0)`** - Checks TensorZero Gateway at `/health`
2. **`check_nats(timeout=2.0)`** - Checks NATS connectivity via connection attempt
3. **`check_gpu_orchestrator(timeout=2.0)`** - Optional GPU Orchestrator check
4. **`get_status()`** - Returns dict with all integration statuses

**Timeout Behavior:**
- All health checks have 2-second timeout
- Failed checks log warnings with details
- Exceptions are caught and return `False`

**Environment Variables:**
- `TENSORZERO_BASE_URL` - Default: `http://tensorzero-gateway:3030`
- `NATS_URL` - Default: `nats://nats:4222`
- `GPU_ORCHESTRATOR_URL` - Optional, no default

## Startup Logging

All three services log integration availability at startup:

```
[STARTUP] Integration Status:
  ✓ tensorzero: http://tensorzero-gateway:3030
  ✗ nats: nats://nats:4222
  ✗ gpu_orchestrator: None
```

This provides immediate visibility into integration health when services start.

## Dependencies

### PMOVES-DoX
Already has required dependencies:
- `aiohttp>=3.13.3`
- `nats-py>=2.8.0`

### PMOVES-BoTZ
**Added to requirements.txt:**
```
aiohttp>=3.8.0
nats-py>=2.0.0
```

**Note:** PMOVES-BoTZ has graceful degradation if dependencies not available:
- Logs warnings if `aiohttp` or `nats-py` not installed
- Health checks return `False` for unavailable dependencies

### Pmoves-Health-wger
**Added to requirements:**
```
requests>=2.28.0  # For synchronous HTTP checks
nats-py>=2.0.0    # For NATS connectivity checks
```

**Note:** Django version uses synchronous `requests` instead of `aiohttp` since Django views are sync by default.

## Testing Instructions

### 1. Test PMOVES-DoX (FastAPI)

```bash
# Start the service
cd /home/pmoves/PMOVES.AI/PMOVES-DoX
docker compose up -d

# Wait for startup, check logs for integration status
docker compose logs -f backend | grep STARTUP

# Test health endpoint
curl http://localhost:8000/healthz | jq

# Expected response with integrations unavailable:
{
  "status": "degraded",
  "version": "1.0.0",
  "uptime_seconds": 123,
  "integrations": {
    "tensorzero": {"healthy": false, "url": "http://tensorzero-gateway:3030"},
    "nats": {"healthy": false, "url": "nats://nats:4222"},
    "gpu_orchestrator": {"healthy": false, "url": null}
  }
}
```

### 2. Test PMOVES-BoTZ (aiohttp)

```bash
# Start the MCP bridge server
cd /home/pmoves/PMOVES.AI/PMOVES-BoTZ
python -m features.mcp_bridge.server --http --port 8100

# In another terminal, test health endpoint
curl http://localhost:8100/healthz | jq

# Expected response:
{
  "status": "degraded",
  "server": "pmoves-mcp",
  "version": "0.1.0",
  "tools_count": 20,
  "prometheus_enabled": true,
  "integrations": {
    "tensorzero": {"healthy": false, "url": "http://tensorzero-gateway:3030"},
    "nats": {"healthy": false, "url": "nats://nats:4222"},
    "gpu_orchestrator": {"healthy": false, "url": null}
  }
}
```

### 3. Test Pmoves-Health-wger (Django)

```bash
# Start Django development server
cd /home/pmoves/PMOVES.AI/Pmoves-Health-wger
python manage.py runserver 0.0.0.0:8000

# In another terminal, test health endpoint
curl http://localhost:8000/healthz/ | jq

# Expected response:
{
  "status": "degraded",
  "checks": {
    "database": {"status": "healthy"}
  },
  "integrations": {
    "tensorzero": {"healthy": false, "url": "http://tensorzero-gateway:3030"},
    "nats": {"healthy": false, "url": "nats://nats:4222"},
    "gpu_orchestrator": {"healthy": false, "url": null}
  }
}
```

### 4. Test with PMOVES.AI Services Running

```bash
# Start the full PMOVES.AI stack
cd /home/pmoves/PMOVES.AI
docker compose --profile agents --profile workers up -d

# Check TensorZero
curl http://localhost:3030/health

# Check NATS
docker exec -it pmoves-nats nc -zv localhost 4222

# Now test submodule health endpoints again
# All integrations should show "healthy": true
curl http://localhost:8000/healthz | jq  # PMOVES-DoX
curl http://localhost:8100/healthz | jq  # PMOVES-BoTZ
curl http://localhost:8000/healthz/ | jq # wger (if on different port)
```

## Graceful Degradation Behavior

All three services follow this pattern:

1. **Service starts successfully** even if integrations are unavailable
2. **Health endpoint returns `200 OK`** with `"status": "degraded"` if integrations down
3. **Core functionality remains available** (database, document processing, etc.)
4. **Integration-specific features fail gracefully** when called
5. **Startup logs clearly indicate** which integrations are available

This ensures services in standalone mode don't fail silently - they provide clear visibility into integration status via health checks.

## Issues Encountered

**None** - Implementation was straightforward with minimal changes to existing code.

## Files Changed Summary

### PMOVES-DoX
- Created: `backend/app/utils/integration_health.py`
- Modified: `backend/app/main.py` (2 changes: health endpoint + startup logging)

### PMOVES-BoTZ
- Created: `features/mcp_bridge/utils/__init__.py`
- Created: `features/mcp_bridge/utils/integration_health.py`
- Modified: `features/mcp_bridge/server.py` (2 changes: health handler + startup logging)

### Pmoves-Health-wger
- Created: `wger/utils/integration_health.py`
- Modified: `wger/observability/views.py` (enhanced healthz view)
- Modified: `wger/observability/apps.py` (added ready() method)

## Recommendations

1. **Add to CI/CD:** Include `/healthz` endpoint checks in smoke tests
2. **Monitoring:** Configure Prometheus to scrape `/healthz` and alert on `status != "healthy"`
3. **Documentation:** Update each submodule's README to document the health endpoint
4. **GPU Orchestrator:** Consider adding GPU Orchestrator service to PMOVES.AI core stack
5. **Timeout Tuning:** Adjust 2-second timeout based on actual network conditions in production

## Compliance

All implementations follow PMOVES.AI standards:
- `/healthz` endpoint for health checks (not `/health`)
- JSON responses with clear `status` field
- Logging with `[STARTUP]` prefix for consistency
- Graceful degradation without service crashes
- Integration URLs exposed in health responses for debugging
