---
description: Monitor CI/CD status of v3-clean → Hardened migration PRs
---

# PR Monitor for v3-clean Migration

## What It Does

Monitors the CI/CD status, mergeability, and review status of all targeted PRs created for the v3-clean → Hardened migration.

## Usage

```bash
# Run PR monitoring
.claude/scripts/pr-monitor.sh
```

## Output

The script displays:
- **Summary table**: PR #, title, mergeable status, CI checks, review status
- **Detailed status**: URL, mergeable state, check results for each PR
- **Next steps**: Commands for approving and merging PRs

## PRs Monitored

| PR | Service | Files |
|----|---------|-------|
| #528 | Hi-RAG v2 | 2 |
| #529 | Flute Gateway | 1 |
| #530 | Presign | 1 |
| #531 | Publisher Discord | 1 |
| #532 | Session Context Worker | 1 |
| #533 | Agent Zero | 1 |
| #534 | Gateway Agent | 2 |

## Status Icons

- ✅ = PASS / MERGEABLE / APPROVED
- ❌ = FAIL / CONFLICTING / CHANGES REQUESTED
- ⏳ = PENDING
- 👀 = REVIEW REQUIRED
- 🔄 = CHANGES REQUESTED
