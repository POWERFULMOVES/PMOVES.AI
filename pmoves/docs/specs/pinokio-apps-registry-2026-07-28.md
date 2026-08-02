# Pinokio Apps Registry — Slice 4 Spec

> **Status:** Slice 4 SHIPPED on `feat/creator-collab-lane`. 4/7 slices
> complete. Companion to the pre-existing
> `pmoves/docs/architecture/PINOKIO8_APP_HOSTING_SPEC.md` (the ADOPT /
> COMPOSE / DEFER stance) and the slice-4 deep-dive report
> `pmoves/docs/research/creator-collab-slice-4-deep-dive-2026-07-28.md`.

## 1. Why slice 4

The slice-1 review-iter-2 cycle-2 review of PR #2264 explicitly flagged
that the `pinokio_app_refs` field in `room.manifest.v1` is meaningless
without the catalog backing it. Slice 1 + 2 + 3 shipped:
- (1) the schema field + first consumer (`creator-studio.room.collab.json`)
- (2) the pinokio_bridge service that reads Pinokio's on-disk state
- (3) the NATS pipeline for runtime events (5 new subjects)

What was missing: **the catalog itself** — a structured registry that
the bridge reads, the mesh exposes, the dashboard renders, and the
helpdesk-skill (slice 6) queries. Slice 4 ships that catalog, the
discovery tool that populates it, and the mesh_exposure service that
keeps the live fleet in sync.

The operator's new directive in this turn also added **network
exposure**: each entry declares how the app is reachable across the 4
network layers (L1 venv, L2 same-host container, L3 tailnet mesh, L4
public website via kvm2 + Cloudflare/Hostinger). This extends the
pre-existing ADOPT/COMPOSE/DEFER stance to a fourth layer.

## 2. The 4-layer reachability model

```
L1: Pinokio venv        Same host, same process space
                        (D:\pinokio\api\<slug>\venv\)

L2: PMOVES container    Same host as the Pinokio venv
(same host)              http://host.docker.internal:<port>

L3: Tailscale mesh      Different host on the headscale tailnet
(different host)         http://<slug>.<tailscale_host>.ts.pmoves.net:<port>
                        (WireGuard-encrypted; ACL-gated)

L4: Public website      kvm2's Cloudflare-Tunnel + Tailscale-Funnel +
(via kvm2 + cloudflare + Hostinger-managed DNS
 hostinger)              https://<app>.pmoves.ai
```

The mesh_exposure service owns the L3 + L4 writes. L1 + L2 are
host-local and don't need a reconcile service.

## 3. Registry schema

`pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json` —
Draft 2020-12, `additionalProperties: false` at every level.

### Top-level required fields
- `schema_version` (semver)
- `slug` (matches `~/pinokio/api/<slug>/`)
- `title` (display name)
- `description` (one paragraph)
- `owner` (pinokio | docker | docker-compose | nvidia | cloudflared | tailscale | pmoves)
- `version_seen` (free-form version string)
- `runtime` (9 sub-fields — see below)
- `endpoints` (primary + alt)
- `pinokio_skill_ref` (P8 managed skill slug, or null)
- `network_exposure` (4-layer ladder — see below)

### `runtime` (9 sub-fields, all required)
- `launcher_script` (e.g. start.js)
- `autostart` (bool — per the slice-1 P1 4-quadrant matrix)
- `gpu_required` (bool)
- `min_vram_mb` (integer ≥ 0; 0 when gpu_required=false)
- `gpu_arch` (array of sm_* / gfx*; empty when gpu_required=false)
- `gpu_reservation_mb` (integer ≥ 0)
- `gpu_reservation_mode` (concurrent | exclusive)
- `dependencies` (array of slugs; intra-node launch order)
- `requires_hf_login` (bool — gates the launch on Pinokio 8's hf.login)

### `endpoints`
- `primary.port` (0 = dynamic, resolved via pinokio_bridge)
- `primary.protocol` (http | https | ws | wss | grpc | tcp)
- `primary.health` (path or null)
- `alt[]` (additional service ports)

### `network_exposure` (4 layers, all required)
- `l1_venv.reachable` (bool)
- `l2_container_same_host.{reachable, address}`
- `l3_mesh.{reachable, address, headscale_acl_ports, tags_required}`
- `l4_public.{reachable, tunnel, dns_record, public_url}`

### `metadata` (the only free-form escape hatch)
- Constrained to `{string, number, boolean, null}` so YAML stays diffable.

## 4. The 12 curated entries

`pmoves/configs/pinokio-apps/curated/*.yaml`:

| Slug | VRAM | Mode | Autostart | L4 |
|---|---|---|---|---|
| comfyui-desktop | 16GB | concurrent | true | **true** (canonical L4 example) |
| ace-step | 8GB | concurrent | true | false |
| wan | 24GB | exclusive | **false** (on-demand) | false |
| lightonocr-2-1b | 2GB | concurrent | true | false |
| ultimate-tts-studio | 6GB | concurrent | true | **true** (public TTS) |
| qwen3-tts | 4GB | concurrent | false | false |
| vibevoice-realtime | 4GB | concurrent | false | false |
| voxforge-pro | 4GB | concurrent | false | false |
| n8n | 0GB | concurrent | true | false |
| sillytavern | 4GB | concurrent | false | false |
| unsloth | 24GB | exclusive | **false** (on-demand) | false |
| customokio | 0GB | concurrent | false | false |

The 2 L4-public entries are the canonical examples. The rest are
mesh-only or host-only. The discovery tool (`discover.py`) populates
`user/` for any new installs the operator adds.

## 5. The 4 layer-TAC trees

`pmoves/configs/tac_trees/{pinokio-venv,pmoves-container,tailnet-mesh,public-tunnel}.tac.yaml`:

| Tree | Layer | Audits |
|---|---|---|
| pinokio-venv.tac.yaml | L1 | Registry <-> disk agreement, GPU detect, hf.login, Miniforge runtime, registry freshness |
| pmoves-container.tac.yaml | L2 | host.docker.internal resolution, port reachability, bridge reachable from container, network policing |
| tailnet-mesh.tac.yaml | L3 | headscale up, ACL ports, FQDN resolve, bridge-on-Pinokio-host, mesh_exposure writer |
| public-tunnel.tac.yaml | L4 | kvm2 up, tunnel config, DNS records, public URL healthz + TLS, mesh_exposure L4 writer |

Each tree has 4-5 phases. The L3 + L4 trees have a "mesh_exposure
writer" loop-close check at the end (Phase 5) that asserts the
service ran within the last 24h — if it didn't, the audit silently
goes stale.

## 6. mesh_exposure service

`pmoves/services/mesh_exposure/` — the writer that keeps the live
fleet in sync with the registry.

**Endpoints:**
- `GET /healthz` — service + registry + writes state + last-reconcile timestamps
- `GET /v1/registry?slug=<slug>` — list all (or specific)
- `GET /v1/reconcile/plan` — desired vs current state as JSON diff
- `POST /v1/reconcile/apply` — apply the plan (fail-closed token + confirm)
- `GET /v1/reconcile/status` — last run + last change + last plan + last apply
- `POST /v1/reconcile/preview?slug=<slug>` — dry-run for a single app

**Auth model:** X-PMOVES-Meshbus-Token (fail-closed, 503 if env unset).
Different from X-PMOVES-Bridge-Token (pinokio_bridge) and
X-PMOVES-NatsBus-Token (nats_event_bus) — tokens are scoped per service.

**Writer mode:** MESH_EXPOSURE_WRITER_MODE=apply|noop. Default noop
(read-only use; the operator's runbook applies the diff). The service
exposes the plan as JSON regardless; production wires SSH-to-kvm2 +
Cloudflare + Hostinger APIs per the slice-4 runbook.

**Host convention:** z890 (infra-coordinator) — has direct file access
to `pmoves/config/headscale/acl.yaml` + SSH reach to kvm2.

## 7. discovery tool

`pmoves/tools/pinokio_apps/discover.py` — CLI that walks
`~/pinokio/api/` (or `D:\pinokio\api\` on Windows) and generates
`pmoves/configs/pinokio-apps/user/<slug>.yaml` for every app that
doesn't already have a curated entry.

- Reads `pinokio.js` (or `pinokio.json`/`pinokio.yml`); tolerates
  JS-style comments + trailing commas
- Falls back to `version.json` (or `package.json`) for the version
- Skips entries already in `curated/` or `user/` — never overwrites
- Validates every generated entry against the slice-4 schema
  before writing; bad entries are reported, not written
- Prints a summary + exits non-zero on any validation error (so
  the CI cron + the operator's runbook both notice)

Promotion workflow: `discover.py` writes to `user/` by default.
The operator reviews the YAML, corrects wrong fields (e.g.
`runtime.gpu_required` may default to `false` if the manifest
doesn't declare it), then uses the `gepeto-wrapper` skill's `promote`
action to copy to `curated/`.

## 8. gepeto-wrapper skill

`pmoves/skills/gepeto-wrapper-skill/SKILL.md` — the PMOVES-side mirror
of Pinokio 8's built-in gepeto skill. Operates on the registry
surface (not the on-disk launchers). 6 actions:
- `list_apps` — list curated + user entries
- `show_app` — show one entry's full YAML
- `scaffold` — interactive entry creation
- `validate` — schema check (pre-commit / CI hook)
- `promote` — `user/` → `curated/`
- `reconcile` — proxy to mesh_exposure

The skill surfaces an MCP tool set so PMOVES agents get the same
surface without needing to shell out to the discover tool.

## 9. Stance on the pre-existing ADOPT/COMPOSE/DEFER map

Per the pre-existing `pmoves/docs/architecture/PINOKIO8_APP_HOSTING_SPEC.md`:

| Feature | Stance | Slice-4 surface |
|---|---|---|
| GPU template vars | ADOPT | runtime.{gpu_required, min_vram_mb, gpu_arch} |
| Home Server | ADOPT | (per-node local; not in slice 4) |
| Phone Access | COMPOSE | network_exposure.l1_venv (LAN-only) |
| Orchestration | COMPOSE | runtime.dependencies (intra-node launch order) |
| Autolaunch | ADOPT | runtime.autostart |
| Miniforge runtime | ADOPT | (env owns it; not in slice 4 schema) |
| `hf.login` | ADOPT | runtime.requires_hf_login |
| Plugin actions as JS functions | ADOPT | gepeto-wrapper (scaffold action computes install state) |
| Public egress via Cloudflare-Tunnel | **NEW ADOPT** | network_exposure.l4_public + mesh_exposure service |
| Tailscale-Funnel egress | **NEW ADOPT** | network_exposure.l4_public.tunnel |
| Hostinger DNS management | **NEW ADOPT** | network_exposure.l4_public.dns_record + mesh_exposure DNS API |
| mesh_exposure reconcile service | **NEW ADOPT** | full service in slice 4 (Q3 operator pick) |

The slice-4 design respects the pre-existing boundary: **Pinokio 8 is
the per-node home-lab button, Tailscale mesh is the cross-network
layer, P7 is the cross-node orchestrator, and now the public-website
tier (kvm2 + Cloudflare/Hostinger) is the new layer above the mesh.**

## 10. Cross-cutting follow-ups (separate lanes)

- `pmoves-pinokio` fork sync to P8 (v1-era stale; carried from slice 2)
- NATS broker deployment (slice 3 schemas are ready; deployment is separate)
- comfy-watcher / comfyui publisher wiring (slice 3 subjects; implementation is separate)
- `z890-coordinator.yaml` profile cache refresh (the `gpu: type: none` is stale; z890 has 3090ti)
- persona-room hygiene (em-dash catalog drift; out of scope per slice-1 review-iter-2)
- slice-4 runbook: `pmoves/docs/operations/MESH_EXPOSURE_RUNBOOK.md` (to be written before the apply path is exercised in production; documents the SSH-to-kvm2 + Cloudflare + Hostinger API calls the mesh_exposure service skips by default)

## 11. Test surface

- `pmoves/services/mesh_exposure/tests/` — 29 cases
- `pmoves/tools/pinokio_apps/tests/` — 19 cases
- 158/158 total across 6 services (mesh_exposure 29 + pinokio_apps 19 + nats_event_bus 20 + pinokio_bridge 28 + p7 46 + a2ui 16)
- 10/11 manifests OK (1 pre-existing `persona.room.livingdoc` em-dash failure out of scope)

No live NATS, Cloudflare, Hostinger, or kvm2 access. Injected reader/
writer callables + `tmp_path` fixtures keep the tests offline.

## 12. Files added (this slice)

```
pmoves/configs/pinokio-apps/
  schema/pinokio-app.v1.schema.json
  curated/{comfyui-desktop,ace-step,wan,lightonocr-2-1b,
          ultimate-tts-studio,qwen3-tts,vibevoice-realtime,
          voxforge-pro,n8n,sillytavern,unsloth,customokio}.yaml
  user/  (empty; discover.py populates)
pmoves/configs/tac_trees/
  pinokio-venv.tac.yaml
  pmoves-container.tac.yaml
  tailnet-mesh.tac.yaml
  public-tunnel.tac.yaml
pmoves/services/mesh_exposure/
  __init__.py, app.py, state.py, Dockerfile, requirements.txt,
  README.md, tests/test_app.py
pmoves/skills/gepeto-wrapper-skill/SKILL.md
pmoves/tools/pinokio_apps/
  discover.py, README.md, tests/test_discover.py
pmoves/docs/research/creator-collab-slice-4-deep-dive-2026-07-28.md
pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md  (this file)
pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md                  (slice 4 CLAIM)
pmoves/tools/creator-collab-state.json                  (ship_count: 3 -> 4)
```

3 stacked commits (P1, functional, docs) per the creator-collab
workflow.
