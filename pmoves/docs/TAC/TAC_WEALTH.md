# TAC Tree: Wealth (Firefly III)

> Technology-Architecture-Context tree for the Wealth finance tracking integration.

## Service Identity

| Field | Value |
|-------|-------|
| **Service** | Wealth (Firefly III) |
| **Port** | None assigned |
| **Health** | **MISSING** — needs `/healthz` endpoint |
| **Submodule** | `PMOVES-Wealth` |
| **Docker Profile** | TBD |
| **Tier** | ui |
| **Class** | Specialized |
| **Evolution** | Base |

## Architecture

Wealth is a **Laravel/Firefly III** personal finance management application integrated into the PMOVES ecosystem. It provides:

1. **Transaction tracking** — Income, expenses, transfers
2. **Budget management** — Category-based budgets and goals
3. **Financial reporting** — Charts, summaries, trends
4. **NATS integration** (planned) — Finance event publishing
5. **ToKenism correlation** — Real spending → FoodUSD simulation validation

## Upstream Dependencies

| Dependency | Type | Required |
|------------|------|----------|
| NATS (4222) | Finance event publishing | Planned |
| Supabase (3010) | Cross-platform user data | Planned |
| MySQL/PostgreSQL | Firefly III database backend | Yes |

## Downstream Consumers

| Consumer | Interface | Description |
|----------|-----------|-------------|
| ToKenism | NATS events | Real spending data for economic simulation |
| Agent Zero | NATS events | Finance-aware agent decisions |
| Publisher-Discord | NATS events | Monthly finance summary notifications |
| Health (wger) | Cross-domain correlation | Spending ↔ health pattern analysis |
| Hyperdimensions | NATS / API | Financial data visualization |

## NATS Subjects (Planned)

| Subject | Direction | Description |
|---------|-----------|-------------|
| `finance.transactions.ingested.v1` | Publishes | New transaction(s) imported |
| `finance.budget.alert.v1` | Publishes | Budget threshold crossed |
| `finance.monthly.summary.v1` | Publishes | Monthly finance summary report |

**Planned Payload for `finance.transactions.ingested.v1`:**
```json
{
  "user_id": "pmoves-user-uuid",
  "transaction_count": 15,
  "total_amount": 523.47,
  "currency": "USD",
  "categories": ["groceries", "utilities", "entertainment"],
  "period": "2026-02-01/2026-02-15",
  "timestamp": "2026-02-15T12:00:00Z"
}
```

**Planned Payload for `finance.monthly.summary.v1`:**
```json
{
  "user_id": "pmoves-user-uuid",
  "month": "2026-02",
  "income": 5000.00,
  "expenses": 3200.00,
  "savings_rate": 0.36,
  "top_categories": [
    {"name": "groceries", "amount": 800.00},
    {"name": "rent", "amount": 1500.00}
  ],
  "budget_adherence": 0.92,
  "timestamp": "2026-03-01T00:00:00Z"
}
```

## CHIT Integration Status

| Capability | Status | Notes |
|------------|--------|-------|
| CGP packet generation | Not active | No CHIT integration yet |
| Delta/Kappa/Hz sensitivity | None | All toggles `false` |
| Swarm participant | No | |
| Attribution gated | No | |
| ToKenism correlation | Planned | Real spending → FoodUSD validation |

### ToKenism ↔ Wealth Bridge (Planned)

```
Real Transactions (Firefly III)
        ↓
finance.transactions.ingested.v1
        ↓
ToKenism Economic Simulation
        ↓
FoodUSD simulation validation
        ↓
tokenism.attribution.recorded.v1
        ↓
CGP packet with real-world grounding
```

## Production Audit Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| `/healthz` endpoint | **MISSING** | Needs implementation |
| `/metrics` (Prometheus) | **MISSING** | Needs implementation |
| Auth (JWT/Bearer) | Partial | Firefly III has its own OAuth; needs PMOVES bridge |
| Docker hardening | Partial | Base Firefly III Docker; needs PMOVES hardening |
| NATS auth | **MISSING** | No NATS integration yet |
| `env.shared` format | **Unknown** | Needs audit |
| Default credentials | **P2** | MinIO default creds risk (if connected) |

## Hardening Roadmap

### Phase 1: Health Check & Metrics
1. Add `/healthz` proxy endpoint (Laravel health check)
2. Add `/metrics` via laravel-prometheus
3. Register in Prometheus scrape config

### Phase 2: NATS Integration
1. Add NATS client to Laravel (via Redis bridge or direct)
2. Publish `finance.transactions.ingested.v1` on import webhook
3. Publish `finance.monthly.summary.v1` via scheduled task

### Phase 3: Docker Hardening
1. Add `cap_drop: [ALL]`, `cap_add: [NET_BIND_SERVICE]`
2. Non-root user directive
3. Secure environment variable handling (no `export` syntax)

### Phase 4: CHIT Integration
1. Bridge real transactions to ToKenism FoodUSD simulation
2. Publish finance CGP packets to `tokenism.cgp.ready.v1`
3. Enable `delta_sensitive` toggle for spending delta tracking

## Cross-Links

- **Submodule:** `PMOVES-Wealth/`
- **ToKenism Bridge:** [`TAC_TOKENISM.md`](./TAC_TOKENISM.md)
- **Health Correlation:** [`TAC_HEALTH.md`](./TAC_HEALTH.md)
- **Integration Topology:** [`TAC_INTEGRATION_TOPOLOGY.md`](./TAC_INTEGRATION_TOPOLOGY.md)
- **Agent Registry:** `pmoves/config/agent_registry.yaml` → `wealth`
- **Agent Topology:** `pmoves/docs/AGENTS/PMOVES_AGENT_TOPOLOGY.md` → Domain Apps

## Open Items

- No `/healthz` or `/metrics` endpoints
- No NATS integration — finance events not published
- Docker hardening incomplete
- No CHIT integration
- Auth bridge between Firefly III OAuth and PMOVES JWT needed
- Port assignment needed
- ToKenism correlation pipeline not implemented

<!-- GRAPHITI_MARK: CLAUDE-OPUS::TAC-TOPOLOGY-AUDIT::2026-02-20 -->
