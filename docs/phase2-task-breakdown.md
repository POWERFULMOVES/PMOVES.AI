# Phase 2 Security Hardening - Task Breakdown with Dependencies

**Generated:** 2026-01-31
**Phase:** 2 of 3 (Infrastructure Security)
**Overall Completion:** 25% (Task 2.1 complete, 2.2-2.4 pending)

---

## Task Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PHASE 2 TASKS                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │   Task 2.1   │──────│   Task 2.3   │      │   Task 2.2   │      │
│  │Harden-Runner │ DONE │Branch Protect│ TODO  │BuildKit Secs │ TODO  │
│  │  ✅ DONE     │      │  (15 min)    │      │  (2-3h TAC)  │      │
│  └──────────────┘      └──────────────┘      └──────┬───────┘      │
│         │                      │                      │              │
│         │                      ▼                      │              │
│         │              ┌──────────────┐             │              │
│         │              │   PR #???    │             │              │
│         │              │ (CODEOWNERS) │             │              │
│         │              └──────────────┘             │              │
│         │                      │                      │              │
│         ▼                      ▼                      ▼              │
│  ┌───────────────────────────────────────────────────────────┐    │
│  │                     Task 2.4                             │    │
│  │              Network Policies (1.5-2h TAC)              │    │
│  │                 Depends on: 2.2, 2.3                   │    │
│  └───────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Task 2.1: Harden-Runner ✅ COMPLETED

**Status:** Deployed in production
**Completion Date:** 2025-12-05
**Documentation:** `.github/workflows/` (all workflows updated)

### Deliverables
- [x] All 7 GitHub Actions workflows protected with Harden-Runner
- [x] Network egress monitoring enabled
- [x] Audit mode active, collecting baseline data
- [x] Metrics available at StepSecurity dashboard

### Next Steps
- [ ] Monitor egress patterns for 1 week
- [ ] Transition from `audit` to `block` mode (Phase 3)
- [ ] Review and whitelist legitimate endpoints

---

## Task 2.2: BuildKit Secrets Migration

**Status:** Ready for TAC implementation
**Priority:** HIGH (Critical security fix)
**Effort:** 2-3 hours with TAC
**Dependencies:** None (can start anytime)
**Blocks:** Task 2.4 (recommended to complete before network policies)

### Documentation
- **Plan:** `/home/pmoves/PMOVES.AI/docs/phase2-buildkit-secrets-migration-plan.md`
- **Target File:** `/home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile`

### Subtasks

| ID | Task | Effort | Skill Required | Status |
|----|------|--------|----------------|--------|
| 2.2.1 | Backup current Dockerfile | 5 min | file-operations | TODO |
| 2.2.2 | Remove lines 49-79 (ARG defaults) | 30 min | docker, security | TODO |
| 2.2.3 | Update ENV section to non-sensitive paths | 15 min | docker | TODO |
| 2.2.4 | Verify build succeeds without ARG defaults | 15 min | docker, testing | TODO |
| 2.2.5 | Test runtime configuration via env_file | 20 min | testing | TODO |
| 2.2.6 | Document secure patterns | 30 min | documentation | TODO |
| 2.2.7 | Validation testing | 30 min | testing, security | TODO |

### Validation Checklist
- [ ] `docker history` shows no secrets
- [ ] `docker inspect` shows no sensitive ENV vars
- [ ] Build cache contains no secrets
- [ ] Runtime configuration works via env_file
- [ ] Service starts and functions correctly

### Agent Skills Required
- `docker` - Dockerfile modification and build operations
- `security` - Security pattern validation
- `file-operations` - Backup and file modification
- `testing` - Runtime validation

---

## Task 2.3: Branch Protection Rules

**Status:** Ready for user implementation
**Priority:** HIGH (Quick win - foundational security)
**Effort:** 15 minutes via GitHub UI
**Dependencies:** None (can start anytime)
**Blocks:** Task 2.4 (recommended for proper git workflow)

### Documentation
- **Guide:** `/home/pmoves/PMOVES.AI/docs/phase2-branch-protection-guide.md`
- **GitHub UI:** `https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches`

### Subtasks

| ID | Task | Effort | Actor | Status |
|----|------|--------|-------|--------|
| 2.3.1 | Navigate to GitHub branch settings | 2 min | User | TODO |
| 2.3.2 | Add branch protection rule for `main` | 1 min | User | TODO |
| 2.3.3 | Configure required settings (see below) | 5 min | User | TODO |
| 2.3.4 | Create `.github/CODEOWNERS` file | 3 min | Agent | TODO |
| 2.3.5 | Test with dummy PR | 3 min | User | TODO |
| 2.3.6 | Communicate to team | 1 min | User | TODO |

### Required Settings Configuration

```
Branch: main

✅ Require pull request before merging
   - Approvals required: 1
   - Dismiss stale reviews: enabled

✅ Require status checks to pass
   - Required checks: tests, verify
   - Require branches to be up to date

✅ Require conversation resolution
   - Mark as resolved

✅ Require signed commits
   - GPG signature required

✅ Linear history
   - Merge method: squash or merge

✅ Apply to administrators
   - Include admins in rules

❌ Lock branch (disabled)
❌ Require deployments (disabled)
```

### CODEOWNERS Template

```yaml
# CATACLYSM_STUDIOS_INC requires admin approval
/CATACLYSM_STUDIOS_INC/ @POWERFULMOVES/admin

# Infrastructure changes require ops approval
*.yml @POWERFULMOVES/ops
*.yaml @POWERFULMOVES/ops
.github/ @POWERFULMOVES/ops

# Security changes require security review
**/SECURITY.md @POWERFULMOVES/security
**/jwt.py @POWERFULMOVES/security
**/auth/** @POWERFULMOVES/security
```

### Validation Checklist
- [ ] Direct push to `main` fails with error
- [ ] PR without approval cannot merge
- [ ] Unsigned commits are rejected
- [ ] Failing CI blocks merge
- [ ] Dummy PR workflow completes successfully

### Agent Skills Required
- `git` - CODEOWNERS file creation
- `documentation` - Team communication

---

## Task 2.4: Network Policies Design

**Status:** Ready for TAC implementation
**Priority:** HIGH (Defense-in-depth)
**Effort:** 1.5-2 hours with TAC
**Dependencies:** Task 2.2, Task 2.3 (recommended)
**Blocks:** None (final Phase 2 task)

### Documentation
- **Design:** `/home/pmoves/PMOVES.AI/docs/phase2-network-policies-design.md`
- **Files to Modify:**
  - `docker-compose.yml`
  - `pmoves/docker-compose.networks.yml` (new)
  - `.k8s/network-policies/` (new directory)

### Subtasks

| ID | Task | Effort | Skill Required | Status |
|----|------|--------|----------------|--------|
| 2.4.1 | Backup current docker-compose.yml | 5 min | file-operations | TODO |
| 2.4.2 | Create 5 tier networks in docker-compose | 15 min | docker, networking | TODO |
| 2.4.3 | Assign services to appropriate tiers | 45 min | docker, architecture | TODO |
| 2.4.4 | Test incremental migration (tier by tier) | 30 min | testing, networking | TODO |
| 2.4.5 | Create Kubernetes NetworkPolicy manifests | 20 min | kubernetes, security | TODO |
| 2.4.6 | Add tier labels to service definitions | 10 min | docker, kubernetes | TODO |
| 2.4.7 | Deploy and validate end-to-end | 15 min | testing, deployment | TODO |

### Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      EXTERNAL                                │
│                      (Internet)                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   API TIER (172.30.1.0/24)                   │
│  • agent-zero, archon, pmoves-yt, supaserch                │
│  • tensorzero-gateway, pmoves-dox                           │
│  • Inbound from External, outbound to App + Bus            │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              APPLICATION TIER (172.30.2.0/24)                │
│  • hi-rag-gateway-v2, extract-worker, ffmpeg-whisper        │
│  • media-*, language-*, notebook-sync                        │
│  • Inbound from API, outbound to Bus + Data                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 BUS TIER (172.30.3.0/24)                     │
│  • nats                                                    │
│  • Central message bus, all tiers connect                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 DATA TIER (172.30.4.0/24)                    │
│  • postgres, qdrant, neo4j, meilisearch                    │
│  • minio, clickhouse                                       │
│  • Inbound only (no outbound)                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              MONITORING TIER (172.30.5.0/24)                │
│  • prometheus, grafana, loki, promtail                     │
│  • Read access to all tiers                                 │
└─────────────────────────────────────────────────────────────┘
```

### Service Tier Assignments

| Tier (172.30.X.0/24) | Services |
|----------------------|----------|
| **API (1)** | agent-zero, archon, pmoves-yt, supaserch, tensorzero-gateway, pmoves-dox |
| **Application (2)** | hi-rag-gateway-v2, hi-rag-gateway, extract-worker, ffmpeg-whisper, media-video, media-audio, language-detection, notebook-sync, publisher-discord |
| **Bus (3)** | nats |
| **Data (4)** | postgres, qdrant, neo4j, meilisearch, minio, clickhouse |
| **Monitoring (5)** | prometheus, grafana, loki, promtail, cAdvisor |

### Validation Checklist
- [ ] Data tier cannot initiate outbound connections
- [ ] Unauthorized cross-tier connections blocked
- [ ] Allowed service communication succeeds
- [ ] Monitoring can still scrape all services
- [ ] NATS can communicate with all services
- [ ] External API access still works

### Agent Skills Required
- `docker` - Docker Compose network configuration
- `networking` - Network segmentation and policy design
- `kubernetes` - NetworkPolicy manifest creation
- `testing` - Incremental migration validation
- `architecture` - Service dependency analysis

---

## Implementation Order

### Option A: Linear (Recommended)

```
Week 1, Day 1:
├── Task 2.3: Branch Protection (15 min) ← START HERE
│   └── Creates secure git workflow
│
Week 1, Day 1-2:
├── Task 2.2: BuildKit Secrets (2-3h)
│   └── Critical security fix, unblocks 2.4
│
Week 1, Day 2-3:
└── Task 2.4: Network Policies (1.5-2h)
    └── Final defense-in-depth layer
```

### Option B: Parallel (With Multiple Agents)

```
Task 2.3 (User) ──────────────────┐
                                  ├──> Complete Phase 2
Task 2.2 (Agent 1) ───────────────┘
Task 2.4 (Agent 2) ──┬─────────────┘ (after 2.2)
```

---

## Risk Mitigation

### Rollback Procedures

| Task | Rollback Command | Time |
|------|------------------|------|
| 2.2 | `git checkout HEAD~ -- pmoves/services/archon/Dockerfile` | 1 min |
| 2.3 | Disable rules via GitHub UI | 2 min |
| 2.4 | `git checkout HEAD~ -- docker-compose.yml` | 1 min |

### Validation Gates

1. **Pre-Implementation**: All backups created
2. **Mid-Implementation**: Service still runs after each change
3. **Post-Implementation**: All validation tests pass
4. **Sign-off**: Security scan confirms improvements

---

## Phase 2 Completion Criteria

- [ ] Task 2.1: Harden-Runner ✅ (DONE)
- [ ] Task 2.2: BuildKit Secrets migration complete
- [ ] Task 2.3: Branch protection rules active
- [ ] Task 2.4: Network policies deployed
- [ ] All validation tests passed
- [ ] Security scanning confirms improvements
- [ ] Documentation updated with implementation notes
- [ ] Team trained on new workflows

**When all items checked: Phase 2 Complete → Ready for Phase 3**
