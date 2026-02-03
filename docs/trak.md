# PMOVES.AI Git Status Tracking Report

**Generated:** 2026-02-03
**Branch:** PMOVES.AI-Edition-Hardened
**Total Files with Changes:** 781

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| Modified (M) | 44 | Needs commit |
| Deleted (D) | 107 | **CRITICAL** - Files removed during merge |
| Untracked (??) | 630 | Needs review & add |
| **TOTAL** | **781** | **ACTION REQUIRED** |

---

## CRITICAL ISSUES - Deleted Files (107)

### 🚨 High Priority - Documentation Files

```
docs/SECRETS_MANAGEMENT.md                              # V5 secrets management docs
docs/DOCUMENTATION-UPDATE-PLAN.md
docs/HARDENED_MAKEFILE_REFACTOR_PLAN.md
docs/Security-Hardening-Summary-2025-01-29.md
docs/architecture/6-tier-environment-architecture.md
docs/external-references-summary-2026-01-29.md
docs/hardening/third-party-recommendations.md
docs/production/GHCR-Namespace-Publishing.md
docs/production/Tailscale-Integration.md
docs/submodule-pr-audit-2026-01-31.md
docs/submodules-audit-final-summary.md
docs/submodules-audit-p1-detailed.md
docs/submodules-audit-p4-p5-summary.md
docs/submodules-upstream-audit.md
docs/subsystems/CHIT_GEOMETRY_BUS.md
docs/subsystems/SUBSYSTEM_INTEGRATION.md
docs/subsystems/VOICE_AGENTS.md
docs/templates/QUICK-REFERENCE.md
docs/templates/STANDARD-DOCUMENTATION-TEMPLATE.md
docs/templates/TEMPLATE-DECISIONS.md
```

### 🚨 High Priority - Agent Zero Event Bus (Deleted)

```
pmoves/services/agent-zero/python/events/QUICKSTART.md
pmoves/services/agent-zero/python/events/__init__.py
pmoves/services/agent-zero/python/events/bus.py
pmoves/services/agent-zero/python/events/schema.py
pmoves/services/agent-zero/python/events/subjects.py
pmoves/services/agent-zero/python/events/test_bus.py
pmoves/services/agent-zero/python/events/test_critical_fixes.py
pmoves/services/agent-zero/python/events/test_thread_safety.py
```

### 🚨 High Priority - Distributed Compute Services (Deleted)

```
pmoves/docs/DISTRIBUTED_COMPUTE_SERVICES.md
pmoves/services/node-registry/__init__.py
pmoves/services/node-registry/api.py
pmoves/services/node-registry/main.py
pmoves/services/node-registry/registry.py
pmoves/services/node-registry/storage.py
pmoves/services/resource-detector/__init__.py
pmoves/services/resource-detector/categories.py
pmoves/services/resource-detector/hardware.py
pmoves/services/resource-detector/main.py
pmoves/services/resource-detector/models.py
pmoves/services/vllm-orchestrator/__init__.py
pmoves/services/vllm-orchestrator/config.py
pmoves/services/vllm-orchestrator/main.py
pmoves/services/vllm-orchestrator/parallelism.py
pmoves/services/vllm-orchestrator/resources.py
pmoves/services/vllm-orchestrator/server.py
pmoves/services/vllm-orchestrator/tensorzero.py
pmoves/services/work-marshaling/__init__.py
pmoves/services/work-marshaling/main.py
pmoves/services/benchmark-runner/__init__.py
pmoves/services/benchmark-runner/benchmark.py
pmoves/services/benchmark-runner/comparison.py
pmoves/services/benchmark-runner/server.py
```

### 🚨 High Priority - Agent Zero Features/Gateway/Security (Deleted)

```
pmoves/services/agent-zero/python/features/__init__.py
pmoves/services/agent-zero/python/features/a2a/__init__.py
pmoves/services/agent-zero/python/features/a2a/server.py
pmoves/services/agent-zero/python/features/a2a/test_server.py
pmoves/services/agent-zero/python/features/a2a/types.py
pmoves/services/agent-zero/python/gateway/__init__.py
pmoves/services/agent-zero/python/gateway/gateway.py
pmoves/services/agent-zero/python/gateway/test_threads.py
pmoves/services/agent-zero/python/gateway/threads.py
pmoves/services/agent-zero/security/__init__.py
pmoves/services/agent-zero/security/hooks/__init__.py
pmoves/services/agent-zero/security/hooks/audit_log.py
pmoves/services/agent-zero/security/hooks/deterministic.py
pmoves/services/agent-zero/security/hooks/probabilistic.py
pmoves/services/agent-zero/security/patterns.yaml
pmoves/services/agent-zero/security/tests/__init__.py
pmoves/services/agent-zero/security/tests/test_security_fixes.py
```

### 🚨 High Priority - Scripts Deleted

```
pmoves/scripts/sync-upstream-forks.sh
pmoves/scripts/task_tracker.py
pmoves/scripts/validate-hardening.sh
.github/workflows/hardening-validation.yml
pmoves/tests/hardening/test_docker_hardening.py
```

---

## Untracked Files (630) - Should Be Added

### Root Level (Add These)
```
CLAUDE.md
CONTRIBUTING.md
LICENSE
Makefile
CRUSH.md
GEMINI.md
.envrc.example
.gitattributes
```

### GitHub Configuration
```
.github/README-badge-snippet.md
.github/copilot-instructions.md
.github/pull_request_template.md
.github/prompts/             (directory)
.github/runners/             (directory)
.github/trivy/              (directory)
```

### Claude Learning Files
```
.claude/commands/pr-monitor.md
.claude/learnings/pr-reviews/ (directory)
.claude/learnings/secrets-audit-2025-12.md
.claude/learnings/submodule-security-audit-2025-12.md
.claude/learnings/tensorzero-pr336-review-2025-12.md
.claude/learnings/tts-docker-cuda-patterns-2025.md
.claude/scripts/pr-monitor.sh
```

### Build Scripts
```
scripts/bootstrap_credentials.sh
scripts/bringup.sh
scripts/bringup_api.sh
scripts/bringup_core.sh
scripts/bringup_data.sh
scripts/bringup_media.sh
scripts/bringup_workers.sh
```

---

## Modified Files (44) - Need Commit

### Submodules (Dirty State)
```
PMOVES-Archon           # modified content
PMOVES-ToKenism-Multi   # modified content, untracked content
```

### Core Configuration
```
.coderabbit.yaml
.github/workflows/build-images.yml
.github/workflows/deploy-gateway-agent.yml
.github/workflows/integrations-ghcr.yml
.github/workflows/python-tests.yml
.gitignore
.gitmodules
```

### PMOVES Services (Modified)
```
pmoves/.gitignore
pmoves/Makefile
pmoves/__init__.py
pmoves/chit/secrets_manifest_v2.yaml
pmoves/contracts/solidity/package-lock.json
pmoves/db/v5_14_seed_standard_personas.sql
pmoves/docker-compose.*.yml (multiple files)
pmoves/env.shared.example
pmoves/env.tier-media
pmoves/scripts/env_setup.ps1
pmoves/scripts/generate_ports.sh
pmoves/scripts/with-env.sh
pmoves/services/*/Dockerfile
pmoves/services/*/app.py
```

---

## Recovery Commands

### Check Stashes for Deleted Files
```bash
git stash list
git stash show -p stash@{0} | grep -A 10 "SECRETS_MANAGEMENT"
```

### Restore from Git History
```bash
# Find commit that had the files
git log --all --full-history -- "*SECRETS_MANAGEMENT.md"

# Restore specific file from previous commit
git checkout HEAD~1 -- docs/SECRETS_MANAGEMENT.md
```

### Restore Distributed Compute Services
```bash
# From commit f52144a5 (before it was lost)
git checkout f52144a504b151b4b860bea07d1aec6fd2914e2f -- pmoves/services/node-registry/
git checkout f52144a504b151b4b860bea07d1aec6fd2914e2f -- pmoves/services/resource-detector/
git checkout f52144a504b151b4b860bea07d1aec6fd2914e2f -- pmoves/services/vllm-orchestrator/
git checkout f52144a504b151b4b860bea07d1aec6fd2914e2f -- pmoves/services/work-marshaling/
git checkout f52144a504b151b4b860bea07d1aec6fd2914e2f -- pmoves/services/benchmark-runner/
```

---

## Recommended Action Plan

1. **IMMEDIATE** - Restore critical deleted files:
   - `docs/SECRETS_MANAGEMENT.md`
   - Distributed compute services
   - Agent Zero event bus code

2. **HIGH** - Commit or discard submodule changes:
   - Review `PMOVES-Archon` changes
   - Review `PMOVES-ToKenism-Multi` untracked content

3. **MEDIUM** - Add important untracked files:
   - `CLAUDE.md`, `CONTRIBUTING.md`, `LICENSE`
   - GitHub templates and prompts
   - Build scripts

4. **LOW** - Clean up Windows artifacts:
   - All `desktop.ini` deletions are correct (ignore)

---

## Original Git Status (Preserved)

[Original status output preserved below for reference]
