# LEARNINGS — PR #2429 (docs/persona LinkedIn profile refresh + content calendar)

> 4-bucket review taxonomy (missed-signal / fix-pattern / wrong-suggestion / already-addressed)
> 5-class pr-trim taxonomy (legit / already-fixed / owner / out-of-scope / pre-existing)
> PR: https://github.com/POWERFULMOVES/PMOVES.AI/pull/2429
> Author: 4090 node (`docs/linkedin-persona-refresh`, 2 commits, 119+/13-, 3 files)
> Reviewer: Mavis (mvs_5d5493b128b640e9aff8d45adcc77a66, orchestrator)
> Review date: 2026-08-06

## What the PR does

3 persona docs in `pmoves/docs/research/persona/`:
- `06_linkedin_profile.md` — adds Featured Item 1 (Persona room) + Featured Item 1b (PMOVES.AI) before the existing item
- `08_darkxside_persona.md` — bumps stale metrics: 91→97 agents, 50→57 submodules, 5→12 rooms, 5→6 months
- `09_linkedin_content_calendar.md` — NEW 102-line file: 7 LinkedIn artifacts × 11 resonance domains, 8-week posting schedule, ActivePieces wiring, auto-research pipeline diagram, 4 prerequisites (one already done)

## 4 review threads (all P2, all from chatgpt-codex-connector)

| # | Comment | 4-bucket | 5-class | Verdict |
|---|---------|----------|---------|---------|
| 1 | "Refresh the linked living-doc alongside this profile" — `08_darkxside_persona.md` is the upstream source for `06_linkedin_profile.md`'s featured items; the PR updates the profile but not the persona | missed-signal | legit | P2 — should add a one-liner note in `06` saying "this section mirrors `08_darkxside_persona.md`, refreshed 2026-08-06" |
| 2 | "Refresh every topology metric in Artifact 1" — 91→97 update is **speculative**; the Week 1 artifact is not yet published, so the line will still claim the old number when readers see it | legit | legit | P1 — this is the strongest concern. The PR makes forward-looking claims that will be stale the moment the persona doc gets a real refresh. The 4090 author should land the persona doc refresh in the same release, or note the version mismatch explicitly. |
| 3 | "Distinguish crawled videos from classified videos" — the calendar says "2,028 crawled (2,017 classified)" but the table cells don't show the distinction. Each row uses "X videos" without making clear which bucket | legit | legit | P2 — add a footnote to the domain table: `crawled / classified` |
| 4 | "Replace the already-completed CHIT Tour merge prerequisite" — `[x] CHIT Tour merge: PR #2076 merged` is correct but the checkbox is misleading; suggests the line should be removed or marked `[x] (merged 2026-XX-XX, no action needed)` | wrong-suggestion | already-fixed | nitpick — the `[x]` is the truth; the comment misreads the checkbox as a TODO. The line could be reworded for clarity, but it's not a fix needed for correctness. |

## 5-class review summary

| Class | Count | Notes |
|-------|-------|-------|
| legit | 3 | Comments 1, 2, 3 — real, actionable, all small P2 fixes |
| already-fixed | 1 | Comment 4 — nitpick, the truth is in the PR |
| owner | 0 | — |
| out-of-scope | 0 | — |
| pre-existing | 0 | — |

## Recommendation

**MERGEABLE after 1 small P2 fix and 1 P1 fix.**

P1 (blocker): address the speculative metric update concern. Either:
- (a) Land `08_darkxside_persona.md` refresh as a follow-up PR in the same release window (preferred — keeps the docs honest)
- (b) Add a header note in `08_darkxside_persona.md` saying "Last refreshed 2026-08-06; current agent count is 97 (was 91 in prior version)" so readers know what they're looking at

P2 (nice-to-have): add the "crawled / classified" footnote to the domain table, add the "mirrors `08_darkxside_persona.md`" note in `06`.

## Cross-cutting observation

The 4090 author's "speculative metric update" pattern is a real risk class. The persona room handoff from CRUSH says the 96→97 transition is coming from 4090 — if the persona doc gets a real refresh this week, the docs align. If not, the LinkedIn copy will say "97 agents" while the persona doc still says "91 agents." The two docs need to be merged in the same window OR a clear version note added.

## What I'm NOT recommending

- Don't block on comment 4 — it's a nitpick.
- Don't ask for a 5-class audit of every change — the P2s are small enough that the 4090 author can fix in one follow-up commit.
- Don't open a separate PR for the speculative-metric fix — keep it in this PR or do a follow-up.
