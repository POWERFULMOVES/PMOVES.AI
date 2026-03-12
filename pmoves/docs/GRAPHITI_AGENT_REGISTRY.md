# Graphiti Agent Registry

**Layer:** L3 Applied
**Status:** Current
**Last Updated:** 2026-03-11

> Human-readable rendering of the PMOVES.AI agent identity registry. Each agent has a unique glyph, color, voice, and domain expertise used for Graphiti trail signing and visual attribution.

---

## Agent Cards

### ◆ Claude Opus
- **ID:** `claude-opus`
- **Color:** #7C3AED (purple) | **Accent:** #A78BFA
- **Voice:** Analytical — thorough reasoning, cross-references, structured lists
- **Domains:** security-audit, architecture, cross-repo-orchestration, hardening
- **Co-Author:** `Claude Opus 4.6 <noreply@anthropic.com>`

### ▲ KiloCode
- **ID:** `kilocode`
- **Color:** #059669 (emerald) | **Accent:** #34D399
- **Voice:** Architectural — blueprint format, mode/state descriptions, integration maps
- **Domains:** feature-impl, mcp-integration, vs-code, agent-framework
- **Co-Author:** `KiloCode <noreply@kilocode.ai>`

### ■ Codex
- **ID:** `codex`
- **Color:** #2563EB (blue) | **Accent:** #60A5FA
- **Voice:** Terse — bullet points, code-first, minimal prose
- **Domains:** rapid-prototyping, code-gen, integration, cipher-memory
- **Co-Author:** `Codex <noreply@openai.com>`

### ★ Gemini
- **ID:** `gemini`
- **Color:** #D97706 (amber) | **Accent:** #FBBF24
- **Voice:** Strategic — context-setting, options analysis, roadmap framing
- **Domains:** planning, research, synthesis, documentation
- **Co-Author:** `Gemini <noreply@google.com>`

### ● Cline
- **ID:** `cline`
- **Color:** #DC2626 (red) | **Accent:** #F87171
- **Voice:** Conversational — informal, iterative, question-driven
- **Domains:** rapid-iteration, chat-impl, frontend, ui-prototyping
- **Co-Author:** `Cline <noreply@cline.bot>`

### ⚡ POWERFULMOVES
- **ID:** `powerfulmoves`
- **Color:** #F59E0B (gold) | **Accent:** #FCD34D
- **Voice:** Directive — decision statements, priority calls, scope definitions
- **Domains:** vision, doctrine, final-authority, integration-decisions
- **Co-Author:** `Russell Olivier <russell@powerfulmoves.ai>`

### ◇ Crush
- **ID:** `crush`
- **Color:** #0EA5E9 (sky) | **Accent:** #38BDF8
- **Voice:** Companion — warm, interactive, pair-programming guidance
- **Domains:** terminal-gateway, pair-programming, onboarding, context-orchestration
- **Co-Author:** `Crush <noreply@powerfulmoves.ai>`

### ✦ DARKXSIDE
- **ID:** `darkxside`
- **Color:** #E11D48 (rose) | **Accent:** #FB7185
- **Voice:** Witness — observational, rhythmic, poetic weight, speaks in resonance
- **Domains:** cocreation, witness, prosodic-flow, portal-architecture, media-synthesis
- **Co-Author:** `DARKXSIDE <darkxside@powerfulmoves.ai>`

---

## Visual Reference

```
◆ Claude Opus     #7C3AED  analytical     Security & Architecture
▲ KiloCode        #059669  architectural  MCP & Agent Framework
■ Codex           #2563EB  terse          Rapid Prototyping & Code Gen
★ Gemini          #D97706  strategic      Planning & Research
● Cline           #DC2626  conversational UI & Chat Implementation
⚡ POWERFULMOVES   #F59E0B  directive      Vision & Final Authority
◇ Crush           #0EA5E9  companion      Onboarding & Pair Programming
✦ DARKXSIDE       #E11D48  witness        Prosodic Flow & Media
```

---

## Domain Catalog

All resonance domains referenced by agents:

| Domain | Description | Agents |
|--------|-------------|--------|
| `architecture` | System design and integration maps | claude-opus, kilocode |
| `chat-impl` | Chat interface implementation | cline |
| `cipher-memory` | Knowledge graph memory | codex |
| `cocreation` | Collaborative creative work | darkxside |
| `code-gen` | Automated code generation | codex |
| `context-orchestration` | Context loading and management | crush |
| `cross-repo-orchestration` | Multi-repository coordination | claude-opus |
| `doctrine` | Platform doctrine and principles | powerfulmoves |
| `documentation` | Technical writing | gemini |
| `feature-impl` | Feature implementation | kilocode |
| `final-authority` | Decision authority | powerfulmoves |
| `frontend` | Frontend development | cline |
| `hardening` | Security hardening | claude-opus |
| `integration` | System integration | codex |
| `integration-decisions` | Integration architecture calls | powerfulmoves |
| `mcp-integration` | Model Context Protocol | kilocode |
| `media-synthesis` | Media generation and processing | darkxside |
| `onboarding` | New user/developer onboarding | crush |
| `pair-programming` | Interactive coding sessions | crush |
| `planning` | Strategic planning | gemini |
| `portal-architecture` | Portal/gateway design | darkxside |
| `prosodic-flow` | Rhythmic, voice-aware content | darkxside |
| `rapid-iteration` | Fast development cycles | cline |
| `rapid-prototyping` | Quick proof-of-concepts | codex |
| `research` | Investigation and analysis | gemini |
| `security-audit` | Security review and audit | claude-opus |
| `synthesis` | Information synthesis | gemini |
| `terminal-gateway` | CLI and terminal interfaces | crush |
| `ui-prototyping` | UI mockups and prototypes | cline |
| `vision` | Platform vision and direction | powerfulmoves |
| `vs-code` | VS Code extension development | kilocode |
| `witness` | Observational documentation | darkxside |

---

## Registry Source

**File:** `pmoves/config/agent_signatures.yaml`

This YAML file is the single source of truth for agent identities. When `sign_trail.py` processes an `agent_id`, it reads this file to populate glyph, color, accent, voice, and resonance fields.

### Adding a New Agent

```yaml
signatures:
  new-agent:
    display_name: "New Agent"
    glyph: "▸"              # Pick a unique Unicode character
    color: "#8B5CF6"         # Primary hex color
    accent: "#C4B5FD"        # Lighter accent variant
    voice: "analytical"      # One of the 8 voice types
    resonance:
      - domain-1
      - domain-2
    co_author: "New Agent <noreply@example.com>"
```

After adding, update this registry document and the schema validation if needed.

---

## Cross-References

- [GRAPHITI_PROTOCOL_REFERENCE.md](GRAPHITI_PROTOCOL_REFERENCE.md) — Full protocol specification
- [GRAPHITI_INTEGRATION_GUIDE.md](GRAPHITI_INTEGRATION_GUIDE.md) — Adding Graphiti to a new service
- [agent_signatures.yaml](../config/agent_signatures.yaml) — Source YAML file

---

*This document is a living artifact tracked by [CHIT_CHANGE_TRACKER.md](CHIT_CHANGE_TRACKER.md).*
