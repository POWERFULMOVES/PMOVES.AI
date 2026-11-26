# Identity → team scope: a clarification, phase 1 (Claude Code and its siblings)

**Kind:** correction / clarification of how node identities and their team
collections are scoped. Not a defect report.
**Operator direction:** 2026-11-08 / 2026-11-09 (Z890 session, POWERFULMOVES).
**Author:** Z890-CLAUDE (signing card `z890-claude`).
**Known Road:** `launcher:handoff:IDENTITY_TEAM_SCOPE_CLARIFICATION.md` covers the
launcher edits this brief calls for.

## The model being clarified

- A **node identity** (e.g. `claude_z890` → Z890-CLAUDE) holds its **node**,
  not just the repo checkout it was launched in.
- Each identity owns **layered teams**: CLI agents, client surfaces, and claws.
  Every harness on the node (Claude Code, Hermes, Agent Zero, crush, minimax,
  kimi, kilo, codex, …) populates its own team.
- What each team gets is provisioned from **node capability**
  (`pmoves/config/node_roles.yaml`, hardware) and **affinity**
  (`topology.node_affinity`, `pmoves/configs/agent-teams.yaml`).
- Agents and teams an identity creates inherit a **narrower** scope taken from
  their registry target. They are never wider than the identity that made them.
  Secret paths stay zero-access through damage-control whatever scope says.

Today none of this is declared. `agent_registry.yaml` has no scope field,
`agent-teams.yaml` is flat (functional teams + node_affinity, no identity or
harness layering), the PMOVES-registry ACP entries carry no permissions, and
the Claude launchers pass no `--add-dir`, so every Claude identity was confined
to its repo by omission rather than by decision.

## Phase 1 (this change): Claude Code identities

Registry entries `claude_z890`, `claude_5090`, `claude_4090`, `claude_b850`,
`claude_spark` gain an optional `scope:` block:

```yaml
scope:
  host_access: node          # node | repo | none
  host_roots: ["C:/", "D:/", "I:/", "N:/"]   # measured per node, never guessed
  max_subagent_scope: repo   # cap for agents/teams this identity creates
```

- `pmoves/tools/node_identity.py` → `resolve_host_roots()` emits
  `PMOVES_HOST_ROOTS` / `PMOVES_HOST_WHY` alongside the identity outputs.
- `pmoves/scripts/claude-pmoves.sh` (+ `pm-node-identity.sh`) and
  `deploy/provision/claude-pmoves.ps1` add `--add-dir=<root>` for the **main
  session only**. A session launched with `--agent <role>` stays repo-scoped.
- Only Z890's roots are measured (C:, D:, I:, N: present on 2026-11-09). The
  siblings keep no roots until each node measures its own. An unmeasured node
  gets an empty list with a stated reason, not a guess.

## Cross-harness integration: designed for, deferred

The same Claude Code surface runs on other model backends
(`PMOVES_CLAUDE_BACKEND=minimax`, GLM, Ollama) and is reached from Archon and
Pinokio. Scope keys on the **identity**, not the model backend, so a Claude
identity on a MiniMax backend keeps the same scope. Later phases extend the
same `scope:` block to the Hermes suits, Agent Zero, crush, minimax, kimi and
kilo, and layer teams by identity × harness in `agent-teams.yaml`.

## Out of scope here, named so it is not lost

MOF layer placement, CHIT signing of scope changes, voice, theme, glyphs, and
room binding (`pmoves/config/rooms/catalog.json`) are all per-identity
configuration surfaces still to be configured. Each gets its own phase.
