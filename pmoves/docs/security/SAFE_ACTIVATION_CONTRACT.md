# PMOVES Safe-Activation Contract

**Status:** Design / invariant (2026-06-29). **DESIGN ONLY — no runtime change in this doc.**
**Owner lane:** Z890-CLAUDE (data tier + activation) + OPERATOR (capability + custody decisions).
**Related:** [`PORT_BINDING_MODEL.md`](./PORT_BINDING_MODEL.md), [`SECURITY_SINGLE_USER.md`](./SECURITY_SINGLE_USER.md), `.claude/skills/pmoves-mesh-preflight/`, `.claude/skills/pmoves-chit-sign/`, `pmoves/docs/integrations/SUPABASE_ASYMMETRIC_JWT_MIGRATION.md`, `docs/superpowers/specs/2026-06-26-voice-agents-design.md`.

## 0. The invariant (one sentence)

> **PMOVES activates from any node it runs on, routed by that node's user-selected capabilities, funnelling the operator onto the safe path — and the act of opening a surface never exposes a credential-protected service unwittingly. Secure the opening; never expose by accident.**

This is the parent contract. The bind-scope rules in `PORT_BINDING_MODEL.md`, the CHIT unseal paths, and the voice-agent capability modes are all **instances** of it, not separate patterns.

## 1. Why this exists

The mic/CHIT block surfaced the real flaw: prod bring-up was implicitly coupled to **one node (Z890)** and **one capability (a microphone, for voice-activated CHIT unseal)**. A node without a mic could neither unseal the credential nor offer a usable voice experience — activation was neither node-agnostic nor capability-aware. At the same time, the long-standing reason Agent Zero forces id+pass (it binds `0.0.0.0`) and the reason "open-claw" must be gated are the *same* concern from the other direction: **opening a surface must not silently expose it.**

Three needs, one contract:

1. **Node-agnostic activation** — every node is a pore in the lattice; any node can be the launch point.
2. **Capability-routing** — the operator selects the hardware path; PMOVES funnels them to the safe variant for that capability.
3. **Safe-opening guard** — anything reachable must be auth-gated; activation verifies this and refuses/funnels rather than exposing.

## 2. Clause 1 — Node-agnostic activation

**Rule:** Activation must not assume a specific node. The launch node may lack the data tier, a GPU, a mic, or a speaker; the contract defines how each gap is filled (peer handoff over the mesh, or a local fallback path), never by silently failing or silently exposing.

**Today:** bring-up is implicitly Z890-centric (the data tier is configured there). The mic block proved activation is not yet node-agnostic.

**Target:** each node declares what it *is* and what it *has*; activation resolves missing pieces explicitly:
- missing data tier → consume a peer's over the mesh, or stand up locally;
- missing unseal capability → use a fallback unseal path (Clause 2) or receive the unsealed credential from a capable peer **over the sanctioned funnel only** (Clause 3 still applies to the receiving node).

## 3. Clause 2 — Capability-routing

**Rule:** The operator selects the hardware path; PMOVES funnels to the safe variant for that capability. No capability is the *sole* path to activation.

A node declares a **capability set** (illustrative, extend as needed):

| Capability | Present → path | Absent → fallback |
|---|---|---|
| **microphone** | voice-activated CHIT unseal; voice-in for agents | typed-passphrase / key-file unseal; **text-in** for agents |
| **speaker / cast (Nest)** | TTS-out, voice responses | text-out only |
| **GPU** | local embeddings (Hi-RAG), local RVC/voice synth | remote/peer inference, or degraded mode |
| **mesh membership** | clone ON (consent/provenance-gated), peer credential funnel | demos/examples only (public posture) |

**Instances of this clause already in flight:**
- **CHIT unseal** must offer **voice OR typed OR key-file** (the mic block's fix). Design lives in the CHIT unseal follow-up; this contract is its parent.
- **No-mic user mode**: text-in → **Nest TTS-out**. Z890 (no mic, has Nest speakers) is the canonical testbed — *to be added* to the voice-agents design spec §1a as an accessibility requirement (owned by the voice lane; this is a forward reference until that section lands).

**Funnel-to-safe, not fail-to-open:** if the selected capability would require exposing a protected surface (Clause 3) and the safe variant is unavailable, activation **refuses and explains**, it does not silently widen a bind.

## 3a. Clause 2b — Identity & blast-radius (auth tiers)

Identity is a Clause-2 capability with its own safe-variant routing. PMOVES uses a
**three-tier** auth model — easy to enter, gated in reach:

| Tier | Mechanism | Scope |
|---|---|---|
| **Identity (front door)** | Google OAuth — one friendly sign-in | Establishes *who*. Cheap to enter; user attribution and the online boundary key off it. |
| **CHIT (local master key)** | CHIT present on a node auto-unlocks/bypasses **local** surfaces (the same auto-unlock as damage-control Known Roads) | Establishes *how far, locally*. CHIT-on-node is sufficient for local unlock. |
| **Online gate (blast radius)** | A separate, stricter gate on egress / cross-node / public surfaces | Establishes *how far, outward*. Identity ≠ blanket access; crossing the online boundary is independently gated. |

**Principle: easy auth ≠ wide auth.** Google gets the operator *in* cheaply; CHIT decides
what that unlocks *locally*; the online boundary is a third, independent gate. Local
master-key unlock is safe precisely *because* the online gate is separate — "master key
for local, but gated before online."

**"Choose where to apply"** = the operator selects *which* surfaces the identity unlocks;
auth-scope is itself capability-routing (Clause 2). The bring-up updater gate (showtime
`/updater/gate`) and the Hermes OpenShell egress policy are both instances:
CHIT-unlock + a Google session admit the action *locally*, while blast-radius scoping
bounds what it may *reach*.

## 4. Clause 3 — Safe-opening guard

**Rule:** Any service bound to a **reachable** interface (`0.0.0.0`, LAN, or mesh) **MUST** be auth-gated. Activation verifies *bind-scope vs auth-presence* and refuses/funnels when a reachable bind lacks a credential gate. Exposure is opt-in and reviewed, never the accidental default.

**"Reachable" has two altitudes.** Per Clause 2b, the same surface sits behind different gates depending on *how far* it reaches: **LAN/mesh** reach is gated by CHIT local-unlock (the local master key), while **online/public/egress** reach is the strictest, *independent* gate (the blast-radius tier of Clause 2b). A surface that is safe on the mesh is **not** automatically safe online — clearing the local gate never implies clearing the online one. Evaluating auth-presence *per altitude* (distinguishing mesh-reach from online-reach) is the **v2 target**. The **v1 implementation** (#1904 `safe_opening_audit.py`) covers the **single-altitude subset**: any non-loopback bind is treated as reachable and must be gated — the conservative floor of this clause (mesh-reachable ⊆ reachable), so the tool never *under*-gates relative to the contract.

This **extends** `PORT_BINDING_MODEL.md`, which already governs *bind scope* (the four-tier model, the `*_BIND` override pattern, `make -C pmoves port-audit`). The contract adds the **bind→auth coupling** that the binding model does not yet assert:

| `PORT_BINDING_MODEL.md` governs | This contract adds |
|---|---|
| *Where* a service binds (loopback / mesh / reviewed override) | *Whether* a reachable bind is auth-gated — and **refuses activation if not** |
| `make port-audit` checks bind defaults vs policy | a **safe-opening preflight** checks reachable-surface → auth-present |
| "don't replay 0.0.0.0 diffs" review rule | "reachable without auth = blocked, funnel the operator" runtime rule |

**Canonical examples (the operator's own framing):**
- **Agent Zero** requires id+pass *because* it binds `0.0.0.0`. The auth is not incidental — it is what makes the open bind safe.
- **open-claw** is the same: opening a claw must carry its gate.
- The point is **not to let the operator open up unwittingly** — the system secures the opening on their behalf.

**Never-widen-without-review surfaces** (from `PORT_BINDING_MODEL.md` §"Never Widen Without Separate Review") — Supabase DB/Auth/REST, Kong Admin, Qdrant/Meili/Neo4j/ClickHouse, MinIO — remain hard-gated regardless of capability selection.

## 5. How the three clauses compose

```
operator triggers activation on node N
  │
  ├─ Clause 1: what does N have? (data tier / GPU / mic / speaker / mesh)
  │     └─ resolve gaps: local fallback OR sanctioned peer handoff
  │
  ├─ Clause 2: operator selects capability path
  │     └─ funnel to the SAFE variant (voice|typed|key-file; voice|text; …)
  │
  └─ Clause 3: for every surface about to open
        └─ reachable bind? → MUST be auth-gated
             ├─ gated      → open
             └─ not gated  → REFUSE + explain (funnel, never silent-expose)
```

The mic/CHIT decision is one walk through this flow: a no-mic node (Clause 1 gap) selects the typed/key-file unseal path (Clause 2 fallback), and whichever path unseals, the credential is never re-exposed on a reachable bind (Clause 3).

## 6. What this contract anchors (downstream work)

1. **Safe-opening preflight** — extend `pmoves-mesh-preflight` (or a sibling skill) from a *health* check into a *bind-scope vs auth-presence* check. Pairs with the damage-control topology-leakage guard (that guards committed docs; this guards runtime activation) and with `make port-audit` (that checks bind policy; this checks the auth coupling).
2. **Capability-router** — node capability declaration + operator selection + safe-variant resolution.
3. **CHIT multi-path unseal** — voice OR typed OR key-file (Clause 2 instance #1). Its own design doc.
4. **No-mic user mode** — text-in → Nest TTS-out (Clause 2 instance #2). Voice-agents spec §1a accessibility requirement.

## 7. Verification (deploy-gated)

Cannot be fully validated without the running stack. Per clause:
- **Clause 1:** activation succeeds from a non-Z890 node (or explicitly funnels to a peer).
- **Clause 2:** each capability fallback reaches a working safe variant (no dead ends).
- **Clause 3:** the safe-opening preflight flags any reachable bind lacking auth, and `make -C pmoves port-audit` stays green.

## 8. Open operator decisions

1. **Peer credential funnel:** is exporting an *unsealed* CHIT credential from a capable node (e.g. the mic-equipped 5090) to a peer (Z890) over the secrets-funnel a **sanctioned** Clause-1 path, or is unseal **local-only** (forcing the stack to run on the capable node)? This gates the 5090 handoff.
2. **CHIT unseal reconsideration:** confirm voice as *one* factor among {voice, typed, key-file}, and which is the default per node class.
3. **Capability declaration source:** where a node's capability set is declared (env file, `pmoves/config/rooms/*`, or runtime probe).
