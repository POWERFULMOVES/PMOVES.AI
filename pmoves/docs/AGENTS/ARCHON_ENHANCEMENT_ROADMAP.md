# Archon Enhancement Roadmap

**Created:** 2026-07-11 (B850 GLM session; adopted + claimed by B850-CLAUDE same day)
**Status:** Active — P0 lanes claimed by B850-CLAUDE (see Active Claim Register)
**Research Sources:** Industry best practices + PMOVES SITREP/BOOTSTRAP context

**Lane state (2026-07-11):** CHIT Signing Tutorial ✅ shipped (PR #2078). The five
remaining P0 lanes are **local session state only** — `.claude/worktrees/` is
git-ignored and these branches were not pushed, so they are not reproducible from a
clean checkout. To recreate them on any node, run from the repo root:

```bash
for lane in p0-chit-completion p0-agent-roles p0-evaluation-gates p0-pr-triage p0-archon-guide; do
  git worktree add -b "$lane" ".claude/worktrees/$lane" origin/main
done
```

(Each is branched from `main` with no commits yet.) CHIT Completion scoping from the
GLM session: Consciousness (8106) ~85% signed, Evo Controller (8113) 0%, A2UI (9224)
is a consumer.

---

## Executive Summary

Post-Archon bring-up enhancements organized by priority (P0/P1/P2) with effort estimates. Based on 2025 multi-agent orchestration patterns, CHIT security requirements, and PMOVES Three-Body governance model.

**Total Effort:** P0 (~12 days), P1 (~15 days), P2 (~18 days)

---

## 1. Archon Integration Patterns

### Current State
- HERMES Agent Integration complete (2026-06-04)
- Archon CI green (lint + E2E)
- Fleet fork-sync campaign completed (31 forks)

### Industry Patterns (2025)
| Pattern | Description | PMOVES Alignment |
|---------|-------------|------------------|
| Supervisor | Central coordinator delegates | Three-Body Control Body |
| Fan-out/Fan-in | Parallel + aggregation | Village Rule validation |
| Pipeline | Sequential handoffs | CHIT signing flow |
| Debate | Vote/resolve conflicts | Delivery Body review |
| Adaptive Handoff | Dynamic routing | Agent Zero orchestration |

**Sources:**
- [Kore.ai - Orchestration Patterns](https://www.kore.ai/blog/choosing-the-right-orchestration-pattern-for-multi-agent-systems)
- [Beam AI - Production Patterns](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production)
- [LangChain - Multi-Agent Architecture](https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture)

---

## 2. Multi-Agent Orchestration Enhancements

### P0 - Immediate (5 days)
1. **Agent Role Consolidation** (2d)
   - Reduce to core roles: planner, worker, reviewer
   - Align with community best practices
   - Update Archon agent registry

2. **Evaluation Gates** (2d)
   - Add automated evaluator gates before Village Rule signoff
   - Implement quality threshold checks
   - Wire to Prometheus metrics

3. **Stop Conditions** (1d)
   - Enforce timeout/iteration limits
   - Prevent infinite loops in agent loops
   - Add circuit breaker pattern

### P1 - Short-term (10 days)
1. **Conflict Resolution** (5d)
   - Implement voting/consensus mechanism
   - Target: 70% conflict reduction (per industry research)
   - Add negotation framework

2. **Handoff Protocol** (3d)
   - Standardize agent→agent handoff
   - Intent negotiation format
   - NATS subject patterns

3. **Observability** (2d)
   - Per-agent telemetry to Prometheus
   - Grafana dashboards
   - Alert rules

### P2 - Long-term
1. Adaptive Planning
2. Multi-Agent Debate
3. Swarm Intelligence

**Sources:**
- [Zylos 2025 Research](https://zylos.ai/research/multi-agent-orchestration-2025)
- [Microsoft Azure - Agent Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)

---

## 3. CHIT-Aware Service Improvements

### Current CHIT Services
| Service | CHIT Status |
|---------|-------------|
| Tokenism Simulator (8103) | Full |
| Hi-RAG v2 (8086/8087) | Full |
| Gateway | Full |
| Consciousness (8106) | **Partial** |
| Evo Controller (8113) | **Partial** |
| A2UI NATS Bridge (9224) | **Partial** |

### P0 - CHIT Completion (5 days)
1. **Consciousness CHIT Signing** (2d)
   - Complete CHIT signing implementation
   - Add tier guarantee enforcement
   - Wire to chit_manifest_merge.py

2. **Evo Controller CHIT Signing** (2d)
   - Complete CHIT signing implementation
   - Add signature verification
   - Integration testing

3. **Archon CHIT Verification Gate** (1d)
   - Add CHIT check to agent minting flow
   - Block unsigned agents in production
   - Developer override for testing

### P1 - Additional CHIT (1 day)
1. **A2UI NATS Bridge CHIT Signing** (1d)
   - Add CHIT signing to bridge
   - Verify signature trails

### P2 - CI Automation
1. Automated CHIT compliance checks in CI
2. Pre-commit CHIT verification
3. Signature validation in PR tests

**Sources:**
- [OWASP - Microservices Security](https://cheatsheetseries.owasp.org/cheatsheets/Microservices_Security_Cheat_Sheet.html)
- [Tigera - Security Patterns](https://www.tigera.io/learn/guides/microservices-security/)

---

## 4. Workflow Automations

### P0 - CI/CD Efficiency (5 days)
1. **Automated PR Triage** (2d)
   - Label PRs based on changed files
   - Auto-assign to reviewers
   - Route to control-body for CHIT changes

2. **CHIT Sign Automation** (2d)
   - Auto-generate sign-trail entries on merge
   - Integrate with Village Rule workflow
   - Emit to NATS chit.signed.v1

3. **Fork Health Monitoring** (1d)
   - Alert on drift > N commits
   - GitHub Actions workflow
   - Fleet-wide dashboard

### P1 - Testing & Docs (6 days)
1. **Agent Deployment CI** (3d)
   - Automated agent image build
   - Deploy to staging environment
   - Health check validation

2. **Testing Automation** (2d)
   - Run `/test:pr` on every push
   - Parallel test execution
   - Results aggregation

3. **Documentation Sync** (1d)
   - Auto-update AGNOTE4482 on PR merge
   - Living docs refresh trigger
   - Conflict detection

### P2 - Operations
1. Self-Healing Fleet (10d)
2. Predictive Scaling (8d)
3. Automated Backport (5d)

---

## 5. Documentation Gaps

### Current State
- Living docs registry configured
- Multiple convergence waves documented
- MOF Architecture + Grand Convergence shipped

### Identified Gaps

| Gap | Priority | Effort | Owner |
|-----|----------|--------|-------|
| Archon Integration Guide | **P0** | 2d | B850-CLAUDE |
| CHIT Signing Tutorial | **P0** | 1d | ✅ B850 (PR #2078) |
| Troubleshooting Playbook | **P1** | 3d | TBD |
| Agent Development Quickstart | **P1** | 2d | TBD |
| Multi-GPU Setup Guide (RDNA4) | **P1** | 1d | B850 |
| Fleet Operations Manual | **P2** | 5d | Ops |

### P0 - Documentation (3 days)
1. **Archon Integration Guide** (2d)
   - Agent minting flow
   - Room manifest configuration
   - NATS subject patterns
   - CHIT signing requirements
   - Testing procedures

2. **CHIT Signing Tutorial** (1d)
   - Quickstart for agents
   - Common patterns
   - Troubleshooting
   - Examples

### P1 - Additional Docs (6 days)
1. Troubleshooting Playbook (3d)
2. Agent Development Quickstart (2d)
3. Multi-GPU RDNA4 Setup Guide (1d)

---

## Summary: Prioritized Roadmap

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P0** | CHIT Completion (Consciousness/Evo/A2UI) | 5d | Security hardening |
| **P0** | Agent Role Consolidation | 2d | Agent quality |
| **P0** | Evaluation Gates | 3d | Quality assurance |
| **P0** | Automated PR Triage | 2d | CI/CD efficiency |
| **P0** | Archon Integration Guide | 2d | Developer onboarding |
| **P0** | CHIT Signing Tutorial | 1d | Knowledge transfer |
| **P1** | Conflict Resolution (voting) | 5d | Agent coordination |
| **P1** | Agent Deployment CI | 4d | Ops efficiency |
| **P1** | Handoff Protocol | 3d | Agent communication |
| **P1** | Troubleshooting Playbook | 3d | Ops support |
| **P1** | Agent Quickstart | 2d | Developer velocity |
| **P1** | Multi-GPU RDNA4 Guide | 1d | B850 enablement |
| **P2** | Self-Healing Fleet | 10d | Reliability |
| **P2** | Fleet Operations Manual | 5d | Ops knowledge |

**Total P0 Effort:** ~15 days
**Total P1 Effort:** ~18 days
**Total P2 Effort:** ~15 days

---

## Execution Notes

1. **Claim lanes via AGNOTE4482PHI.t1** before starting P0 items
2. **Village Rule applies** - no agent operates alone in production validation
3. **CHIT sign all delivery** - use `make -C pmoves sign-trail` on completion
4. **Test before PR** - run `/test:pr` and document results

---

## Related Research

- **B850 RDNA4 ML Compatibility:** Separate research completed 2026-07-11
- **HERMES Integration:** Completed 2026-06-04 (see HERMES_AGENT_INTEGRATION.md)
- **CHIT Hardening Sprint:** Completed 2026-05-16 (66-file audit, 3 services signed)
