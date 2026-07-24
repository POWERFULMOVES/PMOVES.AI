# Fleet Recreation & Service-Placement Plan — 2026-07-22

Written after the Z890 node was reported reconciled to then-current main (it had
been 773 commits behind, causing that session's cipher-401 / "MCP missing"
symptoms). This plans the remaining fleet: 4090 media/networking, creator
pipeline, and KVM recreation. Deferred execution — remote-node deploys are
deliberate, per-node, operator-approved.

> **Historical planning snapshot:** node revisions, health, and deployment
> progress were reported on 2026-07-22. Verify every node live before using this
> as an execution plan.

## Context

- **Z890** was reported cut over to then-current main (`checkout -B origin/main`), with tokenism rebuild/redeploy still pending. Recheck its exact SHA, dirty state, MCP configuration, and running image before proceeding (see `tokenism-pmoves-services-common-packaging-2026-07-22.md`).
- The **KVM and other node revisions were not verified by this document**. Apply the same currency check fleet-wide. The guarded catch-up per node: `git fetch origin`; check for uncommitted/unpushed local work; record a rollback ref (`git branch backup/<node>-pre-cutover`); then `git checkout -B <branch> origin/main` (preserving git-ignored env); regenerate tier files (`make secrets-funnel`); dry-run config; tiered recreate; roll back via the backup ref if recreate fails.

## Node → service placement (current vs intended)

| Node | Tailnet | Current room/role | Intended |
|---|---|---|---|
| **Z890** | pmoves-z890 | infra hub (`z890-infra.room.fabric`) | unchanged; recreated to main |
| **4090 laptop** | pmoves-laptop (active) | review/control (`4090-field.room.control`: notebook, review-console, mcp-hirag) | **+ networking + media** (Jellyfin library, NVENC) — role expansion |
| **5090** | pmoves-5090 (active, on-LAN) | kilocode + voice studios (`5090-kilocode`, `5090-voice`) | **creator pipeline** (ComfyUI/VibeVoice/voice-relay — GPU) |
| **Knuckles/B850** | pmoves-b850-ai-top | designated Linux container host | Linux service host |
| **Spark** | pmoves-spark (active) | ARM64 runner / DGX-Spark | build/runner |
| **kvm4-1** | pmoves-kvm4-1 (exit) | VPS API gateway | recreation check |
| **kvm4-2** | pmoves-kvm4-2 (active exit) | VPS data / NATS fleet bus | recreation check (NATS bus critical) |
| **kvm2** | pmoves-kvm2 (exit) | exit node / VPN product | recreation check |

## Track 1 — 4090: media + networking role expansion

**Goal:** the 4090 becomes the media/Jellyfin-library node and takes a networking role.

1. **Room manifest** — update `pmoves/config/rooms/4090-field.room.control.json` to add media apps (Jellyfin panel) + networking apps. Schema-gated (room domain) — needs a grant + `validate_room_manifests.py`.
2. **Jellyfin** — `pmoves/docker-compose.jellyfin-ai.yml` (lscr.io/linuxserver/jellyfin:10.11.0, NVENC GPU transcode, `media/` library volume). Deploy on the 4090 via `fleet-node-deployer` (Tailscale-SSH + Docker MCP toolkit). Confirm the media library storage path + GPU passthrough. Targets: `up-jellyfin-ai` / `up-jellyfin-ai-nvenc`.
3. **Networking role** — per the mesh-first model ([[project_networking_is_mesh_first_pinokio_owns_it]]): cross-node = mesh + NATS leaf, Pinokio/PBNJ owns it, NOT host ports. The 4090's "networking" likely = a NATS leaf + mesh participation + possibly media-serving egress. Confirm exact scope with operator.

## Track 2 — Creator pipeline (5090)

Components (GPU): `up-comfyui`, `up-vibevoice`, `up-voice-relay`, plus the `cataclysm-creative-pipeline` n8n flow (currently a stub) and media-video/audio. Home = 5090 (already the kilocode/voice studio node). Stand-up: deploy the GPU services on 5090 via fleet-node-deployer; wire the n8n creative pipeline flow (retire its stub). Depends on: the creator-operator (L1) tooling + ComfyUI workflows.

## Track 3 — KVM/VPS recreation

Per-node, via `vps-deployer` (Hostinger MCP + Tailscale-SSH). For each KVM: (a) `git fetch origin` + currency check (behind main?), (b) check/preserve local work + record a rollback ref, (c) bring tree to main, (d) regenerate tier env, (e) recreate its assigned services, (f) roll back via the preserved ref if recreate fails. **kvm4-2 (NATS fleet bus) is the critical one** — coordinate downtime; the bus underpins cross-node. Reference: `deploy/runbooks/hostinger-vps-deploy.md`, memory `project_kvm42_unprovisioned_nats_down`.

## Cross-cutting

- **Stale worktree hygiene**: `.worktrees/pr1720` + `.worktrees/pr1724` (long-closed PRs) carry legacy CHIT paths that fail the secrets-audit gate — prune them ([[feedback_check_worktree_before_remove]] first).
- **Branch hygiene**: ~10 stale merged MCP branch refs to prune (squash-artifact `ahead=N`).
- **Node cutover pattern** (reusable): `git fetch origin` → check for local/unpushed work → record rollback ref (`git branch backup/<node>-pre-cutover`) → `git checkout -B <branch> origin/main` (preserves git-ignored env + untracked grant) → `make secrets-funnel` → `make compose ARGS="config --quiet"` dry-run → tiered recreate → roll back via the backup ref if recreate fails. This is how any behind-node catches up.

## Sequence recommendation

1. Z890: verify current SHA/state, then rebuild/redeploy tokenism-simulator with the packaging fix and verify healthy before considering any broader recreate.
2. kvm4-2 currency (NATS bus health is fleet-critical).
3. 4090 media/networking (Jellyfin).
4. Creator pipeline (5090).
5. kvm4-1 / kvm2 recreation.
