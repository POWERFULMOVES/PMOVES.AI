# TAC Tree: Health (wger)

> Technology-Architecture-Context tree for the Health fitness tracking integration.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Health (wger) |
| **Port** | 8000 (`WGER_PORT`, compose: main + external) |
| **Health** | `GET /healthz/` (app-level, 3-tier: healthy/degraded/unhealthy); compose readiness uses `GET /api/v2/health/` |
| **Metrics** | `GET /metrics/` (Prometheus, gated by `EXPOSE_PROMETHEUS_METRICS`) |
| **Submodule** | `Pmoves-Health-wger` |
| **Docker Profile** | `health`, `wger` |
| **Tier** | api |
| **Class** | Specialized |
| **Evolution** | Stage 1 |

## Architecture

Health is a **Django/wger** fitness tracking application integrated into the PMOVES ecosystem. It provides:

1. **Workout tracking** — Exercise logs, routines, progress
2. **Nutrition logging** — Calorie and macro tracking
3. **Health metrics** — Body measurements, weight history
4. **NATS integration** — Health event publishing (wired in main compose)

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| NATS (4222) | Health event publishing | Yes (main compose) |
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
| `/healthz` endpoint | **GREEN** | 3-tier model (healthy/degraded/unhealthy) at `wger/observability/views.py` |
| `/metrics` (Prometheus) | **GREEN** | Prometheus format at `/metrics/`, gated by `EXPOSE_PROMETHEUS_METRICS` |
| Auth (JWT/Bearer) | **Partial** | Token auth via `WGER_API_TOKEN`; PMOVES JWT bridge still needed |
| Docker hardening | **GREEN** | `*tier-api-hardened` in main compose (cap_drop ALL, security_opt) |
| NATS integration | **GREEN** | `NATS_URL` + `WGER_ENABLE_NATS` in main compose |
| `env.shared` format | **GREEN** | Main compose uses `env.shared` + `env.tier-api` via anchor |
| Prometheus scrape | **MISSING** | Not yet in `prometheus.yml` — wger exposes metrics but isn't scraped |

## Hardening Roadmap

Wger has progressed significantly since initial audit. Phases 1-3 are largely complete:

### Phase 1: Health Check & Metrics — **DONE**
1. ~~Add `/healthz` endpoint~~ → Implemented: 3-tier model in `wger/observability/views.py`
2. ~~Add `/metrics` endpoint~~ → Implemented: Prometheus export in `wger/observability/views.py`
3. Register in Prometheus scrape config → **PENDING** (wger not yet in `prometheus.yml`)

### Phase 2: NATS Integration — **DONE**
1. ~~Add `nats-py` client to wger~~ → Wired via compose `NATS_URL` + `WGER_ENABLE_NATS`
2. Publish `health.metrics.updated.v1` on metric save → Subjects defined; n8n workflow defined, requires activation and smoke test
3. Publish `health.weekly.summary.v1` via cron/celery → n8n workflow `health_weekly_to_cgp.json` defined, requires activation and smoke test

### Phase 3: Docker Hardening — **DONE**
1. ~~Add `cap_drop: [ALL]`~~ → `*tier-api-hardened` in main compose (line 3009)
2. ~~Add security_opt~~ → `no-new-privileges:true` via anchor
3. ~~Healthcheck~~ → Python urllib probe at `/api/v2/health/` (line 3043)

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

- ~~No `/healthz` or `/metrics` endpoints~~ → Implemented in `wger/observability/`
- ~~No NATS integration~~ → Wired in main compose + n8n workflows
- ~~No Docker hardening~~ → `*tier-api-hardened` in main compose
- ~~Port assignment needed~~ → Port 8000, profiles `health`/`wger`
- Prometheus scrape job not yet configured (wger exposes metrics but isn't scraped)
- No CHIT integration
- Auth bridge between wger and PMOVES JWT system needed
- Mobile app integration docs needed in TAC (Flutter Android/iOS official apps)

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-STATUS-UPDATE::2026-03-16 -->
