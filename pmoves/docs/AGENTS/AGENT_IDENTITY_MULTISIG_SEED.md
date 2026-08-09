# Agent Identity + Multi-Sig Quorum — spec seed (2026-08-09)

Operator anchor: 5090 session message 2026-08-09 18:03 EDT (paraphrased by
5090-CLAUDE — not a verbatim quote; the operator's words are theirs to state),
refining the signing-lane sweep's canonicalization proposal (register entry
`5090-CLAUDE::SIGNING-LANE-SWEEP::2026-08-09`). Paraphrase: the variants need
a pydantic model — they are model alts — and this is a two-parter that
exercises the quorum mechanism, since PMOVES agents will multi-sig on work.

**Canonical references this direction points into** (canon is not an island):
- `pmoves/docs/PMOVESCHIT/THREE_BODY_DOCTRINE.md` — **the root**: Human, AI,
  and System as a classical three-body problem stabilized by CHIT geometry;
  without stabilization one body gets ejected. The register's role split is a
  derived application. (This doc was orphaned from every modern discovery
  surface until 2026-08-09 — which is exactly how visiting agents' three-body
  framing drifted.)
- `pmoves/docs/AGENTS/AGNOTE4482.md` §Village Rule — no agent operates alone;
  execution / control-review / memory-security bodies — and the Three-Body
  Pattern blocks used throughout the register.
- `pmoves/docs/AGENTS/KRISS_KROSS_ACCORD.md` — the collision-safe traversal
  protocol (one branch one owner, handshake blocks, JOHNNY BLAZE three-way
  fallback): the written form of bodies-move-freely-without-collision.
- `pmoves/docs/AGENTS/AI_GRAPHITI_PROTOCOL.md` — trail/attribution substrate
  the accord extends.
- `pmoves/config/agent_signatures.yaml` (schema 1.1.0) — `alters` already
  first-class; `pmoves/docs/AGENTS/AGNOTE4482.md` §signing-card /
  `CANONICAL_NAMES.md` decision log + `audit_naming_drift.py` — the existing
  canonical-naming machinery this seed plugs into rather than replaces.

The drift survey's ACK variants (`4090-CLAUDE`/`4090-claude`,
`Mavis`/`Mavis-5090`, `SPARK-KIMI`/`KIMI-SPARK`) are **not sloppiness to
collapse — they are model alts**: distinct instruments of one agent lineage.
`pmoves/config/agent_signatures.yaml` (schema 1.1.0) already models `alters`
as first-class. The fix is typed resolution, not flattening.

## Part 1 — pydantic identity model

A `pmoves` package module (candidate: `pmoves/tools/agent_identity.py`) with:

- `AgentIdentity(BaseModel)`: `agent_id` (canonical), `display_name`, `glyph`,
  `color`, `co_author`, `alters: list[AlterIdentity]`, optional
  `node_bindings` (which nodes this lineage instantiates on).
- `AlterIdentity(BaseModel)`: `alt_id`, `mode`/`context`, same visual fields —
  loaded from the existing `alters` blocks.
- `resolve_ack(ack: str) -> Resolution`: parses `ACK::<id>::<SCOPE>` and maps
  any registered id **or alt (case/order tolerant)** to its canonical lineage.
  Unregistered ids resolve to `UNKNOWN` with a suggestion — warn, never
  rewrite history. `make naming-drift-check` consumes this instead of raw grep.
- Validation of the YAML registry itself at load (the pydantic ask): glyph
  uniqueness, WCAG fields present, co_author exact-match shape.

## Part 2 — multi-sig quorum (the part that scales)

PMOVES agents will **multi-sig on work**. The signoff checklist and pub-gates
become machine-checkable once identities are typed:

- A gate requires **N distinct lineages**, not N signatures: alts of the same
  lineage count ONCE toward quorum (this is why alts must resolve, not
  collapse — a lineage signing twice under two alts is one voice, visibly so).
- Three-Body quorum shape: delivery, control, and memory bodies each sign
  from **different lineages** — the topology is what prevents collision, and
  the quorum check is just the topology made checkable.
- Signature material: `make sign-trail` HMAC receipts (proven live on 5090,
  kid `chit-signing-v01`) become the per-lineage attestation; a gate collects
  receipts and verifies N-of-M distinct lineages over the same payload hash.

## The node-microcosm frame (why lineage ≠ instance)

Operator (same anchor): each node is a **microcosm** — agents build their own
copy that can stand on its own, transform to connect with others on the mesh,
and **combine** (lighter load, added capabilities). So one lineage legitimately
appears as per-node instances and per-mode alts; identity must roll all of
them up without erasing which instrument signed. Relates:
`vision_fullstack_per_node_degrees`, `vision_mirror_becomes_original`,
Jetson combiner fleet.

## Three-Body framing (paraphrase, referencing existing canon)

Per the operator (same anchor, paraphrased): Three-Body is not ritual — it is
a topological solution, captured in retrospect for context, so each body can
move freely and not collide; foundational, it scales, and the hops from there
are easier and still map. **This is not new canon** — it references the canon
already written: the Village Rule and Three-Body Pattern (AGNOTE4482.md) and
the collision-safe traversal topology (KRISS_KROSS_ACCORD.md). Canon authority
is DARKXSIDE's; this doc records a pointer into it, not a replacement for it.

## Status

Seed only — unclaimed. Natural owner: any node; pairs well with the SPARK MCP
audit (both produce typed registries). First slice: `agent_identity.py` +
registry validation + `resolve_ack`, wired into `naming-drift-check` warn-only.
