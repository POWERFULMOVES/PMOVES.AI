#!/usr/bin/env python3
"""Agent-Themed Terminal Renderer

Reads agent_signatures.yaml and node-agent-specialization.yaml to render
ANSI-themed terminal output: banners, status bars, session headers.

W1 deliverable — foundation for BoTZ CLI theme bridge and P7 terminal integration.

Usage:
    python pmoves/tools/agent_terminal_theme.py --demo
    python pmoves/tools/agent_terminal_theme.py --agent 4090-claude
    python pmoves/tools/agent_terminal_theme.py --agent claude-opus --banner
    python pmoves/tools/agent_terminal_theme.py --agent z890-claude --status "19 containers healthy"
    python pmoves/tools/agent_terminal_theme.py --whoami
    python pmoves/tools/agent_terminal_theme.py --agent 4090-claude --json
    python pmoves/tools/agent_terminal_theme.py --agent z890-claude --remote --banner
"""
from __future__ import annotations

import argparse
import json as json_mod
import os
import socket
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Resolve project root (pmoves/) so YAML paths work from any invocation dir.
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
_PMOVES_ROOT = _TOOLS_DIR.parent

_SIGNATURES_PATH = _PMOVES_ROOT / "config" / "agent_signatures.yaml"
_NODE_SPEC_PATH = _PMOVES_ROOT / "configs" / "node-agent-specialization.yaml"


# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
def _supports_color() -> bool:
    """Check if terminal supports ANSI color."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        return os.environ.get("WT_SESSION") is not None or "TERM_PROGRAM" in os.environ
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert #RRGGBB to (R, G, B)."""
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _fg(hex_color: str) -> str:
    """ANSI 24-bit foreground escape for a hex color."""
    if not _supports_color():
        return ""
    r, g, b = _hex_to_rgb(hex_color)
    return f"\033[38;2;{r};{g};{b}m"


def _bg(hex_color: str) -> str:
    """ANSI 24-bit background escape for a hex color."""
    if not _supports_color():
        return ""
    r, g, b = _hex_to_rgb(hex_color)
    return f"\033[48;2;{r};{g};{b}m"


_RESET = "\033[0m" if _supports_color() else ""
_BOLD = "\033[1m" if _supports_color() else ""
_DIM = "\033[2m" if _supports_color() else ""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class AgentTheme:
    agent_id: str
    display_name: str
    glyph: str
    color: str
    accent: str
    voice: str
    resonance: List[str]
    description: str
    co_author: str = ""
    specialization: str = ""
    routes_to: List[str] = None

    def __post_init__(self):
        if self.routes_to is None:
            self.routes_to = []


@dataclass
class NodeSpec:
    node_id: str
    glyph: str
    color: str
    hardware: Dict[str, str]
    specialization: str
    cognitive_strengths: List[str]
    work_types: List[str]
    announce_subject: str


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file, returning empty dict on failure."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        print("WARNING: pyyaml not installed, using fallback", file=sys.stderr)
        return {}
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_agent(agent_id: str) -> Optional[AgentTheme]:
    """Load a single agent's theme from agent_signatures.yaml."""
    data = _load_yaml(_SIGNATURES_PATH)
    sigs = data.get("signatures", {})
    entry = sigs.get(agent_id)
    if not entry:
        return None
    return AgentTheme(
        agent_id=entry.get("agent_id", agent_id),
        display_name=entry.get("display_name", agent_id),
        glyph=entry.get("glyph", "?"),
        color=entry.get("color", "#FFFFFF"),
        accent=entry.get("accent", "#CCCCCC"),
        voice=entry.get("voice", "analytical"),
        resonance=entry.get("resonance", []),
        description=entry.get("description", ""),
        co_author=entry.get("co_author", ""),
        specialization=entry.get("specialization", ""),
        routes_to=entry.get("routes_to", []),
    )


def load_all_agents() -> List[AgentTheme]:
    """Load all agent themes."""
    data = _load_yaml(_SIGNATURES_PATH)
    sigs = data.get("signatures", {})
    agents = []
    for aid, entry in sigs.items():
        agents.append(AgentTheme(
            agent_id=entry.get("agent_id", aid),
            display_name=entry.get("display_name", aid),
            glyph=entry.get("glyph", "?"),
            color=entry.get("color", "#FFFFFF"),
            accent=entry.get("accent", "#CCCCCC"),
            voice=entry.get("voice", "analytical"),
            resonance=entry.get("resonance", []),
            description=entry.get("description", ""),
            co_author=entry.get("co_author", ""),
            specialization=entry.get("specialization", ""),
            routes_to=entry.get("routes_to", []),
        ))
    return agents


def load_node(node_id: str) -> Optional[NodeSpec]:
    """Load a node's spec from node-agent-specialization.yaml."""
    data = _load_yaml(_NODE_SPEC_PATH)
    nodes = data.get("nodes", {})
    entry = nodes.get(node_id)
    if not entry:
        return None
    return NodeSpec(
        node_id=node_id,
        glyph=entry.get("glyph", "?"),
        color=entry.get("color", "#FFFFFF"),
        hardware=entry.get("hardware", {}),
        specialization=entry.get("specialization", ""),
        cognitive_strengths=entry.get("cognitive_strengths", []),
        work_types=entry.get("work_types", []),
        announce_subject=entry.get("announce_subject", ""),
    )


# ---------------------------------------------------------------------------
# Remote loader (BoTZ Gateway at :8054)
# ---------------------------------------------------------------------------
_BOTZ_GATEWAY_URL = os.getenv("BOTZ_GATEWAY_URL", "http://localhost:8054")


def _fetch_remote_theme(agent_id: str) -> Optional[AgentTheme]:
    """Fetch agent theme from BoTZ Gateway API. Returns None on failure."""
    try:
        from urllib.request import urlopen, Request
        from urllib.error import URLError
    except ImportError:
        return None
    try:
        req = Request(f"{_BOTZ_GATEWAY_URL}/v1/agent/theme/{agent_id}")
        req.add_header("Accept", "application/json")
        with urlopen(req, timeout=3) as resp:
            data = json_mod.loads(resp.read())
        return AgentTheme(
            agent_id=data.get("agent_id", agent_id),
            display_name=data.get("display_name", agent_id),
            glyph=data.get("glyph", "?"),
            color=data.get("color", "#FFFFFF"),
            accent=data.get("accent", "#CCCCCC"),
            voice=data.get("voice", "analytical"),
            resonance=data.get("resonance", []),
            description=data.get("description", ""),
        )
    except (URLError, OSError, json_mod.JSONDecodeError, KeyError):
        return None


def _resolve_whoami() -> str:
    """Resolve current agent identity from environment, hostname, or gateway."""
    # 1. Explicit env var (set by BoTZ session or Claude Code hook)
    agent_id = os.environ.get("PMOVES_AGENT_ID")
    if agent_id:
        return agent_id

    # 2. Hostname heuristic — match against known node patterns
    hostname = socket.gethostname().lower()
    _HOST_MAP = {
        "z890": "z890-claude",
        "pmoves-z890": "z890-claude",
        "powerfulmoves": "5090-claude",
        "pmoves-powerfulmoves": "5090-claude",
        "laptop": "4090-claude",
        "pmoves-laptop": "4090-claude",
    }
    for pattern, aid in _HOST_MAP.items():
        if pattern in hostname:
            return aid

    # 3. Gateway fallback
    try:
        from urllib.request import urlopen, Request
        from urllib.error import URLError
        req = Request(f"{_BOTZ_GATEWAY_URL}/v1/agent/whoami")
        req.add_header("Accept", "application/json")
        with urlopen(req, timeout=3) as resp:
            data = json_mod.loads(resp.read())
        return data.get("agent_id", "unknown")
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
def colorize(text: str, hex_color: str) -> str:
    """Apply a hex color to text via ANSI 24-bit codes."""
    return f"{_fg(hex_color)}{text}{_RESET}"


def render_banner(agent: AgentTheme, width: int = 52) -> str:
    """Render a themed banner with glyph and display name."""
    fg = _fg(agent.color)
    ac = _fg(agent.accent)
    border = f"{fg}{'━' * width}{_RESET}"
    title = f"{fg}{_BOLD}{agent.glyph} {agent.display_name}{_RESET}"
    voice_line = f"{ac}  voice: {agent.voice}  |  {', '.join(agent.resonance[:3])}{_RESET}"

    lines = [border, title]
    if agent.specialization:
        lines.append(f"{ac}  [{agent.specialization}]{_RESET}")
    lines.append(voice_line)
    if agent.description:
        lines.append(f"{_DIM}  {agent.description}{_RESET}")
    lines.append(border)
    return "\n".join(lines)


def render_status_bar(agent: AgentTheme, status: str, width: int = 52) -> str:
    """Render a themed single-line status bar."""
    fg = _fg(agent.color)
    label = f"{fg}{_BOLD}{agent.glyph} {agent.display_name}{_RESET}"
    sep = f"{_fg(agent.accent)}│{_RESET}"
    return f"{label} {sep} {status}"


def session_header(agent: AgentTheme, node: Optional[NodeSpec] = None) -> str:
    """Render a combined agent+node session header."""
    fg = _fg(agent.color)
    border = f"{fg}{'═' * 52}{_RESET}"
    title = f"{fg}{_BOLD}{agent.glyph} {agent.display_name}{_RESET}"

    lines = [border, title]

    if node:
        nfg = _fg(node.color)
        hw = node.hardware
        hw_line = f"  {hw.get('gpu', '?')} | {hw.get('cpu', '?')} | {hw.get('ram', '?')}"
        lines.append(f"{nfg}  node: {node.node_id} ({node.specialization}){_RESET}")
        lines.append(f"{_DIM}{hw_line}{_RESET}")

    if agent.resonance:
        ac = _fg(agent.accent)
        lines.append(f"{ac}  resonance: {', '.join(agent.resonance)}{_RESET}")

    if node and node.cognitive_strengths:
        lines.append(f"{_DIM}  strengths: {', '.join(node.cognitive_strengths[:4])}{_RESET}")

    lines.append(border)
    return "\n".join(lines)


def render_roster(agents: List[AgentTheme]) -> str:
    """Render a compact roster of all agents."""
    lines = [f"{_BOLD}Agent Roster ({len(agents)} agents){_RESET}", ""]
    for a in agents:
        fg = _fg(a.color)
        spec = f" [{a.specialization}]" if a.specialization else ""
        lines.append(f"  {fg}{a.glyph} {a.display_name:<20}{_RESET}{spec}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    """Parse CLI args and render themed terminal output for PMOVES agents."""
    # Ensure UTF-8 stdout on Windows (Unicode glyphs in agent signatures)
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Agent-Themed Terminal Renderer")
    parser.add_argument("--agent", "-a", help="Agent ID (e.g. claude-opus, 4090-claude)")
    parser.add_argument("--node", "-n", help="Node ID for session header (e.g. 4090-claude)")
    parser.add_argument("--banner", action="store_true", help="Render full banner")
    parser.add_argument("--status", "-s", help="Status text for status bar")
    parser.add_argument("--session", action="store_true", help="Render session header")
    parser.add_argument("--roster", action="store_true", help="Render all agents roster")
    parser.add_argument("--demo", action="store_true", help="Render demo of all agents")
    parser.add_argument("--json", action="store_true", dest="json_out", help="Output as JSON (for BoTZ CLI / P7 integration)")
    parser.add_argument("--remote", action="store_true", help="Fetch theme from BoTZ Gateway instead of local YAML")
    parser.add_argument("--whoami", action="store_true", help="Resolve and display current agent identity")

    args = parser.parse_args()

    # --- whoami: resolve identity and display ---
    if args.whoami:
        agent_id = _resolve_whoami()
        agent = load_agent(agent_id)
        node = load_node(agent_id)
        if args.json_out:
            result = {"agent_id": agent_id, "source": "env" if os.environ.get("PMOVES_AGENT_ID") else "heuristic"}
            if agent:
                result["theme"] = {"glyph": agent.glyph, "color": agent.color, "accent": agent.accent, "voice": agent.voice}
                result["display_name"] = agent.display_name
                result["specialization"] = agent.specialization
                result["resonance"] = agent.resonance
            if node:
                result["node"] = {"hardware": node.hardware, "specialization": node.specialization}
            print(json_mod.dumps(result, indent=2))
        else:
            if agent:
                print(render_banner(agent))
                if node:
                    print()
                    print(session_header(agent, node))
            else:
                print(f"Resolved agent: {agent_id} (not in signatures)")
        return 0

    if args.demo:
        agents = load_all_agents()
        if not agents:
            print("ERROR: Could not load agent_signatures.yaml", file=sys.stderr)
            return 1
        if args.json_out:
            print(json_mod.dumps([asdict(a) for a in agents], indent=2))
            return 0
        for agent in agents:
            print(render_banner(agent))
            print()
        print(render_roster(agents))
        return 0

    if args.roster:
        agents = load_all_agents()
        if args.json_out:
            print(json_mod.dumps([{"agent_id": a.agent_id, "glyph": a.glyph, "color": a.color, "specialization": a.specialization} for a in agents], indent=2))
            return 0
        print(render_roster(agents))
        return 0

    if not args.agent:
        parser.print_help()
        return 1

    # --- Load agent (local or remote) ---
    agent = None
    if args.remote:
        agent = _fetch_remote_theme(args.agent)
        if agent:
            print(f"{_DIM}(remote: {_BOTZ_GATEWAY_URL}){_RESET}", file=sys.stderr)
        else:
            print(f"WARNING: Gateway unreachable, falling back to local YAML", file=sys.stderr)
    if not agent:
        agent = load_agent(args.agent)
    if not agent:
        print(f"ERROR: Agent '{args.agent}' not found in {_SIGNATURES_PATH}", file=sys.stderr)
        return 1

    # --- JSON output mode ---
    if args.json_out:
        result = asdict(agent)
        if args.session:
            node = load_node(args.node or args.agent)
            if node:
                result["node"] = asdict(node)
        print(json_mod.dumps(result, indent=2))
        return 0

    # --- ANSI render modes ---
    if args.session:
        node = load_node(args.node or args.agent)
        print(session_header(agent, node))
    elif args.status:
        print(render_status_bar(agent, args.status))
    elif args.banner:
        print(render_banner(agent))
    else:
        print(render_banner(agent))

    return 0


if __name__ == "__main__":
    sys.exit(main())
