# PMOVES.AI Repository Overview
[![PMOVES Integrations CI](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/pmoves-integrations-ci.yml/badge.svg)](https://github.com/POWERFULMOVES/PMOVES.AI/actions/workflows/pmoves-integrations-ci.yml)

PMOVES.AI powers a distributed, multi-agent orchestration mesh built around Agent Zero, Archon, and a fleet of specialized "muscle" services for retrieval, generation, and enrichment workflows. The ecosystem focuses on local-first autonomy, reproducible provisioning, and self-improving research loops that integrate knowledge management, workflow automation, and rich media processing pipelines.

## Key Directories
- **`CATACLYSM_STUDIOS_INC/`** – Provisioning bundles and infrastructure automations for homelab and field hardware, including unattended OS installs, Jetson bootstrap scripts, and ready-to-run Docker stacks that mirror the production mesh topology.
- **`docs/`** – High-level strategy, architecture, and integration guides for the overall PMOVES ecosystem, such as system overviews, multi-agent coordination notes, and archival research digests. See also `pmoves/docs/ENVIRONMENT_POLICY.md` for the single‑file environment policy and Jellyfin host‑mount instructions.
- **`pmoves/`** – The primary application stack with docker-compose definitions, service code, datasets, Supabase schema, and in-depth runbooks for daily operations and advanced workflows.
- **`pmoves/contracts/solidity/`** – Hardhat workspace prototyping Food-USD / GroToken governance flows with automated tests that model staking, quadratic voting, and group-buy execution.
- **`pmoves/ui/`** – Next.js + Supabase Platform Kit workspace for the upcoming web UI; reuses `pmoves/.env.local` so frontend hooks can target the same Supabase CLI stack.

## Essential Documentation
- [PMOVES Stack README](pmoves/README.md) – Quickstart environment setup, service inventory, and Codex bootstrap steps for running the orchestration mesh locally.
- [Local Tooling Reference](pmoves/docs/LOCAL_TOOLING_REFERENCE.md) – One-stop index for environment scripts, Make targets, Supabase workflows, smoke tests, and provisioning helpers.
- [Supabase Service Guide](pmoves/docs/services/supabase/README.md) – CLI vs compose expectations, realtime wiring (`supabase start --network-id pmoves-net`), and how PMOVES consumes PostgREST/Realtime in both local and self-hosted deployments.
- [PMOVES Docs Index](pmoves/docs/README_DOCS_INDEX.md) – Curated entry points into the pmoves-specific runbooks covering Creator Pipeline, ComfyUI flows, reranker configurations, and smoke tests.
- [UI workspace bring-up](pmoves/docs/LOCAL_DEV.md#ui-workspace-nextjs--supabase-platform-kit) – Next.js + Supabase quickstart (npm/yarn commands, env loading from `pmoves/.env.local`, Supabase CLI prerequisites).
- [Service Docs Index](pmoves/docs/services/README.md) – Per‑service guides (overview, compose/ports, runbooks, smoke tests, and roadmap alignment).
- [External Integrations Bring-Up](pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md) – Wger, Firefly III, Open Notebook, and Jellyfin commands, token wiring, and port overrides for `make up-external`.
- [Architecture Primer](docs/PMOVES_ARC.md) – Deep dive into mesh topology, service responsibilities, and evolution of the orchestration layers.
- [Complete Architecture Map](pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md) – Full-fidelity view of the latest integration mesh, including data planes and edge deployments.
- [Multi-Agent Integration Guidelines](docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md) – Operational patterns for coordinating Agent Zero, Archon, and automation hubs across environments.
- [Codex + Copilot Review Workflow](docs/COPILOT_REVIEW_WORKFLOW.md) – How to combine the Codex CLI reviewer with GitHub Copilot’s PR assistant, including token setup and evidence logging expectations.
- [Archon Updates for PMOVES](pmoves/docs/archonupdateforpmoves.md) – What changed in the October 2025 Archon bundle, how to wire the Supabase CLI stack, and the MCP/NATS expectations.
- [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) – Command catalog for starting, stopping, and tailoring compose profiles (core data plane, media analyzers, Supabase modes, and agent bundles).
 - [Single‑User (Owner) Mode](pmoves/docs/SECURITY_SINGLE_USER.md) – Personal‑first operation without login prompts; boot‑JWT auto‑auth, owner chip in the UI, and security notes.

## Dashboards & UIs (local defaults)
- Supabase Studio: http://127.0.0.1:65433 (CLI stack) — created by `make supa-start`.
- Hi‑RAG v2 Geometry Console (GPU): http://localhost:${HIRAG_V2_GPU_HOST_PORT:-8087}/geometry/ (after `make up`).
- TensorZero UI: http://localhost:4000 (after `make up-tensorzero`).
- TensorZero Gateway: http://localhost:3030 (proxy to 3000 in‑container).
- Agent Zero UI: http://localhost:8080 (after `make up-agents`).
- Archon Health: http://localhost:8091/healthz (after `make up-agents`).
  - If your forks use non-standard health endpoints, set `NEXT_PUBLIC_AGENT_ZERO_HEALTH_PATH` / `NEXT_PUBLIC_ARCHON_HEALTH_PATH`. See `pmoves/docs/SERVICE_HEALTH_ENDPOINTS.md`.
- Jellyfin: http://localhost:8096 (after `make -C pmoves up-jellyfin-ai`).
- Jellyfin API Dashboard: http://localhost:8400; Gateway: http://localhost:8300.
- Open Notebook: http://localhost:8503 (after `make -C pmoves notebook-up`).
- Invidious: http://127.0.0.1:3000 (companion at http://127.0.0.1:8282).
- n8n: http://localhost:5678 (after `make -C pmoves up-n8n`).

### Default access and operator credentials
- Supabase operator is provisioned by `make supabase-boot-user` (also run by `make first-run`). The command writes values to `pmoves/env.shared` and `pmoves/.env.local`:
  - `SUPABASE_BOOT_USER_EMAIL`, `SUPABASE_BOOT_USER_PASSWORD`, `SUPABASE_BOOT_USER_JWT`.
  - The PMOVES UI auto‑authenticates with `NEXT_PUBLIC_SUPABASE_BOOT_USER_JWT` so most routes won’t prompt for a password. If you need to log in manually, use the email/password above from your env files.
- Jellyfin uses the LinuxServer image defaults. After first boot, confirm the admin user and API key in `pmoves/env.jellyfin-ai` or via the Jellyfin UI (Settings → Dashboard). Update `JELLYFIN_API_KEY` and `JELLYFIN_USER_ID` in `pmoves/env.shared` if you rotate.
- Wger and Firefly are brought up with PMOVES‑branded defaults sourced from `pmoves/env.shared` (see `pmoves/docs/FIRST_RUN.md` “Seeded & Branded Defaults” for the exact initial usernames and emails).
- Open Notebook’s UI password also serves as its API bearer token; keep `OPEN_NOTEBOOK_API_TOKEN` identical to `OPEN_NOTEBOOK_PASSWORD` so CLI helpers and agents work against the same branded login (see `pmoves/docs/services/open-notebook/README.md`).
- For a full list of seeded branded logins and where they come from, see:
  - `pmoves/docs/FIRST_RUN.md` (Seeded & Branded Defaults)
  - `docs/SECRETS.md` (Secret Management Playbook)

- **Creator bundle:** see [`pmoves/creator/`](pmoves/creator/README.md) for installers, tutorials, and ComfyUI workflows supporting WAN Animate, Qwen Image Edit+, and VibeVoice TTS. Key guides include:
  - [WAN Animate 2.2 Tutorial](pmoves/creator/tutorials/wan_animate_2.2_tutorial.md)
  - [Qwen Image Edit+ Tutorial](pmoves/creator/tutorials/qwen_image_edit_plus_tutorial.md)
  - [VibeVoice TTS Tutorial](pmoves/creator/tutorials/vibevoice_tts_tutorial.md)
  - [WAN Animate Installation Scripts](pmoves/creator/tutorials/waninstall%20guide.md)
- [Creator Pipeline Runbook](pmoves/docs/PMOVES.AI%20PLANS/CREATOR_PIPELINE.md) – Current status of n8n automations (health/finance live, creative flows staging) plus geometry mapping and persona playback prep.

### Zero-to-running stack (fast path)

```bash
make first-run
```

This single command orchestrates the full onboarding sequence: environment prompts, Supabase CLI bring-up, data/service seeding, core + agent + external stacks, and the 12-step smoke harness. When it finishes successfully every bundled integration (Wger, Firefly, Jellyfin, Open Notebook, Agent mesh) is online with branded defaults. See the [First-Run Bootstrap Overview](pmoves/docs/FIRST_RUN.md) for a detailed breakdown of each step.

### Initial Setup & Tooling Flow (manual path)
1. **Environment bootstrap** – Walk through [pmoves/README.md](pmoves/README.md) to provision runtime prerequisites, seed `pmoves/env.shared`, and populate secrets. Use `make bootstrap` (wrapping `python -m pmoves.scripts.bootstrap_env`) when you need finer control, or invoke `python3 -m pmoves.tools.mini_cli bootstrap --accept-defaults` to script the same flow alongside the provisioning bundle. Both paths update `env.shared`, `.env.generated`, `.env.local`, and the auxiliary `env.*.additions` files consumed by Compose and the UI launcher.
2. **Supabase realtime alignment** – Follow the [Supabase Service Guide](pmoves/docs/services/supabase/README.md) to start the CLI stack with `supabase start --network-id pmoves-net` (run this before accepting Supabase prompts in `make bootstrap`) and mirror the websocket endpoint (`SUPABASE_REALTIME_URL=ws://host.docker.internal:65421/realtime/v1`). This matches our self-hosted Supabase deployments.
3. **UI workspace bring-up** – `cd pmoves/ui` then `npm install` (or `yarn install`). The Next.js app loads Supabase creds from `pmoves/.env.local` and expects the Supabase CLI stack (`make supa-start` + `make supa-status`) before running `npm run dev`.
4. **Tooling cheatsheet** – Keep [Local Tooling Reference](pmoves/docs/LOCAL_TOOLING_REFERENCE.md) handy for Make targets, smoke tests, and environment scripts (`env_setup`, `flight-check`, `smoke`).
5. **Provisioning & hardware targets** – Browse `CATACLYSM_STUDIOS_INC/` for automated OS images, Jetson bootstrap bundles, and pmoves-net Docker stacks ready for edge hardware.

## Service Index + CHIT Map

**Geometry + CHIT core**
- `pmoves/services/hi-rag-gateway-v2/` — v2 gateway (CPU `:8086`, GPU `:8087`). Handles `/geometry/*`, jump, decode, calibration, Supabase realtime warmups, and CGP persistence.
- `pmoves/services/hi-rag-gateway/` — v1 legacy gateway (host `:8089`). Minimal CHIT endpoints for backward compatibility.
- `pmoves/services/gateway/` — Experimental CHIT UI/API for live geometry visualisation and WebRTC broadcast.
- `pmoves/services/mesh-agent/` — Geometry mesh bridge; signs and republishes `geometry.cgp.v1` across deployments.
- `pmoves/services/evo-controller/` — Geometry tuning controller; reads CGPs from Supabase, emits tuning capsules back into the bus.

**Orchestration & knowledge**
- `pmoves/services/agent-zero/` — MCP bridge + decision engine (ingests Supabase + CHIT events).
- `pmoves/services/archon/` — Agent builder/knowledge management with Supabase CLI realtime + NATS clients.
- `pmoves/services/deepresearch/` — Tongyi DeepResearch bridge with OpenRouter/local modes plus Open Notebook mirroring.
- `pmoves/services/n8n/` — Workflow orchestrator; health/finance webhooks emit CGPs via hi-rag v2.

**External integrations (pmoves-net)**
- `pmoves/services/open-notebook/` (doc lives in `pmoves/docs/services/open-notebook/`) — Streamlit UI + SurrealDB API (container ports 8502/5055 per upstream; host defaults map to `:8503` UI and `:5055` API, override with `OPEN_NOTEBOOK_*_PORT`) mounted via `make up-open-notebook` for research assets and MCP notebooks.
- `pmoves/services/wger/` — Health metrics ingest (paired with Supabase tables + `health.weekly.summary.v1` CGPs).
- `pmoves/services/firefly-iii/` — Personal finance ingest; finance flows create `finance.monthly.summary.v1` CGPs.
- `pmoves/services/jellyfin-bridge/` + `pmoves/docs/services/jellyfin-ai/` — Media sync bridging Jellyfin metadata into Supabase + Discord publisher.

**Operational substrates**
- `pmoves/services/pmoves-yt/` — YouTube ingest; publishes geometry packets after segmentation.
- `pmoves/services/retrieval-eval/` — Retrieval benchmarking, relies on Supabase + hi-rag.
- `pmoves/services/publisher/` — Discord & Jellyfin publisher with geometry-aware payloads.
- `pmoves/services/{presign,render-webhook,extract-worker,langextract,media-audio,media-video,pdf-ingest,comfy-watcher,comfyui}` — Supporting ingestion, extraction, and media tooling.
- `pmoves/services/notebook-sync/` — Bridges Open Notebook datasets into Supabase and LangExtract flows.

See each directory’s README for ports, Make targets, and geometry notes. New integrations reference external repositories under `integrations-workspace/` and the setup steps captured in `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`.

## Getting Started
1. **Bootstrap the stack** – For brand-new machines run `make first-run`. For incremental setup follow the environment and container launch instructions in the [pmoves/README.md](pmoves/README.md): place overrides in `pmoves/.env.local`, run `make bootstrap` to capture credentials, `make up` to start the core services, and `make bootstrap-data` to apply Supabase SQL, seed Neo4j, and load the demo Qdrant/Meili corpus before smoke testing.
2. **Review orchestration flows** – Use the [Make Targets Reference](pmoves/docs/MAKE_TARGETS.md) for day-to-day compose control, and consult the architecture and multi-agent guides in `/docs` for how Agent Zero, Archon, and supporting services communicate across the mesh.

Need a full directory tour? Regenerate `folders.md` using the embedded script to explore the repository structure at depth two before diving deeper into service-specific documentation.
