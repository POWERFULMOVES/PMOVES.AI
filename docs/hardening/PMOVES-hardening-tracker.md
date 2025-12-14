# PMOVES Hardening Tracker (2025-12-13)

Status snapshot and to-dos to align with `PMOVES.AI-Edition-Hardened-Full.md`.

## Recently done
- Hardened CI now builds/scans `pmoves-yt` multi-arch (amd64+arm64) in `.github/workflows/self-hosted-builds-hardened.yml`.
- Added arm64 compose override `pmoves/docker-compose.arm64.override.yml` for Jetson/edge deployments.
- Documented Claude CLI hooks and current hardening state in `AGENTS.md`.
- Removed vendored `PMOVES.YT/yt_dlp` (pmoves-yt now pulls yt-dlp from pip build arg). Removed legacy PEM test fixtures (YT/Tailscale) that were triggering secret scans.
- Added weekly yt-dlp bump workflow (`.github/workflows/yt-dlp-bump.yml`) to keep pmoves-yt aligned with upstream.
- Trivy gating (HIGH/CRITICAL -> fail) is active in hardened self-hosted builds; SARIF uploaded to GitHub Code Scanning.
- GPU/arm64 builds wired for multi-arch; override compose validated on Jetson path.

## High-priority next steps
1) Dependency locks
   - ✅ Regenerated `agent-zero` and `media-video` locks on Python 3.11 (CUDA cu121 wheels) with hashes.
2) Image pinning & freshness
   - Pin remaining image tags as releases land; `flight-check` now warns on `:pmoves-latest`.
3) Secret handling SOP
   - Keep allowlist minimal; rotation checklist lives in `docs/SECRETS_ONBOARDING.md`.
4) Loki readiness
   - ✅ `/ready` returns 200 (`make -C pmoves loki-ready`). Add this to `make monitoring-report` output.
5) Rerank GPU smoke
   - `GPU_SMOKE_STRICT=true make -C pmoves smoke-gpu` passes, but `cuda:false` in stats indicates CPU fallback; ensure NVIDIA runtime exposure on GPU hosts to enable actual GPU acceleration.

## Optional / nice-to-have
- Compose profiles for split deployments (PC + Jetsons + VPS) with minimal service graphs per host.
- Add StepSecurity egress allowlists mirroring service registries per workflow job.

Track progress here and update timestamps when tasks complete.
