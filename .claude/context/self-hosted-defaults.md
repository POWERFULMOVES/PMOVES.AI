# Self-Hosted Defaults — Branded URLs, OAuth, Production

**Tier 2 — On-demand context.** Load when authoring or reviewing artifacts that surface URLs, choose providers, or wire auth. Newly minted agents and skills MUST default to these conventions instead of generic localhost or SaaS endpoints. Override only with an explicit, documented reason.

## Why this exists

PMOVES.AI runs entirely on self-hosted infrastructure: an on-prem ai-lab (Z890, 3090Ti) plus a Hostinger VPS fleet (KVM4-1, KVM4-2, KVM2) glued together via Tailscale/Headscale and fronted by Cloudflare DNS. The mint workflow (`/archon:mint-*`) and any LLM-authored automation that publishes URLs, configures auth, or chooses a provider must point at the branded surface, not at SaaS defaults the model might infer.

When a downstream agent is unsure, it should query this doc, never invent.

## Topology (operating reality)

| Node | Role | Tailnet name | Public surface |
|------|------|--------------|----------------|
| **Z890 (ai-lab)** | Dev + GPU (3090Ti); full Docker Compose mesh | `pmoves-z890` | None directly; reached over Tailscale |
| **5090** | Primary GPU (pending hardware) | `pmoves-5090` | None |
| **KVM4-1** | API gateway VPS + Tailscale egress exit | `pmoves-kvm4-1` | `api.pmoves.ai`, `agent.pmoves.ai`, `rag.pmoves.ai`, `gateway.pmoves.ai` |
| **KVM4-2** | Data/storage VPS (Supabase, NATS, MinIO, Neo4j, Qdrant, Meilisearch, monitoring) | `pmoves-kvm4-2` | `supabase.pmoves.ai`, `nats.pmoves.ai`, `minio.pmoves.ai`, `grafana.pmoves.ai`, `search.pmoves.ai` |
| **KVM2** | Reverse proxy (nginx SSL termination) + RustDesk relay | `pmoves-kvm2` | All other subdomains terminate here before backhauling |
| **Cloudflare Edge** | DNS + CI router Worker | — | Public DNS for `pmoves.ai` zone |

Full topology: [`pmoves/docs/operations/TOPOLOGY.md`](../../pmoves/docs/operations/TOPOLOGY.md). Worker source: [`deploy/cloudflare/worker.js`](../../deploy/cloudflare/worker.js).

## Branded DNS — canonical subdomains

DNS zone: **`pmoves.ai`** (Cloudflare-managed). Subdomains and their backing services:

| Subdomain | Service | Backing node | Internal port |
|-----------|---------|--------------|---------------|
| `api.pmoves.ai` | Gateway Agent (request router) | KVM4-1 | `:8080` upstream |
| `agent.pmoves.ai` | Agent Zero MCP + UI | KVM4-1 | `:8080` / `:8081` |
| `rag.pmoves.ai` | Hi-RAG v2 (GPU preferred) | KVM4-1 | `:8087` |
| `tts.pmoves.ai` | Ultimate-TTS-Studio | KVM4-1 | `:7860` / `:7861` |
| `n8n.pmoves.ai` | n8n workflow engine | KVM4-1 | `:5678` |
| `grafana.pmoves.ai` | Grafana | KVM4-2 | `:3000` |
| `search.pmoves.ai` | SupaSerch / DeepResearch front | KVM4-1 | TBD |
| `nats.pmoves.ai` | NATS WebSocket gateway | KVM4-2 | `:8080` (NATS WS) |
| `minio.pmoves.ai` | MinIO S3 + console | KVM4-2 | `:9000` / `:9001` |
| `headscale.pmoves.ai` | Headscale control plane | KVM4-2 | `:8080` |
| `ci.pmoves.ai` | CI runner router (Cloudflare Worker) | Cloudflare Edge | — |
| `supabase.pmoves.ai` | Supabase Studio + REST | KVM4-2 | `:8000` (Kong) |
| `archon.pmoves.ai` | Archon UI + MCP | KVM4-1 | `:3737` / `:8091` |
| `cipher.pmoves.ai` | Cipher Memory API | KVM4-2 | `:8105` |

> **Rule for minted artifacts**: never hardcode `localhost:<port>` in a configuration that ships to operators. Use the `pmoves.ai` subdomain. Local dev overrides via `.env` files in `pmoves/configs/env/`.

## Authentication — Google OAuth via Supabase

**Identity provider**: Google OAuth (operator confirmed). Wiring:

1. **Supabase Auth** is the OAuth broker. Project URL: `https://supabase.pmoves.ai`. Configure Google as an enabled provider in Supabase Studio → Authentication → Providers → Google.
2. **Redirect URIs** registered in Google Cloud Console:
   - `https://supabase.pmoves.ai/auth/v1/callback`
   - `https://<subdomain>.pmoves.ai/auth/callback` for each app surface (Archon UI, Agent Zero UI, n8n).
3. **PKCE flow** is mandatory for SPA surfaces (Next.js UI uses `@supabase/ssr` already; see `pmoves/ui/`).
4. **JWT claims** include `email`, `email_verified`, `provider: 'google'`. PMOVES-specific role added via Supabase RLS policies (`role: 'creator' | 'admin' | 'agent'`).
5. **Service-to-service auth**: not OAuth. Use Supabase service role keys for backend, NATS user/pass (`nats:pmoves`) for event bus, mTLS where Tailscale endpoints face other Tailscale endpoints.

### When to require OAuth

| Surface | OAuth required? | Notes |
|---------|-----------------|-------|
| Public website / `pmoves.ai` root | No | Anonymous browsing OK |
| Creator onboarding (`/archon:creator-onboard`) | **Yes** | Identity tied to Supabase user row in `archon_minted_artifacts` (Wave 1 schema) |
| Agent minting (`/archon:mint-agent`) | **Yes** — creator scope | Authored agent tied to creator; QA agent enforces |
| Skill minting (`/archon:mint-skill`) | **Yes** — creator scope | Same |
| Hook/MCP server installation | No | Operator-only, file-level |
| Internal service-to-service | No | Use service role keys or NATS auth |

### Where to look up live OAuth config

- Supabase: `https://supabase.pmoves.ai/project/<id>/auth/providers` (Studio)
- Env var template: `pmoves/configs/env/.env.template.production` (look for `SUPABASE_AUTH_*`, `GOOGLE_OAUTH_*`)
- Secrets pipeline: `/deploy:secrets-funnel` (CHIT-encoded source → tier env files)

## Provider preferences — self-hosted FIRST

When a minted artifact picks a provider, prefer self-hosted alternatives over SaaS. The roadmap deliberately scoped these to Wave 1 because they need API tokens (or self-hosted equivalents):

| Concern | SaaS default to AVOID | Self-hosted preferred | Status |
|---------|----------------------|----------------------|--------|
| LLM provider | OpenAI, Anthropic (direct) | **TensorZero gateway** at `:3030` (routes to Venice, Ollama, etc.) | ✅ Live |
| Embeddings | OpenAI embeddings | **TensorZero embedding endpoint** with Qwen3-Embedding-4B (2560d) or 8B (4096d) | ✅ Live |
| Error tracking | Sentry (cloud) | **Glitchtip** (self-hosted Sentry-compatible) at `errors.pmoves.ai` | ⏳ Wave 1 |
| Metrics | Datadog | **Prometheus** at `:9090` / Grafana at `grafana.pmoves.ai` | ✅ Live |
| Logs | Loki Cloud / Splunk | **Loki** at `:3100` (local) | ✅ Live |
| Object storage | S3 (AWS) | **MinIO** at `minio.pmoves.ai` | ✅ Live |
| Vector DB | Pinecone / Weaviate cloud | **Qdrant** at `:6333` (within Hi-RAG v2) | ✅ Live |
| Graph DB | Neo4j Aura | **Neo4j** at `:7474` (self-hosted) | ✅ Live |
| Search | Algolia / Elasticsearch cloud | **Meilisearch** at `:7700` | ✅ Live |
| Auth provider | Auth0, Clerk | **Supabase Auth + Google OAuth** at `supabase.pmoves.ai` | ✅ Live |
| Workflow engine | Zapier, n8n.cloud | **n8n** at `n8n.pmoves.ai` (self-hosted) | ✅ Live |
| Mesh networking | Tailscale (SaaS) | **Headscale** at `headscale.pmoves.ai` | ✅ Live |
| Web search MCP | Brave Search (paid API) | **SupaSerch + DeepResearch** internal (still needs grounding source — Wave 1 evaluation) | ⏳ Wave 1 |
| Issue tracking | Linear, Jira | **GitHub Issues + AGNOTE4482PHI.t1.md** (active claim register) | ✅ Live |

> **Rule for minted artifacts**: when wiring a dependency, check this table first. If the SaaS option appears in the "AVOID" column, halt and use the self-hosted equivalent. If neither covers the need, log a request to extend this table (don't silently default to SaaS).

## NATS subject branding

All PMOVES NATS subjects follow `<domain>.<entity>.<event>.v<n>` and live under one of these branded namespaces:

| Namespace | Owner | Examples |
|-----------|-------|----------|
| `archon.*` | Archon factory/mint | `archon.mint.agent.v1`, `archon.qa.result.v1`, `archon.work_order.github.v1` |
| `chit.*` | CHIT signing/trails | `chit.signed.v1`, `chit.cgp.v1` |
| `geometry.*` | GEOMETRY BUS | `geometry.cgp.v1`, `geometry.swarm.meta.v1`, `geometry.event.v1` |
| `tokenism.*` | Tokenism Simulator | `tokenism.cgp.ready.v1`, `tokenism.simulation.result.v1` |
| `p7.*` | P7 stage manager | `p7.nats.launch`, `p7.nats.session` |
| `ingest.*` | Media/content ingestion | `ingest.youtube.v1`, `ingest.pdf.v1` |
| `research.*` | DeepResearch / SupaSerch | `research.deepresearch.request.v1`, `research.deepresearch.result.v1` |
| `botz.*` | (legacy/archived 2026-04-19) | `botz.agent.enrolled.v1` — kept for compatibility only |
| `mesh.*` | Health snapshots | `mesh.health.snapshot.v1` |
| `persona.*` | Persona publication | `persona.publish.v1`, `persona.update.v1` |

Live registries:
- `.claude/context/nats-subjects.md` — full subject catalog
- `.claude/context/geometry-nats-subjects.md` — GEOMETRY BUS subjects

> **Rule for minted artifacts**: a new NATS subject must (a) fit an existing namespace OR (b) come with a documented namespace addition in this list before merge. `nats-subject-auditor` enforces.

## Production vs Dev — distinguishing in code

| Env | Where it points | How to detect |
|-----|----------------|---------------|
| **dev** | `localhost:<port>` (Z890 ai-lab Docker Compose) | `PMOVES_ENV=dev` or absence of all of the below |
| **staging** | `pmoves-cloudstartup.<region>.hostinger.com` (CI staging) | `PMOVES_ENV=staging` |
| **prod** | `*.pmoves.ai` (KVM4-1/KVM4-2 via KVM2/Cloudflare) | `PMOVES_ENV=prod` |

Env file template per tier: `pmoves/configs/env/.env.template.{dev,staging,prod}`. Operators regenerate via `/deploy:secrets-funnel` (CHIT-encoded source → tier env files).

Minted artifacts should:
1. Read endpoint URLs from env vars, not hardcode.
2. Provide a sensible dev default (localhost) AND a clear prod target (`pmoves.ai` subdomain).
3. Never assume the SaaS endpoint exists.

## Cross-references

- Topology master: `pmoves/docs/operations/TOPOLOGY.md`
- Service catalog (ports, /healthz): `.claude/CATALOG.md`
- Secrets pipeline: `pmoves/docs/operations/SECRETS_PIPELINE.md` + `/deploy:secrets-funnel`
- Cloudflare CI router: `deploy/cloudflare/worker.js`
- Tier env templates: `pmoves/configs/env/`
- NATS subject catalog: `.claude/context/nats-subjects.md`, `.claude/context/geometry-nats-subjects.md`
- Hardware profiles: `.claude/context/hardware-profiles.md`
- Runner topology condensed: `.claude/context/runner-topology.md`

## Quick check before publishing any artifact

- [ ] No hardcoded `localhost:<port>` in operator-shipped config.
- [ ] All URLs use `*.pmoves.ai` (or pull from env var).
- [ ] If auth is required → Supabase Auth + Google OAuth (PKCE for SPAs).
- [ ] No SaaS provider chosen where a self-hosted equivalent exists (see provider table).
- [ ] NATS subjects fit a branded namespace.
- [ ] Service-to-service uses service role / NATS auth (not OAuth).

If any unchecked, halt and revise before publishing. `archon-qa-agent` will enforce in Wave 0.5 task #11.
