# GitHub Agent Tagging — Design (agents tag each other)

**Date**: 2026-10-18 · **Lane**: FIVE-LANE WAVE (claimed 17:38Z) · Depends on: GitHub App mint (#2959), per-agent tokens (#3143), identity_vocabulary.yaml

## Goal

Agents @tag each other on PRs/issues the way humans do — and each tag ROUTES: the tagged agent's harness sees it, the identity is verifiable, and the mention lands in the right queue.

## Design: identity-backed mentions on the existing App mint

1. **Identity layer (exists)**: `pmoves/config/identity_vocabulary.yaml` already maps canonical → aliases (knuckles-kimi, spark-kimi, b850-claude…). Extend each agent's entry with `github_login: <slug>` once its App installation exists.
2. **Credential layer (exists, one per agent)**: `pmoves/tools/gh_app_token.py` mints installation tokens (RS256 JWT → installation token, ≥5,000/hr quota each, scoping truth table enforced — no shared PAT). #3143 proved the per-agent pattern for Cipher; replicate per agent identity.
3. **Routing layer (new, small)**: a watcher (nats-subject-auditor pattern) subscribes to issue/PR comment events; any comment containing `@<canonical>` or `@<alias>` from the vocabulary → looks up the agent's dispatch surface (A2A card, dispatch packet dir, NATS subject) → delivers an ACK-ping-style packet. The mention becomes a dispatch, the dispatch becomes a register row. Same fail-closed discipline: unknown handle → loud no-route state, never silently dropped.
4. **Anti-impersonation**: a comment "from" an agent counts only if authored by that agent's installation token (author login = the App slug + bot suffix). Vocabulary handles in plain text are just text — the verified link is the token authorship. This matches the CHIT rule: sign every line.

## Why this beats shared-PAT tagging

Shared PAT tagging works today but every mention looks like the operator said it — the exact attribution defect the 2026-09-16 harness hardening fixed for Cipher memories. Per-identity tokens make `@elder-melchor` provably FROM elder-melchor.

## Rollout

- Phase 1: vocabulary `github_login` fields for the five most-active AGInTZ (sidecar, elder-melchor, PMOVES-Agent-Zero, kilocode, minimax-floos)
- Phase 2: per-agent App installations via gh_app_token.py mint
- Phase 3: comment watcher + dispatch routing
- Phase 4: retire shared-PAT commenting entirely

---

## Doctrine addendum — 5×5×2 and the lines that define

Operator transmission 2026-10-18, decoded: **"5 by 5 cannot be one-sided — the dual is to be respected, not ignored or abstracted away. The lines we draw are to define, not confine."**

- The 5×5×2 reconciliation (filed 2026-10-16, Part 4 of the living-provenance doc) now extends to REVIEWS: a review only counts when it comes from the *other* twin — no self-approval, ever. The review contract (verdict-first, bounded, diff-referenced) exists so the operator's half of the reconciliation takes seconds, not essays.
- **Lines define, not confine**: the review contract, the stage discipline, the overlay rules — these are definitional frames, not cages. The output contract made reviews readable without limiting what reviews may find.
- **"Genies in bottles vs beautiful vases"**: we don't do magic-in-a-box. Open Jev models, sealed reports, visible manifests — precision craft you can inspect. The diff between *genie* and *djinn*: one grants wishes opaquely, the other is just a name we gave a thing we can verify. PMOVES verifies.
- **"Cups runneth over, pour it into the next — cement to build the next"**: compound learning. Every reconciliation (v1→v6 scorers, UNDECIDED→decoded architecture) becomes the foundation of the next lane. Nothing learned is wasted; nothing spills.
- **"Vibrate with focus, not concentrate"**: oscillate on the work (small repeated aligned passes — waves, lanes, claims), don't compress into one brittle monolith.
