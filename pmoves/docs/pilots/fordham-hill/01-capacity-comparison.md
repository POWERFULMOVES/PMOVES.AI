<!-- PMOVES workflow fordham-pilot-convergence lane=capacity · needsHumanReview=True -->

# Capacity Comparison — Households per KVM vs. One Line per Home

**Pilot:** Fordham Hill (NYC housing cooperative) · **Lane:** Network Capacity
**Status:** Grounded in measured field data + in-repo capacity model. **Every rate/legal claim below is DRAFT — REQUIRES LEGAL REVIEW.**

---

## 1. The question, answered crisply

> **One kvm4-1-class node (~845 Mbps measured down) serves ~84 homes at the repo's own conservative budget, ~169 at 10:1, and ~338 at the ISP-typical 20:1. The current 3-node fleet (~1,976 Mbps aggregate down) serves ~197 (conservative) to ~790 (20:1) homes.**

Fordham Hill is a single co-op of a few hundred units. So **even one node conservatively covers a building's worth of homes, and the 3-node fleet covers it several times over with headroom to spare** — under the *same statistical multiplexing that Verizon already relies on* to sell you a "500 Mbps" plan it could never deliver to every subscriber simultaneously.

The honest catch is in §5: on an *already-fast* home line, routing through an exit node **lowers** peak speed. Pooling's real wins are cost, degraded/expensive links (Starlink), a static IP, resilience, privacy, and agents — not raw peak on a good line.

---

## 2. Measured field data (this session, median-of-3)

| Path | Down | Up | Latency | Jitter | IP |
|------|-----:|---:|--------:|-------:|----|
| Verizon Fios **direct** | 520 | 101 | 19 ms | 10 ms | dynamic residential |
| Through PMOVES **kvm4-1** | 305 | 70 | 22 ms | 8 ms | **static datacenter** |

**KVM exit-node raw uplinks** (each serves the whole mesh; all held DIRECT, non-relayed tunnels, ~2 ms to internet):

| Node | Down | Up | Specs (grounded) | Cost |
|------|-----:|---:|------------------|-----:|
| kvm4-1 | **845** | 347 | 8C / 16GB — `TOPOLOGY.md:20` | $10/mo |
| kvm4-2 | **683** | 704 | 8C / 16GB — `TOPOLOGY.md:21` | $10/mo |
| kvm2   | **448** | 372 | 4C / 8GB — `TOPOLOGY.md:22` | $10/mo |
| **Fleet total** | **1,976** | 1,423 | 3 live nodes, tailnet `tailcad9b4` | ~$30/mo |

**Demand basis:** real household *peak* demand ~50 Mbps (4K stream 25 + HD call 5 + several devices). Busy-hour *average* per active home is far lower — typical residential ~2–6 Mbps — which is exactly why ISPs oversubscribe 20:1–50:1. This deliverable uses **50 Mbps peak-plan** and **~4 Mbps busy-hour-average** as the two bracketing bases.

---

## 3. The model (and its one honest anchor-correction)

The repo already carries the density math: `FLEET_CAPACITY_ANALYSIS.md` §6 (`:121`–`:144`) states *"Hostinger KVMs deliver ~1 Gbps symmetrical; 10 Mbps/user peak budget yields ~100 concurrent users per KVM,"* and §5 (`:95`) codifies the *"10% peak concurrency"* multiplexing assumption. The **only** calibration needed: the measured uplinks (448–845 down) are **below** the assumed nominal 1 Gbps, so every figure here is re-anchored to *measured* down-Mbps rather than the placeholder.

Formula (downstream is the residential constraint):

```
homes = node_downlink_Mbps / per_home_effective_budget_Mbps
oversubscription_ratio (R:1 vs the 50 Mbps retail plan) = 50 / per_home_effective_budget
```

- **Peak-plan basis** = budget 50 Mbps = R 1:1 (worst case, unrealistic — every home peaks at once).
- **Busy-hour-average basis** = budget ~4 Mbps ≈ R **12.5:1** (the model ISPs actually run).
- The repo's conservative **10 Mbps/user** budget = R **5:1**, and sits *above* the 4 Mbps busy-hour average, so it carries real headroom.

**Any row where the effective budget stays ≥ 4 Mbps (R ≤ 12.5) provisions at or above the measured busy-hour average → congestion is rare. Rows past 12.5:1 sell below the average and lean on statistical multiplexing + fair-share shaping (not yet implemented — see §7).**

---

## 4. Sensitivity tables

### Table A — Peak-plan basis (home = full 50 Mbps retail peak)

`homes = downlink x R / 50`. Effective per-home budget = `50 / R`.

| Oversub | Per-home budget | kvm2 (448) | kvm4-1 (845) | kvm4-2 (683) | **Fleet (1,976)** | Congestion posture |
|--------:|----------------:|-----------:|-------------:|-------------:|------------------:|--------------------|
| **1:1** (peak) | 50 Mbps | 9 | 17 | 14 | **40** | Every home full-peak simultaneously — hard-guaranteed floor |
| **5:1** (repo §6 conservative) | 10 Mbps | 45 | **84** | 68 | **197** | Well above busy-hour avg — safe, recommended floor |
| **10:1** | 5 Mbps | 90 | 169 | 137 | **395** | ~busy-hour avg + headroom — safe |
| — *12.5:1 crossover* — | *4 Mbps* | *112* | *211* | *171* | *494* | *busy-hour saturation line (see Table B)* |
| **20:1** (ISP-typical) | 2.5 Mbps | 179 | 338 | 273 | **790** | Below avg — relies on multiplexing + shaping |
| **30:1** | 1.67 Mbps | 269 | 507 | 410 | **1,186** | Aggressive — shaping mandatory |
| **50:1** (ISP-aggressive) | 1.0 Mbps | 448 | 845 | 683 | **1,976** | Upper bound; fair-share enforcement essential |

### Table B — Busy-hour-average basis (home draws ~4 Mbps busy-hour)

`homes = pipe_utilization x downlink / 4`. This is the statistical reality-check: how many homes fit before the pipe's *average* load reaches a target. It reconciles with Table A at the 12.5:1 crossover (100% util row).

| Pipe utilization target | kvm2 (448) | kvm4-1 (845) | kvm4-2 (683) | **Fleet (1,976)** |
|------------------------:|-----------:|-------------:|-------------:|------------------:|
| 50% (deep headroom) | 56 | 106 | 85 | **247** |
| 70% (comfortable) | 78 | 148 | 120 | **346** |
| 85% (busy) | 95 | 180 | 145 | **420** |
| 100% (saturation ceiling) | 112 | 211 | 171 | **494** |

**Read:** at a comfortable 70% busy-hour utilization the 3-node fleet carries **~346 homes** with room to breathe; one kvm4-1 alone carries **~148**. A single Fordham Hill building fits inside one node at safe utilization, and inside the fleet many times over.

---

## 5. (A) Verizon vs. (B) PMOVES — the structural comparison

| Dimension | (A) Verizon — 1 line / home | (B) PMOVES — N homes / KVM |
|-----------|-----------------------------|-----------------------------|
| Capacity model | Each home buys its own peak; ISP oversubscribes upstream invisibly | Homes pool one KVM; oversubscription is explicit + operator-owned |
| Cost scaling | **Linear** — every home pays separately (~$35/mo premium upcharge measured, $420/yr) | **Pooled** — one KVM ~$10/mo (`TOPOLOGY.md:20`) spread across ~50+ homes |
| Public IP | Dynamic residential (rotates, geo-blocked, no inbound) | **Static datacenter** IP (31.97.42.207 measured) — stable, hostable |
| Resilience | Single line down = home offline | Multi-node mesh; a home can fail over across exit nodes |
| Adds | None | Agents, open MANET, privacy egress, community tokenomics (ToKenism) |
| Headroom | Owned by the ISP, invisible to you | **Shared** across the co-op; strengthens with every node added |

**Cost intuition (DRAFT — REQUIRES LEGAL REVIEW):** if ~50 homes each drop a $35/mo premium upcharge and instead share three $10/mo KVMs (~$30/mo total, ~$0.60/home/mo), the *upcharge* line item collapses by roughly two orders of magnitude — while adding a static IP, agents, and mesh resilience no single-home plan offers. This is a *pooling-of-the-premium-tier* argument, **not** a claim that PMOVES replaces each home's base access line (it does not — see §6).

---

## 6. The honest caveat (do not skip this in resident materials)

**The first hop is still each home's own access line.** Routing through an exit node cannot make a home's own line faster — it adds a hop. The measured proof: **through kvm4-1 = 305/70 Mbps vs. direct Fios 520/101** — the exit path is *slower* for peak on an already-fast line, because (a) you inherit the node's tunnel overhead and (b) Tailscale/WireGuard encapsulation caps per-tunnel throughput (raw node uplink 845 down, but only ~305 reaches the client through the tunnel).

Therefore the density figures in §4 describe **aggregate shareable uplink**, while **any single home's ceiling through the tunnel is ~305 down** — this per-tunnel overhead must be re-measured per home before promising aggregate density as if the raw uplink were fully shareable.

**Where pooling actually wins:**
1. **Degraded / expensive links** — on Starlink, congested cable, or a metered LTE backup, a fat datacenter exit node can *beat* the home's own path. This is the case to measure directly (§8 probe).
2. **Shared cost** — the premium/static-IP/egress tier is bought once and split, not paid per home.
3. **Static IP + resilience + privacy + agents** — capabilities a residential plan simply does not sell.

The pitch to the co-op is *cost + capability + resilience under shared multiplexing* — **not** "faster peak speed on your already-fast line."

---

## 7. Known gaps (disclosed — Emperor-CHIT-Humility)

- **Fair-share not enforced.** No per-user rate-limit / QoS / HTB shaping exists in the repo. Every row past ~12.5:1 in Table A *assumes* good behavior rather than enforcing it. Fair-share shaping is a prerequisite before running above the busy-hour crossover.
- **Uplink not machine-tracked.** `pmoves/config/profiles/*.yaml` carry no NIC/throughput field, and `json-to-profile.py` drops the `speed_mbps` that `glances-autodetect.sh` captures — so per-node capacity has no data source of record yet. Recommend adding an `uplink_mbps` field fed by the §8 probe.
- **No load baseline.** `LOAD_TEST_BASELINE.md` (called for in §9.2 of the capacity doc) has never been created; all figures remain best-estimate until a real probe run lands.
- **Colocation rule.** `FLEET_CAPACITY_ANALYSIS.md:140-144` is a HARD rule: kvm4-1 today runs API gateway + YT egress — **do NOT** add paying resident exit traffic to it before splitting the exit tier to a dedicated VPS. The density math assumes a dedicated node.
- **No dedicated exit-node runbook.** Closest coverage is `YT_EGRESS_RUNBOOK.md` (live kvm4-1 egress) + `deploy/provision/kvm2-exit-node.sh` (older draft, never activated — `TOPOLOGY.md:169-171`).

---

## 8. Starlink A/B degraded-link probe (operator runs WHEN on Starlink)

Portable POSIX `sh`, safe **set → test → restore** (restores your original exit node via `trap`, even on Ctrl-C). Measures down/up/latency/jitter **direct** and **through each exit node**, median-of-3 (mirroring this session's field method), and emits JSON whose per-path objects reuse the `glances-autodetect` `speed_mbps` convention so results can flow into a future per-node `uplink_mbps` capacity field. Save as `deploy/provision/exit-node-healthcheck.sh` (does **not** exist yet — this is net-new).

```sh
#!/bin/sh
# exit-node-healthcheck.sh — Starlink A/B exit-node capacity probe.
# Safe set->test->restore. Run ON the degraded link (e.g. Starlink) to capture
# the pooling win. Requires: tailscale, ping, and an Ookla `speedtest` (JSON) —
# falls back to `speedtest-cli --json`. `jq` optional (better parsing if present).
#
# Usage: sh exit-node-healthcheck.sh kvm4-1 kvm4-2 kvm2
#   args = tailscale exit-node names/IPs to A/B against DIRECT. Default: kvm4-1.
set -eu

RUNS=3
NODES="${*:-kvm4-1}"
OUT="exit-node-ab-$(date +%Y%m%dT%H%M%S).json"

command -v tailscale >/dev/null 2>&1 || { echo "tailscale not found" >&2; exit 1; }
if command -v speedtest >/dev/null 2>&1; then ST="ookla";
elif command -v speedtest-cli >/dev/null 2>&1; then ST="cli";
else echo "need Ookla 'speedtest' or 'speedtest-cli'" >&2; exit 1; fi
HAVE_JQ=0; command -v jq >/dev/null 2>&1 && HAVE_JQ=1

# --- capture current exit node so we can restore it no matter what ---
ORIG_EXIT=""
if [ "$HAVE_JQ" -eq 1 ]; then
  ORIG_EXIT=$(tailscale status --json 2>/dev/null | jq -r '.ExitNodeStatus.ID // ""' 2>/dev/null || echo "")
fi
restore() {
  if [ -n "$ORIG_EXIT" ]; then tailscale set --exit-node="$ORIG_EXIT" 2>/dev/null || true
  else tailscale set --exit-node= 2>/dev/null || true; fi
  echo "restored exit node -> ${ORIG_EXIT:-<none>}" >&2
}
trap restore EXIT INT TERM

median() { printf '%s\n' "$@" | sort -n | awk '{a[NR]=$0} END{print a[int((NR+1)/2)]}'; }

# down/up in Mbps, latency+jitter in ms; echoes: "<down> <up> <lat> <jit>"
run_speed() {
  d=0; u=0; l=0; j=0
  if [ "$ST" = "ookla" ]; then
    R=$(speedtest --accept-license --accept-gdpr -f json 2>/dev/null || echo "")
    if [ "$HAVE_JQ" -eq 1 ] && [ -n "$R" ]; then
      d=$(printf '%s' "$R" | jq -r '(.download.bandwidth*8/1e6)|floor')
      u=$(printf '%s' "$R" | jq -r '(.upload.bandwidth*8/1e6)|floor')
      l=$(printf '%s' "$R" | jq -r '(.ping.latency)|floor')
      j=$(printf '%s' "$R" | jq -r '(.ping.jitter)|floor')
    fi
  else
    R=$(speedtest-cli --json 2>/dev/null || echo "")
    if [ "$HAVE_JQ" -eq 1 ] && [ -n "$R" ]; then
      d=$(printf '%s' "$R" | jq -r '(.download/1e6)|floor')
      u=$(printf '%s' "$R" | jq -r '(.upload/1e6)|floor')
      l=$(printf '%s' "$R" | jq -r '(.ping)|floor')
    fi
  fi
  echo "$d $u $l $j"
}

measure_label() {  # $1 = label, emits a JSON object for one path
  label="$1"; ds=""; us=""; ls=""; js=""
  i=1; while [ "$i" -le "$RUNS" ]; do
    set -- $(run_speed)
    ds="$ds $1"; us="$us $2"; ls="$ls $3"; js="$js $4"
    i=$((i+1))
  done
  md=$(median $ds); mu=$(median $us); ml=$(median $ls); mj=$(median $js)
  printf '{"label":"%s","down_mbps":%s,"up_mbps":%s,"latency_ms":%s,"jitter_ms":%s,"runs":%s}' \
    "$label" "${md:-0}" "${mu:-0}" "${ml:-0}" "${mj:-0}" "$RUNS"
}

echo "[probe] baseline DIRECT (exit node cleared)..." >&2
tailscale set --exit-node= 2>/dev/null || true
RESULTS=$(measure_label "direct")

for n in $NODES; do
  echo "[probe] through exit node: $n ..." >&2
  if tailscale set --exit-node="$n" 2>/dev/null; then
    sleep 3    # let the tunnel settle
    RESULTS="$RESULTS,$(measure_label "exit:$n")"
  else
    echo "[probe] WARN could not set exit node $n — skipping" >&2
  fi
done

{
  printf '{"schema":"exit-node-ab/v1","captured_at":"%s","link_under_test":"%s","paths":[%s]}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${LINK:-unknown}" "$RESULTS"
} | tee "$OUT"
echo "[probe] wrote $OUT" >&2
# trap restores your original exit node automatically on exit.
```

**How to read the output:** on Starlink you expect `exit:kvm4-1` to show *higher, steadier* `down_mbps` and *lower jitter* than `direct` — that gap is the pooling win, and it is the number worth putting in resident materials (with the `link_under_test` labeled "Starlink"). On an already-fast Fios line you expect the opposite (direct wins), which is the §6 caveat in data form. Set `LINK=Starlink` in the environment to stamp the capture.

---

## 9. Grounded sources

- `pmoves/docs/operations/FLEET_CAPACITY_ANALYSIS.md:124-125` — the "~1 Gbps / 10 Mbps-per-user / ~100 users per KVM" density anchor (re-calibrated here to measured uplinks).
- `pmoves/docs/operations/FLEET_CAPACITY_ANALYSIS.md:95` — the "10% peak concurrency" statistical-multiplexing assumption.
- `pmoves/docs/operations/FLEET_CAPACITY_ANALYSIS.md:140-144` — HARD rule: do not colocate paying exit traffic with API traffic; split the exit tier first.
- `pmoves/docs/operations/TOPOLOGY.md:20-22` — KVM specs and $10/mo cost per node.
- `pmoves/docs/operations/TOPOLOGY.md:169-171` — kvm2-exit-node.sh is an older draft, never activated; live egress is kvm4-1.
- `deploy/provision/glances-autodetect.sh` — captures `nics[].speed_mbps` (schema the probe mirrors); `deploy/provision/json-to-profile.py` currently drops that value.
- Measured field data (this session, median-of-3) — all Mbps/latency/IP figures in §2.

**Every rate, cost-saving, and structural claim intended for resident-facing use is DRAFT — REQUIRES LEGAL REVIEW.**