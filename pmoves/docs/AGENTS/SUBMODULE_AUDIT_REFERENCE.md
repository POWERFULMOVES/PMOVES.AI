# Submodule Audit Reference

**Created:** 2026-02-16
**Status:** Reference implementation from Agent Zero audit

---

## Purpose

This document captures the audit bootstrap pattern applied to PMOVES-Agent-Zero.
All submodules should follow this checklist to pass the PMOVES Audit Gate.

## What Agent Zero Fixed

1. **NATS Enabled flag** in `PMOVES.AI_INTEGRATION.md` was `False` despite Agent Zero
   subscribing to NATS for task coordination. Changed to `True`.

2. **CI workflow** added at `.github/workflows/pmoves-audit.yml` to validate:
   - Python files compile without syntax errors
   - Integration manifest exists and declares NATS enabled
   - Health check endpoint is documented

## Submodule Audit Checklist

Every PMOVES submodule with a `PMOVES.AI_INTEGRATION.md` should pass these checks:

### Required

- [ ] `PMOVES.AI_INTEGRATION.md` exists in submodule root
- [ ] `NATS Enabled: True` if the service uses NATS (check docker-compose for `NATS_URL`)
- [ ] `/healthz` endpoint documented in the integration manifest
- [ ] `.github/workflows/pmoves-audit.yml` CI workflow present
- [ ] CI targets `PMOVES.AI-Edition-Hardened` branch

### Recommended

- [ ] `GPU Enabled` flag accurate (check for CUDA/GPU dependencies)
- [ ] Service tier documented (agent, worker, media, etc.)
- [ ] Port number documented and matches `services-catalog.md`
- [ ] Health check module present (`pmoves_health/`)
- [ ] NATS announcer present (`pmoves_announcer/`)

## CI Workflow Pattern

Copy from `PMOVES-Agent-Zero/.github/workflows/pmoves-audit.yml`:

```yaml
name: PMOVES Audit Gate
on:
  push:
    branches: [PMOVES.AI-Edition-Hardened]
  pull_request:
    branches: [PMOVES.AI-Edition-Hardened]
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with: { python-version: '3.11' }
      - name: Python compile check
        run: find . -name '*.py' -path '*/python/*' | head -20 | xargs -I{} python -m py_compile {}
      - name: Validate integration manifest
        run: |
          test -f PMOVES.AI_INTEGRATION.md || { echo "Missing integration manifest"; exit 1; }
          grep -q 'NATS Enabled.*True' PMOVES.AI_INTEGRATION.md || { echo "NATS must be enabled"; exit 1; }
          grep -q '/healthz' PMOVES.AI_INTEGRATION.md || echo "WARN: healthz not documented"
```

Customize the compile check path and add service-specific validations as needed.

## Rollout Order

Apply this audit pattern to submodules in dependency order:

1. **PMOVES-Agent-Zero** (done) - Core orchestrator
2. **PMOVES-Archon** - Agent service (depends on Agent Zero MCP)
3. **PMOVES-HiRAG** - RAG gateway (core retrieval)
4. **PMOVES-BoTZ** - Gateway framework
5. **PMOVES.YT** - Media ingestion
6. Remaining submodules by tier: workers, media, utility

## See Also

- `.claude/context/submodule-workflow.md` - Submodule branch workflow
- `pmoves/docs/BRANCH_STRATEGY.md` - Branch model documentation
- `.github/workflows/integration-gate.yml` - Parent repo integration gate
