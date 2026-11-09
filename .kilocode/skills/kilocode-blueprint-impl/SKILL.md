---
name: kilocode-blueprint-impl
description: Blueprint-first feature implementation for PMOVES.AI using GLM-5.2 coding plan. Use when implementing features from field briefs, architecture specs, or design documents with a structured blueprint approach.
keywords: [blueprint, implementation, feature, glm, coding-plan, vs-code]
version: 1.0.0
category: PMOVES/KiloCode-GLM
---

# KiloCode Blueprint Implementation

Blueprint-first feature implementation using GLM-5.2 via Z.AI coding plan on the 5090 GPU node.

## Purpose

Pick up field briefs (from Claude Code analysis or Codex generation) and execute them with
GLM-5.2's blueprint-first mode. Read the spec, implement the code, validate, and commit.

## Capabilities

- 📐 Parse field briefs and design documents into implementation steps
- 🔨 Generate code following PMOVES patterns (FastAPI, NATS, TensorZero routing)
- ✅ Validate with `make -C pmoves smoke` and targeted tests
- 📝 Commit with conventional commits format
- 🎯 Focus on single-task atomic implementation

## Integration Points

- **Model**: GLM-5.2 via Z.AI coding plan (`zai/glm-5.2`)
- **Fallback**: GLM-5-Turbo (`zai/glm-5-turbo`)
- **TensorZero Function**: `coding_kilocode` (weight 0.7 primary)
- **NATS Subject**: `kilocode.agent.status.v1`
- **Mode**: `pmoves-glm`

## Workflow

### Step 1: Parse the Brief

Read the field brief or design document. Extract:
- Target files and their current state
- Required changes (atomic units)
- Acceptance criteria
- Testing requirements

### Step 2: Implement

```bash
# Work in the claimed branch
git branch --show-current

# Implement changes following PMOVES patterns:
# - Python 3.11+, type hints, 4-space indent
# - FastAPI routes: snake_case functions, kebab-case URLs
# - All services expose /healthz and /metrics
# - LLM calls route through TensorZero at localhost:3030
# - Event publishing via NATS at nats://nats:pmoves@nats:4222
```

### Step 3: Validate

```bash
# Run relevant smoke tests
make -C pmoves smoke

# Run targeted tests
pytest -q pmoves/tests/<relevant_path>/

# GPU validation if touching reranker/embedding code
GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu
```

### Step 4: Commit and Release

```bash
# Conventional commits
git add <files>
git commit -m "feat(scope): description"

# Sign trail
make -C pmoves sign-trail SUMMARY="<summary>" AGENT="kilocode" PHASE="implementation"
```

## Trigger Phrases

- "implement this brief"
- "blueprint execution"
- "code this feature"
- "pick up the field brief"
