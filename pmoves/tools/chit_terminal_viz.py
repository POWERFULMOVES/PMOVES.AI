#!/usr/bin/env python3
"""
Terminal CHIT Visualization

Renders CGP constellation data as terminal sparklines and ASCII art.
"Show time is in the terminal" — AGNOTE4482

Thread 8.3: Terminal CHIT Visualization

Usage:
    python pmoves/tools/chit_terminal_viz.py [--mode sparkline|constellation|poincare]
    echo '{"alphas": [0.5, 1.2, 0.3]}' | python pmoves/tools/chit_terminal_viz.py
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Sparkline characters (Unicode block elements)
SPARK_CHARS = " ▁▂▃▄▅▆▇█"
BRAILLE_BASE = 0x2800  # Unicode braille pattern base

SIGNATURES_PATH = Path(__file__).parent.parent / "config" / "agent_signatures.yaml"


def _load_agent_sig(agent_id: str) -> Optional[Dict]:
    """Load a single agent signature by ID from agent_signatures.yaml."""
    try:
        import yaml
    except ImportError:
        return None
    if not SIGNATURES_PATH.exists():
        return None
    with open(SIGNATURES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for entry in data.get("signatures", data.get("agents", [])):
        if isinstance(entry, dict) and entry.get("agent_id") == agent_id:
            return entry
    return None


def _ansi_fg(hex_color: str, text: str) -> str:
    """24-bit ANSI foreground color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return text
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def sparkline(values: List[float], width: Optional[int] = None) -> str:
    """Render values as a sparkline string."""
    if not values:
        return ""

    if width and len(values) > width:
        # Downsample
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]

    min_v = min(values)
    max_v = max(values)
    span = max_v - min_v if max_v != min_v else 1

    chars = []
    for v in values:
        idx = int((v - min_v) / span * (len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return "".join(chars)


def bar_chart(
    labels: List[str], values: List[float], width: int = 40, label_width: int = 15
) -> str:
    """Render horizontal bar chart in terminal."""
    if not values:
        return ""

    max_v = max(values) if values else 1
    lines = []

    for label, value in zip(labels, values):
        bar_len = int((value / max_v) * width) if max_v > 0 else 0
        bar = "█" * bar_len + "░" * (width - bar_len)
        lines.append(f"  {label:<{label_width}} {bar} {value:.3f}")

    return "\n".join(lines)


def poincare_disk(
    points: List[Tuple[float, float]],
    size: int = 21,
    labels: Optional[List[str]] = None,
) -> str:
    """Render Poincare disk visualization in terminal.

    Uses a character grid to show points in hyperbolic space.
    """
    # Initialize grid
    grid = [[" " for _ in range(size * 2)] for _ in range(size)]
    center_x = size
    center_y = size // 2
    radius = min(center_x, center_y) - 1

    # Draw disk boundary (circle)
    for angle in range(360):
        rad = math.radians(angle)
        gx = int(center_x + radius * math.cos(rad) * 2)
        gy = int(center_y + radius * math.sin(rad))
        if 0 <= gy < size and 0 <= gx < size * 2:
            grid[gy][gx] = "·"

    # Draw center cross
    if 0 <= center_y < size and 0 <= center_x < size * 2:
        grid[center_y][center_x] = "+"

    # Plot points
    point_chars = "●○◆◇■□▲△★☆"
    for i, (px, py) in enumerate(points):
        # Map Poincare coords [-1, 1] to grid
        gx = int(center_x + px * radius * 2)
        gy = int(center_y + py * radius)

        if 0 <= gy < size and 0 <= gx < size * 2:
            char = point_chars[i % len(point_chars)]
            grid[gy][gx] = char

    # Build output
    lines = ["  Poincaré Disk (hyperbolic space)"]
    for row in grid:
        lines.append("  " + "".join(row))

    # Legend
    if labels:
        lines.append("")
        for i, label in enumerate(labels):
            char = point_chars[i % len(point_chars)]
            if i < len(points):
                x, y = points[i]
                lines.append(f"  {char} {label} ({x:.2f}, {y:.2f})")

    return "\n".join(lines)


def constellation_map(
    nodes: List[Dict],
    width: int = 60,
    height: int = 20,
) -> str:
    """Render constellation map showing agent relationships."""
    grid = [[" " for _ in range(width)] for _ in range(height)]

    # Place nodes
    for i, node in enumerate(nodes):
        x = int((node.get("x", 0) + 1) / 2 * (width - 2)) + 1
        y = int((node.get("y", 0) + 1) / 2 * (height - 2)) + 1
        x = max(1, min(width - 2, x))
        y = max(1, min(height - 2, y))

        name = node.get("name", f"N{i}")[:3]
        for ci, c in enumerate(name):
            if x + ci < width:
                grid[y][x + ci] = c

    # Border
    for x in range(width):
        grid[0][x] = "─"
        grid[height - 1][x] = "─"
    for y in range(height):
        grid[y][0] = "│"
        grid[y][width - 1] = "│"
    grid[0][0] = "┌"
    grid[0][width - 1] = "┐"
    grid[height - 1][0] = "└"
    grid[height - 1][width - 1] = "┘"

    lines = ["  CHIT Constellation Map"]
    for row in grid:
        lines.append("  " + "".join(row))

    # Legend
    lines.append("")
    for node in nodes:
        lines.append(f"  {node.get('name', '?'):<20} tier={node.get('tier', '?')}")

    return "\n".join(lines)


def render_cgp_summary(cgp: Dict, agent_sig: Optional[Dict] = None) -> str:
    """Render a CGP packet summary in terminal.

    If agent_sig is provided, shows agent attribution with glyph and color.
    """
    lines = [
        "╔══════════════════════════════════════╗",
        "║     CGP v2 Packet Summary            ║",
        "╚══════════════════════════════════════╝",
    ]

    # Agent attribution line
    if agent_sig:
        glyph = agent_sig.get("glyph", "?")
        color = agent_sig.get("color", "#FFFFFF")
        aid = agent_sig.get("agent_id", "unknown")
        voice = agent_sig.get("voice", "")
        attr_line = f"  {_ansi_fg(color, glyph)} {aid} | {color} | {voice}"
        lines.append(attr_line)

    payload = cgp.get("payload", {})

    # Spectral signature sparkline
    spectral = payload.get("spectral_signature", [])
    if spectral:
        lines.append(f"  Spectral:  {sparkline(spectral)}")

    # Dirichlet weights
    dw = payload.get("dirichlet_weights", {})
    if dw:
        alphas = dw.get("alphas", [])
        categories = dw.get("categories", [f"c{i}" for i in range(len(alphas))])
        if alphas:
            lines.append("")
            lines.append("  Dirichlet Weights:")
            lines.append(bar_chart(categories, alphas))

    # Hyperbolic coords
    coords = payload.get("hyperbolic_coords", {})
    if coords:
        x = coords.get("x", 0)
        y = coords.get("y", 0)
        lines.append("")
        lines.append(poincare_disk([(x, y)], size=11, labels=["content"]))

    # Metadata
    lines.append("")
    lines.append(f"  Checksum: {cgp.get('checksum', 'N/A')[:16]}...")
    lines.append(f"  Version:  {cgp.get('version', 'N/A')}")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Terminal CHIT Visualization")
    parser.add_argument(
        "--mode",
        choices=["sparkline", "constellation", "poincare", "cgp", "bar"],
        default="cgp",
        help="Visualization mode",
    )
    parser.add_argument("--input", "-i", help="Input JSON file")
    parser.add_argument("--agent", help="Agent ID for themed rendering (e.g., claude-opus)")

    args = parser.parse_args()

    # Load agent signature if requested
    agent_sig = None
    if args.agent:
        agent_sig = _load_agent_sig(args.agent)
        if not agent_sig:
            print(f"Warning: Agent '{args.agent}' not found in signatures", file=sys.stderr)

    # Read input
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    elif not sys.stdin.isatty():
        data = json.load(sys.stdin)
    else:
        # Demo data
        data = {
            "version": "cgp.v2",
            "payload": {
                "spectral_signature": [14.13, 21.02, 25.01, 30.42, 32.94, 37.59],
                "dirichlet_weights": {
                    "alphas": [0.85, 1.2, 0.3, 0.65, 0.4],
                    "categories": ["factual", "conceptual", "procedural", "contextual", "relational"],
                },
                "hyperbolic_coords": {"x": 0.3, "y": -0.4, "curvature": -1},
            },
            "checksum": "abc123def456789",
        }

    # Use agent glyph as point marker when available
    point_marker = None
    if agent_sig:
        point_marker = agent_sig.get("glyph")

    if args.mode == "cgp":
        print(render_cgp_summary(data, agent_sig=agent_sig))
    elif args.mode == "sparkline":
        values = data if isinstance(data, list) else data.get("values", [])
        result = sparkline(values)
        if agent_sig:
            color = agent_sig.get("color", "#FFFFFF")
            result = _ansi_fg(color, result)
        print(result)
    elif args.mode == "poincare":
        points = data.get("points", [(0.3, -0.4)])
        labels = data.get("labels", [])
        print(poincare_disk(points, labels=labels))
    elif args.mode == "constellation":
        nodes = data.get("nodes", data if isinstance(data, list) else [])
        print(constellation_map(nodes))
    elif args.mode == "bar":
        labels = data.get("labels", [])
        values = data.get("values", [])
        print(bar_chart(labels, values))

    return 0


if __name__ == "__main__":
    sys.exit(main())
