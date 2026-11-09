---
name: kilocode-submodule-parity
description: Ensure KiloCode configuration parity with Claude Code and Codex across PMOVES.AI submodules. Use when auditing config consistency, checking claw scope alignment, or verifying that all three 5090 agents have equivalent capabilities.
keywords: [parity, submodule, audit, claude, codex, config]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode Submodule Parity

Configuration parity auditing between KiloCode GLM, Claude Code, and Codex on the 5090 node.

## Purpose

Ensure KiloCode has equivalent MCP servers, permissions, model access, and operational
capabilities as Claude Code and Codex. Identify gaps and generate remediation tasks.

## Capabilities

- 🔍 Audit MCP server parity across `kilo.json` vs `.claude/mcp.json`
- 🛡️ Compare permission models (allow/deny lists, tool restrictions)
- 📋 Check agent registry and signature completeness
- 🔄 Verify mode coverage (`.kilocodemodes` vs `.claude/commands/`)
- 📊 Generate parity gap report with prioritized remediation

## Integration Points

- **KiloCode Config**: `kilo.json`
- **Claude Code Config**: `.claude/mcp.json`, `.claude/settings.json`
- **Agent Registry**: `pmoves/config/agent_registry.yaml`
- **Agent Signatures**: `pmoves/config/agent_signatures.yaml`
- **Node Scope**: `pmoves/configs/claws/scopes/5090.json`
- **KiloCode Node Config**: `pmoves/configs/claws/opencode-5090.json`

## Workflow

### Step 1: MCP Server Parity

```bash
# Claude Code MCP servers
cat .claude/mcp.json | jq '.mcpServers | keys'

# KiloCode MCP servers
cat kilo.json | jq '.mcp | keys'

# Diff
# Missing from KiloCode: any server in Claude but not in kilo.json
```

### Step 2: Permission Parity

```bash
# Claude deny list
cat .claude/settings.json | jq '.permissions.deny'

# KiloCode should have equivalent guardrails
cat kilo.json | jq '.permission'
```

### Step 3: Model Parity

```bash
# Check that primary model in kilo.json matches agent_signatures.yaml
grep -A5 "kilocode-glm" pmoves/config/agent_signatures.yaml | grep model
grep '"model"' kilo.json
```

### Step 4: Mode Coverage

```bash
# Count modes
grep "slug:" .kilocodemodes | wc -l

# Verify mode references match kilo.json instructions
grep ".kilocodemodes" kilo.json
```

### Step 5: Generate Report

Create a parity gap report with:
- MCP servers missing from KiloCode
- Permission gaps (deny list missing)
- Model configuration mismatches
- Stale documentation references
- Prioritized remediation tasks

## Trigger Phrases

- "parity check"
- "config audit"
- "compare configs"
- "what's missing from kilocode"
- "claude vs kilocode"
