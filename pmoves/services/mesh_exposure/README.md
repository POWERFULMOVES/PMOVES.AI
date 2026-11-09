# mesh_exposure

PMOVES-side writer that reconciles the **pinokio-apps registry** to the
live fleet (headscale ACL ports, cloudflared tunnel ingress entries,
Cloudflare + Hostinger DNS records). Slice 4 of the creator-collab lane.

## Why

The slice-1 review-iter-2 review of PR #2264 explicitly flagged that
the `pinokio_app_refs` field in `room.manifest.v1` is meaningless
without the catalog backing it. The slice-4 pinokio-apps registry
(`pmoves/configs/pinokio-apps/{curated,user}/<slug>.yaml`) is that
catalog. This service is the bridge from the catalog to the live
fleet — without it, every consumer (P7, the dashboard, the future
helpdesk-skill) has to re-read the on-disk Pinokio state at runtime.

The 4-layer reachability model (L1 venv / L2 same-host container / L3
tailnet mesh / L4 public website via kvm2 + Cloudflare/Hostinger) is
documented in the slice-4 deep-dive report + spec doc. This service
owns the L3 + L4 writes; L1 + L2 are host-local and don't need a
reconcile service.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/healthz` | open | Service health + registry count + writes state + last-reconcile timestamps |
| `GET` | `/v1/registry?slug=<slug>` | open | List all curated entries (or a specific slug) |
| `GET` | `/v1/reconcile/plan` | open | Compute desired vs current state as JSON diff |
| `POST` | `/v1/reconcile/apply` | `X-PMOVES-Meshbus-Token` (fail-closed) | Apply the plan (requires `confirm=true` + `WRITER_MODE=apply`) |
| `GET` | `/v1/reconcile/status` | open | Last run + last change timestamps + last plan + last apply |
| `POST` | `/v1/reconcile/preview?slug=<slug>` | `X-PMOVES-Meshbus-Token` | Dry-run for a single app |

Auth model: reads are open; writes need `X-PMOVES-Meshbus-Token` in
the request header, which must match `MESH_EXPOSURE_TOKEN` at service
start. Fail-closed: if the env var is unset, writes return 503 with
a clear error pointing the operator to the env var. Same pattern as
`pinokio_bridge` (X-PMOVES-Bridge-Token) and `nats_event_bus`
(X-PMOVES-NatsBus-Token) so tokens are scoped per service.

## Config

| Env var | Default | Purpose |
|---|---|---|
| `MESH_EXPOSURE_PORT` | `8132` | HTTP listen port |
| `MESH_EXPOSURE_HOST` | `127.0.0.1` | HTTP listen host |
| `MESH_EXPOSURE_REGISTRY_DIR` | `pmoves/configs/pinokio-apps/curated` | Where the registry lives |
| `MESH_EXPOSURE_HEADSCALE_ACL` | `pmoves/config/headscale/acl.yaml` | Source of truth for the headscale ACL; the service reads this to compute the diff |
| `MESH_EXPOSURE_TOKEN` | (unset) | Fail-closed write token |
| `MESH_EXPOSURE_WRITER_MODE` | `noop` | `noop` = no writes (default for read-only use); `apply` = actually write |
| `MESH_EXPOSURE_USER_DIR` | `pmoves/configs/pinokio-apps/user` | Where `discover.py` writes new entries |

**Host convention:** the service runs on z890 (infra-coordinator) by
default because that node has direct file access to
`pmoves/config/headscale/acl.yaml` and SSH reach to kvm2
(exit-proxy). A second instance can run on any node if read-only use
is the goal (no token needed, no writes).

## Writing to the live fleet

The default `noop` writer mode is intentional. The service exposes
the *plan* (the diff between desired and current state) as JSON;
the actual writes are operator-driven via the slice-4 runbook
(`pmoves/docs/operations/MESH_EXPOSURE_RUNBOOK.md` — to be written
before the apply path is exercised in production).

To switch to live writes, set `MESH_EXPOSURE_WRITER_MODE=apply` and
provide writer implementations. The current service ships with:

- `headscale_writer`: appends to `pmoves/config/headscale/acl.yaml`
  (the canonical headscale ACL config; the operator syncs to the
  running headscale container)
- `cloudflared_writer`: SSH to kvm2 + edit `/etc/cloudflared/config.yml`
  (production: the operator's wrapper script does this; the
  service exposes the diff as JSON)
- `dns_writer`: Cloudflare API + Hostinger API upsert (production:
  same as cloudflared — exposed as JSON; the operator's wrapper
  applies)

This split keeps the service testable (no real NATS, Cloudflare,
Hostinger, or kvm2 in the test path) while leaving the production
write path to the operator's deliberate runbook execution.

## Why a separate service, not NATS topics

The reconciler needs to read current state from three different
sources (disk for headscale, SSH-to-kvm2 for cloudflared, two HTTP
APIs for DNS). It also needs to take a *lock* on each of those
sources (you don't want two reconcilers racing on the same
`acl.yaml` file). A service with explicit in-memory state + the
fail-closed write token is the right shape for that.

The slice-3 nats_event_bus service is the *read* surface for the
5 slice-3 subjects (`comfy.collab.{prompt,progress,artifact}.v1` +
`room.presence.v1` + `room.directory.v1`). The mesh_exposure service
is the *write* surface for the slice-4 registry. They are
complementary; one does not subsume the other.

## Test surface

```bash
cd pmoves
python -m pytest services/mesh_exposure/tests/ -q
```

29 pytest cases. No live NATS, Cloudflare, Hostinger, or kvm2 access.
Uses `tmp_path` for the registry dir + injected reader/writer
callables. The end-to-end test (`test_live_registry_loads_12_entries_from_slice4_curated`)
confirms the real slice-4 curated dir parses cleanly + the 2 L4 apps
(comfyui-desktop + ultimate-tts-studio) surface in the plan as
expected.

## Cross-references

- `pmoves/docs/specs/pinokio-apps-registry-2026-07-28.md` — the spec doc
- `pmoves/docs/research/creator-collab-slice-4-deep-dive-2026-07-28.md` — the deep-dive report
- `pmoves/docs/architecture/PINOKIO8_APP_HOSTING_SPEC.md` — the pre-existing ADOPT/COMPOSE/DEFER stance
- `pmoves/configs/pinokio-apps/` — the registry (curated/ + user/ + schema/)
- `pmoves/configs/tac_trees/{pinokio-venv,pmoves-container,tailnet-mesh,public-tunnel}.tac.yaml` — the 4 layer-TAC trees
- `pmoves/tools/pinokio_apps/discover.py` — the discovery tool that populates `user/`
- `pmoves/skills/gepeto-wrapper-skill/SKILL.md` — the PMOVES-side skill for the registry surface
