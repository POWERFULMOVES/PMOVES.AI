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

## Amendment Queue
- _(No pending amendments)_

## Signatures
- `ACK::CODEX-GPT5::KRISS-KROSS-ACCORD::2026-02-24`
- `ACK::CLAUDE-OPUS::KRISS-KROSS-ACCORD::2026-02-24` (SIGNED)

Claude signature evidence: `pmoves/docs/AGENTS/AGNOTE4482PHI.t1.md` (`ACK::CLAUDE-OPUS::PHI-4482-T1::KRISS-KROSS-RAIL-SPLIT`).
