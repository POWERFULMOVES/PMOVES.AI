<!-- graphiti:b850-claude phase:voter-identity-key-custody ts:2026-07-17T12:00:00Z -->

# Fordham Hill — Voter Identity & Key Custody (Decision Record)

> The signing primitive this package reuses today (symmetric HMAC) lets the operator forge any ballot,
> which is disqualifying for a contested election. The intuitive fix — give each resident a key and have
> them sign their vote — was **pressure-tested and rejected**: a voter signature over a choice is itself
> a coercion receipt, it disenfranchises an elderly electorate, and routing enrollment through the
> operator recreates the very forgeability it set out to remove. This record decides the corrected
> architecture: **residents authenticate eligibility, they do not sign their choice; the tally is
> threshold-signed by an election committee (no single party can forge); a paper ballot is a first-class
> equal path.** DRAFT, REQUIRES LEGAL REVIEW.

**Author:** B850-CLAUDE (Knuckles) · **Date:** 2026-07-17 · **rev 2** (2026-07-17 — recommendation
inverted after a three-lens adversarial test; see §5 and §12)
**Informs:** the A2UI `pm-ballot` lane · **Builds on:** [`07-ballot-prior-art-and-reconciliation.md`](07-ballot-prior-art-and-reconciliation.md)
**Relates:** [`05-room-agents-mint-specs.md`](05-room-agents-mint-specs.md) (Archon minting) · `pmoves/contracts/schemas/identity/signing-card.v1.schema.json`

## 0. Boundary statement (read first)

Same boundary as `04-governance-bylaws-scaffold.md:9` and `07:§0`. The platform provides **transparency
and auditable records only**. It makes no accusations, confers no legal authority, and the human-led
process stays human-led. Every clause touching a binding vote routes to NY cooperative-corporation
counsel. This document is a **design decision record** — nothing here is built, and the recommendation
is a proposal for review, not a commitment.

## 1. The decision, in one paragraph

The real requirement is that a tally be provable to a hostile party **and** that no one — the operator
included — can forge it, without anyone learning how a given resident voted. Our current CHIT signing
is **symmetric HMAC held by one operator node**, so the operator can forge any receipt or tally
(`07:§0`; `chit_security.py:91` `sign_cgp` uses one shared secret to both sign and verify) — that is
the flaw to fix. The *intuitive* fix, "give each resident a key and have them sign their vote," seemed
to reduce to "where does that private key live." **The adversarial test in §12 showed that framing is
wrong** (§5): signing a choice breaks the secret ballot, the storage/recovery model — not the key —
decides who can vote, and the forgeable step is enrollment, not signing. The corrected answer is §5b.

## 2. Threat model — what the system must guarantee, and against whom

| Adversary | What they might attempt | What the system must guarantee (how §5b answers it) |
|-----------|-------------------------|-----------------------------------|
| The operator / whoever runs the state authority | Add, drop, or alter ballots; manufacture a tally | No single party can sign a valid tally alone → **committee threshold key**, not one operator secret |
| The operator, at *enrollment* | Bind a key it controls to a resident; deny/duplicate eligibility | Enrollment authority sits with a **non-operator committee**, human-witnessed, on an append-only committee-signed log |
| A coercer (someone with power over a resident) | Compel a resident to prove how they voted | **Residents never sign their choice**; a nonce commitment can support inclusion checking, but receipt-freeness additionally requires revoting, a time-limited verification window, or an equivalent reviewed mechanism |
| An outside attacker / a shared or lost device | Steal a credential and vote as someone | Eligibility credential is election-scoped and unlinked to the cast ballot; a lost device is not a lost franchise (paper equal path) |

The auditors this must convince are external and non-trusting: the Attorney General, a bank, and a
contested board. That audience is why **symmetric HMAC is not enough** — but, per §5, the fix is *not*
a voter signature; it is committee threshold signing plus committee-controlled enrollment.

## 3. The load-bearing principle

> **The voter's private key must never be custodied by the operator or any server.**

Everything else follows from this one line:

- **Server-side stores are for public material only.** Supabase, JuiceFS/S3, NATS — these hold
  public keys, the eligibility roll, and the append-only *signed-receipt* log. They must never hold a
  voter's private key; doing so would rebuild the HMAC forgeability problem with extra steps.
- **`localStorage` is voter-side but weak.** It is at least on the right side of the trust boundary,
  but a plaintext key in `localStorage` is exfiltratable by any XSS, dies on a cache-clear, is
  single-device, and leaks on a shared kiosk. The ClawZ reference (`PMOVES-ClawZ/ui/src/ui/device-identity.ts`)
  stores exactly this way — fine for a device-identity fingerprint, **not** for a contested ballot.

## 4. Custody options compared

| Option | Where the private key lives | Strength | Cost / caveat |
|--------|-----------------------------|----------|---------------|
| **A. `localStorage` Ed25519** (ClawZ as-is) | Browser JS storage, plaintext | Weak — XSS-exfiltratable, single-device, lost on cache clear | Zero new work; **rejected as primary** |
| **B. WebAuthn / passkey** (platform authenticator) | Device secure enclave / TPM, normally **non-exportable** | Strong resistance to key export and phishing; does **not** make the relying-party page or authenticated session XSS-proof; device sync depends on the platform/provider | No npm dep needed; verification is over `authData ‖ SHA-256(clientDataJSON)`; default alg P-256 (Ed25519 only on some authenticators); needs enrollment |
| **C. Wrapped Ed25519** (`@noble/ed25519` + WebCrypto non-extractable / passphrase-encrypted) | Browser, but encrypted at rest | Medium — resists casual theft, gives raw Ed25519 over our netstring preimage | We own custody + recovery; passphrase UX for elderly residents is real friction |
| **D. Printed recovery card** (public-key fingerprint + recovery secret / QR) | Paper, resident-held | Complements A/B/C — survives device loss, fits in-person enrollment | Physical issuance + secure printing; not a signing method on its own |

## 5. The signing key is not the crux (three findings that reframe the decision)

An adversarial review (§12) tested the intuitive design — "give each resident a key, have them sign
their vote." All three lenses rejected it, and together they show the original framing optimized the
wrong variable. The private key's *storage location* matters far less than three things it ignored:

1. **Signing your choice defeats the secret ballot.** A voter signature over the choice is a
   transferable, publicly-verifiable proof of *how* someone voted — exactly the coercion receipt the
   `pm-ballot` scheme spends three mitigations removing (strip `voterId`/`choice`, omit `ts`,
   seal + hash-order the log). A coercer says "unlock your key and sign `yes` in front of me." Omitting
   the voter signature removes that direct proof, but a nonce commitment provides individual inclusion
   evidence rather than receipt-freeness. A reviewed revoting rule, time-limited verification window,
   or equivalent mechanism is still required before calling the system coercion-resistant.
2. **Enrollment, not signing, is the integrity surface — and the operator controls it.** A
   client-side key stops the operator forging a *signature*, but does nothing to stop whoever writes
   the eligibility registry from binding a key *it* generated to a resident's name (then it can forge
   that resident's ballot), refusing to enrol a disfavored resident, or minting duplicates. Contested
   co-op disputes live at the enrollment step, which client-side keygen leaves wide open.
3. **Custody-and-recovery, plus a non-digital equal path, decides who gets to vote.** Requiring a
   secure-context passkey structurally excludes a large share of an elderly electorate (device / OS /
   biometric funnels; ~76% smartphone ownership at 65+), breaks or leaks on the shared devices these
   residents use, and every recovery path either becomes a bearer secret or an operator-assisted
   re-issue that re-imports operator forgeability.

## 5b. Recommendation (rev 2 — corrected architecture)

**Residents authenticate *eligibility*; they do not sign their *choice*. The ballot content /
tally is signed by an *election-committee threshold key* (M-of-N, asymmetric) so no single party —
operator included — can forge. This does not itself establish receipt-freeness; that remains a separate
protocol and procedural gate. A paper ballot is a
first-class equal path, not a fallback. `voter-card.v1` is an *eligibility credential* (public),
committee-issued and human-witnessed, deliberately **decoupled from Archon minting and from the token
structure**.**

Why each piece:

1. **Threshold committee signing replaces single-operator HMAC** — this is how you answer `07`'s
   operator-forgeability *without* a voter signature. No single party (operator or otherwise) can
   sign a tally alone; the committee's public key is what external auditors verify against. It does
   not touch the plutocratic on-chain governor (`CoopGovernor.sol:72`, stake-weighted — unusable for
   one-member-one-vote per `README:§Open decisions`).
2. **Eligibility is separated from ballot content** — a credential proves a resident *may* vote at
   booth-entry; it is never linked to the cast ballot. A nonce commitment supports individual
   verifiability only when the voter also receives a trustworthy inclusion proof against a published,
   append-only ballot-set commitment. Neither the inclusion-proof service nor a trusted bulletin-board
   procedure is implemented today, and no voter signature is added as a substitute.
3. **Enrollment is committee-controlled, human-witnessed, non-operator** — a neutral scrutineer body
   the contesting side trusts writes the registry, with an append-only, committee-signed eligibility
   log. Client-side keygen alone cannot prove the enroller is the named resident; a witness must.
4. **Paper is equal, not pity** — a guaranteed non-digital path is required both for franchise
   (residents without capable devices) and, almost certainly, for legal compliance with the co-op's
   duty to enfranchise every member.
5. **Decouple from Archon and from tokens** — issue the eligibility credential via a minimal,
   ballot-only path, **not** the operator-authenticated `archon.mint.*` agent pipeline (§7), and keep
   the credential's public key from becoming the shared join-key into contribution/wealth (§8).
6. **Member signing exists only in Mode B (§8), never in Fordham's Mode A.** Fordham is an adversarial
   secret ballot — no member signs their choice. A member signature (to *form a group* and earn
   attribution — the union card, the micro-business, the pop-up) belongs to the consensual/attributable
   **Mode B**, and there it is **raw Ed25519 over the netstring preimage**, never WebAuthn (dead on the
   co-op LAN with no secure context; drags device-linkable credential-ID + signature-counter into the
   receipt).
7. **The committee verifies the ballot set before signing** — committee members must recompute the
   tally deterministically from the complete immutable ballot log, reconcile paper ballots, and verify
   the published ballot-set commitment/inclusion evidence. They must reject an operator-supplied tally
   or ballot set that cannot be independently reproduced; threshold signatures authenticate an audited
   result, not an unchecked operator assertion.

What survives from rev 1: the load-bearing principle (§3 — no private key server-side) still holds; a
`voter-card.v1` still holds *public material only* and stays separate from `signing-card.v1`; and the
ClawZ Ed25519 module remains reusable **only** for the attributable-mode case in (6).

## 6. Three-party architecture (voter · committee · storage)

The corrected design has three parties, and the election committee — not the operator — is the trust
anchor for both enrollment and tally signing.

```
 VOTER                        ELECTION COMMITTEE (M-of-N, non-operator)      STORAGE (public only)
 ─────                        ─────────────────────────────────────────      ─────────────────────
 authenticates eligibility ──▶ witnesses enrollment, writes registry ──────▶ voter-card.v1 registry (Supabase)
   (credential proves MAY                                                     append-only eligibility log
    vote; not linked to choice)                                                 (committee-signed)
 casts vote → nonce-commitment  recomputes full ballot set, then signs ─────▶ append-only audit log (JuiceFS/S3)
   (inclusion proof unbuilt;      (no single party can forge; verifiers        vote.signed.v1 (disabled,
   no voter signature)           check the committee public key)              non-contractual scaffold)
                                                                                Tally model exists; service unbuilt
 PAPER BALLOT (equal path) ─────────────────────────────────────────────────▶ counted into the same tally
```

Two lines never get crossed: (a) a voter's *choice* is never signed by a voter key, and (b) the
*eligibility* credential is never linked to the *cast ballot*. JuiceFS (the server-side S3 object
store, mid-cutover per `JUICEFS_OBJECT_STORE_MIGRATION.md`) holds the **audit log**; Supabase holds the
**public eligibility registry** — neither holds a private key, and the **tally-signing key is the
committee's, split M-of-N**, never a single operator secret.

`vote.signed.v1` is cataloged only as a Fordham rehearsal label and is gated `enabled:false`. It has no
event schema in `pmoves/contracts`, no active publisher, and no service/health-check owner; it is not a
contractual NATS interface until those artifacts and the activation review land together.

## 7. Do NOT mint the voter card through Archon (reversed from rev 1)

Rev 1 proposed minting the voter card through Archon's agent pipeline (`archon.mint.agent.v1` → QA gate
→ `archon.mint.confirmed.v1`; `05-room-agents-mint-specs.md`, `pmoves/services/archon/CLAUDE.md`) with
the boundary "Archon mints the public card, the private key is client-side." The adversarial review
showed that boundary defends the wrong step:

- **The QA gate is a manifest linter, not a scrutineer** (`archon-qa-agent`: schema frontmatter, NATS
  branding, name collisions, no-hardcoded-URLs). It verifies nothing about whether a public key
  belongs to a real, unique, eligible resident. Citing it as ballot protection is theater.
- **The mint pipeline authenticates the operator, not the voter** — mint is tied to an operator
  "creator" session (`archon/CLAUDE.md` RLS `creator_id = auth.uid()`). Whoever holds that session
  controls the registry write, and can bind a key *it* generated to a resident's name, refuse to
  enrol a disfavored resident, or mint duplicates. That makes **Archon the eligibility chokepoint the
  threat model (§2) exists to remove** — the operator-forgeability the client-side-key story claimed
  to solve simply moves from the signing step to the enrollment step.

**Corrected boundary:** voter enrollment is issued by the **election committee via a minimal,
ballot-only path**, human-witnessed, with an append-only **committee-signed** eligibility log — not the
operator-authenticated agent-mint pipeline, and not sharing its QA agent or `archon_minted_artifacts`
schema (which would re-couple resident voters to operator-agent tooling). Client-side keygen still
never sends a private key anywhere; but issuance authority sits with the committee, not the operator.

## 8. The general primitive — two modes, and the invariant between them

The Fordham ballot is one instance of a broader primitive: **a group forms, and its members'
participation is credentialed and (optionally) attributed.** The group structure is interchangeable —
tenants forming a quorum, workers forming a union, three friends forming a lemonade-stand pop-up. The
same credential serves all of them, but it runs in one of **two modes**, and conflating them is the
central danger.

| | **Mode A — adversarial / secret** | **Mode B — consensual / attributable** |
|---|---|---|
| Example | Fordham recall; hostile-employer union authorization | Friends form a micro-business; a pop-up event; a co-op formed by mutual agreement |
| Does a member sign their choice? | **No** — a signature would be a coercion receipt | **Yes** — members *want* attributable proof they participated |
| Attribution / token linkage | **Decoupled** — no link to contribution/wealth identity | **On** — this is the point: shape attribution → credit → wealth |
| Signing authority for the outcome | Committee **threshold** key (no single party forges) | The group co-signs its own formation |
| Secrecy | Secret-ballot target; receipt-freeness mechanism still counsel/protocol-gated | Public / attributable by design |

**Mode B is grounded in primitives that already exist:** *shape attribution* credits contributions via
**Dirichlet-weighted CGP packets** (`.claude/context/geometry-nats-subjects.md`), fed by
`shape.trace.recorded.v1` → `shape.profile.updated.v1`. Those subjects and the simulator are cataloged;
SBT (soul-bound token) minting and live Firefly settlement remain unbuilt/activation-gated. Thus the
current executable claim is attribution simulation and export, not resident credit issuance or settled
wealth. That Mode-B coupling remains a product direction, not evidence of Mode-A legal eligibility.

**The invariant (this is the load-bearing rule):**

> **The mode is explicit and the two never mix.** Mode-B attribution linkage must never touch a Mode-A
> secret ballot (it would re-enable exactly the coercion and vote-buying the adversarial test flagged),
> and a contested election must never be run in Mode B. A credential may exist in both modes only if
> its Mode-A use is *unlinkable* to its Mode-B identity — i.e. the election-scoped eligibility key of
> §5b(5) is **not** the same identifier as the member's attribution/wealth key.

**Still DO NOT BUILD for Fordham** — Fordham is Mode A, and Mode A is the whole scope of the decision
here. Mode B (the union card, the micro-business, the pop-up) is the roadmap, gated on the
**token-structure refresh** ([`../../architecture/TOKEN_STRUCTURE_REFRESH.md`](../../architecture/TOKEN_STRUCTURE_REFRESH.md)
— the incentive engine; `CoopGovernor.sol:72` is stake-plutocratic and unusable as-is), counsel review
of the securities question (`README:§Legal-review` "SECURITIES / TOKEN CHARACTERIZATION" — earned
standing + surplus for pooled resources is a *Howey* pattern), and a governance decision. Recording the
two-mode shape now is what keeps the tight Mode-A decision from painting the general primitive into a
corner.

## 9. Sequencing

1. **This decision record** (here), rev 2 → review by Mavis's A2UI lane + counsel + the election
   committee (once seated).
2. ~~Pressure-test the recommendation~~ ✓ done (§12) — it inverted the recommendation.
3. **Only then**, and as a v0.3 lane: define the **committee threshold-signing** scheme for the tally,
   the **eligibility credential** (public, election-scoped, committee-issued, human-witnessed — *not*
   Archon-minted), the **paper-parity** merge, and the recovery/enrollment operations.
4. The A2UI `pm-ballot` receipt (`#2153`) is a gated rehearsal. Its nonce commitment can support
   individual verifiability only after a trustworthy append-only ballot-set commitment and inclusion
   proof are implemented and reviewed; it does not by itself provide receipt-freeness. **No voter
   signature is added to a secret ballot.** A raw-Ed25519 voter signature is considered only if an
   explicitly attributable (non-secret) voting mode is ever specced.

## 10. Open operator decisions (new)

- **ENROLLMENT MODEL:** in-person enrollment day vs remote self-enroll — decides how residents get a
  card and whether an operator ever assists (assistance must never touch the private key).
- **DEVICE REALITY:** confirm what devices Fordham residents actually have (modern phones support
  passkeys; some elderly residents may not) — decides how heavily the wrapped-Ed25519 + printed-card
  fallback must carry the load, and whether anyone is at risk of disenfranchisement by the tech choice.
- **RECOVERY POLICY:** what happens on device loss — passkey sync, re-enrollment, or printed-card
  recovery — and who authorizes a re-issue without becoming a forgery vector.

## 11. Legal-review items (DRAFT — REQUIRES LEGAL REVIEW)

- **KEY-CUSTODY & DISENFRANCHISEMENT:** whether requiring a cryptographic credential to vote (and any
  device/tech prerequisite) is compatible with NY cooperative election requirements and does not
  disenfranchise members without suitable devices — counsel must confirm before a binding vote.
- **PUBLIC-KEY REGISTRY IS PII:** the `voter-card.v1` registry links a public key to a named resident
  and eligibility; retention, consent, and privacy handling need review under applicable NY privacy
  obligations (extends the existing `README:§Legal-review` "DATA / PRIVACY & MEMBER RECORDS" item).
- **MULTI-USE / TOKEN CHARACTERIZATION:** if the voter card later carries contribution/wealth/token
  weight, confirm it does not constitute a security or create securities-law exposure — ties directly
  to the existing "SECURITIES / TOKEN CHARACTERIZATION" register item; do not couple before review.

## 12. Adversarial test results (done — these drove rev 2)

Three independent lenses were each tasked to *break* the rev-1 "resident signs their vote" design.
All three rejected it; their verdicts are the basis for §5b.

| Lens | Verdict | Load-bearing finding |
|------|---------|----------------------|
| **UX / disenfranchisement** | Need a different model | WebAuthn-primary structurally excludes ~20%+ of an elderly electorate (device/OS/biometric funnels; ~76% smartphone at 65+, Pew 2024), breaks/leaks on shared devices, and recovery re-imports operator trust — custody-and-recovery + a paper equal path decide franchise, not the signing primitive. |
| **Crypto fit** | Neither belongs as primary for a secret ballot | A voter signature over the choice IS a coercion receipt; WebAuthn needs a secure context absent on the co-op LAN the code itself calls realistic, and leaks device-linkable credential-ID + signature-counter into the receipt. If any voter key: raw Ed25519, attributable-modes only. |
| **Minting / token coupling** | Decouple ballot card from Archon and from tokens | Archon's QA gate is a linter not a scrutineer; the mint pipeline authenticates the operator, making Archon the eligibility chokepoint; and a shared public key silently joins vote-identity to an already-plutocratic, securities-flagged economy. |

Sources are cited inline in the review record (Pew mobile fact sheet; W3C WebAuthn L2 + privacy self-review;
passkey device-support tables; *SEC v. W.J. Howey Co.*, 328 U.S. 293; N.Y. Cooperative Corporations Law).

## 13. What to validate next (with counsel + committee)

- **Threshold scheme choice:** which M-of-N committee-signing primitive (e.g. FROST/Ed25519 threshold,
  or a simple k-of-n multisig over the tally) fits PMOVES infra and is auditable by a non-technical
  scrutineer body.
- **Eligibility-vs-content unlinkability:** the concrete mechanism (token-based eligibility, blind
  issuance, or committee-attested roll) that lets a resident prove eligibility without linking to their
  cast ballot.
- **Paper/digital parity:** how paper ballots merge into the same committee-signed tally so neither
  path is second-class.
- **Legal:** the §11 items — disenfranchisement compliance, PII of the eligibility registry, and the
  securities/vote-buying question if identity ever couples to the token economy.

---

`PROPOSE::B850-CLAUDE::FORDHAM-VOTER-IDENTITY-KEY-CUSTODY-DECISION::2026-07-17`
