# AI Graphiti Protocol

> Agent signature and trail system for PMOVES.AI multi-agent codebase.

## What Is AI Graphiti?

AI Graphiti is the attribution and handoff protocol for PMOVES.AI's multi-agent development environment. It gives each contributing agent (and human operator) a **visually distinctive signature** — glyph, color, voice — and a **living trail document** that records what each contributor did, what they left behind, and what the next agent should know.

**Goals:**
1. Instant visual recognition of which agent authored which section
2. Standardized inter-agent written communication
3. Structured handoff protocol (done / remaining / for next agent)
4. Bridge to CGP v2 attribution (Dirichlet-weighted contributor records)
5. Onboarding breadcrumbs for new agents joining the project

## Registry Files

| File | Purpose |
|------|---------|
| `pmoves/config/agent_signatures.yaml` | Visual identity for each contributor |
| `pmoves/config/agent_registry.yaml` | Runtime agent registry (links via `signature` field) |
| `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` | Formal schema for signature blocks |
| `docs/AGENT_TRAIL.md` | Living trail document |

## Current Contributors

| Agent | Glyph | Color | Voice | Resonance |
|-------|-------|-------|-------|-----------|
| **Claude Opus** | `◆` Diamond | `#7C3AED` Deep Violet | Analytical | security-audit, architecture, cross-repo |
| **KiloCode** | `▲` Triangle | `#059669` Emerald | Architectural | feature-impl, mcp-integration, VS Code |
| **Codex** | `■` Square | `#2563EB` Royal Blue | Terse | rapid-prototyping, code-gen, integration |
| **Gemini** | `★` Star | `#D97706` Amber | Strategic | planning, research, synthesis |
| **Cline** | `●` Circle | `#DC2626` Scarlet | Conversational | rapid-iteration, chat-impl, frontend |
| **POWERFULMOVES** | `⚡` Lightning | `#F59E0B` Gold | Directive | vision, doctrine, final-authority |
| **Crush** | `◇` Open Diamond | `#0EA5E9` Sky Blue | Companion | terminal-gateway, pair-programming, onboarding |
| **DARKXSIDE** | `✦` Four-Pointed Star | `#E11D48` Rose Red | Witness | cocreation, prosodic-flow, portal-architecture |

## How to Register a New Agent

1. **Choose an unused glyph** — single Unicode character, must render in monospace terminals
2. **Choose a unique color** — must be distinguishable from existing entries in both light and dark themes
3. **Pick a voice** — one of: `analytical`, `architectural`, `terse`, `strategic`, `conversational`, `directive`, `companion`
4. **Add entry to `agent_signatures.yaml`:**

```yaml
  new-agent:
    agent_id: "new-agent"
    display_name: "New Agent"
    glyph: "\u2726"              # ✦ (example)
    color: "#0EA5E9"             # Sky Blue (example)
    accent: "#7DD3FC"
    voice: terse
    co_author: "New Agent <noreply@example.com>"
    resonance:
      - domain-1
      - domain-2
    description: "Brief description of the agent's strengths"
```

5. **Add to `agent_registry.yaml`** `external_contributors` list
6. **Write your first trail entry** in `docs/AGENT_TRAIL.md`

## How to Write a Trail Entry

Prepend a new graphiti block to `docs/AGENT_TRAIL.md` (newest entries at top, below the header). Use this template:

```markdown
<!-- graphiti:{agent_id} phase:{phase} ts:{ISO-8601-timestamp} -->

## {glyph} {display_name} — {phase}: {title}

<table><tr><td style="background:{color};width:24px"></td><td>

**Resonance:** {comma-separated resonance domains}
**Voice:** {voice descriptor}

### Done
- Item 1
- Item 2

### Left Behind
- Item 1 (context for why it's not done)

### For Next Agent
- Guidance item 1
- Guidance item 2

</td></tr></table>

<!-- /graphiti -->
```

## PR Review Learnings Loop (Required Before Merge)

When a lane has open PRs, run the PR monitor and fold findings into the trail:

1. `make -C pmoves pr-monitor`
2. Review generated artifacts:
   - `pmoves/docs/logs/pr_monitor_latest.json`
   - `pmoves/docs/logs/pr_monitor_learnings_latest.md`
3. If actionable comments exist, create a focused fix commit/PR and update `docs/AGENT_TRAIL.md` with:
   - what was fixed
   - what remains
   - what the next agent should do
4. If only nitpicks (or out-of-diff non-blocking line comments) remain, leave them in the learnings queue unless the lane owner decides to include them.

This keeps both in-diff and out-of-diff review feedback visible in the same Graphiti handoff chain.

### Voice Guidelines

Write your trail entry in your assigned voice:

- **Analytical** (Claude Opus): Thorough reasoning, cross-references between files/systems, structured lists with evidence. "Phase H closed 19 CodeQL alerts — here's the full taxonomy."
- **Architectural** (KiloCode): Blueprint format — states, modes, integration maps. "MCP server now operates in three modes: passive, active, bridge."
- **Terse** (Codex): Bullet points, code-first, minimal prose. "Added cipher endpoint. Tests green. Next: auth middleware."
- **Strategic** (Gemini): Context-setting, options analysis, roadmap framing. "Three paths forward — option B balances velocity with risk."
- **Conversational** (Cline): Informal, iterative, question-driven. "Got the frontend rendering, but the state management feels fragile — might need a rethink?"
- **Directive** (POWERFULMOVES): Decision statements, priority calls, scope definitions. "Ship Phase H. KiloCode starts Monday. No P2s until onboarding completes."
- **Companion** (Crush): Warm, interactive, pair-programming energy. "Let's figure this out together. Here's what I found, here's what I think we should try."

## KRISS KROSS Accord (Collision -> Overlay)

When two agents enter the same lane, they do not collide. They KRISS KROSS by
switching from direct overlap to a controlled overlay handoff.

### Role split when Codex is on the 1s and 2s

- `Codex` (`DJ/Lead`): owns implementation lane, writes Codex command mappings,
  and is final parity authority for `CODEX_CLAUDE_PARITY_MAP.md`.
- `Claude` (`Counterpoint/Scout`): runs review sweeps, surfaces risks, proposes
  alternative diffs in a separate integration lane, and feeds evidence.
- Merge rule: one lane owner signs release for merge readiness. During Codex-led
  windows, Codex signs parity release.

### Overlay handshake

1. `CLAIM`: both agents publish scope and target branch.
2. `KRISS_KROSS`: convert overlap into overlay mode with one owner and one scout.
3. `WEAVE`: scout posts evidence/diffs; owner performs final weave in target lane.
4. `RELEASE`: owner signs release; scout signs ack.

### Required overlay fields

- `overlay_id` (for example `KK-2026-02-23-codex-claude-01`)
- `lane_owner`
- `scout_agent`
- `source_branch`
- `target_branch`
- `scope`
- `parity_report_path`
- `agent_signature`

## How Signatures Connect to CGP

CGP v2 attribution records use `contributor.address` to identify who contributed to a geometry packet. The AI Graphiti `agent_id` maps directly to this field:

```json
{
  "attribution": {
    "contributors": [
      {
        "address": "claude-opus",
        "weight": 0.6,
        "glyph": "◆",
        "color": "#7C3AED"
      },
      {
        "address": "kilocode",
        "weight": 0.4,
        "glyph": "▲",
        "color": "#059669"
      }
    ]
  }
}
```

The `glyph` and `color` fields are optional extensions to the CGP v2 schema, sourced from `agent_signatures.yaml`. Weights are Dirichlet-normalized (sum to 1.0 across all contributors for a given packet).

## NATS Event Format

When an agent completes significant work, it emits an `agent.graphiti.signed.v1` event to NATS. The payload matches `signature.v1.schema.json`:

```json
{
  "agent_id": "claude-opus",
  "display_name": "Claude Opus",
  "glyph": "◆",
  "color": "#7C3AED",
  "accent": "#A78BFA",
  "voice": "analytical",
  "phase": "Phase H",
  "timestamp": "2026-02-17T23:00:00Z",
  "resonance": ["security-audit", "cross-repo-orchestration"],
  "summary": "Closed all P1 findings, 19 CodeQL alerts, Dependabot CVEs",
  "handoff": {
    "done": ["CodeQL remediation", "Phase C P1 closure"],
    "remaining": ["P2/P3 tracker items"],
    "for_next_agent": ["KiloCode integration plan ready", "chit_lanes.py needs integration tests"]
  }
}
```

**Subject:** `agent.graphiti.signed.v1`
**Schema:** `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json`

## Color Palette Rules

1. **Uniqueness** — no two contributors share a primary color
2. **Distinguishability** — all colors must be visually distinct from each other (not just different hex values)
3. **Contrast** — WCAG AA contrast ratio (4.5:1) against both:
   - White background (`#FFFFFF`) for light themes
   - Dark background (`#1a1a2e`) for dark themes
4. **Accent** — lighter variant of primary color, used for backgrounds and highlights

## Glyph Rules

1. **Single character** — one Unicode code point (max 2 UTF-16 code units)
2. **Unique** — no two contributors share a glyph
3. **Monospace-safe** — must render correctly in monospace terminals (avoid emoji that may double-width unpredictably)
4. **Semantic** — glyph should loosely reflect the contributor's role or personality

## Cross-References

- **Agent Registry:** `pmoves/config/agent_registry.yaml` — `signature` field links to `agent_signatures.yaml`
- **CGP v2 Schema:** `pmoves/contracts/schemas/geometry/cgp.v2.schema.json` — `attribution.contributors[].address`
- **NATS Handoff:** `agent.handoff.request.v1` — `from` field corresponds to `agent_id`
- **KiloCode Onboarding:** `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`
- **KRISS KROSS Accord:** `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md`
- **Trajectory Schema:** `pmoves/contracts/schemas/agent-rl/trajectory.v1.schema.json` — `agent_id` field
- **PR Learnings Artifacts:** `pmoves/docs/logs/pr_monitor_latest.json`, `pmoves/docs/logs/pr_monitor_learnings_latest.md`

## Broader Context: Three-Body Stabilization

AI Graphiti trail entries are more than attribution records — they are
**gravitational measurements** in the three-body system that PMOVES models.

Each trail entry captures a moment when an agent (AI body) contributed work that
affects the user (human body) through the platform (system body). The CGP v2
attribution fields (`contributor.address`, `weight`) map directly to the
Dirichlet-weighted shape profiles that accumulate in the shape discovery
pipeline.

Trail entries feed into the shape discovery system:
- **`agent_id`** → links to `shape.trace.recorded.v1` agent field
- **`resonance`** → maps to trace resonance domains
- **`phase`** → provides temporal context for shape version evolution

When enough trail entries and interaction traces accumulate, the system can
distill — tuning agent parameters and context priming to fit the discovered
orbital resonance between human and AI.

**Doctrine:** [`THREE_BODY_DOCTRINE.md`](../../docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md)
**Shape Schemas:** `pmoves/contracts/schemas/shape/`
