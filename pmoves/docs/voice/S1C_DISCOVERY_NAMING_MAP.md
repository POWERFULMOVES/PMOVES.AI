# S1c — Voice Discovery Naming Map

> Status: additive config glue (S1c). Spec: [`docs/superpowers/specs/2026-06-26-voice-agents-design.md`](../../../docs/superpowers/specs/2026-06-26-voice-agents-design.md) §4a "Convergence — Voice as a Discoverable Capability (two planes, one join key)".

Voice is now discoverable through the **same `agent_registry → room` plane as every other capability**, with a join key back to the `voice_profiles` **truth plane** and `grounding_source` markers so a discovering agent knows where to fetch startup grounding.

## Two planes, one join key

| Plane | Substrate | Role | Key |
|-------|-----------|------|-----|
| **Truth + routing** | `pmoves_core.voice_profiles` (DB, `pmoves/db/v5_16_voice_catalog.sql`) | One row = one resolvable voice. Rich `engine` + `engine_specific`, RLS, media (`ref_audio_path`), `grounding` JSONB. | `name` (slug, `^[a-zA-Z0-9_-]{3,64}$`) |
| **Discovery** | `agent_registry.yaml` → `mcp_servers.pmoves_voice_mcp` | Thin shim making voice reachable via the registry. `action_namespace: mcp.v1.voice`. | `action_namespace` ↔ room app |
| **Room** | `pmoves/config/rooms/5090-voice.room.studio.json` | App `mcp-voice` + skill binding `voice-mcp-bridge`. Runtime resolves a voice row by `name` slug. | `app_id` / `action_namespace` |

The discovery plane does **not** collapse the truth plane — it bridges to it via the net-new `resolves` join:

```yaml
# agent_registry.yaml → mcp_servers.pmoves_voice_mcp
resolves:
  registry: supabase
  table: pmoves_core.voice_profiles
  by: name
```

## Naming chain (one documented chain)

```
registry_key (snake)   name / provider (kebab)   action_namespace (mcp.v1.<x>)   voice name (slug)
pmoves_voice_mcp   ↔   pmoves-voice-mcp      ↔   mcp.v1.voice                ↔   <voice_profiles.name>
```

- **registry_key** `pmoves_voice_mcp` — YAML key under `mcp_servers:`.
- **name / provider** `pmoves-voice-mcp` — `mcp_servers[].name`, and the room app's `provider`.
- **action_namespace** `mcp.v1.voice` — shared by the registry entry and the room app `mcp-voice` (this is what the validator cross-checks).
- **voice name (slug)** — a row in `voice_profiles.name`, resolved at runtime through `resolves.by`.

Backing provider for the discovery endpoint is **flute-gateway** (`PMOVES_VOICE_MCP_ENDPOINT`, default `http://flute-gateway:8055/sse`), the same service that resolves voice selection across engines.

## `grounding_source` marker

`grounding_source: true` is a net-new boolean flag on the `mcp_servers` entries that are **startup-grounding sources**. It tells a discovering agent *where to fetch grounding* before it acts:

| Entry | `grounding_source` | What it grounds |
|-------|--------------------|-----------------|
| `pmoves_hirag_mcp` | `true` | Hybrid vector + graph + full-text retrieval (Hi-RAG). |
| `pmoves_cipher_mcp` | `true` | Agent memory (agent_plan / checkpoint / completion) + CHIT trail. |
| `pmoves_voice_mcp` | *(absent)* | Voice is a *grounded* capability, not a grounding source. |

## Resolution path (one path)

```
room discovery (mcp-voice app, action_namespace mcp.v1.voice)
  → agent-registry (mcp_servers.pmoves_voice_mcp + grounding_source entries)
  → voice_profiles.grounding  (resolved by name slug via resolves.by)
  → personas (v5_12) / consciousness_theories (v5_15) / paradigm-proponents
```

## Validator cross-check

`pmoves/scripts/validate_room_manifests.py` now extracts every registered MCP `action_namespace` from `agent_registry.yaml` (`mcp_servers`) and asserts that any room app bound to an `mcp.*` namespace resolves to a registered entry (registry ↔ manifest consistency — kills the double source of truth). Non-MCP apps are untouched, so the check is non-breaking for existing rooms.

Run: `cd pmoves && python scripts/validate_room_manifests.py`

## Lifecycle keys (not synonyms)

- `status` (`planned` / `active`) = **deployment** lifecycle; shared across the DB + YAML registries (voice `status` derives from `voice_profiles.is_active`).
- `evolution_stage` = agent **maturity**; orthogonal — not a synonym for `status`.
