# Release Notes — 2026-05-15: MiniMax Token Plan Phase 2

## Overview

This release lands the MiniMax Token Plan Phase 2 integration originally authored by **MiniMax Agent** on 2026-05-13 (`ACK::MINIMAX-AGENT::TOKEN-PLAN-PHASE2-INTEGRATION`) and parked/rebased to current main by 5090-CLAUDE on 2026-05-15.

It is a **suit update** per `pmoves/docs/hardening/PMOVES-hardening-tracker.md` §6.4: a new `minimax-edition` alter is added to the agent signatures, two new model suits land, and provider cascade routing gains Token Plan tier awareness. Activation requires the operator to configure `MINIMAX_TOKEN_PLAN_API_KEY` before the M2.7 1M-context lane is reachable.

## Commits

| Commit | Subject |
|--------|---------|
| (squash target) | `feat(minimax): Token Plan Phase 2 — model suits + agent profile + NATS subjects` |
| `72909b2871` | `fix(minimax): YAML structure — sequence items need explicit name: key` (Codex review fix on PR #1484) |

## Suit-touching changes

| File | Change |
|------|--------|
| `pmoves/config/agent_signatures.yaml` | New alter `minimax-edition` with KiloCode claw resonance; existing `minimax` signature gains Token Plan metadata |
| `pmoves/configs/agent-profiles/minimax_edition.yaml` (new) | M2.7 primary / M2.1 fallback, 5090/4090/Z890 node affinity, FlOO\$ character persona system (Dr. Bean / Mr. Clean / PowerPuff Girls) |
| `pmoves/configs/model-suits/minimax-m2.7.yaml` (new) | 1M token context, multimodal, primary suit |
| `pmoves/configs/model-suits/minimax-m2.1.yaml` (new) | 100K token context, efficient fallback suit |
| `pmoves/tools/models/minimax_provider_cascade.yaml` | Token Plan tier configuration (Starter/Plus/Max/Ultra-Highspeed), rolling 5h quota window for M2.7, `MINIMAX_TOKEN_PLAN_API_KEY` env binding with `MINIMAX_API_KEY` fallback |
| `pmoves/.claude/context/nats-subjects.md` | +7 `minimax.*` NATS subjects (character request/response, voice prosodic, agent trail, agent status, quota warning, quota exhausted) |

## NATS subjects added

- `minimax.character.request.v1` — character persona requests
- `minimax.character.response.v1` — character persona response
- `minimax.voice.prosodic.v1` — prosodic voice synthesis (bridges to FlOO\$ — see PR #1487 architecture review)
- `minimax.agent.trail.v1` — agent trail entries
- `minimax.agent.status.v1` — health heartbeat
- `minimax.quota.warning.v1` — quota low alert
- `minimax.quota.exhausted.v1` — quota exhausted alert (triggers `glm` pay-as-you-go fallback)

## Operator action required before activation

1. **Set `MINIMAX_TOKEN_PLAN_API_KEY` in `env.shared`** — the subscription key for Token Plan access.
2. **Keep `MINIMAX_API_KEY`** as the pay-as-you-go fallback (already present).
3. **Smoke test:** `curl https://api.minimax.chat/v1/models` with the Token Plan key.
4. **Quota monitoring validation:** subscribe to `minimax.quota.warning.v1` and `minimax.quota.exhausted.v1` to confirm alerts flow.

## Skill scaffolding included (not yet wired)

- `.minimax/skills/minimax-docx/` — DOCX manipulation (XSDs, C# Core/CLI, Python helpers)
- `.minimax/skills/minimax-pdf/` — PDF read/create/forms/translate templates
- `.minimax/skills/minimax-pptx/` — PowerPoint helpers
- `.minimax/skills/minimax-xlsx/` — Excel with ISO-IEC29500 schemas
- `.minimax/skills/pocket-init/` — bootstrap scaffolding

These are scaffolding only; skill activation lands in a follow-up PR.

## Downstream chain

- PR #1487 (FlOO\$ architecture) defines how economic-state overlays select MiniMax character archetypes via `persona_overlay.archetype_hint` ↔ `minimax.character.request.v1.persona`.
- Cross-node review team: 4090-CLAUDE (voice integration), SPARK (hologram-geometry overlay), DARKXSIDE (taxonomy + agent_id approval).

## Provenance

- Architecture/code: `MiniMax Agent`, 2026-05-13
- Park / rebase / Codex YAML fix: `5090-CLAUDE`, 2026-05-15
- PR: [#1484](https://github.com/POWERFULMOVES/PMOVES.AI/pull/1484)

<!-- GRAPHITI_MARK: 5090-CLAUDE::MINIMAX-PHASE2-RELEASE-NOTES::2026-05-15 -->
