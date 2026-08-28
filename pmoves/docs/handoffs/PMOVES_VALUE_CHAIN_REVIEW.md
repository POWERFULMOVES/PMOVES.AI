# PMOVES Value Chain — Review

_Status: REVIEW · Produced 2026-08-01 on 4090 · Baseline `origin/main` @ `a84787dfb` · Companion to [`ARCHON_MINT_CONTRACT_REVIEW.md`](./ARCHON_MINT_CONTRACT_REVIEW.md)_

> Question asked: **how do agents and operators create value and get paid?**
> Method: five parallel researchers, each required to label every claim `[BUILT]` / `[DESIGNED]` /
> `[ASPIRATIONAL]` and to verify "built" by reading implementing code rather than trusting docs.
> Two agent claims were found wrong on cross-check and corrected in place (see §7).

## 0. Answer in one paragraph

Today, no one gets paid, and the reason is not laziness — it is a set of *principled constraints* adopted
deliberately and never reconciled with each other. The chain from "an agent did work" to "a human receives
money" is broken in **six independent places**, and one of those breaks is a privacy policy that is correct
and should not be reverted to unblock the others.

Crucially (§6a, added on review): a **complete end-to-end value chain is already designed** under
`pmoves/contracts/schemas/` — work attestation with merkle roots, an attestation ledger table, attribution
records, and dual-rail settlement carrying both a Firefly transaction id and an on-chain tx hash with
deterministic idempotency keys. A 211-line recorder service exists for it. **None of it runs**, and per
§6b none of it is trustworthy yet either: the recorder's insert payload does not match its own table, no
signature is ever verified, and the ledger's RLS policy grants blanket authenticated read rather than
binding a row to its contributor.

So the accurate framing is not "the economy is unbuilt" and not "it half-works." It is: **a sound contract
design exists on paper; the implementing pieces are unjoined, undeployed, and in three specific places
unsound. Economic ownership is not yet expressible anywhere in this repo** — §6a found a better plan, not a
working mechanism. The genuine decision that gates further code is which identity model becomes the
economic anchor, and what must be true of it before anything settles against it.

## 1. The chain, and every break in it

```
agent does work
  │
  ├─ [1] METER THE COST ......................... BLOCKED BY POLICY (§2)
  │
  ├─ [2] RECORD THAT IT HAPPENED ................ two disconnected subsystems (§3)
  │        CHIT signing trail ──> voice casting only
  │        AGNOTE ACK ritual ──> plain text, no code
  │
  ├─ [3] PUBLISH AN ATTRIBUTION ................. publisher + consumer exist, all dead (§3)
  │
  ├─ [4] TRANSPORT IT ........................... interest retention, 0 consumers -> DISCARDED (§4)
  │
  ├─ [5] TURN IT INTO A SHARE ................... SEVERED — random draw, not contribution (§5)
  │
  ├─ [6] SETTLE IT .............................. dryRun default; Firefly records, never pays (§6)
  │
  └─ [7] PAY A HUMAN ............................ two rival identity models, neither running (§6, §6a)
```

**Read §6a and §6b first.** A complete designed chain (`token.work.attested.v1` → `work_attestations` →
`attribution.recorded` → `settlement.requested` → `settlement.recorded`, with dual Firefly/on-chain legs
and idempotency keys) exists under `pmoves/contracts/schemas/` and was missed by the entire fan-out — so
the task is **joining existing design**, not inventing one. But §6b records three claims about that chain
that did not survive review: nothing verifies attestation signatures, the ledger's RLS grants blanket
authenticated read rather than binding rows to contributors, and the recorder cannot write to its own
table. It is a better plan, not a working mechanism.

## 2. Break 1 — metering is blocked by a privacy policy, and the policy is right

`pmoves/tensorzero/config/tensorzero.toml:8-30` disables TensorZero observability. Confirmed live in the
gateway log (`Observability (ClickHouse): disabled`) and in the store itself — ClickHouse has **no
`tensorzero` database and zero tables**; no inference row has ever been written.

> CHIT GATE: Disabled per Cyber Defence Initiative (2026-04-25). TensorZero `observability.enabled=true`
> auto-creates ClickHouse inference tables that store full prompt text + response text with no TTL. This
> violates Data Retention Policy T0 classification (prompts are ephemeral) and creates a warrantable data
> store for user content.

Six re-enable conditions are documented (14-day TTL, prompt column dropped/masked, PII audit, CTO +
security-lead signed commit). For a co-op pilot serving elders, a warrantable prompt store is a real
liability. **This should not be reverted to unblock tokenomics.**

Supporting facts:
- **29** distinct TensorZero functions exist (`tensorzero.toml:763-1734`) — `agent_zero`, `archon_work_orders`,
  `coding_glm`, `pmoves_worker_{glm,qwen,hermes,kimi}`, etc. Granularity is **not** the problem.
- `pmoves/tools/observability/llm_observability_specialist.py:136` groups by `model_name, provider_name`
  only — `function_name` never appears in any of its three queries. Its price table (line 154-161) is
  hardcoded placeholder rates.
- `AgentMintSpec` has no field naming which TensorZero function an agent routes through.

**The gap is a join key, not granularity — and the metering must be content-free.** See §8.

## 3. Break 2+3 — two subsystems that share documentation but no code

**Subsystem A — CHIT signing (alive, but goes somewhere else).** [BUILT]
`pmoves/tools/sign_trail.py` builds a payload, HMAC-SHA256-signs it via `chit_security.sign_cgp()`
(`chit_security.py:91-99`, reused by 10+ services), and writes
`pmoves/docs/logs/graphiti_signed_latest.json`. Two limits matter economically:
- that file is **overwritten each time** — a "latest" snapshot, **not an append-only ledger**;
- the NATS leg is gated on `CHIT_SIGN_PUBLISH=1` **and** `NATS_URL`, off by default, and its only consumer
  is `voice_cast_on_sign.py` — i.e. CHIT signing currently terminates at **voice casting**, not accounting.

**Subsystem B — the AGNOTE ACK ritual (alive, but not cryptographic).** [ASPIRATIONAL]
`ACK::<AGENT>::<SCOPE>` blocks and the Active Claim Register are hand-maintained markdown. No Python or TS
file parses `ACK::` or references `AGNOTE4482PHI`. Note the vocabulary collision: "signature" means an HMAC
in subsystem A and a plain-text acknowledgment string in subsystem B.

**The promised bridge does not exist.** `chit.signed.v1` is documented as a live multi-consumer channel
reaching Consciousness (8106), Tokenism (8103) and Evo (8113). There is **zero** publisher or subscriber
code on either end; `.claude/skills/pmoves-chit-sign/SKILL.md:16` admits it is "staged but not
auto-published until pmoves-nats-mcp is wired into `.claude/mcp.json`" — and that server is not in
`.claude/mcp.json`.

**Concrete bug (fixable now):** `sign_trail.py:270` docstring says it publishes to `chit.signed.v1`; the
constant at `sign_trail.py:55` is `agent.graphiti.signed.v1`. The docstring documents a channel the code
does not use.

**`tokenism.attribution.recorded.v1` has a publisher, a second publisher, and a consumer — all dead:**

| Component | State |
|---|---|
| `pmoves/services/semantic-cache/tokenism.py` `publish_attribution()` | [BUILT], never imported or called |
| ToKenism-Multi `chit-nats-publisher.ts` `publishAttributionRecorded()` | [BUILT], never instantiated |
| `pmoves/services/publisher-discord/main.py:928-940` consumer branch | [BUILT], never fires |
| `pmoves/contracts/topics.json:143` schema | [DESIGNED] |

The repo's own audit registry already knows: `pmoves/services/graphiti/nats_subject_registry.py:68-69` tags
the subject `"defined_only"`.

## 4. Break 4 — the transport silently discards attribution

Live JetStream state on 4090:

```
TOKENISM_ATTRIBUTION | subjects tokenism.> | retention: interest | 90d | 2GB | consumers: 0 | 0 msgs ever
```

Provisioned deliberately at `pmoves/scripts/nats/init_streams.sh:82-86`. Under **interest** retention with
**zero bound consumers**, a published message is accepted and immediately discarded — no error to the
publisher. Compare the one stream that is actually wired: `AGENTZERO` uses **workqueue** with 2 durable
consumers.

For a ledger that decides who gets paid, `interest` makes attribution loss the default rather than an
error. **Change this to workqueue/limits with a durable consumer before any publisher ships**, or the first
real attribution events will vanish silently.

All 7 streams currently hold 0 messages.

## 5. Break 5 — the payout is a random number

This is the sharpest finding.

- `dirichlet-weights.ts` computes a real, fair contribution weight: `alpha = 0.1 + amount × 1.0`,
  `weight = alpha / Σalpha`, guaranteed non-zero for every contributor, 12-week decay half-life. [BUILT]
- `grotoken-model.ts` decides what each holder actually receives. Verified directly: the file has **zero
  imports**, so it cannot reference the Dirichlet module. `generateTokenAmount()` (line 89) is a Box-Muller
  transform over `Math.random()`; `distributeWeekly()` (line 111) mints exactly that amount per holder.

**Contribution is measured fairly and then ignored; distribution is Gaussian noise.**
`TOKEN_STRUCTURE_REFRESH.md:66-72` already flags this; it is true in source, not merely asserted.

Related, and also unresolved: `GroVault.votingPower = sqrt(stake) × lock-bonus` derives governance power
from **staked capital and lock duration, not work** — which the project's own decision record identifies as
violating its stated anti-plutocratic principle.

## 6. Break 6+7 — settlement records, it does not pay; and no one is payable

**Firefly-III is a bookkeeping ledger, not a payment rail.** [BUILT] and genuinely deployable
(`pmoves/compose/docker-compose.firefly.yml`, real GHCR image, wired into `make up-external`). It enforces
double-entry and can mirror to Supabase via n8n. **Nothing moves money between parties** — it records
transactions performed by other means. For Fordham even the recording side is unfinished: no seed script,
a `user_group_id` omission, an env-var mismatch (`02-wealth-community-statements.md:145-149`).

**No payout code exists anywhere.** Repo-wide grep finds no bank/ACH/Stripe/crypto payout implementation.
No Solidity contract is deployed to any network — source plus Hardhat unit tests against the default
in-memory chain only. `GROTOKEN_USD_VALUE` is a simulation parameter, not a conversion rate.

> **See §6a/§6b.** A second, better-designed identity path exists that the fan-out missed — the
> `token.work.attested.v1` contract and the `pmoves_core.work_attestations` table. It is a stronger *plan*
> than anything below, but §6b shows it is not yet a working anchor either (no signature verification, no
> ownership constraint, recorder cannot write to its own table). The section heading below therefore still
> holds for the repo as a whole.

**In the mint/registry surface, economic ownership is inexpressible.** Four identity fields, none economic:

| Field | Denotes | State |
|---|---|---|
| `creator_id` (Archon mint) | Supabase `auth.users.id` of the authenticating human | [ASPIRATIONAL] — no table, no OAuth handler, no `archon.mint.*` code |
| `creator_id` (room manifest) | free-text handle, e.g. `"darkxside"` | [BUILT] but inert — schema-typed opaque string, read by nothing |
| `owning_persona` | accountability/escalation pointer | [DESIGNED] — still a literal placeholder in committed specs |
| `team_ref` | org topology | [DESIGNED]; the live coupling is `agent-teams.yaml`, which has no owner field |
| `signature_ref` | glyph/color/voice/git `co_author` | [BUILT] as **display only**; its own header says so |

No financial primitive accepts any of them. The one money-adjacent agent, `fordham-transaction`, is scoped
`deterministic-tools-only` with `human-signoff-required` — binding decisions deliberately route to an
out-of-band human, not to any identity field.

**A deliberate invariant to respect:** `08-voter-identity-key-custody.md` concludes that **key custody must
NOT imply economic authority**, and that Mode-A (secret-ballot) identity must remain **unlinkable** to
Mode-B (attribution/wealth) identity. This is treated as a hazard to prevent, not a feature to build. Any
economic identity design must satisfy it.

## 6a. Correction — a complete designed chain exists, and the fan-out missed it

All five researchers searched `archon.mint.*` and `tokenism.*`. None searched `token.*`, and none opened
`pmoves/contracts/schemas/`. That directory contains a **coherent, end-to-end designed value chain** that is
materially better than §6 implies:

| Stage | Contract | State |
|---|---|---|
| Work attested | `pmoves/contracts/schemas/token/work.attested.v1.schema.json` | [DESIGNED] — `work_id`, `contributor` (uuid), `attestation_sig` (128-hex **format check only**, see §6b), `merkle_root`, `attested_at` |
| Recorded to ledger | `pmoves/services/token-stub/app.py` (211 LOC) | [BUILT but non-functional] — FastAPI recorder with JSONL evidence log and `TOKEN_STUB_ENABLED` kill switch, but its insert payload does not match the table (§6b) |
| Ledger table | `pmoves/supabase/migrations/20260425000300_work_attestations.sql` | [BUILT] as SQL — `pmoves_core.work_attestations`, RLS on, `chain_status` ∈ pending/confirmed/failed |
| Attribution | `pmoves/contracts/schemas/tokenism/attribution.recorded.v1.schema.json` | [DESIGNED] — `chit_id`, `address`, `action`, `amount`, `week`, `merkle_root` |
| Settlement request | `.../settlement.requested.v1.schema.json` | [DESIGNED] — `settlement_id`, `cgp_hash`, `settlement_profile`, `instructions`, `totals`, `agent_id`, `signature` |
| Settlement result | `.../settlement.recorded.v1.schema.json` (+ `.failed.`) | [DESIGNED] — `idempotency_key`, `amount`, `asset`, **`firefly_transaction_id`**, **`tx_hash`** |

**What this genuinely changes:** an end-to-end chain has been *designed*, including a dual-rail settlement
stage — `settlement.recorded.v1` carries both `firefly_transaction_id` (fiat/ledger leg) and `tx_hash`
(on-chain leg) plus a deterministic `idempotency_key`. That is a serious design, not a sketch, and it means
the task is joining and deploying existing design rather than inventing one.

**What is still true:** nothing runs.
- `token-stub` appears in **no compose file** — grep across `pmoves/docker-compose*.yml` returns nothing.
- The migration has **never been applied**: `SELECT to_regclass('pmoves_core.work_attestations')` on the live Supabase returns null.
- `token.work.attested.v1` was **not registered** in `.claude/context/nats-subjects.md` (added by this PR).

## 6b. Corrections to §6a — three claims that did not survive review

An earlier revision of §6a asserted that a payable human identity is expressible and recommended
`contributor_id` as the stronger anchor. **Codex review (#2332) refuted three claims and it was right on
all three.** Recorded here rather than silently edited, because the original claims were the sort that get
built on.

**1. The RLS policy does not bind rows to contributors.** The policy is:

```sql
FOR SELECT TO authenticated USING (auth.uid() = contributor_id OR auth.uid() IS NOT NULL)
```

For *any* authenticated user `auth.uid() IS NOT NULL` is true, so the `OR` short-circuits the whole
predicate to true — every authenticated user can read **every** attestation. It is also a `SELECT` policy
only: there is no INSERT/ownership constraint, and **no foreign key** ties `contributor_id` to
`auth.users`. So this establishes neither ownership nor a durable human anchor. It is a blanket
authenticated-read policy that merely *mentions* `contributor_id`.

**2. Nothing verifies the attestation signature.** `work.attested.v1` constrains `attestation_sig` to
`^[0-9a-fA-F]{128}$` — a **format check, not a verification**. The schema carries no signer public key and
defines no signed-message payload, and `token-stub` performs no cryptographic verification at all: grep for
`ed25519|nacl|cryptography|verify|public_key` in `pmoves/services/token-stub/app.py` returns **nothing**;
the only validator is `non_empty()`. Consequence: **any caller can attribute arbitrary work to any
contributor** by posting 128 arbitrary hex characters. Calling this an independently-verifiable Ed25519
trust model was wrong, and it must not be adopted as a payout anchor until key binding and real
verification exist.

**3. The recorder cannot write to its own ledger.** `record_to_supabase()`
(`pmoves/services/token-stub/app.py:112-119`) posts `contributor` and an extra `recorded_at`; the migration
defines `contributor_id` and has **no** `recorded_at` column. PostgREST rejects every such insert. So
applying the migration and adding the service to Compose would *not* produce a working ledger — the payload
and table must be reconciled first. `token-stub` is code that exists, not a component that works.

**Revised verdict.** The chain is designed end-to-end but **no stage of it is trustworthy or running yet**.
`contributor_id` remains the most *promising* anchor — it is the only field intended to denote a human —
but it is a **candidate, not a safe choice**, and adopting it requires, at minimum: a foreign key to
`auth.users`, an INSERT/ownership RLS policy (not the current blanket read), a defined signed-message
format with signer key binding, and actual signature verification in the recorder. Until then the honest
statement is the one §6 made about the mint surface: **economic ownership is not yet expressible anywhere
in this repo** — §6a found a better *plan*, not a working mechanism.

Note also the crypto split: `work.attested.v1` *specifies* an Ed25519-shaped signature while the live CHIT
trail uses **symmetric HMAC** with a single operator-held passphrase (§3). Asymmetric is the right target —
a contributor should be able to prove their own attribution without the operator's secret — but since
neither end verifies anything today, this is a decision to make, not a property to rely on.

## 7. Corrections made during this review

Recorded because the same failure mode is already logged in-repo — `tensorzero.toml:26-28` notes a prior
incident where "memory system fabricated verified-clean state from policy document rather than code
reality," flagged as a CHIT intrusion.

1. A researcher reported **one** TensorZero function (`agent_zero`), concluding per-agent cost attribution
   was impossible. Wrong — there are **29**; it had read `agent_zero` plus its ~30 variants. The corrected
   finding is narrower and the fix is cheaper: the join key is missing, not the granularity.
2. This review's own first pass was baselined against a branch **268 commits behind main** and reported
   several already-fixed items as gaps. Corrected in `ARCHON_MINT_CONTRACT_REVIEW.md`.
3. Two researchers could not read `PMOVES-ToKenism-Multi` / `PMOVES-Wealth` (uninitialized submodules in
   that worktree) and correctly declined to guess. Those files were verified from the main checkout instead.
5. **Codex review on #2332 refuted three §6a claims, all correctly** — see §6b. The RLS policy does not
   bind rows to contributors (the `OR auth.uid() IS NOT NULL` disjunct grants blanket authenticated read);
   nothing anywhere verifies an attestation signature, so the "Ed25519, independently verifiable" framing
   was wrong and unsafe as a payout-anchor recommendation; and the recorder's insert payload does not match
   its own table. Two of these were claims *this document* made confidently after already correcting
   itself once. Same root cause as #4 and #2: reading a schema/policy and inferring intent instead of
   evaluating what it actually does. `auth.uid() = contributor_id OR auth.uid() IS NOT NULL` reads like
   ownership and is not.
6. **The largest miss: all five researchers, and my own first synthesis, overlooked
   `pmoves/contracts/schemas/`.** Every search targeted `archon.mint.*` and `tokenism.*`; nobody searched
   `token.*` or listed the schema directory. That directory holds a complete designed value chain plus a
   built service and an unapplied migration (§6a), which falsified the headline "economic ownership is
   inexpressible." Lesson for the next pass: **enumerate the contract directory before grepping subject
   names** — a contract that exists under an unexpected namespace is invisible to a name-based search.

## 8. What to do — the one unlock, and the order

**The unlock is content-free metering.** TensorZero's observability is all-or-nothing: it stores *content*
when tokenomics needs only *counts*. A metering-only path — `{agent_name, tensorzero_function, tokens,
estimated_cost_usd, ts}`, no prompt text, no response text — satisfies the economic requirement while
tripping **none** of the six re-enable conditions, because no prompt is ever stored. That is a far smaller
and safer change than re-enabling observability.

Ordered, each independently reviewable:

1. **Fix the transport before any publisher ships.** `TOKENISM_ATTRIBUTION` → workqueue/limits + a durable
   consumer. Cheap, and prevents silent loss of the first real attribution events.
2. **Enforce the content-free invariant in a schema, not prose — OWED.** The catalog entry for
   `chit.economics.usage.v1` states the no-prompt-text invariant in Markdown only. The event-envelope path
   validates a payload only when the subject is registered in `pmoves/contracts/topics.json` with a schema,
   so as written a future publisher could add a `prompt` field and nothing would stop it. Needed:
   `pmoves/contracts/schemas/chit/economics.usage.v1.schema.json` with `"additionalProperties": false`,
   plus a `topics.json` entry. **Blocked in this session:** `pmoves/contracts/schemas/` is a
   damage-control `readOnlyPath` requiring an operator-set `KNOWN_ROAD=schema:pr:2332` in the launching
   shell; self-granting it was declined. Same applies to the `archon.mint.*` schemas.

   Then **emit** it. Add `chit.economics.usage.v1` to `nats-subjects.md` first (done), then
   publish it. (Same discipline the mint review flagged: catalog before code.)
3. **Add the join key.** `spec.economics.tensorzero_function` in `AgentMintSpec`, and the matching field in
   `agent_registry.yaml` — the landed 97-agent registry has no economic fields either, so both must change.
   Add `function_name` to the cost query's `GROUP BY`. Note the tradeoff: this yields per-*function* cost
   (agents sharing a function are indistinguishable), not per-instance. True per-agent cost needs
   TensorZero-side request tagging, which is a follow-up, not a v2 field.
4. **Join Dirichlet to distribution.** Replace the `Math.random()` draw in `distributeWeekly()` with the
   computed weights. This is the difference between a fair economy and a lottery.
5. **Decide which economic identity model wins** — the one genuine design question, not an implementation
   task. Per §6a there are **two** candidate anchors, and they are not joined:
   - `contributor_id` in `work_attestations` — intended to denote a human, and the more promising target;
   - `creator_id` / `owning_persona` in the Archon mint contract — unimplemented.

   `contributor_id` is the better *direction*, but §6b is explicit that it is not yet safe. **Do not
   deploy or settle against it until all four hold:** a foreign key to `auth.users`; an INSERT/ownership
   RLS policy replacing the current blanket authenticated-read; a defined signed-message format with
   signer key binding; and real signature verification in the recorder. Today any caller can attribute
   arbitrary work to any contributor.

   Whatever is chosen must also preserve the ballot/wealth unlinkability invariant (§6).

   **Do not apply the migration or add `token-stub` to Compose yet.** Those look like easy unblocking
   steps, but §6b shows the recorder's insert payload (`contributor`, `recorded_at`) does not match the
   table (`contributor_id`, no such column) — PostgREST would reject every insert. Reconcile the
   payload/table and add verification *first*; deploying now would produce a ledger that silently records
   nothing while appearing live.
6. **Leave settlement last.** It is correctly gated: `dryRun` default, nothing deployed, and a long
   legal-review list (dues authority, securities characterization of GroToken, NY Cooperative Corporation
   Law, e-voting validity, resident PII, telecom ToS). None of that should be unblocked by engineering.

**Do not** re-enable TensorZero observability to get cost data. **Do not** ship an attribution publisher
before step 1. **Do not** treat the ACK ritual as an economic record — it is a coordination ritual and works
well as one.

## 9. Standing note

The ritual layer — ACK signatures, the claim register, CHIT trails — is alive and genuinely used for
coordination, consistent with the operator's framing that attribution is resonance tracking rather than
blame. What is unbuilt is specifically the *economic* half: turning that ritual into a recorded, payable
attribution. The components are individually sound and the in-repo docs are honest about the gaps; the work
is joining them, plus one identity decision.

---

### Appendix — verification commands

```bash
# metering blocked; store empty
docker exec pmoves-tensorzero-clickhouse-1 clickhouse-client --query "SHOW DATABASES"
docker logs pmoves-tensorzero-gateway-1 2>&1 | grep -i observability

# 29 functions, cost query ignores them
grep -oE "^\[functions\.[a-z0-9_]+\]" pmoves/tensorzero/config/tensorzero.toml | sort -u | wc -l
sed -n '136,150p' pmoves/tools/observability/llm_observability_specialist.py

# distribution is random
grep -n "^import\|Dirichlet" PMOVES-ToKenism-Multi/integrations/contracts/grotoken-model.ts   # no output
sed -n '89,130p' PMOVES-ToKenism-Multi/integrations/contracts/grotoken-model.ts

# transport discards
docker exec pmoves-nats-1 wget -qO- "http://localhost:8222/jsz?streams=1&consumers=1&config=1"

# attribution publishers are dead
grep -rn "publish_attribution\|CHITNATSPublisher" --include=*.py --include=*.ts pmoves/ PMOVES-ToKenism-Multi/

# docstring/constant mismatch
sed -n '55p;270p' pmoves/tools/sign_trail.py
```
