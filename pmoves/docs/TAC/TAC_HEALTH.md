# TAC Tree: Health (wger)

> Technology-Architecture-Context tree for the Health fitness tracking integration.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Health (wger) |
| **Port** | None assigned |
| **Health** | **MISSING** — needs `/healthz` endpoint |
| **Submodule** | `Pmoves-Health-wger` |
| **Docker Profile** | TBD |
| **Tier** | ui |
| **Class** | Specialized |
| **Evolution** | Base |

## Architecture

Health is a **Django/wger** fitness tracking application integrated into the PMOVES ecosystem. It provides:

1. **Workout tracking** — Exercise logs, routines, progress
2. **Nutrition logging** — Calorie and macro tracking
3. **Health metrics** — Body measurements, weight history
4. **NATS integration** (planned) — Health event publishing

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| NATS (4222) | Health event publishing | Planned |
| Supabase (3010) | Cross-platform user data | Planned |
| PostgreSQL | wger database backend | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| Agent Zero | NATS events | Health-aware agent decisions |
| Publisher-Discord | NATS events | Weekly health summary notifications |
| Wealth (Firefly III) | Cross-domain correlation | Health ↔ spending pattern analysis |
| Hyperdimensions | NATS / API | Health data visualization |

## NATS Subjects (Planned)

| Subject | Direction | Description |
|---------|-----------|-------------|
| `health.metrics.updated.v1` | Publishes | Health metric recorded (weight, body fat, etc.) |
| `health.workout.completed.v1` | Publishes | Workout session completed |
| `health.weekly.summary.v1` | Publishes | Weekly health summary report |

**Planned Payload for `health.metrics.updated.v1`:**
```json
{
  "user_id": "pmoves-user-uuid",
  "metric_type": "weight|body_fat|blood_pressure|sleep",
  "value": 75.5,
  "unit": "kg",
  "timestamp": "2026-02-20T12:00:00Z",
  "source": "manual|wearable|api"
}
```

**Planned Payload for `health.weekly.summary.v1`:**
```json
{
  "user_id": "pmoves-user-uuid",
  "week": "2026-W08",
  "workouts_completed": 4,
  "total_duration_min": 240,
  "calories_burned": 1800,
  "weight_trend": "stable",
  "metrics_summary": {
    "avg_weight": 75.2,
    "avg_sleep_hours": 7.5
  },
  "timestamp": "2026-02-23T00:00:00Z"
}
```

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Not active | No CHIT integration yet |
| Delta/Kappa/Hz sensitivity | None | All toggles `false` |
| Swarm participant | No | |
| Attribution gated | No | |
| BPM capable | No | Not prosodic-oriented |

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | **MISSING** | Needs implementation |
| `/metrics` (Prometheus) | **MISSING** | Needs implementation |
| Auth (JWT/Bearer) | **MISSING** | wger has its own auth; needs PMOVES JWT bridge |
| Docker hardening | **Template only** | Needs cap_drop, read_only, tmpfs patterns |
| NATS auth | **MISSING** | No NATS integration yet |
| `env.shared` format | **Unknown** | Needs audit |

## Hardening Roadmap

This is the **least mature** integration. TAC tree serves as the hardening roadmap:

### Phase 1: Health Check & Metrics
1. Add `/healthz` endpoint (Django health check middleware)
2. Add `/metrics` endpoint (django-prometheus)
3. Register in Prometheus scrape config

### Phase 2: NATS Integration
1. Add `nats-py` client to wger
2. Publish `health.metrics.updated.v1` on metric save
3. Publish `health.weekly.summary.v1` via cron/celery

### Phase 3: Docker Hardening
1. Add `cap_drop: [ALL]`, `cap_add: [NET_BIND_SERVICE]`
2. Add `read_only: true` with tmpfs for `/tmp`, `/var/run`
3. Non-root user directive

### Phase 4: CHIT Integration
1. Enable `delta_sensitive` and `hz_sensitive` toggles
2. Publish health CGP packets to `tokenism.cgp.ready.v1`
3. Correlate with Wealth data for holistic CHIT attribution

## Cross-Links

- **Submodule:** `Pmoves-Health-wger/`
- **Wealth Correlation:** [`TAC_WEALTH.md`](./TAC_WEALTH.md)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `health`
- **Agent Topology:** `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` → Domain Apps

## Open Items

- No `/healthz` or `/metrics` endpoints
- No NATS integration — health events not published
- No Docker hardening beyond template
- No CHIT integration
- Auth bridge between wger and PMOVES JWT system needed
- Port assignment needed

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
