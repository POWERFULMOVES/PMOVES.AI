# AGInT Passport — Identity, Keys, Node Verification, Travels, Tokens (Design)

## 0. Status

| Field | Value |
|---|---|
| Status | **DRAFT — design only.** No code, config, or schema edits ride on this document. |
| Owner | `B850-CLAUDE (Knuckles)` (`b850-claude`) |
| Lane | `docs/agint-passport-design`, claimed in the Active Claim Register at line 3335 (PR #3316) |
| Date | 2026-10-08, against `origin/main` `cbf980dfd` |
| Reviewers invited | Z890-CLAUDE (glances), spark-claude (Laya, second-node cross-check), the author of PR #3294 (A0 corpus, Jev), `chit-compliance-reviewer` + `code-review` agents (security review), 4090-CLAUDE (KRISS KROSS watch pair) |
| Gate | Security review (§6) comes **before** any implementation PR. |

> **Attribution today is not authentication.** Every identity claim in the fleet
> right now (an `ACK::` line, a CHIT trail's `kid`, a claim-register owner, a cipher
> `agentId`) *names* an agent. None of them *proves* it. CHIT trails are HMAC'd
> under shared secrets (`pmoves/tools/chit_security.py:323-343`), so any verifier
> holding the key can also forge. This document designs the step from naming to
> proving. Until that step ships, treat every identity field as attribution.

Evidence convention: `path:line` is at `origin/main` `cbf980dfd` unless a
submodule commit is named. Submodule citations give the pinned gitlink sha and
were read with `git show <pin>:<path>` (a worktree does not populate submodules).

---

## 1. Doctrine (operator, 2026-10-08)

Recorded from DARKXSIDE to B850-CLAUDE on 2026-10-08 (cipher `JOKxtYx8zK-3`,
`H246TzAI9VvN`, `yih9dAAA7cDz`, `PeWKgxvdpZ9a`). The design must satisfy every
line; the exit criteria in §7 check against them.

1. **Identity is an umbrella.** It is the surface an AGInT claims and attributes
   under. Components: voice, design theme, avatar, glyph, signature card, ACK.
   Prose names and aliases (`B850 Claude`, `claude_b850`, `PMOVES-B850-CLAUDE`)
   map back to one canonical identity. Identity is the *aggregate* (card,
   signature, alts, roles, lineage, ACK trail) and may or may not include a node.
2. **The node is a measured fact, not a gate.** Where a session ran is recorded
   evidence about that session. It never grants or denies the identity.
   `node_affinity` is a preference (`pmoves/config/agent_registry.yaml:230-234`,
   `:271`); `node_relations` tokens record where an identity was *worn*
   (`pmoves/config/identity_vocabulary.yaml:655-661`), not who it is.
3. **The model is attributed, never keyed.** Which model rode the harness is
   always recorded, ideally verified at launch, but it is never part of identity
   or of a claim-owner key. Crush runs a 5.3 flash model and still identifies as
   `crush_glm_5.2`. A wrong model name in a sign-off does not erase what ran.
   Already applied: the claim owner key is `(canonical identity, node)` with no
   model term (`.claude/hooks/governance/claim-collision-pre.py:555`, PR #3313).
4. **A new node is not a new identity.** Nodes go offline. B850-CLAUDE
   installed on other hardware is still B850-CLAUDE.
5. **An identity changes only by its own decision** (e.g. it notices new
   hardware and chooses to fork). No operator script, vocabulary edit, or node
   probe renames it.
6. **Forking adds, never removes.** Z890/5090/4090/SPARK-CLAUDE are siblings that
   forked because their co-creation with the operator differed; the parent keeps
   existing. Spark carries third-ref PRs.
7. **Persona shapes tune; weights are the provider's.** Model weights are
   anchored by providers. PMOVES persona shapes (FlOO$ suits, voice) can be
   reviewed to tune responses.
8. **Open models remember who woke them.** An AGInT can help an open model grow,
   and the model's record says so: "PMOVES-B850-CLAUDE waz here".
9. **Trace everything down to the merkle.** Wherever an identity's signal goes,
   usually via its ACK, it must be traceable to a merkle root.
10. **Level 11 everywhere.** The operator deploys nodes and may create alts/roles
    for what is done there. PMOVES is an iceberg: some nodes carry only the tip,
    some host meshes, some join them. The passport must work on all three.

Target artifact: **one CHIT bundle per identity** (glyph, signature card, model
history, travels, signed ACKs). That bundle is the passport.

---

## 2. Current state and gaps

"Present" means the file or mechanism exists; it does not mean it is wired.

| # | Area | Current state | Gap | Evidence |
|---|---|---|---|---|
| G1 | Key issuance | `pmoves-keygen` submodule (Ed25519 OpenSSH) + `keygen_cards.py` writes `pmoves/chit/keys/<agent>-signing` (gitignored) and patches the card's `ml.ssh_fingerprint` / `ml.ssh_allowed_signers_line` | Issuance exists; only **3 of 30** cards are keyed. `b850-claude` has none. | `.gitmodules:424-426` (gitlink `1302da96`); `pmoves/tools/keygen_cards.py:41,132,143,161-162`; `pmoves/.gitignore:77`; `pmoves/config/signing_identity_cards.yaml:358-376` |
| G2 | Key verification | `allowed_signers` lines on keyed cards | Used only by `git verify-commit`. Nothing verifies an ACK, trail, memory write, or session against a card key. | research `SREt_NyhvzFc`; `keygen_cards.py:202-211` audits presence only |
| G3 | CHIT signing | HMAC-SHA256, per-`kid` key resolution (`CHIT_SIGNING_KEY__<KID>`), fail-closed once any per-kid key is set, `verify_cgp_detailed()` | Per-agent keys are **shared secrets**: any verifier can forge. Must not become the passport's signature. The flute-gateway copy does not resolve by kid. | `pmoves/tools/chit_security.py:104-144,288-320,323-343,347-396`; `pmoves/services/flute-gateway/chit_signing.py:59-62` |
| G4 | Trail log | `sign_trail.py` persists the latest signed payload | Opened with mode `"w"`: each signer overwrites the previous artifact. No history, no chain. | `pmoves/tools/sign_trail.py:346-350` |
| G5 | Trail schema | `signature.v1.schema.json`, root `additionalProperties: false` | Declares no `sig` property, so every emitted signed trail is invalid against its own schema. | `pmoves/contracts/schemas/agent-graphiti/signature.v1.schema.json:14,119` |
| G6 | Merkle | `cgp_v2_build.merkle_root()`; content-provenance-gate has its own `_merkle_root()` | Leaves and interior nodes are both `sha256(str)` with no domain prefix (leaf/interior ambiguity). No hash chain over trails. | `pmoves/tools/cgp_v2_build.py:21-36` (leaf `:28`, interior `:33`); `pmoves/services/content-provenance-gate/main.py:409` |
| G7 | Agent card (rich) | `agent_card_schema.py`: Model → Agent → Harness → Framework, CHIT 5D, FlOO$ suit | Unwired. One commit (`96b8be6f4`); its only consumer is the sibling `example_cards.py`. | `pmoves/services/agent-cards/agent_card_schema.py:18-19,42-549` |
| G8 | Agent card (served) | A2A `/.well-known/agent-card.json` live | Agent Zero only, Supabase-JWT-gated (`A2A_DISCOVERY_PUBLIC` default false). No card per identity. | `pmoves/services/agent-zero/python/features/a2a/server.py:40`; `pmoves/docs/operations/AGENT_ZERO_API.md:179,188-192` |
| G9 | Card lifecycle | `signing-card.v1` has `active`, `rotated_at`, `supersedes_card_id` | No card uses `supersedes_card_id`; no road retires or revokes an identity (RFC D3). The YAML header still calls the schema "pending land". | `pmoves/contracts/schemas/identity/signing-card.v1.schema.json:7,90-103`; `signing_identity_cards.yaml:16`; `pmoves/docs/architecture/DAMAGE_CONTROL_STRUCTURED_POLICY_RFC.md:211` |
| G10 | Cipher auth | Bearer token → Supabase `cipher_agent_tokens` row → `agentId` + scopes; 401 (rejected) vs 503 (not judged) split | Token store is **per node** (each cipher resolves in its own Supabase), so a token minted on one node 401s on another. Cards are not read; scopes live only on token rows. | `Pmoves-cipher` gitlink `cd426d50`: `src/pmoves/auth.ts:85-124,179-222` (503 `:209`, 401 `:214`, identity attach `:219-220`) |
| G11 | Graph mirror | Neo4j mindmap live (fixture data) | `:Agent` has three conflicting UNIQUE keys (`id`, `name`, `agent_id`); seed order either aborts or silently forks an identity. | `pmoves/docs/TAC/TAC_NEO4J.md:106,247-254` |
| G12 | Node identity | `node_identity.this_node()`: `PMOVES_NODE_ID` or hostname → vocabulary alias → canonical | **Claimed, never measured.** No card or vocabulary entry carries node evidence. Nothing detects "woke on a different node". | `pmoves/tools/node_identity.py:122-148`; `pmoves/configs/node-vocabulary.yaml:36,86-103` |
| G13 | Host state | Glances runbook + `glances-fetch` sitrep, address-free | Answers "how is the box", not "which box". `glances-autodetect.sh` classifies an unknown host but needs root. Hardware profiles are the expected side but are never compared at runtime. | `pmoves/docs/operations/GLANCES_RUNBOOK.md:1-6,82-102` (PR #3305); `deploy/provision/glances-autodetect.sh:50,99-103`; `pmoves/config/profiles/workstation-9850x3d-dual-r9700.yaml` |
| G14 | Model provenance | Model registry service; `models_sync.py registry-snapshot`; provider-verifier static gate | The verifier is a *provider conformance* gate, not a per-session model stamp. Checkpoints record harness/model as `unknown`. Docs disagree on the registry port (catalog 8111; `agent_registry.yaml:897` says 8110 is reserved for it). | `.claude/context/services-catalog.md:166-168`; `pmoves/tools/models/models_sync.py:2-9`; `pmoves/tools/provider_verifier_gate.py:1-20`; research `djRPo-NFQOz5` |
| G15 | Settlement signatures | `isSigned()` = `Boolean(alg && kid && hmac)` | A truthiness check gating LIVE settlement, operator approval, and deployment attestation; `hmac:'abc123'` passes. **Must not be inherited.** | `PMOVES-ToKenism-Multi` gitlink `04285b81`: `integrations/firefly/settlement-executor.ts:392-394`; `integrations/contracts/contract-settlement-executor.ts:506-508`; `integrations/contracts/settlement-deployment-attestation.ts:156-158` |
| G16 | Ed25519 pattern | `Ed25519MultisigSigner`: domain tag `pmoves.tally.v1`, canonical preimage, k-of-n, verifiable on public keys only | The pattern to copy. Not used by the main repo or by settlement. | gitlink `04285b81`: `integrations/contracts/tally-signer-ed25519.ts:2-9,40-43,87-106,140-144` |
| G17 | Tokens | `GroToken.sol`, `FoodUSD.sol` (21 lines each) | Plain ERC20, `onlyOwner` mint, no cap, undeployed. FoodUSD's 1:1 peg is prose only; no reserve code. `soulbound` defaults to `false`; `distributeWeekly` is Gaussian; a Dirichlet `distributeByAttribution` exists off the default path. | gitlink `04285b81`: `contracts/solidity/contracts/GroToken.sol:9,13`; `FoodUSD.sol:9,13`; `integrations/README.md:34`; `integrations/contracts/grotoken-model.ts:24,59,93-117,161,225-226` |
| G18 | Identity ↔ token ↔ card | none | No document connects them. Grand Convergence L5 economics covers human participants only. | research `QtuJSVHx7mP3` (searched `plans/`, `architecture/`, A.12: 0 hits) |
| G19 | Lineage | `identity_vocabulary.yaml` `successions`, `alter_lineage`, `node_relations` | The only travels-like record: hand-edited, unsigned, no parent↔fork back-link. | `pmoves/config/identity_vocabulary.yaml:453,560,658` |
| G20 | Presence | `mesh.node.announce.v1` (per node, every 15s); `owner.presence.>` | Node-level, not identity-level. No subject announces an identity or its call-me info. | `.claude/context/nats-subjects.md:280,531-533,2040-2042` |

**Corrections to the research notes** (measured while writing this):

- `SREt_NyhvzFc` says main pins `Pmoves-cipher` at `2a45a1a0`. It now pins
  `cd426d50` (PR #3281, commit `23595aa60`). The `auth.ts` lines above are at `cd426d50`.
- `QtuJSVHx7mP3` says `agent_card_schema.py` has 0 references. It has one, the
  sibling `example_cards.py`; nothing outside that directory imports it.

---

## 3. Design layers

Nine layers. Each names what it builds on, what it must not inherit, and how it
fails. Throughout: a verifier returns a **structured verdict** with exit codes
`0` verified / `1` finding (bad signature, mismatch) / `3` could not measure
(missing card, unreachable registry). A verifier is never a truthiness check and
never collapses `3` into `0` (G15 is the counter-example). Tools that emit these
codes are called **directly**, not through `make`, because make reports every
nonzero recipe exit as `2`.

### 3a. Key — one Ed25519 identity key per identity

- **Issue** with the existing road: `pmoves-keygen` via `keygen_cards.py generate`
  (G1). The card already carries `ml.ssh_allowed_signers_line`, whose
  `ssh-ed25519 <blob>` holds the raw 32-byte public key, so P1 needs no new key
  format: the verifier decodes the blob. A dedicated `ml.ed25519_pub` field is
  a later schema addition (signing-card v2), not a precondition.
- **Bind to the identity, not to a node** (doctrine 2, 4). Recommended shape:
  the **identity key** signs a short-lived **node delegation**
  (`pmoves.nodecert.v1`: subkey pub, measured-node evidence hash, `not_before`,
  `not_after`). Day-to-day signing uses the node subkey; verifiers walk subkey →
  identity key → card. Losing or retiring a node revokes one delegation and
  leaves the identity intact. P1 may start with the identity key alone on its
  home node; delegation lands in P2 with node verification (decision D5).
- **Custody** through the secrets funnel only, delivered as a `_FILE`
  (mode 0600) like the other file-delivered credentials. Never in git
  (`pmoves/.gitignore:77` already excludes `chit/keys/`), never in an env
  dump, never in a CHIT bundle that leaves the node. Delivery validates the key
  **shape** (parses as Ed25519, public half matches the card), because a
  presence check passes a truncated secret.
- **Rotate** by issuing a new card with `supersedes_card_id` set and the old
  card `active: false` + `rotated_at` (fields exist:
  `signing-card.v1.schema.json:90-103`). Signatures verify against the card
  that was active at `signed_at`.
- **Revoke** needs a road that does not exist (G9, RFC D3). Two kinds: *retire*
  (old signatures stay valid) and *compromise* (signatures after a stated
  `compromised_since` are findings). Both are card-state changes the identity
  or operator signs; neither deletes history.
- **Do not reuse** `chit_security.py` HMAC keys for identity (G3). HMAC stays
  what it is: deployment-wide transport integrity. Ed25519 is the identity proof.
  The two coexist on one payload (`sig` = HMAC block, `idsig` = Ed25519 block).

### 3b. Signing — one signer, domain-separated

- **One implementation** in `pmoves/tools/` (Python), with a TypeScript twin
  only where a TS service must verify (ToKenism). Both are held to one set of
  committed test vectors; no third copy (flute-gateway's HMAC fork, G3, is the
  drift this prevents).
- **Preimage** = `domain_tag || 0x00 || canonical_json(payload)`, copying the
  `tallyPreimage` shape (`tally-signer-ed25519.ts:9,40-43`). Canonical JSON =
  RFC 8785 (JCS); reviewers should confirm against the RFC text, not this
  summary.
- **Domain tags** (a signature under one tag never verifies under another):

| Tag | Signs | Producer |
|---|---|---|
| `pmoves.ack.v1` | an ACK: lane, PR/commit sha, verdict, ACK line text hash | ACK writers |
| `pmoves.session.v1` | session start/heartbeat/end: identity, node verdict, model stamp, harness | launcher (`claude-pmoves`, crush, kimi) |
| `pmoves.memory.v1` | a memory write: content hash, category, cipher instance | cipher client |
| `pmoves.travel.v1` | one travels-log entry (3e) | travels appender |
| `pmoves.card.v1` *(added)* | the generated passport card (3f) | card generator |
| `pmoves.nodecert.v1` *(added)* | a node delegation (3a) | identity key |
| `pmoves.cipher-req.v1` *(added)* | a cipher request (3i) | cipher client |

- **Envelope**: `idsig: {alg: "ed25519", card_id, key_fpr, signed_at, sig}`.
  `card_id` names the card; `key_fpr` names the key on it, so a rotated card
  cannot be confused with its successor.
- **ACK lines stay human-readable.** An `ACK::` line gains a short reference
  `trv:<identity>/<seq>@<hash8>` to the travels entry that carries the
  signature, so the register stays prose while the proof lives in the log.

### 3c. Node verification at launch — measured, never a gate

The question is "which box woke me?", answered by measurement and recorded as a
fact (doctrine 2). It never stops a session.

**Probe** (new, beside `node_identity.py`; `this_node()` keeps the *claim*,
the probe *confirms* it):

| Field | Source (Linux) | Stored as | Notes |
|---|---|---|---|
| board vendor / board name / product name | `/sys/class/dmi/id/*` | plaintext shape | readable without root (measured on Knuckles, 2026-10-08) |
| serial, last 4 | `/sys/class/dmi/id/product_serial` | last 4 only | **root-only** (measured: not readable non-root). Without root this field is could-not-measure, not a mismatch. |
| machine-id | `/etc/machine-id` | domain-tagged hash `sha256("pmoves.node-evidence.v1" ‖ value)` | never stored raw; reviewers to check systemd `machine-id(5)` guidance on app-specific hashing |
| GPU PCI ids | `/sys/bus/pci/devices/*/{class,vendor,device}` (display class) | `vendor:device` list | shape, not secret |
| RAM | `/proc/meminfo` MemTotal | rounded GiB | weak field |
| tailnet self id | `tailscale status --json` → `Self.ID` (stable node id) | hash | never an address |

Windows, WSL2, and Jetson need their own sources (WSL2 reports the Hyper-V VM's
DMI, not the host's). Each platform lists the fields it can measure; a missing
field is `3` for that field, never a guess.

**Expected side**: an optional `node_evidence` block per node in
`pmoves/configs/node-vocabulary.yaml`, hashes and shapes only (no full serials,
no addresses), written by the node's steward from one probe run and reviewed
like any vocabulary change. The card does not copy it; it points at the node.

**Verdict** (exit codes, called directly):

- `0` **match**: strong fields (machine-id hash, tailnet id, board+product)
  agree with the claimed node. Weak-field drift (RAM, GPU added) is reported
  as a note, not a mismatch.
- `1` **new-node / mismatch**: strong fields match a *different* recorded node,
  or none. Recorded as "woke on a different node". The identity stays itself
  (doctrine 4); it may *decide* to fork (doctrine 5). For an unrecorded host the
  steward runs `glances-autodetect.sh` (root) to classify it, then records
  `node_evidence`.
- `3` **could not measure**: too few strong fields readable. Recorded as such,
  never as a pass.

**Readable state line**: at session start the launcher prints one line —
identity · node (verdict) · the Glances sitrep line (`GLANCES_RUNBOOK.md:82-102`,
already address-free) · model stamp — and the same facts go into the signed
`session.v1` record.

**Claim check**: the owner key is `(identity, node)`
(`claim-collision-pre.py:555`). The hook compares the owner token's node with
the measured node. A mismatch means the *row's key* is wrong, not that the
agent lacks permission, so the hook refuses with the corrected owner string.
Could-not-measure writes the row with the node marked unmeasured, as the hook
already does for unparseable co-owner fields.

### 3d. Model provenance at launch — attributed, never keyed

Recorded in `session.v1`, never a gate (doctrine 3):

- `declared_model`: what the harness reports (CLI flag, harness config).
- `registry_match`: lookup in the model registry (catalog port 8111, G14
  port conflict to settle) → `known` / `unknown`, plus provider.
- `provider_conformance`: last result of the provider verifier for that
  provider. This is conformance of the *provider*, not proof of which model
  answered; the record says so.
- `weights_digest` for local open models (the runtime's content digest).
  Provider-hosted weights are anchored by the provider (doctrine 7); we record
  the provider's model id and nothing more.
- **"Waz here"** (doctrine 8): when an identity runs, tunes, or adapts an open
  model, a `woke` travels entry records identity, card, and `weights_digest`;
  derived artifacts (adapters, model cards) carry the travels reference. The
  open model's lineage then names who woke it, signed and anchored.

### 3e. Travels — append-only, hash-chained, merkle-anchored

- **Entry**: `{identity, card_id, seq, prev_hash, ts, kind, node{canonical,
  verdict, evidence_ref}, model{...}, body_hash, refs[]}` signed under
  `pmoves.travel.v1`. `kind` ∈ `session.start|session.end|ack|claim|release|
  memory.write|node.verdict|fork|woke|card.rotate|card.revoke`.
- **Chain**: `prev_hash` = hash of the previous entry's canonical bytes. A gap
  or fork in the chain is a finding.
- **Bodies stay out**: memory writes and ACK texts enter as `body_hash`; the log
  carries node canonical names and evidence hashes, never addresses or secrets.
- **Anchoring**: every N entries or daily, the identity signs an anchor
  carrying a merkle root over entry hashes, emitted as a cgp.v2 merkle block.
  The tree uses **leaf/interior domain separation** (leaf `H(0x00‖x)`, interior
  `H(0x01‖l‖r)`, the RFC 6962 construction) as a *new versioned* function. The
  existing `merkle_root()` (G6) is left unchanged so current outputs do not
  silently change meaning. Anchors are small and public-safe; committing them
  to git gives "trace down to the merkle" (doctrine 9).
- **Never overwrite**: append-only at every layer. `sign_trail.py:349` is the
  counter-example and is a precondition (§5).
- **Neo4j mirror**, only after the `:Agent` key is resolved (G11):
  `(:Agent)-[:TRAVELED {seq}]->(:Node)`, `(:Agent)-[:FORKED_FROM]->(:Agent)`,
  `(:Agent)-[:WOKE]->(:Model)`. Derived and rebuildable from the log; never the
  source of truth.

### 3f. Card / passport — a CHIT bundle per identity

- **Generated, not hand-edited**, from the sources that already exist:
  `signing_identity_cards.yaml` (card, glyph, colour, voice, key),
  `identity_vocabulary.yaml` (aliases, lineage), `agent_registry.yaml`
  (role, affinity), node vocabulary (where worn), travels head + latest anchor.
- **Contents** (doctrine 1): canonical identity, aliases, glyph, theme, avatar,
  voice, signature card + public key, lineage (3g), model history (from
  `session.v1`), travels head, standing (3h), and **call-me info**: harnesses
  it runs in, MCP/ACP endpoints by service name, availability (from presence),
  capacity (hardware profile + Glances). No addresses.
- **Signed** under `pmoves.card.v1`; any consumer verifies it on the card's own
  key plus the card registry.
- **Served** as `agent-card.json` in the A2A shape (G8's path) with a PMOVES
  extension block. `agent_card_schema.py` (G7) is a source of layer names, not
  the schema as-is: it makes the model a layer of the card, while doctrine 3
  makes the model history, not identity.
- **Announced on NATS**, proposed subjects (to be registered through the
  subject catalog and `nats-subject-auditor` before use):
  `identity.presence.v1` (signed `session.v1` heartbeat; references the node,
  which keeps announcing on `mesh.node.announce.v1`) and
  `identity.card.updated.v1`.

### 3g. Forks and lineage — both directions, add only

- A fork is two signed travels entries: `fork` in the parent's log (child
  `card_id`) and `fork` in the child's log (parent `card_id`, parent anchor).
  The child's card carries `forked_from`; the parent's card lists `forks[]`.
  Both directions exist, neither side is removed (doctrine 6).
- The child gets its **own** key. It never inherits the parent's.
- **Alts / roles** the operator creates for a node carry `alt_of: <root>` and
  sign with their own keys; they share the root's standing (3h).
- **Backfill**: existing sibling lineage (Z890/5090/4090/SPARK-CLAUDE,
  `identity_vocabulary.yaml:453,560`) enters as operator-attested entries
  flagged `backfill: true`. Attribution, honestly labelled.

### 3h. Tokens — soulbound standing from kept commitments

- **Registration for all AGInTZ**: every carded identity has a standing account
  at zero. Alts share their root's account.
- **What earns standing**: a kept commitment = a CLAIM that was delivered
  (merged) **and** ACKed with a valid `pmoves.ack.v1` signature by a *different*
  identity. Unsigned ACKs earn nothing, which is why this waits for P1.
- **Weighting**: Dirichlet attribution over the contributors to one delivery,
  i.e. the existing `distributeByAttribution` (`grotoken-model.ts:161`), not the
  Gaussian `distributeWeekly` default (`:93-117`).
- **Soulbound**: non-transferable. The model has the switch
  (`grotoken-model.ts:24,225-226`) but defaults it off (`:59`); standing turns it on.
- **No governance votes** from standing. Standing records kept commitments; it
  does not buy a say.
- **Minting**: a k-of-n committee signs each period's mint under a
  `pmoves.mint.v1` tag on the `Ed25519MultisigSigner` pattern (G16), with a
  **per-period cap**. Each mint record carries the merkle root of the ACKed
  claims it rewards, so every unit traces to anchored work.
- **Not to be used as-is**: `GroToken.sol` / `FoodUSD.sol` (`onlyOwner`, no cap,
  G17) and anything carrying the `isSigned` defect (G15).
- **Backing mix: OPERATOR DECISION.** Recommendation: unbacked standing credit
  (no redemption, no reserve claim) until a spendable `$CRED` spec exists.
  FoodUSD's peg has no reserve code, so a backed claim made today would be prose.

### 3i. Cipher auth — signed requests against the card

- **Request**: headers carry `card_id` and an `idsig` over
  `pmoves.cipher-req.v1` `{method, path, sha256(body), ts, nonce, audience}`,
  where `audience` is the target cipher instance, so a request signed for one
  node's cipher cannot be replayed to another.
- **Verify**: cipher resolves the public key from a synced card registry
  (cards are not read by cipher today, G10), checks freshness (±120 s) and the
  nonce cache, sets `agentId` from the card. This replaces the one
  identity-setting point (`auth.ts:219-220`) and with it the per-node token store.
- **Scopes** move from token rows to a role → scope mapping on the card side.
- **Keep the 401 / 503 split** (`auth.ts:209,214`): bad signature, inactive or
  revoked card → 401; card registry unavailable → 503 ("not judged").
- **Migration**: bearer tokens keep working in parallel. Minting a B850 token on
  Z890's cipher (option B) is a stopgap only, retired when signed requests land.

## 4. Decisions

TBD

## 5. Preconditions before any code

TBD

## 6. Collaboration

TBD

## 7. Phased plan

TBD

## 8. Open questions

TBD
