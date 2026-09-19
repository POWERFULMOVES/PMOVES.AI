"""CHIT braille — render CHIT/CGP state as braille motifs for the CLI world harness.

Every braille cell (U+2800..U+28FF) is eight dots in a two-by-four grid, which
is exactly one byte. That makes braille the only Unicode block where a hex
digest, a Dirichlet weight vector, or a spectral signature can be drawn
directly onto a terminal with no bitmap, no sixel, no image protocol — the
provenance becomes the illustration.

Three renderers:

* ``from_bytes``   — raw bytes to cells (the lossless base case).
* ``agent_motif``  — a stable 2x4-cell illustration derived from an agent
  signature (the glyph's codepoints + voice + resonance). Deterministic:
  the same signature always draws the same motif, on every node, so agent
  cards in ``pmoves/docs/AGENTS/botz-cards/*.yaml`` and any CLI harness
  banner can carry the same illustration without sharing binary assets.
* ``cgp_strip``    — a CGP packet's numeric fingerprint as a braille strip:
  the packet IS the picture. Two packets that differ in content produce
  visibly different strips — a glanceable provenance diff.

``orch_motif`` serves PMOVES-ORCH (the context-motif orchestrator): hash the
active context (room, agent, task line) into a motif so the harness banner
matches what is being worked. Same contract as agent_motif — stable, cheap,
terminal-native.

CLI:
    python -m pmoves.tools.chit_braille agent spark-crush
    python -m pmoves.tools.chit_braille context "cipher fleet restore"
    python -m pmoves.tools.chit_braille cgp pmoves/data/chit/env.cgp.json
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BRAILLE_BASE = 0x2800
BRAILLE_MAX = 0x28FF

REPO_ROOT = Path(__file__).resolve().parents[2]
SIGNATURES = REPO_ROOT / "pmoves" / "config" / "agent_signatures.yaml"


def from_bytes(data: bytes) -> str:
    """One braille cell per byte. 0x00 renders as the blank cell U+2800."""
    return "".join(chr(BRAILLE_BASE + b) for b in data)


def _stable_ints(seed: str, count: int) -> list[int]:
    """Deterministic byte stream from a seed (sha256 chained — no RNG)."""
    out: list[int] = []
    counter = 0
    while len(out) < count:
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        out.extend(digest)
        counter += 1
    return out[:count]


def agent_motif(signature: str, rows: int = 2, cols: int = 4) -> str:
    """A stable rows x cols braille illustration for an agent signature.

    The seed mixes the signature id with a version tag so the motif changes
    only when the identity itself does. Blank cells are forced to the minimum
    dot value so the motif never contains invisible characters.
    """
    cells = _stable_ints(f"pmoves-motif-v1:{signature}", rows * cols)
    forced = [c | 0x28 if c & 0x3F == 0 else c for c in cells]
    rendered = "".join(chr(BRAILLE_BASE + (c & 0xFF)) for c in forced)
    width = cols
    return "\n".join(rendered[i : i + width] for i in range(0, len(rendered), width))


def orch_motif(context: str, rows: int = 2, cols: int = 4) -> str:
    """A stable motif for an arbitrary context string (PMOVES-ORCH banner)."""
    return agent_motif(f"pmoves-orch-v1:{context}", rows, cols)


def cgp_strip(packet_path: str | Path, cells: int = 16) -> str:
    """Braille strip of a CGP packet's content hash — the packet as a picture."""
    raw = Path(packet_path).read_bytes()
    digest = hashlib.sha256(raw).digest()
    return from_bytes(digest[:cells])


def _load_signature(agent_id: str) -> dict:
    """Load one contributor block from the signing roster."""
    import yaml  # local import: CLI stays importable without pyyaml

    doc = yaml.safe_load(SIGNATURES.read_text(encoding="utf-8"))
    sig = (doc.get("signatures") or {}).get(agent_id)
    if not sig:
        known = ", ".join(sorted((doc.get("signatures") or {}).keys()))
        raise SystemExit(f"unknown agent {agent_id!r}; known: {known}")
    return sig


def _render_agent_card(agent_id: str) -> str:
    """A compact CLI-world agent card: motif, glyph, voice, resonance."""
    sig = _load_signature(agent_id)
    lines = [
        agent_motif(agent_id),
        f"{sig.get('glyph', '?')} {sig.get('display_name', agent_id)}  "
        f"({sig.get('color', '?')})",
        f"voice: {sig.get('voice', '?')}  node: {sig.get('node', 'fleet')}",
        f"resonance: {', '.join(sig.get('resonance', [])[:4])}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(__doc__)
        return 2
    command, value = argv[0], argv[1]
    if command == "agent":
        print(_render_agent_card(value))
    elif command == "context":
        rows = int(argv[2]) if len(argv) > 2 else 2
        cols = int(argv[3]) if len(argv) > 3 else 4
        print(orch_motif(value, rows, cols))
    elif command == "cgp":
        print(cgp_strip(value))
    else:
        print(f"unknown command {command!r}; use agent|context|cgp", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
