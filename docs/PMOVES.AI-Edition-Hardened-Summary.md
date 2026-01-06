PMOVES.AI Edition - Hardened Integrations, Images, and CI/CD
_Last updated: 2025-12-14_

Update (2025-12-14)
- Voice Agents are wired end-to-end via n8n + Flute Gateway + TensorZero (default local model: `tensorzero::model_name::qwen2_5_14b`) and publish `voice.agent.response.v1` on NATS.
- FFmpeg-Whisper supports `POST /transcribe_file` (multipart) for ad-hoc STT calls (used by Flute Gateway).
- n8n flow exports in `pmoves/n8n/flows/` use millisecond timeouts for HTTP Request nodes (n8n interprets `options.timeout` as ms).
- n8n production mode: use Postgres (not SQLite) via `N8N_DB=postgres` + `N8N_DB_*` (see `pmoves/docker-compose.n8n.postgres.yml`).
- Optional: VibeVoice realtime can run in Docker (`VOICE_REALTIME=1 make -C pmoves up-vibevoice`); on RTX 5090/SM_120 it auto-falls back to CPU until a compatible PyTorch build lands.

Overview
- Goal: treat each external integration as a first-class, hardened submodule with a pinned image in GHCR, reproducible builds, and CI parity with PMOVES.AI.
- Scope: Archon, Agent Zero, PMOVES.YT, Channel Monitor, Invidious stack, Jellyfin bridge/AI overlay, Notebook/Surreal, DeepResearch, SupaSerch, TensorZero, and core data services (Qdrant, Meili, Neo4j, MinIO, Supabase REST/PostgREST).
- Deliverables: submodule layout, image catalog, hardening baseline, MCP catalog notes, migration plan, and verification gates.
- Companion guidance: follow root `AGENTS.md` for stabilization/CI expectations and `pmoves/AGENTS.md` for pmoves subtree coding norms. Keep any hardening-related edits reflected across these docs.

Inventory (as of Nov 11, 2025)
- Local‑build services (compose `build:`):
  - `services/archon` (API/UI), `services/agent-zero`, `services/channel-monitor`, `services/jellyfin-bridge`, `services/deepresearch`, `services/supaserch`, `services/hi-rag-gateway(-v2)(-gpu)`, `services/invidious-companion-proxy`, `services/grayjay-plugin-host`, `services/presign`, `services/render-webhook`, `services/extract-worker`, `services/notebook-sync`, `services/media-*`, `services/retrieval-eval`, `services/mesh-agent`.
- Pulled images (compose `image:`):
  - Datastores: `ankane/pgvector`, `neo4j:5.22`, `qdrant/qdrant:v1.10.0`, `getmeili/meilisearch:v1.8`, `minio/minio:latest`.
  - Supabase REST: `postgrest/postgrest:latest` (+ CLI variant).
  - Messaging/infra/monitoring: `nats:2.10-alpine`, `prom/*`, `grafana/*`, `loki`, `promtail`, `cadvisor`.
  - Media/YT: `quay.io/invidious/*:latest`, `postgres:14` (Invidious DB), `brainicism/bgutil-ytdlp-pot-provider:1.2.2`.
  - TensorZero stack: `clickhouse/clickhouse-server:24.12-alpine`, `tensorzero/gateway`, `tensorzero/ui`.
  - Ollama sidecar: `${PMOVES_OLLAMA_IMAGE:-pmoves/ollama:0.12.6}`.
  - Optional externals: `ghcr.io/.../pmoves-health-wger:pmoves-latest`, `ghcr.io/.../pmoves-firefly-iii:pmoves-latest`.

Immediate Stabilization — Archon
- Status: Archon is wired to the Supabase CLI stack using a CLI‑first environment contract. The vendor expects `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` (service role key); the PMOVES wrapper maps `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_KEY` to that value before the vendor initializes.
- Base URL resolution:
  - Preferred: `ARCHON_SUPABASE_BASE_URL` (e.g., `http://host.docker.internal:65421` for local CLI).
  - Fallback: derive the base from `SUPA_REST_URL` by stripping `/rest/v1`.
  - There is no implicit fallback to `postgrest:3000`; misconfiguration should fail explicitly so issues surface quickly.
- Compose defaults (local CLI mode):
  - `SUPA_REST_URL=http://host.docker.internal:65421/rest/v1`
  - `ARCHON_SUPABASE_BASE_URL=http://host.docker.internal:65421`
  - `ARCHON_VENDOR_FORCE_PLACEHOLDER=0` (real vendor enabled).
- Health and CI:
  - Archon `/healthz` validates Supabase reachability using the resolved base URL and service key; `/ready` blocks until initial checks pass.
  - `make archon-smoke` should probe `/healthz` and a trivial Supabase REST call via the service role key after the stack is up (for example via `make -C pmoves bringup-with-ui PARALLEL=1 WAIT_T_LONG=300`).
- Bring‑up recipe (local CLI stack):
  - Run `make -C pmoves supa-start` and then `make -C pmoves supabase-boot-user` to stamp Supabase credentials into `pmoves/.env.local`.
  - Confirm `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `SUPA_REST_URL`, `ARCHON_SUPABASE_BASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set.
  - Start the full stack with `make -C pmoves bringup-with-ui PARALLEL=1 WAIT_T_LONG=300`, then run `make -C pmoves agents-headless-smoke` and `make -C pmoves smoke-gpu` to validate agents and GPU paths.

Submodule Strategy (Integrations as Repos)
- Rationale: separate upstream integration code from PMOVES.AI customization; enable independent CI, issue tracking, and GHCR publishing; reduce diff noise in this monorepo.
- Target submodules (new repos under the organization):
  - `PMOVES.YT`, `PMOVES.Archon`, `PMOVES.AgentZero`, `PMOVES.ChannelMonitor`, `PMOVES.JellyfinBridge`, `PMOVES.DeepResearch`, `PMOVES.SupaSerch`, `PMOVES.HiRAG.Gateway`, `PMOVES.GrayjayProxy`.
- Branching/namespacing:
  - Each integration maintains `main` mirroring upstream and a `pmoves/edition` branch carrying our overlays (config, small patches, default envs, health endpoints).
  - Policy: upstream PR first where viable; otherwise, keep overlay minimal and documented.
- Migration steps:
  1) Extract `pmoves/services/<integration>` into its repo preserving history (`git subtree split`), create `pmoves/edition` branch.
  2) Re‑introduce here as `git submodule` under `pmoves/integrations/<name>`.
  3) Update compose to prefer `image: ghcr.io/<org>/<name>:pmoves-latest`; keep `build:` path behind a `profile: [dev-local]` toggle.
  4) Add release workflow: build, SBOM, sign, push, publish provenance; update `pmoves/env.shared` image pin variables.

Hardened Image Catalog (Baseline Controls)
- Supply chain
  - Reproducible builds: pinned tags + digests; prefer distroless/alpine where appropriate.
  - SBOM: generate CycloneDX + SPDX; store as build artifact and attach to GHCR images.
  - Signing: Cosign keyless; verify in `make verify-all` using `cosign verify --certificate-oidc-issuer` policy.
  - Vulnerability scan: Trivy/Grype in CI; block on HIGH/CRITICAL with allowlist only for false positives.
- Runtime security (compose defaults per service)
  - Run as non‑root; read‑only root FS; `no-new-privileges: true`.
  - Linux hardening: drop all capabilities; add back only needed (`CAP_NET_BIND_SERVICE` for <1024 if applicable).
  - Seccomp/AppArmor: apply default Docker profiles; document exceptions.
  - Network: explicit `networks:` sections; disable inter‑service connectivity by default; egress allowlist for known APIs.
  - Resource limits: CPU/mem limits per service; healthchecks with backoff; restart policies `unless-stopped`.
  - Secrets: mount via env files or Docker secrets; avoid composing long secrets inline; rotate via `make supabase-boot-user` and CHIT bundles.
- Observability
  - Uniform `/healthz` and optional `/ready` endpoints; Prometheus metrics where available; Loki labels standardized.
  - Evidence capture: extend `make verify-all` to attach key logs and health JSON into `pmoves/docs/SESSION_IMPLEMENTATION_PLAN.md`.

Dynamic MCP Catalog (Docker‑backed Tools)
- Maintain a registry of Dockerized agent tools (MCP servers) used by integrations; map tool → image → version → ports → scopes.
- Add a generator script to emit a machine‑readable catalog (JSON) from compose + submodules, consumed by MCP clients.
- Security: run tools behind a local gateway with auth; use per‑tool networks; opt‑in exposure via profiles.

CI/CD Plan
- Per‑integration (in submodule repos): build → test → scan → SBOM → sign → push to GHCR; publish `:pmoves-latest` and immutable `:YYYYMMDD.sha` tags.
- Monorepo verification: `make verify-all` pulls pinned digests and runs smokes (`core`, `gpu`, `monitoring`, externals), failing fast on image provenance or healthcheck.
- Renovate: automate tag/digest bumps with PRs, gated by smokes.
 - Implemented: integrations GHCR workflow now emits SBOM (CycloneDX via Syft), runs Trivy (HIGH/CRITICAL gating), and Cosign‑signs all published tags (keyless).

Migration Checklist
- Extract services into submodules (priority: PMOVES.YT, Archon, Agent Zero, Channel Monitor).
- Update compose to image‑first flow with `profiles: [integrations]` and dev‑local build toggles. Archon now prefers submodule build by default in local bring‑up; use published‑images targets to override.
- Add override `pmoves/docker-compose.integrations.images.yml` and `make up-yt-published` to run PMOVES.YT from GHCR without local builds.
- Add security defaults to compose templates (`security_opt`, `read_only`, `cap_drop`, `user`, `healthcheck`).
 - Implemented: `pmoves/docker-compose.hardened.yml` adds non‑root, read‑only, tmpfs /tmp, cap_drop, and no‑new‑privileges for Archon, PMOVES.YT, and Channel Monitor. Use `make up-agents-hardened` and `make up-yt-hardened`.
- Pin images in `pmoves/env.shared`; document overrides.
- Wire CI for GHCR, Cosign, Trivy; add status badges to each repo README.

Verification Gates
- `make -C pmoves verify-all`:
  - Confirms image signatures and SBOM presence for all integrations.
  - Asserts `/healthz` 200 for Archon, Agent Zero, Channel Monitor, Jellyfin bridge, Hi‑RAG gateways (CPU/GPU) and Invidious endpoints.
  - Ensures Supabase REST reachability from Archon using the resolved Supabase base URL (`ARCHON_SUPABASE_BASE_URL` or `SUPA_REST_URL`‑derived) and service role key.

Open Items / Decisions
- Decision: Archon vendor contract is `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (service role); the wrapper maps `SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_KEY` accordingly and documents precedence above.
- Define minimal capability sets per service (TBD per container analysis).
- Establish MCP catalog schema and generation path.

References
- Compose: `pmoves/docker-compose.yml` and `pmoves/compose/*.yml`.
- Local CI: `docs/LOCAL_CI_CHECKS.md`.
- Smokes and runbooks: `pmoves/docs/SMOKETESTS.md`, `pmoves/docs/LOCAL_DEV.md`.
