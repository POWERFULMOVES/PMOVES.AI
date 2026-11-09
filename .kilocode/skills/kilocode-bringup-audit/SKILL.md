---
name: kilocode-bringup-audit
description: Guide for tiered bring-up, smoke validation, and evidence capture during PMOVES service deployments on the KiloCode GLM lane. Use when starting services, running smoke tests, or validating CI/CD pipeline outputs.
keywords: [bringup, smoke, audit, validation, deployment, health, kilocode, glm]
version: 1.0.0
category: PMOVES/KiloCode
---

# KiloCode Bringup Audit

Tiered service bring-up, smoke validation, and evidence capture for PMOVES deployments, optimized for the KiloCode GLM delivery lane.

## Purpose

Execute tiered service bring-up validation, capture pass/fail evidence, and generate remediation queues for PMOVES infrastructure. Route complex failures through TensorZero `coding_glm` / `coding_kilocode` for root-cause analysis.

## Capabilities

- ✨ Execute tiered Make targets for service bring-up
- 🔍 Run health endpoint validation across KiloCode-critical services
- 📊 Generate pass/fail matrix with evidence
- 🔧 Queue remediation items for failures
- 🤖 Route complex failures to GLM-5-Turbo for root cause analysis

## Integration Points

- **NATS Subject**: `pmoves.health.check.v1`
- **Health Endpoints**: TensorZero `:3030/health`, Ollama `:11434/api/tags`, Cipher `:8105/health`
- **Make Targets**: `make -C pmoves kilo-health`, `make -C pmoves smoke`, `make -C pmoves smoke-gpu`
- **TensorZero Functions**: `coding_glm`, `coding_kilocode`

## Workflow

### Tier 1: KiloCode Health

```bash
make -C pmoves kilo-health
```

### Tier 2: Core Smoke

```bash
make -C pmoves smoke
```

### Tier 3: GPU Validation (Strict)

```bash
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
```

### Tier 4: Full Integration

```bash
make -C pmoves verify-all
```

## Evidence Capture

For each validation step, capture:

1. **Timestamp** - ISO 8601 UTC
2. **Service** - Name from `services-catalog.md`
3. **Endpoint** - Health path checked
4. **Status** - HTTP status code or healthy/unhealthy
5. **Response** - JSON body (truncated if large)
6. **Duration** - Milliseconds

## Remediation Queue

Failed checks generate remediation items with:

- Service name
- Expected vs actual status
- Logs snippet (`docker compose logs -f <service>`)
- Suggested action
- Route to `coding_glm` if failure pattern is novel

## Example Usage

```text
User: "Run bringup audit for workstation_5090 profile"

Agent:
1. Loads skill
2. Executes make -C pmoves kilo-health
3. Executes make -C pmoves smoke
4. Captures evidence to /tmp/bringup_audit_<iso>.json
5. Generates pass/fail matrix
6. Routes failures to TensorZero coding_glm for RCA
```

## Trigger Phrases

- "run kilocode bringup audit"
- "smoke test services"
- "validate deployment"
- "service health check"
- "tiered bringup"
- "kilo-health"
