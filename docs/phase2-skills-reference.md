# Phase 2 Skills Reference for Agent Delegation

**Generated:** 2026-01-31
**Purpose:** Map available BoTZ/PMOVES.AI skills to Phase 2 security tasks
**Target:** TAC agents and human collaborators

---

## Available Skills Catalog

### Core Skills (BoTZ)

| Skill | Purpose | Location | Key Files |
|-------|---------|----------|-----------|
| **file-operations** | File analysis, metadata, statistics | BoTZ | `skills/file-operations/SKILL.md` |
| **git-pushing** | Stage, commit, push with conventional commits | BoTZ | `skills/git-pushing/SKILL.md` |
| **feature-planning** | Break down features into implementable plans | BoTZ | `skills/feature-planning/SKILL.md` |
| **python-development** | Python code implementation | BoTZ | `skills/python-development/SKILL.md` |
| **code-review** | Review code for bugs and best practices | BoTZ | `skills/code-review/SKILL.md` |
| **code-documentation** | Generate and update documentation | BoTZ | `skills/code-documentation/SKILL.md` |
| **test-fixing** | Debug and fix failing tests | BoTZ | `skills/test-fixing/SKILL.md` |
| **backend-development** | Backend service implementation | BoTZ | `skills/backend-development/SKILL.md` |
| **javascript-typescript** | JS/TS frontend work | BoTZ | `skills/javascript-typescript/SKILL.md` |
| **docker** | Docker container and compose operations | BoTZ | N/A (native tools) |
| **security** | Security analysis and hardening | N/A | Use Task tool with code-reviewer |
| **networking** | Network configuration and policies | N/A | Use Task tool with Explore |

### MCP Services (Production)

| Service | Port | Purpose | Use For Task |
|---------|------|---------|--------------|
| **TensorZero** | 3030 | LLM gateway | Code analysis, planning |
| **Hi-RAG v2** | 8086 | Knowledge retrieval | Security best practices lookup |
| **Agent Zero** | 8080 | Agent orchestration | Task delegation |
| **Archon** | 8091 | Prompt/form management | Agent configuration |

---

## Task-to-Skill Mapping

### Task 2.2: BuildKit Secrets Migration

**Required Skills:** `file-operations`, `python-development`, `docker`, `git-pushing`

| Subtask | Skill | Agent Type | Prompt Template |
|---------|-------|------------|----------------|
| 2.2.1 Backup Dockerfile | `file-operations` | General | Copy pmoves/services/archon/Dockerfile to pmoves/services/archon/Dockerfile.backup |
| 2.2.2 Remove ARG defaults (lines 49-79) | `python-development` | Plan-implementer | Remove insecure ARG defaults from Archon Dockerfile following phase2-buildkit-secrets-migration-plan.md |
| 2.2.3 Update ENV section | `docker` | General | Update Dockerfile ENV to use only non-sensitive paths |
| 2.2.4 Verify build | `docker` | General | Run docker build and verify no errors |
| 2.2.5 Test runtime config | `python-development` | General | Test that Archon starts with env_file configuration |
| 2.2.6 Document patterns | `code-documentation` | General | Document secure Dockerfile patterns in docs/ |
| 2.2.7 Validation | `code-review` + `security` | code-reviewer | Review Dockerfile for security issues |

**Agent Prompt Template:**
```
Use Task tool with subagent_type='plan-implementer' or 'code-reviewer'

For subtask 2.2.2:
"Update /home/pmoves/PMOVES.AI/pmoves/services/archon/Dockerfile to remove
insecure ARG defaults for secrets (lines 49-79). Follow the migration plan in
/home/pmoves/PMOVES.AI/docs/phase2-buildkit-secrets-migration-plan.md.

Key requirements:
- Remove all ARG defaults for sensitive configuration
- Replace with runtime-only configuration pattern
- Ensure ENV vars use only non-sensitive defaults
- Verify build succeeds after changes
"
```

### Task 2.3: Branch Protection Rules

**Required Skills:** `file-operations`, `git-pushing`

| Subtask | Skill | Agent Type | Action |
|---------|-------|------------|--------|
| 2.3.1-2.3.3 Configure GitHub UI | N/A | **User** | Manual steps via GitHub UI |
| 2.3.4 Create CODEOWNERS | `file-operations` | General | Create .github/CODEOWNERS file |
| 2.3.5 Test dummy PR | `git-pushing` | General | Create test PR to verify rules |
| 2.3.6 Communicate | N/A | **User** | Team notification |

**User Action (2.3.1-2.3.3):**
```
Navigate to: https://github.com/POWERFULMOVES/PMOVES.AI/settings/branches

1. Click "Add branch protection rule"
2. Branch name pattern: main
3. ✅ Require pull request (1 approval)
4. ✅ Require status checks (tests, verify)
5. ✅ Require up-to-date branches
6. ✅ Require conversation resolution
7. ✅ Require signed commits
8. ✅ Require linear history
9. ✅ Apply to administrators
```

**CODEOWNERS Template:**
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

### Task 2.4: Network Policies Design

**Required Skills:** `docker`, `networking`, `kubernetes`, `feature-planning`, `git-pushing`

| Subtask | Skill | Agent Type | Prompt Template |
|---------|-------|------------|----------------|
| 2.4.1 Backup docker-compose.yml | `file-operations` | General | Backup current docker-compose.yml |
| 2.4.2 Create 5 tier networks | `docker` + `networking` | Plan-implementer | Create 5 isolated networks in docker-compose.yml following phase2-network-policies-design.md |
| 2.4.3 Assign services to tiers | `docker` + `architecture` | Plan-implementer | Assign each service to appropriate tier network |
| 2.4.4 Test incremental migration | `testing` | General | Test services tier by tier |
| 2.4.5 Create K8s NetworkPolicies | `kubernetes` + `security` | Plan-implementer | Create NetworkPolicy manifests for 5-tier architecture |
| 2.4.6 Add tier labels | `docker` + `kubernetes` | General | Add tier labels to service definitions |
| 2.4.7 Deploy and validate | `testing` + `networking` | General | End-to-end validation |

**Agent Prompt Template (Subtask 2.4.2):**
```
Use Task tool with subagent_type='plan-implementer'

"Implement 5-tier network segmentation in /home/pmoves/PMOVES.AI/docker-compose.yml
following the design in /home/pmoves/PMOVES.AI/docs/phase2-network-policies-design.md

Network tiers to create:
- API Tier (172.30.1.0/24): agent-zero, archon, pmoves-yt, supaserch, tensorzero-gateway, pmoves-dox
- Application Tier (172.30.2.0/24): hi-rag-gateway-v2, extract-worker, ffmpeg-whisper, media-*
- Bus Tier (172.30.3.0/24): nats
- Data Tier (172.30.4.0/24): postgres, qdrant, neo4j, meilisearch, minio, clickhouse
- Monitoring Tier (172.30.5.0/24): prometheus, grafana, loki, promtail

Requirements:
- Each tier is isolated (no cross-tier access unless explicitly allowed)
- Data tier cannot initiate outbound connections
- Monitoring tier has read access to all tiers
- All services maintain functionality
"
```

---

## Agent Delegation Patterns

### Pattern 1: Sequential Implementation

```
User → Feature Planning → Plan-Implementer → Code Reviewer → Git Pushing
                          ↓
                      (iterate if issues)
```

**Use for:** Task 2.2, Task 2.4 (complex multi-step tasks)

### Pattern 2: User + Agent Hybrid

```
User → Manual GitHub UI (2.3.1-2.3.3)
                ↓
Agent → Create CODEOWNERS (2.3.4)
                ↓
User → Test & Verify (2.3.5-2.3.6)
```

**Use for:** Task 2.3 (Branch Protection)

### Pattern 3: Parallel Execution

```
User → Task 2.3 (15 min)
                ↓
Agent 1 → Task 2.2 (2-3h)     │
                ↓                │
Agent 2 → Task 2.4 (1.5-2h) ←─┘ (after 2.2 complete)
```

**Use for:** Completing all Phase 2 tasks efficiently

---

## TAC Commands for Phase 2

### Available via Agent Zero MCP

| Command | Description | Use For |
|---------|-------------|---------|
| `/botz:start` | Start all BoTZ services | Pre-work |
| `/botz:status` | Check service health | Validation |
| `/cipher:store` | Store memory item | Save progress |
| `/cipher:recall` | Recall memory by query | Retrieve context |

### Custom Commands for Phase 2

```bash
# Task 2.2: BuildKit Secrets
/tac:buildkit-migrate

# Task 2.3: Branch Protection
/tac:branch-protect

# Task 2.4: Network Policies
/tac:network-segment
```

---

## Skill Execution Examples

### Example 1: File Backup (Task 2.2.1)

```bash
# Using file-operations skill
cp pmoves/services/archon/Dockerfile pmoves/services/archon/Dockerfile.backup

# Verify backup
ls -la pmoves/services/archon/Dockerfile*
```

### Example 2: Docker Build Verification (Task 2.2.4)

```bash
# Navigate to service directory
cd pmoves/services/archon

# Build with BuildKit
DOCKER_BUILDKIT=1 docker build -t pmoves-archon:test .

# Verify no secrets in image
docker history pmoves-archon:test --no-trunc | grep -i secret
# Should return empty

# Verify runtime config works
docker run --rm -pmoves/services/archon/.env.test pmoves-archon:test
```

### Example 3: Network Policy Testing (Task 2.4.4)

```bash
# Start with data tier only
docker compose up -d postgres qdrant neo4j

# Verify data tier isolation
docker run --rm --network pmoves_data alpine ping -c 1 google.com
# Should fail (no outbound)

# Start API tier
docker compose up -d agent-zero archon

# Verify API can reach data
docker compose exec agent-zero ping -c 1 postgres
# Should succeed
```

---

## Success Criteria

### Skill Execution Validation

| Criteria | Validation Method |
|----------|-------------------|
| File operations completed | Check file exists, permissions correct |
| Code changes applied | `git diff` shows expected changes |
| Build succeeds | `docker build` exits 0 |
| Runtime works | Service starts, health check passes |
| Tests pass | `pytest` or smoke tests pass |
| Security improved | `docker history` shows no secrets |
| Network segmented | Cross-tier connections blocked as expected |

### Rollback Triggers

If any of these occur, use rollback procedure:
- Build fails → Restore from `.backup` file
- Service won't start → Check ENV var requirements
- Network broken → Revert docker-compose.yml
- Tests fail → Debug with `test-fixing` skill

---

## Best Practices for Agent Delegation

### 1. Always Provide Context

```good
"Update Archon Dockerfile following the BuildKit secrets migration plan at
/home/pmoves/PMOVES.AI/docs/phase2-buildkit-secrets-migration-plan.md.
Remove lines 49-79 which contain ARG defaults for sensitive configuration."
```

```bad
"Update the Dockerfile"
```

### 2. Use Appropriate Agent Types

| Task Complexity | Agent Type | Reason |
|----------------|------------|--------|
| Simple file operations | General | Native Claude tools |
| Code implementation | Plan-implementer | Follows detailed plans |
| Code review | Code-reviewer | Specialized analysis |
| Complex planning | Feature-planning | Breaks down requirements |

### 3. Validate Before Proceeding

After each agent completion:
1. Verify changes with `git diff`
2. Run relevant tests
3. Check service health
4. Store progress in Cipher memory

### 4. Commit Frequently

Use `git-pushing` skill after each subtask:
```bash
bash skills/git-pushing/scripts/smart_commit.sh "feat(security): Remove ARG defaults from Archon Dockerfile"
```

---

## Phase 2 Completion Checklist

### Documentation
- [x] Task breakdown created
- [x] Skills reference created
- [ ] Task 2.2 plan (exists at phase2-buildkit-secrets-migration-plan.md)
- [ ] Task 2.3 guide (exists at phase2-branch-protection-guide.md)
- [ ] Task 2.4 design (exists at phase2-network-policies-design.md)

### Implementation
- [ ] Task 2.1 ✅ (DONE)
- [ ] Task 2.2: BuildKit Secrets
- [ ] Task 2.3: Branch Protection
- [ ] Task 2.4: Network Policies

### Validation
- [ ] All security scans pass
- [ ] All services functional
- [ ] Documentation updated
- [ ] Team trained

---

## Quick Reference

### File Locations

| Resource | Path |
|----------|------|
| Task breakdown | `/home/pmoves/PMOVES.AI/docs/phase2-task-breakdown.md` |
| Skills reference | `/home/pmoves/PMOVES.AI/docs/phase2-skills-reference.md` |
| BuildKit plan | `/home/pmoves/PMOVES.AI/docs/phase2-buildkit-secrets-migration-plan.md` |
| Branch guide | `/home/pmoves/PMOVES.AI/docs/phase2-branch-protection-guide.md` |
| Network design | `/home/pmoves/PMOVES.AI/docs/phase2-network-policies-design.md` |
| Main plan | `/home/pmoves/PMOVES.AI/docs/phase2-security-hardening-plan.md` |
| BoTZ skills | `/home/pmoves/PMOVES.AI/PMOVES-DoX/external/PMOVES-BoTZ/.claude/skills/` |

### Common Commands

```bash
# Backup a file before editing
cp path/to/file path/to/file.backup

# Check git status
git status

# View changes
git diff

# Run smoke tests
cd pmoves && make verify-all

# Check service health
curl http://localhost:8080/healthz  # Agent Zero
curl http://localhost:8091/healthz  # Archon

# Store progress in Cipher
docker exec -i pmz-cipher python3 - << 'EOF'
{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "store_memory", "arguments": {"key": "phase2-task2.2", "content": "BuildKit migration in progress"}}}
EOF
```

---

**Next Steps:**
1. Review this skills reference
2. Choose starting task (recommend Task 2.3 for quick win)
3. Delegate appropriate subtasks to agents
4. Validate each completion before proceeding
5. Store progress for session continuity
