# Handoff — replace the hand-rolled ROCm exporter with AMD's official container

**Node:** B850 / Knuckles (`pmoves-b850`) · **Date:** 2026-08-15
**Known Road:** `KNOWN_ROAD=compose:handoff:rocm-device-metrics-exporter-2026-08-15.md`
**Opens:** `pmoves/docker-compose*.yml` only (to add `docker-compose.rocm.override.yml`)

## Why

Two independent reasons, both measured on this node.

### 1. The host-native exporter was unscrapeable

The repaired `rocm-smi` exporter (merged in #2545) serves correctly on the host —
`HTTP 200`, 756 bytes, 8 samples — but **Prometheus cannot reach it**. Measured from
the Prometheus container via its own bridge gateway:

| Port | Kind | Result |
|---|---|---|
| 4222 (NATS) | docker-published | **OPEN** |
| 9835 (exporter) | host-native systemd socket | **refused/filtered** |

Docker inserts ACCEPT rules for published ports and the `DOCKER-USER` chain is empty,
so published ports bypass UFW. A host-native listener gets no bypass and falls under
UFW's `default deny (incoming)` on the bridge. UFW logging is `low`, so these drops
leave no log line — absence of a `UFW BLOCK` entry is not evidence of no firewall.

The socket itself was healthy (from the host, both loopback and the bridge address
return 200). It is a packet-path problem.

**Running the exporter as a container removes the host hop entirely**, rather than
opening a firewall rule for it. Verified: Prometheus reaches it by service name on
`pmoves_monitoring`, 83358 bytes / 238 samples.

### 2. The underlying tool is deprecated

`rocm-smi` is deprecated upstream in favour of `amd-smi`, and AMD's older
`amd_smi_exporter` is EOL. `ROCm/device-metrics-exporter` is the maintained
replacement.

Coverage difference on this node:

| | hand-rolled | official |
|---|---|---|
| metric families | 4 | **103** |
| samples | 8 | **238** |
| ECC counters | none | per-block (umc, gfx, xgmi_wafl, hdp, bif, df, …) |
| package power / PCIe | none | yes |

The ECC counters matter most: they surface GPU memory degradation long before it
becomes a crash, and the hand-rolled collector could not have grown them without
reimplementing amd-smi.

## What lands

1. **`pmoves/docker-compose.rocm.override.yml`** (new) — the file
   `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` already names under
   `compose_overrides` but which did not exist anywhere in the repo. That absence is
   recorded as a divergence in that profile's `probe:` block; this closes it.

2. **`pmoves/monitoring/prometheus/prometheus.yml`** — adds the `amd-gpu` scrape job
   targeting `pmoves-device-metrics-exporter:5000`. *(Not a protected path; already
   applied.)*

### Service definition

```yaml
services:
  device-metrics-exporter:
    image: rocm/device-metrics-exporter:v1.5.1
    container_name: pmoves-device-metrics-exporter
    restart: unless-stopped
    devices: [/dev/dri:/dev/dri, /dev/kfd:/dev/kfd]
    volumes: ["/sys:/sys:ro"]
    ports: ["${ROCM_EXPORTER_BIND:-127.0.0.1}:${ROCM_EXPORTER_PORT:-5000}:5000"]
    networks: [pmoves_monitoring]
```

**Decisions worth keeping:**

- **NOT `--privileged`.** AMD's docs show it; it is not required for this metric set.
  Verified with only the device nodes and a read-only `/sys`. Keep the narrower grant.
- **Not published to `0.0.0.0`.** Published ports bypass UFW on this node, so `0.0.0.0`
  would expose GPU telemetry to the LAN. Loopback default, overridable for debugging.
- **`pmoves_monitoring`**, the canonical network from `docker-compose.base.yml` — where
  Prometheus and Loki already sit. (It also works on the legacy `pmoves-net`; the
  canonical one is correct.)
- **Healthcheck asserts samples, not liveness** — `grep -q '^gpu_'`. The bug that
  started this was an endpoint returning 200 with an empty body while every health
  check stayed green.

## Verified before writing this

```
exporter (host loopback)      HTTP 200 · 83358 bytes · 238 samples
Prometheus -> service name    83358 bytes · 238 samples
prometheus target amd-gpu     health=up
promQL gpu_average_package_power = 13
promQL gpu_edge_temperature      = 28
promQL up{job="amd-gpu"}         = 1
ingested metric names            102 (gpu_*, pcie_*)
```

Prereqs met: ROCm 7.1.0 (docs require ≥ 6.2.0), `/dev/kfd` present, 2 `/dev/dri`
render nodes.

## Follow-ups (deliberately NOT in this change)

- **Retire the host-native exporter** (`rocm-smi-exporter.service`, `rocm-smi-http.socket`,
  `rocm-smi-http@.service`) once dashboards are migrated. Leave running until then —
  metric names differ (`rocm_gpu_*` → `gpu_*`), so Grafana panels and any alert rules
  need updating with the rename. Doing both at once would make a blank panel impossible
  to attribute.
- **Only rdna4 nodes** should load this overlay. A node without `/dev/kfd` will fail to
  start the service.
- Second R9700 is installed but does not enumerate (BIOS x8/x8 bifurcation not set), so
  this currently reports one discrete GPU plus the Raphael iGPU. Metric count will roughly
  double once bifurcation is enabled.
