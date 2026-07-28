# Creator Collab Lane — Slice 4 Deep-Dive Report
## Pinokio Apps Registry + Network Exposure (mesh + public-website)

**Author:** Mavis (orchestrator, mvs_09c9b116c675418b9d8b1a48b10867dc)
**Date:** 2026-07-28
**Branch:** `slice-4-pinokio-apps-registry` (off `feat/creator-collab-lane @ 4f926ea72e`)
**Status:** Deep-dive report — held for operator signoff before any code lands.

---

## TL;DR (one-screen)

- **Scope (operator-approved):** `pmoves/configs/pinokio-apps/{curated,user}/<slug>.yaml` registry + discovery tool + gepeto wrapper **plus** a `network_exposure` schema block that lets each app declare mesh and hostinger/cloudflare public reachability.
- **Architecture stays firm:** Pinokio 8 = per-node home-lab button (per the pre-existing `pmoves/docs/architecture/PINOKIO8_APP_HOSTING_SPEC.md`); Tailscale mesh = cross-node private; **public website tier** (kvm2 Cloudflare-Tunnel + Tailscale-Funnel + Hostinger-managed DNS) = the new layer the operator asked for in this turn. They stack; none replaces another.
- **PMOVES / Pinokio exec-env gap (operator's call-out):** PMOVES services run in Docker containers; Pinokio apps run in venvs (`~/pinokio/api/<slug>/venv/`) on the host. They have different networking. The registry must declare the right way to reach each app from each environment.
- **TAC trees per environment layer (operator's "TAC around each layer"):** one TAC tree per reachability layer — `pinokio-venv.tac.yaml`, `pmoves-container.tac.yaml`, `tailnet-mesh.tac.yaml`, `public-tunnel.tac.yaml` — each audits "can a client at this layer reach the app?".
- **PMOVES-pinokio fork is v1-era stale (1 star, 0 forks) — out of scope**, separate `fleet-fork-sync` lane (carried from slice 2).
- **3 signoff questions** at the end before any code lands.

---

## 1. Why this slice

The creator-collab lane (3/7 shipped: schema + pinokio-bridge + NATS pipeline) needs the **apps registry** as the contract layer between Pinokio's on-disk state (apps/index.json, autolaunch, orchestration, managed skills) and the PMOVES-side consumers (P7 session-open, the mesh-render broker, the dashboard, the future helpdesk + room-suggest skills). The slice-1 review-iter-2 review specifically flagged that `pinokio_app_refs` is meaningless without the catalog backing it.

The operator's new directive adds **mesh reachability + public-website exposure** (via the existing kvm2 exit-proxy Cloudflare-Tunnel + Tailscale-Funnel + Hostinger-managed DNS) to that registry's scope. The operator also flagged the PMOVES/Pinokio exec-env gap (Docker vs venv) and asked for TAC trees per environment layer so future agent work has a map.

The slice-2 deep-dive + the pre-existing `PINOKIO8_APP_HOSTING_SPEC.md` already establish the adoption stance (ADOPT/COMPOSE/DEFER); this slice builds the contract + tooling on top of that stance.

## 2. Pinokio 8 surfaces (re-confirmed from upstream docs)

| Surface | Stance (per pre-existing spec) | Slice 4 surface use |
|---|---|---|
| GPU template vars (`{{gpu}}`, `{{gpu_model}}`, `{{gpu_target}}`, `{{gpu_driver}}`, `{{vram}}`, `{{gpus}}`) | **ADOPT** | Registry entries carry `runtime.gpu_required: bool` + `min_vram_mb: int` (matches slice 1's `pinokio_app_refs.gpu_reservation_mb`). P8 launcher can self-route wheel/kernel per node. |
| Autolaunch (per-app, /autolaunch page, dependency-aware) | **ADOPT** | Registry entries carry `runtime.autostart: bool` (already in slice 1) + `dependencies: [slug]` (NEW in slice 4). The bridge service's `/v1/autolaunch` already mirrors Pinokio's state. |
| Orchestration (recursive dependencies, A→B→{C,D}) | **COMPOSE** | Registry entries can declare `dependencies: [slug]` for intra-node launch order. P7 still owns cross-node orchestration. |
| Managed skills (library + sync targets + ON/OFF, built-in `pinokio` + `gepeto`) | **ADOPT** | Registry entries declare `pinokio_skill_ref: slug` when an app is a P8-managed skill. The bridge service's `/v1/skills` already mirrors state. |
| Structured `shell.run` argv (no raw shell, multi-line via `PINOKIO_ARG_*` env) | **ADOPT** | Already enforced in pinokio_bridge launch endpoint (slice 2 — `subprocess.Popen([...])`, never `shell=True`). |
| `hf.login` (native Hugging Face device auth) | **ADOPT** (for HF apps only) | NEW in slice 4: registry entries declare `runtime.requires_hf_login: bool` so the launch wrapper knows to surface the native login modal first. |
| Home Server (1-click LAN serve) | **ADOPT** (per-node local) | Out of slice 4 registry scope — lives in Pinokio's own UI. Registry is the contract, not the launcher. |
| Phone Access (LAN-only, no internet tunnel) | **COMPOSE** (LAN only; mesh for cross-network) | NEW in slice 4: registry entries declare `network_exposure.phone_lan: bool` (off by default; only enabled for apps that benefit from same-WiFi phone access). |
| Plugin actions as JS functions (NEW since slice 2) | **ADOPT** | The gepeto wrapper (slice 4 functional) can compute install/update actions from current registry state instead of static arrays. |
| Native Login — GitHub GCM (NEW) | note only | Not relevant to slice 4. |
| Process Monitor (per-app live resource tracking, NEW) | note only | Pinokio 8 shows disk/ram/cpu/vram per app row. Not relevant to slice 4. |
| Miniforge runtime (conda-forge-first, OSS-aligned) | **ADOPT** | Note in registry doc — Pinokio 8 uses Miniforge 26.3.2 / Python 3.10.20 / Node 24.18. The registry should NOT specify venv manager (Pinokio owns it). |
| Homebrew / ssl-cache / etc. | note only | Pinokio-side concerns. |
| Phone View / mobile Dev mode | note only | Pinokio-side concerns. |

**Two NEW since slice 2:** `hf.login` (apps declare it; PMOVES wrapper respects the native modal) and Plugin actions as JS functions (gepeto wrapper is the natural consumer).

## 3. The 4 reachability layers (operator's "TAC around each layer")

The operator's call-out: **Pinokio runs in venvs, not Docker. PMOVES runs in containers. They have different networking.** Each app must be reachable from four classes of consumer:

```
Client layer            How it reaches the app
────────────────────────────────────────────────────────────────────
L1: Pinokio venv        Same host, same process space, or scripts in
                        D:\pinokio\api\<slug>\venv\ call each other
                        (e.g. comfyui calls a model loader).

L2: PMOVES container    Same host, Docker bridge network. Talks to the
(same host as L1)       host's localhost via host.docker.internal:<port>
                        (Linux) or host.docker.internal + Docker for
                        Windows. Container hostname != host hostname.

L3: PMOVES container    Different host. Talks to <node>.ts.pmoves.net
(different host)         over the headscale tailnet. WireGuard encrypted.
                        ACL gates which ports each group can reach.

L4: Public internet     Hostinger-managed DNS (e.g. <app>.pmoves.ai
(via hostinger +         via Cloudflare DNS, or <app>.<custom-domain>
cloudflare)              via Hostinger DNS). Routed through kvm2's
                        Cloudflare-Tunnel + Tailscale-Funnel. Public
                        443 + TLS termination at the tunnel.
```

The existing `PINOKIO8_APP_HOSTING_SPEC.md` covers L1 (Home Server) + L3 (mesh); the slice 4 design extends it to L2 + L4.

**Why this matters in practice:** P7's session-open handler, the future helpdesk-skill, the dashboard, and Fordham's resident-side requests all sit at a different layer than where the Pinokio app runs. The registry has to declare the right address per layer so each consumer knows what to dial.

## 4. Existing fleet topology (per `pmoves/configs/pinokio-network-inventory.yaml` + `pmoves/config/operator_nodes.yaml` + `pmoves/config/headscale/{config,acl}.yaml`)

| Node | Tailscale hostname | Role | GPU | Pinokio LWW | Tag |
|---|---|---|---|---|---|
| POWERFULMOVES | powerfulmoves-1 | primary-gpu-tts | RTX 5090 32GB | **true** | (default) |
| pmoves-z890 | pmoves-z890 | infra-coordinator | RTX 3090ti 24GB (stale profile says none — corrected) | **true** | (default) |
| pmoves-laptop | pmoves-laptop | mobile-relay | RTX 4090 Laptop 16GB | false (consumer) | (default) |
| pmoves-dgx-spark | pmoves-dgx-spark | gpu-inference | GB10 Blackwell 128GB | false | tag:gpu |
| kvm2 | kvm2 | exit-proxy | — | false | **tag:exit** (Cloudflare-Tunnel :7844 + Tailscale-Funnel) |
| kvm4-1 | kvm4-1 | api-gateway | — | false | tag:pmoves |
| kvm4-2 | kvm4-2 | data-storage | — | false | tag:pmoves |
| jetson-orin | jetson-orin | edge-ai | Edge CUDA | false | tag:lab |

**Headscale mesh:** self-hosted at `headscale.pmoves.local:8096`, base domain `ts.pmoves.net`, IP range `100.64.0.0/10`, deny-by-default ACL with tag-level + group-level + port-scoped rules. `tag:exit` is the only auto-approved exit node. Admin group has unrestricted access; user group is port-scoped to infrastructure.

**Public egress:** kvm2 is the only exit-proxy. Cloudflare-Tunnel listens on :7844 (cloudflared) + Tailscale-Funnel (dynamic port) provide the public 443 path. The mcp/cloudflare.yaml + mcp/hostinger.yaml configs already declare the operator credentials for tunnel creation + VPS provisioning — slice 4 reads from these, doesn't redeclare.

**Pinokio apps installed on 5090 (22 total per slice 2 survey):** comfyui-desktop, ace-step, wan, ultimate-tts-studio, qwen3-tts, vibevoice-realtime, voxforge-pro, n8n, sillytavern, unsloth, customokio, heartmula-studio, clawdbot, discord-id-bypass-tool, cropper, hermes-agent, hermes-mod, Qwen3-TTS-Pinokio, SongGeneration-Studio, Ultimate-TTS-Studio-SUP3R-Edition-Pinokio, voicebox, VoxForge-Pro, lightonocr-2-1b. The first 12 of these are the slice-4 curated set (slice-1 review-iter-2 reference list).

**PMOVES-pinokio fork state:** `POWERFULMOVES/PMOVES-pinokio` (1 star, 0 forks, fork of pinokiocomputer/pinokio). Description: "AI Browser". The fork is v1-era — the README documents Pinokio's own v1 launchers/venv/security model, not any PMOVES-specific P8 work. The pinokio_bridge service (slice 2) talks to the *running* P8 desktop, not to this fork. Out of slice 4 scope; separate `fleet-fork-sync` lane.

## 5. Registry schema design (with `network_exposure` block)

`pmoves/configs/pinokio-apps/curated/<slug>.yaml` — one file per app, validated against `pmoves/configs/pinokio-apps/schema/pinokio-app.v1.schema.json`.

```yaml
# Example: comfyui-desktop.yaml (the canonical first entry)
schema_version: "1.0.0"
slug: comfyui-desktop
title: "ComfyUI Desktop"
description: "Node-based Stable Diffusion / SDXL / Flux workflow runner (Gradio)"
owner: pinokio
version_seen: "0.3.41"

runtime:
  # venv_manager owned by Pinokio (Miniforge 26.3.2 / Python 3.10.20 / Node 24.18).
  # We only declare the hardware + dependency facts P7 needs at session-open.
  launcher_script: start.js
  autostart: false                  # slice 1 P1 — wan-style big VRAM apps default off
  gpu_required: true
  min_vram_mb: 16384
  gpu_arch: [sm_120, sm_110]
  gpu_reservation_mb: 16384
  gpu_reservation_mode: concurrent  # concurrent | exclusive (slice 1 P1)
  dependencies: []                  # NEW: intra-node launch order
  requires_hf_login: true           # NEW: hf.login device auth before start

endpoints:
  primary:
    port: 8188
    protocol: http
    health: "/system_stats"
  alt: []

pinokio_skill_ref: null            # P8 managed skill slug, if any

network_exposure:                  # NEW: per-layer reachability contract
  # Every layer has a flag + concrete address when reachable.
  # None = this app is reachable only via Pinokio's own UI on the host.

  l1_venv:                          # same-host, same process space
    reachable: true                 # apps can call each other in the same venv graph

  l2_container_same_host:           # PMOVES container on the Pinokio host
    reachable: true
    address: "http://host.docker.internal:8188"  # Docker for Windows / Linux pattern

  l3_mesh:                          # other host on the tailnet
    reachable: true
    address: "http://comfyui-desktop.powerfulmoves-1.ts.pmoves.net:8188"
    # The .ts.pmoves.net suffix comes from headscale base_domain.
    # The hostname template is <slug>.<tailscale_host> (or just <tailscale_host>
    # for the headscale-assigned FQDN).
    headscale_acl_ports: [8188]     # added to pmoves/config/headscale/acl.yaml
    tags_required: []               # ACL group/tag requirements to reach

  l4_public:                        # public website via kvm2 + Cloudflare/Hostinger
    reachable: false                # opt-in; per-app decision
    tunnel: null                    # kvm2 Cloudflare-Tunnel name when reachable
    dns_record: null                # hostinger/cloudflare-managed DNS record
    public_url: null                # e.g. "https://comfyui.pmoves.ai"

notes:
  - "creator-studio.room.collab.json consumes this entry via slice 1 pinokio_app_refs"
```

**Schema enforcement:** every field with a `*` is `required` and `additionalProperties: false` on the envelope. The metadata block is `{string,number,boolean,null}` only. Versions are semver. The schema is itself a JSON Schema (Draft 2020-12) at `pinokio-apps/schema/pinokio-app.v1.schema.json`.

**Network exposure policy levels (proposed — see Q1):**
- `none` — no exposure outside the Pinokio host
- `l1+l2` — host-local only
- `l1+l2+l3` — mesh-only (default for internal apps)
- `l1+l2+l3+l4` — full public via Cloudflare-Tunnel + hostinger.cloudflare.com

## 6. Discovery tool

`pmoves/tools/pinokio_apps/discover.py` reads `D:\pinokio\api\` (or `~/pinokio/api/`) and generates `pmoves/configs/pinokio-apps/user/<slug>.yaml` entries for any installed app that doesn't already exist in `curated/`. The tool:

- Walks `~/pinokio/api/<slug>/pinokio.js` (the launcher JSON) + `~/pinokio/api/<slug>/SKILL.md` (if present) + `~/pinokio/api/<slug>/requirements.txt` (if present)
- Cross-references `~/pinokio/apps/index.json` for the official metadata (version, endpoints, health)
- Cross-references `pmoves/config/operator_nodes.yaml` for `node_id` → `tailscale_host` mapping
- Validates the generated entry against `pinokio-app.v1.schema.json` before writing
- Skips entries already in `curated/` (curated wins over user)
- Reports a summary (N new, M skipped, K validation errors) without writing on errors

This is a read-only tool — it generates `user/` entries that the operator (or gepeto wrapper) can review before promoting any to `curated/`.

## 7. gepeto wrapper

`pmoves/skills/gepeto-wrapper-skill/SKILL.md` — a PMOVES-side skill that wraps Pinokio 8's built-in `gepeto` skill for PMOVES-flavored operations:

- **List apps:** call `pmoves/configs/pinokio-apps/` (curated + user) and return the registry as a list
- **Show app details:** return a single entry's full YAML + the bridge state (from pinokio_bridge)
- **Scaffold a new app entry:** interactive — operator provides slug + title + description + runtime facts; the wrapper writes a `user/<slug>.yaml` template; the operator promotes to `curated/` after review
- **Validate against schema:** pure local — load `pinokio-app.v1.schema.json`, run Draft 2020-12, report errors
- **Promote user → curated:** copy + update the `_note` block + remove the auto-generated provenance

This is the PMOVES-side mirror of the registry surface. Pinokio's built-in `gepeto` handles launchers; ours handles the contract.

## 8. TAC trees per environment layer (operator's "TAC around each layer")

Four new TAC trees, each with the same 5-phase shape (install + autolaunch + orchestration + managed skills + GPU/VRAM) but audited at a different reachability layer:

| Tree | Path | Audits |
|---|---|---|
| `pinokio-venv.tac.yaml` | `pmoves/configs/tac_trees/` | Same-host, same-process: `D:\pinokio\api\<slug>\` resolves; `venv` activates; scripts run isolated. Companion to `pinokio-p8.tac.yaml` (slice 2) but focused on intra-host reachability. |
| `pmoves-container.tac.yaml` | new | PMOVES containers on the same host: `host.docker.internal:<port>` resolves from inside the container; the container's DNS doesn't break; the headscale-agent container can dial `<tailscale_host>:port` over the bridge. |
| `tailnet-mesh.tac.yaml` | new | Cross-host: ACL ports in `pmoves/config/headscale/acl.yaml` open for the app; `<slug>.<tailscale_host>.ts.pmoves.net` resolves via headscale DNS; the service responds on the ACL'd port. |
| `public-tunnel.tac.yaml` | new | kvm2 Cloudflare-Tunnel + Tailscale-Funnel: tunnel name + hostname + DNS record in `pmoves/config/mcp/{cloudflare,hostinger}.yaml` agree; the TLS cert is valid; the public URL reaches the mesh endpoint. |

Each tree is auditable via `pmoves/scripts/tac.py run <path>` and gates the next layer's reachability. If `pinokio-venv.tac.yaml` fails, the `pmoves-container.tac.yaml` for the same app will fail too. Cascading gates are a feature, not a bug.

The companion is the existing `networking-defense-in-depth.tac.yaml` (security posture, ACL enforcement) and `pinokio-p8.tac.yaml` (slice 2; bridge service health). Slice 4 doesn't rewrite any of those.

## 9. Out of scope (recorded, not chased in slice 4)

- **`mesh_exposure` service** (a hypothetical service that reads the registry and reconciles `cloudflared` config on kvm2 + headscale ACL ports + hostinger DNS records) — this is the runtime half of L4. The spec + schema land in slice 4; the actual reconcile code is a separate lane (the operator can decide to run it as slice 4b or as a follow-up).
- **`pmoves-pinokio` fork sync to P8** — v1-era stale (1 star, 0 forks). Carried from slice 2 as a separate `fleet-fork-sync` lane. The bridge talks to the *running* P8 desktop, not to this fork.
- **Visual evidence (Playwright screenshots)** — slice 5 (creator-studio E2E smoke). The registry + TAC trees + gepeto wrapper are headless.
- **Comfy-watcher / comfyui publishers on the slice-3 NATS subjects** — the schemas are ready, the publishers are a separate infra lane. Slice 4 just declares the registry that those consumers will read from.
- **Pre-existing failures out of lane scope:** persona.room.livingdoc em-dash catalog drift, claude-review + triage CI Bun runtime bug, stale z890-coordinator.yaml profile cache, hostinger.cloudflare.com DNS surface (read-only; not modified by slice 4).

## 10. Cross-cutting follow-ups (separate lanes, not slice 4)

- Pinokio fork sync to P8 (`fleet-fork-sync`)
- NATS broker deployment (NATS JetStream in `pmoves/config/nats/`)
- comfy-watcher publisher wiring
- `z890-coordinator.yaml` profile cache refresh
- persona-room hygiene (em-dash catalog drift)

## 11. Files to be created (preview, pending signoff)

```
pmoves/configs/pinokio-apps/
  schema/
    pinokio-app.v1.schema.json        # JSON Schema (Draft 2020-12) for the registry
  curated/                            # 12 first entries (one per known app)
    comfyui-desktop.yaml
    ace-step.yaml
    wan.yaml
    lightonocr-2-1b.yaml
    ultimate-tts-studio.yaml
    qwen3-tts.yaml
    vibevoice-realtime.yaml
    voxforge-pro.yaml
    n8n.yaml
    sillytavern.yaml
    unsloth.yaml
    customokio.yaml
  user/                               # populated by discover.py
    .gitkeep
pmoves/tools/pinokio_apps/
  discover.py                         # the discovery tool
  README.md
  tests/
    test_discover.py
pmoves/skills/gepeto-wrapper-skill/
  SKILL.md                            # the PMOVES-side gepeto wrapper
pmoves/configs/tac_trees/
  pinokio-venv.tac.yaml
  pmoves-container.tac.yaml
  tailnet-mesh.tac.yaml
  public-tunnel.tac.yaml
pmoves/docs/specs/
  pinokio-apps-registry-2026-07-28.md # the spec doc for slice 4 (extends PINOKIO8_APP_HOSTING_SPEC.md)
pmoves/docs/research/
  creator-collab-slice-4-deep-dive-2026-07-28.md   # this report
pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md            # slice 4 CLAIM entry (docs commit)
pmoves/tools/creator-collab-state.json            # ship_count: 3 -> 4, slice 4 SHIPPED
```

**Estimated size:** ~1500 lines YAML (12 curated + schema) + ~400 lines discovery tool + ~100 lines gepeto SKILL + ~300 lines × 4 TAC trees + ~200 lines spec doc + ~150 lines state + AGNOTE. ~3000 lines total. 3-stacked commits (P1 schemas + functional discovery+gepeto+12 curated + docs spec+AGNOTE+state). Comparable to slice 2's 1680 lines.

## 12. Test surface

- `pmoves/tools/pinokio_apps/tests/test_discover.py` — discovery tool tests (mock `D:\pinokio\api\` with fixture, assert output)
- `pmoves/configs/pinokio-apps/schema/` — Draft 2020-12 check on the schema
- `pmoves/configs/pinokio-apps/curated/*.yaml` — schema validation per file (12 files, 12 OK)
- `pmoves/configs/pinokio-apps/user/` — generated entries validate (test fixture)
- TAC trees — auditable via `tac.py run` (no test code per se; the trees ARE the audit)
- gepeto-wrapper SKILL.md — frontmatter + section coverage (manual review)
- **No regression target:** existing 110/110 across 4 services + 10/11 manifests (1 pre-existing failure) must hold
- `validate_room_manifests.py` — slice 1/5/6 only per workflow (not slice 4)

## 13. Signoff questions (held for operator)

The slice-2 lesson: ask the few questions that actually change the outcome. I have 3:

**Q1 — Network exposure policy levels.** The proposed 4-level ladder is `none | l1+l2 | l1+l2+l3 | l1+l2+l3+l4` (escalating). Alternative 1: keep just 3 levels (none | mesh-only | public-website) and let the schema default L1+L2 on everything (they're free). Alternative 2: keep all 4 levels but have L1+L2 be implicit (never set explicitly). Which shape do you want for the registry contract?

**Q2 — TAC tree structure.** The proposed 4 separate trees (pinokio-venv / pmoves-container / tailnet-mesh / public-tunnel). Alternative: one combined `pinokio8-networking.tac.yaml` with 4 sub-phases. Separate trees give clearer per-layer failure isolation + per-layer ownership; combined tree is easier to run in one go. Which shape?

**Q3 — `mesh_exposure` service scope.** Do you want a stub `mesh_exposure` service in slice 4 (just a skeleton that reads the registry and prints "would publish tunnel X for app Y" — no actual reconcile code) so the contract has a future home, or do you want slice 4 to ship only the contract + the operator runs the actual reconcile out-of-band? The skeleton path is ~50 lines + 1 endpoint; the contract-only path is faster but leaves a TODO. Which?

---

**End of deep-dive report. Awaiting operator signoff on Q1/Q2/Q3 before any code lands.**
