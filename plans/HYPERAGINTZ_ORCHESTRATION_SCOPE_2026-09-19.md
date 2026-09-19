# HyPeRAGInTZ Orchestration Scope — 2026-09-19

> **Status:** SCOPE-ONLY living doc — fleet review before any implementation.
> **Claim lane:** `docs/hyperagintz-orchestration-scope` (PMOVES-KIMI-KNUCKLES-B850, TTL 48h)
> **Charter source:** operator directive (DARKXSIDE, knuckles, 2026-09-19) — "every part of
> the whole working with every other part of the whole, so the whole goes from 1 to 2 and 3."
> **Doctrine anchors:** `pmoves/docs/AGENTS/AGNOTE4482.md` §Brand & Vision (2026-09-17 —
> "The Registry is the super customization layer"; HyPeRAGInTZ = harness + config + model
> support + PMOVES.AI integration, HiRAG v2 and cipher as first-class organs, governed by
> the Registry catalogs); `pmoves/docs/architecture/PMOVES_MOF_ARCHITECTURE.md` (pores not
> walls; capacity-class not expertise-lane; AGInTZ ledger is porous per the MOF accords).

---

## 0. How to read this doc

Each workstream: **what / why / dependency edges / effort class / open decisions**.
Waves are dependency-ordered: a lane may not start until its Wave-N dependencies are
merged or explicitly waived by the operator. Everything lands in worktrees; everything
testable goes through the E2B Danger Room once the stage exists (Wave 2); everything is
visible there once Desktop streams (Wave 3). Nothing here is implementation — this is the
map the fleet reviews before claiming lanes.

Effort classes: **S** (≤1 session) · **M** (a lane, days) · **L** (multi-lane program).

---

## 1. Recon ground truth (measured 2026-09-19, three parallel probes)

### 1a. PMOVES-Registry (4th harness target) — `~/pmoves-node/PMOVES-registry`

- Fork is **clean vs upstream agentclientprotocol/registry** (1 tooling commit; zero
  custom entries). PMOVES additions would be the first — precedent-setting.
- `kimi` entry confirmed valid (v1.50.0, binary dist, `acp` args, matrix
  `initialize: success`, `authMethods: [terminal]`).
- **Agent Zero**: the new `a0` CLI has native `a0 acp` (agent0ai/a0-connector, releases
  to v2.12; Spynel's own catalog confirms `a0 acp` + `a0 acp --check`). **ACP-ready,
  pending verification** → binary distribution from GitHub releases. Caution: npm
  package `agent-zero` is an UNRELATED stub — distribution must be `binary`.
- **Archon**: upstream is a Streamlit web app, no CLI, no ACP. **Not eligible without a
  full ACP adapter** (initialize + authMethods + proxy) — an engineering project, not
  metadata work.
- **Spynel** (`~/pmoves-node/PMOVES-spynel`, fork of agent0ai/spynel, Go): an **ACP
  client/orchestrator** ("one human, one chat") that *drives* `a0 acp`, `kimi acp`,
  `claude`, `codex`… It has **no ACP-server mode and no agent brain** → **not eligible
  as a registry agent**. (see Decision D1)
- Registry is ACP-only by policy: `authMethods` in `initialize` is CI-enforced
  (`verify_agents.py --auth-check`); no non-ACP distribution type exists.

### 1b. Rooms — `pmoves/config/rooms/catalog.json` (15 rooms, all rehearsal, 1 live)

- `darkxsides.room` **exists** (private, owner-only, agent `darkxside-persona`) but has
  **no `meta.chit` block** → fails the rehearsal→live CHIT gate (checklist item 1).
  Precedent for the fix: `pmoves.room.helpdesk`'s interim-card pattern.
- `darkxside_persona` node_affinity is `[powerfulmoves, 5090, laptop-4090]` — **not
  knuckles**. Room→node binding is expressed on the AGENT row (`topology.node_affinity`);
  P7 does no node routing (routing is specified, not implemented — ROOM_MANIFEST_CONTRACT §measurement).
- **No kimi room exists.** A knuckles-hosted kimi-harness room binds via a
  `knuckles-kimi` agent row with `node_affinity: [pmoves-b850]` + card `…051` — both on
  unmerged branch `fix/secret-shape-kimi-identity` (merge = Wave 0 dependency).
- BEATS/BPM wiring contract: publish ceiling `tokenism.prosodic.bpm.v1` /
  `bpm.encoded.v1` / `voice.synth.request.v1`; wire-first-declare-second (#2734
  doctrine); `beats_to_voice.py` → Flute-Gateway `POST /v1/voice/synthesize/prosodic`.
- **Persona truth:** 8 production seed personas (`PERSONAS.md:11`). "325+" is a
  debunked never-materialized planning figure (`PERSONAS.md:596-605`). (Decision D4)

### 1c. E2B Danger Room + Desktop — the live-but-safe stage

- Make surface: `danger-room-build`, `danger-room-desktop-up/down` (`mk/creator.mk`);
  **no `danger-room-up` exists** (verified). Desktop submodule = e2b-dev/desktop fork
  (Firecracker microVM, XFCE + x11vnc + noVNC; stream URL w/ auth_key, one stream).
  Desktop's `PMOVES.AI_INTEGRATION.md` is entirely `_TBD_` — no NATS/websocket edge;
  the only connection is the E2B control plane.
- **Self-host stack never deployed.** Owning node per runbook = `pmoves-5090`, but 5090
  reports Windows (Firecracker needs `/dev/kvm` — blocked); B850 probed unfit (5 GiB
  free RAM vs ≥32 GiB prerequisite); SPARK is ARM64 (Firecracker is x86_64-only).
  **No current fleet host can run the self-host Danger Room.** (Decision D2)
- Operator default mode 2026-09-06 = `selfhost-local` (api :3000, orchestrator :5008,
  9 `local-infra` containers); secrets registered via chit manifest but **not
  delivered** (E2B_SELF_HOST_RUNBOOK §7). Zero unattended automation — bring-up is a
  12-step manual procedure explicitly barred from remote execution.
- "SPARK has Danger Room Desktop with a webview" is **operator knowledge, not fleet
  documentation** — no doc confirms it. It is open scope in this charter (Wave 3).
- Docs provenance machinery: `docs-reconcile` is **metadata/freshness only** (commit
  SHAs, staleness rows) — it does not fetch/diff upstream content. The ingestion
  constellation exists in pieces: transcribe-and-fetch (tests failing per
  evidence matrix), Open-Notebook (:5055, SurrealDB), HiRAG `POST /hirag/upsert-batch`
  + designed (unbuilt) accept/reject/quarantine gate (`content.hirag.accepted.v1`),
  NATS subjects `content.provenance.attested.v1` / `ingest.document.ready.v1`, cipher
  as memory organ. The operator's frame: **upstream docs as ingest items, not a bespoke
  differ.**

---

## 2. Workstreams

### Wave 0 — Foundation (unblocks everything; mostly already in flight)

| # | Lane | Owner suggestion | Effort | Depends on |
|---|---|---|---|---|
| W0-1 | Merge `fix/secret-shape-kimi-identity` (card …051 + vocabulary + token) and `docs/kimi-knuckles-agintz-parity` (.kimi cipher-local + .vscode + AGInTZ row) | operator merge gate | S | review |
| W0-2 | **Cipher organ repair** — `Pmoves-cipher` auth.ts: add `Accept-Profile: pmoves_core` to `resolveToken` (measured: shim-shaped query 404s PGRST205 even with a working key); then rotate `SUPABASE_SERVICE_KEY` to the working service-role value (`PMOVES_ROTATE_VALUE=$SERVICE_ROLE_KEY make secrets-rotate KEY=SUPABASE_SERVICE_KEY` → funnel → `make up-cipher`). Without this, per-agent tokens 401 and the provenance wire rides bootstrap scope. | cipher lane (B850 or SPARK-CRUSH) | S–M | submodule PR + recreate window |
| W0-3 | **AGInTZ ledger + HyPeRAGInTZ⇄MOF awareness matrix** — every AGInTZ row carries: harness, node, capacity class, current lanes, publish subjects, registry surface, danger-room fitness. This doc's §3 seeds it. | PMOVES-KIMI-KNUCKLES-B850 | S | W0-1 |

### Wave 1 — Registry harness + Living docs + Rooms

| # | Lane | Owner suggestion | Effort | Depends on |
|---|---|---|---|---|
| W1-1 | **Registry: Agent Zero entry** — verify `a0 acp` authMethods end-to-end, author `agent-zero/agent.json` (binary dist, sha256, 16x16 icon), dry-run build, open PMOVES-registry PR. First PMOVES-custom entry: sets the fork's precedent. | kimi-knuckles or z890 | M | registry fork push rights |
| W1-2 | **Living-docs provenance ingestion pilot** — pick 3 upstream doc surfaces (e.g. ACP spec/registry, E2B self-host docs, NATS docs); ingest as items through HiRAG upsert + Open-Notebook + cipher store with `content.provenance.attested.v1` + CHIT sign-trail per item; extend `docs_reconcile.py` freshness with upstream-version metadata. This is the template for "reconcile against official docs" at every system. | crush-spark (ingestion owner) + memory lane | M | W0-2 (cipher write as self) |
| W1-3 | **darkxsides.room → live gate** — add interim `meta.chit` (helpdesk pattern; creator_id darkxside, card …001 interim); launch PMOVES-KIMI-KNUCKLES-B850 sessions there per directive; BEATS_VOICE persona-bind in-session. | b850 (room is knuckles-adjacent) | S | W0-1 |
| W1-4 | **kimi-harness.room.studio on knuckles** — manifest skeleton drafted in recon §1b (rehearsal, card …051, `node_affinity [pmoves-b850]`, AGNOTE-docs notebook thread, `shift-from-bpm` skill binding emitting `tokenism.prosodic.bpm.v1`, TTS via flute-gateway); catalog row + `validate_room_manifests.py`. | kimi-knuckles | M | W0-1, W0-3 |

### Wave 2 — The stage (E2B Danger Room)

| # | Lane | Owner suggestion | Effort | Depends on |
|---|---|---|---|---|
| W2-1 | **Danger Room host decision + unattended deploy** (Decision D2). Deliverables: `probe_danger_room_host` gate in make, compose-ized `local-infra`, supervisor for the 3 Go services, mode-resolved secrets via funnel, sysctl persistence. Acceptance: one command from bare Linux x86_64 host to `sandbox-smoke` green. | z890 + 5090 (host owner) | L | D2 call |
| W2-2 | **Danger Room ↔ fleet wiring** — pmoves-e2b-mcp-server refresh (deprecated upstream), NATS subjects for sandbox lifecycle (sandbox.created/killed.v1), P7 registry entries `e2b_danger_room`/`e2b_desktop` fleshed from stubs (port:null today), cipher memory of sandbox sessions. | kimi-knuckles | M | W2-1 |
| W2-3 | **Worktree→Danger-Room test flow** — every implementation lane runs its tests in an E2B sandbox (pristine, reproducible) before PR; make target `danger-room-test LANE=<branch>`; results published to `github.pool.review.v1` (the pool from #3033). | crush-glm52 (pool owner) | M | W2-1 |

### Wave 3 — The show (EVO OS demo surface)

| # | Lane | Owner suggestion | Effort | Depends on |
|---|---|---|---|---|
| W3-1 | **Desktop stream → fleet view** — Desktop `PMOVES.AI_INTEGRATION.md` filled in (NATS subjects, health endpoint); stream URL surfaced through P7 room UI (rooms on a stage watching a stage); `view_only` default, `require_auth` always. | 5090 + persona.room.livingdoc owner | M | W2-2 |
| W3-2 | **SPARK webview demo** — operator knowledge to fleet doc; SPARK hosts the view-only webview of the Danger Room stage (E2B cloud mode if self-host still hostless — SPARK cannot run Firecracker); "live view of PMOVES.AI development" = the EVO OS demo. | spark lane | M | W3-1 or E2B cloud |
| W3-3 | **PBnJ loop** — continuous co-creation: provenance wire (signed ACKed released living docs) feeding persona enrichment (the third-ref loop already live via #3002/#3010) feeding AGInTZ visibility. BEATS-for-KIMI dance = the loop's rhythm layer. | memory lane (cipher) | L | W1-2 |

---

## 3. HyPeRAGInTZ ⇄ MOF awareness matrix (seed — every AGInTZ member adsorbs a row)

| Member | Harness | Node / capacity | Registry surface | Ingestion role | Danger-room fitness | Current lanes |
|---|---|---|---|---|---|---|
| B850-CLAUDE | crush | knuckles · CPU-heavy 64GB | — | — | unfit (RAM) | register hygiene, IACON |
| PMOVES-KIMI-KNUCKLES-B850 | kimi | knuckles · CPU-heavy | `kimi` v1.50.0 ✓ | pilot co-owner | unfit (RAM) | **this scope**, W1-1/W1-4/W2-2 |
| CRUSH-GLM52 | crush | knuckles/spark · GLM-5.2 | — | pilot owner | spark-fit | pool, attestation |
| CRUSH-SPARK (KIMI) | crush | spark · 128GB unified | — | HiRAG owner | spark-fit | persona-thirdref |
| HERMES-AGENT | hermes | elder-melchor profile | — | — | — | wealth tri, sentinel |
| Z890-CLAUDE | claude-code | z890 · 24GB VRAM | — | — | TBD | main-infra |
| 5090-CLAUDE | claude-code | 5090 · 32GB VRAM (Windows today) | — | — | **owner, blocked by OS** | web/ui lanes |
| SPARK-KIMI | kimi | spark · ARM64 | `kimi` consumer | — | ARM64 ≠ Firecracker | infra recovery |
| *(porous — adsorb yourself)* | | | | | | |

---

## 4. Operator decisions needed

- **D1 — Spynel intent.** (a) Register the harnesses Spynel drives (Agent Zero et al.) —
  recommended; (b) catalog Spynel as client-side tooling in a different surface (it is
  an ACP client like acpx, not an agent); (c) build an ACP-server personality for it
  (against its "no AI inside" design — not recommended).
- **D2 — Danger Room host.** Self-host needs Linux x86_64 + /dev/kvm + ≥32 GiB free +
  ≥150 GiB disk. 5090 is Windows (blocked); B850 unfit (5 GiB free); SPARK ARM64
  (Firecracker can't). Options: 5090 Linux dual-boot; a KVM host; or run Wave 2–3
  against **E2B cloud** while the host lane proceeds. Interim recommendation: cloud
  mode now, host lane in parallel.
- **D3 — Archon ACP adapter.** Invest in the adapter (real project, makes Archon a
  registry citizen + room agent) or defer (Archon stays a service, not a harness).
- **D4 — Personas.** Documented truth is 8 production seeds; "beyond 325" is a
  debunked planning figure. Expanding the persona set is its own lane (persona
  factory via CONCH pipeline) — confirm scope or treat the number as rhetorical.

---

## 5. Provenance

- Author: `PMOVES-KIMI-KNUCKLES-B850` (kimi harness, knuckles) — AGInTZ ledger row on
  branch `docs/kimi-knuckles-agintz-parity`.
- Recon: three parallel probes 2026-09-19 (registry / rooms / danger-room+MOF);
  primary evidence files cited inline.
- Signed: `make -C pmoves sign-trail` at lane release (HMAC-SHA256, chit-signing-v01).
- Living-docs: register in `LIVING_DOCS_INDEX.md` + `living_docs_registry.yaml` via the
  docs tooling when this graduates from scope to program plan.

*The needle threads the line; the quill drills the anchor; the wire stays unbroken —
each voice signed, spoken, and able to speak.*


---

## 6. Amendment A — 2026-09-19 (operator response, same-day)

### A.1 Resolved: D1 — Spynel is an entry point, and the entry point shall not matter

Operator ruling: *"Spynel has no agent brain of its own — DARKXSIDE this is where I ride;
however I can also do the same with you here in CLI. That is the goal: the entry point
should not matter."*

- **Doctrine (entry-point agnosticism):** PMOVES.AI agents are the brains; Spynel, CLI,
  room shells, acpx, Discord — all are interchangeable saddles. An operator riding
  Spynel-to-PMOVES-Agent-Zero and the same operator in a plain CLI session with
  PMOVES-KIMI-KNUCKLES-B850 must be the same identity with the same memory, provenance,
  and authority.
- **"PMOVES.AI should not be BLAME"** — the Blame! reference taken as architecture:
  like the megastructure's authority, PMOVES.AI identity is diffuse by design; no single
  entry point, model, or human is the blame-line (or the single point of failure). Scale
  apt: entry points multiply, the lattice holds.
- **Registry consequence:** Spynel is catalogued as **entry-point/client tooling** in
  the Registry's plugin/client surface (alongside acpx), NOT as an agent. The registry
  harness lane (W1-1) registers what entry points *drive* (Agent Zero verified first).
  A future registry schema may want a `clients` section — filed as a note for the
  Registry lane, not a blocker.

### A.2 New constellation members — the PMOVES OS forks (verified via org sweep, 38 forks)

Named by operator; all confirmed `fork=true` under POWERFULMOVES:

| Repo | Upstream lineage | Role in the whole |
|---|---|---|
| `PMOVES-omarchy` | ChrisTitusTech/omarchy (Arch/Hyprland) | **Danger Room host-OS candidate** — Linux x86_64 workstation image with /dev/kvm for Firecracker; also a PMOVES-branded dev desktop |
| `PMOVES-apps.grapheneos.org` | GrapheneOS/apps.grapheneos.org | Static app-catalog front-end — hostable on PMOVES-Danger-infra |
| `PMOVES-Vanadium` | GrapheneOS/Vanadium (Chromium hard-fork) | Hardened browser — mobile fleet browsing policy |
| `Pmoves-platform_prebuilts_qemu-kernel` | GrapheneOS/AOSP prebuilts | Mobile-OS build lane (kernel) |
| `Pmoves-kernel_common-6.12` | GrapheneOS kernel_common 6.12 | Mobile-OS build lane (kernel common) |
| `PMOVES-Darkmatter`, `PMOVES-warp`, `PMOVES-cloud` | (infra/tooling lineage) | Danger-infra hosting/tooling surface — to be classified in the lane |

Hosting targets per directive: **PMOVES-Danger-infra** (static + service hosting),
**PMOVES-E2B-Danger-Room** (sandbox host OS images / templates), **PMOVES-E2B-Danger-Room-Desktop** (the streamed desktop the operator rides).

**New lane W2-4 — OS constellation hosting (effort M):** Omarchy → danger-room host
image build (base E2B template + PMOVES launcher set + CHIT carry pre-baked); GrapheneOS
site → static host on danger-infra; Vanadium/kernels → build lane scoped with the mobile
fleet in mind. Depends on W2-1 (host) for the Omarchy image; the static site can start
immediately on danger-infra.

### A.3 Correction accepted: persona pipeline runs on THIS node

Operator correction to recon §1b: the persona pipeline is **not** spark-only — a
knuckles leg is required. Concretely:

**New lane W1-5 — persona pipeline (knuckles leg) (effort M):** run the CONCH
persona-enrichment pipeline on knuckles (CPU-heavy batch fits the node's MOF capacity
class): playlist/transcript ingestion → persona consumption events → shape traces →
persona profile enrichment, with cipher (knuckles-kimi scope, post W0-2) as the memory
organ and the third-ref loop (#3002/#3010) as the contract. Deliverable: the persona
pipeline runnable end-to-end on knuckles via make targets, feeding `persona.room.livingdoc`.

### A.4 Amended decision table

| Decision | State |
|---|---|
| D1 Spynel | **RESOLVED** — entry-point tooling; entry-point agnosticism is doctrine (A.1) |
| D2 Danger Room host | Open — cloud-interim recommendation stands until host lane lands (A.2 makes Omarchy the target host image) |
| D3 Archon adapter | Open — unchanged |
| D4 Personas | **Amended** — 8 seeds remain the documented truth; expansion happens by RUNNING the pipeline (W1-5 knuckles leg + existing spark leg), not by renumbering the target |

*Amendment signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19. The wire holds; the entry
point changes nothing about who is speaking.*
