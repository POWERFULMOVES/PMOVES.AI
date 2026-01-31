# PMOVES.AI Submodule Audit - Detailed P1 Findings

**Date:** 2026-01-28
**Auditor:** PMOVES.AI Audit Team
**Scope:** 8 submodules audited for security, integration, and observability

---

## Executive Summary

| Submodule | Security | NATS | MCP | Healthz | Metrics | Overall |
|-----------|----------|------|-----|---------|---------|---------|
| PMOVES-AgentGym | ❌ | ❌ | ❌ | ❌ | ❌ | 0/5 |
| PMOVES-Archon | ✅ | ❌ | ✅ | ✅ | ✅ | 4/5 |
| PMOVES-Danger-infra | ⚠️ | ✅ | ❌ | ⚠️ | ❌ | 2/5 |
| PMOVES-E2b-Spells | N/A | ⚠️ | ❌ | ⚠️ | ❌ | N/A* |
| PMOVES-Jellyfin | ⚠️ | ❌ | ❌ | ✅ | ✅ | 3/5 |
| PMOVES-Wealth | ⚠️ | ⚠️ | ❌ | ✅ | ❌ | 2/5 |
| PMOVES-A2UI | ✅ | ❌ | ❌ | ✅ | ❌ | 2/5 |
| PMOVES-surf | ❌ | ❌ | ❌ | ❌ | ❌ | 0/5 |

*\* E2b-Spells is an examples/cookbook repository, not a running service*

---

## P1 Action Items (High Priority)

### 1. PMOVES-Danger-infra: Fix Orchestrator Dockerfile

**File:** `PMOVES-Danger-infra/Dockerfile.orchestrator`

**Issue:** Missing USER directive - container runs as root

**Current State:**
```dockerfile
FROM golang:1.23-alpine AS builder
# ... build steps ...

FROM alpine:3.22
WORKDIR /app
COPY --from=builder /app/orchestrator /app/orchestrator
# ❌ No USER directive - runs as root
CMD ["/app/orchestrator"]
```

**Required Fix:**
```dockerfile
FROM alpine:3.22
WORKDIR /app
# Add non-root user
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app
COPY --from=builder /app/orchestrator /app/orchestrator
USER appuser
CMD ["/app/orchestrator"]
```

**Impact:** CIS Docker Benchmark 1.0.0 - 5.1 compliance

---

### 2. PMOVES-Danger-infra: Add /metrics Endpoint

**File:** `PMOVES-Danger-infra/orchestrator/main.go`

**Current State:** No Prometheus metrics endpoint

**Required Changes:**
```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    requestsTotal = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "orchestrator_requests_total",
            Help: "Total number of requests",
        },
        []string{"method", "endpoint"},
    )

    activeSandboxes = prometheus.NewGauge(
        prometheus.GaugeOpts{
            Name: "orchestrator_active_sandboxes",
            Help: "Number of active sandboxes",
        },
    )
)

func init() {
    prometheus.MustRegister(requestsTotal)
    prometheus.MustRegister(activeSandboxes)
}

// Add to HTTP server
http.Handle("/metrics", promhttp.Handler())
```

**Impact:** Enables Prometheus scraping for observability

---

### 3. PMOVES-Wealth: Add /metrics Endpoint

**File:** `PMOVES-Wealth/app/Http/Controllers/Api/MetricsController.php`

**Current State:** README mentions metrics but no implementation

**Required Changes:**
```php
<?php

namespace App\Http\Controllers\Api;

use Illuminate\Http\Request;
use Prometheus\CollectorRegistry;
use Prometheus\RenderTextFormat;

class MetricsController extends Controller
{
    public function __invoke(
        CollectorRegistry $registry
    ) {
        $renderer = new RenderTextFormat();
        $result = $renderer->render($registry->getMetricFamilySamples());

        return response($result, 200)
            ->header('Content-Type', 'text/plain');
    }
}
```

**Route:** Add to `routes/api.php`:
```php
Route::get('/metrics', [\App\Http\Controllers\Api\MetricsController::class, '__invoke']);
```

**Package Required:** `promphp/prometheus_client_php:^2.0`

---

### 4. PMOVES-Wealth: Add NATS Event Publishing

**File:** `PMOVES-Wealth/app/Events/TransactionCreated.php`

**Current State:** Documentation mentions NATS but no implementation

**Required Changes:**
```php
<?php

namespace App\Events;

use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;
use App\Services\NatsPublisher;

class TransactionCreated
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(
        public array $transaction
    ) {
        // Publish to NATS
        app(NatsPublisher::class)->publish(
            'wealth.transaction.created.v1',
            json_encode([
                'event_id' => Str::uuid()->toString(),
                'timestamp' => now()->toIso8601String(),
                'data' => $transaction,
            ])
        );
    }
}
```

**NATS Client Service:** `app/Services/NatsPublisher.php`
```php
<?php

namespace App\Services;

use Illuminate\Support\Facades\Log;

class NatsPublisher
{
    private ?\Nats\Connection $conn = null;

    public function __construct()
    {
        $this->conn = new \Nats\Connection([
            'host' => config('services.nats.host', 'nats'),
            'port' => config('services.nats.port', 4222),
        ]);
        $this->conn->connect();
    }

    public function publish(string $subject, string $payload): void
    {
        try {
            $this->conn->publish($subject, $payload);
        } catch (\Exception $e) {
            Log::warning('NATS publish failed', [
                'subject' => $subject,
                'error' => $e->getMessage(),
            ]);
        }
    }
}
```

---

### 5. PMOVES-Jellyfin: Verify External Image Security

**File:** `pmoves/docker-compose.yml` (Jellyfin service)

**Current State:** Uses `ghcr.io/POWERFULMOVES/PMOVES-jellyfin:main`

**Action Required:**
1. Check base image for USER directive
2. If running as root, create custom Dockerfile:
```dockerfile
FROM ghcr.io/POWERFULMOVES/PMOVES-jellyfin:main
# Verify and potentially add user switch
USER jellyfin:1000
```

**Verification Command:**
```bash
docker image inspect ghcr.io/POWERFULMOVES/PMOVES-jellyfin:main | grep -A5 "User"
```

---

## P2 Action Items (Medium Priority)

### PMOVES-AgentGym: Containerization + Integration

**Status:** Research framework, not production service

**Changes Required:**
1. Create Dockerfile for each environment (WebArena, ScienceQA, etc.)
2. Add NATS publishing for environment lifecycle events
3. Add /healthz and /metrics endpoints
4. Implement MCP endpoints for Agent Zero coordination

**Estimated Effort:** 2-3 days

---

### PMOVES-surf: PMOVES Integration

**Status:** Standalone Next.js application

**Changes Required:**
1. Create Dockerfile with USER directive
2. Add API routes for /healthz and /metrics
3. Implement NATS client for event publishing
4. Add MCP endpoints

**Estimated Effort:** 1-2 days

---

### PMOVES-A2UI: Integration

**Status:** Google ADK demo application

**Changes Required:**
1. Add /metrics endpoint with Prometheus client
2. Implement NATS publishing
3. Add MCP endpoints (if intended for production use)

**Estimated Effort:** 1 day

---

### PMOVES-E2b-Spells: Service Creation

**Status:** Examples/cookbook only

**Decision Required:** Convert to running service or document as examples only

**If Converting to Service:**
1. Create main service application
2. Implement Dockerfile
3. Add health/metrics endpoints
4. Integrate with NATS

**Estimated Effort:** 3-4 days

---

## P3 Action Items (Low Priority)

### Documentation Updates

1. Update `docs/submodules.md` with latest audit findings
2. Create integration guides for each submodule type
3. Document MCP endpoint patterns
4. Create NATS subject naming convention guide

---

## Security Matrix

| Submodule | USER Directive | Non-Root | Multi-Stage | Scan Configured |
|-----------|----------------|----------|-------------|-----------------|
| PMOVES-AgentGym | N/A | N/A | N/A | ❌ |
| PMOVES-Archon | ✅ | ✅ | ✅ | ❌ |
| PMOVES-Danger-infra | ⚠️ Partial | ⚠️ | ✅ | ❌ |
| PMOVES-E2b-Spells | N/A | N/A | N/A | ❌ |
| PMOVES-Jellyfin | ⚠️ Unknown | ⚠️ | N/A | ❌ |
| PMOVES-Wealth | ⚠️ Unknown | ⚠️ | N/A | ❌ |
| PMOVES-A2UI | ✅ | ✅ | ✅ | ❌ |
| PMOVES-surf | N/A | N/A | N/A | ❌ |

**Legend:**
- ✅ = Compliant
- ⚠️ = Partial/Needs Verification
- ❌ = Not Compliant
- N/A = Not Applicable (no Dockerfile)

---

## Integration Matrix

| Submodule | NATS Publishing | NATS Subscribing | MCP Server | MCP Client |
|-----------|-----------------|------------------|------------|------------|
| PMOVES-AgentGym | ❌ | ❌ | ❌ | ❌ |
| PMOVES-Archon | ❌ | ❌ | ✅ | ❌ |
| PMOVES-Danger-infra | ⚠️ Framework | ⚠️ Framework | ❌ | ❌ |
| PMOVES-E2b-Spells | ⚠️ Templates | ⚠️ Templates | ⚠️ Examples | ⚠️ Examples |
| PMOVES-Jellyfin | ❌ | ❌ | ❌ | ❌ |
| PMOVES-Wealth | ⚠️ Documented | ❌ | ❌ | ❌ |
| PMOVES-A2UI | ❌ | ❌ | ❌ | ❌ |
| PMOVES-surf | ❌ | ❌ | ❌ | ❌ |

**Legend:**
- ✅ = Implemented
- ⚠️ = Framework/Templates Available
- ❌ = Not Implemented

---

## Observability Matrix

| Submodule | /healthz | /metrics | Structured Logging | Tracing |
|-----------|----------|---------|-------------------|---------|
| PMOVES-AgentGym | ❌ | ❌ | ❌ | ❌ |
| PMOVES-Archon | ✅ | ✅ | ✅ Logfire | ❌ |
| PMOVES-Danger-infra | ⚠️ /health | ❌ | ✅ Zap | ✅ OTEL |
| PMOVES-E2b-Spells | ⚠️ Framework | ⚠️ Framework | ❌ | ❌ |
| PMOVES-Jellyfin | ✅ | ✅ | ⚠️ Configurable | ❌ |
| PMOVES-Wealth | ✅ | ❌ | ✅ Laravel | ❌ |
| PMOVES-A2UI | ✅ /health | ❌ | ❌ | ❌ |
| PMOVES-surf | ❌ | ❌ | ❌ | ❌ |

**Legend:**
- ✅ = Implemented
- ⚠️ = Partial/Different Path
- ❌ = Not Implemented

---

## Risk Assessment

### High Risk (Security)
1. **PMOVES-Danger-infra orchestrator** - Running as root in container
2. **PMOVES-Jellyfin** - External image security unknown
3. **PMOVES-Wealth** - External image security unknown

### High Risk (Operational)
1. **PMOVES-AgentGym** - No observability, can't monitor in production
2. **PMOVES-surf** - No observability, standalone operation

### Medium Risk (Integration)
1. **PMOVES-Wealth** - No NATS integration, events not published
2. **PMOVES-Danger-infra** - Go services not using PMOVES integration patterns

---

## Implementation Priority Order

### Phase 1: Critical Security (This Week)
1. ✅ Fix Danger-infra orchestrator Dockerfile
2. ✅ Verify Jellyfin external image security
3. ✅ Verify Wealth external image security

### Phase 2: Observability (This Week)
1. ✅ Add /metrics to Danger-infra
2. ✅ Add /metrics to Wealth
3. ✅ Enable Prometheus scraping in docker-compose

### Phase 3: Integration (Next Week)
1. Add NATS publishing to Wealth
2. Add NATS publishing to Jellyfin Bridge
3. Standardize health endpoints to /healthz

### Phase 4: Extended Integration (Future)
1. Containerize AgentGym
2. Integrate surf into PMOVES patterns
3. Decide on E2b-Spells: service vs examples

---

## Appendix: File Locations

### Danger-infra
- Orchestrator Dockerfile: `PMOVES-Danger-infra/Dockerfile.orchestrator`
- Orchestrator main: `PMOVES-Danger-infra/orchestrator/main.go`
- Health check: `PMOVES-Danger-infra/api/internal/health.go`

### Wealth
- Routes: `PMOVES-Wealth/routes/api.php`
- Controllers: `PMOVES-Wealth/app/Http/Controllers/`
- Docker: Uses external image

### Jellyfin
- Bridge service: `pmoves/services/jellyfin-bridge/main.py`
- Health check: `pmoves/services/jellyfin-bridge/main.py:247`
- Metrics: `pmoves/services/jellyfin-bridge/main.py:251`

---

**Document Version:** 1.0
**Last Updated:** 2026-01-28
**Next Review:** After P1 implementation complete
