# KiloCode Rules for PMOVES.AI

## Context Sources

Use the `.claude` folder as primary reference:
- `.claude/README.md` — context loading guide
- `.claude/CLAUDE.md` — full architecture overview, service catalog, development patterns
- `.claude/context/` — detailed documentation (services, NATS subjects, MCP API, testing)
- `.claude/commands/` — skill definitions for CLI operations

## Agent Taxonomy

PMOVES.AI uses a structured agent classification system:
- **Registry:** `pmoves/config/agent_registry.yaml` — canonical definitions for all 46 agents
- **Taxonomy:** `pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md` — 4 classes, 7 types, evolution paths
- **Signatures:** `pmoves/config/agent_signatures.yaml` — agent identity and capability signatures

## Mode-Type Mapping

KiloCode modes map to PMOVES service tiers and agent types. See `.kilocodemodes` at repo root for the 8 configured modes:

| Mode | Agent Types | Service Tiers |
|------|------------|---------------|
| `pmoves-code` | Worker + LLM | 3-4 |
| `pmoves-architect` | Agent + LLM | 6 + 3 |
| `pmoves-ask` | API + Data | 1-2 |
| `pmoves-debug` | Worker + Data | 4 + 1 |
| `pmoves-review` | Agent | 6 |
| `pmoves-frontend` | UI | 7 |
| `pmoves-portal` | Agent + Geometry | 6 + L2.5 |
| `pmoves-crush` | UI + Agent | 7 + 6 |

## Integration Plan

Full integration architecture: `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`
