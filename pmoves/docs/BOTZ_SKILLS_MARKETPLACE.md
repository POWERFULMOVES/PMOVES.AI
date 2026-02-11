# BoTZ Skills Marketplace Documentation

**Date:** 2026-02-11
**Component:** PMOVES-BoTZ (Bot Skills Framework)
**Purpose:** Complete catalog and integration guide for Claude Code skills marketplace

---

## Overview

The **BoTZ Skills Marketplace** is a comprehensive collection of reusable Claude Code skills organized under `PMOVES-BoTZ/features/skills/repos/`. Each skill provides specialized capabilities that can be invoked by Claude Code CLI.

### Location

```
PMOVES-BoTZ/
└── features/skills/repos/
    ├── skillcreator-skills/       # Core engineering skills
    ├── skills-marketplace/        # Main marketplace catalog
    ├── anthropics-skills/        # Anthropic-specific skills
    ├── awesome-claude-skills/   # Community skills
    ├── aws-skills/               # AWS-related skills
    ├── d3js-skill/               # D3.js visualizations
    ├── epub-skill/                # EPUB document handling
    ├── huggingface-skills/       # Hugging Face integration
    ├── obsidian-plugin-skill/    # Obsidian development
    └── playwright-skill/          # Browser automation
```

---

## Skill Repositories

### 1. skillcreator-skills (Engineering Workflow)

**Location:** `PMOVES-BoTZ/features/skills/repos/skillcreator-skills/`

**Purpose:** Core engineering workflow skills for feature development, code review, and testing

**Skills Included:**

| Skill | Purpose | Activation |
|-------|---------|------------|
| `feature-planning` | Break down features into implementable plans | "plan this feature", "break down the requirements" |
| `review-implementing` | Implement code review feedback systematically | "implement review feedback", "address PR comments" |
| `test-fixing` | Fix failing tests with smart error grouping | "fix the tests", "tests are failing" |
| `git-pushing` | Stage, commit, push with conventional commits | "commit these changes", "push to GitHub" |
| `code-auditor` | Comprehensive codebase analysis | "audit the code", "review codebase" |
| `code-refactoring` | Code refactoring patterns | "refactor this code", "improve code quality" |
| `code-documentation` | Effective code documentation | "document this code", "add API docs" |
| `project-bootstrapper` | Project setup with best practices | "set up this project", "initialize project" |
| `conversation-analyzer` | Analyze Claude conversation patterns | "analyze my conversations" |
| `plan-implementer` | Agent for implementing from detailed plans | (auto-invoked) |
| `skill-creator` | Guide for creating new skills | "create a skill", "build a Claude skill" |

**Agent:** `plan-implementer` - Cost-effective implementation agent (Haiku model)

### 2. skills-marketplace (Main Catalog)

**Location:** `PMOVES-BoTZ/features/skills/repos/skills-marketplace/`

**Purpose:** Central marketplace for all skills with plugin.json metadata

**Structure:**
- `.claude-plugin/marketplace.json` - Plugin registry
- Individual plugins under `*-plugin/` directories

**Key Plugins:**
- `engineering-workflow-skills` - Feature planning, test fixing, git operations
- `visual-documentation-skills` - HTML documentation generation
- `productivity-skills` - Code auditing, project bootstrapping

### 3. anthropics-skills

**Location:** `PMOVES-BoTZ/features/skills/repos/anthropics-skills/`

**Purpose:** Anthropic-specific Claude capabilities

### 4. aws-skills

**Location:** `PMOVES-BoTZ/features/skills/repos/aws-skills/`

**Purpose:** AWS development skills

**Skills:**
- `aws-cdk-development` - Cloud Development Kit expertise
- `aws-serverless-eda` - Serverless event-driven architecture
- `aws-agentic-ai` - AWS Bedrock AgentCore
- `aws-cost-operations` - Cost optimization

### 5. huggingface-skills

**Location:** `PMOVES-BoTZ/features/skills/repos/huggingface-skills/`

**Purpose:** Hugging Face platform integration

**Skills:**
| Skill | Purpose |
|-------|---------|
| `hf-tool-builder` | Build tools/scripts with marketplace API |
| `hf-paper-publisher` | Publish research papers to Hugging Face |
| `hf-evaluation-manager` | Manage model evaluation results |
| `hf-dataset-creator` | Create and manage datasets |
| `hf-model-trainer` | Train and fine-tune models |

### 6. playwright-skill

**Location:** `PMOVES-BoTZ/features/skills/repos/playwright-skill/`

**Purpose:** Complete browser automation with Playwright
- Auto-detects dev servers
- Writes and debugs Playwright tests
- Handles complex web interactions

### 7. Other Skills Repositories

| Repo | Purpose |
|------|---------|
| `d3js-skill` | Interactive data visualizations with D3.js |
| `epub-skill` | EPUB document creation and conversion |
| `obsidian-plugin-skill` | Obsidian.md plugin development |
| `awesome-claude-skills` | Community-curated skill collection |

---

## Skill Structure

Every skill follows this pattern:

```
skill-name/
├── SKILL.md              # Required: Skill specification
├── references/            # Optional: Reference materials
│   ├── best-practices.md
│   ├── examples.md
│   └── patterns.md
└── scripts/              # Optional: Helper scripts
    └── *.py
```

**SKILL.md Required Sections:**
1. Purpose - What the skill does
2. When to Use - Activation scenarios
3. What It Does - Workflow explanation
4. Approach - Tool usage patterns
5. Example Interaction - Realistic example
6. Tools Used - Which tools and why
7. Success Criteria - How to know when done

---

## Integration with PMOVES.AI

### BoTZ Gateway

**Port:** 8054
**Purpose:** Serves skills marketplace to Claude Code CLI via MCP

### Context Loading

**Tier 4** - Explicit load only (per AGENT_CONTEXT_PATTERNS.md):
- Individual skill contexts are NEVER auto-loaded
- Skills loaded only when explicitly invoked
- Prevents circular context loading

### Agent Coordination

Skills communicate via:
1. **MCP API** - Direct tool invocation through BoTZ gateway
2. **NATS Events** - Async coordination for long-running tasks
3. **Agent Zero** - Orchestration for multi-agent workflows

---

## Development Workflow

### Creating a New Skill

1. **Use skill-creator skill** - Don't create manually
2. **Follow structure** - SKILL.md, references/, scripts/
3. **Test thoroughly** - Natural activation, edge cases
4. **Add to marketplace** - Update marketplace.json
5. **Document** - Update README.md

### Skill Activation Patterns

**Good (natural activation):**
- "audit the code" → code-auditor
- "fix the tests" → test-fixing
- "plan this feature" → feature-planning

**Bad (manual invocation):**
- "/audit" - Too manual
- "run code-auditor" - Not natural

---

## Quick Reference

### Core Engineering Skills
```
feature-planning      → Break down features
test-fixing          → Fix failing tests
git-pushing          → Git operations
review-implementing   → PR feedback
code-auditor         → Codebase analysis
project-bootstrapper  → Project setup
```

### Specialized Skills
```
hf-tool-builder       → Hugging Face tools
aws-cdk-development  → AWS infrastructure
playwright-skill      → Browser automation
d3js-skill           → Data visualization
```

---

## Documentation

**Skill Development Guide:** `PMOVES-BoTZ/features/skills/repos/skills-marketplace/CLAUDE.md`

**Agent Context Patterns:** `pmoves/docs/AGENT_CONTEXT_PATTERNS.md`

**BoTZ Integration:** `pmoves/docs/BOTZ_SKILLS_INTEGRATION.md`

---

## Summary

The BoTZ Skills Marketplace provides 50+ specialized skills across:
- **Engineering workflow** - Planning, testing, git, code review
- **Cloud platforms** - AWS, Hugging Face
- **Specialization** - Browser automation, visualization, documentation
- **Productivity** - Project setup, code auditing

**Key Integration Point:** Use via BoTZ Gateway (port 8054) with MCP API for skill invocation.

**Context Loading:** Tier 4 (explicit only) - never auto-load individual skill contexts to prevent circular loading.

---

*See AGENT_CONTEXT_PATTERNS.md for universal context loading strategy across all PMOVES.AI agents.*
