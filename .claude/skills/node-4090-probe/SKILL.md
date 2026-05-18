---
name: 4090:probe
description: >
  Run the W0 Substrate hardware probe on the 4090 node.
  Windows: deploy/provision/glances-autodetect.ps1
  Linux: deploy/provision/glances-autodetect.sh
  Outputs structured YAML: gpu, cpu, nics, nic_collisions, system specs.
  NOTE: Full wiring is blocked until feat/w0-pr4-ghost-detector merges to main.
---

# 4090:probe — W0 Substrate Hardware Probe

Runs the W0 Substrate hardware probe to capture the 4090 node's system
profile: GPU, CPU, NIC stats (including collision counters), and system
memory. Output feeds into the node TAC tree and ghost detector pipeline.

## Status

> **BLOCKED**: Full wiring requires `feat/w0-pr4-ghost-detector` to merge
> to `main`. After merge, update this SKILL.md with actual script paths and
> full probe output format.

## Run (Windows)

```powershell
# Requires glances running: http://localhost:61208
# Run as Administrator for full NIC collision data
powershell -ExecutionPolicy Bypass -File deploy/provision/glances-autodetect.ps1
```

## Run (Linux)

```bash
bash deploy/provision/glances-autodetect.sh
```

## Expected Output Shape

```yaml
node: pmoves-laptop
timestamp: 2026-05-18T15:00:00Z
gpu:
  name: "NVIDIA GeForce RTX 4090 Laptop GPU"
  memory_total_mb: 16376
  memory_used_mb: 512
cpu:
  brand: "Intel Core i9-13980HX"
  cores_physical: 24
  cores_logical: 32
nics:
  - name: "Wi-Fi"
    speed_mbps: 1201
    nic_collisions: 0
  - name: "Ethernet"
    speed_mbps: 1000
    nic_collisions: 42
system:
  ram_total_gb: 64
  os: "Windows 11 Pro"
```

## Ghost Detector Use

The `nic_collisions` field is the primary ghost detector signal. A rising
collision counter on an idle interface indicates phantom traffic. Compare
across two probe runs:

```bash
# Run probe twice, 60s apart — diff the nic_collisions values
powershell -File deploy/provision/glances-autodetect.ps1 > probe1.yaml
sleep 60
powershell -File deploy/provision/glances-autodetect.ps1 > probe2.yaml
```

## Prerequisites

- Glances running with JSON API: `pip install glances[web]` then `glances -w`
- Windows: PowerShell 5.1+ with `Get-NetAdapterStatistics` available
- Linux: `glances` + `ip -s link`

## After W0 PR-4 Merge

Once `feat/w0-pr4-ghost-detector` merges:
1. Update script paths above with the merged paths
2. Add full probe YAML schema
3. Wire PR-6 profile auto-write target
4. Update TAC entry `n4090.shift-crew.probe-wire` status to `done`

## Notes

- See PR #1535 for W0 PR-3 + PR-4 changes
- See `node-4090-sitrep` for quick health check (doesn't require glances)
- See `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml` Phase 6 for probe TAC entries
