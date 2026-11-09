# PR #<N> LEARNINGS — <short title>

> **Why this file exists.** CodeRabbit/Codex review threads are a learning signal, not
> just a fix candidate. DARKXSIDE (2026-07-15): *"learnings can sometimes show more
> than the actual review comments"*. This file is the **persistent, agent-readable
> record** of what a PR taught us. The GraphQL-resolved thread disappears into
> GitHub's audit log; this file stays on disk and is readable by any agent on any
> node, cold, with no GraphQL access.
>
> **How to use this template.** Copy to `pmoves/docs/logs/pr_trim_<N>_LEARNINGS.md`,
> fill in the four buckets, link the evidence. Treat the bucket count as a
> soft check: a healthy trim has at least one entry in each of `missed-signal`
> and `fix-pattern`; `wrong-suggestion` and `already-addressed` are bonus signal
> (lots of entries here means our PR description is unclear, not that the
> bot is wrong).
>
> **Where it flows.** This file → `post-review-chit.sh` →
> `pmoves/docs/logs/claude_review_latest.cgp.json` → NATS
> `ops.pr.review.completed.v1` → cross-node PR review stream.
>
> **For local models on Spark / Knuckles reading this cold:** the worked
> example at the bottom is the most important part. It shows what a
> filled-in entry looks like. Pattern-match the worked example first,
> read the rest if you have time.

---

## PR metadata

| Field | Value |
|-------|-------|
| PR number | `<#>` |
| Branch | `<head-branch>` |
| AGNOTE CLAIM | `<link to AGNOTE4482PHI.t1.md row>` |
| AGNOTE RELEASE | `<link to AGNOTE4482PHI.t1.md row>` |
| Conformance pre-PR | `<result — e.g. 19/19 python, 10/10 components, 0 axe-core>` |
| Conformance post-trim | `<result>` |
| Reviewer surfaces | `<peer CLAUDE / CodeRabbit / Codex / self>` |
| Trim mode | `<single / batch / dry-run / report>` |
| CHIT trail sign | `<chit-stub:... or full sha256:...>` |

## Thread classification (5-class spine, extended)

This PR: **<N>** total review threads.

| Class | Count | Notes |
|-------|-------|-------|
| Legitimate (real bug/drift) | `<n>` | real fixes applied |
| Already-fixed (in HEAD) | `<n>` | verified in diff, resolved with commit ref |
| Owner-addressed (rationale accepted) | `<n>` | resolved with summary, no code change |
| Out-of-scope (separate PR) | `<n>` | noted as follow-up |
| Pre-existing (not introduced) | `<n>` | noted, resolved |

**Extension over the 5-class taxonomy:** every thread above also lands in
**one of the four LEARNINGS buckets below**. A thread can be both
"Already-fixed" *and* land in the `wrong-suggestion` bucket (we did fix it,
but the bot's reasoning was off — record that so the spec is tuned).

---

## Bucket 1 — missed-signal (what the bot saw that we missed)

> The most valuable bucket. A missed-signal entry means our process, our spec,
> or our test surface had a blind spot that an external reviewer caught. Fix
> the upstream generator / spec / test, **not just the symptom in this PR**.

### `<thread-id-or-label>` — `<one-line summary>`

- **What the bot flagged:** `<paste the suggestion verbatim>`
- **Why we missed it:** `<be honest — was it a spec gap? a test gap? a copy-paste residue?>`
- **What we changed:** `<commit ref + the actual diff>`
- **Upstream fix to prevent recurrence:** `<e.g. "added to a2ui-v0.1.md §4.2 as a MUST-NOT pattern" / "added a conformance test case in test_compose.py">`
- **Evidence:** `<screenshot path / conformance output / link>`

## Bucket 2 — fix-pattern (patterns of fixes — patch the generator, not the symptom)

> When 3+ threads across PRs fix the same kind of thing, that's a generator
> bug. Promote the fix into the template / spec / scaffolding tool so the
> next PR starts clean.

### Pattern: `<short name, e.g. "_escapeText missing on new component">`

- **First seen:** `<PR #N, commit, date>`
- **Recurrence count (this PR):** `<n>`
- **Recurrence count (last 30 days):** `<n>` — `<check pmoves/docs/logs/pr_trim_*_LEARNINGS.md history>`
- **Root cause:** `<why does this keep happening? is the component template missing this? is the conformance test not exercising it?>`
- **Generator fix:** `<e.g. "added `_escapeText` to pm-component-template.js" / "added HTML escaping assertion to conformance test">`
- **PRs that previously hit this:** `<#N1, #N2, ...>`

## Bucket 3 — wrong-suggestion (the bot's reasoning was off — tune the spec)

> The bot is sometimes confidently wrong. A `wrong-suggestion` entry is not
> "the bot is bad" — it's "our spec was ambiguous enough that the bot
> landed here". Tighten the spec, the suggestions tighten with it.

### `<thread-id-or-label>` — `<one-line summary>`

- **What the bot suggested:** `<verbatim>`
- **Why it's wrong:** `<concrete reasoning — link the spec section that contradicts>`
- **What we did instead:** `<the actual design choice + why>`
- **Spec fix to prevent recurrence:** `<e.g. "a2ui-v0.1.md §3.1 now reads '...must use data-source, not data-fetch' — was previously 'prefer data-source'">`

## Bucket 4 — already-addressed (signal that our PR description is unclear)

> If a thread says "you should do X" and X is already in the diff, the issue
> is the **PR description**, not the code. Fix the description template, not
> the code.

### `<thread-id-or-label>` — `<one-line summary>`

- **What the bot suggested:** `<verbatim>`
- **Where it already is in the diff:** `<file:line>`
- **Why the bot missed it:** `<description didn't list it / file path was hard to find / naming was confusing>`
- **Description-template fix:** `<e.g. "PR template now requires a 'pre-PR checks' section listing conformance run + axe-core + which components changed">`

---

## Comment-source triangulation (full picture, not just inline threads)

> Inline review threads are one source. The other sources often contain more
> signal than the threads themselves.

| Source | What to look for | Count this PR |
|--------|------------------|---------------|
| Inline review threads | `gh api graphql ... reviewThreads` | `<n>` |
| Issue-level comments | `gh api repos/{owner}/{repo}/issues/{PR}/comments` | `<n>` |
| Review body comments | `gh api repos/{owner}/{repo}/pulls/{PR}/reviews` (summary) | `<n>` |
| AGNOTE trail entry | The design decision this PR claims to implement | `<n>` |
| Prior conformance run | Did the "bug" the bot flagged already fail in `baseline-results.json`? | `<Y/N>` |
| DARKXSIDE pre-PR notes | Did DARKXSIDE already flag this in chat before the bot did? | `<Y/N>` |

## Conformance delta (pre-fix → post-fix)

| Surface | Pre-trim | Post-trim | Delta |
|---------|----------|-----------|-------|
| Python tests | `<n>/<m>` | `<n>/<m>` | `<±k>` |
| A2UI components conformance | `<n>/<m>` | `<n>/<m>` | `<±k>` |
| axe-core WCAG 2 AA | `<n> violations` | `<n> violations` | `<±k>` |
| Color contrast (custom) | `<n> failures` | `<n> failures` | `<±k>` |

> **Rule:** a trim that breaks conformance is wrong. Revert and re-classify.

## Evidence directory (screenshot deltas, etc.)

- Pre-trim baseline: `<path under pmoves/docs/evidence/>`
- Post-trim: `<path>`
- Visual diff: `<path if generated>`

## Trail sign

```
make -C pmoves sign-trail \
  SUMMARY="PR #<N> Trim: resolved <K> threads, captured <L> learnings, conformance <pre>→<post>"
```

---

## Worked example (so a fresh local model knows what a filled entry looks like)

> Pulled from PR #<N> — the parallel batch v0.2 implementation
> (`55c6f80e01` + `43070b3590` + `0c826336f9`) where Mavis-5090 caught its
> own `_escapeText` / `_escapeAttr` omission on `<pm-ballot>` before the
> bot could. This is a hypothetical worked example, not a real trim cycle.

### missed-signal example

**`<pm-ballot>:commit-fail-pre-commit-fail-escape` — XSS via choice label**

- **What the bot flagged (hypothetical):** "`<pm-ballot>` renders
  `choice.label` via `innerHTML` without escaping. A malicious ballot JSON
  payload with `<img src=x onerror=...>` in the label would execute script
  in the host page context."
- **Why we missed it:** The component template at
  `pmoves/web-components/README.md` had a "Use `_escapeText` for all string
  props" rule but it was in prose, not enforced by the conformance test.
  The conformance test only checked that the component *rendered* — not that
  it escaped.
- **What we changed:** Replaced `innerHTML` with `textContent` for the
  choice label in `pm-ballot.js`. Added `test_ballot_xss_payload_returns_text`
  to `pmoves/contracts/a2ui-v0.1-conformance.test.html`.
- **Upstream fix to prevent recurrence:** The conformance test now
  includes a "malicious payload → no script execution" assertion. Every
  component in the registry has this assertion.
- **Evidence:** `pmoves/docs/evidence/website-baseline-2026-07-14/conformance-10-components.png`

### fix-pattern example

**Pattern: "ARIA attrs on HOST element, not just shadow root"**

- **First seen:** PR #<N> (v0.1 first slice, `b4e2a3a7be`) — axe-core
  flagged `<pm-metric-tile role="meter">` because `aria-valuenow` was on
  the shadow root, not the host. axe-core doesn't pierce shadow DOM by
  default.
- **Recurrence count (this PR):** 1
- **Recurrence count (last 30 days):** 1 (this is the only one so far — keep
  watching)
- **Root cause:** The component template put ARIA on the inner div. Spec
  wasn't explicit that ARIA must be on the host for screen readers + axe-core.
- **Generator fix:** `a2ui-v0.1.md §6.2` now reads: *"ARIA attributes MUST
  be set on the host element (`this.setAttribute('role', ...)`), not on
  inner shadow DOM. axe-core and most screen readers do not pierce shadow
  DOM by default."*
- **PRs that previously hit this:** none yet

### wrong-suggestion example

**`<pm-toast>:use-semantic-<output>-instead-of-role=alert`**

- **What the bot suggested:** "Use `<output>` element instead of
  `role='alert'` for toast notifications."
- **Why it's wrong:** `<output>` is for calculation results, not
  notifications. The ARIA Authoring Practices Guide explicitly recommends
  `role='alert'` (or `role='status'`) for transient notifications. The
  spec section `a2ui-v0.2-ballot.md §3.4` already specifies
  `role='alert'` for `<pm-toast>`.
- **What we did instead:** Kept `role='alert'`. Added a one-line comment
  to `<pm-toast>` README explaining the choice.
- **Spec fix to prevent recurrence:** `a2ui-v0.2-ballot.md §3.4` now
  includes a "Why not `<output>`" callout to head off this suggestion.

### already-addressed example

**`<pm-ballot>:missing-CHIT-receipt-verification-on-render`**

- **What the bot suggested:** "Receipt should be verifiable on the client
  side before rendering."
- **Where it already is in the diff:** `pm-ballot.js` lines 87-95 — the
  `connectedCallback` calls `crypto.subtle.digest` to verify the receipt
  hash before render.
- **Why the bot missed it:** The PR description listed the file changes
  but didn't mention the verification step explicitly.
- **Description-template fix:** PR template now requires a
  "security-sensitive behaviors" section listing all client-side
  verification / signing / hashing in the diff.

---

## See also

- `pmoves/docs/operations/REVIEW_STYLE_2026-07-15.md` — how Mavis-5090 does
  review (the meta-doc)
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` — claim/release register
- `pmoves/contracts/a2ui-v0.1.md` — the spec the A2UI components follow
- `.claude/hooks/a2ui-crew-trail.sh` — companion hook that emits NATS trail
  on a2ui file edits
- `.claude/hooks/post-review-chit.sh` — the chit encoder that consumes this
  file's summary
