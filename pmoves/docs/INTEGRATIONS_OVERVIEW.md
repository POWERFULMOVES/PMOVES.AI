# PMOVES.AI Integration Layer

> **Symbiotic Enhancement** --- PMOVES.AI connects to and enhances any repository through five integration systems: a Skill Registry maps submodules to CLI skills, CHIT tools encode/decode geometric packets and secrets, a secrets pipeline ensures credentials flow safely through tiers, GPU orchestration manages VRAM and models, and damage-control hooks protect the developer workflow.

---

## The Five Integration Systems

### 1. Skill Registry & Context Tags

**What:** Declarative JSON manifest mapping 49 submodules to CLI skills, context tiers (1--4), and 12 domain tags. The registry is the single source of truth for which skills, context files, and agent docs belong to each submodule.

| Asset | Path |
|-------|------|
| Registry | `pmoves/configs/submodule_skill_registry.json` |
| Tag injector | `pmoves/tools/skill_tag_injector.py` |
| Validator | `pmoves/tools/skill_registry_validate.py` |
| Make target | `make -C pmoves skill-registry-validate` |

**Domain tags:** `orchestration`, `media`, `voice`, `knowledge`, `documents`, `infra`, `llm`, `math`, `ci`, `memory`, `sandbox`, `workflows`

**Deep dives:**
- [Submodule Integration Contract](SUBMODULE_INTEGRATION_CONTRACT.md) --- overlay structure and contract rules
- [Submodule Integration Guide](PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md) --- tier credentials and bootstrap flow

---

### 2. CHIT Tools & Scripts

**What:** Python toolchain (13+ modules) for CGP encoding/decoding, HMAC-SHA256 signing, AES-GCM encryption, spectral filtering via Riemann zeta zeros, and multimodal decode via CLIP/CLAP.

| Asset | Path |
|-------|------|
| Secret encoder | `pmoves/tools/chit_encode_secrets.py` |
| Secret decoder | `pmoves/tools/chit_decode_secrets.py` |
| Security library | `pmoves/tools/chit_security.py` |
| Text decoder | `pmoves/tools/chit/chit_decoder.py` |
| Multimodal decoder | `pmoves/tools/chit/chit_decoder_mm.py` |
| Zeta filter | `pmoves/tools/zeta_filter.py` |

**CLI skills:** `/chit:encode`, `/chit:decode`, `/chit:visualize`, `/chit:bus`

**Deep dives:**
- [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md) --- full catalog of all 13+ tools with usage examples
- [CHIT Documentation Suite](PMOVESCHIT/README.md) --- 5-layer protocol/conceptual/applied/vision/reference iceberg
- [CHIT Integration Status](CHIT_INTEGRATION_STATUS.md) --- service-by-service CGP adoption

---

### 3. Secrets Management Pipeline

**What:** A 6-step cryptographic funnel that transforms secrets from a single `env.shared` source into 6 tiered environment files via CHIT Geometry Packets. Zero human interaction with generated files.

| Asset | Path |
|-------|------|
| Canonical command | `make -C pmoves secrets-funnel` |
| CLI skill | `/deploy:secrets-funnel` |
| Encoder | `pmoves/tools/chit_encode_secrets.py` |
| Sync engine | `pmoves/tools/secrets_sync.py` |
| Manifest (98 entries) | `pmoves/chit/secrets_manifest.yaml` |
| Hardening audit | `pmoves/tools/secrets_hardening_audit.py` |

**6 tiers:** `data` (infrastructure), `api` (data-access), `worker` (background), `media` (ingestion), `agent` (orchestration), `llm` (LLM gateway --- only tier with external API keys)

**Deep dives:**
- [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) --- the complete 6-step funnel, tier architecture, and all tools
- [Secrets Management Guide](SECRETS.md) --- universal credential management
- [Secrets Onboarding](SECRETS_ONBOARDING.md) --- 5-minute quick start
- [Docker Secrets Guide](DOCKER_SECRETS_GUIDE.md) --- Docker/Kubernetes integration
- [GitHub Secrets Guide](GITHUB_SECRETS_GUIDE.md) --- CI/CD pipeline secrets

---

### 4. GPU Orchestration

**What:** Dynamic GPU resource management: VRAM tracking, model lifecycle (load/unload/idle-evict), priority queues, and session tracking. Supports Ollama, vLLM, and TTS providers.

| Asset | Path |
|-------|------|
| GPU Orchestrator API | Port 8200 (`http://localhost:8200/api/gpu/`) |
| Model registry | `pmoves/config/gpu-models.yaml` |
| Smoke test | `pmoves/tools/smoke_gpu.py` |
| Profile loader | `pmoves/tools/profile_loader.py` |
| Glancer (system metrics) | Port 9105 |

**CLI skills:** `/gpu:status`, `/gpu:models`, `/gpu:optimize`, `/model:load`, `/model:unload`

**Make targets:** `up-gpu`, `smoke-gpu`, `gpu-rerank-evidence`, `recreate-v2-gpu`, `smoke-qwen-rerank`

**Deep dive:**
- [GPU Orchestration Guide](GPU_ORCHESTRATION_GUIDE.md) --- full API reference, make targets, hardware profiles, NATS events

---

### 5. Damage Control & Developer Hooks

**What:** Pre/post-tool hooks protecting the developer workflow from destructive operations and adversarial prompt injection. 150+ patterns in `patterns.yaml` classify commands as block, ask, or zero-access.

| Asset | Path |
|-------|------|
| Pre-tool hook | `.claude/hooks/pre-tool.sh` |
| Post-tool hook | `.claude/hooks/post-tool.sh` |
| Pattern config | `.claude/hooks/damage-control/patterns.yaml` |
| Bash damage control | `.claude/hooks/damage-control/bash-tool-damage-control.py` |
| Edit damage control | `.claude/hooks/damage-control/edit-tool-damage-control.py` |
| Write damage control | `.claude/hooks/damage-control/write-tool-damage-control.py` |

**GAN defense model:** Pipeline-bypass patterns detect commands that skip canonical make targets and surface `ask` prompts with the correct operational path (Known Roads).

**NATS telemetry:** Post-tool hook publishes to `claude.code.tool.executed.v1` for observability in Grafana/Supabase.

**Deep dive:**
- [Hooks README](../../.claude/hooks/README.md) --- installation, event format, NATS integration
- [Known Roads table](../../.claude/CLAUDE.md) --- dangerous ops mapped to canonical make targets

---

## Document Index

All integration-related documentation organized by domain.

### Integration Architecture

| Document | Description |
|----------|-------------|
| [Service Integration Guide](INTEGRATIONS.md) | Service auth, API endpoints, troubleshooting |
| [Submodule Integration Guide](PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md) | Tier credentials, bootstrap, universal integration |
| [Submodule Integration Contract](SUBMODULE_INTEGRATION_CONTRACT.md) | `pmoves-integrations/` overlay rules |
| [External Integrations Bring-Up](EXTERNAL_INTEGRATIONS_BRINGUP.md) | Wger, Firefly III, Jellyfin, Open Notebook |
| [E2B Integration](E2B_INTEGRATION.md) | Agentic computer use (sandbox) |
| [Archon Integration](ARCHON_INTEGRATION.md) | Nested submodule architecture |
| [Monitoring Integration](MONITORING_INTEGRATION.md) | Prometheus, Grafana, Loki stack |

### Secrets & Credentials

| Document | Description |
|----------|-------------|
| [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) | Complete 6-step funnel reference |
| [Secrets Management Guide](SECRETS.md) | Universal credential management |
| [Secrets Onboarding](SECRETS_ONBOARDING.md) | 5-minute quick start |
| [Docker Secrets Guide](DOCKER_SECRETS_GUIDE.md) | Docker/Kubernetes secrets |
| [GitHub Secrets Guide](GITHUB_SECRETS_GUIDE.md) | CI/CD pipeline secrets |

### CHIT & Geometry

| Document | Description |
|----------|-------------|
| [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md) | All 13+ Python tools with usage |
| [CHIT Documentation Suite](PMOVESCHIT/README.md) | 5-layer iceberg index |
| [CHIT Integration Status](CHIT_INTEGRATION_STATUS.md) | Service-by-service adoption |
| [CHIT User Guide](CHIT_USER_GUIDE.md) | Encoding/decoding user guide |

### GPU & Hardware

| Document | Description |
|----------|-------------|
| [GPU Orchestration Guide](GPU_ORCHESTRATION_GUIDE.md) | Full GPU management reference |
| [Hardware Profiles](../../.claude/context/hardware-profiles.md) | Multi-node GPU fleet config |

### Developer Workflow

| Document | Description |
|----------|-------------|
| [Hooks README](../../.claude/hooks/README.md) | Pre/post-tool hooks, damage control |
| [Documentation Index](../../.claude/context/documentation-index.md) | Cross-reference navigation matrix |

---

## Reading Paths

Pick the path that matches your role:

**New developer onboarding:**
> [Secrets Onboarding](SECRETS_ONBOARDING.md) --> [Service Integration Guide](INTEGRATIONS.md) --> `/deploy:up` --> `/deploy:smoke-test`

**Submodule integrator:**
> [Submodule Integration Contract](SUBMODULE_INTEGRATION_CONTRACT.md) --> [Submodule Integration Guide](PMOVES.AI_SUBMODULE_INTEGRATION_GUIDE.md) --> `skill_tag_injector.py` --> `skill_registry_validate.py`

**CHIT developer:**
> [CHIT Documentation Suite](PMOVESCHIT/README.md) --> [CHIT Tools Catalog](CHIT_TOOLS_CATALOG.md) --> [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) --> `/chit:encode`

**GPU/ML engineer:**
> [GPU Orchestration Guide](GPU_ORCHESTRATION_GUIDE.md) --> `/gpu:status` --> `/model:load` --> `smoke_gpu.py`

**Security/ops:**
> [Hooks README](../../.claude/hooks/README.md) --> `patterns.yaml` --> [Secrets Pipeline Reference](SECRETS_PIPELINE_REFERENCE.md) --> `/deploy:audit-layers`

---

## CLI Skills Quick Reference

| Category | Skills | Description |
|----------|--------|-------------|
| **CHIT** | `/chit:encode`, `/chit:decode`, `/chit:visualize`, `/chit:bus` | CGP encoding, decoding, visualization, GEOMETRY BUS |
| **Deploy** | `/deploy:up`, `/deploy:services`, `/deploy:secrets-funnel`, `/deploy:preflight`, `/deploy:audit-layers`, `/deploy:bootstrap-env`, `/deploy:smoke-test` | Full deployment lifecycle |
| **GPU** | `/gpu:status`, `/gpu:models`, `/gpu:optimize`, `/model:load`, `/model:unload` | GPU and model management |
| **Health** | `/health:check-all`, `/health:metrics`, `/health:quick` | Service health monitoring |
| **Test** | `/test:pr`, `/test:smoke` | Testing workflows |

---

## Make Targets Quick Reference

| Target | Purpose |
|--------|---------|
| `make -C pmoves secrets-funnel` | Run the complete 6-step secrets pipeline |
| `make -C pmoves up` | Start core services |
| `make -C pmoves up-gpu` | Start with GPU profile |
| `make -C pmoves verify-all` | Full smoke test suite |
| `make -C pmoves smoke-gpu` | Validate GPU rerank path |
| `make -C pmoves skill-registry-validate` | Validate skill registry |
| `make -C pmoves secrets-audit` | Audit secrets hardening |
| `make -C pmoves docker-prune` | Safe Docker cleanup |
| `make -C pmoves volume-reset SERVICE=...` | Reset specific service volume |
