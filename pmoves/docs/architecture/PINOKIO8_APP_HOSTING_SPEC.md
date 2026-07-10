# Pinokio 8 for PMOVES App Hosting — Review-to-Spec

> **Status:** Draft spec / ADR — 2026-07-10 · Author: 4090-claude
> **Decision sought:** How (and how far) PMOVES.AI adopts Pinokio 8.0.0 as the
> per-node "home-lab button" for app hosting, and where it composes with vs.
> defers to existing PMOVES layers (Tailscale mesh, P7 stage manager).
> **TL;DR:** Adopt Pinokio 8 as the **per-node local app-hosting + GPU-aware
> runtime** layer. Keep the **Tailscale mesh** as the cross-network/pilot layer
> (Pinokio 8 phone access is LAN-only). Keep **P7** as the cross-node room
> orchestrator (Pinokio 8 orchestration is single-node dependency sequencing).
> Biggest immediate win: **GPU template variables** solve fleet wheel-routing.

## 1. Why this review

The operator flagged Pinokio 8 as "a literal home-lab button, PBNJ-plus — solves
our app-hosting problem." This spec reviews what Pinokio 8.0.0 *actually* ships
(verified against the [8.0.0 release notes](https://cocktailpeanutlabs.github.io/p8/),
2026-07-10) and maps each feature to a PMOVES app-hosting need, marking each as
**Adopt**, **Compose**, or **Defer** so we build the right thing rather than
duplicating a layer we already have.

PMOVES already has three layers this touches, so the review is fundamentally
about **boundaries**, not greenfield:

| Existing PMOVES layer | Role | Pinokio 8 overlap |
|---|---|---|
| **P7** (Pinokio 7 stage manager) | room-aware, cross-node orchestration (rehearsal→live→review→archive) | Pinokio 8 adds *single-node* app-dependency sequencing |
| **Tailscale mesh** (Serve/Funnel/exit-nodes) | cross-network identity, remote/pilot access, egress | Pinokio 8 phone access is *LAN-only* |
| **Compose profiles / rooms** | service definition + bring-up | Pinokio 8 is a *1-click* launcher over the same apps |

## 2. Pinokio 8.0.0 features (verified) → PMOVES mapping

### 2.1 GPU template variables — **ADOPT (highest value)**

Pinokio 8 exposes hardware as script template vars:

| Var | Value | PMOVES relevance |
|---|---|---|
| `{{gpu}}` | `nvidia` / `amd` / `apple` / `none` | fleet is mixed-vendor |
| `{{gpu_model}}` | e.g. `nvidia rtx a4500` | node identity |
| `{{gpu_target}}` | `sm_*` (NVIDIA) / `gfx*` (AMD) | **B850 = `gfx1201` (RDNA4)**, SPARK/5090 = `sm_*` |
| `{{gpu_driver}}` | driver version string | wheel gating |
| `{{vram}}` | integer GB | **the exact fact `host_affinity.min_vram_mb` gates on** |

Example from the release notes — conditional wheel routing:

```js
"when": "{{gpu === 'nvidia' && Number.parseFloat(gpu_driver || '0') >= 580}}"
// → route to cu130 wheels on newer drivers
```

**Why this is the top win.** The PMOVES fleet is deliberately heterogeneous —
NVIDIA `sm_*` (SPARK ARM64-CUDA, 5090, 4090), AMD RDNA4 `gfx1201` (B850
"Knuckles", which needs the `tlee933/llama.cpp-rdna4-gfx1201` HIP fork because
stock Ollama lacks gfx1201 kernels). Today that wheel/kernel routing is manual
and error-prone. Pinokio 8's `{{gpu_target}}` + `{{vram}}` let a single launcher
script self-route the correct wheel per node.

**Direct tie-in to the voice work (#2037):** the new
`tts-engine-capabilities.yaml` `host_affinity` table encodes `requires: cuda|rocm`
+ `min_vram_mb` per engine. Pinokio 8's `{{gpu_target}}` (`sm_*` vs `gfx*`) and
`{{vram}}` are the *runtime* half of that same fact. A Pinokio 8 launcher for a
voice engine can read `{{vram}}` and refuse to start on an under-provisioned node,
exactly matching the config-level affinity we just shipped. **These are two halves
of one impedance-matching story.**

### 2.2 Home Server — **ADOPT (per-node local hosting)**

1-click serve of an app "across a network" from an app row or a management page.
This *is* the "home-lab button" — the right shape for letting a non-developer
operator stand up a PMOVES room/service on a node without compose incantations.

**Boundary:** Home Server serves on the **local network**. It is the *local*
hosting primitive; it does **not** replace the Tailscale mesh for cross-site /
pilot / remote access (see 2.3). Adopt it as the on-node launcher; keep compose
profiles as the source-of-truth service definitions Pinokio wraps.

### 2.3 Phone Access — **COMPOSE (mesh remains the WAN layer)**

Release notes, verbatim: *"Phone access is now part of the shared sidebar. The
Phone button opens a focused local-access panel with a QR code and local URL"* and
**"setup is gated when the local network router is not ready."** Access is
**LAN-only; no internet tunnel** is provided for phone access.

**This is the key architectural finding.** Pinokio 8 phone access is a
same-LAN convenience (scan QR → open the app on your phone on the same WiFi). It
does **not** solve the PMOVES pilot use-case, which is explicitly cross-network
(the operator travelling in PA reaching Fordham-Hill nodes; residents reaching a
community node). PMOVES already solves that with the **Tailscale mesh** —
`tailscale serve` (tailnet-internal HTTPS) and `tailscale funnel` (public 443)
per the exit-node runbook.

**Composition (not competition), mirroring the Haven/Reticulum finding:**

```
Phone on same WiFi as node   →  Pinokio 8 Phone Access (QR + local URL)   [LAN]
Phone anywhere on the tailnet →  tailscale serve  https://<node>.ts.net    [mesh, private]
Public pilot / resident       →  tailscale funnel https://<node>.ts.net    [mesh, public 443]
```

Adopt Pinokio 8 phone access for the local dev/demo path; **route all
cross-network access through the mesh**, never through a Pinokio-exposed port.
(Consistent with the privacy-mesh-only stance: mesh + Docker, never Windows LAN
sharing.)

### 2.4 Orchestration / app dependencies — **COMPOSE (P7 stays the cross-node brain)**

Pinokio 8: apps declare `dependencies` (required apps) that launch first, resolved
**recursively** (A→B→{C,D} launches C,D,B,A), for both autolaunch and manual
launch — a **single-node** dependency DAG.

**Boundary vs P7.** P7 is the *room-aware, cross-node* stage manager (selects
rooms, loads suits, manages rehearsal→live→review→archive, control plane on NATS
`p7.nats.launch`/`p7.nats.session`). Pinokio 8 orchestration is a lighter,
single-node launch-ordering feature. They compose:

- **Pinokio 8**: order the app stack *within* a node (e.g. start the model runner
  before the service that calls it).
- **P7**: orchestrate *across* nodes and lifecycle stages (which room runs where,
  cross-node NATS coordination).

Do **not** try to replace P7 with Pinokio 8 orchestration; use Pinokio 8's
dependency block only for intra-node launch order in the launcher scripts P7 (or
the operator) invokes.

### 2.5 Autolaunch — **ADOPT (per-node service auto-start)**

First-class `/autolaunch` page; any app auto-launches on Pinokio start, 1-click,
with a persisted script selection + separate toggle. Useful for the "always-on"
voice/announcer roles (`service_runners.always_on` in `tts-engine-capabilities.yaml`)
and for a node's baseline room. Adopt for the always-on tier; keep on-demand
services manual/P7-triggered.

### 2.6 Miniforge / conda-forge runtime — **ADOPT (aligns with OSS-only policy)**

Managed runtime moved Miniconda → **Miniforge** (conda-forge-first). This aligns
with the PMOVES open-source-only rule (conda-forge is community/OSS vs Anaconda's
commercial defaults channel). No action beyond noting it removes a licensing
foot-gun for managed Python envs. Bundled: Conda 26.3.2, Python 3.10.20 (SSL
fixes), Node 24.18.0, FFmpeg 8.1.2.

## 3. Decision — adoption stance

| Feature | Stance | PMOVES boundary |
|---|---|---|
| GPU template vars | **ADOPT** | wheel/kernel self-routing; runtime half of `host_affinity` |
| Home Server | **ADOPT** | on-node local hosting; compose profiles stay source-of-truth |
| Phone Access | **COMPOSE** | LAN convenience only; **mesh = all cross-network** |
| Orchestration | **COMPOSE** | intra-node launch order only; **P7 = cross-node** |
| Autolaunch | **ADOPT** | always-on tier per node |
| Miniforge runtime | **ADOPT** | OSS-policy aligned; no action |

**One-line architecture:** *Pinokio 8 is the per-node home-lab button (local
hosting + GPU-aware runtime + autolaunch); the Tailscale mesh is the cross-network
layer; P7 is the cross-node orchestrator. They stack; none replaces another.*

## 4. Proposed adoption plan (phased)

1. **Phase 0 — GPU-var launcher spike (highest ROI).** Write one Pinokio 8
   launcher for an existing PMOVES service that must run on mixed hardware — the
   **kokoro-tts CPU unit** (`services/kokoro-tts`, PR #2024) is the ideal first
   target: it's CPU-only, so `{{gpu}} === 'none'` / low `{{vram}}` nodes (the KVMs)
   are valid, exactly matching its `host_affinity` row. Validates the home-lab
   button on the cheapest node and proves the GPU-var → `host_affinity` bridge.
   Use the `gepeto` skill; destination resolved via `PINOKIO_HOME`.
2. **Phase 1 — mesh seam.** Document + template the `tailscale serve`/`funnel`
   wrapping so a Pinokio-hosted app is reachable over the mesh, not a raw LAN port.
   (Extends `TAILSCALE_EXIT_NODE_RUNBOOK.md` §Serve/Funnel.)
3. **Phase 2 — GPU-var wheel routing for the real pain case.** Apply
   `{{gpu_target}}` conditional wheel selection to the **B850 RDNA4 `gfx1201`**
   path (the llama.cpp-HIP fork) and the SPARK ARM64-CUDA path — the two nodes
   where manual wheel routing hurts most.
4. **Phase 3 — autolaunch the always-on tier.** Wire `/autolaunch` for each node's
   baseline room + always-on voice roles.
5. **Phase 4 — P7 ↔ Pinokio 8 handshake.** Define how P7 invokes Pinokio 8
   launchers (intra-node dependency block) while retaining cross-node control on
   NATS. (Design only; do not collapse the layers.)

## 5. Risks / open questions

- **Windows/WSL2 nodes** (Z890, 4090): confirm Pinokio 8 GPU detection reports the
  right `{{gpu_target}}` under WSL2 (the 4090 laptop has "no heavy VRAM budget" —
  `{{vram}}` gating should keep heavy engines off it automatically).
- **Z890 GPU verified 2026-07-10 as RTX 3090 Ti 24GB** (on-node `nvidia-smi`) —
  the runner-topology.md "GTX 1650 4GB" line was a *different* node and is wrong.
  This is exactly the case that proves the GPU-var thesis: a doc line mis-stated the
  hardware and would have mis-routed voice; Pinokio 8's `{{vram}}`/`{{gpu_model}}`
  (or an on-node probe) is the source of truth. `host_affinity` (#2037) now lists
  z890 as a live 24GB CUDA fallback. Fix the stale runner-topology.md line separately.
- **AMD/ROCm coverage:** verify `{{gpu_target}} === 'gfx1201'` is detected on B850
  and that Pinokio's conda-forge base doesn't fight the ROCm 7.1 / HIP fork.
- **No internet tunnel by design:** confirmed — do not expect Pinokio 8 to provide
  remote access; that stays a mesh responsibility. Guard against anyone exposing a
  Pinokio Home Server port to the WAN directly (privacy-mesh-only).
- **Source-of-truth drift:** launchers must *wrap* compose profiles / room manifests,
  not fork them, or we get two definitions of a service.

## 6. Recommendation

**Adopt Pinokio 8 as the per-node hosting + GPU-aware runtime layer, starting with
the Phase 0 kokoro-tts launcher spike** (cheapest node, direct `host_affinity`
tie-in, lowest risk). Keep the mesh and P7 boundaries firm. The GPU template
variables alone justify adoption — they turn the fleet's heterogeneous
NVIDIA/AMD/ARM hardware from a manual wheel-routing chore into a self-routing
launcher fact, and they are the runtime complement to the `host_affinity` routing
table shipped in #2037.

## References

- Pinokio 8.0.0 release notes — https://cocktailpeanutlabs.github.io/p8/
- Pinokio releases — https://github.com/pinokiocomputer/pinokio/releases
- `pmoves/configs/tts-engine-capabilities.yaml` — `host_affinity` (#2037)
- `pmoves/docs/operations/TAILSCALE_EXIT_NODE_RUNBOOK.md` — Serve/Funnel, mesh access
- `pmoves/docs/AGENTS/AGNOTE_P7_PLAYGROUND.md` — P7 stage manager
- `.claude/context/runner-topology.md` — fleet GPU inventory (sm_* / gfx1201)
- gepeto skill — Pinokio launcher authoring (`PINOKIO_HOME` resolution)
