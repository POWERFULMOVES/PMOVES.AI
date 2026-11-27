# PMOVES NATS Accounts + Leaf Topology — v0 Design Spec

**Date:** 2026-08-07  **Author:** z890-claude (KEYSTONE, infra)  **Status:** design — operator review
**Lane:** NATS fork completion (`PMOVES-nats-server` + `pmoves-nats-mcp`) grounded in official NATS refs.

**Goal:** Give PMOVES a real NATS multi-tenancy + leaf-node trust model — trust-zone accounts,
nsc/JWT credentials, a hub leafnode listener that edge/cloud nodes actually attach to — and
complete the two NATS forks so they are real integrations (config + packaging), not shims.

**Architecture:** Stock `nats-server` (upstream-clean fork) configured with four trust-zone
accounts (SYS/CORE/EDGE/CLOUD) via a memory resolver of nsc-minted account JWTs. Hub exposes a
`7422` leafnode listener; edge/cloud nodes attach as account-scoped leaves. CHIT signing rides
inside messages as an orthogonal, reinforcing trust layer. The MCP bridge becomes a CHIT-aware
signed publisher bound to CORE.

**Tech stack:** `nats-server` 2.11.x (stock), `nsc` (JWT operator/account/user), memory resolver,
Python MCP (`pmoves-nats-mcp`), CHIT signing tooling (existing), CHIT vault + secrets-funnel.

## Global Constraints

- **Server stays upstream-clean** — no Go patches to `PMOVES-nats-server` in v0. Value lives in
  config + packaging. Broker-level CHIT enforcement is explicitly out of scope (see §11).
- **No plaintext credentials** anywhere — replaces b850's `nats:pmoves`. All creds are nsc-minted
  `.creds`, held in the **CHIT vault**, materialized via secrets-funnel. Never hand-edit `env.shared`.
- **Committed artifacts use hostnames/placeholders, never literal IPs** (refer to nodes by Tailscale hostname).
- **Compose/Dockerfile/config edits are Known-Road domains** — operator-authorized.
- Reconcile against prior operator decisions in `#1901` (JWT key custody + voice RBAC) — do not contradict.
- 100% stock NATS features only (accounts, leafnodes, memory resolver, JWT) — verified against official docs (§ References).

---

## 1. Current state (measured 2026-08-07)

- `pmoves-nats-1` = `nats:2.11.8-alpine`, launched via **flags** (`--user/--pass`, `--http_port 8222`) —
  **no accounts, one flat global namespace.**
- Client `4222` published cross-node; monitoring `8222`→`9223` bound loopback but **not credential-guarded**.
- Leaf `.conf` files exist (`elder-melchor-leaf.conf`, `configs/nats-leaf-z890.conf`, `nats/config/external.conf`)
  but the server is **not** launched with them, and **no leafnode listener** exists.
- **Bug:** b850's `elder-melchor-leaf.conf` remote points at `${TS_Z890}:4222` (client port) with plaintext
  `nats:pmoves`. Per NATS docs a leaf attaches to the hub's **7422** leafnode port. It has never been a real leaf.
- `PMOVES-nats-server` = clean fork of `nats-io/nats-server`, tracking upstream, **zero PMOVES commits**.
- `pmoves-nats-mcp` = tracked (7 files), env `NATS_URL=nats://nats:pmoves@…:4222`, tools `nats_publish` /
  `nats_subscribe`. **No Dockerfile/compose/examples** — shim-shaped.

## 2. Account topology (trust zones)

| Account | Holds | Users (initial) |
|---|---|---|
| **SYS** | NATS system account: `$SYS.*` events, monitoring. Guards `8222` (fixes the unguarded gap). | `sys` (ops) |
| **CORE** | All hub services on z890 — agents, geometry/chit, media, tokenism, mesh, archon, evo, a2ui. Shared account: they already share a flat namespace and mutually trust; keeps cross-lane subjects friction-free. | `core-service` (per-service split deferred) |
| **EDGE** | Jetson/edge leaves. Sees only what CORE exports. | `edge-nano-1` (+ `edge-*` per leaf) |
| **CLOUD** | Hostinger VPS/KVM leaves (egress/exit-node lane). Separate trust zone from EDGE. | `cloud-kvm-*` per leaf |

Rationale: NATS "one account per application, don't over-fragment." Four zones give isolation at the
network trust boundary without walling the mutually-trusting hub services off from each other.

## 3. Auth — nsc hierarchy + memory resolver

nsc mints one **Operator** (`PMOVES`) → four **Accounts** (SYS/CORE/EDGE/CLOUD) → **Users** (`.creds` JWTs).

Hub config (rendered from env like the kong pattern):
```
resolver: MEMORY
resolver_preload: {
  <SYS_ACCOUNT_PUBKEY>:   <sys account JWT>
  <CORE_ACCOUNT_PUBKEY>:  <core account JWT>
  <EDGE_ACCOUNT_PUBKEY>:  <edge account JWT>
  <CLOUD_ACCOUNT_PUBKEY>: <cloud account JWT>
}
system_account: <SYS_ACCOUNT_PUBKEY>
```
Memory resolver is the doc-recommended choice for "a small number of accounts that don't change
very often" — exactly our four fixed zones. User creds are still nsc-rotatable; only the four
account JWTs are preloaded (edit + reload to change an account, which is rare).

**Custody (aligned to `#1901` precedent):** the operator holds key-custody decisions. `#1901`
(Supabase asymmetric JWT) set the fleet precedent — **file-mounted Docker secret for initial
rollout (the `_FILE` convention used across `pmoves/services/**`), CHIT-managed custody as a
follow-up.** This spec follows that: v0 mounts the nsc operator seed (`PMOVES.nk`) + account/user
`.creds` as **file-mounted Docker secrets**; **CHIT-vault-managed custody is the documented
follow-up**, not v0. The `resolver_preload` account JWTs (public, non-secret) render into the
`.conf` via secrets-funnel. Final custody choice remains the operator's per `#1901` §7.

## 4. Leaf binding + the 7422 fix

Hub adds:
```
leafnodes {
  listen: 0.0.0.0:7422
}
```
and **publishes 7422** cross-node (currently only 4222/8222 are exposed).

Each leaf's remote (fix `4222`→`7422`, plaintext→creds):
```
leafnodes {
  remotes: [
    {
      urls: [ "nats://<Z890_TS_HOST>:7422" ]
      credentials: "/etc/nats/creds/edge-nano-1.creds"
      # account binding is carried by the creds' user→account JWT
    }
  ]
}
```
> **Open detail to confirm at implementation:** the exact field for pinning a leaf-side local account
> to the remote (`account:` on the remote vs. implied by creds). The nats.docs leaf-JWT page 404'd at
> design time; confirm against `nsc` docs / the security deep-dive before writing the leaf conf.

## 5. Export/import matrix (the isolation payoff)

CORE exports a **curated** set; EDGE/CLOUD export their announcements back. Everything else in CORE
(chit trails, `tokenism.attribution.*`, `archon.mint.*`) stays hub-private by construction.

| Flow | Subjects | Type |
|---|---|---|
| CORE → EDGE | `image.gen.request.v1` (jobs to jetsons); prosodic **control** (voice-suit param surface) | stream |
| EDGE → CORE | `mesh.gpu.status.v1`, `voice.stt.edge.v1`, `image.prompt.expanded.v1`, `image.analysis.v1`, `mesh.combiner.heartbeat.v1`, **`tokenism.prosodic.bpm.v1`** (signed CGP), `chit.cgp.v1` | stream |
| CORE ↔ CLOUD | `mesh.*` + egress/exit-node subjects only | stream |
| CORE → EDGE (reserved, not wired v0) | `evoswarm.training.genome.v1` (genome to evaluate) | stream |
| EDGE → CORE (reserved, not wired v0) | `evoswarm.training.fitness.v1` (result) | stream |
| Agent inbox (OPEN, §5a) | `mesh.inbox.agent.<agent_id>.v1`, `mesh.inbox.room.<room_id>.v1` | stream `AGENT_INBOX` |

### 5a. Agent inbox — which account holds it (OPEN decision, added 2026-11-27)

**Subjects.** One inbox per agent, `mesh.inbox.agent.<agent_id>.v1`, and one fan-out subject per room,
`mesh.inbox.room.<room_id>.v1`, on a single stream `AGENT_INBOX` over `mesh.inbox.>`
(`pmoves/docs/architecture/AGENT_INBOX_ROAD_DESIGN_2026-11-21.md:47-48`, `:56`, on branch
`feat/agent-inbox-road` @ `72f518d32`, not on main; cited below as "design"). `<agent_id>` is the
signing-card `agent_id` (design `:23`). Neither subject is in `.claude/context/nats-subjects.md` on main
or on that branch yet (grep, 2026-11-27).

**Why it needs this spec.** The hub today is one `$G` account plus `$SYS` (design `:32-33`). In one
account any connection may subscribe `>`, so a subject name gives no confidentiality (design `:38-41`).
The tap is one unset variable away: `nats-echo` defaults to `>` (`pmoves/services/nats-echo/nats_echo.py:38`).
The shipped stanzas override it to `research.deepresearch.{request,result}.v1`
(`pmoves/docker-compose.yml:4942`, `:4971`), so the code default is the hazard; whether a running
instance uses it was not measured. Until §5a is decided and cut over, inbox bodies carry no secrets.
Whichever option wins, the CORE ↔ CLOUD row above must stay `mesh.*` (one token) and never become
`mesh.>`, or a CORE-held inbox would cross to CLOUD.

**Option (a): stay in CORE, with per-agent users.** One nsc user per agent, minted into CORE:
- publish: `mesh.inbox.agent.*.v1`, `mesh.inbox.room.*.v1`
- subscribe: `mesh.inbox.agent.<own-id>.v1` plus the rooms it belongs to, nothing else (`>` denied)

This reverses the §11 deferral of "fine-grained intra-CORE permissions", for agent identities only.
Cost: subject permissions do not guard the stream. A durable pull consumer reads through
`$JS.API.CONSUMER.MSG.NEXT.AGENT_INBOX.<durable>`, and `$JS.API.STREAM.MSG.GET.AGENT_INBOX` returns any
stored message. So each user also needs `$JS.API` rights narrowed to its own durable, with stream-level
GET excluded. That is reasoned from upstream permission semantics and is not measured here.

**Option (b): a dedicated AGENTS account.** `AGENT_INBOX` lives in an AGENTS account. CORE sees only
what AGENTS exports (for example a review-request seam), and AGENTS imports the CORE subjects agents need.
JetStream is per-account: a CORE client reaches AGENTS JetStream only through an import with an altered
API prefix, which is stripped back to `$JS.API` at the boundary (upstream ADR-19,
`POWERFULMOVES/Pmoves-nats-architecture-and-design` `adr/ADR-19.md:14`, `:24-25`, `:32`). Cost: a fifth
account breaks the "four fixed zones" rationale of §3 (`:72-74`), adds a fifth `resolver_preload` entry to
`pmoves/config/nats/pmoves-nats.conf:51-56`, and needs an nsc mint after Phase 1. Agents inside AGENTS
still share one account, so per-agent privacy still needs option (a)'s user permissions inside it.

**Proposed lab proof (NOT run).** Repeat the 2026-08-15 throwaway-container method
(`pmoves/docs/operations/NATS_LEAF_TOPOLOGY_ROLLOUT_RUNBOOK.md:83-86`; production `pmoves-nats-1` untouched):
1. Mint a **throwaway** nsc operator in a scratch store, not the z890 vault (runbook `:41`).
2. Render `pmoves/config/nats/pmoves-nats.conf` from it, keeping `operator:` (`:45`; required, runbook `:100`).
3. Mint user `inbox-a` with subscribe allow `mesh.inbox.agent.a.v1` only, and user `inbox-b` unrestricted.
4. `inbox-a` subscribing `>` and `mesh.inbox.agent.b.v1` must each get `Permissions Violation`.
5. Positive control: `inbox-b` publishes to `mesh.inbox.agent.a.v1` and `inbox-a` receives it (count 1).
6. Measure whether an explicit deny `>` beside the allow list also blocks the allowed subject; pick the form from that.
7. For (a), repeat steps 4-5 through an `AGENT_INBOX` pull consumer, which exercises the `$JS.API` scoping.

**Cutover stays with the operator.** Either option takes effect only when the hub leaves `$G` (runbook
Phase 2). Phase 2 and Phase 3 land in the same window (runbook `:31`, `:52-54`), through the Known-Road
compose road the operator authorizes (runbook `:31-32`, `:68-69`).

**Signing is orthogonal (§6).** CHIT covers the payload: `sign_cgp(kid=actor)` and `verify_cgp_detailed`
(`pmoves/tools/chit_security.py:323`, `:347`; design `:76-77`). Accounts cover who may read it. An HMAC
under the deployment-wide key is attribution, not authentication (design `:22`), and it does not make a
body private.

## 6. CHIT / GEOMETRY BUS / EVO SWARM / prosodic integration

**Two orthogonal, reinforcing trust layers:**
- **NATS accounts = transport trust** — who may pub/sub which subjects across a boundary.
- **CHIT signing = payload provenance** — the CGP packet is signed (`chit.signed.v1`, `chit.cgp.v1`);
  the signature rides inside the message regardless of account.

A message from a leaf is trusted only if it clears **both** gates: the account let the bytes cross,
and the CHIT signature proves origin.

- **All GEOMETRY BUS / CHIT services are CORE** (Tokenism `:8103`, Hi-RAG, Consciousness `:8106`,
  Evo `:8113`, A2UI NATS Bridge `:9224`). `geometry.*`, `chit.*`, `tokenism.*`, `a2ui.*`, `evoswarm.*`
  flow freely intra-CORE; invisible to leaves unless exported (§5).
- **Prosodic bpm is the CORE↔EDGE seam.** A jetson "prosodic ear" emitting `tokenism.prosodic.bpm.v1`
  needs **both** an EDGE export right **and** a CHIT signing key — two-layer gate on the one subject
  that must cross. CORE returns prosodic *control* so edge agents are "tuned like a tuning fork."
- **EVO SWARM stays CORE for v0** (evo-controller models grounded ∪ synthetic on the hub) with a
  reserved edge seam (§5) for future distributed fitness evaluation — defined, not walled off.
- **Convergence:** `tokenism.credential.rotated.v1` already exists. The nsc creds lifecycle emits a
  **CHIT-signed, tokenism-attributed** rotation event; A2UI renders the live trust topology
  (`a2ui.trail.v1`). The accounts model *feeds* the geometry bus.

## 7. The two forks — real-integration treatment

### 7a. `PMOVES-nats-server` (register as submodule)
Stock binary, **no Go patches**. Carries the PMOVES config + packaging:
- `conf/pmoves-nats.conf` — accounts (memory resolver), `system_account`, `leafnodes{listen:7422}`,
  monitoring behind SYS, rendered from env.
- `Dockerfile` (thin: stock `nats-server` + baked conf + entrypoint that templates the resolver_preload).
- compose stanza (replaces the flag-launched `nats` service) + `examples/` (a working leaf-attach demo).
- Tracks upstream for CVE currency via the existing fork-sync discipline.

### 7b. `pmoves-nats-mcp` (complete + enhance)
1. **CORE `.creds` auth** — replace `NATS_URL=nats://nats:pmoves@…` with a CORE user `.creds` file
   (env `NATS_CREDS` path); connect on the client port with the CORE account.
2. **CHIT-signed publish** — `nats_publish(subject, payload, sign?)`: when the subject is CHIT-aware
   (`chit.*`, `tokenism.prosodic.*`, `geometry.*`, or `sign:true`), sign the CGP via the existing CHIT
   signing tooling before publishing; otherwise raw publish (back-compat). Makes the MCP a first-class
   two-layer-trust citizen.
3. **Packaging** — `Dockerfile`, compose service (CORE-bound), `examples/` (signed + raw publish, subscribe).

## 8. Secrets & rendering

- nsc keyring: operator seed + account/user seeds as **file-mounted Docker secrets** for v0 (per
  `#1901` precedent); CHIT-vault-managed custody (`%APPDATA%/pmoves/chit` lane) is the follow-up.
- `.creds` files materialized to `/etc/nats/creds/` per node (file-mounted secret) — never committed, never in `ps`.
- Account JWTs (public) render into the hub `.conf` `resolver_preload` at funnel time.
- Add the new secret ids to `secrets_manifest.yaml` (example → manifest → funnel), never `env.shared` by hand.

## 9. Rollout (greenfield, phased — each independently testable)

1. **Mint** — nsc operator + 4 accounts + initial users; stash seeds in CHIT vault; add manifest entries.
2. **Hub** — deploy `PMOVES-nats-server` with accounts + `leafnodes{listen:7422}` + SYS; publish 7422.
   Verify SYS-guarded monitoring, CORE clients connect with `.creds`.
3. **Migrate CORE** — switch hub services' `NATS_URL`→CORE `.creds`; verify the flat-namespace traffic
   is unchanged intra-CORE.
4. **EDGE** — attach nano-1 as an EDGE leaf at 7422; wire §5 exports/imports; prove isolation.
5. **CLOUD** — attach a KVM as a CLOUD leaf; egress subjects only.
6. **MCP** — cut `pmoves-nats-mcp` to CORE `.creds`; land the CHIT-signed publish path.

## 10. Acceptance tests (proves the model holds)

- **Leaf handshake:** nano-1 leaf attaches at `7422` (hub `varz`/`leafz` shows the leaf); `4222`-target refused.
- **Isolation (the point):** an EDGE user subscribing a CORE-private subject (`tokenism.attribution.recorded.v1`)
  is **denied**; publishing outside its export set is denied.
- **Export round-trip:** jetson publishes `mesh.gpu.status.v1` → observed on CORE; CORE publishes
  `image.gen.request.v1` → observed on EDGE.
- **Two-layer trust:** an EDGE `tokenism.prosodic.bpm.v1` with a valid CHIT signature is accepted+trusted;
  an unsigned one crosses transport but fails CHIT verification at the consumer.
- **MCP signed publish:** `nats_publish("tokenism.prosodic.bpm.v1", …, sign=true)` yields a CHIT-verifiable CGP.
- **Monitoring guard:** `8222`/`9223` requires SYS creds.
- **Rotation:** rotate a user cred via nsc without dropping CORE traffic; emits `tokenism.credential.rotated.v1`.

## 11. Out of scope (v0)

- **Broker-level CHIT enforcement** (Go patches rejecting unsigned publishes at the server) — deliberate
  future decision; commits us to maintaining patches against a fast upstream.
- NATS-based (full) resolver / `nsc push` dynamic distribution — memory resolver suffices for 4 static accounts.
- Per-service CORE sub-accounts / fine-grained intra-CORE permissions.
- TLS on the leaf link (add after the account model lands; Tailscale already encrypts the transport).
- Wiring the EVO edge-fitness seam (reserved in §5, not built).

## References (verified 2026-08-07)
- NATS accounts (multi-tenancy, export/import): `nats.docs .../securing_nats/accounts`
- NATS leafnodes (7422, remotes, credentials): `docs.nats.io/.../configuration/leafnodes`
- NATS JWT resolvers (memory vs full): `nats.docs .../securing_nats/jwt/resolver`
- `nats-io/nsc`, `nats-io/nats-architecture-and-design` (operator/account/user + accounts topology)
- Local: `.claude/context/geometry-nats-subjects.md`, `.claude/context/nats-subjects.md`, `#1901` decisions
- Sibling: `pmoves/docs/handoffs/jetson-combiner-archon-assignment-2026-08-07.md` (§C1 leafnode), `JUICEFS_MEDIA_MINIO_REFORMAT_RUNBOOK.md`
