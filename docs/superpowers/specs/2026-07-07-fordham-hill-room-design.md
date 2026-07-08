# Fordham Hill Community Room — Design Spec

_Spec date: 2026-07-07 · Status: DRAFT · Room id: `fordham.room.community` · Stage: `rehearsal`_

> One shared box delivers cheaper+more-private internet **and** the tamper-evident ledger/ballot box
> for co-op self-governance. This spec turns that four-lane pilot into one **room-on-a-stage** so P7 can
> launch it, Archon can mint its agents, and residents get a single audience-facing surface instead of
> four disconnected docs. Every dollar/vote/governance claim in this room is
> **DRAFT — REQUIRES LEGAL REVIEW** (pmoves/docs/pilots/fordham-hill/README.md:3).

## Honesty key (carried from the pilot)

This room inherits the pilot's three-tier framing verbatim — no claim may cross a tier boundary in the UI:

- **PROVEN (measured this session):** the 3 KVM exit nodes run and were measured (845/683/448 Mbps down,
  ~1,976 aggregate; $10/mo/node); HMAC `sign_cgp` vote-receipt primitive exists and is tested
  (pmoves/docs/pilots/fordham-hill/README.md:10).
- **MODELED (projected arithmetic, not adopted):** homes-per-node (~84/node, ~197 fleet), the ~$10 pooled
  due, ~$25/mo ($300/yr, 71%) per-home saving, Dirichlet contribution attribution
  (pmoves/docs/pilots/fordham-hill/README.md:12).
- **SCAFFOLDED (designed, needs humans before binding use):** the governance layer — roll lists 1 of N
  (users.yaml:9), on-chain governor is plutocratic quadratic-stake with a flat quorum
  (CoopGovernor.sol:72/:96) and MUST NOT ship as-is for a board election
  (pmoves/docs/pilots/fordham-hill/README.md:14).

The room renders each surface **badged** with its tier. The fraud investigation stays human-led
(PMOVES-mike + Missing Link); the platform provides transparency/auditable records only, never accusations
(pmoves/docs/pilots/fordham-hill/README.md:16).

---

## 1. Purpose — why a room, not just docs

The pilot README already proves the four lanes are "one system seen from four angles"
(pmoves/docs/pilots/fordham-hill/README.md:8). But a README is not an audience-facing topology. Per the
Room Manifest Contract, "a room is the audience-facing topology — the entrypoint through which users
(human or agent) access the platform's capabilities" (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:26). The
Fordham Hill residents and Committee on Elders are exactly the "human users" that contract is written for.

A room (vs. loose docs) buys four things the pilot cannot get from Markdown:

1. **A single declared shell.** Panels/apps/routes become a manifest P7 can select and stage-manage
   (rehearsal → live → review → archive), instead of implied setup
   (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:18).
2. **Durable notebook state separated from presentation.** Room owns presentation; notebook owns durable
   state (the voter roll, the dues ledger, the vote receipts) so a resident session can reopen the same
   threads/snapshots later (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:69).
3. **Room-aware skill bindings.** The pilot's real primitives (mesh-egress-ab, pmoves-chit-sign,
   persona-bind) bind to declared surfaces with guardrails, not raw UI assumptions
   (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:70).
4. **Agents Archon can actually mint.** Four resident-facing roles become mint specs on
   `archon.mint.agent.v1 → archon.mint.confirmed.v1`, not hand-rolled service code.

Naming follows `<name>.room.<type>` (e.g. `demo.room.rehearsal`,
pmoves/config/rooms/catalog.json:37) → **`fordham.room.community`**, `room_type: community`,
`owner_mode: shared` (a co-op is a shared identity, not one agent's alter). Stage starts at `rehearsal`,
mirroring the demo room's `"stage": "rehearsal"` (pmoves/config/rooms/demo.room.json:153).

> Note: `room_type: community` and `owner_mode: shared` are proposed additions. The current schema enum is
> `operator|builder|scout|creator|viewer|hybrid` (room.manifest.v1.schema.json:45) and
> `owner_mode` is `primary|alter|shared|ephemeral` (`shared` already valid, :48). Either extend the
> `room_type` enum to include `community`, or fall back to `hybrid` for the seed manifest. **Operator
> decision — flagged in §7.**

---

## 2. Room shape (shell / panels / apps)

Mirrors the shape of the validated `4090-field.room.control.json` seed
(pmoves/config/rooms/4090-field.room.control.json) so it diffs and validates like any other room.

**Shell** — `theme_id: fordham-community`, a warm resident-facing accent (not the ops-green
`#065F46`); layout `default_route: /dashboard/fordham/overview`.

**Panels** (schema-valid `kind`/`position`, room.manifest.v1.schema.json:96/:99):

| panel_id | kind | position | purpose |
|---|---|---|---|
| `voice-console` | `chat` | left | FlOO$ spoken interaction (the accessibility front door) |
| `pilot-overview` | `custom` | center | the four-lane dashboard, each tile tier-badged |
| `ledger-graph` | `graph` | right | contribution/roll trail (who contributed == who may vote) |

**Apps** (each declares `route` + `action_namespace` + `capabilities`, room.manifest.v1.schema.json:125):

| app_id | kind | route | action_namespace | status | notes |
|---|---|---|---|---|---|
| `pilot-dashboard` | `dashboard` | `/dashboard/fordham/overview` | `fordham` | `active` | served by `deploy/provision/pilot-dashboard-serve.sh`; generated by `pilot-dashboard-gen.sh` |
| `mesh-ab` | `dashboard` | `/dashboard/fordham/capacity` | `capacity` | `active` | A/B measured vs. raw uplink (mesh-egress-ab skill) |
| `coop-ledger` | `dashboard` | `/dashboard/fordham/wealth` | `wealth` | `planned` | Firefly III co-op ledger view (life-team `wealth` agent, agent-teams.yaml:166) |
| `voter-roll` | `notebook` | `/dashboard/fordham/roll` | `governance` | `planned` | eligible-voter roll + enrollment; `planned` because roll = 1 of N today (users.yaml:9) |
| `ballot-box` | `dashboard` | `/dashboard/fordham/governance` | `governance` | `planned` | HMAC vote receipts; `planned` — MUST NOT go `active` until legal + one-member-one-vote basis resolved |

App `status` values are schema-supported (`active|planned|deprecated`,
room.manifest.v1.schema.json:153) — governance surfaces ship as `planned` so the room can **declare**
them without any binding vote path being reachable in rehearsal (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:306).

**Notebook** — `provider: open-notebook`, `workspace_ref: fordham-hill`, `sync.mode: mirrored`,
`writeback_targets: [entries, threads, pages, snapshots]`, `artifact_prefix: rooms/fordham-community`.
The notebook is the durable plane that holds the roll, the ledger entries, and the vote receipts; the room
never replaces it (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:44).

**Runtime taxonomy** (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:316):
- `team_refs`: `[life, infra, media, orchestration]` — wealth/health (life, agent-teams.yaml:159),
  mesh/headscale (infra, :120), voice (media, :41), Archon minting (orchestration, :10).
- `service_refs`: `[archon, nats, supabase, flute-gateway, headscale, wealth]`.
- `launcher_refs`: `[pilot-dashboard-serve, up-agents]`.

---

## 3. Agent roster — the 4 roles (Archon mint specs)

All four are **mint specs** Archon consumes via `archon.mint.agent.v1`, confirmed on
`archon.mint.confirmed.v1`. Each is scaffolded with the `archon:mint-agent` skill (persona doc + form +
room assignment + NATS mint event). Each role names the room-bound skills it owns.

### 3.1 `fordham-onboarding` — enrollment
- **Owns:** enrolling a resident onto the mesh **and** onto the eligible-voter roll in one act — because
  "who may vote" and "who contributed" are two reads of one source of truth
  (pmoves/docs/pilots/fordham-hill/README.md:40). Writes the roll into the `voter-roll` notebook app;
  emits a `fleet:enroll` CHIT-signed device token.
- **Binds:** `fleet:enroll` (device enrollment token), `pmoves-cipher-memory` (durable roll memory).
- **Surface:** `voter-roll` app (`/dashboard/fordham/roll`), toolbar activation.
- **Guardrail:** `require_approval: true` — no resident is added to the *eligible* roll without human
  confirmation (the roll is legally load-bearing; today it lists 1 of N, users.yaml:9).

### 3.2 `fordham-transaction` — pooled dues / co-op ledger / surplus
- **Owns:** the pooled-dues → Firefly III co-op ledger → surplus accounting. Every line maps to a real
  Firefly account type; the ~$25/mo saved per home is exactly what the ledger books as community surplus —
  one flow of money, two lanes (pmoves/docs/pilots/fordham-hill/README.md:36). Drives the life-team
  `wealth` agent (agent-teams.yaml:166).
- **Binds:** `pmoves-chit-sign` (signed surplus/dues trail receipts), `pmoves-cipher-memory`.
- **Surface:** `coop-ledger` app (`/dashboard/fordham/wealth`).
- **Guardrail:** every figure rendered is tier-badged **MODELED / illustrative**; no figure is presented as
  adopted until the operator sets the ADOPTED RATE (§7) — three dollar anchors ($5 product, $10 due, $35
  premium) are unreconciled (pmoves/docs/pilots/fordham-hill/README.md:37).

### 3.3 `fordham-creator` — resident materials + dashboard
- **Owns:** resident-facing materials (flyers, plain-language explainers, the meeting one-pager) and the
  generation half of the pilot dashboard (`deploy/provision/pilot-dashboard-gen.sh`). Routes render work
  through the media-team `creator` pipeline (agent-teams.yaml:57).
- **Binds:** `pmoves-cipher-memory`; pilot-dashboard generator; (creator/ComfyUI pipeline as available).
- **Surface:** `pilot-dashboard` app (`/dashboard/fordham/overview`).
- **Guardrail:** `require_approval: true` on any resident-distributed artifact — no material leaves the
  room asserting a binding figure or a fraud accusation (transparency only,
  pmoves/docs/pilots/fordham-hill/README.md:16).

### 3.4 `fordham-voice` — spoken, accessible interaction
- **Owns:** the speaking front door. Binds a FlOO$ suit to the session voice pipeline so residents (incl.
  low-vision / low-literacy / elder members) interact by voice. Uses the media-team `flute_gateway`
  prosodic synth (agent-teams.yaml:52).
- **Binds:** `persona-bind` (sets `BEATS_VOICE`, CGP param-surface overrides), `shift-from-bpm`
  (beats→voice prosodic packet on `tokenism.prosodic.bpm.v1`).
- **Suit:** default `dr-bean` (analytical/slow) for governance explanations; `powerpuff-bubbles`
  (coordination) for onboarding — both documented in persona-bind. Slow BPM (60–80, sentence/breath) for
  accessible pacing.
- **Surface:** `voice-console` panel (left).
- **Guardrail:** voice reads tier badges aloud ("this is a *modeled* figure, not adopted") so the honesty
  framing survives the text→speech boundary.

---

## 4. Lane → surface mapping

How each of the four lanes (one system, four angles) appears as a concrete room surface:

| Lane | Tier | Room surface (app · namespace) | Owning agent | Bound skill | Source anchor |
|---|---|---|---|---|---|
| **Capacity** | PROVEN | `mesh-ab` · `capacity` (`/dashboard/fordham/capacity`) | fordham-onboarding (mesh side) | `mesh-egress-ab`, `fleet:enroll` | README:10 (measured 845/683/448 Mbps; honest caveat 305/70 vs 520/101) |
| **Wealth** | MODELED | `coop-ledger` · `wealth` (`/dashboard/fordham/wealth`) | fordham-transaction | `pmoves-chit-sign` + Firefly (`wealth`) | README:12,36 ($35→~$10, ~$25/mo saved = surplus) |
| **Tokenism** | MODELED + FLAGGED | `pilot-dashboard` contribution tile · `fordham` | fordham-transaction | Dirichlet/CHIT attribution (attribution-preview only) | README:12 (12-wk decay; flags: localEconomicActivities inert, Dirichlet not wired to distribution) |
| **Governance** | SCAFFOLDED | `voter-roll` + `ballot-box` · `governance` (both `status: planned`) | fordham-onboarding (roll) / fordham-voice (accessible read-out) | `fleet:enroll`, `pmoves-chit-sign` (`vote.signed.v1` HMAC receipts) | README:14,39 (roll 1 of N; governor plutocratic — DO NOT SHIP as-is) |

**The convergence in the room:** the dollars the capacity tile frees are the dollars the wealth tile books
as surplus; the contribution the tokenism tile attributes is what earns roll standing; the governance
surfaces are how the co-op votes on that surplus — all on **one mesh + one signing key**
(pmoves/docs/pilots/fordham-hill/README.md:39). The room makes that literal: the same
`pmoves-chit-sign` HMAC primitive that receipts a dues trail (wealth) receipts a vote
(`vote.signed.v1`, governance) — no blockchain, no wallets.

---

## 5. Launch-readiness gates (rehearsal → live)

The room ships at stage `rehearsal`. **All of the following must be true (and human-confirmed) before P7
promotes `fordham.room.community` to `live`:**

**Platform gates**
- [ ] **Archon minting live:** `archon:status` green + Supabase connectivity confirmed; all four roster
      agents minted (`archon.mint.confirmed.v1` received for each). Governance-touching mints
      (`fordham-onboarding`, `ballot-box` wiring) require operator sign-off.
- [ ] **Supabase up:** roll + ledger + receipt tables reachable; `voter-roll` notebook writeback resolves
      (data team, agent-teams.yaml:64).
- [ ] **Voice pipeline healthy:** `voice:status` (Flute-Gateway + Ultimate-TTS) green; `persona-bind`
      binds a suit and `shift-from-bpm` publishes to `tokenism.prosodic.bpm.v1` end-to-end.
- [ ] **CF dev-site reachable:** the pilot dashboard (`pilot-dashboard-serve.sh`) serves the four-lane
      overview on the Cloudflare dev-site; tier badges render on every tile.
- [ ] **Manifest validates:** `python pmoves/scripts/validate_room_manifests.py` passes; room registered
      in `pmoves/config/rooms/catalog.json` (pmoves/docs/ROOM_MANIFEST_CONTRACT.md:92).

**Honesty gates (block promotion even if platform is green)**
- [ ] Governance apps (`voter-roll`, `ballot-box`) remain `status: planned` — do **not** flip to `active`
      until: (a) voting basis chosen, (b) roll populated beyond 1 of N (users.yaml:9), (c) legal sign-off
      on E-VOTING validity (§6). The plutocratic on-chain governor (CoopGovernor.sol:72) is **out of scope**
      for any live board election.
- [ ] Every wealth/tokenism figure is tier-badged and keyed to a single **ADOPTED RATE** (§7) — no bare
      dollar figure ships unbadged.
- [ ] No room artifact contains a fraud accusation; investigation attribution points to the human-led lane
      (pmoves/docs/pilots/fordham-hill/README.md:65).

**Live means:** capacity (PROVEN) + wealth/tokenism (MODELED, badged) surfaces are interactive; governance
stays declared-but-inactive until its legal + roster gates clear independently.

---

## 6. Legal-review carryovers (DRAFT — REQUIRES LEGAL REVIEW)

Pulled forward from the pilot README so **nothing binding ships from the room**. Each is a hard gate on the
surface it governs (pmoves/docs/pilots/fordham-hill/README.md:58-69):

- **All dollar/rate claims** (the $35 premium counterfactual, ~$10 due, per-home savings, surplus, every
  Firefly figure) are DRAFT pending legal/accounting review → gates `coop-ledger` + tokenism tile (:60).
- **Bylaws amendment clauses** (Committee on Elders, resident e-voting) require NY cooperative-corporation
  statute review → gates `ballot-box` going `active` (:61).
- **Voting basis & quorum legality** (one-member vs unit vs share; roll-percentage quorum) must be
  counsel-confirmed against the certificate/bylaws/NY law before any binding vote → gates governance
  namespace (:62).
- **E-voting / remote-quorum validity** — whether HMAC-receipted (`vote.signed.v1`) mesh ballots satisfy NY
  cooperative-meeting/notice/quorum requirements → hard gate on `ballot-box` (:63).
- **Board/management transition process** — legal mechanics stay counsel-led; the platform provides
  auditable records only and must not be represented as conferring legal authority (:64).
- **Fraud-investigation boundary** — tooling outputs are transparency/audit artifacts only; no accusations;
  investigation human-led (PMOVES-mike + Missing Link). Enforced on `fordham-creator` + `fordham-voice`
  outputs (:65).
- **Telecom / ISP terms & liability** — pooling/sharing internet via community exit nodes vs residents' ISP
  ToS, and co-op liability for shared-IP egress → gates the capacity onboarding flow (:66).
- **Cooperative entity for the mesh** — program of the housing co-op vs separate entity vs vendor; affects
  who books surplus + dues authority → gates `fordham-transaction` surplus policy (:67).
- **Data / privacy & member records** — roll + ledger hold resident PII; retention/consent/privacy under NY
  obligations → gates `voter-roll` + receipt storage (:68).
- **Securities / token characterization** — confirm Dirichlet-weighted pool / on-chain governor is NOT a
  security before any token concept is member-facing → gates tokenism tile going beyond attribution-preview
  (:69).

---

## 7. Open operator decisions

Only the Committee/board can set these; the room renders placeholders until they land
(pmoves/docs/pilots/fordham-hill/README.md:45-55):

- **ADOPTED RATE** — one monthly member due. Lanes model ~$10; repo product price $5/user; current premium
  $35. Every wealth/tokenism figure re-flows from this one number (:47). Until set, all ledger figures are
  MODELED/illustrative.
- **REAL HOME COUNT** — replace the cohort=50 placeholder with Fordham Hill's actual opt-in unit count; all
  per-community totals are meaningless until set (:48).
- **VOTING BASIS** — one-member-one-vote vs one-unit-one-vote vs shares. Most consequential choice; the
  existing on-chain governor is plutocratic quadratic-stake and **cannot** represent a co-op board election
  as-is (CoopGovernor.sol:72) — basis must be fixed before any voting tool is built (:49).
- **QUORUM DEFINITION** — quorum as a percentage of the eligible roll; current on-chain quorum is a flat
  numeric threshold (CoopGovernor.sol:96) that cannot express "X% of eligible members" (:50).
- **Room-type/owner-mode** (spec-local) — extend schema `room_type` enum to add `community`, or seed the
  manifest as `hybrid`; confirm `owner_mode: shared` for co-op identity (room.manifest.v1.schema.json:45).
- **Secondary (from README §Open):** POPULATE THE ROLL (1 of N today), HOSTING ECONOMICS (who hosts / earns
  dues credit), SURPLUS POLICY (what surplus is for), STARLINK/DEGRADED-LINK PILOT (where pooling wins on
  peak), WIRING WORK (consume localEconomicActivities; wire Dirichlet to distribution — or defer and label
  "attribution-preview only") (:51-55).

---

## 8. Provenance & related

- Contract: `pmoves/docs/ROOM_MANIFEST_CONTRACT.md`
- Schema: `pmoves/contracts/schemas/room/room.manifest.v1.schema.json`
- Seed to mirror: `pmoves/config/rooms/4090-field.room.control.json`
- Registry: `pmoves/config/rooms/catalog.json` (register `fordham.room.community` here)
- Pilot source of truth: `pmoves/docs/pilots/fordham-hill/README.md`
- Roster conventions: `pmoves/configs/agent-teams.yaml`
- Dashboard scripts: `deploy/provision/pilot-dashboard-gen.sh`, `deploy/provision/pilot-dashboard-serve.sh`
- Skills bound: `mesh-egress-ab`, `persona-bind`, `shift-from-bpm`, `pmoves-chit-sign`,
  `pmoves-cipher-memory`, `fleet:enroll`, `archon:mint-agent`

_Next implementation step: author `pmoves/config/rooms/fordham.room.community.json` from this spec, register
it in the catalog, run `validate_room_manifests.py`, then hand the four mint specs to Archon._
