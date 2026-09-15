# CHIT-FORKS — provenance for PMOVES-forked artifacts

> **Status:** PROPOSAL. This document declares CHIT provenance for the
> artifacts in this repo that come from upstream forks, where the
> upstream authors are out of PMOVES's direct sign-off loop.
>
> **Operator anchor (paraphrased):** "the schema constraints in cipher
> are not arbitrary, they're upstream byterover-cli defaults baked into
> the fork at fork-time — and that's the flat-hierarchy failure mode the
> identity proposal is trying to fix." See
> [`pmoves/docs/AGENTS/AGENT_IDENTITY_PROPOSAL_2026-09-04.md`](../docs/AGENTS/AGENT_IDENTITY_PROPOSAL_2026-09-04.md)
> §1 and
> [`pmoves/docs/AGENTS/AGENT_IDENTITY_MULTISIG_SEED.md`](../docs/AGENTS/AGENT_IDENTITY_MULTISIG_SEED.md)
> for the upstream doctrine this proposal extends.
>
> **Lane:** `docs/chit-forks-declares-provenance-for-pmoves-forked-artifacts`
> (operator claim, 2026-09-15). PR is docs-only; no schema, secret,
> or compose changes. Operator review only.

---

## 1. The gap this document closes

Every artifact in PMOVES that came from an upstream fork carries
constants, schemas, or conventions that **PMOVES did not author**.
When those constants matter — a cap, a default, a behavior — the
PMOVES side has no signing card on them. The artifact drifts with
upstream; PMOVES notices only when something breaks.

**Concrete examples observed 2026-09-14:**

| Artifact | Constant | Source | PMOVES signing card |
|----------|----------|--------|----------------------|
| Cipher memory schema (`Pmoves-cipher/src/agent/infra/memory/memory-manager.ts:21-23`) | `MAX_CONTENT_LENGTH = 10_000`, `MAX_TAG_LENGTH = 50`, `MAX_TAGS = 10` | upstream `byterover-cli` (campfirein) | **none** |
| Cipher auth (`Pmoves-cipher/src/pmoves/auth.ts`) | Bearer header on every route except `/health` | PMOVES shim | `5090-claude` (this session's reconcile) |
| Cipher A2A agent card (`Pmoves-cipher/src/pmoves/a2a.ts`) | capabilities, endpoints, protocols | PMOVES shim | `5090-claude` |
| Flute-Gateway auth (`pmoves/services/flute-gateway/main.py:218`) | `X-API-Key` header only; fails open when `FLUTE_API_KEY` unset | PMOVES | `5090-claude` (per `pmoves/docs/TAC/TAC_FLUTE.md`) |
| Agent Zero inner-runtime fork (PMOVES-Agent-Zero) | Hardened overlay + bound-isHttp patch | PMOVES fork | `5090-claude` per release |
| Pipecat fork (PMOVES-Pipecat) | PMOVES.AI integration patterns | PMOVES fork | pending |
| Crush fork (PMOVES-crush) | CHIT-aware boot + GLM windows | PMOVES fork | pending |
| Notebook-mcp fork | `Pmoves-cipher`-style additive shim | PMOVES | `5090-claude` |

This table is the **declared surface** for the flat-hierarchy problem.
A constant with a card has an author and a verification surface; a
constant without a card is downstream's responsibility until it breaks.

## 2. What a CHIT-FORK declaration is

A CHIT-FORK declaration is a small, append-only record that asserts:

1. **Artifact identity.** What is the artifact (path, version, fork commit).
2. **Upstream source.** Where it came from, pinned to a specific commit.
3. **PMOVES overlay.** What PMOVES added on top — additive or override.
4. **Signing card claim.** Which PMOVES agent owns the *PMOVES overlay*
   (the upstream side is byterover-cli / openclaw / etc., out of our
   sign-off loop; we sign only for what we wrote or reviewed).
5. **Override surface.** If a PMOVES constant overrides an upstream
   constant, point at the local file. The override is what
   PMOVES's signing card owns.

The declaration is **append-only**: every fork point is a record.
There is no deletion — only supersede (new commit + supersede link).
This mirrors the `pmoves/config/agent_signatures.yaml` schema (1.1.0)
which already treats `alters` as first-class.

## 3. The record for Cipher (worked example)

The reconcile this session did on cipher (PR not opened yet — see
§6 follow-ups) is the seed record.

```yaml
artifact:
  path: Pmoves-cipher/
  pmoves_fork_commit: <filled when PR opens>
  upstream:
    repo: POWERFULMOVES/byterover-cli  (formerly `campfirein/byterover-cli`)
    pinned_commit: <filled when PR opens — currently `campfirein/byterover-cli` HEAD on the PMOVES fork's tracking branch>
    role: upstream
  pmoves_overlay:
    path: Pmoves-cipher/src/pmoves/
    files: 9 (rest-server.ts, auth.ts, health.ts, memory-routes.ts,
            mcp-sse.ts, a2a.ts, embedding.ts, nats-emitter.ts,
            README.md)
    role: additive shim, REST + MCP-over-SSE + A2A discovery surface
  overrides:
    - file: Pmoves-cipher/src/pmoves/auth.ts
      subject: "Bearer header on every route except /health"
      upstream_default: "no public paths"
      pmoves_choice: "Bearer required everywhere; /health is dev-skip
                       only when CIPHER_API_TOKEN unset"
      signing_card: 5090-claude
      verified_live: "POST /api/memory with X-API-Key -> 401; same with
                       Authorization: Bearer <correct> + body {} -> 400
                       (body schema validates before auth; 400 = auth
                       passed). Live 2026-09-14."
    - file: Pmoves-cipher/src/agent/infra/memory/memory-manager.ts:21-23
      subject: "MAX_CONTENT_LENGTH, MAX_TAG_LENGTH, MAX_TAGS"
      upstream_default: "10000 / 50 / 10"
      pmoves_choice: "no override — accept upstream values"
      signing_card: none
      note: |
        The PMOVES side has NO signing card on these constants; they
        come from upstream byterover-cli. Raising them requires a
        byterover upstream bump, NOT a PMOVES-only patch. The
        effective PMOVES user-tag cap is 9, not 10, because the shim
        (memory-routes.ts:24) prepends the category string to the
        user-supplied tags. The Zod error message is misleading — it
        reports the schema's own max(10), not the combined count.
  signing_card: 5090-claude (this lane)
  superseded_by: null
  operator_review: pending
```

A record of this shape is the **CHIT answer to a flat-hierarchy constant**.
It does not change the constant; it declares whose it is and how to
change it.

## 4. The flat-hierarchy failure mode (named precisely)

The Three-Body problem from
[`pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md`](../docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md):
without stabilization, one body gets ejected. In PMOVES terms:

- **Human body** = operator (you). Authorizes intent and the merge wave.
- **AI body** = PMOVES Claude instances. Authorize what they wrote.
- **System body** = the artifact (cipher, agent-zero, pipecat, …).
  Carries the constant the others interact with.

A constant with no signing card has **only one body** (the System).
The other two never authorized it; the artifact is a self-authorized
black hole. PR #2950's rooms-bug is a recent example: a doc table set
the canonical state, but the doc had no signing card, so the table
drifted. CHIT's answer — make every artifact declare its author at
write-time with a key the author can't later disavow — applies to
constants too.

A CHIT-FORK declaration is **the artifact author signing card for
upstream-forked constants**. It does not change the upstream; it
records the PMOVES side.

## 5. Operator follow-up

- This PR is docs-only. The first record (§3) is the cipher fork.
- Future CHIT-FORK records land as their respective forks are
  re-baselined or as their constants become operationally relevant.
- Each record is **reviewed by the lane owner**, signed by their
  signing card, and stored in cipher under category `architecture`.
- The records are **append-only**; they supersede, not delete.

## 6. Open follow-ups from this lane

1. **PR to land this document + the cipher record** — once the
   cipher fork's `pmoves_fork_commit` is known (operator-side:
   `git -C Pmoves-cipher log -1 --format=%H`), this PR becomes
   mergeable.
2. **PMOVES-Pipecat record** — Pipecat fork has the recent
   integration patterns commit (`a74aa0cc9`); a record for that
   fork is the natural next.
3. **PMOVES-Crush record** — operator deferred the Crush rebase;
   when it lands, the record follows.
4. **PMOVES-Agent-Zero record** — the inner-runtime fork already
   ships the hardened overlay; the record is overdue.
5. **CHIT audit of fork_registry.json** — the wave-3 ratchet caught
   4 undeclared PMOVES submodules (Composio/Activepieces/N8N). The
   ratchet is right: undeclared forks are exactly the artifacts
   with no signing card. Land those fork-registry entries first;
   they pair with this document.

---

## Cross-references

- `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md` — the root: why a
  constant with no card is the three-body ejection in slow motion.
- `pmoves/docs/AGENTS/AGENT_IDENTITY_PROPOSAL_2026-09-04.md` §1 —
  the operator's exact words, and the four sites that already carry
  the doctrine (`identity_lineage.py` is the most developed).
- `pmoves/docs/AGENTS/AGENT_IDENTITY_MULTISIG_SEED.md` — Part 2:
  multi-sig on work; PMOVES agents sign for what they reviewed.
- `pmoves/docs/AGENTS/AGNOTE4482.md` §Village Rule — no agent
  operates alone; three-body quorum shape (delivery, control, memory).
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` — collision-safe
  traversal (one branch one owner, JOHNNY BLAZE three-way fallback).
- `pmoves/config/agent_signatures.yaml` (schema 1.1.0) — `alters`
  are first-class; the precedent this doc plugs into.
- `pmoves/docs/rooms/ROOM_MANIFEST_CONTRACT.md` — the rooms lane
  CHIT answer; PR #2950's rooms-bug is the example this doc mirrors.
- `pmoves/PMOVES-cipher/PMOVES.AI_INTEGRATION.md` — the canonical
  PMOVES-side surface description for cipher; the §3 record above
  is the CHIT side of the same surface.
- `pmoves/docs/integrations/INTEGRATIONS.md` — Flute-Gateway auth
  is documented there; the Flute CHIT-FORK record (future) lives
  alongside.

---

**Lane:** docs/chit-forks-declares-provenance-for-pmoves-forked-artifacts
**Filed:** 2026-09-15 by 5090-claude (cipher reconcile this session).
**TTL:** 24h, expires 2026-09-16T16:30Z.
**Operator review:** pending.
