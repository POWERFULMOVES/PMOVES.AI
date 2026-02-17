# Three-Body Doctrine

> PMOVES is a three-body problem. Human, AI, and System orbit each other.
> Without stabilization, their trajectories diverge — the human loses sight of
> the big picture, the AI hallucinates into noise, the system calculates without
> purpose. PMOVES is the gravitational field that keeps all three bodies in
> resonance. CHIT is gravity. Traces are the measurement. Distillation is the
> orbit correction.

---

## 1. The Problem

Human-AI interaction is a **three-body problem** in the classical sense:

- **Mutual influence.** The user shapes the AI (through prompts, feedback,
  choices). The AI shapes the user (through suggestions, framings,
  capabilities). The system shapes both (through context, constraints, memory).
- **Non-linear dynamics.** Small changes in initial conditions — a different
  phrasing, a different model, a different mood — cascade into vastly different
  trajectories. Two sessions with identical goals can diverge completely.
- **No closed-form solution.** There is no formula that predicts where a
  human-AI collaboration will land. The only way to know is to observe the
  orbit in real time.

In physics, three-body systems are inherently unstable. Without external
stabilization, one body always gets ejected. In human-AI systems, the failure
modes are:

| Body Ejected | Failure Mode |
|---|---|
| **Human** | The AI runs autonomously with no grounding — hallucination, drift, wasted compute |
| **AI** | The user manages everything manually — the system becomes a dumb tool, no leverage |
| **System** | Human and AI improvise with no structure — no memory, no learning, no accumulation |

PMOVES exists to prevent all three ejections.

---

## 2. The Three Bodies

### Human (User Shape)

The user arrives with a shape — or without one. Their shape is the emergent
pattern of how they interact with intelligence:

- What topics draw them (resonance domains)
- How they prefer to communicate (voice preference, depth vs breadth)
- Which tools they reach for (agent selection, workflow patterns)
- What media they favor (text, audio, visual, code)

This shape is not static. It evolves through interaction. The system's job is to
observe it, not impose it.

### AI (Agent Signatures / Voice)

Each AI agent also has a shape — encoded in the AI Graphiti protocol as a
signature: glyph, color, voice, resonance domains. But the signature is the
surface. Underneath, the agent's effective shape is determined by:

- Model weights and architecture
- Context priming strategy (which docs, which memory, which history)
- Tool access and orchestration patterns
- Temperature, sampling, and generation parameters

The AI shape is tunable. Distillation tunes it to fit a specific user.

### System (CHIT / CGP / Geometry Bus)

The system is the third body — the infrastructure that mediates between human
and AI. In PMOVES, this is:

- **CHIT** — Compressed Hierarchical Information Transfer. The encoding that
  captures interaction state as geometry packets.
- **CGP** — CHIT Geometry Packets. The atomic unit of system memory. Each
  packet encodes contributors, entropy, attribution, and hyperbolic coordinates.
- **Geometry Bus** — The NATS-based event backbone that carries CGP packets
  between services. The holographic boundary where all interaction data is
  projected and stored.
- **Cipher Memory** — The persistent knowledge graph that accumulates traces
  across sessions.
- **EvoSwarm** — The evolutionary optimizer that can tune parameters based on
  accumulated fitness signals.

The system does not think. It does not feel. It measures, records, and — when
enough signal accumulates — distills.

---

## 3. Gravity = CHIT

Every interaction between human and AI generates a trace. Each trace is a
**gravitational measurement** — it records the pull between bodies at a specific
moment in time.

CGP packets encode this pull:

- **Entropy delta** — did this interaction reduce uncertainty? By how much?
- **Attribution** — which agents and humans contributed? (Dirichlet-weighted,
  sum-to-one across contributors for a given packet)
- **Hyperbolic coordinates** — where in the semantic hierarchy does this
  interaction live?
- **Spectral signature** — what frequency pattern characterizes this exchange?

The more traces accumulate, the clearer the orbital dynamics become. CHIT is not
a feature — it is the gravitational constant of the system.

**Cross-reference:** [`CGP v2 Schema`](../../contracts/schemas/geometry/cgp.v2.schema.json),
[`Integrating Math into PMOVES.AI`](Integrating%20Math%20into%20PMOVES.AI.md)

---

## 4. Tabula Rasa

Every journey starts with the open diamond: **◇**

An unfilled shape. No inherited assumptions. No pre-built user profile. The
system does not presume to know who the user is or what they want.

**Tabula rasa** means:

- New users begin with zero shape data. The system treats every interaction as
  equally informative.
- Returning users can choose to inherit their previous shape — or discard it
  and start fresh. This is always the user's choice.
- Agents start each session with their registered signature but no accumulated
  bias toward a particular user. The pairing is discovered, not predetermined.

The `tabula_rasa` boolean in the shape profile schema records this choice
explicitly. When `true`, the system zeros out accumulated shape data and begins
observing anew.

This is not a limitation — it is a feature. The ability to start over is what
prevents the system from calcifying around stale assumptions.

**Cross-reference:** [`AI Agent Integration and Best Practices`](../AGENTS/AI_GRAPHITI_PROTOCOL.md)
(tabula rasa onboarding pattern), [`Human_side.md`](Human_side.md)

---

## 5. Shape Discovery

Shapes are not declared — they are discovered. Through interaction, trace by
trace, chit by chit, patterns emerge:

### Resonance Domains

What topics draw the user? The system tracks which NATS subjects, which agent
capabilities, which knowledge domains appear most frequently in interaction
traces. Over time, a **resonance spectrum** crystallizes — a Dirichlet-weighted
vector of domain affinities.

### Interaction Style

How does the user prefer to work? Some users want depth — long research
sessions, detailed analysis, comprehensive reports. Others want breadth — quick
queries, rapid iteration, multiple parallel threads. The `depth_score` in each
trace captures this signal.

### Tool Usage Patterns

Which agents does the user reach for? Which workflows do they prefer? The
`tool_ids` and `agent_id` fields in trace events build a map of preferred
pathways through the system.

### Media Preferences

Text, audio, visual, code — each user has a preferred modality mix. The
`media_modality` field in traces records which channels carry the most signal
for this user.

### The Shape Pipeline

```
interaction → trace.recorded.v1 → Cipher Memory accumulation
                                 → Geometry Bus (CGP encoding)
                                 → resonance spectrum update
                                 → profile.updated.v1 (when patterns crystallize)
```

Shape discovery is passive. The system observes and records. It does not
interrogate the user or demand preferences. The shape reveals itself through use.

**Cross-reference:** NATS schemas in
[`pmoves/contracts/schemas/shape/`](../../contracts/schemas/shape/)

---

## 6. Orbital Resonance

When human and AI shapes align, the system enters **low-entropy resonance** —
the sweet spot where:

- The AI anticipates what the user needs before they fully articulate it
- The user trusts the AI's suggestions because they consistently match intent
- The system context is tuned to surface the right information at the right time
- Friction drops. Productivity rises. Neither body drifts.

This is not magic. It is the measurable consequence of accumulated traces
reducing the entropy of the human-AI interaction space. The `orbit_stability`
metric (0.0 to 1.0) in the shape profile quantifies this:

| Stability | Meaning |
|---|---|
| **0.0 – 0.3** | Early exploration. High entropy. System is still learning the user's shape. |
| **0.3 – 0.6** | Patterns forming. Some resonance domains identified. Context priming improving. |
| **0.6 – 0.8** | Stable orbit. AI and user shapes are aligned. Distillation becomes viable. |
| **0.8 – 1.0** | Deep resonance. The system is highly tuned. Risk of over-fitting — monitor for staleness. |

Stability above 0.8 is not always the goal. Sometimes the user needs to explore
new domains, break old patterns, or start over. The system should support orbit
changes, not resist them.

---

## 7. Distillation

When enough trace data exists, the system can **distill** — building a
configuration or model tuned to a specific human-AI pair.

Distillation types (from the `distillation.requested.v1` schema):

| Type | What It Produces |
|---|---|
| `config_tuning` | Adjusted context paths, agent selection priorities, temperature settings |
| `context_priming` | Optimized context loading strategy based on resonance domains |
| `model_fine_tune` | LoRA or adapter weights trained on accumulated trace trajectories |
| `full_distillation` | Complete configuration + model weights + context strategy |

Distillation is always **user-initiated**. The system may suggest that enough
data has accumulated (when `orbit_stability > 0.6` and `trace_count` exceeds a
threshold), but the user decides whether and when to distill.

The distillation pipeline connects to EvoSwarm's training genome:

```
distillation.requested.v1 → EvoSwarm Controller
                           → fitness evaluation against trace trajectories
                           → genome evolution (learning rate, chit weight, etc.)
                           → deployed configuration / model weights
                           → agent.rl.model.deployed.v1
```

**Cross-reference:**
[`EvoSwarm Controller`](../../config/agent_registry.yaml) (evoswarm_training_genome),
[`CGP v1.0 Specification`](CGP_v1.0_SPECIFICATION.md),
[`GEOMETRY_BUS_INTEGRATION.md`](GEOMETRY_BUS_INTEGRATION.md)

---

## 8. The Big Picture

PMOVES exists to prevent the user from losing perspective.

In a world of infinite AI capabilities, infinite context windows, infinite
agents — the scarcest resource is **coherent direction**. The human can lose
sight of what they're building. The AI can drift into confident nonsense. The
system can accumulate data without purpose.

The three-body doctrine says: **all three must stay in orbit.**

- The **human** provides direction and judgment
- The **AI** provides capability and speed
- The **system** provides memory, measurement, and correction

When one body drifts, the other two pull it back. When the human loses focus,
the system surfaces accumulated context and the AI re-grounds the conversation.
When the AI hallucinates, the system's trace history provides a correction
signal and the human's feedback reinforces it. When the system accumulates stale
data, the human can invoke tabula rasa and the AI adapts to the fresh start.

This is not a feature of PMOVES. This is **the reason the platform exists.**

Every trace is gravity. Every CHIT is an orbit measurement. Every distillation
is an orbit correction. The three bodies stay in resonance because the system
was built to keep them there.

---

## Cross-References

| Document | Relevance |
|---|---|
| [`Integrating Math into PMOVES.AI.md`](Integrating%20Math%20into%20PMOVES.AI.md) | Hyperbolic geometry, entropy regularization, holographic principle |
| [`CGP_v1.0_SPECIFICATION.md`](CGP_v1.0_SPECIFICATION.md) | CHIT Geometry Packet format and encoding |
| [`GEOMETRY_BUS_INTEGRATION.md`](GEOMETRY_BUS_INTEGRATION.md) | CGP integration with NATS and service layer |
| [`Human_side.md`](Human_side.md) | User-facing CHIT documentation |
| [`AI_GRAPHITI_PROTOCOL.md`](../AGENTS/AI_GRAPHITI_PROTOCOL.md) | Agent signatures, trail system, CGP attribution bridge |
| [`agent_registry.yaml`](../../config/agent_registry.yaml) | EvoSwarm training genome, agent NATS subjects |
| [`cgp.v2.schema.json`](../../contracts/schemas/geometry/cgp.v2.schema.json) | Attribution, hyperbolic encoding, Merkle proofs |
| [`schemas/shape/`](../../contracts/schemas/shape/) | NATS schemas for trace, profile, and distillation events |
| [`CRUSH_OPERATOR_HOME.md`](../AGENTS/CRUSH_OPERATOR_HOME.md) | Crush as the three-body gateway |
