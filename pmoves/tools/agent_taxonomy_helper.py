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


def _load_signatures():
    """Load agent signatures indexed by agent_id."""
    if yaml is None or not SIGNATURES_PATH.exists():
        return {}
    with open(SIGNATURES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("signatures", {})


def _load_themes():
    """Load agent theme packs and agent-to-character mappings."""
    if yaml is None or not THEMES_PATH.exists():
        return {}, {}
    with open(THEMES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("theme_packs", {}), data.get("agent_theme_map", {})


def _fg(hex_color: str, text: str) -> str:
    """24-bit ANSI foreground color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return text
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m{text}\033[0m"


def _bg(hex_color: str, text: str) -> str:
    """24-bit ANSI background color."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return text
    r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[48;2;{r};{g};{b}m{text}\033[0m"


def _color_swatch(hex_color: str) -> str:
    """Render a small color swatch block."""
    return _bg(hex_color, "  ")


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
        # Runtime id -> registry key is NOT always reversible, so the hyphen/underscore
        # swap above is not sufficient on its own.
        #
        # Registry keys must match validate_agent_registry.SNAKE (^[a-z][a-z0-9_]*$) —
        # they must begin with a LETTER. Runtime ids match KEBAB
        # (^[a-z0-9][a-z0-9.-]*$) and may begin with a DIGIT. For an id like
        # `4090-claude` the only underscore form is `4090_claude`, which is an
        # ILLEGAL key, so no registry key can ever derive from it. Those entries
        # carry the runtime id in `signature` instead (the same field agent_zero
        # uses to point at `claude-opus`).
        #
        # Without this branch such an agent is registered but unreachable under the
        # id the rest of the repo actually uses — present in the file, invisible to
        # the lookup.
        # Resolve ONLY on a unique hit. `signature` is not a unique key —
        # `claude-opus` is carried by six agents (agent_zero plus the four
        # observability specialists and llm_observability). Taking the first match
        # would answer an ambiguous question with a confident wrong card, which is
        # worse than not resolving at all.
        wanted = {args.name.lower(), agent_id}
        by_signature = [
            key for key, entry in agents.items()
            if str((entry or {}).get("signature", "")).lower() in wanted
        ]
        if len(by_signature) == 1:
            agent_id = by_signature[0]
            agent = agents[agent_id]
        elif len(by_signature) > 1:
            print(
                f"'{args.name}' is a signature shared by {len(by_signature)} agents: "
                f"{', '.join(sorted(by_signature))}. Ask for one by its registry key.",
                file=sys.stderr,
            )
            sys.exit(1)

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

    print("╔══════════════════════════════════════════╗")
    print(f"║  {agent.get('name', agent_id):^38}  ║")
    print("╠══════════════════════════════════════════╣")
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
    # `submodule` is for real gitlinks; `path` is for first-party in-repo code.
    # Both are shown, labelled honestly, so a reader is never told to
    # `git submodule update --init` something that is not a submodule.
    if agent.get("submodule"):
        print(f"║  Submodule: {agent['submodule']:<28} ║")
    elif agent.get("path"):
        print(f"║  Path:      {agent['path']:<28} ║")
    print("╠══════════════════════════════════════════╣")
    print("║  CHIT Toggles:                           ║")
    for k, v in toggles.items():
        icon = "●" if v else "○"
        print(f"║    {icon} {k:<36} ║")
    print("╠══════════════════════════════════════════╣")
    print("║  NATS Subjects:                          ║")
    pubs = nats.get("publishes", [])
    subs = nats.get("subscribes", [])
    if pubs:
        for p in pubs:
            print(f"║    PUB  {p:<32} ║")
    if subs:
        for s in subs:
            print(f"║    SUB  {s:<32} ║")
    if not pubs and not subs:
        print("║    (none)                                ║")
    print("╠══════════════════════════════════════════╣")
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
    print("╚══════════════════════════════════════════╝")


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


def cmd_render_card(registry, args):
    """Render a themed agent identity card with ANSI colors."""
    sigs = _load_signatures()
    theme_packs, theme_map = _load_themes()

    agent_id = args.name.lower().replace(" ", "-")
    sig = sigs.get(agent_id)
    if not sig:
        # Fuzzy match
        matches = [k for k in sigs if agent_id in k]
        if matches:
            agent_id = matches[0]
            sig = sigs[agent_id]
        else:
            print(f"Agent '{args.name}' not found in signatures. Available: {', '.join(sorted(sigs.keys()))}", file=sys.stderr)
            sys.exit(1)

    fmt = args.card_format

    if fmt == "json":
        entry = {"agent_id": agent_id, **sig}
        mapping = theme_map.get(agent_id.replace("-", "_").replace("_", "-"), theme_map.get(agent_id, {}))
        if mapping:
            entry["theme_mapping"] = mapping
        print(json.dumps(entry, indent=2, ensure_ascii=False))
        return

    if fmt == "minimal":
        glyph = sig.get("glyph", "?")
        color = sig.get("color", "#888888")
        voice = sig.get("voice", "unknown")
        display = sig.get("display_name", agent_id)
        print(f"{_fg(color, glyph)} {display} | {_color_swatch(color)} {color} | voice: {voice}")
        alters = sig.get("alters", [])
        for alt in alters:
            alt_glyph = alt.get("glyph", "?")
            alt_color = alt.get("color", "#888888")
            print(f"  {_fg(alt_color, alt_glyph)} {alt.get('name', '?')} | {_color_swatch(alt_color)} {alt_color} | voice: {alt.get('voice', '?')}")
        return

    # Terminal format — full ANSI box
    w = 50
    glyph = sig.get("glyph", "?")
    color = sig.get("color", "#888888")
    accent = sig.get("accent", color)
    display = sig.get("display_name", agent_id)
    voice = sig.get("voice", "unknown")
    co_author = sig.get("co_author", "")
    resonance = sig.get("resonance", [])
    sig.get("description", "")
    alters = sig.get("alters", [])

    def box_line(text, pad=w - 4):
        return f"║  {text:<{pad}}║"

    print(f"╔{'═' * (w - 2)}╗")
    title = f"{_fg(color, glyph)}  {_fg(color, display)}"
    # Can't pad ANSI strings normally, just print
    print(f"║  {title}{'':>{w - len(display) - len(glyph) - 7}}║")
    print(f"╠{'═' * (w - 2)}╣")
    print(box_line(f"ID:       {agent_id}"))
    print(box_line(f"Color:    {_color_swatch(color)} {color}  {_color_swatch(accent)} {accent}"))
    print(box_line(f"Voice:    {voice}"))
    print(box_line(f"Resonance: {', '.join(resonance[:4])}"))
    if len(resonance) > 4:
        print(box_line(f"          {', '.join(resonance[4:])}"))
    if co_author:
        print(box_line(f"Author:   {co_author[:w - 14]}"))

    # Theme mapping
    agent_key = agent_id.replace("-", "_").replace("_", "-")
    mapping = theme_map.get(agent_key, theme_map.get(agent_id.replace("-", "_"), {}))
    if mapping:
        primary = mapping.get("primary", "")
        secondary = mapping.get("secondary", "")
        rationale = mapping.get("rationale", "")
        print(f"╠{'═' * (w - 2)}╣")
        print(box_line("Theme:"))
        if primary:
            # Resolve character name from theme pack
            parts = primary.split("/")
            if len(parts) == 2:
                pack = theme_packs.get(parts[0], {})
                char = pack.get("characters", {}).get(parts[1], {})
                char_name = char.get("name", parts[1])
                print(box_line(f"  Primary:   {char_name} ({parts[0]})"))
            else:
                print(box_line(f"  Primary:   {primary}"))
        if secondary:
            parts = secondary.split("/")
            if len(parts) == 2:
                pack = theme_packs.get(parts[0], {})
                char = pack.get("characters", {}).get(parts[1], {})
                char_name = char.get("name", parts[1])
                print(box_line(f"  Secondary: {char_name} ({parts[0]})"))
            else:
                print(box_line(f"  Secondary: {secondary}"))
        if rationale:
            print(box_line(f"  {rationale[:w - 6]}"))

    # Alters
    if alters:
        print(f"╠{'═' * (w - 2)}╣")
        print(box_line(f"Alters ({len(alters)}):"))
        for alt in alters:
            alt_glyph = alt.get("glyph", "?")
            alt_color = alt.get("color", "#888888")
            alt_name = alt.get("name", "?")
            alt_voice = alt.get("voice", "?")
            print(box_line(f"  {_fg(alt_color, alt_glyph)} {alt_name}  {_color_swatch(alt_color)} {alt_color}"))
            print(box_line(f"    voice: {alt_voice}"))
            alt_res = alt.get("resonance", [])
            if alt_res:
                print(box_line(f"    {', '.join(alt_res[:4])}"))
            alt_desc = alt.get("description", "")
            if alt_desc:
                # Word-wrap
                words = alt_desc.split()
                line = "    "
                for word in words:
                    if len(line) + len(word) + 1 > w - 6:
                        print(box_line(line))
                        line = "    " + word
                    else:
                        line = line + " " + word if line.strip() else "    " + word
                if line.strip():
                    print(box_line(line))

    print(f"╚{'═' * (w - 2)}╝")


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

    render_card_parser = subparsers.add_parser("render-card", help="Render themed agent identity card")
    render_card_parser.add_argument("name", help="Agent signature ID (e.g. 4090-claude)")
    render_card_parser.add_argument("--card-format", choices=["terminal", "json", "minimal"],
                                    default="terminal", help="Output format (default: terminal)")

    mermaid_parser = subparsers.add_parser("mermaid", help="Generate Mermaid diagram")
    mermaid_parser.add_argument("--style", choices=["topology", "tac", "nats"],
                                default="topology", help="Diagram style (default: topology)")

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
        "render-card": cmd_render_card,
        "mermaid": cmd_mermaid,
    }

    commands[args.command](registry, args)


if __name__ == "__main__":
    main()
