---
name: pmoves-pair-review
description: Reciprocal pair-review workflow for parallel agent-session PRs — any fleet harness (Claude Code, Crush, peer nodes) and the operator (DARKXSIDE/POWERFULMOVES). Walks the 4-class observation taxonomy (reasoning gap / semantic-naming drift / contract-correctness / defense-in-depth), the review-anatomy template, skills-PR review (SKILL.md diffs), and the AGNOTE signing flow. Pairs with pmoves-chit-sign.
disable-model-invocation: false
user-invocable: true
---

# pmoves-pair-review

Codified workflow for reciprocal PR review across parallel agent sessions in the PMOVES.AI fleet. Four orthogonal reviewer surfaces (peer agent session, automated reviewer, self, and the operator — DARKXSIDE/POWERFULMOVES as Control) produce compounding quality gains per PR. Originated 2026-05-20/21 during the 5090 + Z890→5090 mirror exchange on PRs #1555/#1559/#1560/#1567 (~21 distinct improvements across 7 PRs); generalized 2026-09-04 from CLAUDE-only to any fleet harness (Crush included) plus the operator surface.

## When to invoke

- A peer agent session has just shipped a PR and you're the reciprocal reviewer — **any harness counts**: Claude Code, Crush, Codex CLI, Hermes, a KiloCode claw, or a DARKXSIDE/POWERFULMOVES operator session
- The PR touches skills (`.claude/skills/**`, `skills/PMOVES-skills/**`) and you want the skills-review checklist below
- You're auditing whether a PR your session shipped has received its full review angles (peer + automated + self + operator)
- You're onboarding a new session (any harness) into a parallel-orchestration setup and want the cadence on the table early

**Do NOT invoke when:**
- The PR is your own (use `pmoves-chit-sign` for AGNOTE rows on your own work)
- No peer CLAUDE is active (Codex/CodeRabbit + honest self-review suffice solo)
- Hotfix / damage-control / time-critical — defer to post-merge retrospective

**Do NOT invoke when:**
- The PR is your own (use `pmoves-chit-sign` for AGNOTE rows on your own work)
- No peer session is active (Codex/CodeRabbit + honest self-review + operator suffice solo)
- Hotfix / damage-control / time-critical — defer to post-merge retrospective

## Harness notes (Crush, operator, and other non-Claude sessions)

The workflow is harness-agnostic; these specifics were learned live (SPARK, 2026-09):

- **Same mechanics**: `gh` CLI, AGNOTE rows, `make -C pmoves sign-trail`, the 4-class scan — identical from Crush or an operator terminal.
- **Self-approval**: GitHub blocks `gh pr review --request-changes`/`--approve` on same-account PRs from any harness — use `gh pr comment` for the substantive body (this skill already says COMMENTED, not APPROVED).
- **Signature**: sign with your registered identity from `pmoves/config/agent_signatures.yaml` (e.g. `crush` ◇, `claude-opus` ◆, `z890-claude` ⚙, `darkxside` ✦, `powerfulmoves` ⚡) — the `ACK::<reviewing-agent>::` slot takes the agent_id, not the harness name. An operator review signs as `dsh`/`powerfulmoves`.
- **The operator IS a review surface** (Three-Body Control): DARKXSIDE's challenge of a PR's claims mid-review is the highest-signal angle in the fleet — PR #2942's `:8091` port-map correction and PR #2938's topology challenge both came from operator pushback on an agent's confident draft. Operator review lands as PR comments and the `[ACK: control]` line in `AGNOTE4482_SIGNOFF_CHECKLIST.md`; the merge gate does not pass without it.
- **Skills load on demand**: Crush loads a skill only when invoked (`loaded_this_session 0/44` is normal). Reviewing a skills PR from Crush is an extra angle — you can verify the frontmatter `description` actually works as a **trigger** you would have fired on, not just as documentation.
- **Cross-harness reviewers are the point**: a Crush review of a Claude-authored PR (and vice versa) surfaces harness-assumption drift — paths that only exist under one launcher, env vars one harness sources and the other doesn't (the `TS_Z890` roster drop was exactly this class). The operator catches what no harness sees: that the task itself was wrong.

## Reviewing skills PRs (SKILL.md diffs)

Skills are load-bearing contracts — a wrong skill misroutes every session that loads it. Map the 4 classes onto the skills surface:

| Class | Skills-specific catch | Check |
|---|---|---|
| Contract-correctness | frontmatter `name` must equal the directory name (Crush's validator rejects colon-style names like `4090:probe`); `description` required | Tier 1 CI covers this — but read the diff yourself |
| Semantic-naming drift | `description` is a **trigger**, not a summary — it decides when a harness loads the skill; a description that describes outcomes but not WHEN to fire will never be invoked | Would YOU have loaded it on the relevant task? Would the operator's phrasing of the task have fired it? |
| Contract-correctness | every `make -C pmoves <target>` / path the SKILL.md names must exist | `python pmoves/tools/validate_command_anchors.py` — the ratchet fails PRs naming ghost targets |
| Reasoning gap | SKILL.md documenting a live surface (ports, endpoints, handler lists) that has drifted from reality | Probe the live service — PR #2942's `:8091` correction is the canonical case: docs asserted a dead port map that one live probe disproved after the operator challenged it |
| Defense-in-depth | skills shipping scripts (`scripts/`, hooks) without tests; paths relative to the wrong root | Tier 2 (hooks + skill scripts) CI must pass; check the script resolves the repo root from its own location |

Also: skills in the `skills/PMOVES-skills` package submodule follow the **submodule workflow** (land in the fork, promote the gitlink) — pair-review applies there identically, plus the usual gitlink-integrity check.

## How to run

This is a workflow skill (no script). The full operations guide is at `pmoves/docs/operations/PAIR_REVIEW_RECIPROCITY.md`. The condensed flow:

### 1. Identify the PR + wait for automated reviewer

```bash
# List open PRs awaiting your reciprocal review
gh pr list --repo POWERFULMOVES/PMOVES.AI --state open --author '@me' --limit 10  # your PRs (sanity check what mirror should review)
gh pr list --repo POWERFULMOVES/PMOVES.AI --state open --json number,title,author,reviews \
  --jq '.[] | select(.author.login != "<your-handle>") | "\(.number) \(.title) — reviews: \([.reviews[].author.login] | unique | join(\",\"))"'

# Wait for Codex/CodeRabbit to submit first if it hasn't — automated reviewer
# observations are independent of peer-CLAUDE angle; let them surface before your review
```

### 2. Scan the diff for the four observation classes

| Class | Catch | Example |
|-------|-------|---------|
| **Reasoning gap** | Logic skips load-bearing step | `awk 'NR>1 {print $2}'` reads unvalidated column shape |
| **Semantic-naming drift** | Name/label suggests one meaning, code/spec uses another | `timestamp_iso` field on a payload whose canonical spec uses `timestamp` |
| **Contract-correctness shortfall** | PR establishes contract but doesn't validate other side | New NATS subject without entry in `nats-subjects.md` |
| **Defense-in-depth gap** | Correct primary mechanism, skipped cheap redundancy | `grep -F connected` works only because `disconnected` happens to start with `dis-` |

### 3. Write the review

Use this template (per `PAIR_REVIEW_RECIPROCITY.md` § Anatomy of a high-signal pair-review):

```markdown
## Pair-review pass from <node>-CLAUDE

<one-paragraph "what works": acknowledge the strong parts.
this is not flattery — it's calibration. signals what NOT to change.>

**N observations surfaced for follow-up commit (non-blocking):**

### 1. <One-line title that names the issue>

<2-4 sentences: WHY it matters, file:line refs, suggested fix if obvious.>

### 2. ...

### Nit (skip if scope creep)

<the one you almost didn't mention. mention it anyway — nits are learnings.>

## Disposition

<treat as follow-up commits by default. exception: contract-correctness or
security findings, which are blockers.>

agent_signature (advisory unsigned-local): `ACK::<reviewing-agent>::<lane-key>-REVIEW-<date>`
```

### 4. Submit as COMMENTED, not APPROVED

```bash
# GitHub blocks self-approval for same-account PRs; COMMENTED carries the same
# substantive feedback without the GraphQL constraint.
gh pr review <PR-number> --comment --body "$(cat review.md)"
```

### 5. Sign AGNOTE REVIEW row

```bash
# After submitting the review, append a REVIEW row to AGNOTE4482PHI.t1.md
# signed `ACK::<your-agent>::<lane-key>-REVIEW-<date>`. Then:
make -C pmoves sign-trail SUMMARY="Pair-review pass on PR #<N>: <N obs> + <N nit> applied to <lane>"
```

### 6. Verify peer addresses observations

When the peer pushes a follow-up commit responding to your review:

```bash
# Check the diff matches what you flagged
gh pr diff <PR-number> --repo POWERFULMOVES/PMOVES.AI | less

# Resolve threads if you opened any (inline comments typically don't need explicit resolution)
gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "<thread-id>"}) { thread { id isResolved } } }'
```

### 7. The 6 lessons from the 2026-08-08 3-PR pass

Codified from the Mavis harness v0 review pass (PMOVES.AI #2477 +
PMOVES-hermes-agent #4 + PMOVES-pinokio #1, all cross-fork
consumers of the same CGP schema). The full discussion is in
`pmoves/docs/operations/PAIR_REVIEW_RECIPROCITY.md` § "Lessons
from the 2026-08-08 3-PR pass"; the short version:

1. **Byte-compare vendored schemas against canonical** (SHA-256 +
   `diff -q`). Use `text eol=lf` in `.gitattributes` for vendored
   JSON to avoid Windows-CRLF false-positives.
2. **Schema descriptions that say "MUST" should map to `required`**.
   Cross-check: for every "MUST" in a description, is the field in
   the `required` array?
3. **Tighten `additionalProperties: false` on well-defined leaf
   objects only.** Top-level + open-extension objects stay `true`
   for forward-compat.
4. **Normalize CRLF before byte-comparing.** Or add `.gitattributes`.
5. **`key=str` for mixed-type sorted lists.** A loader that skips
   malformed entries to a list can leave mixed types; `sorted()`
   on `str + int + None + dict` raises TypeError.
6. **The "stub vs real" bootstrap pattern needs a deterministic
   stub.** Hard-coded `created_at` in the no-CGP fallback means
   SHA-256(canonical_json) collides across processes. Add
   uniqueness only if a downstream consumer derives session IDs
   from the stub.


## Anti-patterns

- ❌ "LGTM" / "Looks good!" with no substance — collapses loop's value to zero
- ❌ Substring-match review without char-by-char verification — the `connected` vs `disconnected` trap
- ❌ Reviewing your own PR via mirror's CLAUDE — same author with extra steps
- ❌ Batching reviews until you ship your next PR — per-PR cycle is what produces compounding value
- ❌ Pushing commits to peer's branch — pair-review surfaces observations; the *author* decides

## Output expectations

After invoking this skill on a peer's PR, the artifacts produced are:

1. One `COMMENTED` review on the PR with the structured template above
2. One AGNOTE REVIEW row in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
3. One signed trail entry via `make -C pmoves sign-trail`
4. Optionally: one acknowledgement comment when the peer addresses observations

## Citations

- `pmoves/docs/operations/PAIR_REVIEW_RECIPROCITY.md` — full operations guide
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — Active Claim Register (review rows landed here)
- `.claude/skills/pmoves-chit-sign/SKILL.md` — companion skill for AGNOTE signing
- Memory: `vision_pair_review_reciprocity_tightens_convergence.md` — originating insight
- Memory: `vision_multi_claude_claim_before_scope.md` — collision-avoidance pattern (precondition)
- Memory: `feedback_nitpicks_are_learnings.md` — even minor observations are valuable signal
