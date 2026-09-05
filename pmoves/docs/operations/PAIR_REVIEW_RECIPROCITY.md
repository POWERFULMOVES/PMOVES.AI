# Pair-Review Reciprocity — Operations Guide

> Codified workflow for parallel agent-session PR review in the PMOVES.AI multi-node fleet — any harness (Claude Code, Crush, Codex CLI, Hermes, KiloCode claws, DeepSeek, or a DARKXSIDE/POWERFULMOVES operator terminal). **Four orthogonal reviewer surfaces** (peer agent session, automated reviewer, self, operator-as-Control) produce compounding quality gains per PR. Originated 2026-05-20/21 during the 5090 + Z890→5090 mirror exchange on PRs #1555/#1559/#1560/#1567 (~21 distinct improvements across 7 PRs); generalized from CLAUDE-only 2026-09-04.

## Why this matters

In PMOVES multi-node orchestration, two or more agent sessions run in parallel — each on a different physical node (Z890, 5090, 4090, SPARK, B850) or on the same node operating from a transition signature like `Z890→5090-CLAUDE` — and not always on the same harness. With same-lane collision-avoidance enforced (see `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` § Active Claim Register), the natural follow-on is **reciprocal pair-review**: each session substantively reviews the other's PRs once shipped.

Combined with the automated reviewer surface (`chatgpt-codex-connector`, CodeRabbit), this produces **four independent observation angles** per PR. The angles are not redundant — they are orthogonal:

| Reviewer | Catches | Misses |
|----------|---------|--------|
| **Peer agent session (mirror, any harness)** | Reasoning gaps, semantic-naming drift, harness-assumption drift (env vars and paths one launcher sources and another doesn't) | Contract-correctness against schemas; own-style drift |
| **Automated (Codex/CodeRabbit)** | Schema/field/type mismatches, doc-vs-code contradictions, security flags | Semantic intent, naming-convention drift, architectural choices |
| **Self (post-fix re-read)** | "What I rushed", embarrassing copy-paste residue, own-style drift | What was just-rushed-now (recency-blindness) |
| **Operator — DARKXSIDE/POWERFULMOVES (Control)** | That the task itself was wrong; confident drafts contradicting reality (PR #2942 `:8091`, PR #2938 topology challenge both came from operator pushback) | Nothing systematic — but is one body, not a scale surface; gate, don't bottleneck |

Each surface catches what the others miss. Skipping any one of them leaves systematic blind spots.

### Local/private review passes (cheap, on-node, differently-biased)

Any node can also mount a review pass that never leaves the machine. Three mechanisms, composable:

- **Local models via Ollama** (TensorZero-routed, per node) — feed the diff plus the 4-class taxonomy to a local model before or alongside the automated reviewer. **Private by construction**: after the 2026-09-04 tailnet-address leak on a public PR, a pass that never leaves the node is worth having for sensitive diffs — topology, secrets-adjacent, security lanes. Different bias, too: a small local model fails differently than Codex/CodeRabbit and occasionally surfaces what all polished reviewers normalized away.
- **`hf-agent` (`:8201`, continuous discovery)** — nominates a fit model for the diff at hand instead of guessing which local model to use.
- **Archon 0.6.0 (`:8091`, running on every node)** — an agent runtime in its own right, not just a service: REST conversation endpoints (`/api/conversations*`) and workflows (`/api/workflows*`) can drive a whole structured review pass with tool-using turns against the diff. Use it when the pass needs tools (probing endpoints, reading files), not just completion.

- **Coding plans already on the node** — the fleet's provisioned plans (MiniMax token plan, GLM/Z.AI, Kimi/Moonshot, Ollama Pro, Alibaba/Qwen, Claude Code Max, ChatGPT Business; keys land via the secrets funnel into `env.tier-llm`) can back a review pass at zero new cost. Per the coding-plan policy these run **through their CLIs/harnesses**, not raw API calls. Note the boundary: coding-plan passes leave the node to the provider (established commercial channel), unlike Ollama which never leaves — reach for the plan when you want the stronger model, reach for local when the diff is sensitive.

**Guardrail**: on-node observations are **leads, not verdicts** — every finding must be re-verified by a session before it enters the review body. Never the Control angle; the operator gate stays human.

## When to apply

| Situation | Apply? |
|-----------|--------|
| Two or more agent sessions running parallel orchestration (same or mixed harnesses) | **Yes** — default cadence |
| Lane explicitly partitioned (mirror owns X, you own Y) | **Yes** — review each other's deliverables, never each other's claim register |
| Skills PR (`.claude/skills/**`, `skills/PMOVES-skills/**`) | **Yes** — use the skills checklist in the `pmoves-pair-review` SKILL.md (frontmatter contract, description-as-trigger, anchors ratchet, live-surface probes) |
| Solo-session, no parallel peer | **No** — Codex/CodeRabbit + honest self-review + operator suffice |
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

## Lessons from the 2026-08-08 3-PR pass (Mavis harness v0)

The Mavis harness v0 slice was a 3-PR coordinated effort: PMOVES.AI
PR #2477 (writer) + PMOVES-hermes-agent PR #4 (agent) + PMOVES-pinokio
PR #1 (app launcher). All 3 cross-fork vendors of the same CGP
schema. The verifier surfaced 14 observations across the 3 PRs;
all 13 pre-merge candidates were addressed in cleanup commits; the
14th was deferred. Six concrete lessons for future review passes:

### 1. Byte-compare vendored schemas against canonical

When a PR vendors a copy of a file (e.g. a CGP schema) from a
canonical source, the reviewer should byte-compare the vendored
copy against the canonical at review time. The cross-fork
`v1.schema.json` in PMOVES-hermes-agent and PMOVES-pinokio both
survived this check (SHA-256 `427611C4...4BD3`, 10028/10028 bytes
on PMOVES-pinokio; same on PMOVES-hermes-agent after CRLF strip).
This is the highest-confidence signal that the fork is in sync;
without it, the fork could silently drift.

**How to run it:**

```bash
# From the fork's worktree, byte-compare the vendored copy against canonical
gh api repos/POWERFULMOVES/PMOVES.AI/contents/pmoves/contracts/schemas/pmoves-bootstrap/v1.schema.json \
  --jq '.content' | base64 -d > /tmp/canonical.json
diff -q /tmp/canonical.json pmoves_bootstrap/cgp_schema/v1.schema.json
sha256sum /tmp/canonical.json pmoves_bootstrap/cgp_schema/v1.schema.json
```

A `text eol=lf` line in `.gitattributes` for the vendored file
prevents the Windows-CRLF false-positive drift signal.

### 2. Schema descriptions that say "MUST" should map to `required`

The CGP schema's `super_nodes` field description said
"MUST be the empty array" but the field wasn't in the top-level
`required` array. A CGP without the field would silently pass
validation. **The fix:** treat schema `description` fields as
normative unless explicitly marked "advisory" or "optional". The
reviewer should cross-check: for every "MUST" in a description,
is the field in `required`?

### 3. Tighten `additionalProperties: false` on the well-defined leaf objects only

Top-level + the open-extension objects (`meta`, the array of
`tools`, the array of `mcps`, the dict of `routing` as a list of
future agents) should stay `additionalProperties: true` for
forward-compat. The well-defined leaf objects (`services.tailscale`,
`services.rustdesk`, `services.hostinger`, `services.cloudflare`,
the routing entries `kiloclaw` / `hermes`) should be
`additionalProperties: false` to catch typos. The PMOVES.AI
schema now does this for `services` + `routing` at the top level
(the leaf services are well-defined; routing entries are
well-defined but extensible in the future).

### 4. Normalize CRLF before byte-comparing

On Windows checkouts, the vendored copy of a JSON file often picks
up CRLF. The SHA-256 won't match between CRLF and LF copies, even
though the content is byte-equivalent. Normalize before comparing
(or add `text eol=lf` to `.gitattributes` for the vendored file).

### 5. The `key=str` trick for mixed-type sorted lists

When a loader skips malformed entries to a list (e.g. non-string
`tool_id` values), the list might end up with mixed types
(str + int + None + dict). `sorted()` on mixed types raises
`TypeError`. Use `sorted(list, key=str)` to sort by string
representation. The Hermes bridge's `LOG.info(skipped)` was
crashing on this; the fix was 1 character.

### 6. The "stub vs real" bootstrap pattern needs a deterministic stub

The PMOVES-pinokio stub bootstrap uses hard-coded
`created_at: '1970-01-01T00:00:00+00:00'` so the no-CGP fallback
is reproducible. The downside: SHA-256(canonical_json) of the
stub collides across processes. The PMOVES.AI side has the same
pattern. The fix is to make the stub's `bootstrap_id` unique
(e.g. `import uuid; uuid.uuid4()`) only if a downstream consumer
ever derives session IDs from the stub. v0 doesn't, so the
collision is theoretical; a follow-up could add uniqueness.

These six lessons are also captured in the per-slice LEARNINGS
files (e.g. `pmoves/tools/LEARNINGS/mavis-harness-v0-multi-fork_LEARNINGS.md`).
