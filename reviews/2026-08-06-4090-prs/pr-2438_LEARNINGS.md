# LEARNINGS — PR #2438 (feat/rooms wire ComfyUI + TTS + E2B bindings to DARKXSIDE room)

> 4-bucket review taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed)
> 5-class pr-trim taxonomy (legit / already-fixed / owner / out-of-scope / pre-existing)
> PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/2438
> Author: 4090 node (`feat/darkxside-room-enhancements`, 2 commits, 412+/40-, 3 files)
> Reviewer: Mavis (mvs_5d5493b128b640e9aff8d45adcc77a66, orchestrator)
> Review date: 2026-08-06

## What the PR does

3 files, 412 insertions, mostly in `pmoves/config/rooms/darkxsides.room.json`:
- 3 new skill bindings: `pinokio-launch-comfyui`, TTS voice (not visible in truncated diff but title mentions), `e2b-shared-desktop`
- 2 new top-level fields on the room: `skills: [pinokio-bridge, flute-gateway, comfyui, e2b-mcp]` and `default_services: [up-comfyui]`
- Reformats existing JSON bindings (no semantic change to existing entries, just whitespace expansion)
- Updates `website/chit-tour/data.generated.js` and `website/chit-tour/index.html` for agent count 96→97
- A small piece of the diff shows `\ No newline at end of file` — minor lint issue, not a bug

## 2 review threads (BOTH P1, chatgpt-codex-connector) — REAL BLOCKERS

| # | Comment | 4-bucket | 5-class | Verdict |
|---|---------|----------|---------|---------|
| 1 | "Remove skill bindings from the apps array" — the 3 new entries (binding_id, skill_id, room_id, display_name, intent, activation, surface, execution, context, outputs, guardrails, enabled, tags) are **inside the `apps` array**, but the apps array expects app entries (app_id, kind, route, etc.) not skill bindings. When the room is validated, these 3 will fail schema validation. | legit | legit | **P1 BLOCKER.** The 3 new entries are skill bindings (the correct structure is in `skill_bindings[]`), not app entries. Move them to a new `skill_bindings[]` top-level array (matching the pattern in `tokenism.room.exchange.json` from the 2026-07-20 first slice). |
| 2 | "Define new room fields in the schema before using them" — `skills` and `default_services` are new top-level fields that aren't in the room manifest schema (`pmoves/contracts/schemas/room.manifest.v1.schema.json`). Any room validator (e.g., `validate_room_manifests.py`) will reject the room. | legit | legit | **P1 BLOCKER.** Add `skills` and `default_services` to the schema with the right types (skills: string[] of skill_ids; default_services: string[] of docker-compose service names), OR document them as provisional pending the slice 1 operator signoff (matching the precedent in `Mavis::OPEN-ROOM-LANE-CLAIM::2026-07-20` where `room_type: exchange` and `meta` were provisional). |

## 5-class review summary

| Class | Count | Notes |
|-------|-------|-------|
| legit | 2 | Both P1s are real blockers — must fix before merge |
| already-fixed | 0 | — |
| owner | 0 | — |
| out-of-scope | 0 | — |
| pre-existing | 0 | — |

## Sub-bug also worth flagging

The diff ends with `\ No newline at end of file` for `darkxsides.room.json`. This is a lint issue (`pmoves/lint` likely flags it) and the file should end with a trailing newline. Trivial fix, but real.

## 96→97 agent count update: CORRECT

I verified the agent count by parsing `pmoves/config/agent_registry.yaml` directly:

```
$ python -c "import yaml; d=yaml.safe_load(open('pmoves/config/agent_registry.yaml',encoding='utf-8')); print('agents:', len(d.get('agents',[])))"
agents: 97
```

The CHIT tour data was at 96 (stale, generated 2026-08-01 with 96 agents). The actual current count is 97. The PR's 96→97 update is **accurate and necessary** — the chit-tour tour was showing a stale number.

## Recommendation

**BLOCK ON MERGE.** Two P1 schema/binding issues must be resolved before the room manifest can be loaded by the validator. Suggested order:

1. **Move the 3 new entries** from `apps[]` to a new `skill_bindings[]` top-level array (or whatever the existing convention is — check `tokenism.room.exchange.json` or `persona.room.livingdoc.json` for the canonical pattern).
2. **Update the schema** (`pmoves/contracts/schemas/room.manifest.v1.schema.json`) to add `skills` and `default_services` with proper types.
3. **OR** if the operator prefers the provisional path (matching the slice 1 precedent), add a comment to the manifest noting the fields are pending operator signoff.
4. **Add the trailing newline** to `darkxsides.room.json`.
5. **Re-run** `pmoves/scripts/validate_room_manifests.py` to confirm the room now passes validation.

## The 96→97 count update is the more interesting learning

The CHIT tour was showing 96 agents in the live tour (data.generated.js, generated 2026-08-01). The actual registry has 97. The drift was 6 days. This is a small but real example of why the chit-tour data is `data.generated.js` and NOT a static file — the make target `chit-tour-data` should be part of the standard "after adding an agent" workflow. This is a **process improvement** signal, not a PR-blocker.

## What I'm NOT recommending

- Don't ask the 4090 author to also do the schema work in this PR — that's a separate concern and should be tracked in the room-manifest lane (which Mavis owns per the 2026-07-20 first slice).
- Don't block on the title wording — "wire ComfyUI + TTS + E2B bindings" is accurate.
- Don't request tests for the new bindings — those are pure config, no logic to test.
