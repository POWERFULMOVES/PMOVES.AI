# W6 Convergence Wave — Lanes 6 & 7 Implementation Plans

Research Date: 2026-07-08
Issues: #1410 (Lane 6), #1412 (Lane 7)

## Lane 6 — W6-P1: Health Phase 4 CHIT + Prometheus wger

### Phase 4.1 — Registry & Config Fixes (P0)
- [x] Fix wger port: null → 8000
- [x] Fix wger health: null → /api/v2/
- [x] Fix wger compose_profile: null → "wger"

### Phase 4.2 — Test Coverage
- [ ] Add wger to EXPECTED_SCRAPE_TARGETS in Prometheus scrape tests

### Phase 4.3 — NATS Subject Activation (P1)
- [ ] Implement NATS publishing for health.metrics.updated.v1
- [ ] Implement NATS publishing for health.workout.completed.v1
- [ ] Implement NATS publishing for health.weekly.summary.v1
- Architecture: wger API events → n8n webhook → NATS publish

### Phase 4.4 — CHIT Integration
- [ ] Wire CHIT signing for health metrics (HMAC-SHA256 + AES-GCM)
- [ ] Verify CHIT_PROD_PASSPHRASE is set
- Dependency: Phase 4.3 must complete first

### Phase 4.5 — Alert Rules
- [ ] Create Prometheus alert rules (alert.rules.wger.yml)
- [ ] Verify with promtool check rules
- [ ] Alertmanager routes team:life alerts

### Phase 4.6 — Grafana Health Dashboard (P2)
- [ ] Create config/grafana/dashboards/health-wger.json

### Phase 4.7 — TAC Verification
- [ ] Verify all TAC_HEALTH.md checks pass

## Lane 7 — W6-P5: FlOO$ Life-Persona-Voice Pipeline

### Phase A.1 — Service Skeleton
- [ ] services/flooz/__init__.py
- [ ] services/flooz/main.py (FastAPI, port 8119)
- [ ] services/flooz/config.py
- [ ] services/flooz/nats_client.py
- [ ] services/flooz/health.py
- [ ] services/flooz/metrics.py
- [ ] services/flooz/Dockerfile
- [ ] services/flooz/requirements.txt

### Phase A.2 — NATS Registration
- [ ] Add flooz to agent_registry.yaml (port 8119, publishes tokenism.prosodic.bpm.v1)

### Phase A.3 — JSON Schema
- [ ] contracts/schemas/flooz/persona_overlay.v1.schema.json

### Phase B.1 — State Machine
- [ ] FlOO$ Persona Mapper (economic-state → persona-overlay)

### Phase B.2 — TTL Cache
- [ ] services/flooz/cache.py (per-user LRU, asyncio locks, 5s debounce)

### Phase B.3 — Test Suite
- [ ] test_state_machine.py, test_envelopes.py, test_cache.py, test_pipeline.py

### Phase C.1 — ToKenism Merge
- [ ] Overlay-aware logic (merge overlay + BPM profile)

### Phase C.2 — Smoke Test
- [ ] make flooz-smoke (finance.event.v1 → audio output)

### Phase C.3 — MiniMax Archetype Handoff
- [ ] Route archetype_hint → minimax.character.request.v1

## Cross-Lane Dependencies
- wger health.metrics.updated.v1 → FlOO$ finance.event.v1 (optional, post-Phase-A)
