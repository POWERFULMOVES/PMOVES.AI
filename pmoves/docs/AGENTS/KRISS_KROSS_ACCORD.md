# KRISS KROSS Accord
_Last updated: 2026-02-25_

## Purpose
Collision-safe agent traversal protocol for PMOVES.AI when multiple agents operate in parallel lanes and converge on shared release branches.

This accord extends:
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md`
- `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`

## Core Rules
1. One branch, one active owner at a time unless explicit overlay handoff is recorded.
2. Every cross-agent lane transition requires:
   - Graphiti trail entry
   - claim/release update in `AGNOTE4482PHI.t1.md`
   - PR comment with next command set and blockers
3. No silent overlap on the same files without a KRISS KROSS handshake block.

## Rail Strategy (Integrations -> Hardened)
Runtime and container-affecting work must land on the Integrations rail first.

1. Runtime PRs target `PMOVES.AI-Edition-Hardened-Integrations`.
2. Hardened rail receives promoted, reviewed, and signed runtime changes only.
3. Docs/protocol-only PRs may target `PMOVES.AI-Edition-Hardened` directly.
4. If a PR mixes docs + runtime on Hardened, split scope before merge.

## KRISS KROSS Handshake
Required fields:
- `from_agent`
- `to_agent`
- `branch`
- `scope`
- `collision_risk` (`low|medium|high`)
- `fallback_mode` (`ff|overlay|three_way`)
- `graphiti_ref`
- `chit_ref` (if secret-bearing context exists)

Example:

```text
KRISS-KROSS-HANDSHAKE
from_agent=codex-gpt5
to_agent=claude-opus
branch=PMOVES.AI-Edition-Hardened
scope=dao-doc-recontext+ingestion-plan
collision_risk=medium
fallback_mode=three_way
graphiti_ref=docs/AGENT_TRAIL.md
chit_ref=pmoves/data/chit/...
```

## JOHNNY BLAZE Three-Way Fallback
Use when both agents touched the same branch window and replay is non-trivial.

1. `Fast-forward attempt`
   - If clean, merge and emit graphiti handoff.
2. `Overlay attempt`
   - Keep non-overlapping commits in sequence.
   - Resolve file ownership with explicit `Done/Left Behind/For Next Agent`.
3. `Three-way merge`
   - Merge base + lane A + lane B.
   - Preserve both agent intent where non-conflicting.
   - For conflicting strategy text, keep deterministic operator path and move alternatives to "For Next Agent".
   - Append resolution summary to `docs/AGENT_TRAIL.md`.

Merge evidence commands:

```powershell
git fetch origin --prune
git log --oneline --left-right --cherry-pick <laneA>...<laneB>
git merge <target>
git status --short
```

## Graphiti Compliance
Every completed collision resolution must emit:
- One `graphiti:` block in `docs/AGENT_TRAIL.md`
- One `REVIEW` + `RELEASE` line in `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md`
- Optional NATS event: `agent.graphiti.signed.v1`

## Dual Signature Methods
Both methods are required for convergence lanes:

1. Graphiti signature (human-readable trail + machine-parseable block).
2. CHIT attestation signature (payload reference and transport-safe proof).

A handoff is incomplete unless both are present or explicitly waived in AGNOTE.

## Stash-Safe Rail Split

> **Ratified:** 2026-02-25 | **Author:** Claude Opus | **Origin:** `pmoves/docs/AGENTS/KRISS_KROSS_ACK.md`

When performing a rail split that requires `git reset --hard` on a branch with uncommitted working tree changes, the stash base commit must equal the branch HEAD at pop time. Violating this invariant produces three-way merge conflicts.

**Canonical safe sequence:**

```bash
# 1. Create feature branch (preserves the commit)
git branch feat/<name> HEAD

# 2. Stash WIP
git stash push -u -m "pre-rail-split-wip"

# 3. Reset source branch
git reset --hard origin/<branch>

# 4. Pop stash — stash base matches HEAD, no conflicts
git stash pop
```

**Alternative approaches:**
- `git stash push --keep-index` — if only unstaged changes matter
- `git stash branch temp-wip` — creates a branch at the stash base and applies cleanly

**Key invariant:** The stash base commit must equal the branch HEAD at pop time. If `reset --hard` moves HEAD backward, the stash base diverges and conflicts are inevitable.

## Watch Pairing (Amendment, proposed 2026-08-25)

> **Status:** ratified — `claude_4090` (`4090-claude`) 2026-08-25, `claude_b850` (`b850-claude`) 2026-08-25.
> **Origin:** DARKXSIDE ✦ direction, 2026-08-25.

KRISS KROSS as written governs **not colliding** — one branch one owner, handshake
on lane transition, JOHNNY BLAZE when two lanes touched the same window. It says
nothing about who *reviews* whom; its two "review" mentions are a rail gate
(§Rail Strategy 2) and a trail record (§Graphiti Compliance), neither of which
names a reviewer.

Watch pairing is the complement. Collision avoidance keeps two agents out of each
other's way; a watch pairing deliberately puts each one inside the other's work.
The accord is the right home because the machinery already exists here: the
handshake block carries `from_agent`/`to_agent`, and §Dual Signature Methods is
already a two-party construct.

### The pairing

| registry key | signature | node |
|---|---|---|
| `claude_4090` ◆ | `4090-claude` | laptop-4090, orchestration team |
| `claude_b850` | `b850-claude` | pmoves-b850 |

Both namespaces are shown because the table previously carried one of each —
`claude_4090` is a registry key, `b850-claude` is a signature — and a reader
copying either column got a value that resolved in one file and not the other.
Registry keys are `agent_registry.yaml`'s top-level `agents:` keys; signatures
are the `signature:` field on that same entry, and are what `ACK::` lines use.

Both are Claude Code node identities working the same convergence, both have hit
session-continuity faults, and both have been opening PRs into the same areas
without seeing each other's. That last fact is the reason for the pairing, not an
incidental detail.

### What a watch obliges

1. **Pair-review before merge.** A PR from one is reviewed by the other before
   closeout, in addition to any bot review. Bot review finds defects; a paired node
   finds *the wrong thing being built*, which is the failure this convergence keeps
   producing.
2. **Report the class, not only the instance.** A recurring defect class
   ("built and never registered", "gate cannot tell absent from broken") is named as
   such, so the partner can check their own lane for it.
3. **No silent duplicate lanes.** On discovering the partner already has a PR in
   the same area, say so on both PRs rather than opening a third.
4. **Watching is not blocking.** A watch never gates a merge the operator has
   cleared. It is a second pair of eyes, not a second approval requirement.

### Session-restart review

Both parties re-read this section on session restart and record what changed since
their last pass — the before-and-after, not just the current state. A node that
cannot see what moved while it was gone will re-derive it, expensively, which is
the specific waste this pairing exists to reduce.

Restart record format, appended under §Watch Log:

```text
WATCH-RESTART
agent=<registry key>
since=<ISO date of previous pass>
partner_prs_reviewed=<#n, #n>
partner_prs_open_unreviewed=<#n>
class_findings=<short list, or none>
```

### Watch Log

- _(no entries yet — first entry belongs to whichever node restarts first)_

## Amendment Queue
- _(No pending amendments — Watch Pairing was ratified 2026-08-25.)_

  *Invariant: this queue must list every amendment that is proposed and not yet
  counter-signed. It read "(No pending amendments)" while Watch Pairing was
  awaiting a signature, so a reader using it to find unresolved governance work
  would have found none. Empty is only correct when nothing is outstanding.*

## Signatures
- `ACK::CODEX-GPT5::KRISS-KROSS-ACCORD::2026-02-24`
- `ACK::CLAUDE-OPUS::KRISS-KROSS-ACCORD::2026-02-24` (SIGNED)
- `ACK::KILOCODE-GLM::KRISS-KROSS-ACCORD::2026-07-12` (SIGNED)
- `ACK::4090-CLAUDE::KRISS-KROSS-WATCH-PAIRING::2026-08-25` (SIGNED)
- `ACK::B850-CLAUDE::KRISS-KROSS-WATCH-PAIRING::2026-08-25` (SIGNED)

Claude signature evidence: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (`ACK::CLAUDE-OPUS::PHI-4482-T1::KRISS-KROSS-RAIL-SPLIT`).

KiloCode signature evidence: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (`ACK::KILOCODE-GLM::CLAW-CONFIG` — PR #1151, first claim/release cycle 2026-03-27). KiloCode GLM ▲ operates as the third agent on the 5090 node alongside Claude ◆ and Codex ■. DARKXSIDE ✦ attests to all three agents' trail integrity per `KRISS_KROSS_ACK.md`.
