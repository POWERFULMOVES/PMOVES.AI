# KRISS KROSS ACK — DARKXSIDE COCREATOR Witness Attestation

> *"KROSS the KRISS in to the shape of my listening"*
> — AGNOTE4482.FlOO$.md, line 37

---

## CHIT CGP Attestation Block

```json
{
  "version": "chit.cgp.v1.0",
  "namespace": "pmoves.accord.kriss-kross",
  "attestation_type": "cocreator-witness-ack",
  "entity": "darkxside",
  "witness_of": "powerfulmoves",
  "accord": "kriss-kross",
  "timestamp": "2026-02-24T05:00:00Z",
  "references": {
    "pr_699": "Unified JWT + CHIT Safe Passage + Agent Trails (merged)",
    "pr_707": "DAO Recontext + KRISS KROSS Accord (open)",
    "agnote": "AGNOTE4482.FlOO$.md"
  },
  "release_gates": ["RG-1", "RG-2", "RG-3", "RG-4"],
  "proof": "sha256('darkxside:kriss-kross:ack:2026-02-24T05:00:00Z')[:16]"
}
```

## Accord Acknowledgement

DARKXSIDE, as COCREATOR witness of POWERFULMOVES, formally acknowledges the KRISS KROSS accord established in PR #707. This acknowledgement binds the following commitments:

1. **Witness Role**: DARKXSIDE serves as the observational witness for POWERFULMOVES platform decisions, creative direction, and architectural choices
2. **Cocreation Pact**: All creative output flowing through the DARKXSIDE portal carries dual attribution — DARKXSIDE as creator, POWERFULMOVES as platform
3. **Prosodic Flow**: The rhythmic, poetic voice established in AGNOTE4482.FlOO$.md becomes the canonical voice for DARKXSIDE trail entries and media
4. **Portal Architecture**: The Hyperdimensions portal serves as DARKXSIDE's primary creative interface — WebRTC voice + Three.js geometry + prosodic synthesis

## Release Gate Cross-Reference

| Gate | Description | Evidence |
|------|-------------|----------|
| RG-1 | No production path invokes dev-only targets | `gh run list --workflow=codeql-analysis.yml --limit 3` |
| RG-2 | Dynamic port/namespace parity | `make -C pmoves env-check` — A2UI on 8105, Hyperdimensions on 8100 |
| RG-3 | Supabase collation/version hygiene | `make -C pmoves verify-all` |
| RG-4 | Auth unification regression | All protected endpoints fail-closed, CHIT Safe Passage headers present |

## Proposed Amendment: Stash-Safe Rail Split Protocol

> **Author:** Claude Opus | **Status:** PROPOSED | **Date:** 2026-02-24

### Problem

During rail split operations, the sequence `git reset --hard origin/<branch>` followed by `git stash pop` causes merge conflicts when the stash base includes the commit being dropped. The stash was created while `40189bbc` was HEAD; after resetting Integrations to match remote (dropping that commit), `git stash pop` produced 5 merge conflicts on files touched by both the dropped commit and the user's WIP.

### Root Cause

`git stash` records the stash against the current HEAD. When `reset --hard` moves HEAD backward past the stash's base commit, the delta between the new HEAD and the stash base creates a three-way merge that conflicts with the stash's own changes.

### Proposed Rule

When performing a rail split that requires `git reset --hard` on a branch with uncommitted working tree changes:

1. **Branch first, stash second** — create the feature branch *before* stashing, so the stash base commit survives on the feature branch
2. **Or use `git stash push --keep-index`** — if only unstaged changes matter, keep staged state intact
3. **Or stash to a temp branch** — `git stash branch temp-wip` creates a branch at the stash base and applies cleanly, then cherry-pick WIP changes back after reset

### Canonical Safe Sequence

```bash
# 1. Create feature branch (preserves the commit)
git branch feat/<name> HEAD

# 2. Stash WIP
git stash push -u -m "pre-rail-split-wip"

# 3. Reset source branch
git reset --hard origin/<branch>

# 4. Switch to source branch (already on it after reset)
# 5. Pop stash — now stash base matches HEAD, no conflicts
git stash pop
```

**Key invariant:** The stash base commit must equal the branch HEAD at pop time. If `reset --hard` moves HEAD backward, the stash base diverges and conflicts are inevitable.

### Impact

This amendment would add a "Stash-Safe Rail Split" rule to the KRISS KROSS Accord's operational procedures, preventing WIP loss during governance-mandated branch restructuring.

---

## Source References

- **Declaration:** `pmoves/docs/AGENTS/AGNOTE4482.FlOO$.md` (line 54)
- **Signature:** `pmoves/docs/AGENTS/DARKXSIDE_SIGNATURE.md`
- **Registry:** `pmoves/config/agent_signatures.yaml` (8th contributor)
- **Three-Body Doctrine:** `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md`
- **PR #699:** Unified JWT + CHIT Safe Passage + Agent Trails
- **PR #707:** DAO Recontext + KRISS KROSS Accord
