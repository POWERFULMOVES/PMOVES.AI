# Docker Build Operator Guide

> Single reference for the PMOVES.AI Docker image lifecycle: local validation, CI pipelines, compose profiles, and model runners.

**Last Updated:** 2026-03-09
**See Also:** [Build Visibility Matrix](../PRODUCTION_AUDIT_DASHBOARD.md#build-visibility-matrix-mar-9-2026) | [Make Targets](MAKE_TARGETS.md) | [CI Images](../infrastructure/CI_IMAGES.md) | [Docker Secrets](../security/DOCKER_SECRETS_GUIDE.md)

---

## 1. Prerequisites

| Tool | Required | Install |
|------|----------|---------|
| Docker with buildx plugin | Yes | `docker buildx version` to verify |
| GHCR credentials | For push only | `make -C pmoves docker-login` or `gh auth login --with-token` |
| Python 3.10+ | For prepublish scripts | `python --version` |
| Trivy | For security scanning | `brew install trivy` / `sudo apt install trivy` |
| `make` | For target shortcuts | Pre-installed on most systems |

**Bootstrap the buildx builder:**

```bash
make -C pmoves buildx-setup
```

---

## 2. Image Matrix (`pmoves/images.yaml`)

`pmoves/images.yaml` is the **canonical source of truth** for all 29 PMOVES Docker images built via the `build-images.yml` manual dispatch workflow.

**Structure per entry:**

```yaml
- name: supaserch              # Human-readable name (used by Make targets)
  repo: .                       # Git repo (`.` = this repo, or external URL)
  ref: main                     # Git ref to checkout for external repos
  context: pmoves               # Docker build context path
  dockerfile: pmoves/services/supaserch/Dockerfile
  image: ghcr.io/darkxside/pmoves-supaserch
```

**Image categories:**

| Category | Count | Examples |
|----------|-------|---------|
| Submodule-backed | 18 | agent-zero, archon, hirag, jellyfin |
| In-tree (pmoves/services/) | 9 | extract-worker, channel-monitor, model-registry |
| GPU-heavy | 2 | ollama-cuda, hirag-gpu |

---

## 3. Local Build Validation

Local validation mirrors CI gates so issues are caught before push. All commands run from the repo root.

### Full Gate (Build + Trivy)

```bash
# All in-repo images
make -C pmoves ghcr-prepublish-inrepo

# Single image with Trivy
make -C pmoves ghcr-prepublish-one IMAGE=supaserch
```

### Build-Only (Skip Trivy for Speed)

```bash
# All in-repo images, build only
make -C pmoves ghcr-prepublish-inrepo-build

# Single image, build only
make -C pmoves ghcr-build-one IMAGE=supaserch
```

### Full Matrix (Including External Repos)

```bash
# Requires clone access to external submodule repos
make -C pmoves ghcr-prepublish-all
```

**Output:** Tab-separated summary with `build/trivy/status` columns per image. Per-image logs are written to `pmoves/docs/logs/ghcr-local-prepublish/`.

**Implementation:** `pmoves/tools/ghcr_local_prepublish.py` — reads `images.yaml` (for `build-images` matrix) or `integrations-ghcr.matrix.json` (for integrations matrix) and runs deterministic build + optional Trivy validation.

---

## 4. CI Pipelines

Three workflows build Docker images. See the [Build Visibility Matrix](../PRODUCTION_AUDIT_DASHBOARD.md#build-visibility-matrix-mar-9-2026) for the full service-to-pipeline mapping.

### `integrations-ghcr.yml` — Multi-Arch Production Pipeline

| Attribute | Value |
|-----------|-------|
| **Trigger** | push to main, PR to main, workflow_dispatch |
| **Matrix source** | `.github/workflows/integrations-ghcr.matrix.json` |
| **Images** | 16 |
| **Architecture** | amd64 + arm64 |
| **Security** | Trivy (HIGH/CRIT gate), Cosign (keyless signing), SBOM (10/16) |
| **When to use** | Primary pipeline for production images |

### `self-hosted-builds.yml` — Fast amd64 Builds

| Attribute | Value |
|-----------|-------|
| **Trigger** | push to main/develop, PR to main, workflow_dispatch |
| **Matrix source** | Inline in workflow YAML |
| **Images** | 9 in matrix (3 excluded from auto-trigger by path filters) |
| **Architecture** | amd64 only |
| **Security** | None (no Trivy, no Cosign, no SBOM) |
| **When to use** | Fast iteration on in-tree services; deploy to self-hosted staging/production |

**Note:** `agent-zero`, `archon`, and `pmoves-yt` are in the matrix but excluded from push/PR triggers via path filters — they're built multi-arch by `integrations-ghcr` instead. All 9 are still buildable via `workflow_dispatch`.

### `build-images.yml` — Manual Dispatch Full Matrix

| Attribute | Value |
|-----------|-------|
| **Trigger** | workflow_dispatch only |
| **Matrix source** | `pmoves/images.yaml` |
| **Images** | 29 |
| **Architecture** | amd64 (default; configurable) |
| **Security** | SBOM (all images) |
| **When to use** | Full rebuild, new image onboarding, one-off builds |

### Pipeline Selection Guide

| Scenario | Pipeline |
|----------|----------|
| Normal PR / push to main | `integrations-ghcr` (auto) + `self-hosted-builds` (auto) |
| Build a single image manually | `build-images` with dispatch filter |
| Verify build locally before CI | `make ghcr-prepublish-inrepo` or `make ghcr-build-one IMAGE=<name>` |
| Dispatch after local validation | `make -C pmoves ghcr-dispatch-all` or `make -C pmoves ghcr-dispatch-supaserch` |

---

## 5. Compose Profiles

Docker Compose uses profiles to organize services into logical groups. Start a profile with:

```bash
docker compose --profile <name> up -d
```

| Profile | Services | Notes |
|---------|----------|-------|
| `agents` | agent-zero, archon, archon-ui, mesh-agent, publisher-discord | Core orchestration |
| `workers` | extract-worker, langextract, notebook-sync, pdf-ingest | Background processing |
| `orchestration` | supaserch, deepresearch, model-registry | Research + model catalog |
| `yt` | pmoves-yt, ffmpeg-whisper, bgutil-pot-provider | YouTube ingestion |
| `gpu` | hi-rag-gateway-v2-gpu, gpu-orchestrator, ollama | GPU-accelerated services |
| `tts` | ultimate-tts-studio, flute-gateway | Voice synthesis |
| `monitoring` | prometheus, grafana, loki, promtail, cadvisor | Observability stack |
| `health` | wger, wger-nginx | Health/fitness integration |
| `wealth` | firefly-iii, firefly-db | Finance integration |
| `remote` | invidious | Remote media proxy |
| `vpn` | tailscale | VPN connectivity |
| `botz` | botz-gateway | Skills marketplace |

### Override Files

| File | Purpose |
|------|---------|
| `docker-compose.agents.images.yml` | Switch agent services to published GHCR images |
| `docker-compose.integrations.images.yml` | Switch integration services to published GHCR images |
| `docker-compose.gpu.yml` | GPU runtime configuration (nvidia) |
| `docker-compose.arm64.override.yml` | arm64-specific image overrides |

**Image switching example** (local build → published):

```bash
docker compose -f docker-compose.yml -f docker-compose.agents.images.yml --profile agents up -d
```

### Make Target Shortcuts

```bash
make -C pmoves up-agents          # agents profile
make -C pmoves up-media           # media analyzers
make -C pmoves up-yt              # YouTube ingestion
make -C pmoves up-model-management # model-registry + gpu-orchestrator
make -C pmoves up-external        # Wger, Firefly, Open Notebook, Jellyfin
```

---

## 6. Model Runners

PMOVES uses a layered model management architecture:

### TensorZero Gateway (Port 3030)

Centralized LLM routing proxy for all model providers (OpenAI, Anthropic, Venice, Ollama). All services call TensorZero rather than providers directly.

```bash
# Test inference
curl -X POST http://localhost:3030/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "Hello"}]}'

# Test embeddings
curl -X POST http://localhost:3030/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma_embed_local", "input": "Text to embed"}'
```

**Metrics:** ClickHouse-backed at port 8123. UI dashboard at port 4000.

### Ollama (GPU Profile)

Local model serving with GPU acceleration. Started via `--profile gpu`.

### Model Registry (Port 8110)

Dynamic model catalog backed by Supabase (`pmoves_core.model_*` tables). Provides service-to-model mappings.

### GPU Orchestrator (Port 8200)

VRAM management and model lifecycle via NATS (`mesh.gpu.*` subjects). Coordinates model loading/unloading across GPU resources.

### Operator Commands

```bash
make -C pmoves up-model-management    # Start model-registry + gpu-orchestrator
make -C pmoves models-sync-dynamic    # Sync TensorZero config from Supabase catalog
make -C pmoves models-seed-ollama     # Pre-pull Ollama models from registry
make -C pmoves models-registry-snapshot  # Export registry state for audit
```

**Reference:** [`MODEL_REGISTRY.md`](../MODEL_REGISTRY.md) | [`LOCAL_MODEL_SETUP.md`](../PMOVESCHIT/LOCAL_MODEL_SETUP.md) | [`MODEL_FABRIC_CONTRACT.md`](../MODEL_FABRIC_CONTRACT.md) | [`MODEL_SOURCE_OF_TRUTH.md`](../MODEL_SOURCE_OF_TRUTH.md)

---

## 7. Troubleshooting

### Trivy Gate Failures

Per-image scan logs are written to `pmoves/docs/logs/ghcr-local-prepublish/`. Check the log for the failing image to see which CVEs triggered the HIGH/CRIT gate.

```bash
cat pmoves/docs/logs/ghcr-local-prepublish/<image-name>.log
```

### Build Context Errors

Verify the `context` field in `images.yaml` matches the Dockerfile location. In-tree services use `context: pmoves` (since CI runs from repo root), not `./services/<name>`.

### Runner Queue Starvation

Self-hosted runners can get blocked when too many jobs queue up (known AB-9 blocker).

```bash
# Check queued runs
gh run list --status queued --limit 20

# Cancel stale runs
make -C pmoves ci-queue-drain-nonpr        # Dry-run
make -C pmoves ci-queue-drain-nonpr-apply  # Execute cancellations

# Check runner status
make -C pmoves ci-runners-check
make -C pmoves ci-runners-local-cert-status
```

### Port Conflicts

Consult [`PORT_REGISTRY.md`](PORT_REGISTRY.md) and the **CI Pipeline** annotations in [`.claude/context/services-catalog.md`](../../.claude/context/services-catalog.md) for port allocations.

### Common Build Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `curl: not found` in healthcheck | Image missing curl | Use `wget -q --spider` or add `curl` to Dockerfile |
| `context: .` not finding files | Wrong context path | In-tree services use `context: pmoves`, not `./services/` |
| PyAV (`av`) build failure | Missing system deps | Add `gcc`, `libavformat-dev` to Dockerfile |
| Buildx builder not found | Builder not initialized | `make -C pmoves buildx-setup` |
