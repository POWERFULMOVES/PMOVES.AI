# Register citation convention (AGNOTE4482)

## Why this exists

Incident 2026-10-24: PR #3408 merged with all five review threads unresolved. Three of them flagged register citations that do not check out - each pointed at a bare line number in this register (line 3410 at the time) for claims the register does not contain (kilo-code-bot roast, verdict: address before merge). Re-verified 2026-11-25 on main: the doc has had zero post-merge commits, and a case-insensitive count of multistrat on the register returns 0.

The register is append-only. **Line numbers rot as rows land** - a file:line citation into it is unverifiable by construction, and in this incident it also pointed at the wrong claims. That is the map-as-distraction failure TAC exists to prevent: the witness ledger cited as authority for claims it never witnessed.

## Rule

Cite CLAIM rows by identity, never by line number:

    AGNOTE4482[<owner>@<branch> @<ISO8601 UTC timestamp>]

Example (real row from this register):

    AGNOTE4482[PMOVES-KIMI-KNUCKLES-B850@docs/kimi-knuckles-agintz-parity @2026-09-19T02:52:47Z]

- The timestamp is the row's leading YYYY-MM-DDTHH:MM:SSZ stamp.
- The branch is the row's branch token.
- The owner is the row owner as written (parentheses allowed).

A bare line citation into the register file is rejected in review. Line numbers may appear in addition to the canonical token, never instead of it.

## Future lanes

Recommendations pointing at a lane that does not exist yet cite the **PR number** (example: #3407), not a register row. A register row witnesses what happened; it is not a promise of what will.

## Verification (deterministic, zero-LLM)

    python3 pmoves/tools/verify_register_citations.py [--register PATH] DOC...

Resolves every canonical token against the register by row match (timestamp prefix + branch token on one row) and rejects bare line citations. Exit 1 lists violations. Intended for the docs-reconcile drift scan.

## Provenance of this amendment

Row: AGNOTE4482[Z890-A0 (pmoves-docked-a0)@docs/register-citation-convention @2026-11-25T10:54:24Z] - filed in-register within this same PR via collision-checked append (node spark unreachable at filing time; on-node make re-claim to follow when it returns). Incident reviewed under operator commission 2026-11-25. Companion ops change, same day, operator-approved: main branch protection enforce_admins=true, so unresolved review threads now hard-gate all merges including admin merge-waves.
