---
name: minimax-bringup-audit
description: Guide for tiered bring-up, smoke validation, and evidence capture during PMOVES service deployments. This skill should be used when starting services, running smoke tests, or validating CI/CD pipeline outputs.
keywords: [bringup, smoke, audit, validation, deployment, health]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Bringup Audit

Tiered bring-up, smoke validation, and evidence capture for PMOVES service deployments with MiniMax backend.

## Purpose

Execute tiered service bring-up validation, capture pass/fail evidence, and generate remediation queues for PMOVES infrastructure using MiniMax for fast tactical inference.

## Capabilities

- ✨ Execute tiered Make targets for service bring-up
- 🔍 Run health endpoint validation across all services
- 📊 Generate pass/fail matrix with evidence
- 🔧 Queue remediation items for failures
- 🤖 Route complex failures to MiniMax for root cause analysis

## Integration Points

- **NATS Subject**: `pmoves.health.check.v1`
- **Health Endpoints**: See `.claude/context/services-catalog.md`
- **Make Targets**: `make -C pmoves smoke`, `make -C pmoves smoke-gpu`
- **TensorZero**: Routes through `localhost:3030` for inference

## Workflow

### Tier 1: Core Smoke

```bash
make -C pmoves smoke
```

### Tier 2: GPU Validation (Strict)

```bash
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
```

### Tier 3: Full Integration

```bash
make -C pmoves verify-all
```

## Evidence Capture

For each validation step, capture:

1. **Timestamp** - ISO 8601 UTC
2. **Service** - Name from `services-catalog.md`
3. **Endpoint** - Health path checked
4. **Status** - HTTP status code
5. **Response** - JSON body (truncated if large)
6. **Duration** - Milliseconds

## Remediation Queue

Failed checks generate remediation items with:

- Service name
- Expected vs actual status
- Logs snippet (`docker compose logs -f <service>`)
- Suggested action

## Example Usage

```
User: "Run bringup audit for workstation_5090 profile"

Agent:
1. Loads skill
2. Executes make -C pmoves smoke
3. Captures evidence to /tmp/bringup_audit_2026-03-30.json
4. Generates pass/fail matrix
5. Routes failures to MiniMax for RCA
```

## Trigger Phrases

- "run bringup audit"
- "smoke test services"
- "validate deployment"
- "service health check"
- "tiered bringup"
