# PMOVES.AI PR Review Tracking

This directory tracks PR review learnings and comment catalogs for merge validation.

## Monitoring Tools

### NATS Monitor Agent
**Location:** `PMOVES-BoTZ/features/n8n/monitor_agent.py`

**Capabilities:**
- Subscribes to `claude.code.tool.executed.v1` - Tool execution tracking
- Subscribes to `n8n.workflow.executed.v1` - Workflow results
- Subscribes to `code.review.completed.v1` - Review outcomes
- Uses TensorZero for pattern analysis and learning extraction
- Stores learnings in memory with JSON export capability

**Usage:**
```bash
cd PMOVES-BoTZ/features/n8n
python3 monitor_agent.py
```

### GitHub PR Review Skill
**Skill:** `/github:pr-review`

**Usage:**
```
/github:pr-review <pr-number>
```

**Features:**
- Comprehensive PR review using specialized agents
- Categorizes comments by severity
- Tracks review status

## Active PRs

| PR # | Title | Target Branch | Status | Review Date |
|------|-------|---------------|--------|-------------|
| 519 | chore: Complete hardened architecture merge to v3-clean | PMOVES.AI-Edition-Hardened-v3-clean | In Review | 2026-01-22 |

## Review Catalog Template

```markdown
# PR #XXX Review Catalog

## Summary
- **PR Number:** XXX
- **Title:** ...
- **Total Comments:** XX
- **Blocking Issues:** XX
- **Suggestions:** XX
- **Questions:** XX

## Blocking Issues (Must Fix)
| File | Line | Issue | Status | Assigned To |
|------|------|-------|--------|-------------|
| path/to/file.py | 42 | Missing docstring | Open | @user |

## Suggestions (Should Fix)
| File | Line | Suggestion | Status |
|------|------|-------------|--------|

## Questions (Needs Response)
| Comment | Response | Status |

## CI/CD Status
- [ ] CodeQL Analysis
- [ ] CHIT Contract Check
- [ ] SQL Policy Lint
- [ ] CodeRabbit Review

## Learnings
*Add key learnings from this review cycle*
```

## Merge Strategy

**Reverse Merge Approach:**
1. Merge `feat/personas-first-architecture-hardened` → `PMOVES.AI-Edition-Hardened-v3-clean`
2. Validate in v3-clean environment
3. Merge `PMOVES.AI-Edition-Hardened-v3-clean` → `PMOVES.AI-Edition-Hardened` (production)
