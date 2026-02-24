# PMOVES.AI Integration Checklist

> Standard checklist for any submodule joining the PMOVES.AI ecosystem.
> Last updated: 2026-02-23

Use this checklist when onboarding a new submodule or auditing an existing one.

---

## 1. Documentation

- [ ] **`PMOVES.AI_INTEGRATION.md`** exists at submodule root
  - All `_TBD_` placeholders filled with actual values
  - Purpose, tier, NATS subjects, health endpoints documented
  - Cross-references to service catalog and NATS subject docs

- [ ] **README.md** includes PMOVES.AI integration section
  - How to run in "docked" mode (connected to PMOVES.AI cluster)
  - Environment variables required for integration

---

## 2. NATS Event Bus

- [ ] **NATS_URL** defaults to authenticated URL: `nats://nats:pmoves@nats:4222`
  - Check: `docker-compose*.yml`, `.env*`, Python/JS code defaults
  - Pattern (internal Docker-only): `os.getenv("NATS_URL", "nats://nats:pmoves@nats:4222")`
  - Production/external deployments should inject `NATS_URL` via secrets (`os.getenv("NATS_URL")`) and avoid credential defaults in source.

- [ ] **NATS subjects** documented in integration template
  - Publish subjects listed with schema examples
  - Subscribe subjects listed with expected payload format

- [ ] **JetStream** enabled if reliable delivery needed
  - `NATS_JETSTREAM=true` in environment

---

## 3. Health & Observability

- [ ] **`/healthz` endpoint** exposed (HTTP GET, returns JSON)
  - Returns `{"status": "healthy"}` when operational
  - Returns `{"status": "unhealthy", "reason": "..."}` on failure
  - Includes dependency status (NATS, DB, upstream services)

- [ ] **`/metrics` endpoint** exposed (Prometheus format)
  - Request counters, latency histograms, error rates
  - Uses `prometheus_client` (Python) or `prom-client` (Node.js)

- [ ] **Prometheus scrape labels** configured in Docker Compose
  ```yaml
  labels:
    - "pmoves.service=true"
    - "prometheus.io/scrape=true"
    - "prometheus.io/port=<service-port>"
    - "prometheus.io/path=/metrics"
  ```

---

## 4. Docker & Compose

- [ ] **Docker Compose overlay** exists for `pmoves-net` network
  - Service joins `pmoves_app` and/or `pmoves_bus` networks
  - Uses tier-based hardening anchor (`*tier-<tier>-hardened` or `-ro`)

- [ ] **`read_only: true`** for stateless services
  - tmpfs mounts for `/tmp`, `/var/run` if read-only

- [ ] **Security hardening** applied
  - `cap_drop: [ALL]`
  - `cap_add:` only specific capabilities needed
  - `security_opt: [no-new-privileges:true]`
  - Non-root `USER` directive in Dockerfile

- [ ] **Health check** in compose file
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:<port>/healthz"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 10s
  ```

- [ ] **No `version:` key** in compose files (deprecated in Compose V2+)

---

## 5. Environment & Secrets

- [ ] **Tier assignment** declared
  - One of: `data`, `api`, `llm`, `worker`, `media`, `agent`, `ui`
  - Set via `TIER=<tier>` environment variable

- [ ] **No `export` syntax** in env files
  - Docker `env_file:` requires plain `KEY=VALUE`
  - Wrong: `export NATS_URL=nats://...`
  - Right: `NATS_URL=nats://nats:pmoves@nats:4222`

- [ ] **No default credentials** in production env files
  - No `minioadmin`, `root:root`, `neo4j`, `tensorzero:tensorzero`
  - Use `${VAR:?error message}` for required secrets

- [ ] **CHIT secrets manifest** entry exists
  - `chit/secrets_manifest_v2.yaml` lists required/optional variables

- [ ] **`.env*` files** in `.gitignore`
  - Template files (`.env.example`, `.env.defaults`) are committed
  - Actual env files with secrets are gitignored

---

## 6. Authentication

- [ ] **Auth pattern** follows PMOVES.AI standards
  - JWT Bearer token validation using `SUPABASE_JWT_SECRET`
  - OR shared secret via `MCP_SERVER_TOKEN` for service-to-service (legacy; prefer JWT for new integrations)
  - Fail-closed: if secret not configured, return HTTP 500 (not bypass)

- [ ] **Public endpoints** clearly defined
  - `/healthz`, `/metrics` — always public
  - All other endpoints require authentication

- [ ] **CORS headers** include `Authorization`
  ```http
  Access-Control-Allow-Headers: Content-Type, Authorization
  ```

---

## 7. Service Announcement

- [ ] **Service announcement** on NATS at startup
  - Publishes to `services.announce.v1` subject
  - Includes: slug, name, URL, port, tier, health_check URL
  - Uses `pmoves_announcer` library (Python) if available

---

## 8. Network & Ports

- [ ] **Port allocation** checked against services catalog
  - No conflicts with existing services (see `.claude/context/services-catalog.md`)
  - Registered in the services catalog document

- [ ] **Binds to `127.0.0.1`** or `0.0.0.0` within Docker
  - Never binds to host-specific IPs
  - Host port mapping via Docker Compose

---

## 9. CI / Quality

- [ ] **Dockerfile** follows multi-stage build pattern
  - Builder stage installs dependencies
  - Runtime stage is minimal (slim/alpine)

- [ ] **Image SHA pins** for base images
  - Prevents supply chain attacks
  - Example: `FROM python:3.11-slim@sha256:abc123...`

- [ ] **Tests exist** and pass locally
  - Unit tests for core functionality
  - Integration test for health endpoint

---

## Quick Validation Commands

```bash
# Check NATS auth in all files
grep -r "nats://nats:4222" . --include="*.py" --include="*.yml" --include="*.yaml" --include="*.env*"
# Should return NO results (all should use nats://nats:pmoves@nats:4222)

# Check for export syntax in env files
grep -r "^export " . --include="*.env*" --include="env.*"
# Should return NO results

# Check for default credentials
grep -rn "minioadmin\|root:root\|neo4j:neo4j\|tensorzero:tensorzero" . --include="*.env*" --include="env.*"
# Should return NO results in production env files

# Verify health endpoint
curl -sf http://localhost:<port>/healthz | jq .status
# Should return "healthy"
```

---

## Cross-References

- **Service Topology:** `pmoves/docs/PMOVES_SERVICE_TOPOLOGY.md`
- **Integration Guide:** `pmoves/docs/integrations/INTEGRATIONS.md`
- **Security Patterns:** `.claude/context/security-patterns.md`
- **Services Catalog:** `.claude/context/services-catalog.md`
- **Phase C Audit Results:** `docs/submodules-audit-final-summary.md`
