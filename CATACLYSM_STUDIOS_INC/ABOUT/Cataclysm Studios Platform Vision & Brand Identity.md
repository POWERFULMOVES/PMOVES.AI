# Cataclysm Studios Platform Vision & Brand Identity

_Status review: October 26 2025 (repo branch `feature/supabase-tensorzero-cloudflare`)_

This document aligns the Cataclysm Studios brand platform with the current PMOVES.AI codebase so product, engineering, and creative teams can work from a single, verifiable blueprint.

## 1. Brand System Overview

### 1.1 Cataclysm Studios Inc.
- Operates the end-to-end platform and infrastructure bundles kept under `CATACLYSM_STUDIOS_INC/`.  
- Hosts provisioning scripts, Jetson/edge images, and Docker stacks that mirror production (`folders.md`, `README.md`, `pmoves/README.md`).
- Stewardship focus: trustworthy operations, reproducible builds, and compliance with internal security policies (`SECURITY.md`, `docs/PMOVES_Multi-Agent_System_Crush_CLI_Integration_and_Guidelines.md`).

### 1.2 PMOVES.AI (Powerful Moves AI)
- Primary technical product—multi-agent orchestration mesh centred on Agent Zero, Archon, and Hi‑RAG services (`README.md`, `docs/PMOVES_ARC.md`, `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md`).
- Code, compose profiles, and runbooks live under `pmoves/`; roadmap and implementation evidence are tracked in `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`, `NEXT_STEPS.md`, and `SESSION_IMPLEMENTATION_PLAN.md`.
- Brand promise: “Local-first autonomy, reproducible provisioning, and self-improving research loops.”

### 1.3 DARKXSIDE
- Artistic persona and storytelling lens for Cataclysm’s community activation.  
- Creative workflows, tutorials, and media automation are located in `pmoves/creator/` with plans under `pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE.md`.
- Responsible for the emotional identity, visual direction, and narrative arcs that connect technology to grassroots movements.

### 1.4 POWERFULMOVES / Community Ecosystem
- GitHub organization home for PMOVES.AI source and integrations (`README.md`); migrations to the `CATACLYSM-STUDIOS-INC` org and GHCR namespace are in progress per roadmap stability initiative.
- Community programs (Fordham Hill cooperative pilot, creator collectives) inherit platform guidance from this document and the referenced runbooks.

## 2. Platform Pillars (verified against repository artefacts)

| Pillar | Description | Primary Evidence |
| --- | --- | --- |
| Orchestration Mesh | Agent Zero + Archon + Hi‑RAG gateways ingest, reason, and enrich data across Supabase, Neo4j, Qdrant, Meili, and TensorZero providers. | `README.md`, `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md`, `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` |
| Knowledge & Data Plane | Supabase CLI stack, render/presign services, retrieval-eval harness, telemetry dashboards. | `pmoves/README.md`, `pmoves/docs/services/supabase/README.md`, `pmoves/docs/TELEMETRY_ROI.md` |
| Creative & Media Stack | ComfyUI pipelines, pmoves-yt ingestion, publisher + Discord bridge, Jellyfin integration. | `pmoves/creator/README.md`, `pmoves/services/publisher/`, `pmoves/services/pmoves-yt/`, `pmoves/docs/services/jellyfin-ai/README.md` |
| Health & Finance Integrations | Branded Wger and Firefly stacks with smoke tests and env guidance. | `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`, `pmoves/docs/services/wger/README.md`, `pmoves/docs/services/firefly-iii/README.md`, `pmoves/Makefile` (smoke targets) |
| Research Notebook Workflow | Open Notebook deployment, local model seeding via Ollama, notebook-sync bridge. | `pmoves/docs/services/open-notebook/README.md`, `pmoves/scripts/open_notebook_seed.py`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md` |
| Governance & Reliability | CI parity expectations, reproducible make targets, upcoming change-control expansion. | `docs/LOCAL_CI_CHECKS.md`, `pmoves/docs/MAKE_TARGETS.md`, `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` (Stability initiative) |

## 3. Implementation Snapshot (as of October 26 2025)

- **Roadmap alignment** – Milestone M1 complete, M2 mid-flight with active tasks on publisher metadata, Discord automation, and Wger/Firefly integration polish (`pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`).  
- **UI platform** – `pmoves/ui` upgraded to Next 16 + React 19, secured upload ingestion via owner-scoped Supabase policies (`pmoves/ui/app/api/uploads/presign/route.ts`), added Playwright/Jest harnesses, and documented eslint migration guidance (`pmoves/ui/README.md`, `pmoves/docs/LOCAL_DEV.md#ui-workspace-nextjs--supabase-platform-kit`).  
- **External services** – `make up-external-wger` and `make up-external-firefly` now pull `ghcr.io/cataclysm-studios-inc` images, apply branding defaults (`pmoves/scripts/wger_brand_defaults.sh`), and expose dedicated smoke targets (`pmoves/Makefile`, `pmoves/docs/SMOKETESTS.md`).  
- **Open Notebook** – Local-first embeddings enabled via `OPEN_NOTEBOOK_*` envs and Ollama integration; sync helpers logged a successful validation run on 2025‑10‑26 (`pmoves/docs/services/open-notebook/README.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`).  
- **YouTube ingestion** – Async `/yt/emit` pipeline with status endpoint, lexical fallback, and vendored `httpx` refresh using `make vendor-httpx`; pytest suite green (13 tests) (`pmoves/services/pmoves-yt/`, `pmoves/Makefile`, `pmoves/docs/MAKE_TARGETS.md`).  
- **Security posture** – Supabase anon role restricted on upload presign paths; previews require authenticated sessions. Wger ships with Django Axes enabled and documented Redis cache expectations (`pmoves/docs/services/wger/README.md`).  
- **Pending clean-up** – `pmoves/ui/middleware.ts` rename to `proxy.ts` is tracked, Playwright scenarios need expansion, and untracked assets under `CATACLYSM_STUDIOS_INC/ABOUT/` require triage before release (noted in repo `git status`).

## 4. Brand & Experience Guidelines

### 4.1 Core Narrative
- **Promise:** empower communities to self-govern creative, economic, and knowledge work using accessible AI + cooperative tooling (reinforced by `README.md` and roadmap positioning).
- **Tone:** confident, community-first, rebellious optimism (anchored by DARKXSIDE persona).
- **Mantra:** “Powerful Moves for everyday creators”—use across UI hero copy, onboarding, and media kits (`pmoves/ui/app/(marketing)/` assets forthcoming).

### 4.2 Touchpoints & Implementation Hooks
- **Web UI:** adopt Supabase auth gating, enforce owner-prefixed object keys, and surface branded onboarding text pulled from this document (`pmoves/ui/app/dashboard/*`).  
- **External services:** run `make wger-brand-defaults` after bootstrap to set site name, admin identity, and default gym descriptors; keep `OPEN_NOTEBOOK_PASSWORD` and `OPEN_NOTEBOOK_API_TOKEN` in lockstep for branded deployments (`pmoves/env.shared`, `pmoves/docs/services/open-notebook/README.md`).  
- **Docs:** when updating workflows, cross-link relevant runbooks under `docs/` or `pmoves/docs/` and note rationale/decisions per repo guidance (see root `README.md` documentation expectations).  
- **Security defaults:** highlight Axes rate limiting in onboarding docs, recommend Redis cache wiring, and include Supabase RLS examples in UI documentation.

### 4.3 Visual & Messaging Anchors (to be expanded)
- Logo lockups and color references live in `CATACLYSM_STUDIOS_INC/ABOUT/notes/` (pending vector cleanup).  
- Future design system should reference Next.js app tokens once `pmoves/ui` design tokens land.

## 5. Blueprint Backlog (cross-reference with ROADMAP & NEXT_STEPS)

### 5.1 Now (active sprint)
1. **Finalize publisher & Discord embeds** – Close remaining M2 deliverables (`pmoves/docs/PMOVES.AI PLANS/ROADMAP.md`, `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`).  
2. **Document Axes + Redis wiring** – Extend `pmoves/docs/services/wger/README.md` with production cache setup and link from `docs/LOCAL_CI_CHECKS.md`.  
3. **UI middleware migration** – Replace `pmoves/ui/middleware.ts` with new proxy entrypoint, update docs/tests.

### 5.2 Next
1. **Extend uv/vendor workflow** – Apply `make vendor-httpx` pattern to other Python services (publisher, notebook-sync) and capture instructions in `pmoves/docs/LOCAL_TOOLING_REFERENCE.md`.  
2. **Playwright scenarios** – Add authenticated upload + presign E2E tests (`pmoves/ui/e2e/`) and document expected datasets.  
3. **Integrations cleanup** – Decide on tracking vs ignoring `CATACLYSM_STUDIOS_INC/ABOUT/` subdirectories and `.dockerignore`; formalize policy in repository `.gitignore`.

### 5.3 Later
1. **DAO / Tokenomics implementation** – Move conceptual token suite (Food-USD, GroToken, Fame/$WORK) from research into actionable specs: generate contracts, define Supabase schemas, and author enforcement docs.  
2. **Design system & brand kit** – Build shared component library for `pmoves/ui`, Figma token export, and printable brand book referencing this document.  
3. **Community pilot playbook** – Translate Fordham Hill prototype steps into a repeatable guide under `docs/PMOVES_COMMUNITY_PILOT.md` (new file).

## 6. Governance & Token Strategy (Research Track)

- The repo currently contains **no smart contract code or token schemas**; all references to Food-USD, GroToken, Fame Coin/$WORK remain conceptual.  
- Actions required before launch:
  1. Produce technical specs and risk assessment (`docs/` future section).  
  2. Align DAO constitution drafts with `pmoves/docs/` formatting and host them in-repo (replace external links).  
  3. Prototype off-chain governance via Supabase tables + serverless functions before deploying on-chain implementations.
- Until implemented, messaging should label tokenomics as “planned” and avoid implying production availability.

## 7. Reference Map

| Domain | Key Files (repo-relative) | Purpose |
| --- | --- | --- |
| Architecture & Ops | `README.md`; `pmoves/README.md`; `pmoves/docs/context/PMOVES_COMPLETE_ARCHITECTURE.md`; `pmoves/docs/PMOVES.AI PLANS/ROADMAP.md` | System overview, service inventory, roadmap status |
| Integrations | `pmoves/docs/EXTERNAL_INTEGRATIONS_BRINGUP.md`; `pmoves/docs/services/{wger,firefly-iii,open-notebook}/README.md`; `pmoves/scripts/wger_brand_defaults.sh` | Runbooks and automation helpers |
| Security & CI | `SECURITY.md`; `docs/LOCAL_CI_CHECKS.md`; `pmoves/docs/MAKE_TARGETS.md`; `pmoves/docs/SMOKETESTS.md` | Policies, required checks, smoke harness |
| Creative Stack | `pmoves/creator/README.md`; `pmoves/docs/PMOVES.AI PLANS/CREATOR_PIPELINE.md` | DARKXSIDE media workflows and creative automation |
| UI & Frontend | `pmoves/ui/README.md`; `pmoves/ui/app/api/uploads/*`; `pmoves/ui/e2e/`; `pmoves/ui/__tests__/` | Next.js platform kit, ingestion security, test suites |
| Notebook & Knowledge | `pmoves/docs/services/open-notebook/README.md`; `pmoves/scripts/open_notebook_seed.py`; `pmoves/scripts/mindmap_to_notebook.py`; `pmoves/scripts/hirag_search_to_notebook.py` | Research workspace integration |

## 8. Change Log

- **2025‑10‑26:** Rebuilt document to match repository state, removed external-only references, and established blueprint backlog linked to `pmoves/docs/`.

---

_Maintainers: update this file alongside roadmap or branding updates. Reference specific commits in PR descriptions to keep brand, product, and engineering aligned._
