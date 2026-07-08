# Kong Route Seeder Specification

**Version:** 1.0.0  
**Author:** PMOVES.AI Infrastructure Team  
**Date:** 2026-07-09  
**Branch:** `research/comprehensive-analysis-2026-07-09`

---

## 1. Problem Statement

Kong Gateway runs in **DB mode** (not declarative). On a fresh bring-up, Kong has **zero routes**, meaning all 91 agents fail to reach model providers through the `Kong -> TensorZero -> Provider` routing chain. This document specifies the idempotent route seeder that closes this gap.

---

## 2. Architecture

### 2.1 Routing Chain

```
+--------------+     +----------+     +-------------+     +------------------+
| 91 Agents    |---->| Kong     |---->| TensorZero  |---->| Z.AI / Moonshot  |
| (Agent Zero, |     | :8000    |     | :3030       |     | / MiniMax / etc  |
|  Archon,     |     | (proxy)  |     | (gateway)   |     |                  |
|  Typer, ...) |     | :8001    |     |             |     |                  |
+--------------+     | (admin)  |     +-------------+     +------------------+
                     +----------+
```

### 2.2 Kong Entity Model

For each **provider**, the seeder creates:

| Entity   | Naming Convention          | Purpose                                  |
|----------|---------------------------|------------------------------------------|
| Service  | `<provider>-glm` etc.     | Maps provider name to upstream URL       |
| Upstream | `<service>-upstream`      | Health-checked load balancer             |
| Target   | Provider hostname         | Backend API endpoint                     |
| Route    | `route/<model-slug>`      | Per-model path routing                   |
| Plugin   | `key-auth` per service    | API-key authentication                   |

### 2.3 Path Convention

```
POST /v1/chat/completions/glm-4-plus        -> zai-glm service
POST /v1/chat/completions/glm-4.7           -> zai-glm service
POST /v1/chat/completions/glm-5.1           -> zai-glm service
POST /v1/chat/completions/glm-5-turbo       -> zai-glm service
POST /v1/chat/completions/glm-4-air         -> zai-glm service
POST /v1/chat/completions/glm-4-flash       -> zai-glm service
POST /v1/chat/completions/kimi-k2           -> moonshot-kimi service
POST /v1/chat/completions/minimax-m2.7      -> minimax service
... (scales to any model suit in pmoves/configs/model-suits/*.yaml)
```

---

## 3. Idempotency Guarantees

The seeder uses **Kong PUT endpoints** for all create-or-update operations:

- `PUT /services/{name}` -- creates or updates a service
- `PUT /routes/{name}` -- creates or updates a route
- `PUT /upstreams/{name}` -- creates or updates an upstream
- `POST /upstreams/{name}/targets` -- adds a target (idempotent when same target)
- `POST /plugins` -- creates plugin; 409 conflicts are treated as "already exists"

Running the seeder **N times** produces the same result as running it **once**.

---

## 4. CLI Reference

```bash
# Basic usage
python3 pmoves/tools/kong_route_seeder.py

# Dry-run (no changes)
python3 pmoves/tools/kong_route_seeder.py --dry-run

# Prune stale routes (routes whose model suits were deleted)
python3 pmoves/tools/kong_route_seeder.py --prune

# Custom Kong Admin URL
python3 pmoves/tools/kong_route_seeder.py --kong-url http://kong:8001

# JSON summary
python3 pmoves/tools/kong_route_seeder.py --json-summary

# Debug output
python3 pmoves/tools/kong_route_seeder.py --debug
```

### Make Targets

```bash
make kong-seed-routes      # Idempotent seed
make kong-dry-run          # Preview changes
make kong-prune-routes     # Remove stale routes
make kong-sync             # Seed + prune
make kong-list-routes      # List all routes
make kong-list-services    # List all services
make kong-health           # Check Kong Admin API health
make kong-reset-routes     # DANGER: delete all and re-seed
make kong-help             # Show CLI help
```

---

## 5. Security

- **API keys are never logged.**  The seeder extracts `api_key_env` (the environment variable *name*) but never reads or logs the actual key value.
- All log records pass through a `SecretsFilter` that redacts anything resembling a credential.
- The `key-auth` plugin is installed per-service with `hide_credentials: true` so upstream providers never see the Kong-level API key.

---

## 6. Supported Model Suit Schemas

The seeder auto-detects two YAML schemas:

### Schema A: `model_suit:` (GLM family)
```yaml
model_suit:
  name: glm-4-plus
  provider: zai
  base_url: "https://api.z.ai/v1"
  api_key_env: Z_AI_API_KEY
```

### Schema B: `suit:` + `model_config:` (KIMI, MiniMax)
```yaml
suit:
  id: minimax-m2.7
  name: MiniMax M2.7
  provider: minimax
model_config:
  api_base: "https://api.minimax.chat/v1"
  api_key_env: MINIMAX_TOKEN_PLAN_API_KEY
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Kong Admin API not reachable` | Kong not started or wrong port | Check `docker ps`; ensure port 8001 is exposed |
| `No model suits found` | Wrong directory or no YAMLs | Verify `pmoves/configs/model-suits/*.yaml` exists |
| Route returns 404 | Route not seeded | Run `make kong-seed-routes` |
| Route returns 401 | key-auth plugin active but no consumer | Create a Kong consumer + key: `POST /consumers` then `POST /consumers/{name}/key-auth` |
| Model suit missing `base_url` | Schema B file without `api_base` | Check YAML; seeder will use fallback host |

---

## 8. Operational Notes

- **Bring-up order:** Kong must be running before the seeder is invoked. Add `make kong-seed-routes` to the Supa bring-up path after `kong` container health check passes.
- **Credential rotation:** Since the seeder only references env-var *names*, rotating a provider API key requires no changes to Kong -- just update the environment variable and restart TensorZero (not Kong).
- **Adding a new model:** Drop a new model-suit YAML into `pmoves/configs/model-suits/`, then run `make kong-seed-routes`. The new route will be created idempotently.
- **Removing a model:** Delete the YAML and run `make kong-sync` (seed + prune).
