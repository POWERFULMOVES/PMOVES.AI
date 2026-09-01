---
name: node-5090-sitrep
description: >
  Full situation report for the 5090 desktop workstation node (POWERFULMOVES):
  git status, active worktrees, GPU (RTX 5090 32GB), NATS health, running
  containers, TTS engine health, Pinokio LWW, cross-machine connectivity to Z890,
  and open PRs. Output formatted as AGNOTE4482 audit record block. Run before
  every CLAIM/RELEASE in AGNOTE4482PHI.t1.md on the 5090 node.
---

# node-5090-sitrep — Node Situation Report (5090 POWERFULMOVES)

Runs the 5090 node health check and outputs a formatted AGNOTE4482 audit
record. Use this before making a CLAIM or RELEASE in `AGNOTE4482PHI.t1.md`
when working on the 5090 desktop workstation.

## Node Identity

| Field | Value |
|-------|-------|
| Hostname | `POWERFULMOVES` |
| Agent hint | `5090-claude` |
| Tailscale | `powerfulmoves-1.ts` |
| Role | Primary GPU / TTS host, Pinokio native runtime |
| Profile | `desktop-9950xd` (canonical), `workstation_5090` (alias) |
| TAC tree | `pmoves/configs/tac_trees/node-5090-powerfulmoves.tac.yaml` |
| OS | Windows 11 Pro |
| CPU | AMD Ryzen 9 9950X3D, 16 cores / 32 threads |
| GPU | NVIDIA RTX 5090 — 32GB VRAM |
| RAM | 192 GB |
| Pinokio root | `D:\pinokio\api\` (18 apps, 5 TTS) |
| LWW | `http://powerfulmoves-1.ts:42000` (Pinokio network view) |

## Run — Full Sitrep

```bash
echo "=== 5090 SITREP $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
# The shared script carries the checks EVERY node has (identity, git, roster,
# GPU, NATS, containers, PRs). Prefer it: per-skill copies drift, and all of
# them probed the wrong NATS port for months.
#
# It replaces the COMMON half only. An earlier version of this line said
# `bash ... && exit 0` — and because the script ends on a successful `echo` it
# always returns 0, so every WORKING invocation skipped the 5090-specific
# remainder below and produced a shorter sitrep than the copy it replaced.
# Sharing common code must not silently drop what is not common.
if bash .claude/scripts/node-sitrep.sh 2>/dev/null; then
  :  # common section covered by the shared script
else
  echo "(shared sitrep unavailable — inline fallback for the common section)"
  echo "--- GIT ---"
  git status --short
  git log --oneline -3
  echo "--- GPU ---"
  nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "GPU: not available"
  echo "--- NATS ---"
  # Derive the whole published endpoint; do NOT hardcode it, and do not keep
  # only the port. `8222` is the CONTAINER-side port and never answers on the
  # host: pmoves-nats-1 publishes `127.0.0.1:9223->8222/tcp`. Probing 8222
  # reported a healthy NATS as DOWN (measured 2026-08-31: uptime 2d15h, 7
  # connections, on :9223). a0-archon-bridge/SKILL.md:71 already documented
  # this — the correction had landed where the error was found, not where it
  # is read. Keep the HOST too: a node that binds the monitor to a specific
  # address rather than loopback (KVM4-2's `NATS_MONITORING_BIND`) is not
  # reachable on `localhost`, and dropping the host reintroduces the same
  # false DOWN one layer down.
  NATS_PUB=$(docker port pmoves-nats-1 8222 2>/dev/null | head -1)
  NATS_HOST=${NATS_PUB%:*}; NATS_MON=${NATS_PUB##*:}; NATS_MON=${NATS_MON:-9223}
  case "$NATS_HOST" in ''|'0.0.0.0'|'::'|'[::]') NATS_HOST=localhost ;; esac
  # docker port ALREADY brackets IPv6; bracket only a bare one.
  case "$NATS_HOST" in \[*\]) : ;; *:*) NATS_HOST="[$NATS_HOST]" ;; esac
  curl -sf "http://$NATS_HOST:$NATS_MON/healthz" >/dev/null 2>&1 \
    && echo "NATS: OK (http://$NATS_HOST:$NATS_MON)" \
    || echo "NATS: DOWN (http://$NATS_HOST:$NATS_MON)"
  echo "--- CONTAINERS ---"
  docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | head -20
  echo "--- OPEN PRs ---"
  gh pr list --state open --limit 10 2>/dev/null
fi

# --- 5090-SPECIFIC — always runs. The shared script has no node-local
# knowledge, so nothing below can be assumed covered by it.
echo "--- WORKTREES ---"
git worktree list
echo "--- TTS ENGINES ---"
curl -sf http://localhost:7860/gradio_api/info >/dev/null 2>&1 && echo "Ultimate-TTS-Studio (:7860): UP" || echo "Ultimate-TTS-Studio (:7860): DOWN"
echo "--- KEY SERVICES ---"
for port_label in "11434:Ollama" "3030:TensorZero" "8077:PMOVES.YT" "8078:Whisper" "5678:n8n"; do
  port="${port_label%%:*}"; label="${port_label##*:}"
  curl -sf "http://localhost:${port}" >/dev/null 2>&1 && echo "${label} (:${port}): UP" || echo "${label} (:${port}): DOWN"
done
echo "=== END SITREP ==="
```

## Run — Quick Health Check (5s)

Fastest triage: NATS + git + GPU + TTS hub only.

```bash
# One derivation, one place. `8222` is the CONTAINER-side port; the host half
# AND the port vary per node (compose default 9223, Z890 8222, and
# NATS_MONITORING_BIND can move the host off loopback). See nats-endpoint.sh.
NATS_URL=$(bash .claude/scripts/nats-endpoint.sh)
curl -sf "$NATS_URL/healthz" >/dev/null 2>&1 && echo "NATS: OK ($NATS_URL)" || echo "NATS: DOWN ($NATS_URL)"
curl -sf http://localhost:7860/gradio_api/info >/dev/null 2>&1 && echo "TTS UP" || echo "TTS DOWN"
git log --oneline -1
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader
git worktree list | wc -l
```

## Run — Cross-Machine Connectivity

Checks that the 5090 can reach the Z890 coordinator hub over Tailscale.

```bash
echo "--- CROSS-MACHINE (Z890 hub) ---"
curl -sf http://pmoves-z890.ts:3030/v1/models >/dev/null 2>&1 && echo "Z890 TensorZero: reachable" || echo "Z890 TensorZero: unreachable"
# 8222 is RIGHT here, and only here: docker-compose.z890.yml:32 publishes
# `127.0.0.1:8222:8222`, unlike the base compose (:9223). Do not "correct" this
# to 9223 — and do not derive it either, since `docker port` reads the LOCAL
# daemon and this is a remote node. Verified against the compose file 2026-09-01.
curl -sf http://pmoves-z890.ts:8222/healthz >/dev/null 2>&1 && echo "Z890 NATS hub: reachable" || echo "Z890 NATS hub: unreachable"
```

## Run — VRAM Budget Check

RTX 5090 has 32GB VRAM. Multiple TTS engines + Docker GPU services compete.
Use this before launching additional GPU workloads.

```bash
echo "--- VRAM BUDGET (32GB total) ---"
nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv,noheader 2>/dev/null || echo "(no GPU processes)"
```

Interpretation:
- Baseline (idle): < 4GB used (driver + Ollama idle)
- Single TTS engine: +2-6GB depending on engine
- Safe concurrent: Kokoro (2GB) + Fish S2 (4GB) + IndexTTS (6GB) = 12GB
- All 14 engines simultaneously: does NOT fit in 32GB
- See `pmoves/configs/tts-engine-capabilities.yaml` for per-engine VRAM

## AGNOTE4482 Output Format

The sitrep produces an audit block for pasting into `AGNOTE4482PHI.t1.md`:

```text
## SITREP [5090-claude] 2026-07-28T15:00:00Z

**Node**: POWERFULMOVES (5090 desktop)
**Branch**: main
**Worktrees**: 21 active
**GPU**: NVIDIA RTX 5090 — 10220MB used / 21968MB free (32GB total)
**NATS**: OK (http://127.0.0.1:9223)   <- whatever nats-endpoint.sh derives on THIS node
**TTS**: Ultimate-TTS-Studio UP (:7860)
**Containers**: [list]
**Open PRs**: #2394, #2382, #2381

<!-- GRAPHITI_MARK: sitrep.5090-claude.2026-07-28T15:00:00Z -->
```

## CLAIM/RELEASE Workflow

1. Run `node-5090-sitrep` (full sitrep above) → paste output block into `AGNOTE4482PHI.t1.md`
2. Add CLAIM entry with `[5090-claude]` agent hint and task description
3. Do work
4. Run `node-5090-sitrep` again → paste as verification
5. Add RELEASE entry with summary of what was done

## Differences from 4090 Sitrep

| Aspect | 4090 (laptop) | 5090 (desktop) |
|--------|---------------|----------------|
| Hostname | `PMOVES-4090` | `POWERFULMOVES` |
| GPU | RTX 4090 16GB | RTX 5090 32GB |
| CPU | Intel i9-13980HX | AMD Ryzen 9 9950X3D |
| RAM | 64 GB | 192 GB |
| Role | Mobile/pilot | Primary GPU + TTS host |
| Pinokio | Bridge service | Native runtime (`D:\pinokio\`) |
| TTS | Via Flute Gateway | 5 native engines, 14 sub-engines |
| NATS | Self-hosted | Leaf/client to Z890 hub |
| Cross-machine | Tailscale client | Tailscale + LWW server (:42000) |
| Agent hint | `4090-claude` | `5090-claude` |

## Notes

- 5090 is the canonical TTS host — all voice synthesis flows through Pinokio apps here
- Pinokio LWW (`D:\pinokio\`) exposes all localhost TCP listeners via Caddy HTTPS proxy on `0.0.0.0:PORT` — cross-machine access requires TLS SNI (hostname, not IP)
- The `workstation_5090` profile is a deprecated alias of `desktop-9950xd` — use the canonical ID in new work
- GPU VRAM is the primary constraint for multi-engine TTS; check budget before launching workloads
- `GRAPHITI_MARK` footer required on all audit records per AGNOTE4482 protocol
- See `node-5090-powerfulmoves.tac.yaml` for the full 7-phase capability tree (inventory, TTS health, network, Docker, VRAM, cross-machine, NATS announcement)
- See `AGNOTE4482PHI.t1.md` Active Claim Register for current claims on this node
- For W0 substrate hardware probe, the probe scripts in `deploy/provision/` work on any node — run with `--node-id pmoves-5090`
