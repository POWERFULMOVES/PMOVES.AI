---
name: minimax-submodule-parity
description: Ensure PMOVES overlays align with upstream submodule capabilities. This skill should be used when auditing submodule alignment, checking overlay compatibility, or validating integration contracts.
keywords: [submodule, parity, overlay, upstream, gitmodules, integration]
version: 1.0.0
category: PMOVES/MiniMax
---

# MiniMax Submodule Parity

Audit PMOVES submodule overlays against upstream capabilities and generate parity reports.

## Purpose

Ensure PMOVES overlay branches stay aligned with upstream submodule commits and capabilities. Generate parity audits and missing mapping reports.

## Capabilities

- 📊 Parse `.gitmodules` for submodule configuration
- 🔍 Compare overlay branches against upstream
- ⚖️ Validate integration contracts between submodules
- 📋 Generate missing mapping reports
- 🤖 Route complex parity issues to MiniMax for analysis

## Integration Points

- **Gitmodules**: `.gitmodules` at repo root
- **Overlay Docs**: `.claude/context/submodules.md`
- **Submodule Workflow**: `.claude/context/submodule-workflow.md`
- **Codex Homes**: `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/README.md`
- **NATS Subject**: `pmoves.submodule.parity.v1`

## Workflow

### 1. Audit Submodule Configuration

```bash
# List all submodules
git submodule status

# Check overlay branch
git -C <submodule-path> branch --show-current

# Compare against upstream
git -C <submodule-path> fetch upstream
git -C <submodule-path> log --oneline upstream/main..HEAD
```

### 2. Validate Integration Contracts

Check that submodule interfaces match PMOVES expectations:

```bash
# Run contract validation
make chit-contract-check
```

### 3. Generate Parity Report

```bash
# Generate audit
./scripts/submodule-parity-audit.py --output parity_report.md
```

## Parity Matrix

| Submodule | Overlay Branch | Upstream | Status | Gap |
|-----------|---------------|----------|--------|-----|
| PMOVES-HiRAG | pmoves/latest | upstream/main | ✅ OK | - |
| PMOVES-TensorZero | pmoves/v2 | upstream/develop | ⚠️ 3 commits behind | MCP schema |

## Constraints

- ✅ Work in submodule, land commit, update PMOVES.AI gitlink
- ✅ Update Claude-facing AND Codex-facing docs in same PR
- ✅ Never commit directly to submodule overlays

## Example Usage

```
User: "Run submodule parity audit for HiRAG"

Agent:
1. Reads .gitmodules
2. Checks PMOVES-HiRAG overlay vs upstream
3. Validates integration contracts
4. Generates parity report
5. Identifies missing MCP schema mappings
```

## Trigger Phrases

- "submodule parity audit"
- "check overlay alignment"
- "validate submodule contracts"
- "sync upstream changes"
- "gitlink update"
