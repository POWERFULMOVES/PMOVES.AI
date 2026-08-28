# FlOO$ Character Persona System — Phase A Specification

## 1. Overview
The FlOO$ layer introduces **Character Suits** — persona archetypes that agents can wear, mix, and match. Powered by MiniMax and summoned by the orchestrating node, these are not mere costumes; they are mathematically tuned parameter surfaces (`control_plane.param_surface`) mapped directly on top of the Geometry Bus CGP state vectors.

This spec outlines the Phase A integration: defining the initial 3 character archetypes, mapping them to the `param_surface` control layer, and establishing the integration point with MiniMax's voice/character synthesis engine.

## 2. Character Suit Archetypes

### 2.1 Dr. Bean
- **Archetype**: Methodical genius, quietly absurd.
- **Voice Register**: Measured, precise, occasional deadpan.
- **When to Use**: Deep analysis, code auditing, and CHIT signature review.
- **Param Surface Override**:
  - `temperature`: 0.3 (highly deterministic)
  - `speaking_rate`: 0.85 (deliberate pacing)
  - `pitch_shift`: -2.0 (slightly deeper resonance)
  - `register`: "deadpan_analytical"

### 2.2 Mr. Clean
- **Archetype**: Precise, powerful, no-nonsense.
- **Voice Register**: Direct, confident, crisp.
- **When to Use**: Deployment, infrastructure scaling, security, and hardening.
- **Param Surface Override**:
  - `temperature`: 0.1 (strict constraint adherence)
  - `speaking_rate`: 1.15 (brisk and efficient)
  - `pitch_shift`: 0.0 (neutral)
  - `register`: "authoritative_crisp"

### 2.3 PowerPuff Girls (Trinity Mode)
- **Archetype**: Trio of specialized powers.
- **Voice Register**: High energy, distinct voices per lane, harmonizing dynamically.
- **When to Use**: Multi-agent coordination, celebration, high-throughput parallel execution.
- **Param Surface Override**:
  - `temperature`: 0.8 (creative, emergent)
  - `speaking_rate`: 1.25 (fast-paced, overlapping)
  - `pitch_shift`: +3.0 (higher energy band)
  - `register`: "high_energy_triad"

## 3. CGP Parameter Mapping

Character suits are broadcast via the `control_plane` block of a CGP `v0.2` payload on the `geometry.cgp.v1` NATS subject. 

When a CGP packet contains a `param_surface` override, the Flute NATS Consumer (`cgp_consumer.py`) intercepts this block and patches the local state vector before passing the instructions to the MiniMax API.

### 3.1 Payload Structure
```json
{
  "spec": "chit.cgp.v0.2",
  "type": "geometry.packet.decoded.v1",
  "super_nodes": [...],
  "control_plane": {
    "state_vector": {
      "delta": 0.5,
      "kappa": -0.2,
      "Hz": 0.8
    },
    "param_surface": {
      "suit_id": "mr_clean",
      "temperature": 0.1,
      "speaking_rate": 1.15,
      "register": "authoritative_crisp"
    }
  }
}
```

## 4. MiniMax Integration Engine

1. **Trigger**: An agent publishes a CGP packet requesting a specific `suit_id` (e.g., `mr_clean`) via the `control_plane`.
2. **Intercept**: Flute's `cgp_consumer.py` decodes the packet and reads the `param_surface`.
3. **Synthesis**: The `voice_relay` service hits the MiniMax API, injecting the text payload alongside the parameter constraints (`temperature`, `speaking_rate`). 
4. **Playback**: The resulting audio stream is broadcast back out, matching the exact prosody and emotional cadence of the requested character suit.

## 5. Next Steps for Phase B
- Dynamic "Suit Swapping" mid-sentence based on real-time NATS tokenomics (Wealth Tokenism).
- Custom Voice Clones generated via few-shot MiniMax API endpoints.
