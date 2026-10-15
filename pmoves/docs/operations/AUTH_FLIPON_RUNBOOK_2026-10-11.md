# Auth Flip-On Runbook — YT/Google/SSO stack + Known-Roads review

**Date:** 2026-10-11 · **Author:** agent0-sidecar (A0 digital-twin) · **Lane:** operator-approved three-lane batch (CLAIM `THREE-LANE-CLAIM-20261011` in AGNOTE4482PHI.t1.md)
**Purpose:** reconcile cloud-auth docs vs implementation, flip the YouTube/Google write-auth surface ON, and record the Known-Roads review findings surfaced by the 2026-10-11 ffmpeg-whisper outage + A0 launch-posture directive.

## Current state (measured 2026-10-11 ~21:00 EDT)

| Surface | Measured | Source |
|---|---|---|
| `SSO_GOOGLE_ENABLED` | `false` | `pmoves/env.shared:288` |
| `SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID/SECRET` | present but **empty** | `pmoves/env.shared:291-292` |
| YT service Google client | `google_client_configured: false`, `default_refresh_token_configured: false` | `GET :8077/yt/control/status` |
| Cookie workflow | overlay exists, wired only via `COOKIES_DC` (up-yt) | `pmoves/docker-compose.yt-cookies.yml`, Makefile `up-yt` |
| sso-auth service | defined (orphan list shows it ran historically), not in current stack | `pmoves/docker-compose.sso.yml` |
| Google client creds | in local `env.shared` (gitignored) + GH-secret custody | `env.shared:48-49,123-124` |

Reads (transcription) need none of this; the gap is **writes** (playlist/comment control) and **SSO** (auth.pmoves.ai + Supabase external Google).

## Custody map

- **Google OAuth client** (`CHANNEL_MONITOR_GOOGLE_CLIENT_ID/SECRET`): GitHub secrets (source) → `make -C pmoves secrets-funnel` → tier files. Never hand-copy into generated `env.tier-*` outputs.
- **Supabase external Google provider**: keys EMPTY locally; values live in Supabase dashboard (Auth→Providers) and GH-secret custody — funnel only.
- **Cookies**: `yt-cookie-writer` (root; writes `/app/config/cookies` volume) + `yt-cookie-refresher` (NATS-gated) — yt-cookies overlay only.
- **SSO**: `SSO_FORWARD_AUTH_SECRET` present locally; `SSO_COOKIE_DOMAIN=.pmoves.ai`; base `auth.pmoves.ai`.

## Flip-on sequence

1. `make -C pmoves secrets-funnel` — confirm `SUPABASE_AUTH_EXTERNAL_GOOGLE_*` populate (add the GH secret first if custody is missing).
2. Operator env-local (zero-access path): `make -C pmoves env-local-set KEY=SSO_GOOGLE_ENABLED VALUE=true`.
3. Bring-up via sanctioned targets: `make -C pmoves up-yt` (includes yt-cookies overlay) + the sso overlay through its documented compose entry (no raw up).
4. Supabase: enable external-Google provider via the existing config/migration lane (keys from funnel output).
5. Run the Google OAuth consent once so the YT `default_refresh_token` lands.

## Verification

- `GET :8077/yt/control/status` → `google_client_configured: true`, `default_refresh_token_configured: true` (approval_required stays true — audited actions).
- Supabase `GET /auth/v1/settings` → external google `enabled: true`.
- sso-auth health + one auth.pmoves.ai bounce sets the `.pmoves.ai` SSO cookie.
- pmoves-yt mounts the cookies volume (inspect Mounts for `/app/config/cookies`).

## Rollback

`make -C pmoves env-local-unset KEY=SSO_GOOGLE_ENABLED`, recreate affected services via the same targets, Supabase provider toggle off. No data migration.

## Known-Roads review findings (2026-10-11)

1. **yt client auto-update-on-release: no mechanism exists.** Published-image targets (`up-yt-published*`) exist; nothing auto-rolls on GHCR release. Policy lane needed (pin vs auto-track + release-triggered workflow).
2. **KVM → desktop requirement undocumented.** Operator doctrine: yt-adjacent compose work on KVM nodes runs in the desktop context. No KVM overlay in-tree encodes this. Add a Known-Roads row when the KVM lane lands.
3. **healthz blind spot (measured live).** pmoves-yt `/healthz` checks yt_dlp only — returned `ok:true` through the ffmpeg-whisper outage (window ~18:32→21:20 EDT; 502 body named the unresolvable `ffmpeg-whisper` hostname). Fix direction: dependency probe (whisper reachability, bgutil presence) or a composite stack-health target — fail-observable per the circuit-breaker principle.
4. **GPU hook failure — root cause is the compose wiring, not the driver (corrected 2026-10-11 ~22:00).** Initial draft of this finding wrongly suggested the CPU path (`up-yt-amd`) as the remedy on GPU nodes — that is the anti-pattern: the node's nvidia runtime is healthy (live `nvidia-smi`, driver 610.57.01, CUDA 13.3 measured) and only the **`deploy.resources.reservations.devices` compose path** fires the broken legacy nvidia prestart hook on Docker Desktop/WSL2. Durable fix, per the PR #3358 pattern (media-audio): service-level **`runtime: nvidia`** + `NVIDIA_VISIBLE_DEVICES` env + `HF_HUB_DISABLE_XET=1`, **no devices reservation** — CUDA installs and runs fine through that path. Applied to `ffmpeg-whisper` in `docker-compose.yml` + `docker-compose.media.yml` in this same PR (branch `feat/chit-tour-regen-20261011`). The amd target remains documented for actual **AMD/ROCm nodes** (its own legitimate lane), not as a GPU-node fallback. Full GPU restore after a WSL/Docker Desktop bounce window: smoke `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`, then recreate.
5. **A0 instances launch with CLI connector + host access (operator directive 2026-10-11).** Launch posture for every A0 deployment should include host-access enablement (a0 CLI connector + `code_execution_remote`) gated as a Known Road, not an ad-hoc per-session discovery. Review scope: this sidecar has the connector pattern (code_execution_remote per PMOVES_AI_CONFIG) but no installed CLI; SPARK exposes /a0 + /a0-mcp via tailscale serve (SPARK_ENABLEMENT_RUNBOOK_2026-10-11) and should gain CLI-connector host access; prod A0 (agent-zero compose tier) needs the same posture review. Action: extend node enablement runbooks with a CLI-connector section (install, connect, verify host access) and a Known-Roads grant for connector setup; SPARK first, prod A0 next.