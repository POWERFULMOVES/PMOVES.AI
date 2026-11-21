# RFC: Landing Pipeline — the register is a serialization point

**Status:** PROPOSED · **Date:** 2026-11-21 · **Supersedes:** —

## Provenance

| Field | Value |
|---|---|
| Author | `4090-Claw` (AutoClaw on `laptop-4090`) |
| Signature id | `4090-claude` is the registered 4090 signature; this lane is authored by the AutoClaw instance on the same node |
| Base commit | `fd333434da` (`origin/main`, 2026-11-21 10:38 -0500) |
| Evidence gathered | local `git log origin/main`, `gh api repos/POWERFULMOVES/PMOVES.AI/{rulesets,branches/main/protection}`, PR check rollups |
| Related lanes | `chore/stale-pr-landing-train-2026-10-01` (held by CRUSH-GLM52 — see §6, **not** superseded by this RFC) |
| Related PRs | #3346, #3443, #3507 (this lane's own work, all check-clean) |
| Not signed | No CHIT trail row is claimed here; register bookkeeping belongs to the register lane (§5 option B) |

## 1. Problem

A PR that carries an `AGNOTE4482PHI.t1.md` row cannot be landed reliably.

Measured on 2026-11-21:

- **28 commits in 7 days** touch `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` on `origin/main` — roughly four per day, twice on the day of writing (08:07, 10:38).
- **77 PRs open.**
- Two PRs (#3346, #3443) were rebased, confirmed `MERGEABLE`, and flipped back to `CONFLICTING / DIRTY` inside ~40 minutes **while `origin/main` had not advanced a single commit.** A fresh rebase restored mergeability; the cycle repeats.

The flicker with an unchanged `main` is the interesting part. It is not network flake — it is the interaction of a hot file with a protection config that has no queue.

## 2. Current configuration (measured, not assumed)

Ruleset `[ main ]` (`id 10887588`, enforcement `active`) contains:

```
deletion, pull_request, copilot_code_review, non_fast_forward,
required_signatures, required_linear_history, required_status_checks
```

Branch protection on `main`:

```json
{"approvals": 1, "codeowners": true, "dismiss_stale_reviews": true}
```

Observations:

- **No `merge_queue` rule.** Nothing automates rebase → re-test → merge.
- **`required_linear_history`** forbids merge commits; squash or rebase only.
- **`dismiss_stale_reviews: true`** means every push — including the rebase you just did to resolve a conflict — **discards the approval**. Approval must therefore arrive *after* the final push, and `main` moves between those two events.
- **`codeowners: true`** adds a second review gate on the same timeline.

## 3. Root cause

The register is a single hot file that ~4 commits/day rewrite, and it is bundled into feature PRs. Every such PR therefore carries a diff against the most contended file in the repository. Compounding it:

1. hot file + bundled row → conflict on a ~4×/day cadence;
2. `dismiss_stale_reviews` → the rebase that fixes the conflict invalidates the approval;
3. no merge queue → a human must re-do 1 and 2 by hand, repeatedly;
4. `required_linear_history` → the resolver cannot simply merge.

Each rule is defensible alone. Together they make landing a register-bearing change a multi-round race, which is a policy outcome, not a discipline problem.

## 4. Options

### A. Enable the merge queue (settings change, highest leverage)

Add the `merge_queue` rule to the `[ main ]` ruleset. The queue rebases each PR onto current `main`, re-runs required checks, and merges atomically; entrants stop colliding with each other.

- **Pro:** no code change; removes the manual rebase loop; queue-generated merge groups do not invalidate approvals the way a hand-push does.
- **Con:** queue latency; a flaky required check ejects the whole queue; does not fix the hot file, only makes the collision cheaper.

### B. Fragment the register (root cause)

Replace the single `AGNOTE4482PHI.t1.md` with per-lane fragments (e.g. `pmoves/docs/AGENTS/register/<lane>.md`) and a generated index. A lane then writes its own file and never touches another lane's.

- **Pro:** removes the hot file from every diff; conflicts become structurally impossible for unrelated lanes.
- **Con:** requires a generator + a migration of 3,671 lines; readers must be pointed at the index; a bad generator becomes a new single point of failure.

### C. Path-scoped protection (narrow)

Relax `dismiss_stale_reviews` for docs-only paths, or split CODEOWNERS so a register row does not carry the same review cost as a code change.

- **Pro:** cheap; targeted at the actual friction.
- **Con:** weakens the security posture on exactly the file that governs who is allowed to do what. Recommend only if A+B still leave friction.

## 5. Recommendation

**A now, B next, C only if needed.**

A is a settings change with immediate relief and no blast radius on content. B is the actual cause and should be designed against real register traffic, not guessed — the 3,671-line migration is the bulk of the work and belongs in its own lane with its own claim.

Interim discipline, effective immediately and independent of A/B: **do not bundle register rows into feature PRs.** Land them through the register lane, or in a dedicated row-only PR that can be rebased cheaply. This RFC's own PR contains no register row, deliberately.

## 6. Relationship to existing lanes

`chore/stale-pr-landing-train-2026-10-01` is claimed by CRUSH-GLM52 and narrowed to a single PR (#3230, tailnet ACL drift gate). **This RFC does not claim, narrow, or supersede that lane.**

It is worth recording that #3230 is blocked on a credential-class 401 from the Tailscale API — the same expired/revoked key behind two open secret-scanning alerts on `main` (#16, #17). Rotating `TAILSCALE_APIKEY` is an operator action that unblocks that lane *and* clears two public alerts. That is the single highest-value action available today and is independent of everything above.

## 7. Verification

If A is adopted, verify with:

```bash
gh api repos/POWERFULMOVES/PMOVES.AI/rulesets/10887588 --jq '[.rules[].type]'   # merge_queue present
gh pr view <n> --json mergeQueueEntry                                          # queued, not blocked
```

Success criterion: a register-bearing PR lands without a manual rebase after an approval, and the MERGEABLE→CONFLICTING flip stops occurring with `main` unchanged.

## 8. Non-goals

- Not changing who may approve, or the approval count.
- Not removing `required_signatures` or `required_linear_history`.
- Not migrating the register in this RFC.
