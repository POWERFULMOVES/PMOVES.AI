# Headset Engine — 325 Worldview Try-On (Lane Spec)

> Authored 5090, 2026-08-04. Companion to
> `hf-seat-curator-spark-2026-08-04.md` (the seat pattern this generalizes)
> and the DARKXSIDE room surface. Grounding corpus status at the bottom.

## Operator seeds (verbatim, seed-don't-prune)

> "the 325 theories of consciousness vid ... that and the links are the
> grounding for the personas 325 headsets we will make it so people can try
> others worldviews on instead of funneling into existential silo"

> "when wiring hyperdimensions is control surface but we need a2ui/comfyui
> overlay we are gonna turn it to a game engine almost geomtery bus gives us
> any anchor to map to any other or like a vendiagram with 11 screens might
> be polarized might not and what does the laser do as what you believe is
> kinda like a filter or can act as one will work great for evo swarm and
> tokensim sim as now user gets to model user and model gets to model model"

## The napkin

People run one worldview, installed by accident, defended by identity. The
325-theory map is the index of every alternative seriously proposed. PMOVES
makes them WEARABLE: theory → grounding pack → persona headset → room. The
product is the SWITCHING, not any theory being right — a person who has worn
five worldviews can't be silo'd into one.

## Architecture (decoded from the seeds)

| Layer | Component | Role |
|---|---|---|
| Index | `pmoves_core.consciousness_theories` | the 325 (216 pre-existing; completion lane running) |
| Grounding | `grounding_packs` + `pack_members` | one pack per theory: transcript slice + source links + axioms |
| Voice | `personas` + persona seat (cf. model-seat pattern, PR #2376) | a persona WEARS a pack; swap = one binding, zero surgery |
| Control surface | **Pmoves-hyperdimensions** | headset wiring/selection lives here |
| Render | **A2UI + ComfyUI overlay** | "almost a game engine" — not a dashboard; ComfyUI generates the visual field per worldview |
| Mapping | **GEOMETRY_BUS** | any anchor maps to any other anchor — cross-worldview comparison is a bus operation, not a bespoke join |
| Display | **11-screen Venn** | the ~11 taxonomy categories as overlapping screens (materialism, non-reductive physicalism, quantum, IIT, panpsychism, monism, dualism, idealism, anomalous, challenge, +) |
| Stage | rooms (DARKXSIDE first) + Showtime | where you stand while wearing one |

## The polarization model (physics metaphor, load-bearing)

A belief system behaves like a **polarizing filter**: it passes some of
reality and attenuates the rest. Design consequences:

- Each theory-pack carries a **filter profile**: what it foregrounds, what
  it renders invisible (extracted from its axioms).
- Switching headsets = rotating the filter; stacking two = seeing the
  interference (GEOMETRY_BUS anchor mapping renders the overlap).
- "Might be polarized might not" — polarization is a **detected property**
  per theory, not an assumption; some theories are broadband.
- "What does the laser do" — OPEN SEED, preserved: coherent single-frequency
  throughput; candidate meaning: a maximally-committed worldview as coherent
  beam (high power, narrow band). To be developed, not resolved here.

## EVO SWARM + Tokenism payoff

Mutual modeling becomes first-class: **the user gets to model the user, and
the model gets to model the model.** Headsets give agents wearable user-
worldviews (agent models user through the user's own filter) and give users
wearable agent-views. Tokenism sim can price worldview-switching behavior;
EVO SWARM can evolve filter combinations. (Canon: mutual-watching /
tuning-fork / marco-polo.)

## Build order

1. **Index completion** (running): extract all theories from the 141k-char
   transcript (`pmoves.consciousness.grounding`), diff vs the 216, verify
   the video's actual coverage of "325", fill the gap with attribution.
2. **Pack generator**: per theory — transcript slice + category + proponents
   + filter profile stub → `grounding_packs`/`pack_members`. Deterministic
   tool, not hand-authored.
3. **Headset binding**: persona seat wears a pack (env/config binding, same
   shape as AUDIO_MODEL_ID); DARKXSIDE room gets the first try-on surface.
4. **Overlay lane** (cross-node, A2UI/ComfyUI owners): 11-screen Venn +
   geometry-bus anchor mapping + game-engine ambition. Needs its own spec
   once 1–3 are real.

## Out of scope here

The laser semantics (open seed); the full game-engine overlay
implementation; Kuhn-paper licensing for verbatim theory text (packs use
transcript + our own summaries + links, not the paper's text).

**Three-body:** delivery = 5090 (index, packs, binding) + A2UI/ComfyUI lane
owners (overlay); control = DARKXSIDE (every gate, room approvals); memory =
this spec + vision memories (325-headsets, polarization-geometry) + the
transcript in the grounding namespace.
