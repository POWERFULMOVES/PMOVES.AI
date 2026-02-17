# Agent Resilience Patterns

_Last updated: 2026-02-16_

Canonical patterns for ensuring PMOVES agents can survive context limits, recover from failures, and resume interrupted work. Born from Phase C hardening (2026-02-16) where 7 background agents hit context walls before completing PR workflows.

## Problem Statement

Background agents launched via Claude Code's `Task` tool operate within a fixed token budget. When the budget runs out:

- Work-in-progress is lost if not committed
- PRs cannot be created
- No structured report reaches the orchestrator
- Resumption requires manual context reconstruction

## Three-Layer Resilience Model

```
┌──────────────────────────────────────┐
│  Layer 3: Systemic (Taxonomy)        │  Agent registry encodes resilience
│  - Context budget class              │  attributes per agent definition.
│  - Checkpoint frequency              │
│  - Recovery strategy                 │
├──────────────────────────────────────┤
│  Layer 2: Recovery (Cipher Memory)   │  Structured snapshots in Cipher
│  - agent_plan                        │  enable resumption by new agent
│  - agent_checkpoint                  │  instances or human operators.
│  - agent_completion                  │
├──────────────────────────────────────┤
│  Layer 1: Preventive (Discipline)    │  Commit-early, push-often, keep
│  - Pre-flight snapshot               │  responses compact, prioritize
│  - Checkpoint after each step        │  irreversible actions first.
│  - Budget-aware work ordering        │
└──────────────────────────────────────┘
```

---

## Layer 1: Preventive Discipline

### Pre-flight Snapshot

Before starting work, agents store their plan so that recovery is possible even if the agent hits a wall on the first step.

**Rule:** First action is always `git checkout -b <branch>` + Cipher snapshot.

```
# Agent's first step (pseudocode):
1. Create/checkout working branch
2. POST to Cipher Memory:
   {
     "content": "<plan summary>",
     "category": "agent_plan",
     "tags": ["<phase>", "<submodule>", "<task-type>"]
   }
3. Begin actual work
```

### Commit-Early, Push-Often

Agents should commit and push after every discrete, self-contained change. This ensures that even if the agent is interrupted:

- All completed work is preserved on the remote
- Another agent (or human) can pick up from the last commit
- The branch state is always valid (no half-applied changes)

**Rule:** Never accumulate more than 3 file changes before committing.

### Budget-Aware Work Ordering

Structure work so that the highest-value, most-irreversible steps happen first:

1. **Code changes** — the actual fixes (commit after each file group)
2. **Push to remote** — preserve work externally
3. **PR creation** — the deliverable
4. **Documentation updates** — nice-to-have, can be added later

**Rule:** If you've completed code changes but haven't pushed, push before starting new work.

### Compact Responses

Agents should minimize output verbosity:

- Don't echo full file contents when a summary suffices
- Don't repeat the plan in every response
- Use `--stat` instead of full `git diff` for progress checks
- Avoid reading files you won't modify

---

## Layer 2: Cipher Memory Integration

### Memory Categories for Resilience

| Category | Purpose | When to Write | TTL |
|----------|---------|---------------|-----|
| `agent_plan` | Pre-flight plan for resumable work | Before first code change | 7 days |
| `agent_checkpoint` | Mid-work progress snapshot | After each commit+push | 3 days |
| `agent_completion` | Final summary of all changes | After PR creation | 30 days |

### Cipher Memory API

**Store a plan:**
```bash
curl -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Plan: fix NATS auth in Agent Zero. Scope: 3 Dockerfiles (USER directive) + 3 pmoves libs (NATS URL). Branch: fix/phase-c-hardening",
    "category": "agent_plan",
    "tags": ["phase-c", "agent-zero", "security", "nats-auth"]
  }'
```

**Store a checkpoint:**
```bash
curl -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Checkpoint: Agent Zero phase-c. DONE: 3 pmoves lib NATS fixes (committed abc1234). REMAINING: 3 Dockerfile USER directives. BLOCKER: none.",
    "category": "agent_checkpoint",
    "tags": ["phase-c", "agent-zero"]
  }'
```

**Store completion summary:**
```bash
curl -X POST http://localhost:8096/api/memory \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Complete: Agent Zero phase-c hardening. PR #6 created. Changes: NATS auth in 3 pmoves libs + USER directive in 3 Dockerfiles. Branch: fix/phase-c-hardening.",
    "category": "agent_completion",
    "tags": ["phase-c", "agent-zero", "pr-6"]
  }'
```

**Search for recovery context:**
```bash
curl "http://localhost:8096/api/memory/search?q=phase-c+agent-zero&category=agent_checkpoint"
```

### Checkpoint Content Format

Checkpoints follow a structured format for machine-parseable recovery:

```
Checkpoint: <agent-name> <task-name>
DONE: <completed items with commit hashes>
REMAINING: <items not yet started>
BLOCKER: <any blockers, or "none">
BRANCH: <branch name>
REPO: <repo name>
```

---

## Layer 3: Systemic (Agent Registry)

### Resilience Attributes in Registry

Every agent in `pmoves/config/agent_registry.yaml` declares resilience attributes:

```yaml
resilience:
  context_budget: small | medium | large
  checkpoint_frequency: per_file | per_wave | per_submodule
  recovery_strategy: cipher_resumable | idempotent_replay | manual_handoff
  cipher_categories: [agent_plan, agent_checkpoint]
```

### Attribute Definitions

**Context Budget Class:**

| Class | Token Budget | Use Case |
|-------|-------------|----------|
| `small` | ~25K tokens | Single-file fixes, simple queries |
| `medium` | ~50K tokens | Multi-file changes within one repo |
| `large` | ~100K+ tokens | Cross-repo orchestration, complex refactors |

**Checkpoint Frequency:**

| Frequency | Trigger | Best For |
|-----------|---------|----------|
| `per_file` | After each file modification | Fine-grained recovery, small budgets |
| `per_wave` | After each logical group of changes | Medium tasks, balanced overhead |
| `per_submodule` | After completing one submodule | Multi-repo sweeps |

**Recovery Strategy:**

| Strategy | How It Works | When to Use |
|----------|-------------|-------------|
| `cipher_resumable` | Cipher Memory holds full plan + checkpoints; new agent reads and continues | Default for all agents |
| `idempotent_replay` | Work is idempotent; just re-run the same plan from scratch | Config changes, env file updates |
| `manual_handoff` | Agent produces structured handoff doc; human completes | Complex decisions, merge conflicts |

### Failure Modes

| Mode | Description | Recovery Path |
|------|-------------|---------------|
| **Graceful** | Agent detects budget pressure, commits, pushes, writes Cipher snapshot, stops | New agent reads checkpoint, continues |
| **Hard** | Context wall hit mid-operation; no final snapshot | Check git log on branch for last commit; reconstruct from there |
| **Blocked** | External dependency (API down, permissions, merge conflict) | Agent writes blocker to Cipher; human resolves, re-launches |

---

## Practical Patterns

### Pattern 1: Multi-Submodule Security Sweep

Used in Phase C hardening (2026-02-16) where 8 submodules needed parallel fixes.

```
Orchestrator:
  1. Read audit findings
  2. For each submodule:
     a. Store plan in Cipher (agent_plan)
     b. Launch background agent with:
        - Specific submodule path
        - Branch name convention (fix/phase-c-hardening)
        - List of files to modify
        - Commit message template
     c. Agent works: checkout → fix → commit → push → checkpoint
  3. Orchestrator creates PRs from pushed branches
  4. Store completion summary in Cipher
```

**Lesson learned:** Keep PR creation in the orchestrator, not in background agents. PR creation is low-token-cost but requires all branches to be ready.

### Pattern 2: Resumable Agent

When an agent hits a wall or fails:

```
Recovery Agent:
  1. Search Cipher: GET /api/memory/search?q=<task>&category=agent_checkpoint
  2. Read last checkpoint → extract DONE/REMAINING/BRANCH
  3. git checkout <branch>
  4. git log --oneline -5 → verify last commit matches checkpoint
  5. Continue from REMAINING list
  6. Write new checkpoint after each step
```

### Pattern 3: Orchestrator Health Check

After launching background agents, the orchestrator checks:

```
For each agent:
  1. Check if agent process is still running
  2. If finished: read output, verify success
  3. If still running: check Cipher for latest checkpoint
  4. If no checkpoint after N minutes: assume stalled, log warning
```

---

## Integration with Agent Taxonomy

This document is part of the PMOVES Agent Class Taxonomy system:

- **Registry:** `pmoves/config/agent_registry.yaml` — `resilience` field per agent
- **Taxonomy:** `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` — Section 10
- **Cross-Reference:** `pmoves/docs/AGENTS/AGENT_TAXONOMY_CROSS_REFERENCE.md` — Entry #17

---

## Related Documents

- [Agent Class Taxonomy](./PMOVES_AGENT_CLASS_TAXONOMY.md)
- [Taxonomy Cross-Reference](./AGENT_TAXONOMY_CROSS_REFERENCE.md)
- [Cipher Memory Service](../../.claude/context/services-catalog.md) (port 8096)
- [Phase C Audit Summary](../hardening/PMOVES-hardening-tracker.md)
