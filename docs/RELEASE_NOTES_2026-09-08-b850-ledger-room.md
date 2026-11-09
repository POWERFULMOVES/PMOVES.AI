# Release Notes — B850 Ledger Evidence Room (2026-09-08)

**PR:** #2950 · **Suit concern:** `pmoves/config/agent_signatures.yaml` (§6.4)

## What changed

- `pmoves/config/agent_signatures.yaml` gains an `alters` block under the
  existing `b850-claude` identity, declaring one alter: **`b850-ledger`**
  (glyph `⌬`, AMD Red `#DC2626`, voice `analytical`). The roster goes from 25
  identities to 26. **Zero deletions** — the `kiloclaw` block below it is
  byte-identical to its pre-change state (sha256
  `0c1e258dada9e724fca133a269352d201482211f18c0a16aa402ebd7588d391b` on both
  sides), checked explicitly because an earlier draft nearly copied a whole
  file over those records.
- New room manifest `pmoves/config/rooms/b850-ledger.room.evidence.json`,
  registered in `pmoves/config/rooms/catalog.json`.
- `pmoves/docs/ROOM_MANIFEST_CONTRACT.md` documents `hardware_requirements`
  and the semantics of `policies.publish.allowed_subjects`.

## Why the suit gate fired

Adding an alter is a suit change. An alter is a **signing identity**: it
carries a `co_author` line, a persona/voice binding, and a `room` back-ref, and
`pmoves/tools/sign_trail.py` resolves it when attributing a CHIT trail. New
signing identities are a release concern, not a background chore — which is the
standing rule the gate enforces.

## The alter name is node-qualified on purpose

`b850-ledger`, not `ledger`. `_resolve_alter_parent()` in `sign_trail.py`
returns the **first** parent declaring a matching alter and has no
duplicate-alter gate. A generic name would misattribute trails fleet-wide the
moment a second node declared it. Every existing alter follows this convention.

The room keeps that name for the same reason, and the name refers to a
**function** — the ledger/evidence alter — not to a machine. The room declares
no GPU, no node-local storage and no host-specific address, so any fleet node
satisfying `hardware_requirements` (`x86_64` or `arm64`, no GPU) can host it.

## What this does NOT do

**The room ships at `stage: rehearsal`. It activates nothing.**

- The `rehearsal → live` transition is the operator's, taken from inside the
  room via P7. Nothing in this PR performs it.
- Two of the seven CHIT activation items — `PGRST_DB_EXTRA_SEARCH_PATH` and
  `CHIT_REQUIRE_SIGNATURE` — are environment-dependent and can only be read
  where P7 actually runs. P7 is not running on this node, so they are recorded
  as unmeasured rather than asserted.
- The room's `policies.publish.allowed_subjects` is a **ceiling**, not a
  claim that anything emits today. `claude_b850` in
  `pmoves/config/agent_registry.yaml` declares `nats.publishes: []` and that
  stays true: this session publishes nothing to NATS. Declaring subjects an
  agent does not publish is the defect #2734 exists to fix, and this PR does
  not do it — see `ROOM_MANIFEST_CONTRACT.md` § "Publish policy is a ceiling,
  not a topology claim" for why the two fields are allowed to differ.

## Operator follow-up

Activation is operator-side and separate:

1. Bring up P7 on the host that will run the room.
2. Read the two ENV-dependent CHIT activation items there.
3. Transition `b850-ledger.room.evidence` from `rehearsal` to `live` from
   inside the room.
