# PMOVES Room Manifest Contract
_Last updated: 2026-03-27_

## Purpose
Define one interface contract for agent-owned rooms so OpenRoom-style browser desktops and Open Notebook-style durable workspaces can converge on a shared PMOVES control plane.

This contract makes four things explicit:
- the room shell an agent sees
- the notebook state the room reads and writes
- the apps/actions available inside the room
- the skills bound to those surfaces

## Why This Exists
OpenRoom demonstrates a useful shape: a browser desktop where an agent operates apps through a structured action system. PMOVES already has the other half of that system in Open Notebook, Notebook Workbench, Graphiti, persona/alter identity, and BoTZ skills.

The gap is the interface contract.

Without a room manifest:
- agent shells are implied by docs and local setup, not declared
- notebook persistence and UI state are coupled informally
- skills exist as catalogs, but not as room-aware bindings
- alters can change voice and identity, but not their workspace layout or action affordances

## Contract Model
### 1. Room
A room is the audience-facing topology — the entrypoint through which users (human or agent) access the platform's capabilities.

It owns:
- shell theme and layout
- installed apps and default routes
- room-local policy decisions
- bindings between skills and surfaces

It does not own durable memory.

### 2. Notebook
The notebook is the durable state plane.

It owns:
- threads, entries, pages, sources, and snapshots
- writeback targets for skills and apps
- durable artifacts the room can reopen later

A room may mirror notebook state or treat it as authoritative, but it should not replace it.

### 3. Apps and Actions
Apps are surface providers inside the room. They expose structured actions instead of free-form UI assumptions.

Examples:
- notebook workbench
- chat panel
- media panel
- graph canvas
- dashboard/operator views

The room manifest declares which apps are present and which action namespace they speak.

### 4. Skill Bindings
Skills are reusable capabilities. A room binding makes a skill executable in context.

A binding answers:
- where the skill appears
- what context it receives
- how it runs
- where outputs go
- what permissions and guardrails apply

## Core Rules
1. Room owns presentation and session ergonomics; notebook owns durable state.
2. Skills never bind directly to raw UI assumptions; they bind to declared surfaces and action namespaces.
3. Suits and personas are runtime overlays on the platform — they control appearance, voice, and model routing within a room, but do not define the platform's topology or contract shape. The platform exists before any suit is applied.
4. Skills may write back into notebook state only through declared targets.
5. Room policy must remain compatible with PMOVES model routing, Graphiti, and CHIT rails.
6. Rooms should be additive overlays, not hard forks of upstream interface systems.

## Schema Files
- `pmoves/contracts/schemas/room/room.manifest.v1.schema.json`
- `pmoves/contracts/schemas/room/skill.binding.v1.schema.json`

## Canonical Seed Location
Git is now the canonical seed for room manifests.

- Catalog: `pmoves/config/rooms/catalog.json`
- Seed manifests:
  - `pmoves/config/rooms/4090-field.room.control.json`
  - `pmoves/config/rooms/5090-voice.room.studio.json`
  - `pmoves/config/rooms/z890-infra.room.fabric.json`

Supabase or another runtime store can mirror these later, but the seed shape starts here so rooms can be reviewed, diffed, and versioned like any other PMOVES control-plane asset.

Validation command:
- `python pmoves/scripts/validate_room_manifests.py`

## Room Manifest Shape
The room manifest declares:
- identity: `room_id`, `agent_id`, optional `alter`
- shell: theme, layout, panels
- apps: routes, capabilities, action namespaces
- notebook: provider, workspace/thread refs, sync mode
- skill bindings: room-local binding records
- policies: model routing, publish policy, memory policy
- stage: current lifecycle state (`rehearsal` | `live` | `review` | `archive`)
- telemetry/provenance: optional observability and trace context

## Skill-to-Room Binding Model
A skill binding is intentionally separate from the skill definition.

The skill definition says what a skill is.
The binding says how this room uses it.

Binding dimensions:
- activation: explicit, suggested, ambient, or workflow
- surface: panel, canvas, toolbar, sidebar, modal, floating, background
- execution: inline, workflow, background, deferred
- context: notebook thread, selection, graphiti trail, persona, room state, open apps
- outputs: notebook entry/page, room state, app action, NATS event, artifact store, chat response
- guardrails: approval, runtime cap, one-run-at-a-time, fail-open vs fail-closed

This keeps the marketplace portable while letting each agent room feel distinct.

## Example Manifest
```json
{
  "room_id": "4090-field.room.control",
  "version": "1.0.0",
  "display_name": "4090 Field Control Room",
  "description": "Noise-reduction room for review, topology, and handoff control.",
  "agent_id": "4090-claude",
  "alter": "4090-field",
  "room_type": "scout",
  "owner_mode": "alter",
  "shell": {
    "theme": {
      "theme_id": "field-control",
      "accent_color": "#065F46",
      "skin": "signal-grid",
      "icon": "fresnel"
    },
    "layout": {
      "default_route": "/dashboard/notebook/runtime",
      "panels": [
        {
          "panel_id": "chat-main",
          "kind": "chat",
          "position": "left",
          "size": 28,
          "pinned": true
        },
        {
          "panel_id": "notebook-main",
          "kind": "notebook",
          "position": "center",
          "size": 52,
          "pinned": true
        },
        {
          "panel_id": "graphiti-side",
          "kind": "graph",
          "position": "right",
          "size": 20,
          "pinned": false
        }
      ]
    }
  },
  "apps": [
    {
      "app_id": "notebook-workbench",
      "kind": "notebook",
      "route": "/notebook-workbench",
      "provider": "pmoves-notebook-workbench",
      "action_namespace": "notebook",
      "capabilities": ["threads", "entries", "snapshots", "search"],
      "pinned": true
    },
    {
      "app_id": "graphiti-status",
      "kind": "graph",
      "route": "/dashboard/graphiti",
      "provider": "pmoves-ui",
      "action_namespace": "graphiti",
      "capabilities": ["trail", "audit", "handoff"],
      "pinned": false
    }
  ],
  "notebook": {
    "provider": "open-notebook",
    "workspace_ref": "ops-control",
    "thread_ref": "agent-handoffs",
    "default_page": "current-lane",
    "sync": {
      "mode": "mirrored",
      "writeback_targets": ["entries", "threads", "snapshots"],
      "artifact_prefix": "rooms/4090-field"
    }
  },
  "skill_bindings": [
    {
      "binding_id": "handoff-scout",
      "skill_id": "submodule-parity",
      "room_id": "4090-field.room.control",
      "display_name": "Scout Handoff",
      "intent": ["handoff", "review", "triage"],
      "activation": {
        "invocation_mode": "suggested",
        "trigger_phrases": ["prepare handoff", "review this lane"],
        "requires_selection": true
      },
      "surface": {
        "app_id": "notebook-workbench",
        "target": "toolbar",
        "route": "/notebook-workbench"
      },
      "execution": {
        "mode": "workflow",
        "run_as": "agent",
        "stream": "status",
        "max_steps": 6
      },
      "context": {
        "sources": ["notebook-thread", "graphiti-trail", "persona", "room-state"],
        "include_last_turns": 8,
        "notebook_writeback": true,
        "artifact_types": ["text", "json"]
      },
      "outputs": [
        {
          "target": "notebook-entry",
          "delivery": "append",
          "path": "threads/agent-handoffs",
          "artifact_type": "text"
        },
        {
          "target": "chat-response",
          "delivery": "notify",
          "artifact_type": "text"
        }
      ],
      "guardrails": {
        "require_approval": false,
        "max_runtime_sec": 300,
        "fail_open": false,
        "one_active_run": true
      },
      "enabled": true,
      "tags": ["handoff", "graphiti", "control"]
    }
  ],
  "policies": {
    "model_routing": "hybrid",
    "publish": {
      "allow_nats_emit": true,
      "allow_external_publish": false,
      "allowed_subjects": ["agent.graphiti.signed.v1", "ops.pr.review.completed.v1"]
    },
    "memory": {
      "graphiti": true,
      "notebook_writeback": true,
      "chit_handoff": true
    }
  },
  "telemetry": {
    "graphiti_phase": "Control Room",
    "room_events_subject": "room.session.updated.v1",
    "healthcheck_route": "/api/audit/summary"
  },
  "provenance": {
    "source": "PMOVES room contract draft",
    "updated_at": "2026-03-27T12:00:00Z",
    "related_docs": [
      "pmoves/docs/MODEL_FABRIC_CONTRACT.md",
      "pmoves/docs/infrastructure/UI_NOTEBOOK_WORKBENCH.md",
      "pmoves/docs/BOTZ_SKILLS_MARKETPLACE.md"
    ]
  }
}
```

## Integration Guidance
### OpenRoom-style interfaces
Use the room manifest as the browser-desktop declaration layer.

That means:
- window/panel composition comes from `shell.layout`
- installed apps come from `apps`
- chat/app interoperability comes from `action_namespace`
- per-agent flavor comes from `agent_id` + `alter` + `theme`

### Open Notebook / Notebook Workbench
Use notebook as the durable substrate.

That means:
- room sessions can reopen the same threads/pages/snapshots
- skills can persist outputs without inventing a second storage model
- room shells stay swappable while notebook history remains stable

### PMOVES skills marketplace
Keep skill definitions portable and context-light.
Bind them into rooms locally through `skill.binding.v1`.

This prevents one marketplace skill from assuming every agent needs the same panel, model lane, or notebook target.

## App Status Lifecycle
_Added 2026-03-28_

Each app declared in a room manifest has an optional `status` field:
- `active` — route exists and is functional (default if omitted)
- `planned` — route declared but not yet implemented; renders as inactive in UI
- `deprecated` — route exists but scheduled for removal

This lets rooms declare future surfaces without breaking validation.

## Runtime Taxonomy
_Added 2026-03-28_

Three optional array fields bridge room contracts to the operational topology:
- `team_refs` — agent team identifiers from `pmoves/configs/agent-teams.yaml`
- `service_refs` — Docker Compose service names the room depends on
- `launcher_refs` — make targets or Pinokio launcher identifiers for room bringup

Example:
```json
{
  "team_refs": ["orchestration", "data", "infra"],
  "service_refs": ["agent-zero", "supabase", "nats", "prometheus"],
  "launcher_refs": ["up-agents", "up-monitoring"]
}
```

## Recommended Next Implementation Steps
1. Add a `room_events_subject` consumer in the UI/launcher layer so room changes become observable.
2. Map existing Notebook Workbench surfaces onto declared `action_namespace` values.
3. ~~Add room defaults for `5090-voice`, `4090-field`, and `z890-infra` as first manifest examples.~~ DONE — seeded under `pmoves/config/rooms/`.
4. Mirror room manifests into Supabase or another runtime store only after a loader exists; keep git as canonical seed.
5. ~~Add one smoke path that loads a manifest and verifies app routes, notebook refs, and skill bindings resolve.~~ DONE — `validate_room_manifests.py`.
6. Add `/dashboard/review`, `/dashboard/voice`, `/dashboard/media` route implementations. DONE — PR #1142.
7. Populate `team_refs`/`service_refs`/`launcher_refs` in all room manifests. DONE — PR #1143.

## Related References
- `pmoves/docs/MODEL_FABRIC_CONTRACT.md`
- `pmoves/docs/infrastructure/UI_NOTEBOOK_WORKBENCH.md`
- `pmoves/docs/BOTZ_SKILLS_MARKETPLACE.md`
- `pmoves/config/agent_signatures.yaml`
- `plans/KILOCODE_PMOVES_INTEGRATION_PLAN.md`

