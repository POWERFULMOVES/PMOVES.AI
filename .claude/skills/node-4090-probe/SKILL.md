---
name: node-4090-probe
description: >
  Run the W0 Substrate hardware probe on the 4090 node.
  Windows: deploy/provision/glances-autodetect.ps1
  Linux: deploy/provision/glances-autodetect.sh
  Outputs structured JSON: gpu, cpu, nics, nic_collisions, unifi_topology, system specs.
  Pipe through json-to-profile.py to write pmoves/config/profiles/<node>.yaml.
---

# 4090:probe — W0 Substrate Hardware Probe

Runs the W0 Substrate hardware probe to capture the 4090 node's system
profile: GPU, CPU, NIC stats (including collision counters), Unifi network
topology, and system memory. Output feeds into the node TAC tree and ghost
detector pipeline.

## Run (Windows)

```powershell
# Requires glances running: http://localhost:61208
# Run as Administrator for full NIC collision data
powershell -ExecutionPolicy Bypass -File deploy/provision/glances-autodetect.ps1
```

Optional: write JSON output to file for piping to the profile writer:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/provision/glances-autodetect.ps1 `
    --json-file probe.json
python deploy/provision/json-to-profile.py --json probe.json --node-id pmoves-4090
```

## Run (Linux)

```bash
bash deploy/provision/glances-autodetect.sh
```

Pipe directly to profile writer:

```bash
bash deploy/provision/glances-autodetect.sh --json-file /tmp/probe.json
python deploy/provision/json-to-profile.py --json /tmp/probe.json --node-id pmoves-4090
```

## Profile Auto-Write

`json-to-profile.py` (W0-PR6, merged in PR #1486) converts the probe JSON
into a canonical node profile YAML at `pmoves/config/profiles/<node-id>.yaml`.

```text
USAGE:
  python deploy/provision/json-to-profile.py \
      --json probe.json \
      --node-id pmoves-4090 \
      [--out-dir pmoves/config/profiles/] [--dry-run] [--force]
```

The profile includes hardware tags, GPU list, Tailscale role, `unifi_topology`
(null if Unifi probe was skipped), ghost adapter warnings, and compose overrides.

## Expected Probe Output Shape (JSON)

```json
{
  "hostname": "PMOVES-4090",
  "timestamp": "2026-05-18T15:00:00Z",
  "arch": "x86_64",
  "suggested_node_type": "gpu-4090",
  "suggestion_confidence": "high",
  "cpu": { "model": "Intel Core i9-13980HX", "cores_physical": 24, "cores_logical": 32 },
  "ram_gb": 64,
  "gpus": [{ "vendor": "NVIDIA", "model": "RTX 4090 Laptop GPU", "vram_gb": 16 }],
  "nic_collisions": [],
  "unifi_topology": null,
  "os": { "distro": "Windows", "version": "11 Pro" }
}
```

## Ghost Detector Use

The `nic_collisions` field is the primary ghost detector signal. A rising
collision counter on an idle interface indicates phantom traffic. Compare
across two probe runs:

```bash
# Run probe twice, 60s apart — diff the nic_collisions values
powershell -File deploy/provision/glances-autodetect.ps1 --json-file probe1.json
sleep 60
powershell -File deploy/provision/glances-autodetect.ps1 --json-file probe2.json
# Compare nic_collisions values between probe1.json and probe2.json
```

## Prerequisites

- Glances running with JSON API: `pip install glances[web]` then `glances -w`
- Windows: PowerShell 5.1+ with `Get-NetAdapterStatistics` available
- Linux: `glances` + `ip -s link`
- Profile writer: `pip install pyyaml`

## Notes

- W0-PR4 (ghost detector/Shift Crew) merged as PR #1591
- W0-PR5 (Unifi probe) merged as PR #1588
- W0-PR6 (json-to-profile.py) landed in PR #1486
- See `node-4090-sitrep` for quick health check (doesn't require glances)
- See `pmoves/configs/tac_trees/node-4090-laptop.tac.yaml` Phase 6 for probe TAC entries
- TAC entry `n4090.shift-crew.probe-wire` status: `done` (updated 2026-05-24)
