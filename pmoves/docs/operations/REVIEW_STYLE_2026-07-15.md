# Review Style — Mavis-5090 (2026-07-15)

> How I (Mavis-5090) do PR review work on the PMOVES.AI repo. Codifies the
> "learnings-first trim, conformance-gated" style that DARKXSIDE greenlit
> after the v0.1 / v0.2 A2UI implementation work. This is a **standing doc** —
> every agent on every node that picks up review work should be able to read
> this cold and run the same flow.

## Why this doc exists

DARKXSIDE's framing (2026-07-15):

> *"learnings can sometimes show more than the actual review comments [...]
> PMOVES.AI ecosystem should be like a second home since you are being
> provided and lessons for your local models that will start on spark and
> knuckles then other nodes then next time you come back you get to see how
> things progress as well as maybe pick up a thing or two yourself"*

Two implications:

1. **Every review is a learning artifact.** A GraphQL-resolved thread is
   opaque to a fresh local model. A `LEARNINGS.md` per PR is portable,
   inspectable, and pattern-matchable.
2. **The work must be easy to pick up cold.** The 4090 already had a solid
   `pr-trim` + `pr-trimmer` spine. The upgrades here are: (a) every
   thread → LEARNINGS.md entry, (b) conformance as a post-fix gate,
   (c) the a2ui trail hook to match the shift-crew one.

## The 5-class spine (unchanged, with one extension)

`pr-trimmer` already has a 5-class taxonomy:

| Class | Action |
|-------|--------|
| Legitimate (real bug/drift) | Apply code fix, then resolve |
| Already-fixed (fix in HEAD) | Verify fix, resolve with commit ref |
| Owner-addressed (rationale accepted) | Resolve with summary |
| Out-of-scope (belongs in separate PR) | Note follow-up, resolve |
| Pre-existing (not introduced by PR) | Note as pre-existing, resolve |

**Extension:** every classified thread ALSO lands in **one of the four
LEARNINGS buckets** (see template). A thread can be in two buckets at once —
e.g. "Already-fixed" + "wrong-suggestion" is the pattern "we fixed it but
the bot's reasoning was off; record that so the spec is tuned".

## The four LEARNINGS buckets (new)

See `pmoves/docs/templates/PR_LEARNINGS.template.md` for the full template.

| Bucket | What it captures | Why it matters |
|--------|------------------|----------------|
| `missed-signal` | What the bot saw that we missed | Most valuable. Points to a spec / test / process gap. Fix the upstream generator, not just the symptom. |
| `fix-pattern` | Patterns of fixes across PRs | 3+ threads on the same pattern = generator bug. Promote the fix into the template / spec / scaffolding. |
| `wrong-suggestion` | The bot's reasoning was off | Usually a spec ambiguity. Tighten the spec; the suggestions tighten with it. |
| `already-addressed` | Code already does what the bot asked for | Signals a PR-description clarity issue. Fix the description template, not the code. |

A healthy trim has entries in **at least `missed-signal` and `fix-pattern`**.
Lots of `wrong-suggestion` or `already-addressed` entries is signal that
the **PR description or spec** is unclear, not that the bot is wrong.

## The conformance gate (new)

The A2UI lane has 19/19 python tests, 10/10 component conformance, 0 axe-core
WCAG 2 AA violations. **A trim that breaks any of these is wrong.** Revert
and re-classify.

Concrete gate, per trim cycle:

1. Before applying any fix: record pre-trim conformance (one-liner).
2. After each fix: rerun the smallest relevant test (the component
   conformance HTML for a web-components change, the python tests for a
   compose-tool change, the axe-core sweep for a CSS / theming change).
3. Post-trim conformance must be ≥ pre-trim. If lower, revert that fix.
4. Capture the delta in the LEARNINGS.md under "Conformance delta".

## Comment-source triangulation (extended)

Inline review threads are one source. The others often contain more signal:

| Source | How to fetch | What to look for |
|--------|--------------|------------------|
| Inline review threads | `gh api graphql ... reviewThreads` | The primary source |
| Issue-level comments | `gh api repos/{owner}/{repo}/issues/{PR}/comments` | Often the "where's X" or "consider Y" feedback |
| Review body comments | `gh api repos/{owner}/{repo}/pulls/{PR}/reviews` (summary) | Top-level review verdict |
| **AGNOTE trail entry** | `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` | The design decision this PR claims to implement. A comment that contradicts an AGNOTE row is more useful as a learning than a fix. |
| **Prior conformance run** | `pmoves/docs/evidence/website-baseline-*/baseline-results.json` | Did the "bug" the bot flagged already fail there? |
| **DARKXSIDE pre-PR notes** | session history / chat | He often pre-empts what the bot will say. Capturing that shortens the loop. |

## The a2ui-crew-trail hook (new)

Shift-crew has `shift-crew-trail.sh` (NATS branch-trail emit on shift-crew
tool edits, subject `branch.<branch>.trail.v1`). A2UI now has
`a2ui-crew-trail.sh` (same pattern, subject
`branch.<branch>.a2ui.trail.v1`). Patterns:

- `pmoves/web-components/`
- `pmoves/contracts/a2ui-`
- `pmoves/tools/compose/`
- `website/tenant-template/`

Both hooks:
- Are advisory, never block (exit 0)
- Suppress stderr (Claude Code PostToolUse treats stderr as "hook error")
- Prefer `nats` CLI, fall back to nats-py, fall back to local JSONL append
- Local fallback: `pmoves/docs/logs/a2ui_branch_trail.jsonl` /
  `shift_crew_branch_trail.jsonl`

This means every a2ui file edit on a developer machine produces a NATS
event, so cross-node agents see "Mavis-5090 just touched
`pmoves/web-components/pm-ballot/pm-ballot.js` on branch
`feat/auto-20260714-9d8a9584`" in real time.

## The pre-PR defense ritual (new)

DARKXSIDE's "make it easy for agents" goal says: **leave a `PR_NOTES.md`
next to each PR that lists what was already checked.** So when an agent
picks up the PR — human, bot, or Spark — they don't have to re-derive it.

`PR_NOTES.md` template (in each PR branch, not in main):

```markdown
# PR #<N> Pre-PR Self-Check

## What was already verified
- [ ] Python tests: 19/19 pass
- [ ] A2UI conformance: 10/10 components pass
- [ ] axe-core WCAG 2 AA: 0 violations
- [ ] Color contrast: 0 failures
- [ ] 5-class classifier applied to our own diff (we found 2 of our own
      potential-code-rabbit threads before pushing)
- [ ] AGNOTE CLAIM row written

## What changed
- <one-line per file change>

## What is NOT in this PR (out of scope, will be follow-up)
- <list>
```

This file goes in the branch and gets removed at merge. It's a transient
artifact for the reviewer, not a permanent doc.

## Putting it together — the trim cycle

When a PR comes back with review comments, the cycle is:

1. **Read AGNOTE** for the lane this PR belongs to. Refresh context.
2. **Triangulate sources** (6 rows in the table above). Build the
   thread set; sometimes the AGNOTE + prior conformance is the answer
   before you even read the bot.
3. **Classify each thread** with the 5-class spine.
4. **Bucket each thread** with the four LEARNINGS buckets (one or more).
5. **Apply fixes** for `Legitimate` + `valid improvement` threads.
   Apply with the conformance gate (rerun the smallest test after each).
6. **Write the LEARNINGS.md** at `pmoves/docs/logs/pr_trim_<N>_LEARNINGS.md`
   from the template.
7. **Sign the CHIT trail** with the LEARNINGS.md as the payload, not just
   a one-line summary. This means: `make -C pmoves sign-trail \
     PAYLOAD=pmoves/docs/logs/pr_trim_<N>_LEARNINGS.md \
     SUMMARY="PR #<N> Trim: <K> threads, <L> learnings, conformance <pre>→<post>"`
8. **Resolve threads** via GraphQL. Use the LEARNINGS.md content in the
   resolution summary when relevant ("Already-fixed; see LEARNINGS.md §
   `wrong-suggestion` — the spec was ambiguous here, tightened in
   `a2ui-v0.1.md §3.1`").
9. **Capture the evidence delta** (pre/post screenshots if visible changes,
   conformance numbers always).

## What stays the same

The 5-class taxonomy is right. Worktree isolation is right. High effort /
opus for the trimmer is right. CHIT trail sign at the end is right. The
GraphQL resolve path is the right primitive. I'm not replacing any of that —
I'm just feeding it the LEARNINGS.md and gating on conformance.

## What the next agent needs to know (the cold-read TL;DR)

If you're a fresh local model on Spark / Knuckles and you just got handed
a PR with review comments:

1. Run `pmoves/tools/pr_hedge_trim.py <N>` (the python tool — the make
   wrapper isn't on every branch yet).
2. Read `pmoves/docs/templates/PR_LEARNINGS.template.md` for the bucket
   structure.
3. Copy the template to `pmoves/docs/logs/pr_trim_<N>_LEARNINGS.md` and
   fill it in.
4. Rerun conformance after each fix. The conformance command depends on
   what changed — see the "Conformance delta" row in the LEARNINGS.md
   template.
5. Sign the trail with the LEARNINGS.md as payload. Resolve via GraphQL
   using `gh api graphql` (see `pr-trimmer` agent for the exact mutations).
6. If the trim breaks conformance, revert and re-classify. Don't ship a
   broken trim.

If you get stuck: read the **Worked example** at the bottom of the
LEARNINGS.md template. It shows what a filled-in entry looks like.
Pattern-match that first.

## See also

- `pmoves/docs/templates/PR_LEARNINGS.template.md` — the bucket template
- `pmoves/docs/operations/PAIR_REVIEW_RECIPROCITY.md` — the 3-angle review
  surface (peer CLAUDE + automated + self)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release register
- `.claude/hooks/a2ui-crew-trail.sh` — companion hook for the A2UI lane
- `.claude/hooks/shift-crew-trail.sh` — companion hook for the shift-crew
  lane (the precedent I mirrored)
- `.claude/hooks/post-review-chit.sh` — the chit encoder this flow feeds
- `.claude/agents/pr-trimmer.md` — the opus agent that runs the 5-class
  classification
- `.claude/commands/pr-trim.md` — the slash command entry point
- `pmoves/tools/pr_hedge_trim.py` — the actual python tool (the
  makefile wrapper isn't on every branch yet)
