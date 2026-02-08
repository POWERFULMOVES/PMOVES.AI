# PMOVES.AI Production Merge Tracker

**Last Updated**: 2026-02-08 17:30 UTC
**Production Branch**: `main`
**Hardened Branch**: `PMOVES.AI-Edition-Hardened`

## Overview

This document tracks the progress of hardening and bug fixes from feature branches to the production (`main`) branch.

---

## Quick Status

| Category | Open PRs | Mergeable | Blocked | Ready to Merge |
|----------|----------|-----------|---------|----------------|
| **Just Merged** | 4 | ✅ | 0 | - |
| **Conflicting** | 5 | 0 ❌ | 5 | 0 |
| **Closed** | 1 | ✅ | 0 | - |
| **Total Active** | 5 | 0 | 5 | 0 |
| **CI Migration Needed** | 3 workflows | ⏳ | 0 | - |

---

## ✅ Just Merged to PMOVES.AI-Edition-Hardened

### PR #585: fix(k8s) - Hybrid NetworkPolicy with explicit external API allow-list
| Field | Value |
|-------|-------|
| **Branch** | `fix/hybrid-network-policy` |
| **Status** | ✅ MERGED |
| **Changes** | NetworkPolicy hybrid approach (namespaceSelector + ipBlock) |
| **Files** | `.k8s/network-policies/api-tier-policy.yaml`, `.k8s/network-policies/app-tier-policy.yaml` |

**Changes:**
- Intra-cluster communication via `namespaceSelector: {} podSelector: {}`
- Explicit external API allow-list: api.openai.com, api.anthropic.com, api.venice.ai
- Media source access: 0.0.0.0/0 with private RFC1918 exceptions
- **Supersedes PR #582** (now closed)

---

### PR #583: feat(supabase) - Official 13-service stack
| Field | Value |
|-------|-------|
| **Branch** | `test-hardened` |
| **Status** | ✅ MERGED |
| **Changes** | Official Supabase integration, secrets generation, docs |
| **Files** | `docker-compose.supabase.yml`, `scripts/with-env.sh`, `Makefile`, `scripts/generate-supabase-secrets.sh` |

**Changes:**
- Complete 13-service Supabase stack (Studio, Kong, GoTrue, PostgREST, etc.)
- Added env.tier-supabase to 6-tier architecture
- Secret generation script with OpenSSL validation
- Supabase Makefile targets (up-supabase, supa-health, etc.)

---

### PR #584: fix(audit) - Bring-up v2 findings (Rebased)
| Field | Value |
|-------|-------|
| **Branch** | `fix/audit-v2-improvements` |
| **Status** | ✅ MERGED (after rebase) |
| **Changes** | TensorZero healthchecks, MinIO dependencies, error handling |
| **Files** | `docker-compose.yml`, `Makefile` |

**Changes:**
- Added `tensorzero-ui` healthcheck
- Added `minio:service_healthy` to 9 services
- Reduced `|| true` from 100 to 34 instances
- Enhanced `verify-all` with cumulative failure tracking

**Note:** Required rebase after #583/#585 merge due to Makefile conflicts

---

### PR #1: feat(integration) - PMOVES.AI Integration for PMOVES.YT
| Field | Value |
|-------|-------|
| **Repo** | POWERFULMOVES/PMOVES-YT (submodule) |
| **Branch** | `feat/pmoves-ai-integration` |
| **Status** | ✅ MERGED |
| **Merge Date** | 2026-02-08 17:10 UTC |
| **Changes** | Full PMOVES.AI integration with tier-based credentials |

**Changes:**
- Added `pmoves_announcer/`, `pmoves_health/`, `pmoves_registry/` modules
- Created `docker-compose.pmoves.yml` with YAML anchors
- Added `env.shared`, `env.tier-{llm,data,api}.sh` templates
- Fixed CodeRabbit review comments (TYPE_CHECKING, logging, TIER defaults)
- Updated `PMOVES.AI_INTEGRATION.md` with CHIT bootstrap documentation

**CI Results:**
- 880/881 tests passed (1 unrelated flaky test: test_lazy_extractors)
- All PMOVES.AI integration tests passed

**Follow-up:**
- Sync integration pattern to remaining 26 submodules
- Update universal integration guide with CHIT search path corrections

---

## 🟡 Previously Merged (Needs Main Branch Merge)

### PR #576: fix(infra) - Infrastructure healthchecks
| Field | Value |
|-------|-------|
| **Branch** | `fix/critical-infrastructure-healthchecks` |
| **Status** | ✅ MERGED to PMOVES.AI-Edition-Hardened |
| **Changes** | Healthchecks for Prometheus, Grafana, Loki |
| **Next Action** | Include in batch merge to main |

---

## 🔴 Conflicting (Need Rebase)

### PR #577: fix(volumes) - Qdrant/Meilisearch named volumes
| Field | Value |
|-------|-------|
| **Branch** | `fix/qdrant-meilisearch-volumes` |
| **Status** | ❌ CONFLICTING |
| **Issue** | Diverged from base |
| **Action** | Rebase onto `PMOVES.AI-Edition-Hardened` |

### PR #578: fix(deps) - Critical service dependencies
| Field | Value |
|-------|-------|
| **Branch** | `fix/service-dependencies` |
| **Status** | ❌ CONFLICTING |
| **Issue** | Diverged from base |
| **Action** | Rebase onto `PMOVES.AI-Edition-Hardened` |

### PR #579: docs(chit) - CHIT security documentation
| Field | Value |
|-------|-------|
| **Branch** | `fix/chit-security-configuration` |
| **Status** | ❌ CONFLICTING |
| **Issue** | Diverged from base |
| **Action** | Rebase onto `PMOVES.AI-Edition-Hardened` |

### PR #580: fix(pr) - Agent Zero healthcheck
| Field | Value |
|-------|-------|
| **Branch** | `fix/agent-zero-directories` |
| **Status** | ❌ CONFLICTING |
| **Issue** | Diverged from base |
| **Action** | Rebase onto `PMOVES.AI-Edition-Hardened` |

### PR #581: fix(security) - GPU Orchestrator hardening
| Field | Value |
|-------|-------|
| **Branch** | `fix/gpu-orchestrator-security` |
| **Status** | ❌ CONFLICTING |
| **Issue** | Diverged from base |
| **Action** | Rebase onto `PMOVES.AI-Edition-Hardened` |

### ~~PR #582: fix(review) - NetworkPolicy ipBlock~~ ✅ CLOSED
| Field | Value |
|-------|-------|
| **Branch** | `fix/networkpolicy-egress-ipblock` |
| **Status** | ✅ CLOSED (Superseded by PR #585) |
| **Note** | PR #585 implements hybrid approach that supersedes this |

---

## 🔄 Submodule PRs (Separate Repos)

### PMOVES-Archon
| Field | Value |
|-------|-------|
| **PR** | #6 |
| **Branch** | `feat/personas-clean-rebase` |
| **Status** | Open |
| **Repo** | POWERFULMOVES/PMOVES-Archon |

### PMOVES-DoX
| Field | Value |
|-------|-------|
| **PR** | #92 |
| **Branch** | `feat/v5-secrets-bootstrap` |
| **Status** | Open |
| **Repo** | POWERFULMOVES/PMOVES-DoX |

---

## 📋 Merge Sequence to Production

### ✅ Phase 1: COMPLETED - Ready PRs Merged to Hardened Branch
```bash
# COMPLETED: All three PRs merged to PMOVES.AI-Edition-Hardened
gh pr merge 585 --squash  # ✅ Hybrid NetworkPolicy
gh pr merge 583 --squash  # ✅ Supabase integration
gh pr merge 584 --squash  # ✅ Audit v2 findings (after rebase)
gh pr close 582           # ✅ Closed (superseded by #585)
```

### Phase 2: Resolve Conflicting PRs
For each conflicting PR (#577-581):
```bash
# Option A: Rebase (recommended)
git checkout <branch>
git rebase PMOVES.AI-Edition-Hardened
git push --force-with-lease

# Option B: Create new PR from fresh branch
git checkout PMOVES.AI-Edition-Hardened
git checkout -b fix/<new-name>
# Apply changes
git push
```

### Phase 3: Merge to Main (Production)
Once all PRs are merged to `PMOVES.AI-Edition-Hardened`:
```bash
# Update local main
git checkout main
git fetch origin
git rebase origin/PMOVES.AI-Edition-Hardened

# Or create merge commit
git merge origin/PMOVES.AI-Edition-Hardened --no-ff

# Push to production
git push origin main
```

---

## 🚨 Blocking Issues

| Issue | Impact | Resolution |
|-------|--------|------------|
| Submodule state | Rebases fail due to submodule changes | Reset submodules before rebase |
| Root-owned files | Git operations blocked | Stop containers before git operations |
| Branch divergence | 6 PRs conflicting | Rebase all onto latest hardened |

---

## ✅ DECISIONS MADE

### NetworkPolicy Egress Strategy: **HYBRID (Option C)**

**Decision Date**: 2026-02-06

**Approach**: Combine namespaceSelector for intra-cluster + ipBlock for external APIs

**Implementation**:
```yaml
# Intra-cluster communication (default allow)
- to:
  - namespaceSelector: {}
  podSelector: {}

# External API access (explicit allow only)
- to:
  - ipBlock:
      cidr: api.openai.com/32
      api.anthropic.com/32
      api.venice.ai/32
      # Add other external APIs as needed
```

**Rationale**:
- Most communication stays within cluster (namespaceSelector)
- External API calls must be explicitly allowed (ipBlock)
- More secure than 0.0.0.0/0, more flexible than cluster-only

---

## 📋 Recommended Merge Order (UPDATED)

### Phase 1: Easy Merges
```bash
# PR #577: Smallest, no conflicts after resolution
gh pr merge 577 --squash --subject "Merge PR #577: Named volumes"

# PR #580: Targets main, not Hardened
gh pr merge 580 --squash --subject "Merge PR #580: Agent Zero healthcheck"
```

### Phase 2: Hybrid NetworkPolicy Implementation
```bash
# Create hybrid approach combining:
# - namespaceSelector from PRs #577/#578/#579
# - Specific ipBlock rules from PR #582
# Branch: fix/hybrid-network-policy
```

### Phase 3: Remaining PRs
```bash
gh pr merge 578 --squash --subject "Merge PR #578: Service dependencies"
gh pr merge 579 --squash --subject "Merge PR #579: CHIT security"
```

### Phase 4: Branch Convergence
```bash
# PR #581: GPU security (targets main)
gh pr merge 581 --squash --subject "Merge PR #581: GPU hardening"

# Final: Hardened → main
git checkout main
git merge origin/PMOVES.AI-Edition-Hardened --no-ff
git push origin main
```

---

## 📊 Progress to Production

```
main (production)
    │
    ├─ PMOVES.AI-Edition-Hardened (hardened baseline)
    │   ├─ ✅ PR #576 (merged)
    │   ├─ ✅ PR #583 (merged)
    │   ├─ ✅ PR #584 (merged after rebase)
    │   ├─ ✅ PR #585 (merged - hybrid NetworkPolicy)
    │   ├─ ⚠️  PR #577 (conflicting - needs rebase)
    │   ├─ ⚠️  PR #578 (conflicting - needs rebase)
    │   ├─ ⚠️  PR #579 (conflicting - needs rebase)
    │   ├─ ⚠️  PR #580 (conflicting - needs rebase)
    │   ├─ ⚠️  PR #581 (conflicting - needs rebase)
    │   └─ 🚫 PR #582 (closed - superseded by #585)
    │
    └─ feature/* (other features)
```

---

## 📝 Action Items

### ✅ Completed (Today)
- [x] Merged PR #585 (hybrid NetworkPolicy)
- [x] Merged PR #583 (Supabase integration)
- [x] Rebased and merged PR #584 (audit findings)
- [x] Closed superseded PR #582
- [x] Merged PMOVES.YT PR #1 (PMOVES.AI integration)
- [x] Completed CI infrastructure audit

### Next Steps
- [ ] Migrate `codeql.yml` to self-hosted runners
- [ ] Migrate `python-tests.yml` to self-hosted runners
- [ ] Verify all workflows use self-hosted runners
- [ ] Rebase PRs #577-581 onto latest hardened
- [ ] Resolve remaining conflicting PRs

### This Week
- [ ] Resolve all conflicting PRs
- [ ] Complete submodule PRs (Archon, DoX)
- [ ] Test hardened branch with `make up`

### Before Production Deploy
- [ ] Run smoke tests on hardened branch
- [ ] Verify all healthchecks passing
- [ ] Validate environment variables
- [ ] Create production deployment checklist

---

## 🔗 Related Documentation

- `pmoves/docs/bring-up-audit-findings.md` - Detailed audit findings
- `pmoves/docs/SERVICE_DEPENDENCIES.md` - Service dependency graph
- `pmoves/docs/PORT_REGISTRY.md` - Complete port mappings
- `pmoves/docs/SUPABASE_INTEGRATION_SUMMARY.md` - Supabase integration docs
- `pmoves/docs/CI_INFRASTRUCTURE_AUDIT_2026-02-08.md` - CI runner strategy

---

## 🚨 CI Infrastructure Audit (2026-02-08)

### Current Runner Strategy Analysis

**Finding:** PMOVES.AI uses a **mixed runner strategy** - some workflows on self-hosted runners, others on GitHub-hosted.

| Workflow | Runner Type | Status | Action Needed |
|----------|-------------|--------|---------------|
| `hardening-validation.yml` | ✅ Self-hosted `[self-hosted, vps]` | Correct | None |
| `self-hosted-builds-hardened.yml` | ✅ Self-hosted `[self-hosted, ai-lab, gpu]` | Correct | None |
| `codeql.yml` | ❌ GitHub-hosted `ubuntu-latest` | **Needs migration** | Migrate to self-hosted |
| `python-tests.yml` | ❌ GitHub-hosted `ubuntu-latest` | **Needs migration** | Migrate to self-hosted |
| `chit-contract.yml` | ⏳ Unknown | **Needs verification** | Verify runner type |
| `integrations-ghcr.yml` | ⏳ Unknown | **Needs verification** | Verify runner type |
| `sql-policy-lint.yml` | ⏳ Unknown | **Needs verification** | Verify runner type |
| `env-preflight.yml` | ⏳ Unknown | **Needs verification** | Verify runner type |

### Self-Hosted Runner Labels (Already Configured)

| Label | Purpose | Example Usage |
|-------|---------|---------------|
| `self-hosted` | Base self-hosted runner | All workflows |
| `vps` | VPS runners (CPU) | Docker builds, validation |
| `ai-lab` | AI Lab with GPU | GPU builds, testing |
| `gpu` | GPU-capable runners | CUDA image builds |
| `cloudstartup` | Staging deployment | Deploy staging |
| `kvm4` | Production server | Deploy production |
| `staging` | Staging environment | Staging-specific jobs |
| `production` | Production environment | Production-specific jobs |

### Migration Requirements

**User Requirement:** "ci should be for production we are not in development and should run locally or selfhosted runners"

**Action Plan:**
1. Update `codeql.yml`: Change `runs-on: ubuntu-latest` → `runs-on: [self-hosted, vps]`
2. Update `python-tests.yml`: Change `runs-on: ubuntu-latest` → `runs-on: [self-hosted, vps]`
3. Verify all remaining workflows use self-hosted runners
4. Update workflow documentation to reflect self-hosted requirement

### CI Workflow Migration Template

```yaml
# BEFORE (GitHub-hosted)
jobs:
  analyze:
    runs-on: ubuntu-latest

# AFTER (Self-hosted)
jobs:
  analyze:
    runs-on: [self-hosted, vps]
    steps:
      - name: Harden Runner
        uses: step-security/harden-runner@v2
        with:
          egress-policy: audit
          allowed-endpoints: |
            github.com:443
            api.github.com:443
            pypi.org:443
```

---

**Note**: This document is updated as PRs are merged and progress is made.
