---
name: gepeto-wrapper
description: PMOVES-side mirror of Pinokio 8's built-in gepeto skill. Operates on the pmoves/configs/pinokio-apps/{curated,user}/ registry (slice 4 of the creator-collab lane). Use when a PMOVES agent needs to list / inspect / scaffold / validate / promote Pinokio app entries in the PMOVES registry. Do NOT use for Pinokio 8 launchers themselves — that's the built-in gepeto skill.
version: 1.0.0
lane: creator-collab
slice: 4
date: 2026-07-28
---

# gepeto-wrapper — PMOVES registry surface for the Pinokio apps lane

Pinokio 8 ships a built-in `gepeto` skill that scaffolds new Pinokio
launchers. This PMOVES-side mirror operates on the registry half:
**the YAML entries in `pmoves/configs/pinokio-apps/{curated,user}/`**.
Launchers live in `~/pinokio/api/<slug>/` and are managed by Pinokio
8's own gepeto; this skill doesn't touch them.

The boundary is intentional: **gepeto-wrapper is the contract layer
between Pinokio and PMOVES**. It reads the registry, calls
`pmoves/services/mesh_exposure` to reconcile the live fleet, and
scaffolds new entries. The launchers themselves stay in the Pinokio
git ecosystem.

## When to use

Use `gepeto-wrapper` when a PMOVES agent needs to:

- **List** the curated Pinokio apps + their network_exposure contracts
- **Show** one app's full registry entry (runtime, endpoints, network_exposure)
- **Scaffold** a new entry to `user/<slug>.yaml` from operator inputs
- **Validate** an entry against the slice-4 schema
  (`pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json`)
- **Promote** a `user/` entry to `curated/` after operator review
- **Reconcile** the registry against the live headscale ACL +
  cloudflared tunnel + Cloudflare / Hostinger DNS via the mesh_exposure
  service (slice 4)

Do NOT use this skill for:

- Pinokio 8 launcher authoring → use the built-in `gepeto` skill
- Pinokio 8 SKILL.md generation → use the built-in `pinokio` skill
- Pinokio 8 app discovery (the on-disk scan) → use
  `pmoves/tools/pinokio_apps/discover.py` directly (this skill
  surfaces a *registry* surface, not the disk)

## Companion surfaces

- **pinokio-bridge** (slice 2, `pmoves/skills/pinokio-bridge-skill/`):
  reads Pinokio's on-disk state. gepeto-wrapper is the PMOVES-side
  mirror of *that*, focusing on the registry contract instead of
  the live Pinokio state.
- **pterm**: launches Pinokio apps. gepeto-wrapper does NOT call pterm
  directly — the registry is metadata; pterm is execution.
- **mesh_exposure** (slice 4, `pmoves/services/mesh_exposure/`): the
  writer that keeps the fleet in sync with the registry. The
  `gepeto-wrapper.reconcile` action proxies to mesh_exposure's
  `GET /v1/reconcile/plan` + (operator-approval-gated) `POST /v1/reconcile/apply`.

## Surface

### `list_apps`

List every entry in the curated + user registries, with a one-line
summary per entry.

**Inputs:**
- `--scope` (default: `curated`): one of `curated | user | all`

**Output:** JSON array of `{slug, title, description, l4_public, runtime_summary}`.

**Example:**
```bash
$ pmoves registry list
[
  {"slug":"comfyui-desktop","title":"ComfyUI Desktop","l4_public":true,"runtime_summary":"16GB concurrent autostart"},
  {"slug":"ace-step","title":"ACE-Step Music","l4_public":false,"runtime_summary":"8GB concurrent autostart"},
  {"slug":"wan","title":"Wan Video","l4_public":false,"runtime_summary":"24GB exclusive on-demand"},
  ... 9 more
]
```

### `show_app`

Return the full YAML for one entry, parsed + pretty-printed.

**Inputs:**
- `--slug <slug>` (required)

**Output:** the entry as a JSON dict.

**Example:**
```bash
$ pmoves registry show comfyui-desktop
{
  "schema_version": "1.0.0",
  "slug": "comfyui-desktop",
  "title": "ComfyUI Desktop",
  ...
  "network_exposure": {
    "l1_venv": {"reachable": true},
    "l2_container_same_host": {"reachable": true, "address": "http://host.docker.internal:8188"},
    "l3_mesh": {"reachable": true, "address": "http://comfyui-desktop.powerfulmoves-1.ts.pmoves.net:8188", "headscale_acl_ports": [8188], "tags_required": []},
    "l4_public": {"reachable": true, "tunnel": "pmoves-edge", "dns_record": "comfyui-desktop.pmoves.ai", "public_url": "https://comfyui-desktop.pmoves.ai"}
  }
}
```

### `scaffold`

Interactive: operator provides the required fields; the wrapper
generates a `user/<slug>.yaml` template, validates it against the
schema, and writes the file. The operator can then review and
`promote` it to `curated/`.

**Inputs:** (all required, prompted interactively)
- `slug` (must match the Pinokio app dir name in `~/pinokio/api/<slug>/`)
- `title` (human-readable display name)
- `description` (one paragraph)
- `primary_port` (0 = dynamic, Pinokio assigns at runtime)
- `gpu_required`, `min_vram_mb`, `gpu_arch` (array of `sm_*` / `gfx*`)
- `gpu_reservation_mb`, `gpu_reservation_mode` (concurrent | exclusive)
- `autostart` (default false for new apps; flips true after operator review)
- `requires_hf_login` (default false)
- `l4_public` (default false; set to true to also expose on the public website)
- `l4_tunnel` (default `pmoves-edge` when l4_public is true)
- `l4_dns_record` (default `<slug>.pmoves.ai` when l4_public is true)
- `l4_public_url` (default `https://<slug>.pmoves.ai` when l4_public is true)

**Output:** the path to the generated file + the validation result.

**Note:** `scaffold` does NOT mark the app as promoted; new entries
land in `user/` by default. The operator runs `promote` after review.

### `validate`

Validate one or all entries against the schema. Useful as a pre-commit
hook or a CI check.

**Inputs:**
- `--slug <slug>` (optional; default validates all)

**Output:** per-entry pass/fail + the first validation error if any.

**Example:**
```bash
$ pmoves registry validate
12/12 entries valid
```

### `promote`

Copy a `user/<slug>.yaml` to `curated/<slug>.yaml` after operator
review. The `user/` copy is left in place (the operator can delete
it manually after confirming the curated copy is correct). The
promoted copy gets a `notes` update: `"promoted from user/ on
<date> by <operator>"`.

**Inputs:**
- `--slug <slug>` (required)
- `--operator <handle>` (default: `pmoves`)

**Output:** the path to the promoted file + the diff summary.

**Guard:** refuses to overwrite an existing curated entry without
`--force`. The operator should review + delete the curated copy
manually if the force flag is needed.

### `reconcile`

Proxy to the mesh_exposure service. Compute the desired state
(headscale ACL ports, cloudflared tunnel ingress, DNS records)
from the registry, and (with operator approval) apply the diff.

**Inputs:**
- `--action` (default: `plan`): one of `plan | preview | apply`
- `--slug <slug>` (required for `preview`; ignored otherwise)

**Output:** the reconcile plan as JSON (the same shape as
`GET /v1/reconcile/plan` on the mesh_exposure service).

**Guard:** `apply` requires `--confirm` and the
`X-PMOVES-Meshbus-Token` env var to be set. Without the token the
service returns 503.

## MCP integration

The gepeto-wrapper surface is also exposed as MCP tools when the
PMOVES MCP server is configured. Add the following to
`pmoves/config/mcp/{hostinger,cloudflare}.yaml`-style config or the
PMOVES MCP catalog:

```yaml
mcp_tools:
  - name: pmoves_registry_list
    description: "List all Pinokio app entries in the PMOVES registry"
  - name: pmoves_registry_show
    description: "Show one Pinokio app's full registry entry"
    inputs:
      - name: slug
        type: string
        required: true
  - name: pmoves_registry_scaffold
    description: "Scaffold a new Pinokio app entry in user/ from operator inputs"
  - name: pmoves_registry_validate
    description: "Validate registry entries against the slice-4 schema"
  - name: pmoves_registry_promote
    description: "Promote a user/ entry to curated/ after operator review"
    inputs:
      - name: slug
        type: string
        required: true
  - name: pmoves_registry_reconcile
    description: "Compute (or apply) the live-fleet reconcile plan from the registry"
    inputs:
      - name: action
        type: string
        required: false
        default: plan
```

## Schema reference

`pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json` is
the source of truth. The validator (`pmoves/tools/pinokio_apps/discover.py`)
is the reference implementation. The slice-4 deep-dive report
(`pmoves/docs/research/creator-collab-slice-4-deep-dive-2026-07-28.md`)
documents the design rationale + the 4-layer network_exposure contract.

## Cross-references

- `pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md` — the slice-4 spec doc
- `pmoves/docs/architecture/PINOKIO8_APP_HOSTING_SPEC.md` — the pre-existing
  Pinokio 8 app-hosting spec that defines the ADOPT/COMPOSE/DEFER stance
- `pmoves/configs/tac_trees/{pinokio-venv,pmoves-container,tailnet-mesh,public-tunnel}.tac.yaml`
  — the 4 layer-TAC trees that audit reachability per layer
- `pmoves/services/mesh_exposure/` — the writer that keeps the live
  fleet in sync with the registry (the `reconcile` action)
- `pmoves/services/pinokio_bridge/` — the slice-2 surface that reads
  Pinokio's on-disk state (the read-side; gepeto-wrapper is the
  PMOVES-side mirror)
- `pmoves/skills/pinokio-bridge-skill/SKILL.md` — the slice-2 skill
  that wraps the bridge (the companion for Pinokio live-state reads)
