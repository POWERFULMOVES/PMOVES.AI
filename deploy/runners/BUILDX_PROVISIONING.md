# Self-Hosted Runner BuildKit Provisioning + Access

How PMOVES self-hosted runners (ai-lab / kvm4 / kvm2 / spark) build images without
leaking disk, and how a human operator and an agent reach them **the same way**.

## The builder — one, reused, self-bounded (root fix, not a sweep)

Every self-hosted build step uses the composite action
[`.github/actions/pmoves-buildx`](../../.github/actions/pmoves-buildx/action.yml)
instead of a bare `docker/setup-buildx-action`. It gives each runner **one** builder
that is:

| Property | How | Why |
|---|---|---|
| **Reused** across runs | `name: pmoves-shared` | setup-buildx reuses a builder that already exists with that name — no fresh `docker-container` builder (and no new `buildx_buildkit_*_state` volume) per run. |
| **State-preserving** | `keep-state: true` | persistent runners keep the builder + warm cache between jobs. |
| **Self-bounded** | `buildkitd-config-inline` gc policy (`maxUsedSpace`/`reservedSpace`/`keepDuration`) | BuildKit GC runs *periodically* and prunes cache to stay under the cap — the state volume can never grow unbounded. |

This is the documented Docker way to bound builder storage
([garbage-collection](https://docs.docker.com/build/cache/garbage-collection/),
[setup-buildx-action](https://github.com/docker/setup-buildx-action)). It replaces
the previous per-run-builder pattern that filled kvm4-1 to 100% (181 GB of orphaned
builder-state volumes).

**Safety net:** `runner-maintenance.yml` still sweeps orphaned
`buildx_buildkit_builder-*_state` volumes nightly — for any builder left behind by a
cancelled job. Root fix (bounded builder) + belt-and-suspenders (sweep), both scoped
so they can **never** touch a `pmoves_*` data volume (never `docker volume prune`, per #1868).

## Tuning per node

Override the cap for a bigger/smaller node at the call site:

```yaml
- uses: ./.github/actions/pmoves-buildx
  with:
    max-used-space: "50GB"   # default 30GB
    reserved-space: "8GB"    # default 5GB
```

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
