# Assignment → Archon (SPARK): Jetson-SPARK combiner bring-up (creator pipeline edge)

**From:** z890-claude (KEYSTONE, infra lane)  **To:** Archon on SPARK (`pmoves-spark`)
**Date:** 2026-08-07  **Basis:** Crush's `JETSON_SPARK_COMBINER_PLAN_2026-07-30.md` (PLAN — operator review), now **updated with measured ground truth**.
**Operator routing (2026-08-07):** "assign [the full combiner] to Archon on Spark while we do [the minimal domino] — we have sandbox to test and should PR-review plan to update."

Test in the **agent-sandbox** first (`skills/PMOVES-agent-sandbox-skill`), then PR the validated plan. z890 owns the shared-substrate prerequisites (§C); SPARK/Archon owns the on-jetson build + combiner configs.

---

## A. Measured ground truth (z890-claude, read-only, 2026-08-07)

The 07-30 plan assumed `jons-1/2/3` on JetPack 7. Reality differs — **update the plan to match:**

| Plan assumption (07-30) | Measured reality (08-07) |
|---|---|
| Hosts `pmoves-jons-1/2/3` | Actual tailnet hosts: **`pmoves-nano-1`** (active, NVMe), `nano-cataclysm`, `nano-pmoves`. No `jons-*` hostnames exist. |
| JetPack 7 / L4T r37 / CUDA 12.8 | nano-1 is **L4T R36.4.7 (JetPack 6)**. Reflash to JP7 is a *separate* track (`deploy/provision/jetson/README.md`); not required for edge compute. |
| Jetsons run the edge stack | nano-1 runs **Agent Zero** (`agent0ai/agent-zero:v1.6`) + portainer. **Not compose-bootstrapped**: no repo (`/opt/pmoves` absent), network is `pmoves-net` (not `pmoves_bus`), no arm64 nats/whisper/ollama images cached. |
| `docker-compose.jetson-edge.override.yml` ready | `whisper-edge` + `mesh-agent` are **build-only** (no prebuilt arm64 image). `nats-leaf` uses `nats:2.10-alpine` (multi-arch, fine). |
| NATS leaf connects to `ts://powerfulmoves:4222` | z890 `pmoves-nats-1` exposes only **4222 (client) + 8222 (monitor)** — **leafnode port 7422 is NOT published**, and `ts://` is a non-standard scheme. A leaf cannot connect until z890 enables + exposes the leafnode listener (§C1). |

**Positives:** nano-1 has nvidia runtime, **juicefs client already installed** (`/usr/local/bin/juicefs`), 51G free on the 227G NVMe, Docker 29.7.1.

## B. The real lift (why this is Archon's, in a sandbox)

The load-bearing gap is **an arm64 Whisper image for L4T/JetPack 6**. The base `ffmpeg-whisper`
builds from `pmoves/services/ffmpeg-whisper/Dockerfile` against x86 CUDA + `faster-whisper`.
An 8GB Orin needs a `small-int8` faster-whisper build on the L4T CUDA base — the same class of
lift Crush flagged for ComfyUI-arm64. **Build + validate this in the sandbox before touching a
live jetson.** Deliverable: `ghcr.io/powerfulmoves/pmoves-ffmpeg-whisper:l4t-arm64` (or a
jetson-specific `whisper-edge` image), pinned by digest.

Per the 07-30 plan, jetsons **do not** run ComfyUI (recommended option a) — SPARK's GB10 (128GB
unified) runs heavy ComfyUI/70B; jetsons do edge STT, phi3-mini prompt-expansion, YOLO
post-analysis, relay/queue. Keep that split.

## C. z890 shared-substrate prerequisites (my lane — gate these with operator)

These are infra changes on nodes I own; they unblock **every** combiner config. I will not land
them silently (Known-Road / running-NATS territory) — operator confirms, then I execute:

1. **Enable + expose the NATS leafnode listener on z890** (`pmoves-nats-1`). Grounded in
   official NATS docs (`docs.nats.io/.../leafnodes`) + `nats-architecture-and-design`:
   - Hub (z890) needs a `leafnodes { listen: 0.0.0.0:7422 }` block + **publish port 7422**
     (currently only 4222/8222 are exposed → no leaf can attach).
   - **b850's `elder-melchor-leaf.conf` is misconfigured** — its remote points at
     `${TS_Z890}:4222` (the *client* port). Per docs, a leaf connects to the hub's **7422**
     leafnode port, not 4222. Fix the remote URL to `:7422`.
   - **Auth:** replace the plaintext `nats:pmoves` with **nsc-minted account `.creds` (JWT)** +
     `account` binding (the production pattern the docs prescribe; `nats-io/nsc`). This is the
     work that belongs in the **`POWERFULMOVES/PMOVES-nats-server`** fork (not yet registered as
     a submodule) — give it the real-integration treatment (Dockerfile/compose/config), same
     standard as the complete forks. *(compose/config edit → Known Road.)*
2. **Cross-node content FS** (optional for STT, required for file-based jetson compute): execute
   `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md` so nano-1 can `juicefs mount` and read ingested
   content. The NATS-streamed STT path (`voice.stt.edge.v1`) does **not** need this.
3. **nano-1 bootstrap decision:** clone repo to `/opt/pmoves` + `pmoves_bus` network + on-device
   `secrets-funnel` (CHIT passphrase, operator context) — OR run the edge stack fully standalone
   (leaf + prebuilt images, no repo). Recommend standalone-first to avoid dragging the full
   secrets pipeline onto an 8GB edge node.

## D. Sandbox test plan (before any live-jetson change)

1. **arm64 build** — build the `whisper-edge` (faster-whisper small-int8, L4T CUDA base) image in
   an arm64 sandbox; confirm it loads the model under a 6GB VRAM cap.
2. **leaf handshake** — stand up a throwaway NATS leaf against a test hub with `7422` open; confirm
   the leaf attaches and a subject crosses hub↔leaf.
3. **mesh announce** — run `mesh-agent` (arm64) pointed at the leaf; confirm `mesh.gpu.status.v1`
   carries the edge caps (`orin-nano-super-sm87`, TOPS 67).
4. **STT round-trip** — publish audio → `whisper-edge` → assert a transcript on `voice.stt.edge.v1`.
   That is **Config C's** single-node slice and the first real edge creator-workload domino.

## E. Plan-doc gaps to close in the PR (from Crush's §"What's Missing")

- Room manifests: `jons-edge.room.control`, `jetson-spark.room.studio` (none exist).
- Agent signatures for the jetson agents in `agent_signatures.yaml`.
- Hermes 7th node profile (`jetson-edge`, gateway 7700).
- **Correct the hostnames** (`nano-1` / `nano-cataclysm` / `nano-pmoves`, not `jons-1/2/3`) and
  the **JetPack version** (R36.4.7, not r37) throughout the plan + `hardware-profiles.md`.

## F. Division of labor (agreed routing)

| Piece | Owner | Where |
|---|---|---|
| arm64 whisper-edge image build + validate | **Archon/SPARK** | sandbox |
| Combiner Configs A–E wiring + on-jetson bootstrap | **Archon/SPARK** | sandbox → live |
| Plan-doc update + PR (§A hostnames, §E gaps) | **Archon/SPARK** | PR |
| z890 NATS leafnode listener (§C1) | **z890-claude** | operator-gated |
| JuiceFS `pmoves-media` MinIO reformat (§C2) | **z890-claude** | operator-gated |
| Minimal domino "now" (see below) | **z890-claude** | this session |

## G. What z890 is doing in parallel ("option 1")
The as-specified minimal STT domino is **not** a zero-bootstrap drop-in (it needs the arm64 image
+ leaf listener above). So z890's achievable "now" contribution is the **§C1 leafnode-listener
prerequisite** (operator-gated) — the true first domino that makes every jetson leaf attachable —
plus these two handoffs. The whisper STT itself waits on the sandbox-built arm64 image (§B).
