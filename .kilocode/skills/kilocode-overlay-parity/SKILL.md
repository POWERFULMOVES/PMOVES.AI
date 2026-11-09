---
name: kilocode-overlay-parity
description: Ensure PMOVES overlays align with upstream submodule capabilities on the KiloCode GLM lane. Use when auditing git submodule alignment, checking overlay compatibility, or validating integration contracts.
keywords: [overlay, parity, submodule, upstream, gitmodules, integration, kilocode, glm]
version: 1.0.0
category: PMOVES/KiloCode
---

# KiloCode Overlay Parity

Audit PMOVES git submodule overlays against upstream capabilities and generate parity reports with KiloCode GLM analysis.

## Purpose

Ensure PMOVES overlay branches stay aligned with upstream submodule commits and capabilities. Generate parity audits and missing mapping reports. Route complex parity issues through TensorZero `coding_glm` / `coding_kilocode` for analysis.

## Capabilities

- 📊 Parse `.gitmodules` for submodule configuration
- 🔍 Compare overlay branches against upstream
- ⚖️ Validate integration contracts between submodules
- 📋 Generate missing mapping reports
- 🤖 Route complex parity issues to GLM-5-Turbo for analysis

## Integration Points

- **Gitmodules**: `.gitmodules` at repo root
- **Overlay Docs**: `.claude/context/submodules.md`
- **Submodule Workflow**: `.claude/context/submodule-workflow.md`
- **Codex Homes**: `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/README.md`
- **TensorZero Functions**: `coding_glm`, `coding_kilocode`
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
4. Routes analysis through TensorZero coding_glm
5. Generates parity report
6. Identifies missing MCP schema mappings
```

## Trigger Phrases

- "overlay parity audit"
- "check overlay alignment"
- "validate submodule contracts"
- "sync upstream changes"
- "gitlink update"
- "kilocode overlay parity"
