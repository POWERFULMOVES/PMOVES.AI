#!/usr/bin/env python3
"""PMOVES Agent Taxonomy Helper — CLI tool for querying the agent registry.

Usage:
    python -m pmoves.tools.agent_taxonomy_helper list          # all agents, table format
    python -m pmoves.tools.agent_taxonomy_helper show <name>   # single agent card
    python -m pmoves.tools.agent_taxonomy_helper connections    # network graph (JSON)
    python -m pmoves.tools.agent_taxonomy_helper types          # type effectiveness chart
    python -m pmoves.tools.agent_taxonomy_helper mermaid        # Mermaid diagram (topology|tac|nats)

Registry: pmoves/config/agent_registry.yaml
Docs:     pmoves/docs/AGENTS/PMOVES_AGENT_CLASS_TAXONOMY.md
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    import yaml
except ImportError:
    yaml = None  # Fallback to manual parsing not needed — PyYAML is standard


REGISTRY_PATH = Path(__file__).parent.parent / "config" / "agent_registry.yaml"
SIGNATURES_PATH = Path(__file__).parent.parent / "config" / "agent_signatures.yaml"
THEMES_PATH = Path(__file__).parent.parent / "configs" / "agent-themes.yaml"

# Type effectiveness matrix (attacker → target → effectiveness)
TYPE_EFFECTIVENESS = {
    "agent":  {"worker": "super", "llm": "super", "data": "effective", "api": "effective", "media": "effective", "agent": "neutral", "ui": "effective"},
    "worker": {"data": "super", "agent": "effective", "worker": "neutral", "llm": "neutral", "media": "neutral", "api": "neutral", "ui": "neutral"},
    "media":  {"worker": "super", "data": "effective", "media": "neutral", "llm": "neutral", "api": "neutral", "agent": "neutral", "ui": "effective"},
    "llm":    {"data": "super", "worker": "effective", "llm": "neutral", "api": "effective", "media": "neutral", "agent": "neutral", "ui": "neutral"},
    "api":    {"data": "effective", "llm": "effective", "worker": "effective", "api": "neutral", "media": "neutral", "agent": "neutral", "ui": "effective"},
    "data":   {"api": "effective", "data": "neutral", "llm": "neutral", "worker": "neutral", "media": "neutral", "agent": "neutral", "ui": "neutral"},
    "ui":     {"agent": "effective", "ui": "neutral", "data": "neutral", "llm": "neutral", "worker": "neutral", "media": "neutral", "api": "neutral"},
}


def load_registry():
    """Load agent registry from YAML."""
    if yaml is None:
        print("Error: PyYAML required. Install with: uv pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    if not REGISTRY_PATH.exists():
        print(f"Error: Registry not found at {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        print(f"Error: Failed to parse registry YAML:\n  {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("Error: Registry is empty or not a YAML mapping", file=sys.stderr)
        sys.exit(1)
    return data


def cmd_list(registry, args):
    """List all agents in table format."""
    agents = registry.get("agents", {})
    fmt = args.format

    if fmt == "json":
        print(json.dumps(agents, indent=2))
        return

    # Table format
    header = f"{'ID':<22} {'Name':<24} {'Class':<13} {'Type':<14} {'Tier':<5} {'Port':<6} {'Layers':<8} {'Stage':<10}"
    print(header)
    print("─" * len(header))

    types_def = registry.get("types", {})
    for aid, agent in sorted(agents.items()):
        primary = agent.get("primary_type", "")
        secondary = agent.get("secondary_type", "")
        type_str = f"{primary}/{secondary}" if secondary else primary
        tier = types_def.get(primary, {}).get("tier", "?")
        layers = len(agent.get("layers", []))
        port = agent.get("port") or "—"
        stage = agent.get("evolution_stage", "base")
        cls = agent.get("class", "?")
        name = agent.get("name", aid)
        print(f"{aid:<22} {name:<24} {cls:<13} {type_str:<14} {tier:<5} {str(port):<6} {layers:<8} {stage:<10}")

    print(f"\nTotal: {len(agents)} agents")


def cmd_show(registry, args):
    """Show a single agent card."""
    agents = registry.get("agents", {})
    types_def = registry.get("types", {})
    classes_def = registry.get("classes", {})

    agent_id = args.name.lower().replace("-", "_").replace(" ", "_")
    agent = agents.get(agent_id)
    if not agent:
        # Fuzzy match
        matches = [k for k in agents if agent_id in k or agent_id in agents[k].get("name", "").lower()]
        if matches:
            agent_id = matches[0]
            agent = agents[agent_id]
        else:
            print(f"Agent '{args.name}' not found. Available: {', '.join(sorted(agents.keys()))}", file=sys.stderr)
            sys.exit(1)

    primary = agent.get("primary_type", "")
    secondary = agent.get("secondary_type", "")
    cls = agent.get("class", "?")
    cls_info = classes_def.get(cls, {})
    type_info = types_def.get(primary, {})
    layers = agent.get("layers", [])
    toggles = agent.get("chit_toggles", {})
    nats = agent.get("nats", {})

    print(f"╔══════════════════════════════════════════╗")
    print(f"║  {agent.get('name', agent_id):^38}  ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  ID:        {agent_id:<28} ║")
    print(f"║  Class:     {cls:<12} ({cls_info.get('prefix', '?')})       ║")
    type_display = f"{primary}/{secondary}" if secondary else primary
    print(f"║  Type:      {type_display:<28} ║")
    print(f"║  Element:   {type_info.get('element', '?'):<28} ║")
    print(f"║  Tier:      {type_info.get('tier', '?'):<28} ║")
    print(f"║  Port:      {str(agent.get('port') or '—'):<28} ║")
    print(f"║  Health:    {str(agent.get('health') or '—'):<28} ║")
    print(f"║  Stage:     {agent.get('evolution_stage', 'base'):<28} ║")
    print(f"║  Layers:    {', '.join(layers):<28} ║")
    if agent.get("submodule"):
        print(f"║  Submodule: {agent['submodule']:<28} ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  CHIT Toggles:                           ║")
    for k, v in toggles.items():
        icon = "●" if v else "○"
        print(f"║    {icon} {k:<36} ║")
    print(f"╠══════════════════════════════════════════╣")
    print(f"║  NATS Subjects:                          ║")
    pubs = nats.get("publishes", [])
    subs = nats.get("subscribes", [])
    if pubs:
        for p in pubs:
            print(f"║    PUB  {p:<32} ║")
    if subs:
        for s in subs:
            print(f"║    SUB  {s:<32} ║")
    if not pubs and not subs:
        print(f"║    (none)                                ║")
    print(f"╠══════════════════════════════════════════╣")
    desc = agent.get("description", "")
    # Word-wrap description to 38 chars
    words = desc.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 <= 38:
            current = f"{current} {w}" if current else w
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    for line in lines:
        print(f"║  {line:<38}  ║")
    print(f"╚══════════════════════════════════════════╝")


def cmd_connections(registry, args):
    """Output network graph as JSON (nodes + edges from NATS subject overlaps)."""
    agents = registry.get("agents", {})
    types_def = registry.get("types", {})

    nodes = []
    edges = []

    # Build subject → publisher/subscriber maps
    publishers = {}   # subject → [agent_id]
    subscribers = {}  # subject → [agent_id]

    for aid, agent in agents.items():
        nats = agent.get("nats", {})
        layers = agent.get("layers", [])
        nodes.append({
            "id": aid,
            "name": agent.get("name", aid),
            "class": agent.get("class", "?"),
            "primary_type": agent.get("primary_type", "?"),
            "secondary_type": agent.get("secondary_type", ""),
            "tier": types_def.get(agent.get("primary_type", ""), {}).get("tier", "?"),
            "layers": len(layers),
            "evolution_stage": agent.get("evolution_stage", "base"),
            "port": agent.get("port"),
        })
        for subj in nats.get("publishes", []):
            publishers.setdefault(subj, []).append(aid)
        for subj in nats.get("subscribes", []):
            subscribers.setdefault(subj, []).append(aid)

    # Create edges where publishers meet subscribers
    for subj in set(publishers.keys()) | set(subscribers.keys()):
        pubs = publishers.get(subj, [])
        subs = subscribers.get(subj, [])
        for pub in pubs:
            for sub in subs:
                if pub != sub:
                    edges.append({
                        "source": pub,
                        "target": sub,
                        "via": subj,
                        "type": "nats_event",
                    })

    graph = {"nodes": nodes, "edges": edges}

    print(json.dumps(graph, indent=2))


def cmd_types(registry, args):
    """Display type effectiveness chart."""
    types_def = registry.get("types", {})
    type_names = sorted(types_def.keys(), key=lambda t: types_def[t].get("tier", 0))

    # Header
    header = f"{'Attacker ↓ / Target →':<24}"
    for t in type_names:
        header += f" {t:<8}"
    print(header)
    print("─" * len(header))

    for attacker in type_names:
        row = f"{attacker:<24}"
        for target in type_names:
            eff = TYPE_EFFECTIVENESS.get(attacker, {}).get(target, "neutral")
            if eff == "super":
                icon = "★★"
            elif eff == "effective":
                icon = "★ "
            else:
                icon = "· "
            row += f" {icon:<8}"
        print(row)

    print()
    print("★★ = Super effective  ★  = Effective  ·  = Neutral")


SUBSYSTEM_MAP = {
    "AGENT_ZERO_CORE": {
        "label": "Agent Zero Core — The Matrix",
        "agents": ["agent_zero"],
    },
    "ARCHON_NEXUS": {
        "label": "Archon Nexus — External Data Gate",
        "agents": ["archon"],
    },
    "BOTZ_SHIP": {
        "label": "BoTZ Ship — Agent Runtime",
        "agents": ["botz_gateway", "gateway_agent"],
    },
    "DOX_INTEL": {
        "label": "DoX Intel — Document Intelligence",
        "agents": ["dox"],
    },
    "RESEARCH_KNOWLEDGE": {
        "label": "Research & Knowledge",
        "agents": ["supaserch", "deep_research", "hirag_v2", "open_notebook"],
    },
    "MEDIA_PIPELINE": {
        "label": "Media Pipeline",
        "agents": ["pmoves_yt", "ffmpeg_whisper", "media_video", "media_audio",
                    "channel_monitor", "extract_worker", "langextract"],
    },
    "VOICE_COMMS": {
        "label": "Voice & Comms — Flute",
        "agents": ["flute_gateway", "ultimate_tts"],
    },
    "CIPHER_EVOLUTION": {
        "label": "Cipher Evolution Backbone",
        "agents": ["cipher_memory", "consciousness_service", "evoswarm_controller",
                    "swarm_attribution"],
    },
    "AGENT_TRAINING": {
        "label": "Agent Training & Sandbox",
        "agents": ["agentgym", "agentgym_rl", "e2b_danger_room", "e2b_desktop",
                    "danger_infra", "e2b_spells", "surf"],
    },
    "UI_FRONTEND": {
        "label": "UI & Frontend",
        "agents": ["mai_ui", "a2ui", "crush", "hyperdimensions"],
    },
    "PERSISTENCE": {
        "label": "Persistence — CHIT Data Stores",
        "agents": ["supabase", "qdrant", "neo4j", "meilisearch", "minio"],
    },
    "INFRA": {
        "label": "Infrastructure Backbone",
        "agents": ["nats", "tensorzero", "prometheus", "grafana", "loki",
                    "n8n", "headscale", "rustdesk", "invidious"],
    },
    "DOMAIN_APPS": {
        "label": "Domain Applications",
        "agents": ["wealth", "health", "creator", "llama_lab", "jellyfin_bridge",
                    "jellyfin_ai", "transcribe_and_fetch", "pdf_ingest",
                    "notebook_sync", "publisher_discord", "presign",
                    "render_webhook", "mesh_agent"],
    },
}

# Class colors for Mermaid classDef
CLASS_COLORS = {
    "legendary": {"fill": "#FFD700", "stroke": "#B8860B", "color": "#000"},
    "standard":  {"fill": "#9370DB", "stroke": "#6A0DAD", "color": "#fff"},
    "specialized": {"fill": "#00CED1", "stroke": "#008B8B", "color": "#000"},
    "utility":   {"fill": "#A9A9A9", "stroke": "#696969", "color": "#000"},
}


def _append_class_defs(lines):
    """Append Mermaid classDef styles for agent classes."""
    for cls, colors in CLASS_COLORS.items():
        lines.append(f"    classDef {cls} fill:{colors['fill']},stroke:{colors['stroke']},color:{colors['color']}")


def cmd_mermaid(registry, args):
    """Generate Mermaid diagram from agent registry."""
    style = args.style
    agents = registry.get("agents", {})

    handlers = {"topology": _mermaid_topology, "tac": _mermaid_tac, "nats": _mermaid_nats}
    handler = handlers.get(style)
    if handler is None:
        print(f"Error: Unknown mermaid style '{style}'. Available: {', '.join(handlers)}", file=sys.stderr)
        sys.exit(1)
    handler(agents)


def _mermaid_topology(agents):
    """Generate master topology graph TD with subgraphs."""
    # Validate SUBSYSTEM_MAP coverage
    mapped = set()
    for sg in SUBSYSTEM_MAP.values():
        for aid in sg["agents"]:
            mapped.add(aid)
            if aid not in agents:
                print(f"Warning: SUBSYSTEM_MAP references '{aid}' not in registry", file=sys.stderr)
    orphans = set(agents.keys()) - mapped
    if orphans:
        print(f"Warning: {len(orphans)} agent(s) not in any subsystem: {', '.join(sorted(orphans))}", file=sys.stderr)

    lines = ["graph TD"]
    _append_class_defs(lines)
    lines.append("")

    # Subgraphs
    for sg_id, sg in SUBSYSTEM_MAP.items():
        lines.append(f"    subgraph {sg_id}[\"{sg['label']}\"]")
        for aid in sg["agents"]:
            agent = agents.get(aid)
            if agent:
                name = agent.get("name", aid)
                port = agent.get("port")
                label = f"{name}<br/>:{port}" if port else name
                cls = agent.get("class", "utility")
                lines.append(f"        {aid}[\"{label}\"]:::{cls}")
        lines.append("    end")
        lines.append("")

    # Core connections (MCP / orchestration)
    lines.append("    %% MCP / orchestration links")
    lines.append("    agent_zero --> archon")
    lines.append("    agent_zero --> botz_gateway")
    lines.append("    agent_zero --> mesh_agent")
    lines.append("    agent_zero --> supaserch")
    lines.append("    agent_zero --> deep_research")
    lines.append("    archon --> tensorzero")
    lines.append("    botz_gateway --> gateway_agent")
    lines.append("")

    # Data flow (dotted)
    lines.append("    %% Data flow")
    lines.append("    extract_worker -.-> qdrant")
    lines.append("    extract_worker -.-> meilisearch")
    lines.append("    hirag_v2 -.-> qdrant")
    lines.append("    hirag_v2 -.-> neo4j")
    lines.append("    hirag_v2 -.-> meilisearch")
    lines.append("    cipher_memory -.-> neo4j")
    lines.append("")

    # NATS connections (dashed)
    lines.append("    %% NATS pub/sub")
    lines.append("    pmoves_yt -.- |NATS| extract_worker")
    lines.append("    pmoves_yt -.- |NATS| publisher_discord")
    lines.append("    mesh_agent -.- |NATS| agent_zero")
    lines.append("    flute_gateway -.- |NATS| hirag_v2")
    lines.append("    evoswarm_controller -.- |NATS| swarm_attribution")

    print("\n".join(lines))


def _mermaid_tac(agents):
    """Generate TAC hierarchy graph TD."""
    lines = ["graph TD"]
    _append_class_defs(lines)
    lines.append("")
    lines.append("    PMOVES[\"POWERFULMOVES\"]:::legendary")
    lines.append("    PMOVES --> agent_zero")
    lines.append("")

    # Group agents by class
    by_class = {}
    for aid, agent in agents.items():
        cls = agent.get("class", "utility")
        by_class.setdefault(cls, []).append((aid, agent))

    for cls in ["standard", "specialized", "utility"]:
        for aid, agent in sorted(by_class.get(cls, [])):
            name = agent.get("name", aid)
            lines.append(f"    {aid}[\"{name}\"]:::{cls}")

    lines.append("")

    # Connections from Agent Zero to major subsystem heads
    lines.append("    agent_zero --> archon")
    lines.append("    agent_zero --> botz_gateway")
    lines.append("    agent_zero --> supaserch")
    lines.append("    agent_zero --> deep_research")
    lines.append("    agent_zero --> dox")
    lines.append("    agent_zero --> flute_gateway")
    lines.append("    agent_zero --> cipher_memory")
    lines.append("    agent_zero --> evoswarm_controller")
    lines.append("    agent_zero --> mai_ui")
    lines.append("")

    # Subsystem internal links
    lines.append("    archon --> tensorzero")
    lines.append("    botz_gateway --> gateway_agent")
    lines.append("    supaserch --> hirag_v2")
    lines.append("    deep_research --> open_notebook")

    print("\n".join(lines))


def _mermaid_nats(agents):
    """Generate NATS nervous system graph LR — only agents with NATS subjects."""
    lines = ["graph LR"]
    _append_class_defs(lines)
    lines.append("    classDef subject fill:#FFF3E0,stroke:#FF9800,color:#000")
    lines.append("")

    publishers = {}   # subject -> [agent_id]
    subscribers = {}  # subject -> [agent_id]
    nats_agents = set()

    for aid, agent in agents.items():
        nats = agent.get("nats", {})
        pubs = nats.get("publishes", [])
        subs = nats.get("subscribes", [])
        if pubs or subs:
            nats_agents.add(aid)
            cls = agent.get("class", "utility")
            name = agent.get("name", aid)
            lines.append(f"    {aid}[\"{name}\"]:::{cls}")
        for subj in pubs:
            publishers.setdefault(subj, []).append(aid)
        for subj in subs:
            subscribers.setdefault(subj, []).append(aid)

    lines.append("")

    # Subject nodes
    all_subjects = sorted(set(publishers.keys()) | set(subscribers.keys()))
    for subj in all_subjects:
        node_id = subj.replace(".", "_")
        lines.append(f"    {node_id}{{\"{subj}\"}}:::subject")

    lines.append("")

    # Edges: publisher --> subject --> subscriber
    for subj in all_subjects:
        node_id = subj.replace(".", "_")
        for pub in publishers.get(subj, []):
            lines.append(f"    {pub} --> {node_id}")
        for sub in subscribers.get(subj, []):
            lines.append(f"    {node_id} --> {sub}")

    print("\n".join(lines))


def _load_signatures():
    """Load agent signatures YAML."""
    if yaml is None or not SIGNATURES_PATH.exists():
        return {}
    with open(SIGNATURES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("agents", data)


def _load_themes():
    """Load agent themes YAML."""
    if yaml is None or not THEMES_PATH.exists():
        return {}
    with open(THEMES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _hex_to_ansi(hex_color: str) -> str:
    """Convert #RRGGBB to ANSI 24-bit color escape."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return ""
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


def _reset() -> str:
    return "\033[0m"


def _bold() -> str:
    return "\033[1m"


def _dim() -> str:
    return "\033[2m"


def _find_character_mapping(themes: dict, agent_id: str) -> dict:
    """Find character mapping for an agent across all theme packs."""
    mappings = themes.get("service_character_mappings", {})
    for service_key, mapping in mappings.items():
        # Match by agent_id or service name
        sid = service_key.lower().replace("-", "_").replace(" ", "_")
        if agent_id in sid or sid in agent_id:
            return mapping
    return {}


def cmd_render_card(registry, args):
    """Render a themed agent card with signature colors and character mapping."""
    agents = registry.get("agents", {})
    signatures = _load_signatures()
    themes = _load_themes()

    agent_id = args.name.lower().replace("-", "_").replace(" ", "_")
    agent = agents.get(agent_id)

    # Try signature lookup by agent_id or with hyphens
    sig_id = agent_id.replace("_", "-")
    sig = signatures.get(sig_id) or signatures.get(agent_id)

    if not agent and not sig:
        # Fuzzy match
        all_keys = set(agents.keys()) | set(signatures.keys())
        matches = [k for k in all_keys if agent_id in k]
        if matches:
            key = matches[0]
            agent = agents.get(key) or agents.get(key.replace("-", "_"))
            sig = signatures.get(key) or signatures.get(key.replace("_", "-"))
            agent_id = key
        else:
            print(f"Agent '{args.name}' not found.", file=sys.stderr)
            print(f"Registry agents: {', '.join(sorted(agents.keys()))}", file=sys.stderr)
            print(f"Signature agents: {', '.join(sorted(signatures.keys()))}", file=sys.stderr)
            sys.exit(1)

    fmt = args.format

    if fmt == "json":
        card = {"agent_id": agent_id}
        if sig:
            card.update(sig)
        if agent:
            card["registry"] = agent
        char_map = _find_character_mapping(themes, agent_id)
        if char_map:
            card["character_mapping"] = char_map
        print(json.dumps(card, indent=2))
        return

    # Terminal (ANSI) rendering
    glyph = (sig or {}).get("glyph", "?")
    color = (sig or {}).get("color", "#FFFFFF")
    accent = (sig or {}).get("accent", "#CCCCCC")
    voice = (sig or {}).get("voice", "unknown")
    resonance = (sig or {}).get("resonance", [])
    co_author = (sig or {}).get("co_author", "")
    description = (sig or agent or {}).get("description", "")
    display_name = (sig or {}).get("display_name", "") or (agent or {}).get("name", agent_id)

    c = _hex_to_ansi(color)
    a = _hex_to_ansi(accent)
    b = _bold()
    d = _dim()
    r = _reset()

    char_map = _find_character_mapping(themes, agent_id)
    primary_char = char_map.get("primary", "")
    secondary_char = char_map.get("secondary", "")
    rationale = char_map.get("rationale", "")

    width = 46
    border = f"{c}{'═' * width}{r}"
    line = f"{c}{'─' * width}{r}"

    print(f"{c}╔{border}╗{r}")
    print(f"{c}║{r}  {c}{b}{glyph}  {display_name}{r}{' ' * (width - len(display_name) - 5)}{c}║{r}")
    print(f"{c}║{r}  {d}{color}{r}{' ' * (width - len(color) - 2)}{c}║{r}")
    print(f"{c}╠{line}╣{r}")
    print(f"{c}║{r}  {a}Voice:{r}      {voice}{' ' * (width - len(voice) - 14)}{c}║{r}")

    if resonance:
        res_str = ", ".join(resonance[:4])
        print(f"{c}║{r}  {a}Resonance:{r}  {res_str}{' ' * max(0, width - len(res_str) - 14)}{c}║{r}")

    if agent:
        port = agent.get("port", "—")
        cls = agent.get("class", "—")
        stage = agent.get("evolution_stage", "base")
        print(f"{c}║{r}  {a}Class:{r}      {cls}{' ' * (width - len(str(cls)) - 14)}{c}║{r}")
        print(f"{c}║{r}  {a}Port:{r}       {port}{' ' * (width - len(str(port)) - 14)}{c}║{r}")
        print(f"{c}║{r}  {a}Stage:{r}      {stage}{' ' * (width - len(str(stage)) - 14)}{c}║{r}")

    if primary_char or secondary_char:
        print(f"{c}╠{line}╣{r}")
        if primary_char:
            print(f"{c}║{r}  {b}Primary:{r}    {primary_char}{' ' * max(0, width - len(primary_char) - 14)}{c}║{r}")
        if secondary_char:
            print(f"{c}║{r}  {b}Secondary:{r}  {secondary_char}{' ' * max(0, width - len(secondary_char) - 14)}{c}║{r}")

    if description:
        print(f"{c}╠{line}╣{r}")
        words = description.split()
        lines = []
        current = ""
        for w in words:
            if len(current) + len(w) + 1 <= width - 4:
                current = f"{current} {w}" if current else w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        for ln in lines:
            print(f"{c}║{r}  {d}{ln}{r}{' ' * max(0, width - len(ln) - 2)}{c}║{r}")

    print(f"{c}╚{border}╝{r}")


def main():
    parser = argparse.ArgumentParser(
        description="PMOVES Agent Taxonomy Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--format", choices=["table", "json"], default="table",
                        help="Output format (default: table)")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("list", help="List all agents")

    show_parser = subparsers.add_parser("show", help="Show agent card")
    show_parser.add_argument("name", help="Agent ID or name (fuzzy match)")

    subparsers.add_parser("connections", help="Network graph (JSON)")

    subparsers.add_parser("types", help="Type effectiveness chart")

    mermaid_parser = subparsers.add_parser("mermaid", help="Generate Mermaid diagram")
    mermaid_parser.add_argument("--style", choices=["topology", "tac", "nats"],
                                default="topology", help="Diagram style (default: topology)")

    card_parser = subparsers.add_parser("render-card", help="Render themed agent card (ANSI/JSON)")
    card_parser.add_argument("name", help="Agent ID or name (fuzzy match)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    registry = load_registry()

    commands = {
        "list": cmd_list,
        "show": cmd_show,
        "connections": cmd_connections,
        "types": cmd_types,
        "mermaid": cmd_mermaid,
        "render-card": cmd_render_card,
    }

    commands[args.command](registry, args)


if __name__ == "__main__":
    main()
