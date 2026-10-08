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

TBD

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
