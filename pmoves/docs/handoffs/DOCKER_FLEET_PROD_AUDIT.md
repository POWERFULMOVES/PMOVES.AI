# Docker Fleet Production-Readiness Audit (synthesized)

This is a synthesis task — I have all five subsystem audits in the prompt and need to produce a single prioritized remediation plan. The repo context (CLAUDE.md, memory) is already loaded. Let me write the plan directly.

# PMOVES Dynamic Fleet — Docker Production-Readiness Remediation Plan

Synthesized by 4090-CLAUDE (deploy/CI spine) from 5 subsystem audits. Drives PRs + a Z890 handoff.

> ## ⚠️ VERIFICATION CORRECTIONS (2026-06-23) — READ BEFORE ACTING
> The audit agents read a checkout **291 commits behind main** and several findings are stale/hallucinated. **Verify every item against current `origin/main` before implementing.** Confirmed so far:
> - ✅ **REAL & SHIPPED (PR #1868):** `docker system prune -af --volumes` on self-hosted runners (4× `runner-maintenance.yml` + 2× `integrations-ghcr.yml`) — data-loss hazard on co-hosted fleet nodes (SPARK/Z890). This was *under*-weighted by the audit (buried as P2) but is the most important finding. Fixed → safe image/builder prune.
> - ❌ **PHANTOM — P1-G "`cataclysm` missing restart":** `cataclysm` is a **network** (`cataclysm-net`), not a service. No fix needed.
> - ❌ **PHANTOM — P2 "Qdrant `QDRANT_RECREATE_ON_DIM_MISMATCH=false` missing":** already `=false` everywhere (compose default + code default `worker.py:158`). Guard is already in place.
> - ✅ **REAL — log rotation missing:** confirmed no `logging:`/`max-size` in main compose. Best fixed at **daemon level** (`daemon.json log-opts`), host-coordinated — not a solo compose PR.
> - ⏭️ **STALE — P1-D "free-disk after buildx race":** already fixed on main (`integrations-ghcr.yml` frees disk before buildx). `self-hosted-builds*.yml` are **dormant** (`build-gpu` is `if:false`, dispatch-only) → low priority.
> Treat the rest of this plan as DIRECTIONAL, not authoritative. Re-verify P2/P3 compose limit/healthcheck claims before editing.

---

## 1. Verdict per subsystem

| Subsystem | Verdict | Headline gap |
|---|---|---|
| **Buildx/BuildKit builders** | Properly configured (CI path), **scaffolded for persistence** | No GC bounds on persistent builders; disk-free step runs *after* buildx setup (P1 race). |
| **Self-hosted runners** | **Scaffolded only** for disk hygiene | No per-job workspace cleanup + no pre-flight disk gate → **recurring "No space left on device" root cause**. |
| **Model runners** | Properly configured (GPU serving stack) | Docker Model Runner unused (fine); real risks are unpinned model images + missing `QDRANT_RECREATE_ON_DIM_MISMATCH=false` (data-loss). |
| **Engine/daemon + disk hygiene** | **Scaffolded only** | Zero container log rotation + no VPS `daemon.json` → unbounded `json-file` logs are the *other half* of the disk-full root cause. |
| **Compose (prod + modular)** | Properly configured (~99% health/restart) | Small coverage gaps (3 services no limits/health, `cataclysm` no restart) + hardening anchors not applied fleet-wide. |

---

## 2. P1 fixes (do first)

These break or risk production self-host **now**. The two disk-full P1s (runner cleanup + log rotation) are the same root incident from two angles — ship together.

### P1-A — Container log rotation (the disk-full root cause, half 1) · **Z890-coordinated + VPS**
Unbounded `json-file` logs fill `/var/lib/docker/containers/<id>/*.log`. Add a global YAML logging anchor in `pmoves/docker-compose.base.yml` and merge into all services:
```yaml
x-logging-production: &x-logging-production
  logging:
    driver: json-file
    options: { max-size: "50m", max-file: "3" }
```
Per node-class: Z890 (`max-file: 2`), KVM4 data tier (`max-file: 5, max-size: 100m`). Doc: https://docs.docker.com/config/containers/logging/json-file/
- **Lane:** 4090 can author the anchor + `docker compose config` validate; **Z890 + VPS apply** (touches running daemons → handoff).

### P1-B — Per-job workspace cleanup on self-hosted runners (disk-full root cause, half 2) · **4090-lane**
No step cleans `/tmp/runner/_work` between sequential matrix jobs. Add to the END of every self-hosted build job in `self-hosted-builds.yml` + `self-hosted-builds-hardened.yml`:
```yaml
- name: Clean workspace
  if: always()
  run: rm -rf "$RUNNER_WORKSPACE/_work"/* || true; df -h /
```
Doc: https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners
- **Lane:** 4090 authors workflow YAML; validate locally with `actionlint`. Pure workflow edit — no node access needed.

### P1-C — Disk-space pre-flight gate before build dispatch · **4090-lane**
Add a `check-disk-capacity` job (≥20GB free) as a `needs:` dependency for build jobs across both self-hosted build workflows:
```yaml
- run: |
    AVAIL=$(df / | awk 'NR==2{print $4}'); REQ=$((20*1024*1024))
    [ "$AVAIL" -ge "$REQ" ] || { echo "::error::<20GB free"; exit 1; }
```
Doc: https://docs.docker.com/build/building/best-practices/#managing-runner-disk-space
- **Lane:** 4090 (workflow YAML).

### P1-D — Move "Free disk space" BEFORE buildx setup in `integrations-ghcr.yml` · **4090-lane**
Reorder lines 265–270 to run *before* line 273 buildx setup (currently a race that can corrupt buildx bootstrap on a near-full runner). Also fix the PR-validation job's ordering.
- **Lane:** 4090 (workflow YAML, mechanical reorder).

### P1-E — VPS `daemon.json` (KVM4-1/-2, KVM2) · **VPS, IaC-tracked**
No version-controlled daemon config on production VPS → no log rotation/live-restore. Create `/etc/docker/daemon.json`:
```json
{ "storage-driver":"overlay2","log-driver":"json-file",
  "log-opts":{"max-size":"50m","max-file":"3"},
  "live-restore":true,"icc":false,"userland-proxy":false }
```
Track in `pmoves/docs/operations/VPS_DAEMON_BOOTSTRAP.md` + Ansible/Terraform (PMOVES-Danger-infra IaC pattern). Doc: https://docs.docker.com/config/daemon/ , https://docs.docker.com/engine/containers/live-restore/
- **Lane:** Not 4090. Use Hostinger MCP + vps-deployer agent (per memory: never raw SSH). Requires `daemon-reload && restart docker` → coordinate maintenance window.

### P1-F — Z890 shared-builder coordination gate (governance) · **Z890-coordinated**
Z890 is workstation + GPU runner + inference host. Any persistent buildx/`buildkitd.toml`/GC change must not be unilateral. Create `pmoves/docs/operations/BUILDER_COORDINATION.md`, file a claim in `AGNOTE4482PHI.t1.md` before changes. Doc: https://docs.docker.com/build/builders/#driver-options
- **Lane:** doc is 4090-lane; the *gate it enforces* is Z890.

### P1-G — `cataclysm` missing restart policy · **4090-lane**
`cataclysm` has no `restart:` → no auto-recovery on crash. Add `restart: unless-stopped`. Doc: https://docs.docker.com/compose/compose-file/compose-file-v3/#restart_policy

---

## 3. P2 / P3

### P2 — Should fix

**CI / builders (4090-lane, workflow edits):**
- Add `docker/setup-qemu-action@v4` before buildx in `self-hosted-builds-hardened.yml` (declares arm64 but no QEMU → emulation/fail). https://docs.docker.com/build/building/multi-platform/#using-qemu
- Persistent builder + GC bounds where adopted: `buildkitd.toml` `[gc] policy=["max-unused-build-cache-size=2gb"]`. **Z890-coordinated** if on Z890. https://docs.docker.com/build/buildkit/toml-config/#gc
- Bound GHA cache on self-hosted (prefer `type=registry` for persistence). https://docs.docker.com/build/cache/backends/gha/

**Runners (mixed):**
- Scheduled disk cleanup — systemd timer or `.github/workflows/fleet-docker-cleanup.yml` (cron weekly, `docker image/builder prune -af --filter until=72h`). **VPS/Z890 apply.**
- Move runner workspace off `/tmp` → persistent host dir in `pmoves/tools/local_cert_runners.py:326` (`/tmp` can be purged mid-job). **4090-lane code edit** + runner restart.

**Model runners (4090-lane, compose edits):**
- **`QDRANT_RECREATE_ON_DIM_MISMATCH=false` on Hi-RAG v2 GPU** (data-loss guard — treat as near-P1). CATALOG.md.
- Pin TensorZero/Hi-RAG images to digests (Ollama/NIM already pinned).
- Standardize GPU reservation syntax (long-form `deploy.resources.reservations.devices`); deprecate `gpus: all`. https://docs.docker.com/compose/gpu-support/
- `CUDA_VISIBLE_DEVICES` per service on multi-GPU nodes (Knuckles dual-GPU, SPARK).
- Resolve `VLLM_BASE_URL` dangling ref (remove or add `pmoves-vllm` service).
- Audit gpu-orchestrator docker.sock `:ro` vs spawn requirement (likely needs `:rw`).
- Hi-RAG v1/v2 routing clarity in `tensorzero.toml`.

**Daemon / compose (mixed):**
- Apply hardening anchors (`x-tier-*-hardened`) fleet-wide (follow-up PR; pre-commit gate). CIS Docker 5.x.
- Add limits to `cataclysm`/`nvidia-nim`/`wger`; add healthchecks to `supabase-postgrest`/`cataclysm`/`llama-throughput-lab`/`wger`/`nvidia-nim`. CIS 5.28.
- Remove nvidia device block from `vibevoice-realtime` (breaks CPU nodes; handoff `z890-compose-voice-vibevoice-media-profile.md` ready). **Z890-coordinated.**

### P3 — Nice to have
- BuildKit cache metrics (`docker buildx du` → NATS `geometry.buildx.cache_bytes`).
- Runner disk Prometheus/Grafana alerts (`node-exporter`, alert <15% free).
- ARC (Actions Runner Controller) scale-to-zero evaluation.
- Docker Model Runner as optional edge/Jetson layer.
- Cross-node model affinity routing via model-registry + NATS.
- Dev-node `daemon.json` templates; explicit `overlay2` storage-driver pinning.
- Network-tier anchors PR-A (`z890-compose-base-network-tier-anchors.md`, ready). **Z890-coordinated.**
- Compose overlay migration (`-f base -f core` stacking); dependency policy doc; `service_started`→`service_healthy` for `nats-init`/`pdf-ingest`/`notebook-sync`.

---

## 4. Dynamic-fleet enablement (zero-waste / on-demand)

Concrete changes so the fleet is modular and burns no idle electricity:

1. **Bounded GC is the precondition for persistence.** Only adopt persistent builders on fixed-capacity nodes (Z890, KVM4) *with* `max-unused-build-cache-size=2gb`. Keep ephemeral builders + `type=registry` cache (GHCR buildcache) on scale-on-demand nodes so layer cache never persists on short-lived hosts.
2. **Model scale-to-zero Make targets** (currently missing the down-path): add `down-model-servers`, `sleep-models` (`OLLAMA_KEEP_ALIVE=0` forces immediate unload vs lazy 300s), `status-model-servers`. Wire to laptop sleep hook / KVM off-peak scheduler. https://docs.docker.com/compose/reference/docker_compose_down/
3. **Keep baseload thin:** always-on = TensorZero (:3030) + model-registry (:8110) + NATS (route/discover only, hold no models). Ollama spawned on first request by gpu-orchestrator, not pre-running.
4. **Affinity scheduling:** model-registry consumes `mesh.node.*` topology + per-node VRAM, publishes `model.available.v1` with `target_nodes`/`blacklist` (e.g. 32B → Z890 only, reject 4090 16GB). TensorZero/gpu-orchestrator route or reject.
5. **Profiles already enable incremental bring-up** (`up-minimal`→`up-core`→`up-all-new`, ~3GB→~20GB). Gap: no lazy profile auto-enable and `unless-stopped` services stay resident. Interim wins available now: `make down-tensorzero` (~150W), `make down-integrations` (~30W).
6. **ARC for true scale-to-zero** (P3): RunnerDeployment + HorizontalRunnerAutoscaler → ephemeral pods, scale to zero on empty queue. Capacity-aware fallback now via `ci_queue_guard.py` (`pmoves/mk/preflight.mk`).
7. **Emit runner/model state to NATS** (`ops.github.runner.disk|queue_depth|load`) so P7 room manager / evo-controller can gate high-resource jobs.

---

## 5. Z890 coordination (do NOT do unilaterally)

Z890 = workstation + GPU runner + primary inference host (RTX 3090 Ti, 24GB — VRAM-constrained). File a claim in `AGNOTE4482PHI.t1.md` before any of these; off-peak (midnight UTC) window; 5-min warning; log to `pmoves/docs/operations/Z890_SHARED_RUNNER_CHANGE_LOG.md`:

- **P1-A log rotation apply** + any **daemon.json** change (affects runners *and* inference; verify no in-flight builds, drain CI before `restart docker`).
- **Persistent builder / buildkitd.toml / GC policy** (P1-F gate, P2 GC) — land/validate on Z890 first, then promote to VPS/CI.
- **Scheduled prune on Z890** — must not run during CI hours; guard `docker ps | grep -q runner || prune`; exclude inference model cache dirs.
- **Ollama image tag / `GPU_ORCHESTRATOR_VRAM_THRESHOLD` / `IDLE_TIMEOUT`** changes — dev workflow breaks if models unload too aggressively; bench-test first.
- **New GPU services / quantization downgrades** — 24GB is the hard ceiling.
- **NATS `mesh.gpu.model.*` topic changes** — gpu-orchestrator, model-registry, Agent Zero all subscribe.
- **Two ready handoffs to land on Z890:** network-tier anchors (`z890-compose-base-network-tier-anchors.md`) + VibeVoice media profile (`z890-compose-voice-vibevoice-media-profile.md`) — both need `COMPOSE_EDIT=1`, zero runtime change.
- **Runner token freshness:** `make -C pmoves gha-runner-4090-preflight` before assuming 4090/Z890 has a current PAT.

**Pure 4090-lane (no Z890 needed):** P1-B, P1-C, P1-D, P1-G, all workflow-YAML and compose-text edits (QEMU, Qdrant guard, image pinning, limits/healthchecks, restart policies, doc creation). Validate via `docker compose config` + `actionlint` locally.

---

## 6. Local validation plan (4090 first, then runner-only)

**Validate on 4090 before trusting the fleet:**
1. **Compose correctness (catches anchors, limits, health, restart):**
   `docker compose -f pmoves/docker-compose.yml config --quiet` (and with overlays once stacked). Confirms YAML logging anchor merges, no duplicate keys.
2. **Workflow lint (P1-B/C/D, QEMU):** `actionlint .github/workflows/self-hosted-builds*.yml .github/workflows/integrations-ghcr.yml` — catches job-ordering/`needs:` errors without dispatching.
3. **Local build of one service** (build context = repo root per memory `feedback_docker_build_context.md`):
   `docker buildx build --build-arg PIP_CONSTRAINT=requirements.lock -f <Dockerfile> .` — proves the build arg + context path before fleet dispatch.
4. **Cache/GC behavior:** create a throwaway named builder with the proposed `buildkitd.toml`, run two builds, `docker buildx du` to confirm GC bound holds. (Throwaway only — do NOT touch Z890's builder.)
5. **Qdrant guard:** assert `QDRANT_RECREATE_ON_DIM_MISMATCH=false` resolves in rendered config: `docker compose config | grep -A2 hi-rag` after edit.
6. **Log rotation locally:** start one service on 4090 Docker Desktop, confirm `docker inspect <c> --format '{{.HostConfig.LogConfig}}'` shows `max-size=50m max-file=3`.
7. **Pre-dispatch gate:** existing `pmoves/mk/build-gate.mk` (`build_gate.py`) before pushing workflow changes.

**Can ONLY be validated on runner hosts (not 4090):**
- Actual `/var/lib/docker` disk reclamation + the disk-free gate firing under a real near-full runner (P1-C/E, scheduled prune).
- `live-restore: true` surviving a `restart docker` without killing containers (VPS).
- Per-job `_work` cleanup across a real sequential matrix run (P1-B) — observable only on a persistent self-hosted runner.
- GHA-cache-on-self-hosted disk footprint, and QEMU arm64 cross-build on amd64 runners.
- GPU-specific items (CUDA_VISIBLE_DEVICES isolation, gpu-orchestrator sock spawn, VRAM affinity) — Z890/SPARK/Knuckles only.

**Sequencing for PRs:** ship pure-4090 workflow + compose-text PRs first (P1-B/C/D/G, P2 Qdrant guard/QEMU/pinning) → validate green on 4090 → then the Z890 handoff bundle (P1-A log rotation, P1-F builder gate, ready compose handoffs) → then VPS daemon.json via Hostinger MCP/vps-deployer (P1-E) in an off-peak window.
