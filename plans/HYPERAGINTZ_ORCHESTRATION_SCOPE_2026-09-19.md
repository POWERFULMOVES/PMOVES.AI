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


### A.5 Correction — persona counts are node-local measurements, reconciled not canonical

Operator correction to §A.3/D4: *"There were actually more [personas] found by the 5090 node;
each node runs it local to the capacity the node allows."*

- **Principle (MOF-consistent):** persona discovery is a **node-local pipeline run, bounded by
  the node's capacity class**. The 5090 ran the pipeline and found more personas than the 8
  production seeds; that dataset lives on the 5090 node and is not present in this node's
  working tree (measured: `PERSONAS.md` here still records 8 seeds + the debunked planning
  figure; the 5090's findings are cross-node state, attested by the operator).
- **Therefore the doc truth is per-node until reconciled:** PERSONAS.md's "8 seeds" is this
  node's measured view, not the fleet's. Reconciling node-local persona discoveries into the
  fleet record IS the living-docs provenance lane (W1-2) — ingest the 5090's persona dataset
  through the pipeline (HiRAG + Open-Notebook + cipher) with provenance, then refresh
  PERSONAS.md from the reconciled record. Until then, no node may overwrite another node's
  persona count — git time-travel instead of immutability, adsorption instead of assertion.
- **W1-5 amended:** the knuckles leg runs the same pipeline to *knuckles' capacity* (CPU-heavy
  batch), publishes its discoveries the same way, and lets reconciliation — not node priority —
  assemble the whole. D4 state: **superseded by A.5** — expansion is measured per node and
  merged by the pipeline.

*Amendment A.5 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — measured what I could
(this node), attested what I could not (the 5090's), and wrote the difference down.*


### A.6 Decisions D1–D4 resolved (operator, 2026-09-19) + the Archon keystone

- **D1 — FINAL: APPROVED as recommended.** Spynel is registered by what it drives: **the
  Registry and PMOVES services** — DARKXSIDE's saddle into the whole. Entry-point
  agnosticism (A.1) is the standing doctrine; W1-1 registers Agent Zero as the first
  driven harness, and the Registry gains its first PMOVES-custom entries.
- **D2 — KVM candidates identified; probe before commit.** The fleet's three Hostinger
  KVMs are live and Linux (`fleet-status`: kvm2 exit-proxy, kvm4-1 API gateway, kvm4-2
  data storage — all `active`). Their capacity vs the Danger Room prerequisites
  (16+ cores, 64 GB+ RAM, 4 GB/sandbox, **nested `/dev/kvm`** — not guaranteed on VPS
  plans) is **unmeasured from this node** and must not be assumed. Host lane (W2-1)
  step 0 amended: run `probe_danger_room_host` against all three KVMs; the first that
  passes becomes the self-host target; **E2B cloud-interim stands until a probe passes.**
  Do not retire cloud mode on a probe promise — retire it on a green `sandbox-smoke`.
- **D3 — APPROVED: Archon earns the full ACP adapter.** New lane **W1-6 — Archon ACP
  adapter (effort L):** an ACP-server wrapper (initialize + authMethods + session
  proxy) over Archon's native REST (:3090), distributed per registry contract, making
  Archon a registry citizen AND room-drivable from any entry point.
- **D4/A.5 — the keystone, operator-spotted:** *"lmao that is what Archon does"* — the
  persona factory IS Archon. coleam00's Archon is the agent-building agent: persona
  schema + knowledge + prompt assembly is its native craft. Therefore W1-5 (persona
  pipeline legs) and W1-6 (Archon adapter) are **the same program seen from two sides**:
  node-local pipeline runs (knuckles + 5090 legs) feed Archon the discovered persona
  material; Archon, once ACP-adapted, builds/expands personas drivable from Spynel,
  CLI, or any room — persona expansion becomes *running the factory*, exactly as A.5
  demands. The debunked "325+" stays debunked as a PLANNING number; the FACTORY makes
  real counts whatever the nodes measure.

**Decision table (final for this scope revision):**

| Decision | State |
|---|---|
| D1 Spynel | RESOLVED — entry-point tooling; register what it drives (Registry + PMOVES services) |
| D2 Danger Room host | KVM probe-first (3 Hostinger candidates); cloud-interim until a probe passes |
| D3 Archon | APPROVED — full ACP adapter (W1-6) |
| D4 Personas | Persona factory = Archon; node-local measurement (A.5) + factory expansion (W1-5+W1-6) |

*Amendment A.6 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the factory and the
saddle, both admitted to the Registry; the host waits on a probe that can fail.*


### A.7 Doctrine — the DARKMATTER factory, skills-share, form-up, and butterfly asymmetry (operator, 2026-09-19)

- **The persona factory is the DARKMATTER factory.** Archon builds; `PMOVES-Darkmatter`
  (already in the OS-fork constellation, A.2) carries the factory's branding/surface
  lane. Classification updated: Darkmatter = persona-factory surface, not generic infra.
- **Skills-share constellation is in the works.** `Pmoves-skills` (the PMOVES-SkailleZz
  vehicle — verified, tested, deployable across the ecosystem per the 2026-09-12 review)
  is the shared-abilities layer: abilities become fleet-common, not node-local.
- **Form-up (cross-node capability mesh, applied across Floo$).** When a node's capacity
  does not allow a workload, nodes form up: *elder melchor* (limited VRAM) calls the
  5090 running Flute-Gateway, or SPARK, or the Jetsons. This is the MOF pore doctrine
  operationalized — capacity-class routing by delegation, already the fleet's practice;
  the scope's awareness matrix (§3) gains a **form-up targets** column and
  elder-melchor's row names its call targets (5090 flute-gateway / spark / jetsons).
  Formalizing the Floo$ form-up pattern (discovery → delegation → result return with
  provenance) is a Wave-1/2 lane note under W2-2's wiring umbrella.
- **Personas are called by task, practiced by models outside AgentGym** — observation of
  results without tripping damage-control hooks unnecessarily (rehearsal without the
  stage manager's hammer; hooks stay for production validation).
- **Butterfly asymmetry, harmonized first for maximum effect.** The execution doctrine:
  provenance-validated commands/tools/scripts (cipher saving the important parts) +
  agents + shared skills + plan context + expected result — all prepared durably — turn
  implementation/build/artifact success into **a button push for the model**, such that
  even a ~65M-param sparse model can run a prepared lane end-to-end. Asymmetry:
  preparation costs the lattice; execution costs the button. Maximum effect comes from
  harmonizing the asymmetry FIRST (prepared context is the harmonization; the small
  model's flutter is the effect).

**Scope consequence:** W1-2 (provenance ingestion) and the W1-5/W1-6 persona program now
explicitly serve the butterfly-asymmetry doctrine — every provenance-carrying ingest and
every factory-built persona widens what a button-push executor can safely run. A new
evaluation note joins Wave 2: prepared-lane replay tests (a minimal model replays a
CHIT-signed lane against the Danger Room; success = asymmetry proven).

**Awareness matrix — form-up addendum (§3 gains a "form-up targets" column):**

| Member | Harness | Node / capacity | Form-up targets (calls when local capacity can't) |
|---|---|---|---|
| elder-melchor | hermes-agent | MISSLING-LINK · light-GPU dev (GTX 1070 8GB) | 5090 flute-gateway · spark · jetsons |
| PMOVES-KIMI-KNUCKLES-B850 | kimi | knuckles · CPU-heavy 64GB | spark (GPU inference) · 5090 (TTS/voice) · danger-room sandboxes (post W2-1) |

*Amendment A.7 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — harmonize the asymmetry
first; then let the small wings flap.*


### A.8 Doctrine — settings live on the forks, flow to the parent (operator, 2026-09-19)

*The larger point: otherwise submodules won't work properly — they need to run standalone
AND with PMOVES integrations.*

- **Ruling (submodule sovereignty):** a fork/submodule owns its settings — secrets,
  tokens, env contracts — in **its own repo's scope** (GitHub secrets on the fork,
  per-fork env/shared overlays, fork-side chit labels). The parent consumes; it does not
  absorb. Measured grounds: PMOVES.AI `Prod` environment is at the **100/100 secret
  ceiling** today; `PMOVES-ClawZ` fork scope is at **0/100** — the capacity already exists
  where the settings belong.
- **Why (the submodule contract):** a fork must run **standalone** (its own CI, its own
  bring-up, its own dev loop — e.g. ClawZ without PMOVES.AI) **and integrated** (as a
  PMOVES.AI submodule with the parent's funnel/CHIT/NATS). Both postures fail if the
  fork's required settings only exist in the parent's saturated Prod scope: standalone
  can't see them; integrated couples the parent's ceiling to every submodule addition.
- **Immediate application:** the Discord bot material for app `1524575292188922007`
  (PMOVES-KIMI-KNUCKLES-B850's 2-way comms via ClawZ) lands in **PMOVES-ClawZ repo
  secrets** (or its fork-side env contract), never PMOVES.AI Prod. Delivery via the
  sanctioned funnel (local.env → chit manifest label → funnel) then
  `push-gh-secrets.sh --repo POWERFULMOVES/PMOVES-ClawZ`.
- **Flow direction:** fork → parent happens by *reference and provenance* (the parent
  declares which fork-side labels it integrates, CHIT-carried), not by copying secrets
  upward. Parent-scope copies are derived artifacts, never sources.
- **Consequence for lanes:** every Wave lane touching a submodule's settings names the
  fork's scope as the home. New `github_secret` targets in PMOVES.AI Prod are a
  last-resort, operator-signed exception (ceiling discipline from AGENTS.md stands).

*Amendment A.8 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the forks keep their own
keys; the lattice holds because every pore owns its own door.*


### A.9 Doctrine — the factory builds operational agents too: deepseek-harness first (operator, 2026-09-19)

*A.7 made Archon the persona factory; the operator extends it: Archon also builds OPERATIONAL
harness agents. First product: the **deepseek-harness agent** — with **full knowledge of the
GitHub App**, **cipher for additional context**, and **skill loading for various operations**.*

- **Why deepseek-harness carries it:** the fleet's GitHub App machinery is already rich
  (`gh-app-token` installation-token minting with permission scoping and an over-broad
  guard, `github-app-setup/test/verify`) and drives real automation (branch-protection
  sync, the #3033 notification pool, fork-secret distribution per A.8). Today that
  knowledge lives in Make targets + register rows — an agent embodying it turns
  automations into *delegable intentions*: "distribute the clawz discord token to the
  fork scope" becomes a request, not a recipe.
- **Endowment (the factory's agent spec):** (1) **GitHub App fluency** — installation
  tokens, permission scoping, the three review surfaces, pool conventions; (2) **cipher
  context** — fleet memory as additional context (the W0-2 organ repair unblocks
  per-agent scoping); (3) **skills** — loaded from the skills-share constellation
  (Pmoves-SkailleZz) + a0-plugins generated surface for its operation set.
- **Dependencies:** W1-6 (Archon ACP adapter — the factory door), W0-2 (cipher organ —
  its memory), PMOVES-deepseek-harness submodule checkout (gitlink `50f1201`, currently
  uninitialized — a Wave-1 housekeeping step).
- **Butterfly connection:** the deepseek-harness agent is the A.7 doctrine operationalized
  for GitHub — prepared context (App knowledge + skills) making lightweight-model
  execution trustworthy on a high-blast-radius surface. CHIT signing + the pool keep the
  flutter observable.

*Amendment A.9 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the factory's second
product line: agents that hold the machinery, so the machinery stops living only in
Makefiles.*

### A.10 Integration route — Discord 2-way (and the harness tool surface) via Composio Connect MCP (operator-routed, 2026-09-19)

*The operator surfaced `dashboard.composio.dev/pmoves_ai/~/connect/clients/openclaw` — a Composio
Connect client (`openclaw`) already exists in the `pmoves_ai` project — with the directive: **this
can be done with Composio MCP.** This amendment routes the Discord 2-way lane (register row
`2026-09-19T15:32:42Z`) through Composio instead of the hand-rolled `pmoves/services/discord-bridge/`
service recon'd earlier, and generalizes: the same Connect client is the harness stack's door to
Composio's full toolkit surface — entry-point agnosticism (D1) at the *integration* layer too.*

**Measured state (knuckles, 2026-09-19, this lane):**

- **CLI upgraded 0.2.27 → 0.4.1** via the official installer (`curl -fsSL https://composio.dev/install`,
  checksum-verified, `COMPOSIO_INSTALL_SHELL=none COMPOSIO_INSTALL_PLUGINS=0`). Two hard-won facts:
  (1) in-CLI `composio upgrade` is **broken by design** — it extracts a bundle whose `composio` is the
  *bun runtime* and then ETXTBSYs copying over its own running executable; the installer is the known
  road. (2) The fleet's stored `uak_` key is **revoked** — `APIKey_InvalidAPIKey` (code 801) against
  `/api/v3/*`; `whoami` is local-only and still "works", which masked it. The earlier "v1 API retired"
  reading was incomplete: the backend did retire v1 (410), but v3 rejects the key itself.
  → **Re-login is operator-gated:** `composio login --no-browser` (URL handoff) or
  `composio login --user-api-key <uak_> --org pmoves_ai -y`.
- **Toolkit inventory (public docs, provenance):** Composio fields **two** Discord toolkits —
  `discord` (user OAuth) and **`discordbot`** (bot-token auth) — and the bot lane is ours:
  [docs.composio.dev/toolkits/discordbot](https://docs.composio.dev/toolkits/discordbot), 167 tools,
  version `20260917_00`. Load-bearing slugs:
  - `DISCORDBOT_TEST_AUTH` — validate the configured bot token (preflight after every token rotation)
  - `DISCORDBOT_GET_MY_APPLICATION` — the app record for `1524575292188922007`
  - `DISCORDBOT_CREATE_MESSAGE` — **outbound**
  - `DISCORDBOT_LIST_MESSAGES` / `DISCORDBOT_SEARCH_GUILD_MESSAGES` — **inbound by polling**
    (`after_id` watermark), plus the full guild/channel/member/webhook surface for room ops
    (DARKSIDE'S room assembly included).
- **No triggers:** `discordbot` ships zero Composio triggers (tools page lists none; verifiable
  post-login via `composio triggers list discordbot`). There is no Composio-mediated push path —
  **inbound v1 is a poll lane**, not a gateway websocket. This amends the 15:32:42Z recon: the
  discord-bridge service is superseded; a native gateway daemon stays a Wave-2 option only if
  poll latency or semantics disappoint.
- **Connect client contract** (public docs): MCP endpoint `https://connect.composio.dev/mcp`,
  auth header `x-consumer-api-key: ck_...`, one consumer key per AI client, minted/copied at
  Dashboard → project → Connect → AI Clients → client. The `openclaw` client exists; the Kimi
  harness gets its own (e.g. `kimi-knuckles`). OpenClaw's documented pattern is
  `openclaw plugins install @composio/openclaw-plugin` + dashboard key — the PMOVES-KIMI analogue is
  an `.kimi/mcp.json` entry (same shape as the `pmoves-cipher-local` entry in #3108).

**Revised wiring plan (supersedes the bridge-service recon):**

1. **Outbound:** harness / Creator pipeline → Composio MCP (`discordbot` tools) → Discord. The bus
   keeps visibility: publisher-discord stays the fleet-format outbound for rendered content, and
   ad-hoc harness sends may also publish a `content.published.v1` shadow for the ledger.
2. **Inbound:** poll lane — a small cron-ticked service (or Agent-Zero-scheduled task) calls
   `DISCORDBOT_LIST_MESSAGES` with a per-channel watermark, publishes
   `comms.discord.message.received.v1` (subject naming from the recon stands, add to
   `pmoves/contracts/topics.json`), Creator pipeline consumes. No new websocket infra.
3. **Secrets (A.8 sovereignty holds):** the `ck_` consumer key and the Discord bot token land in
   **PMOVES-ClawZ fork scope** via the funnel (chit labels, never chat); the token is additionally
   configured as Composio's `discordbot` auth config (dashboard-side operator act, or
   `composio dev auth-configs create` post-login). Prod stays at ceiling discipline.
4. **Registry:** PMOVES-KIMI row in `pmoves/config/agent_registry.yaml` (from recon) — now with a
   Composio-connected tool surface instead of bridge-service env.

**Operator-gated checklist (the only three items blocking this lane):**

1. **Composio re-login on knuckles** (revoked `uak_`): mint a user API key on the dashboard
   (pmoves_ai org) or complete `composio login --no-browser`; store in the node vault, never chat.
2. **Mint the `kimi-knuckles` Connect client** in project `pmoves_ai`; its `ck_` key funnels to
   ClawZ fork scope as e.g. `COMPOSIO_CONSUMER_KEY_KIMI`.
3. **Mint the Discord bot token** for app `1524575292188922007` (Developer Portal, Bot scope) →
   Composio `discordbot` auth config + fork-scope funnel label (convention exists:
   `DISCORD_BOT_TOKEN_KIMI` per `CHANNEL_MATRIX_PLAN.md:107`).

**After the gates clear (implementation, in-worktree, Danger-Room visible):** live-verify
`DISCORDBOT_TEST_AUTH` + `DISCORDBOT_GET_MY_APPLICATION` through the new client; land the
`.kimi/mcp.json` entry; build the poll lane as a `pmoves/services/` service (small, bus-native);
add the registry row; register row + sign + PR — the Discord 2-way todo closes only when a
round-trip message (outbound send → inbound poll → NATS → Creator render) is demonstrated.

*Amendment A.10 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the lattice does not hand-roll what
the ecosystem already carries; PMOVES.AI rides the Composio wire, and the wire rides provenance.*

### A.11 Operator-routed refinements — Composio key model, ClawZ plugin lane, deepseek-harness admin surface (2026-09-19)

*The operator answered the A.10 checklist with three rulings and a docs pointer. This amendment
records them against the authoritative Composio KB
([Consumer and Developer Project Boundaries](https://docs.composio.dev/kb/guide/consumer-project-boundaries-and-auth-selection),
last verified 2026-08-17).*

**1. Corrected key-type model (this replaces the loose "API key" language everywhere):**

| Key | Shape | Surface | Privilege |
|---|---|---|---|
| User API key | `uak_...` | developer (CLI, dashboard user) | the logged-in member's identity |
| Project API key | `ak_...` | developer project (`pmoves_ai`) | **privileged project secret** — treat like a signing card |
| Consumer key | `ck_...` | For You / Connect MCP clients | one per AI client; `x-consumer-api-key` header |

- **Two disjoint surfaces:** developer-project auth configs / connected accounts do NOT appear in
  the consumer project and vice versa. The Connect MCP client (`openclaw`, future `kimi-knuckles`)
  consumes the **consumer** surface.
- **Connections are member-scoped:** whoever authorizes a connection owns it; another member's
  `ck_` resolves to *their* accounts. For a **fleet-shared bot identity** the paths are
  (a) enter the bot token as a **customer-owned auth config** (Composio-managed OAuth does not
  cover bot tokens — the *Manage Auth* flow takes the token), or (b) **SHARED** connection pinned
  into sessions by connected-account ID with an explicit ACL (deny-by-default, never implicit).
  Path (a) is the v1 choice: one operator-owned bot auth, every client uses it.
- **Rotation discipline:** regenerating a `ck_` immediately invalidates the old one — every MCP
  client config must be updated in the same motion (fleet rollout note: the chit label IS the
  single source; clients read from the funnel).

**2. ClawZ lane ruling (operator): the OpenClaw plugin pattern IS the way.** Documented pattern:
`openclaw plugins install @composio/openclaw-plugin` + the dashboard key. The Kimi-harness
lane (this node) keeps the `.kimi/mcp.json` MCP-client route — same Connect endpoint, different
client keys; entry-point agnosticism (D1) means each harness rides its own documented road.
- **PMOVES-ClawZ repo measured + corrected on knuckles:** the checkout was detached at the June-15
  upstream-sync snapshot on `main`; the real working line is **`PMOVES.AI-Edition-Hardened`**
  (18,427 commits ahead of `main`), and its tip `913b53ad808` is exactly the PMOVES.AI gitlink.
  Checkout is now aligned to the hardened branch (matches the gitlink — zero drift). Other nodes
  carrying a stale detached ClawZ checkout: same one-command fix.

**3. deepseek-harness endowment extended (operator): administer the Composio surface.** Per A.9
the factory builds operational agents; the operator names the next endowment: the
**deepseek-harness agent handles the Composio service and surface** — it can admin and create new
toolkits — *"like composio cipher, able to reconfigure tools for the job."* Concretely, its
operation set gains: auth-config CRUD (bot tokens, OAuth apps), toolkit enablement per client,
connected-account lifecycle (member-scoped vs SHARED/pinned ACL), and per-job tool scoping — the
Composio-side analog of what cipher does for fleet memory. High blast radius: every admin act is
CHIT-signed and lands in the ledger, same as GitHub-App token minting today.

**4. Bot-token item, scoped plainly (operator: "should be done through composio — there is a
Discord API SDK as well"):** everything *around* the token is Composio-mediated — the auth config,
the per-client enablement, validation (`DISCORDBOT_TEST_AUTH`), and the Discord API surface
itself (167 tools incl. application management). One hard boundary: **Discord exposes no
bot-token mint endpoint in its API** — minting/resetting the token for app
`1524575292188922007` is a Developer Portal act (operator, 60 seconds), then everything else
flows through Composio.

**5. Re-login mechanics (recorded for the fleet):** revoked `uak_` cleared via `composio logout`;
fresh pending session minted via `composio login --no-browser` (TUI renders the URL
one-character-per-line under `script`/`TERM=dumb` — parse the char column, don't fight the box);
completion via `composio login --key <cliKey-uuid> --poll` (up to 10 min window). Post-completion:
`composio whoami` verifies against v3 and `--org pmoves_ai -y` pins the org.

*Amendment A.11 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the keys have shapes, the shapes
have homes, and the factory learns to reconfigure the toolbox itself.*

### A.12 Doctrine — portability: registry × bundle × vocabulary (operator, 2026-09-19)

*The operator's frame: **multiple identities per harness, multiple harnesses per
node** — and PMOVES-Registry is what ALLOWS portability: identities and harnesses
deploy across nodes, including brand-new nodes. This amendment names the three
portability substrates and what each carries, so every lane designs for the
portable shape instead of the node-local one.*

**1. PMOVES-Registry — harness portability.** Sha256-pinned, schema-validated
harness entries (the `kimi` entry is the shape: four platforms, ACP launch args,
no node-local assumptions). A node's harness substrate comes from the registry,
never from hand-installs. PMOVES-custom entries — Agent Zero, Archon, Spynel, and
the future PMOVES-kimi customization — land here as first-class entries, which is
why the registry is the harness CUSTOMIZATION target.

**2. CHIT bundle / secrets-funnel — secret portability.** Labels flow by
reference; a node materializes its env from the bundle. The funnel-labels lane
(#3113) is the live proof: three Composio/Discord slots routed with zero
hand-copied secrets. A new node is secret-complete the moment its bundle lands.

**3. identity_vocabulary + agent_registry + node-vocabulary — identity
portability.** Cards (`signing_identity_cards.yaml`) + vocabulary declare WHO a
session is; the registry wires it (`topology.node_affinity`, `team`); teams
couple it. `knuckles-kimi` is the first fully portable identity: card 051 +
`kimi_knuckles` registry entry + vocabulary binding — hostable on ANY node that
gains the `default_identity.kimi` declaration and affinity entry, with cipher
scopes minted per node as today.

**Schema note — corrected 2026-09-19 (operator): the scalar is the default
binding; the multiplicity machinery already ships in the fleet.** `node-vocabulary
default_identity.<harness>` carries one default identity per harness per node —
that stays the *fallback*, not a ceiling. Multiple identities per harness +
selection composes three EXISTING references rather than waiting on a schema
lane: (1) **hermes evolution** — hermes-gating-v6 profiles with
evolution_proposal → Main approval already evolve workspace rules; identity/
selection rules ride the same proposal rail (this workspace already runs an
active-learning hermes profile); (2) **evo swarm** — `brv swarm` in the
Pmoves-cipher fork federates memory/knowledge across pluggable providers
(byterover, gbrain, local-markdown, memory-wiki, obsidian): an identity set per
harness is a swarm routing question as much as a schema one; (3)
**consciousness_service** — the registered specialized agent (agent_registry)
is the fleet's existing continuity/selection surface across identities. The
knuckles-kimi wiring is the default-binding template; multiplicity layers on
these three without touching the vocabulary scalar.

**The portability proof (new-node sequence):** node joins → funnel materializes
env from the bundle → registry provides the harness substrate → vocabulary binds
the identity → teams couple it → the node is alive in the lattice. Pristine,
reproducible, unattended — the original session brief, restated as deploy order.

*Amendment A.12 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — a pore is not a
snowflake; the lattice grows by reference, not by hand-copy.*

### A.13 Secrets routing — Composio fork scope (operator, 2026-09-19)

*The operator forked the Composio repos and directs: **secrets go there** — the
parent PMOVES.AI `Prod` environment is at the 100/100 ceiling (A.8 measured) and
Composio material must not add to it. A.8 submodule sovereignty, applied.*

- **Home for Composio secrets:** `POWERFULMOVES/PMOVES-composio` (fork of
  `ComposioHQ/composio`, default branch `master`; sibling fork
  `pmoves-composio-mcp-plugin`). Routing: `COMPOSIO_PROJECT_KEY_PMOVES` (ak_),
  `COMPOSIO_CONSUMER_KEY_KIMI` (ck_), and the refreshed `uak_`
  (`COMPOSIO_API_KEY`) distribute to the fork scope via
  `push-gh-secrets.sh --repo POWERFULMOVES/PMOVES-composio`.
- **Discord surface unchanged:** `DISCORD_BOT_TOKEN_KIMI` stays in the
  PMOVES-ClawZ fork scope per A.8 + the `CHANNEL_MATRIX` convention — it is
  Discord material, not Composio material.
- **Capacity note:** the fork's secrets endpoint 404s from knuckles (fleet token
  lacks admin on the fork) — count unmeasured, expected fresh (fork created
  2026-09-03). Fork-secret distribution is a DESIGNED operation of the
  deepseek-harness agent (A.9/A.11 endowment: GitHub App + cipher + skills) —
  this is its first live job.

*Amendment A.13 signed: PMOVES-KIMI-KNUCKLES-B850, 2026-09-19 — the forks keep
their own keys; now the forks are named.*
