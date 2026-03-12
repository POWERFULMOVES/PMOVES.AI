# Codex Ecosystem Traversal (PMOVES)
_Last updated: 2026-03-12_

This document defines how Codex should traverse the PMOVES.AI ecosystem in
final-stage production. It is the shortest path from "open the repo" to
"choose the right PMOVES service, submodule, memory surface, persona lane, and
validation command."

## Identity

Codex is a PMOVES external contributor and should be treated as a
legendary traversal/operator persona for implementation lanes, even though the
runtime taxonomy reserves the `legendary` class for the `POWERFULMOVES` brand
umbrella.

Canonical sources:
- `pmoves/config/agent_registry.yaml` -> `external_contributors`
- `pmoves/config/agent_signatures.yaml` -> `codex`
- `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
- `pmoves/docs/AGENTS/CODEX_RUNTIME_PROTOCOL.md`

Codex signature:
- `display_name`: `Codex`
- `glyph`: `■`
- `color`: `#2563EB`
- `voice`: `terse`
- `resonance`: `rapid-prototyping`, `code-gen`, `integration`, `cipher-memory`

## Bootstrap

Use this sequence before meaningful work:

1. `make -C pmoves codex-config`
2. `codex --profile pmoves`
3. `make -C pmoves codex-health-quick`
4. `make -C pmoves codex-audit`
5. `make -C pmoves codex-parity-check`

For overlap with Claude or other agent lanes, also load:
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md`
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md`

## Traversal Order

When requirements are unclear, traverse in this order:

1. `Operator lane` — `CODEX_OPERATOR_HOME.md`, `CODEX_RUNTIME_PROTOCOL.md`
2. `Service map` — `.claude/CLAUDE.md`, `.claude/context/services-catalog.md`
3. `Submodule map` — `.claude/context/submodules.md`, `.claude/context/submodule-workflow.md`
4. `Skill map` — `pmoves/docs/AGENTS/PmovesSKillZ.md`, `pmoves/configs/skill-pairings.yaml`
5. `Submodule skill routing` — `pmoves/configs/submodule_skill_registry.json`
6. `Persona + voice` — `pmoves/docs/AGENTS/PERSONAS.md`, `.claude/context/voice-personas.md`
7. `Memory + continuity` — `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`

## Core PMOVES Surfaces

| Need | Primary PMOVES surface | Secondary surface |
| --- | --- | --- |
| Task orchestration | `PMOVES-Agent-Zero` | `PMOVES-Archon` |
| Knowledge retrieval | `PMOVES-HiRAG` | `PMOVES-Deep-Serch` |
| Tool and MCP access | `PMOVES-BoTZ` | `PMOVES-BotZ-gateway` |
| Persistent memory | `Pmoves-cipher` | `Supabase` |
| Persona selection | `PERSONAS.md` + persona seeds | `Agent Zero` / `Archon` |
| Voice and narration | `Flute-Gateway` | `PMOVES-Ultimate-TTS-Studio`, `PMOVES-Pipecat` |
| Workflow automation | `PMOVES-n8n` | `PMOVES-BoTZ` |
| Media ingest | `PMOVES.YT` | `PMOVES-transcribe-and-fetch` |
| Media publish/playback | `PMOVES-Jellyfin` | `Pmoves-Jellyfin-AI-Media-Stack` |
| Geometry/CHIT routing | `PMOVES-ToKenism-Multi` | `Pmoves-hyperdimensions`, `EvoSwarm` |
| Model routing | `PMOVES-tensorzero` | Supabase model registry |
| UI traversal | `pmoves/ui`, `PMOVES-MAI-UI`, `PMOVES-A2UI` | `PMOVES-crush` |

## Skills, Memory, Personas, Voice

### Skills

Primary sources:
- `pmoves/docs/AGENTS/PmovesSKillZ.md`
- `pmoves/configs/skill-pairings.yaml`
- `pmoves/configs/submodule_skill_registry.json`

Codex should prefer PMOVES-native pairings before inventing ad hoc chains:
- `ingest-chit-index`
- `research-summarize-render`
- `voice-synthesis`
- `agent-card-gen`
- `pr-monitor-graphiti-chit`
- `health-sync`
- `finance-sync`

### Memory

Primary memory path:
- `Pmoves-cipher` at `http://localhost:8096`

Codex memory functions:
- store decisions, checkpoints, and reasoning traces in Cipher
- use Graphiti/CHIT handoff artifacts for cross-agent continuity
- fall back to repo-local docs only when Cipher is unavailable

Reference:
- `pmoves/docs/AGENTS/CODEX_CIPHER_MEMORY_IMPLEMENTATION_MAP.md`

### Personas

Primary persona path:
- `pmoves/docs/AGENTS/PERSONAS.md`
- `pmoves/supabase/initdb/17_persona_seed.sql`

Codex should think in persona lanes, not just command lanes:
- `Developer`
- `Researcher`
- `Coordinator`
- `Security Auditor`
- `Tester`
- `Archivist`

Choose the persona that matches the task's risk and evidence needs, then keep
the Codex voice terse while honoring the selected persona's tool and routing
policy.

### Voice

Primary voice path:
- `pmoves/config/agent_signatures.yaml`
- `pmoves/docs/AGENTS/CODEX_PERSONA_STYLE_PLAYBOOK.md`
- `.claude/context/voice-personas.md`

Codex default writing voice remains `terse`, but Codex may route through PMOVES
voice surfaces when the task needs narration or persona-aligned audio:
- `Flute-Gateway`
- `PMOVES-Ultimate-TTS-Studio`
- `PMOVES-Pipecat`

## Submodule Traversal

For submodule work:

1. Read `.claude/context/submodules.md`
2. Read `.claude/context/submodule-workflow.md`
3. Read the matching overlay in `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/`
4. Use `pmoves/configs/submodule_skill_registry.json` to choose skills/docs
5. Work in the submodule first
6. Land the submodule commit
7. Update the PMOVES.AI gitlink last

High-value submodules for Codex-led traversal:
- `PMOVES-Agent-Zero`
- `PMOVES-Archon`
- `PMOVES-BoTZ`
- `PMOVES-HiRAG`
- `PMOVES.YT`
- `PMOVES-supabase`
- `Pmoves-cipher`
- `PMOVES-ToKenism-Multi`
- `PMOVES-Pipecat`
- `PMOVES-n8n`

## Selection Heuristics

Use these defaults unless repo evidence says otherwise:

- If the task is cross-service and action-oriented, start with `Agent Zero`.
- If the task is prompt, form, or persona heavy, bring in `Archon`.
- If the task needs retrieval, ask `Hi-RAG` before adding new data paths.
- If the task needs long-lived continuity, use `Cipher Memory`.
- If the task touches audio, narration, or persona voice, route through `Flute`.
- If the task touches workflow glue, prefer `n8n` over bespoke orchestration.
- If the task touches YouTube/media ingestion, start at `PMOVES.YT`.
- If the task touches CHIT/geometry, start at `ToKenism` and validate with `Hyperdimensions`.
- If the task touches model/provider routing, keep `TensorZero` and the Supabase model registry authoritative.

## Validation

Minimum validation for Codex-led repo work:
- `make -C pmoves codex-health-quick`
- `make -C pmoves codex-audit`
- `make -C pmoves codex-parity-check`

Then run the domain-specific validation path for the touched surface:
- retrieval -> `make -C pmoves smoke-gpu`
- UI -> `make -C pmoves notebook-workbench-smoke`
- media/publisher -> `make -C pmoves jellyfin-verify`
- general runtime -> `make -C pmoves smoke`

## Related Docs

- `pmoves/docs/AGENTS/CODEX_OPERATOR_HOME.md`
- `pmoves/docs/AGENTS/CODEX_RUNTIME_PROTOCOL.md`
- `pmoves/docs/AGENTS/CODEX_CLAUDE_PARITY_MAP.md`
- `pmoves/docs/AGENTS/PmovesSKillZ.md`
- `pmoves/docs/AGENTS/PERSONAS.md`
- `pmoves/docs/AGENTS/PMOVES_UNIFIED_AGENT_TAXONOMY.md`
- `pmoves/docs/AGENTS/SUBMODULE_CODEX_HOMES/README.md`
