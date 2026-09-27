# Self-Hosted Runner BuildKit Provisioning + Access

How PMOVES self-hosted runners (ai-lab / kvm4 / kvm2 / spark) build images without
leaking disk, and how a human operator and an agent reach them **the same way**.

## The builder — one, reused, bounded by an explicit prune

Every self-hosted build step uses the composite action
[`.github/actions/pmoves-buildx`](../../.github/actions/pmoves-buildx/action.yml)
instead of a bare `docker/setup-buildx-action`. It gives each runner **one** builder
that is:

| Property | How | Why |
|---|---|---|
| **Reused** across runs | `name: pmoves-shared` | setup-buildx reuses a builder that already exists with that name — no fresh `docker-container` builder (and no new `buildx_buildkit_*_state` volume) per run. |
| **State-preserving** | `keep-state: true` | setup-buildx removes the builder at the end of the job but keeps its state volume `buildx_buildkit_pmoves-shared0_state`, so the next job starts warm. |
| **GC-configured** | `buildkitd-config-inline`: an age-out rule plus an `all = true` catch-all (`maxUsedSpace`/`reservedSpace`/`minFreeSpace`) | BuildKit GCs ~1s after the daemon starts and after builds (at most once a minute). Before the catch-all it did **not** hold the cap (below). |
| **Config actually applied** | action step `--preflight` | setup-buildx reuses an already-registered builder **without** re-applying the inline config, so a leftover one is detached (`--keep-state`) first. |
| **Bounded** | [`deploy/provision/pmoves-buildx-cap.sh`](../provision/pmoves-buildx-cap.sh) | An explicit `docker buildx prune --builder pmoves-shared` to the cap: in every build job right after attach, and nightly between jobs. |

### Why the GC policy alone was not enough (measured 2026-09-27)

The state volume was **139.5GB on kvm4-1 and 146.4GB on kvm4-2** against a 30GB
`maxUsedSpace`, growing 5-9 GiB/day, while `runner-maintenance.yml` succeeded every
night. The builder exists only during a job; between jobs there is a volume and no
builder, and every nightly prune missed it:

- `docker builder prune` reaches only the **default** builder (0B on those hosts);
- the stale-builder loop in `runner-maintenance.yml` matched only the old per-run
  `buildx_buildkit_builder-*` names;
- `fleet-docker-cleanup.yml` and `deploy/provision/docker-fleet-cleanup.sh` had the
  same limitation.

**Why the in-daemon GC never trimmed it.** The builder did parse the config:
BuildKit v0.31.2 logged `GC Policy rule#0: All: false / Keep Duration: 168h /
Reserved Space: 5GiB / Max Used Space: 30GiB`. With the builder re-attached on
kvm4-2, `docker buildx du` reported Total 155.5GB and Reclaimable 155.5GB, so
nothing had leaked outside BuildKit's view. The config simply never selected
anything to delete. From the source (moby/buildkit v0.32.2):

- An inline `[[worker.oci.gcpolicy]]` list **replaces** the default list
  (`DefaultGCPolicy`, `cmd/buildkitd/config/gcpolicy.go`), whose last rule is an
  `All: true` catch-all. Ours had only one rule.
- `pruneOnce` (`cache/manager.go`) skips every record with `lastUsedAt` inside
  `keepDuration`. With `168h`, anything used in the last week is never eligible,
  and a builder in daily use touches most of its cache every week.
- With `all = false` it also skips internal, frontend and shared records.

The fix adds a second rule, `all = true` with no `keepDuration`, capped at
`maxUsedSpace` and with a `minFreeSpace` floor (default `20%`, BuildKit's own
default). This is the same shape as the default list's last rule.

**Reuse hazard (observed on kvm4-2 2026-09-27).** If a builder named
`pmoves-shared` is already registered on the runner (left by a failed job or an
operator), setup-buildx-action reuses it and does **not** re-apply
`buildkitd-config-inline`, so it runs BuildKit's bare default policy. The action's
first step (`pmoves-buildx-cap.sh --preflight`) detaches it with `--keep-state`
so setup-buildx recreates it with the config. If the builder is running and
another `Runner.Worker` is active on the host (b850), it may be in use. In that
case the step reuses it only if `docker buildx inspect` shows an `All: true`
rule, and otherwise fails the job with the command to run once the builder is idle.

### The model now

One script, one cap. [`pmoves-buildx-cap.sh`](../provision/pmoves-buildx-cap.sh)
holds the default cap (`DEFAULT_CAP`, 30GB) and the action reads its
`maxUsedSpace` default from it (`--print-cap`), so there is a single value.

| Where | When | What |
|---|---|---|
| `pmoves-buildx` action | every build job: `--preflight` before setup-buildx, `--attached` right after | preflight as above; then prune the live builder to the cap (`--all`). The prune is non-fatal; a failure is a `::warning::`. |
| `runner-maintenance.yml` | nightly 03:00 UTC, per host | re-attach `pmoves-shared` by name (node `pmoves-shared0`, so it mounts the kept volume), `buildx prune --all` to the cap, `buildx rm --keep-state`. |
| `fleet-docker-cleanup.yml` | nightly, per host | same script. |
| `docker-fleet-cleanup.sh` (systemd timer) | daily, where installed | same script, installed beside it by `make -C pmoves docker-fleet-cleanup-install`; its orphan-volume sweep excludes the shared volume. |

Why a prune at attach instead of at the end of the job: composite actions have no
`post:` hook, and an end-of-job step would need `if: always()` added to all seven
callers. Pruning at attach bounds the volume to the cap plus at most one job's
growth, with no caller changes, and it runs even when the previous job was
cancelled.

Invariants: the script **never** removes the state volume and never uses
`buildx rm` without `--keep-state`. The prune uses `--all` because without it
BuildKit skips internal/frontend/shared records and the cap would not count the
whole volume. It skips a builder whose container is running while another
`Runner.Worker` is active on the host (b850 runs two runners on one daemon; a
systemd timer is not a job at all), because detaching it would kill an
in-flight build. Exit codes: 0 bounded / nothing to do,
1 prune or attach failed, 3 docker unavailable.

**Safety net:** `runner-maintenance.yml` still reclaims leftover per-run
`buildx_buildkit_builder-*` builders and their state volumes, for any left by the
pre-#2021 pattern or a cancelled job. Everything is scoped so it can **never**
touch a `pmoves_*` data volume (never `docker volume prune`, per #1868).

Manual reclaim that DELETES the shared cache outright (a cold rebuild next job):
`pmoves/scripts/pmoves-disk-cleanup.sh` and `make -C pmoves docker-prune-all`
(their dangling-volume sweep removes `buildx_buildkit_pmoves-shared0_state` when no
builder is attached). Use those on a sick node, not as routine maintenance.

## Tuning per node

Override the cap for a bigger/smaller node at the call site (both the GC policy
and the on-attach prune use it):

```yaml
- uses: ./.github/actions/pmoves-buildx
  with:
    max-used-space: "50GB"   # default: DEFAULT_CAP in deploy/provision/pmoves-buildx-cap.sh
    reserved-space: "8GB"    # default 5GB
    min-free-space: "25%"    # default 20% (catch-all rule)
```

The nightly jobs use the script default; set `PMOVES_BUILDX_CAP` in their
environment to change it for a host.

## Access — the operator and an agent use the same lane

The KVMs are reached over the **Tailscale mesh by hostname** (never a raw IP) — the
identical path whether a person or an agent is driving:

| Who | How | Notes |
|---|---|---|
| **Operator** | `tailscale ssh root@pmoves-kvm4-1` | ACL `autogroup:admin`/`owner` → `tag:vps`/`tag:exit`, root allowed. Hostname only. |
| **Agent** (`vps-deployer`) | its sanctioned SSH/CLI lane + Hostinger MCP | same hosts, same hostnames; used for the reclaim + obs deploy in this session. |
| **Both** | `make -C pmoves exit-node-observe NODE=<host>` / `exit-node-obs-install NODE=<host>` | make targets are the shared Known Road — a human types it, an agent runs it. |

## The KVMs "speak" — observability like an agent reports

Each runner/exit node now exports metrics the same way a service does, so the fleet
is queryable instead of silent:

- `node_exporter` on `:9100` surfaces two textfile writers (see
  [`tailscale-textfile-collector.md`](../../pmoves/monitoring/prometheus/tailscale-textfile-collector.md)):
  native `tailscaled_*` (path-labelled direct/derp) + `pmoves_exit_*`
  (peers/load/mem/**bw cap headroom**).
- Prometheus scrapes it → the Grafana **"Tailscale Network Health"** board.
- Deployed via `make -C pmoves exit-node-obs-install NODE=<host>`.

Continuous obs is what turns "kvm4-1 filled up 18h ago and we found it by hand" into
"the board flags disk pressure the moment it starts."
