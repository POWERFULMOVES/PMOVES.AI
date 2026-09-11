---
name: chit-braille
description: Render CHIT/CGP provenance as braille motifs for agent cards, harness banners, and provenance strips. Use when asked for an agent's CLI-world illustration, a context-matched PMOVES-ORCH banner, or a glanceable fingerprint of a CGP packet.
---

# CHIT Braille

Every braille cell (U+2800..U+28FF) is eight dots — one byte. Provenance
becomes the illustration: a digest or spectral signature draws straight onto
a terminal with no image protocol.

The renderer lives at `pmoves/tools/chit_braille.py` (stdlib-only; pyyaml
only for the `agent` command).

## Commands

```bash
# An agent's CLI-world card: 2x4 motif + glyph/name/color/voice/resonance.
# The id must exist in pmoves/config/agent_signatures.yaml.
python pmoves/tools/chit_braille.py agent spark-crush

# A stable motif for arbitrary context (PMOVES-ORCH banner contract):
# same context string -> same motif, on every node.
python pmoves/tools/chit_braille.py context "room: fordham community"
python pmoves/tools/chit_braille.py context "lane text" 3 6   # rows cols

# A CGP packet's content hash as a 16-cell strip — a changed packet
# visibly changes the picture (glanceable provenance diff).
python pmoves/tools/chit_braille.py cgp pmoves/data/chit/env.cgp.json
```

## Contracts

- **Determinism**: `agent_motif` and `orch_motif` are sha256-chained, no RNG.
  The same identity or context draws the same motif fleet-wide — this is
  what lets agent cards and harness banners share one illustration without
  binary assets.
- **Non-blank**: motif cells always carry at least the minimum dot pattern
  (U+2800 alone renders as invisible whitespace, which would corrupt
  layouts).
- **Content sensitivity**: `cgp_strip` is the SHA-256 of the packet bytes;
  any mutation changes the strip.

## When to use which

| Need | Command |
|---|---|
| Illustration for an agent card / room view | `agent <id>` |
| Harness banner matched to the active lane | `context "<lane>"` |
| Verify which packet a viewer/artifact carries | `cgp <file>` |

Windows consoles: run python with `PYTHONUTF8=1` (cp1252 cannot encode
braille).
