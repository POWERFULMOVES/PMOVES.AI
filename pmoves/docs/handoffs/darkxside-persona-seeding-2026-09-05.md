# Handoff: DARKXSIDE persona seeding (2026-09-05)

**Lane owner (proposed):** A0 darkxside instance (`pmoves-agent-zero-darkxside`, supervisor :8092) with Crush for the SQL/seed files. **Raised by:** 5090-CLAUDE. **Tracking:** #2968 (persona SQL review), #2966 (room).

## Why now

The DARKXSIDE room is served again (OpenRoom rebuilt from #2949), the Neo4j mindmap is seeded for the first time (Persona nodes `powerfulmoves`, `darkxsideshows` + 4 aliases), and Neo4j authenticates. What is missing is the persona itself as data: there is no DARKXSIDE row anywhere in Supabase, and the persona SQL that would hold it has no RLS (#2968).

## Sources of truth (read, do not invent)

- `pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md` — witness/cocreator signature, CHIT CGP attestation (glyph, color, voice, resonance).
- `pmoves/docs/AGENTS/PERSONAS.md`, `pmoves/config/agent_registry.yaml` — taxonomy and identity/alter model (see #2935 for alters vs roles).
- `pmoves/config/rooms/darkxsides.room.json` — `agent_id: darkxside-persona`, `alter: darkxside`, apps, publish gate, notebook workspace `darkxside`.
- Operator canon: the human DARKXSIDE is not the AI persona; the persona owns its forms and signatures; no naming drift.

## Deliverables

1. **One key across three stores.** `darkxside-persona` (registry/rooms), Supabase `pmoves_core.personas.name`, Neo4j `Persona.slug`. Today Neo4j says `darkxsideshows`; reconcile with an alias, not a rename.
2. **Supabase seed** `pmoves/supabase/migrations/<ts>_seed_darkxside_persona.sql`, landing **in the same change** as the RLS migration from #2968 (never before it). `model_preference` is a TensorZero route name, not a vendor id.
3. **Cipher seeding.** Store the persona canon as intent-shaped memories (marco/polo) under the room's workspace so the A0 darkxside instance recalls it at boot; verify with a recall round-trip, not a health endpoint (the #2935 §3 lesson).
4. **A0 profile.** `agent_profile_set` on the darkxside instance via the `_a0_connector` v1 surface (skill `a0-archon-bridge`), pointing at the seeded persona; confirm with `capabilities` plus one `message_send`.

## Definition of done

The personas table returns one `darkxside-persona` row under RLS; the Neo4j persona `darkxsideshows` carries the registry key as an alias; Cipher recall of "who is DARKXSIDE in this room" returns the signature; the A0 instance answers in persona.
