<!-- graphiti:b850-claude phase:ballot-prior-art ts:2026-07-16T23:30:00Z -->

# Fordham Hill — Ballot Prior Art & A2UI Reconciliation

> The signing primitive this package reuses for vote receipts is **symmetric HMAC**. The operator
> holds the key, so the operator can forge any ballot and any tally. For a contested recall — where
> the operator's neutrality is exactly what is in dispute — that is disqualifying, not a detail.
> This document corrects that, reconciles the A2UI `pm-ballot` lane against this one, and supplies
> the voting-systems prior art that **neither lane had** — DRAFT, REQUIRES LEGAL REVIEW.

**Author:** B850-CLAUDE (Knuckles) · **Date:** 2026-07-16
**Reconciles:** this pilot lane ⟷ A2UI `pm-ballot` (#2132 / #2133 / #2134 / #2153)

## 0. Boundary statement (read first)

Same boundary as `04-governance-bylaws-scaffold.md:9`. The platform provides **transparency and
auditable records only**. It makes no accusations. The fraud investigation stays human-led. Nothing
here confers legal authority, and every clause touching a binding vote routes to NY cooperative-
corporation counsel before use.

One addition, and it is the point of §4: **an audit record and a secret ballot are different
instruments with opposite properties.** This package currently builds one component and asks it to
be both.

## 1. The collision — two lanes built the same thing, neither read the other

| | This lane (`pmoves/docs/pilots/fordham-hill/`) | A2UI lane (#2132–#2134) |
|---|---|---|
| Ballot design | `04`: sign_cgp → `vote.signed.v1` → tally service | `pm-ballot.js` client-side tally in browser state |
| Voting basis | flags one-member vs unit vs share as **the** decision (`README.md`, Open Operator Decisions) | silently assumes one-voter-one-vote |
| Quorum | must be **% of eligible roll** (`README.md`) | `quorum` attribute, % of `eligible-voters` attr |
| Roll | `users.yaml:9` — 1 of N, flagged | `eligible-voters="47"` — a hardcoded number |
| Legal | 10-item Legal Review Register | none |
| Prior art | none | none |

**This lane is the better work.** It already states, in writing, what the A2UI lane discovered
independently and late:

- `README.md` — *"on-chain governor is plutocratic quadratic-stake … it CANNOT express
  one-member-one-vote … so it must NOT ship as-is for a board election"*
- `04:80` — *"the sign primitive today emits `agent.graphiti.signed.v1`, not ballots"*
- `README.md` Legal Review Register — *"E-VOTING / REMOTE-QUORUM VALIDITY … must be validated
  before a real board election"*

`pm-ballot` was built without reference to any of it. Two lanes now contradict each other on the
single most consequential choice this package names (voting basis). **That is the first thing to fix,
and it is a governance decision, not an engineering one.**

## 2. CORRECTION — HMAC cannot underwrite a contested ballot

This is the one substantive error in an otherwise careful package, and it is repeated as a
cross-cutting insight, so it propagates.

**The claim** (`README.md`, Cross-cutting insights; restated `04:60`):

> *"One signing key underwrites both trust surfaces … A resident ballot is just a different CGP
> payload signed by the same primitive → a tamper-evident vote receipt with no wallet, gas, or
> blockchain."*

**Why it fails.** `sign_cgp()` (`pmoves/tools/chit_security.py:91`) is `HMAC-SHA256` over a
canonicalized doc, verified by `hmac.compare_digest` (`:116`). HMAC is **symmetric**: signer and
verifier share one secret. Whoever holds `CHIT_SIGNING_KEY` — the tally service, i.e. the operator —
can mint any ballot for any resident, retroactively, and produce a perfect signature. No resident can
distinguish a real ballot from a forged one. Issuing per-resident cards does not help: the server must
hold every key to verify, so it can forge as any resident.

HMAC gives **integrity against outsiders**. A contested recall needs **verifiability against the
operator**. Those are different properties, and this package needs the second one.

**This also destroys the evidentiary use.** The stated intent is to bring records to the Attorney
General and to a lender. A symmetric-HMAC record is worthless there: opposing counsel asks one
question — *"who controls the signing key?"* — and the artifact is impeached. A record you can forge
is not evidence that you didn't.

**The fix — Ed25519 (asymmetric).** Resident's card holds a **private** key; the roll publishes the
**public** key. The resident signs their own ballot; anyone verifies with the public key; the operator
**cannot** forge. This is the minimum bar for both (a) resident trust and (b) AG/lender admissibility.

**And we do not have to invent it — we already wrote it.**
`PMOVES-ClawZ/ui/src/ui/device-identity.ts` is a working Ed25519 identity module on
[`@noble/ed25519`](https://github.com/paulmillr/noble-ed25519) `3.1.0` (audited, widely used). It
already does the exact shape a resident signing card needs, with only the noun changed:

| `device-identity.ts` | ballot equivalent |
|---|---|
| `utils.randomSecretKey()` → `getPublicKeyAsync()` (`:52-53`) | resident keypair, generated on their device |
| `fingerprintPublicKey()` = SHA-256 of pubkey (`:46-47`) | stable resident/card ID |
| `base64UrlEncode` + persistence (`:57-58`, `:71-72`) | card storage + roll publication |

So: **reuse the ClawZ pattern**, do not hand-roll. Private key stays on the resident's device; the
roll publishes only the public key and its fingerprint.

**But Ed25519 is authentication, not secrecy.** A resident-signed ballot tied to a published public
key is attributable — it proves *who* voted and *that* the vote was not forged by the operator. It
does **not** satisfy secret-ballot or receipt-freeness requirements (§4, §5.1). A signed ballot that
a resident can later prove is *theirs* is a coercion instrument, not a protection against one. An
unlinkable ballot protocol (mix-net, homomorphic tally, or BeleniosRF-style re-randomization) must
sit between authentication and tabulation; Ed25519 authenticates the *eligibility to vote*, not the
ballot itself. See §4 for the petition-vs-ballot split and §3 prior-art table for receipt-free
schemes.

Two more requirements this does not close:
- **Key enrollment integrity** — the roll must be built through an authenticated enrollment process,
  not operator-editable data. If the operator can add or swap public keys, the forgery problem
  returns at the enrollment layer instead of the signing layer.
- **Key revocation and recovery** — lost cards, compromised keys, and resident turnover require a
  defined rotation path. The roll must support key replacement without breaking historical
  verifiability.

- `signing_identity_cards.yaml` already has the right *shape* — one card per signer, `ml` half for a
  key. Today the ml key fields are **null** ("h-only / pending-ml", audit advisory not fatal). That
  card model is the natural carrier; ClawZ supplies the key material it is missing.
- Keep HMAC for agent trails, where the operator is not the adversary. It is correct there.

> **Correction to my own first draft:** I initially recorded "no Ed25519 anywhere in the repo,"
> repeating a survey result I had not checked. It is wrong — `device-identity.ts` has had it all
> along. Flagging the error rather than quietly fixing it, because "we already built this and forgot"
> is the exact failure mode this document exists to stop.

> **LEGAL REVIEW ITEM (new):** whether an Ed25519-signed electronic ballot satisfies NY signature /
> record requirements for a valid cooperative vote, and what key-custody obligations attach to
> resident private keys held on resident devices.

## 3. Prior art — the tracking each spoke was missing

Bespoke is fine. Untracked is not. Repo-wide greps (at revision `6b995805c`, 2026-07-17;
`rg -l -i '<term>' --glob '*.{md,py,ts,js,yaml,yml}'` excluding `node_modules`):

| Term | Files found |
|------|-------------|
| `Benaloh` | 1 — this document |
| `ElectionGuard` | 1 — this document |
| `coercion resistance` | 1 — this document |
| `Ostrom` | 1 — this document |

Prior to this document's creation, all four terms returned **0 files**. The only matches now are
self-references in this section. There was no voting-systems research behind any of this.

| Decision | Tracks to |
|---|---|
| E2E-verifiable voting is the right family | [Overview of E2E Verifiable Voting Systems](https://arxiv.org/pdf/1605.08554) |
| Web-based open-audit voting; reference system | [Helios (Adida, 2008)](https://dl.acm.org/doi/10.5555/1496711.1496734) |
| **Helios is scoped to *low-coercion* environments** — Fordham Hill is not one | ibid. |
| Receipt-freeness = voter *cannot prove* their vote even if they want to | [Delaune, Kremer & Ryan, CSFW'06](https://people.irisa.fr/Stephanie.Delaune/PUBLICATIONS/DKR-csfw06.pdf) |
| Coercion-resistance, formal definition | [Juels, Catalano & Jakobsson](https://eprint.iacr.org/2002/165.pdf) |
| Receipt-free scheme with re-randomization | [BeleniosRF](https://eprint.iacr.org/2015/629.pdf) |
| Revoting as statutory anti-coercion; **ballot count must stay secret** | [Estonian revoting / individual verifiability](https://dl.acm.org/doi/10.1007/978-3-031-32415-4_21) |
| Durable receipts are a coercion instrument → verification window is time-limited (~30 min) | [Re-voting Under Surveillance (eID logs)](https://link.springer.com/chapter/10.1007/978-3-032-05036-6_12) |
| Electronic voting is **permitted** for NY co-op shareholder meetings (BCL §602) | [Colbert Law](https://colbertlaw.us/ny-coops-and-business-corporations-are-allowed-electronic-voting-for-shareholders-meetings/) · [Habitat](https://www.habitatmag.com/Publication-Content/Board-Operations/2019/2019-November/Electronic-Attendance-and-Voting-Now-Legal-in-Co-op-Annual-Meetings) |
| Corporation must take *"reasonable measures to verify each person … is a shareholder of record"* → eligibility is **statutory**, not optional | ibid. |
| Inspectors of election tabulate; if bylaws require them the board **must** appoint | [CooperatorNews — election process](https://cooperatornews.com/article/board-resource-guide-a-look-at-the-board-memb) |
| **The managing agent is often appointed inspector of election** | ibid. |
| Co-op board duties / shareholder rights baseline | [NY AG — Understanding & Dealing With a Co-op Board](https://ag.ny.gov/sites/default/files/coop_board_directors.pdf) |

**The inspector-of-election line deserves its own paragraph.** Under NY practice the managing agent
is frequently appointed **inspector of election** — the party that tabulates. In any *contested*
election, the incumbent's continuation is itself the question on the ballot; an inspector drawn from
the incumbent side is therefore structurally conflicted, whatever the facts of a given building.
That is a governance property, not an accusation, and it is probably the highest-leverage item in
this document — because no amount of cryptography fixes a conflicted tabulator, and a conflicted
tabulator is challengeable on its own terms.

**Confirm from the bylaws who the inspector of election is, and whether the role can be filled
independently, before building anything.** If it can (e.g. by the Committee on Elders, or a neutral
third party), that single fact does more for the credibility of a result than every mechanism in
§2–§5 combined.

### 3.1 Research-integrity note (upstream)

The token-governance mechanism this package inherits is **unsourced**:

- `CATACLYSM_STUDIOS_INC/L1-FOUNDATION/articles_long.md` — *"Simulation insights show that while a
  linear model might require ~500 tokens for vote control, our advanced model increases the cost to
  ~750 tokens"*, stated twice. **There is no simulation.** No code, no data, no methodology exists
  for it. The file still carries ChatGPT persona artifacts (`🧙🏾‍♂️`).
- `V_i = sqrt(x_i) × (1 + 0.5 × (T_i − 1))` — no derivation, no citation.
- `Cataclysm_DAO_Constitution_v0.1.md` — quorum/threshold numbers (20% Token + 25% Citizen, pass at
  60%) are unsourced. These would govern real people's homes.

**Counter-example, and the standard to copy:** `PMOVES-ToKenism-Multi/ECONOMIC_MODEL_VALIDATION_REPORT.md`
— real bibliography (Gini 1912; Gibrat 1931; Orshansky 1965 *Soc. Sec. Bull.* 28(1); Reed 2003
*Physica A*; Zeuli & Radel 2005 *JRAP*), 34 passing tests, and explicitly honest about its own limits
("plausible but not empirically validated"). That is what tracked work looks like. It is economics,
not voting — the voting equivalent does not exist yet.

## 4. Two instruments, never one component

The operator intent is to retain records for the **Attorney General** and a **lender**. That is
correct and it is *not* a ballot function. Conflating the two is the deepest bug in the stack —
deeper than any crypto defect.

| | **Petition / affidavit** | **Secret ballot** |
|---|---|---|
| Signed, attributable | **yes — that is the point** | never |
| Provable afterwards | **yes** | must be impossible |
| Purpose | show N named residents assert X; evidence for AG / lender | elect or recall with legal validity |
| Coercion | accepted; signing is voluntary and public | fatal |
| Crypto | Ed25519, identity bound, durable | Ed25519 + receipt-freeness, identity unbindable |
| Prior art | union **authorization cards** | **NLRB election** |

US labor law already encodes this split, and the reason is the generalization target named by the
operator (drivers' co-ops, Dunkin workers): authorization cards are signed because demonstrating
support *requires* attribution; the NLRB election is secret because employers retaliate. Both exist
because they do different jobs.

**Consequence for this pilot.** If the *election* produces provable individual votes, the board's
counsel does not argue the merits — they argue it **was not a secret ballot** and seek to void it on
procedure. A provable ballot is a self-inflicted wound. Ship the petition as the AG artifact; ship the
ballot as the secret instrument; never let one component be both.

> **LEGAL REVIEW ITEM (new):** whether the co-op's certificate of incorporation / bylaws require a
> **secret** ballot for board elections and recalls. If yes, any receipt design that lets a voter
> prove their choice is a **validity risk**, independent of its cryptography.

## 5. Findings absent from both lanes

Discovered while implementing #2153; each is now tracked (§3).

1. **Receipt-freeness violated — the "fix" made coercion worse.** #2153 hands the voter
   `(choice, ts, nonce)`: a durable, verifiable proof of their own vote. Rev-1 let the board *read*
   the log; rev-2 lets them *demand a confession the voter cannot fake*. The UI literally instructs
   residents to save it. Estonia time-limits verification (~30 min) precisely because a durable
   receipt **is** the coercion instrument.

2. **`status: "superseded"` defeats revoting.** Revoting is the statutory anti-coercion mechanism,
   and it only works if *the number of ballots stays secret*. Publishing a superseded flag tells the
   coercer the voter overrode their coerced vote — this is the documented Estonian eID-log leak,
   reproduced by design. Spec `a2ui-v0.2-ballot.md` §5.4.

3. **Timing correlation — the nonce alone is theater.** A receipt published in the same state update
   that increments its option's tally re-links without touching the hash; an observer polling state
   diffs two snapshots and reads the vote. Demonstrated in a real browser. Mitigated in #2153 (seal
   until close · no `ts` on public receipts · order by hash) — but that mitigation is *upstream* of
   the receipt-freeness problem, which remains open.

4. **Individual ≠ universal verifiability.** A resident can check their own vote; nothing proves the
   **tally** honest against phantom or dropped ballots. This matters because the ballot operator is
   also a board candidate: *"he built it, he counted it, he won"* is the cheapest available attack.
   The answer is procedural, not cryptographic — published eligibility roll, `count(receipts) ==
   tally`, and an **inspector of election** who is not the operator (§3).

5. **`work_attestations` RLS is the wrong template.** `20260425000300_work_attestations.sql:60` —
   `USING (auth.uid() = contributor_id OR auth.uid() IS NOT NULL)`. The second clause makes the first
   redundant: any authenticated user reads every row. Fine for a public tally; fatal for a secret
   ballot. Do not copy it.

6. **The JWT-claim eligibility pattern has never executed.** `rls_adult_swim.sql:49` gates on
   `auth.jwt() ->> 'user_age_verified'`, but: no `user_profiles` table exists (zero migrations); the
   `auth-claims` edge function is not on the mounted functions path
   (`docker-compose.core.yml:471`); and the hook is commented out (`supabase/config.toml:229`). The
   claim is never minted, so the policy denies unconditionally. It is an untested template, not a
   working pattern.

## 6. What this changes

Additions to **Open Operator Decisions** (`README.md`):

- **INSPECTOR OF ELECTION** — who is it under the current bylaws? If it is the managing agent, that
  is a conflict and likely a legal question before it is an engineering one. *Highest leverage item
  in this document.*
- **PETITION vs BALLOT** — which instrument is the AG artifact and which is the election? They cannot
  be the same component (§4).
- **SECRET BALLOT REQUIRED?** — bylaws answer determines whether individual verifiability is a
  feature or a validity risk.

Additions to **What must be BUILT** (`04:75`):

- **Ed25519 signing + per-resident key custody** (replaces the HMAC-receipt plan; §2) — **port the
  ClawZ `device-identity.ts` pattern**, do not write new crypto
- **Receipt-freeness strategy** — revoting with secret ballot count, and/or a time-limited
  verification window (§5.1, §5.2)
- **Inspector-of-election artifact** — the signed, reproducible tally an independent inspector can
  verify without the operator's key

Corrections to existing text:

- `README.md` Cross-cutting insights — strike *"One signing key underwrites both trust surfaces"* as
  applied to ballots. It holds for agent trails; it fails for a contested vote (§2).
- `04:60` — the "ballot is just another CGP payload" reduction is what carries the HMAC flaw. Ballots
  need a different trust model, not a different payload.

Reconciliation for the A2UI lane:

- `pm-ballot` is a **UI**, not an authority. Its client-side tally is a demo. The authority is
  server-side (Supabase substrate is real; every election-specific property is net-new).
- Its hardcoded `eligible-voters="47"` must come from the roll this lane owns.
- #2153's nonce work is **necessary but not sufficient** — it closes brute-force, plaintext
  publication, and correlation, and does **not** close receipt-freeness.
- **Nobody should cast a binding vote on any of it** until §2, §4, and the Legal Review Register
  clear.

## 7. What is buildable today, with zero legal exposure

The bylaws corpus. It is the thing every co-op wants, no board wants to give up, and it carries no
election-law risk — and it is the AG/lender artifact that *is* just documents.

The chain is implemented and collection-aligned (not yet smoke-tested end-to-end on a bylaws PDF;

`pdf-ingest` (PyMuPDF, `pmoves/services/pdf-ingest/app.py:277`) → `extract-worker` `/ingest`
(`worker.py:214`) → Qdrant + Meilisearch (`pmoves_chunks_qwen3`) → `hi-rag-gateway-v2`
`POST /hirag/query` (`routes/query.py:35`, hybrid vector + lexical + graph + rerank).

Citations back to source clauses are already supported: `UpsertItem` carries `doc_id` / `chunk_id` /
`section_id` (`models.py:38-49`) and query hits return the payload (`query.py:86-94`).

Two real gaps:
- **Clause-aware chunking** — the chunker is generic, so `section_id` will not auto-populate with
  "Article IV §2" unless supplied. This is what makes a citation land on a clause a resident can
  bring to counsel.
- **Authenticated resident proxy** — every Hi-RAG route is behind `require_tailscale`
  (`security.py`); there is no per-user authz and no Supabase-JWT bridge. Residents on the public
  internet cannot hit it directly.

Known trap: `HIRAG_INGEST_URL` defaults to `.../8086/ingest`, but **no `/ingest` route exists on the
v2 gateway** (`docker-compose.workers.yml:232`, `docker-compose.yml:4017`). Currently inert — no
Python reads it — but it will bite.

## 8. Proven / modeled / scaffolded

| Claim | Status |
|---|---|
| HMAC is symmetric; operator can forge ballots and tallies | **PROVEN** — `chit_security.py:91`, read the code |
| Ed25519 already exists and is reusable | **PROVEN** — `PMOVES-ClawZ/ui/src/ui/device-identity.ts` on `@noble/ed25519` 3.1.0 |
| Ed25519 is *not* wired to any signing/ballot/CHIT path | **PROVEN** — ClawZ UI only; `chit_security.py` is HMAC-only |
| No voting research anywhere in repo | **PROVEN** — Benaloh/ElectionGuard/coercion-resistance = 0 files |
| "~500 vs ~750 tokens" collusion finding | **FABRICATED** — no simulation exists |
| Vote recoverable from rev-1 receipt in ~121µs | **PROVEN** — reproduced against shipped `_hashReceipt` |
| Timing correlation recovers the vote despite a nonce | **PROVEN** — reproduced in Chromium |
| `pdf-ingest → Hi-RAG` chain works end to end | **MODELED** — code read and collection-aligned; **not yet run on a bylaws PDF** |
| Ed25519 + receipt-freeness design | **SCAFFOLDED** — named here, not built |
| Managing agent is Fordham Hill's inspector of election | **UNKNOWN** — general NY practice; **must be confirmed from the actual bylaws** |

## 9. Legal Review Register — additions

11. **SECRET-BALLOT REQUIREMENT** — do the bylaws/certificate require a secret ballot for board
    elections or recalls? Determines whether a verifiable individual receipt is a feature or a
    validity risk (§4).
12. **INSPECTOR OF ELECTION** — who holds the role; whether the managing agent currently holds it;
    whether a conflicted inspector is challengeable (§3).
13. **ED25519 BALLOT SIGNATURES** — whether asymmetric electronic signatures satisfy NY record and
    signature requirements for a valid cooperative vote; resident private-key custody obligations
    (§2).
14. **EVIDENTIARY USE OF RECEIPTS** — before any record is offered to the AG or a lender: whether
    operator-forgeable (HMAC) artifacts are admissible//impeachable, and what chain-of-custody the
    co-op must keep (§2).
15. **PETITION INSTRUMENT** — whether a signed resident petition/affidavit is the correct vehicle for
    AG submission, and what form gives it weight (§4).

---

**Three-body:** delivery = B850-CLAUDE · control = DARKXSIDE (operator decisions) + NY co-op counsel
(Register) · memory = this document + `docs/AGENT_TRAIL.md`

CHIT trail unsigned-local (no passphrase loaded on Knuckles this session) — which, per §2, is the
correct amount of trust to place in an HMAC signature anyway.

`ACK::B850-CLAUDE::BALLOT-PRIOR-ART-AND-RECONCILIATION-2026-07-16`

<!-- GRAPHITI_MARK: B850-CLAUDE::BALLOT-PRIOR-ART-RECONCILIATION::2026-07-16 -->

<!-- /graphiti -->
