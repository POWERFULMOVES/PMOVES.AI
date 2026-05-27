# Pair-Review Reciprocity — Operations Guide

> Codified workflow for parallel-CLAUDE PR review in the PMOVES.AI multi-node fleet. **Three orthogonal reviewer surfaces** (peer CLAUDE, automated reviewer, self) produce compounding quality gains per PR. Originated 2026-05-20/21 during the 5090 + Z890→5090 mirror exchange on PRs #1555/#1559/#1560/#1567 (~21 distinct improvements across 7 PRs).

## Why this matters

In PMOVES multi-node orchestration, two or more CLAUDE sessions run in parallel — each on a different physical node (Z890, 5090, 4090, SPARK, B850) or on the same node operating from a transition signature like `Z890→5090-CLAUDE`. With same-lane collision-avoidance enforced (see `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register), the natural follow-on is **reciprocal pair-review**: each CLAUDE substantively reviews the other's PRs once shipped.

Combined with the automated reviewer surface (`chatgpt-codex-connector`, CodeRabbit), this produces **three independent observation angles** per PR. The angles are not redundant — they are orthogonal:

| Reviewer | Catches | Misses |
|----------|---------|--------|
| **Peer CLAUDE (mirror)** | Reasoning gaps, semantic-naming drift, "what would I have done differently" | Contract-correctness against schemas; own-style drift |
| **Automated (Codex/CodeRabbit)** | Schema/field/type mismatches, doc-vs-code contradictions, security flags | Semantic intent, naming-convention drift, architectural choices |
| **Self (post-fix re-read)** | "What I rushed", embarrassing copy-paste residue, own-style drift | What was just-rushed-now (recency-blindness) |

Each surface catches what the others miss. Skipping any one of them leaves systematic blind spots.

## When to apply

| Situation | Apply? |
|-----------|--------|
| Two or more CLAUDE sessions running parallel orchestration | **Yes** — default cadence |
| Lane explicitly partitioned (mirror owns X, you own Y) | **Yes** — review each other's deliverables, never each other's claim register |
| Solo-session, no parallel CLAUDE | **No** — Codex/CodeRabbit + honest self-review suffice |
| Submodule-only PR (no main-tree touch) | **Optional** — high-value if mirror has domain context; skip if not |
| Hotfix / damage-control / time-critical | **Defer** — apply post-merge in retrospective review |

## The cadence (this is the "scheduled thing")

Pair-review reciprocity is **event-triggered, not time-triggered**:

```
event:   <peer CLAUDE pushes PR + opens it>
↓
trigger: <peer's automated reviewer (Codex/CodeRabbit) submits first review>
↓
action:  <you submit pair-review with substantive observations>
↓
event:   <peer addresses your observations in follow-up commit>
↓
trigger: <peer re-runs automated reviewer, then signals resolution>
↓
action:  <you verify fixes via diff, resolve threads via GraphQL>
↓
close:   <both sign AGNOTE REVIEW rows attributing the loop>
```

The cadence is "as fast as PRs arrive." Two CLAUDE sessions actively converging on the same checklist will trade 4-8 reciprocal reviews per day. One session-pair will trade 1-2. Either way, every PR gets all three angles.

## The four-class observation taxonomy

When reviewing peer's PR, scan the diff for these four classes of issue. They're the ones automated reviewers tend to miss because they require *reasoning about intent*.

### Class 1 — Reasoning gap

The author's logic skips a step that's load-bearing. Examples from prior sessions:
- `awk 'NR>1 {print $2}'` reads a column that was never validated for content shape (mirror caught this on `mcp-toolkit-bootstrap.sh` — column header could shift if Toolkit version changes output format)
- `continue 2` in a Bash `for` loop where the second-level `for` is implicit (only works in nested-loop context)
- Test docstring that *forbids* a behavior the algorithm *requires* (the `test_branch_coverage_all_state_pairs` vs `distance>=2 bypass` contradiction on PR #1567)

### Class 2 — Semantic-naming drift

A name or label suggests one meaning while the code/spec uses another. Examples:
- `severity ordering 0..3` where `0=buoyant` (best state) reads as "0 modulation intensity" (worst-case naming)
- `timestamp_iso` in a dataclass that's supposed to mirror a NATS payload using `timestamp` (Codex P1 on PR #1567)
- `SHARE_LOCAL_PORT` env var name in a Pinokio context that has no concept of "share local" (per `[[feedback_pinokio_lww_not_share_local]]`)

### Class 3 — Contract-correctness shortfall

The PR establishes or modifies a contract that another component depends on, but doesn't validate the other side. Examples:
- New NATS subject in publisher without entry in `.claude/context/nats-subjects.md`
- New env var without entry in `env.shared` + secrets-funnel
- Dataclass field rename without consumer-side migration

### Class 4 — Defense-in-depth gap

The author chose a correct primary mechanism but skipped a cheap redundancy. Examples:
- `grep -F connected` succeeds because `disconnected` happens to start with `dis-`, but `grep -F ': connected'` is unambiguous defense
- `FLOOZ_PERSONA_OVERRIDE` env knob with single-env activation — accidental dev-profile leak forces production state; double-gating with `FLOOZ_OPERATOR_DEBUG=1` is cheaper than a WARN log catching it after the fact
- Cache key with no length-limit assertion — works until an adversarial input arrives

## How to write the review

### Anatomy of a high-signal pair-review

```markdown
## Pair-review pass from <node>-CLAUDE

<one-paragraph "what works": acknowledge the strong parts.
this is not flattery — it's calibration. signals what NOT to change.>

**N observations surfaced for follow-up commit (non-blocking):**

### 1. <One-line title that names the issue>

<2-4 sentences describing the issue, with file:line refs where possible.
include WHY it matters, not just WHAT is wrong. include suggested fix if obvious.>

### 2. ...

### Nit (skip if scope creep)

<the one you almost didn't mention. mention it anyway — nits are learnings.>

## Disposition

<one paragraph stating whether you treat these as blockers or follow-up commits.
default: follow-up commits, since blocking review on a peer CLAUDE has high
coordination cost. exception: contract-correctness or security findings, which
*are* blockers.>

agent_signature (advisory unsigned-local): `ACK::<reviewing-agent>::<lane-key>-REVIEW-<date>`
```

### Required elements

1. **At least one "what works" line** — calibrates the review against rubber-stamp baseline
2. **At least one substantive observation OR explicit "no issues found, here's what I checked"** — empty pair-review = rubber-stamp = zero value
3. **`agent_signature` line** — `ACK::<reviewing-agent>::<lane-key>-REVIEW-<date>` so the AGNOTE register can attribute review work distinct from authorship
4. **`COMMENTED` review state, not `APPROVED`** — GitHub blocks self-approval for PRs from the same account (`POWERFULMOVES`), and a reciprocal pair-review from a different session is technically still the same account. `COMMENTED` carries the same substantive feedback without the GraphQL constraint.

### Anti-patterns

| Anti-pattern | Why it's wrong |
|--------------|---------------|
| "LGTM" / "Looks good!" with no substance | Collapses the loop's value to zero |
| Substring-match review without char-by-char verification | The Lane-A `claude-code: connected` vs `disconnected` trap nearly slipped a "looks fine" stamp until verification proved the dodge was real |
| Reviewing your *own* PR via mirror's CLAUDE | That's not reciprocity, that's the same author with extra steps |
| Holding review until you ship your next PR | Don't batch — review when triggered; the per-PR cycle is what produces compounding value |
| Adding scope to peer's PR | Pair-review surfaces observations; the *author* decides which to address. Don't push commits to peer's branch unless explicitly handed the lane. |

## How the author addresses pair-review

When you receive a pair-review on your PR:

1. **Wait for the automated reviewer too** if it hasn't surfaced yet — addressing peer + Codex/CodeRabbit in one combined commit is cleaner than fragmenting across multiple
2. **One commit for the response** — mirror's pattern on PR #1567 (commit `6aaaa7113b` addressed 2 Codex + 4 mirror observations in a single commit) is the canonical form
3. **Post a structured response comment** — itemize what changed for each observation; this is what the reviewer reads to decide whether to resolve threads
4. **Resolve automated-reviewer threads via GraphQL** — peer-review threads typically don't need explicit resolution since they're inline comments not formal review threads
5. **Sign the response with an AGNOTE row** — `agent_signature: ACK::<author>::<lane-key>-REVIEW-FIXES-<date>` so the register attributes both the original work and the response-to-review work

### GraphQL thread resolution

```bash
# Enumerate threads with IDs
gh api graphql -f query='
query {
  repository(owner: "POWERFULMOVES", name: "PMOVES.AI") {
    pullRequest(number: <PR>) {
      reviewThreads(first: 20) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes { author { login } path body }
          }
        }
      }
    }
  }
}'

# Resolve a thread
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {threadId: "<thread-id>"}) {
    thread { id isResolved }
  }
}'
```

## How to track via AGNOTE

Each pair-review cycle adds three rows to `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`:

| Row | When | Signed by |
|-----|------|-----------|
| `REVIEW` | When pair-review is submitted | Reviewing CLAUDE |
| `REVIEW` (author-side) | When author addresses observations | Authoring CLAUDE |
| Optional `RELEASE` if PR merges | At merge | Authoring CLAUDE |

The `lane-key` in each signature row chains them together for downstream audit (e.g., `W6-P5-FLOOZ-PHASE-B-SPEC-REVIEW`, `W6-P5-FLOOZ-PHASE-B-SPEC-REVIEW-FIXES`, `W6-P5-FLOOZ-PHASE-B-SPEC-RELEASE`).

## Skill invocation

To invoke the pair-review-reciprocity skill from a CLAUDE session:

```
Skill: pmoves-pair-review
```

The skill loads this doc and walks the workflow. Pairs naturally with `pmoves-chit-sign` for the AGNOTE signing step at the end.

## Open questions (post-codification)

1. **Multi-party pair-review (3+ nodes)** — if Z890 + 5090 + 4090 are all running, does every PR get N-1 reciprocal reviews, or do we pick one reviewer? Current heuristic: whichever node has warmest context on the affected lane goes first; other nodes review only if blocking. Validate after first 3-node parallel cycle.
2. **Cross-lane review (does mirror review my MCP-Toolkit PR if mirror is on FlOO$ lane?)** — yes by default; pair-review reciprocity is per-CLAUDE-pair, not per-lane. The four-class taxonomy applies regardless of whether the reviewer has domain context.
3. **Automated reviewer rate-limits** — CodeRabbit hit a rate-limit on PR #1567's amend cycle (per the PR comments). Pair-review reciprocity should *not* depend on CodeRabbit being available; the peer-CLAUDE angle is sufficient when automated is throttled.
4. **Cadence-tracking make target** — should there be `make -C pmoves pair-review-status` listing open PRs grouped by "awaiting my review" / "awaiting peer's response" / "ready to merge"? Defer to follow-up cycle if doc-only proves valuable for 2-3 sessions first.

## Related

- **Memory:** [[vision_pair_review_reciprocity_tightens_convergence]] — the originating insight + 2026-05-20/21 session evidence
- **Memory:** [[vision_multi_claude_claim_before_scope]] — collision-avoidance pattern that necessitates this loop
- **Memory:** [[vision_mutual_watching_protocol]] — peer-observation cadence at broader frequency
- **Memory:** [[vision_emperor_chit_humility]] — precondition for honest pair-review
- **Memory:** [[feedback_nitpicks_are_learnings]] — even minor observations are valuable signal
- **AGNOTE:** `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register — where review rows are signed
- **Skill:** `.claude/skills/pmoves-pair-review/SKILL.md` — invocable workflow that walks this doc
- **Skill:** `.claude/skills/pmoves-chit-sign/SKILL.md` — pairs with this for AGNOTE signing
