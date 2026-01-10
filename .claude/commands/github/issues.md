# GitHub Issues

List and triage GitHub issues for the PMOVES.AI repository.

## Usage

```
/github:issues [filter]
```

## Arguments

- `filter` (optional): Filter type - `open`, `closed`, `bugs`, `features`, `security`, or label name

## What This Command Does

1. **List Open Issues:**
   ```bash
   gh issue list --state open --limit 20
   ```

2. **Filter by Label:**
   ```bash
   gh issue list --label "bug" --state open
   gh issue list --label "enhancement" --state open
   gh issue list --label "security" --state open
   ```

3. **Get Issue Details:**
   ```bash
   gh issue view <issue_number> --json title,body,labels,assignees,comments
   ```

4. **Check Linked PRs:**
   ```bash
   gh issue view <issue_number> --json linkedBranches
   ```

## Issue Triage Guidelines

### Priority Labels

| Priority | Criteria | Response Time |
|----------|----------|---------------|
| P0 - Critical | Production down, security breach, data loss | Immediate |
| P1 - High | Major feature broken, security vulnerability | < 24h |
| P2 - Medium | Feature degraded, non-critical bug | < 1 week |
| P3 - Low | Minor issue, cosmetic, nice-to-have | Backlog |

### Service Area Labels

Based on PMOVES architecture:

- `area/agent-zero` - Agent orchestration
- `area/hi-rag` - Knowledge retrieval
- `area/tensorzero` - LLM gateway
- `area/nats` - Event bus
- `area/media` - PMOVES.YT, Whisper, analyzers
- `area/infra` - Docker, CI/CD, monitoring
- `area/tac` - Claude Code CLI integration

### Type Labels

- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `documentation` - Documentation updates
- `security` - Security-related issue
- `performance` - Performance improvement
- `tech-debt` - Code cleanup, refactoring

## Output Format

```markdown
## Open Issues Summary

### By Priority
- **P0 Critical:** X issues
- **P1 High:** Y issues
- **P2 Medium:** Z issues
- **P3 Low/Unclassified:** N issues

### Recent Issues (Last 7 Days)
| # | Title | Labels | Assignee | Age |
|---|-------|--------|----------|-----|
| ... | ... | ... | ... | ... |

### Needs Triage
<Issues without priority label>

### Stale Issues (> 30 days)
<List of stale issues>
```

## Example

```bash
# List all open issues
/github:issues

# Filter bugs only
/github:issues bugs

# Filter by custom label
/github:issues area/agent-zero

# Show security issues
/github:issues security
```

## Actions

After listing issues, common actions:

```bash
# Assign issue
gh issue edit <number> --add-assignee @me

# Add labels
gh issue edit <number> --add-label "P1,bug,area/hi-rag"

# Close issue
gh issue close <number> --comment "Fixed in PR #XXX"

# Create linked branch
gh issue develop <number> --checkout
```

## Notes

- Requires `gh` CLI authenticated with repo access
- Issues are sorted by creation date (newest first)
- Dependabot alerts appear separately in `/security/dependabot`
