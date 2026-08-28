# fordham-room-5090

Implement what the **5090 node owns** for the `fordham.room.community` room after the
Fordham Hill fan-out: the **creator pipeline** for resident-facing materials, the
**Cloudflare dev-site / pilot dashboard** update, and the **voice-studio collaboration**
seam. The Fordham creator/voice agents are MINTED BY ARCHON (`archon.mint.agent.v1` →
`archon.mint.confirmed.v1`); this brief does not hand-roll agent service code — it wires the
render + publish + voice surfaces those agents drive on the 5090.

## Lane

Fordham-Creator · KiloCode GLM (5090) · branch `feat/fordham-room-5090-creator`

Three-Body: **Claude (4090) analyzed → KiloCode GLM (5090) implements → `chit:sign-trail`
closes the loop.** Do NOT duplicate the existing `5090-voice.room.studio` — collaborate with it.

## Arguments

- `room_id` (string, required): `fordham.room.community` — the room these surfaces attach to. Stage starts at `rehearsal`.
- `homes` (int, required): actual opt-in unit count for the pilot dashboard. **Placeholder only** — the real number is an Open Operator Decision (`pmoves/docs/pilots/fordham-hill/README.md:48`); never bake a made-up count into committed output.
- `adopted_rate` (int, optional): monthly per-home savings figure fed to the dashboard `--savings-per-home`. Three anchors are in play ($5 product / $10 due / $35 premium, `README.md:37`); the dashboard default is `35` (`deploy/provision/pilot-dashboard-gen.sh:16`). Pass through as-is; do NOT reconcile to one binding rate here — that is a Committee/board decision.
- `node_cap` (int, optional): homes-per-node capacity for the load gauge, default `40` (`pilot-dashboard-gen.sh:16`).
- `voice_suit` (string, optional): FlOO$ persona to bind for the voice agent (`dr-bean`, `mr-clean`, `powerpuff-bubbles`, `powerpuff-blossom`, `powerpuff-buttercup`) — routed through the existing `persona-bind` skill, default `powerpuff-bubbles` (coordination).
- `publish_target` (enum, optional): `tailnet` (Tailscale-served, private) | `cf-pages` (public pmoves-ai Pages), default `tailnet`.

## Implementation

### 1. Creator pipeline — resident-facing materials (5090 ComfyUI)

The creator agent renders flyers/onboarding cards/dashboard hero art via the **self-hosted
ComfyUI on the fleet** (NOT RunPod). The 5090 is the impedance-matched render node; image +
anime workstreams route here.

- Reuse the existing self-host ComfyUI (`PMOVES-Creator/Dockerfile`, `PMOVES-Creator/docker-compose.pmoves.yml`); runtime is decoupled via `COMFYUI_URL` so the 5090 container and the 4090 host/Pinokio ComfyUI are interchangeable. Do NOT stand up a second ComfyUI.
- **License gate is a hard requirement** — only license-clean models in the pipeline:
  - Image / text-in-image: `Qwen/Qwen-Image` (Apache-2.0), `black-forest-labs/FLUX.1-schnell` (Apache-2.0, fast drafts).
  - Anime: `cagliostrolab/animagine-xl-4.0` (OpenRAIL++, honor use-restrictions).
  - REJECTED (do not add): Ideogram-4, ANIMA (both non-commercial). Mine their *workflows*, swap the model.
- Render seam = **`comfy-watcher` → MinIO** (the watcher harvests finished renders to object storage), NOT a render-webhook. Emit resident-material artifacts under a `rooms/fordham/creator/` MinIO prefix so the dashboard and notebook can reference them by presigned URL.
- Output artifacts are decorative/informational only — a rendered flyer must never assert a dollar/vote figure as binding (see Notes honesty rules).

### 2. Cloudflare dev-site + pilot dashboard

Two publish paths already exist — wire the creator lane to both, gated by `publish_target`:

- **Resident dashboard (primary, `tailnet`):** pipe a live snapshot into the existing generator, serve privately over the mesh — no app, just a browser on a passed-around tablet.
  ```bash
  deploy/provision/exit-node-observer.sh --json \
    | deploy/provision/pilot-dashboard-gen.sh \
        --homes "$homes" --node-cap "$node_cap" \
        --savings-per-home "$adopted_rate" --out /opt/pilot-dashboard/index.html
  deploy/provision/pilot-dashboard-serve.sh   # Tailscale HTTPS, private
  ```
  The generator already renders resident-friendly, non-technical status (`All good` / `Needs a look`, capacity %, savings) and honors the measured-caveat framing — extend it, don't rewrite it.
- **Public dev-site (`cf-pages`):** the pilot page ships into the `pmoves-ai` Cloudflare Pages project. Site source is `PMOVES_AI_DIR ?= ../website` (`pmoves/Makefile:1940`), project `pmoves-ai` (`:1939`), preview port `8789` (`:1942`).
  - Local preview: `make -C pmoves pmoves-ai-dev` (`Makefile:1945`, wrangler pages dev).
  - Deploy: `make -C pmoves pmoves-ai-deploy` (`Makefile:1966`) — requires `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` from the secrets bundle, do not hardcode.
  - Scope any CSP per document route, NOT via a `/*` `_headers` override (CF Pages `_headers` APPENDS and browsers intersect → over-broad `/*` breaks other routes).
- Add the pilot page as static content under `../website/` (or a `fordham/` subroute); the CF path is for the *public-facing* pilot story, the tailnet path is for the *live private* dashboard. Do not put live resident PII or the voter roll on the public CF site.

### 3. Voice-studio collaboration (do NOT duplicate)

The Fordham `voice` agent gives accessible, spoken interaction. `5090-voice.room.studio`
already owns the TTS/audition/prosody surface — the Fordham voice agent **collaborates with
it**, it does not fork it.

- Bind the FlOO$ suit through `persona-bind` (sets `BEATS_VOICE`) and encode prosody through `shift-from-bpm` (publishes CGP v0.2 on `tokenism.prosodic.bpm.v1`). Reuse; do not reimplement the BPM→voice path.
- Route spoken output through the studio's existing `voice-console` app (`route /dashboard/voice`, `action_namespace voice`, capabilities `tts/engine-status/audition/prosody`) — see `pmoves/config/rooms/5090-voice.room.studio.json:44-54`.
- Cross-room signal: the Fordham voice agent listens for the studio's `voice.cast.completed.v1` (`5090-voice.room.studio.json:203`) and references finished casts by artifact ref; it does NOT spin up a second Flute/TTS service. `service_refs` for the Fordham room point at the same `flute-gateway` / `ultimate-tts`, not new containers.
- Register the collaboration as a room-local `skill.binding.v1` on `fordham.room.community` that surfaces `persona-bind` + `shift-from-bpm` — bindings are room-local per the contract (`pmoves/docs/ROOM_MANIFEST_CONTRACT.md:105-119`); the skill definitions stay portable in the studio.

### 4. Registration + validation

- The `fordham.room.community` manifest and its 4 agent mint-specs land in the sibling fan-out facets; this brief assumes the manifest exists. Verify it validates: `python pmoves/scripts/validate_room_manifests.py`.
- Confirm the room is registered in `pmoves/config/rooms/catalog.json` (same shape as the other 5 rows, `catalog.json:3-44`).

## Related

- `pmoves/docs/pilots/fordham-hill/README.md` — the 4-lane convergence package + honesty ledger (proven / modeled / scaffolded). Read `:10` (measured caveat), `:16` (fraud human-led), `:45-55` (open operator decisions).
- `deploy/provision/pilot-dashboard-gen.sh` + `pilot-dashboard-serve.sh` — resident dashboard generator + Tailscale server (reuse, extend).
- `deploy/provision/exit-node-observer.sh` — `--json` snapshot source feeding the dashboard.
- `pmoves/Makefile:1944-1989` — `pmoves-ai-{dev,create,deploy,status}` CF Pages targets.
- `pmoves/config/rooms/5090-voice.room.studio.json` — existing voice studio to collaborate with (do not duplicate).
- `pmoves/config/rooms/catalog.json` — room registry.
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` — room/notebook/apps/skill-binding contract + `validate_room_manifests.py`.
- `PMOVES-Creator/` — self-host ComfyUI (Dockerfile, `docker-compose.pmoves.yml`); `COMFYUI_URL` decouples 5090 container ↔ 4090 host.
- Memory `reference_creator_pipeline_models` — license-vetted model picks (Qwen-Image / FLUX.1-schnell / Animagine-XL-4.0 ADOPT; Ideogram-4 / ANIMA REJECTED).
- Memory `project_creator_comfyui_selfhost` — self-host-not-RunPod, `comfy-watcher→MinIO` render seam, 5090 image/anime routing.
- Skills: `persona-bind`, `shift-from-bpm`, `mesh-egress-ab` (capacity A/B for the dashboard numbers), `pmoves-chit-sign`, `pmoves-cipher-memory`.

## Notes

- **HONESTY IS LOAD-BEARING.** Every dollar / vote / governance figure the dashboard or a rendered flyer surfaces is **DRAFT — REQUIRES LEGAL REVIEW** (`README.md:3`). Do not invent binding figures. The `--savings-per-home` value is a pass-through placeholder, not an adopted rate. Show the measured caveat honestly — on a good Fios line the tunnel LOWERS peak (305/70 vs 520/101, `README.md:10`); the honest win is cost / privacy / resilience / self-governance, not raw peak.
- **Transparency only, never accusation.** The fraud investigation stays human-led (PMOVES-mike + Missing Link, `README.md:16`). Nothing the creator pipeline renders may frame an accusation or imply legal authority — auditable records only.
- **Privacy first.** The voter roll and resident PII stay on the mesh (Tailscale-served dashboard); never publish them to the public CF Pages site. Mesh + Docker only — no Windows local-network sharing.
- **Village Rule / reuse, don't reimplement.** Collaborate with `5090-voice.room.studio` (existing `voice-console`, `flute-gateway`, `voice.cast.completed.v1`); reuse the ComfyUI self-host, the `pilot-dashboard-gen.sh` generator, and the `pmoves-ai-deploy` CF target. New surfaces = room-local `skill.binding.v1` records, not new services.
- **Secrets discipline.** `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` come from the secrets bundle via the funnel — never hardcode; the deploy target already fails closed if they are unset (`Makefile:1968-1974`).
- **Known Roads.** Use `make` targets for CF deploy and the provision scripts for the dashboard — no raw wrangler/docker guessing. Route render through ComfyUI + `comfy-watcher→MinIO`, not ad-hoc file copies.
- After implementation, run `chit:sign-trail` to close the brief loop (GRAPHITI_MARK footer). Carry DARKXSIDE co-creation attribution in the PR trail.
