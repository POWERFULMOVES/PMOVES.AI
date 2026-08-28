<!-- PMOVES workflow fordham-pilot-convergence lane=governance · needsHumanReview=True -->

# Fordham Hill — Governance, Public-Quorum & Bylaws-Transition Scaffold

> **DRAFT — REQUIRES LEGAL REVIEW.** This document is an engineering + process scaffold, not legal advice and not an adopted instrument. Every clause touching bylaws, board transition, quorum, notice, or voting validity is marked and MUST be reviewed by New York cooperative-corporation counsel and adopted through the co-op's own statutory amendment procedure before it has any binding effect. Nothing here certifies an election result.

> **SECURITY RECONCILIATION:** The original HMAC ballot-receipt and shared-roster design below was
> rejected by decision records `07` and `08`. HMAC remains agent-trail integrity only;
> `vote.signed.v1` is disabled/non-contractual; contribution records are not legal eligibility; and
> no election path is active. The corrected target uses an independently attested roll, a complete
> immutable ballot set with inclusion evidence, committee Ed25519 tally attestation, paper parity,
> and a separately reviewed receipt-freeness mechanism.

---

## 0. Boundary statement (read first)

The fraud/mismanagement investigation into the outgoing board and management company is **human-led** — driven by **PMOVES-mike** and the **Missing Link** node. This platform provides **transparency and rehearsal models only**. The software **makes no accusations, reaches no findings, adjudicates nothing, and currently produces no binding ballot evidence**. Any future audit record must preserve ballot secrecy and be accepted only after legal, resident, and election-committee review.

---

## Part 1 — Architecture: Resident Public-Quorum + Voting Platform

### 1.1 What already exists in the repo (grounded)

| Layer | Primitive | Where | State |
|-------|-----------|-------|-------|
| Bylaws-analog design | Bicameral quorum/threshold/amendment model | `CATACLYSM_STUDIOS_INC/L2-DESIGN/constitution/Cataclysm_DAO_Constitution_v0.1.md:15-52` | DRAFT, token-weighted |
| Fordham-specific rollout | 90-day plan, resident-steward nomination | `CATACLYSM_STUDIOS_INC/L2-DESIGN/proposals/Cataclysm_Studios_DAO_Fordham_Hill_Proposal_v0.1.md` | DRAFT |
| "Who governs what" overlay | Instruments table + open TODOs | `CATACLYSM_STUDIOS_INC/L5-LEGENDARY/GOVERNANCE_ROSTER.md:36-41` | Flags the exact gaps |
| Eligible-voter roll | Humans registry | `CATACLYSM_STUDIOS_INC/PMOVES-PROVISIONS/roster/users.yaml:8-26` | Only founder populated |
| Signing / attestation | `sign_cgp()` HMAC over CGP payloads | `pmoves/tools/sign_trail.py:33`, `pmoves/tools/chit_security.py:72` | Real, tested — signs **agent** trails |
| Signing identity | Per-identity signing cards | `pmoves/config/signing_identity_cards.yaml`, `pmoves/config/agent_signatures.yaml` | Agent-scoped |
| Receipt schema | `agent.graphiti.signed.v1` JSON schema | `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json` | Agent-scoped |
| On-chain reference | Quadratic governor + ve-vault | `pmoves/contracts/solidity/contracts/CoopGovernor.sol`, tests `test/governance.test.js` | Tested but **plutocratic** |

**Do NOT reuse for a binding board vote:** `CoopGovernor.sol` computes voting power as `vault.votingPower(msg.sender)` and charges `rawVotes * rawVotes` (`CoopGovernor.sol:72-75`) — voting power is `sqrt(stake) × lock-multiplier`, i.e. more money = more votes. Its quorum check is a flat count `tally.forVotes >= proposalThreshold` (`CoopGovernor.sol:96`), not a percentage of the eligible roll. A NY housing co-op board election is **one-member/one-unit** (or per-share as the certificate of incorporation dictates) — the on-chain path is kept only as a *future optional* reference and must have equal-weight voting swapped in before any binding use.

### 1.2 Target architecture (reuse the attestation + mesh layers, replace the vote engine)

```
Resident (phone/laptop, no wallet, no gas)
        │  authenticates over the mesh (Tailscale tailnet: tailcad9b4)
        ▼
[Voter Roll]  users.yaml:humans  ──►  eligibility check (one unit = one vote)
        │
        ▼
[Ballot Service]  (NEW — does not exist today)
   • presents the open proposal (lifecycle below)
   • builds a CGP ballot payload
   • signs it via sign_cgp()  →  vote.signed.v1   (NEW subject, mirrors chit.signed.v1)
        │
        ▼
[Mesh Bus / NATS]  publish vote.signed.v1     (transport already used by chit.signed.v1)
        │
        ▼
[Tally Service]  (NEW — deterministic, "tool can tool")
   • counts one accepted signed ballot per eligible unit
   • applies the BYLAW quorum % against the eligible roll size
   • emits a committee-attested audit report after independent recomputation
        │
        ▼
[Audit Log]  append-only ballot-set commitment + inclusion proofs (unbuilt)
```

Grounding for each reused piece:
- **Signing:** `sign_cgp()` HMAC is valid for operator-controlled agent trails only. The rehearsal tally model uses distinct Ed25519 committee signatures, while a production non-operator key ceremony remains unbuilt.
- **Transport:** `vote.signed.v1` is a disabled, non-contractual room label with no schema, publisher, or service owner. It is not a direct analog of `chit.signed.v1` until an interface and activation review land.
- **Identity:** agent signing cards cannot establish resident voting eligibility. A future `voter-card.v1` must be election-scoped, committee-issued, human-witnessed, and unlinkable from contribution/token identity.
- **Roll:** `users.yaml:humans` is a one-entry template, not a legal voter roll. An independently governed committee process must establish residency and membership before quorum math is meaningful.

### 1.3 Proposal lifecycle (transparent, auditable)

1. **Draft** — proposal authored, classified (see amendment clause 2.5), notice window set per bylaw.
2. **Notice / comment** — published to all residents over the mesh; open comment period (the constitution's amendment model already uses a 2-week comment window, `Cataclysm_DAO_Constitution_v0.1.md:49`).
3. **Open vote** — future ballot intake writes to an immutable ballot set; no voter signs their choice and no active `vote.signed.v1` publisher exists.
4. **Close** — voting window ends; no further ballots accepted.
5. **Tally** — deterministic count, quorum-% check against roll, majority/supermajority per class.
6. **Publish audit report** — after independent deterministic recomputation, publish the committee-attested tally, ballot-set commitment, and privacy-preserving inclusion proof. Receipt-freeness still requires a separate reviewed mechanism.
7. **Archive** — immutable record retained for the co-op's books and for investigators.

### 1.4 What must be BUILT (gaps — none of this ships today)

- **Ballot service + Tally service** — grep of `pmoves/services` for `quorum|ballot|castVote|proposal` returns nothing; the only vote engine is the on-chain governor. These are net-new (small, deterministic, mesh-native).
- **Equal-weight voting model** — implemented/tested in the ToKenism rehearsal; no election service or binding activation exists. The SBT/`$WORK` "Citizen House" remains unbuilt.
- **Percentage-of-roll quorum model** — implemented against a proposal-snapshotted roll; the legal roll source and production service remain unbuilt.
- **Ballot contract + evidence path** — define any future subject/schema/service together with committee-issued eligibility, immutable ballot-set commitment, inclusion proofs, receipt-freeness, paper merge, and tally/audit generation. `vote.signed.v1` is not currently contractual.
- **Proxy / absentee / meeting-quorum tracking** — standard for a co-op annual meeting and a board transition; absent everywhere in the repo. Required before a real election.
- **Populated roll + Committee on Elders as a governance actor** — see Part 2.2.

**Design principle applied:** "tool can tool, model can model" — the tally is **deterministic code** (reproducible grounding), never a model judgment. Models have no role in counting votes.

---

## Part 2 — Bylaws-Amendment Framework (clause outline, NOT final text)

> **DRAFT — REQUIRES LEGAL REVIEW.** This is a *structured outline of clauses to amend*, so counsel and the Committee can see the shape of the transition. It is **not** amendment language. The existing Fordham Hill **certificate of incorporation and bylaws** are the governing instruments; the `Cataclysm_DAO_Constitution` is a *new parallel design artifact*, **not** an amendment to those bylaws. Each clause names where NY Business Corporation Law / Cooperative Corporations Law and the co-op's own amendment procedure (notice, quorum, supermajority) govern — those steps cannot be satisfied in a repo.

### 2.1 Board & management transition
- **Clause A — Removal / non-renewal of the current board & managing agent.** Outline: state the mechanism (removal vote vs. term expiry vs. management-contract non-renewal). **[COUNSEL: statutory removal grounds, notice, and required vote threshold; management contract termination terms.]**
- **Clause B — Interim governance during transition.** Outline: who holds authority between old and new boards; scope limits (no major expenditures) mirroring the constitution's "emergency brake" concept (`Cataclysm_DAO_Constitution_v0.1.md:44`) — **but recast to co-op law, not multisig.** **[COUNSEL + statutory: interim board authority.]**
- **Clause C — Records & fiduciary handover.** Outline: outgoing board/agent must deliver books, contracts, bank access, keys. **[COUNSEL. Also: this is where the human-led investigation consumes records — the platform only timestamps/attests receipt, it does not audit them.]**

### 2.2 Committee on Elders — enshrined role
- **Clause D — Recognition & standing.** Outline: define the Committee on Elders (long-time residents) as a named, first-class governance body with defined advisory/oversight rights. Register it in `users.yaml:humans` and record its decision rights in `GOVERNANCE_ROSTER.md` — the roster's own open TODO calls for exactly this (`GOVERNANCE_ROSTER.md:41`, `:38`). **[COUNSEL: whether a standing committee needs bylaw authorization and what powers it may hold vs. the board.]**
- **Clause E — Committee composition, selection, term, recall.** Outline: eligibility (tenure-based), how members are seated, terms, and recall — the constitution's "stewards recallable by vote" pattern (`Cataclysm_DAO_Constitution_v0.1.md:34-35`) is a reusable *shape*, re-keyed to residents. **[COUNSEL.]**

### 2.3 Resident electronic voting
- **Clause F — Authorization of electronic/remote voting & e-notice.** Outline: permit signed electronic ballots and electronic meeting notice as valid. **[COUNSEL + statutory: NY law on electronic voting/consent for cooperative corporations; whether bylaws must expressly authorize e-voting and e-notice; retention requirements.]**
- **Clause G — Ballot integrity & auditability.** Outline: adopt tamper-evident signed receipts (Part 1) as the record of a vote; require a reproducible, published tally; preserve receipts. **[COUNSEL: evidentiary sufficiency of cryptographic receipts for a valid corporate vote.]**
- **Clause H — Proxy & absentee voting.** Outline: define proxy/absentee mechanics and how they enter the tally. **[COUNSEL + statutory: proxy rules.]**

### 2.4 Quorum & thresholds (re-keyed from token % to member/unit)
- **Clause I — Quorum basis.** Outline: quorum = a percentage of **eligible units/shares present or voting**, computed against the populated roll — **replacing** the design layer's token-% quorum (`Cataclysm_DAO_Constitution_v0.1.md:20-27`). **[COUNSEL + statutory: the bylaws/statute set the quorum number; the % below are placeholders only.]**
- **Clause J — Vote thresholds by matter class.** Outline (re-keyed to one-unit-one-vote; percentages are PLACEHOLDERS pending counsel):
  - *Major (bylaw amendment, board removal, major expenditure)* — longest notice, highest quorum, **supermajority**.
  - *Standard (budgets, vendor/management selection)* — medium notice, majority.
  - *Routine (day-to-day, minor spend)* — short notice, simple majority.
  This mirrors the A/B/C-Type tiering shape (`Cataclysm_DAO_Constitution_v0.1.md:18-27`) but **strips all token weighting.** **[COUNSEL + statutory.]**

### 2.5 Amendment procedure itself
- **Clause K — How these bylaws are amended.** Outline: notice period + comment window + quorum + supermajority to adopt any future amendment (the constitution uses "amendment + 2-week comment," `Cataclysm_DAO_Constitution_v0.1.md:49` — a usable *shape*). **[COUNSEL + statutory: the actual amendment procedure for THIS co-op's bylaws is the controlling process; this clause must conform to it, not replace it.]**

### 2.6 Mesh/economic tie-in (informational, non-binding)
- **Clause L — Community mesh & contribution economy (optional, later).** Outline: authorize the pooled community-run exit-node mesh as a co-op service and reference the contribution-tracking layer (PMOVES-ToKenism) and the community's books (PMOVES-Wealth). Keep **strictly separate** from voting rights — contribution tokens MUST NOT translate into vote weight (that would re-introduce the plutocracy Clause I/J removes). **[COUNSEL: whether the co-op may operate a shared internet service and how costs/savings are allocated on the books.]**

---

## Part 3 — Sequenced next steps (engineering, not legal)

1. **Populate the roll** — fill `users.yaml:humans` template rows (`users.yaml:19-26`) with residents + seat the Committee on Elders; record rights in `GOVERNANCE_ROSTER.md` (closes its own TODOs at `:38`,`:41`).
2. **Fork the design instrument** — copy `Cataclysm_DAO_Constitution_v0.1.md` to a Fordham-specific file, re-key every quorum/threshold from token% to unit basis, and mark it DRAFT — REQUIRES LEGAL REVIEW. This is a design draft *for counsel to work from*, not the bylaws.
3. **Define `vote.signed.v1`** — new schema mirroring `signature.v1.schema.json`; issue per-resident signing cards in `signing_identity_cards.yaml` shape.
4. **Build ballot + deterministic tally services** — mesh-native, wallet-free, publishing signed audit reports.
5. **Counsel review + statutory adoption** — notice, quorum, supermajority per the co-op's real procedure. Only after this does anything bind.

Throughout: the platform attests and tallies; **it never investigates or concludes.** That remains with PMOVES-mike + Missing Link.
