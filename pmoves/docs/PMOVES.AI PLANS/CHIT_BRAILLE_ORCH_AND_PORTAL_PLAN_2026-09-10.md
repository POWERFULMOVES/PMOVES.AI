# CHIT Braille, PMOVES-ORCH, and the Provenance Media Plane

_Created: 2026-09-10 — CRUSH-SPARK (Z890) for DARKXSIDE_
_Status: kernel SHIPPED (see §0); slices 1–4 queued_

## Thesis

CHIT provenance should be *visible, playable, and traceable*. The braille
kernel makes it **visible** (terminal-native illustrations with no image
protocol). PMOVES-ORCH makes it **playable** (a harness banner that motifs to
match the active context). The media plane makes it **traceable and audible**:
a WebRTC portal streaming an agent or a room, an announcer narrating from the
corpus, and every narrative item carrying a Kevin-Bacon-style verification
chain — N hops through the corpus graph back to CHIT-signed sources. Any item
that cannot trace its chain is not broadcast; silence is the fail-closed state.

## 0 — Kernel (shipped 2026-09-10)

`pmoves/tools/chit_braille.py` + `pmoves/tests/tools/test_chit_braille.py`
(8 tests):

- `from_bytes` — one braille cell per byte (U+2800 + byte), the lossless base.
- `agent_motif(id)` — deterministic rows×cols illustration per signing-roster
  identity; same identity draws the same motif on every node, so agent cards
  (`pmoves/docs/AGENTS/botz-cards/*.yaml`, `.claude/agents/*.md` frontmatter)
  and any CLI harness banner share one illustration without binary assets.
- `orch_motif(context)` — stable motif from arbitrary context text; the
  PMOVES-ORCH banner contract.
- `cgp_strip(packet)` — SHA-256 of a CGP packet as a 16-cell strip; a changed
  packet changes the picture (glanceable provenance diff).
- CLI: `agent | context | cgp`.

First roster member of the motif family: `spark-crush` (⠿, lime-700) —
SPARK's node identity, wired the same day in agent_registry +
node-vocabulary.

## 1 — PMOVES-ORCH: context-motif orchestrator

Wire `orch_motif` into the harness surfaces so every terminal, agent card,
and room view renders a motif matching its live context.

- Harness banner: `crush-pmoves` / `claude-pmoves` print `orch_motif(node +
  ":" + active-lane)` at startup (launcher already resolves node + identity).
- Agent cards: botz-cards grow an optional `motif_seed` field; the Showtime
  API (`showtime-api`, :9225) exposes `GET /motif/{agent}` returning the
  ASCII/braille block — the A2UI surface renders it verbatim.
- Acceptance: two nodes launching the same lane draw identical banners.

## 2 — WebRTC portal: stream an agent or a room

Extend the DARKXSIDE Hyperdimensions portal (already scaffolded with the
prosodic-geometry bridge; blocked only on a live Flute-Gateway E2E test):

- Room stream: P7 publishes stage facts (transitions, CHIT activations) to
  NATS (`p7.nats.session`); the portal bridges those facts into a WebRTC data
  channel + renders the room's braille motif as the poster frame.
- Agent stream: agent stdout/NATS activity is sampled into CGP-sized frames;
  the `cgp_strip` of each frame is the stream's visual fingerprint, so a
  viewer can verify "I am watching the agent I think I am watching."
- Acceptance: a viewer on a second tailnet node watches `fordham.room.*`
  facts live and can quote the poster-frame strip that matches the room's
  published CGP.

## 3 — Announcer radio: narrative from the corpus

The announcer/narrator voices already exist (`voice-personas.md`,
`tts-engine-capabilities.yaml → service_runners`); Flute renders voice on
B850/ROCm and the 5090.

- Source: the DARKXSIDE playlist corpus (2,017 videos classified across 11
  resonance domains, live in Supabase) + Open Notebook evidence.
- Format: a "radio lane" generator composes an announcer segment per theme —
  pick a domain, pull the top-N classified items, narrate transitions with
  the announcer persona, publish to `content.published.v1` → Discord +
  Jellyfin deep links via the existing publisher chain.
- Motif pairing: each segment carries its `orch_motif` in the embed footer —
  the radio is identifiable in text before it is audible.
- Acceptance: one fully synthesized segment per corpus domain, each with a
  Kevin-Bacon chain (below) attached.

## 4 — Kevin-Bacon provenance: N-hop verification chains

Every narrative item (radio segment, portal frame, agent claim) ships a
verification chain: the shortest hop path from the item through the corpus
graph (Neo4j mindmap; cipher `pmoves_cipher_graph_expand` neighborhoods) back
to CHIT-signed sources (signed trails, CGP packets, monitored-ingest
records).

- Chain record: `item → edge… → source`, each edge labeled with the corpus
  relation; each terminal source carries its CHIT signature id.
- Policy: chains are computed at composition time, embedded in the NATS
  envelope (`meta.provenance_chain`), and rendered as a hop list in the
  Discord embed.
- Fail-closed: no chain, no broadcast. An announcer segment sourced from an
  unverified corner of the corpus is held in rehearsal, never live.
- Acceptance: every broadcast item's embed prints its hops; a tampered item
  (chain broken) is refused by the publisher.

## Order

1 → 2 → 3 → 4. ORCH is pure presentation and lands value immediately; the
portal needs a live Flute-Gateway; radio needs the portal's identity strip
for embeds; the provenance chain audits everything 1–3 produce and is last
because it is the gate, not the feature.
