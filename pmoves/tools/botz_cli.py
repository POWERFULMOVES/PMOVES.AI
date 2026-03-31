#!/usr/bin/env python3
"""BoTZ CLI — Agent Persona Selector + Identity Tool

W6-P3 deliverable: CLI for selecting agent personas, resolving identity,
applying terminal themes, planning, and auditing across PMOVES nodes.

Usage:
    python pmoves/tools/botz_cli.py whoami
    python pmoves/tools/botz_cli.py theme 4090-claude
    python pmoves/tools/botz_cli.py persona list
    python pmoves/tools/botz_cli.py persona select 4090-claude
    python pmoves/tools/botz_cli.py plan -d "Add NATS wiring to Health service"
    python pmoves/tools/botz_cli.py audit -t pmoves/tools/provider_cascade.py

Shell integration (set persona for current session):
    eval $(python pmoves/tools/botz_cli.py persona select 4090-claude --export)
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_TOOLS_DIR = Path(__file__).resolve().parent
_PMOVES_ROOT = _TOOLS_DIR.parent
_SIGNATURES_PATH = _PMOVES_ROOT / "config" / "agent_signatures.yaml"
_BOTZ_GATEWAY_URL = os.getenv("BOTZ_GATEWAY_URL", "http://localhost:8054")


# ---------------------------------------------------------------------------
# ANSI helpers (minimal — full rendering delegates to agent_terminal_theme)
# ---------------------------------------------------------------------------
def _supports_color() -> bool:
    """Return whether the terminal supports ANSI color output."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if sys.platform == "win32":
        return os.environ.get("WT_SESSION") is not None or "TERM_PROGRAM" in os.environ
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _fg(hex_color: str) -> str:
    """Return ANSI escape sequence for the given hex foreground color."""
    if not _supports_color():
        return ""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


_RST = "\033[0m" if _supports_color() else ""
_BOLD = "\033[1m" if _supports_color() else ""
_DIM = "\033[2m" if _supports_color() else ""


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def _load_signatures() -> Dict[str, Any]:
    """Load agent signatures from YAML."""
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml required (pip install pyyaml)", file=sys.stderr)
        return {}
    if not _SIGNATURES_PATH.exists():
        print(f"ERROR: {_SIGNATURES_PATH} not found", file=sys.stderr)
        return {}
    with open(_SIGNATURES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("signatures", {})


def _resolve_agent_id() -> tuple[str, str]:
    """Resolve current agent identity. Returns (agent_id, source)."""
    agent_id = os.environ.get("PMOVES_AGENT_ID")
    if agent_id:
        return agent_id, "env"

    hostname = socket.gethostname().lower()
    host_map = {
        "z890": "z890-claude",
        "pmoves-z890": "z890-claude",
        "powerfulmoves": "5090-claude",
        "pmoves-powerfulmoves": "5090-claude",
        "laptop": "4090-claude",
        "pmoves-laptop": "4090-claude",
    }
    for pattern, aid in host_map.items():
        if pattern in hostname:
            return aid, "hostname"

    return "unknown", "fallback"


def _alter_name(alter: Dict[str, Any]) -> str:
    """Return the display key used across persona tooling for an alter."""
    return alter.get("name") or alter.get("id") or alter.get("display_name", "?")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_whoami(args: argparse.Namespace) -> int:
    """Resolve and display current agent identity."""
    agent_id, source = _resolve_agent_id()
    sigs = _load_signatures()
    sig = sigs.get(agent_id, {})

    if args.json:
        result = {
            "agent_id": agent_id,
            "source": source,
            "display_name": sig.get("display_name", agent_id),
            "glyph": sig.get("glyph", "?"),
            "color": sig.get("color", "#888888"),
            "voice": sig.get("voice", "unknown"),
            "specialization": sig.get("specialization", ""),
            "resonance": sig.get("resonance", []),
        }
        print(json.dumps(result, indent=2))
    else:
        glyph = sig.get("glyph", "?")
        color = sig.get("color", "#888888")
        name = sig.get("display_name", agent_id)
        spec = sig.get("specialization", "")
        fg = _fg(color)
        print(f"{fg}{_BOLD}{glyph} {name}{_RST}", end="")
        if spec:
            print(f"  {_DIM}[{spec}]{_RST}", end="")
        print(f"  {_DIM}(source: {source}){_RST}")
    return 0


def cmd_theme(args: argparse.Namespace) -> int:
    """Display theme for a specific agent."""
    sigs = _load_signatures()
    sig = sigs.get(args.agent_id)
    if not sig:
        available = ", ".join(sorted(sigs.keys()))
        print(f"ERROR: Agent '{args.agent_id}' not found. Available: {available}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "agent_id": args.agent_id,
            "display_name": sig.get("display_name"),
            "glyph": sig.get("glyph"),
            "color": sig.get("color"),
            "accent": sig.get("accent"),
            "voice": sig.get("voice"),
            "resonance": sig.get("resonance", []),
            "specialization": sig.get("specialization", ""),
            "description": sig.get("description", ""),
            "alters": sig.get("alters", []),
        }, indent=2))
    else:
        fg = _fg(sig.get("color", "#FFF"))
        ac = _fg(sig.get("accent", "#CCC"))
        border = f"{fg}{'━' * 52}{_RST}"
        print(border)
        print(f"{fg}{_BOLD}{sig.get('glyph', '?')} {sig.get('display_name', args.agent_id)}{_RST}")
        spec = sig.get("specialization")
        if spec:
            print(f"{ac}  [{spec}]{_RST}")
        res = sig.get("resonance", [])
        print(f"{ac}  voice: {sig.get('voice', '?')}  |  {', '.join(res[:3])}{_RST}")
        desc = sig.get("description", "")
        if desc:
            print(f"{_DIM}  {desc}{_RST}")
        alters = sig.get("alters", [])
        if alters:
            alter_names = [_alter_name(a) for a in alters]
            print(f"{_DIM}  alters: {', '.join(alter_names)}{_RST}")
        print(border)
    return 0


def cmd_persona_list(args: argparse.Namespace) -> int:
    """List all available personas."""
    sigs = _load_signatures()
    if not sigs:
        print("ERROR: No signatures loaded", file=sys.stderr)
        return 1

    current_id, _ = _resolve_agent_id()

    if args.json:
        personas = []
        for aid, sig in sigs.items():
            entry = {
                "agent_id": aid,
                "display_name": sig.get("display_name", aid),
                "glyph": sig.get("glyph", "?"),
                "color": sig.get("color"),
                "voice": sig.get("voice"),
                "specialization": sig.get("specialization", ""),
                "is_current": aid == current_id,
            }
            alters = sig.get("alters", [])
            if alters:
                entry["alters"] = [_alter_name(a) for a in alters]
            personas.append(entry)
        print(json.dumps(personas, indent=2))
    else:
        print(f"{_BOLD}Available Personas ({len(sigs)}){_RST}")
        print()
        for aid, sig in sigs.items():
            fg = _fg(sig.get("color", "#FFF"))
            glyph = sig.get("glyph", "?")
            name = sig.get("display_name", aid)
            spec = sig.get("specialization", "")
            marker = " *" if aid == current_id else ""
            spec_str = f"  [{spec}]" if spec else ""
            alters = sig.get("alters", [])
            alter_str = f"  +{len(alters)} alters" if alters else ""
            print(f"  {fg}{glyph} {name:<20}{_RST}{spec_str}{alter_str}{_DIM}{marker}{_RST}")
        print()
        if current_id != "unknown":
            print(f"{_DIM}  * = current ({current_id}){_RST}")
    return 0


def cmd_persona_select(args: argparse.Namespace) -> int:
    """Select a persona — outputs shell export commands."""
    sigs = _load_signatures()
    sig = sigs.get(args.agent_id)
    if not sig:
        available = ", ".join(sorted(sigs.keys()))
        print(f"ERROR: Agent '{args.agent_id}' not found. Available: {available}", file=sys.stderr)
        return 1

    if args.export:
        # Shell-evaluable output: eval $(botz_cli.py persona select <id> --export)
        print(f'export PMOVES_AGENT_ID="{args.agent_id}"')
        print(f'export PMOVES_AGENT_GLYPH="{sig.get("glyph", "?")}"')
        print(f'export PMOVES_AGENT_COLOR="{sig.get("color", "#888888")}"')
        print(f'export PMOVES_AGENT_VOICE="{sig.get("voice", "unknown")}"')
        spec = sig.get("specialization", "")
        if spec:
            print(f'export PMOVES_AGENT_SPEC="{spec}"')
    elif args.json:
        print(json.dumps({
            "selected": args.agent_id,
            "display_name": sig.get("display_name"),
            "glyph": sig.get("glyph"),
            "color": sig.get("color"),
            "voice": sig.get("voice"),
            "env": {
                "PMOVES_AGENT_ID": args.agent_id,
                "PMOVES_AGENT_GLYPH": sig.get("glyph", "?"),
                "PMOVES_AGENT_COLOR": sig.get("color", "#888888"),
                "PMOVES_AGENT_VOICE": sig.get("voice", "unknown"),
            },
        }, indent=2))
    else:
        fg = _fg(sig.get("color", "#FFF"))
        glyph = sig.get("glyph", "?")
        name = sig.get("display_name", args.agent_id)
        print(f"{fg}{_BOLD}{glyph} {name}{_RST} selected")
        print()
        print(f"  To apply to your shell session:")
        print(f"  {_DIM}eval $(python {__file__} persona select {args.agent_id} --export){_RST}")
        print()
        print(f"  Or set directly:")
        print(f"  {_DIM}export PMOVES_AGENT_ID={args.agent_id}{_RST}")
    return 0


def cmd_persona_current(args: argparse.Namespace) -> int:
    """Show the currently active persona."""
    agent_id, source = _resolve_agent_id()
    sigs = _load_signatures()
    sig = sigs.get(agent_id, {})

    if args.json:
        print(json.dumps({
            "agent_id": agent_id,
            "source": source,
            "display_name": sig.get("display_name", agent_id),
            "glyph": sig.get("glyph", "?"),
            "color": sig.get("color", "#888888"),
            "voice": sig.get("voice", "unknown"),
        }, indent=2))
    else:
        if agent_id == "unknown":
            print(f"No persona active. Set via: export PMOVES_AGENT_ID=<agent-id>")
        else:
            fg = _fg(sig.get("color", "#888"))
            glyph = sig.get("glyph", "?")
            name = sig.get("display_name", agent_id)
            print(f"{fg}{_BOLD}{glyph} {name}{_RST}  {_DIM}(via {source}){_RST}")
    return 0


# ---------------------------------------------------------------------------
# Shared helper — agent header rendering
# ---------------------------------------------------------------------------
def _render_agent_header(agent_id: str, label: str, value: str) -> str:
    """Render a consistent agent attribution header line."""
    sigs = _load_signatures()
    sig = sigs.get(agent_id, {})
    glyph = sig.get("glyph", "?")
    color = sig.get("color", "#888888")
    name = sig.get("display_name", agent_id)
    fg = _fg(color)
    header = f"{fg}{_BOLD}{glyph} {name}{_RST} | {fg}{color}{_RST} | {label}: {value}"
    print(header)
    return header


# ---------------------------------------------------------------------------
# Plan command (botz-architect persona)
# ---------------------------------------------------------------------------
_PLAN_VERBS = [
    "Analyze", "Design", "Implement", "Validate", "Deploy",
    "Research", "Configure", "Wire", "Test", "Document",
]


def cmd_plan(args: argparse.Namespace) -> int:
    """Create a structured plan using the botz-architect persona."""
    description = args.description
    _render_agent_header("botz-architect", "Plan", description)

    # Generate steps heuristically based on description length
    words = description.split()
    step_count = 3 if len(words) < 8 else 4 if len(words) < 15 else 5

    steps = []
    for i in range(step_count):
        verb = _PLAN_VERBS[i % len(_PLAN_VERBS)]
        if i == 0:
            step = f"{verb} requirements and existing patterns"
        elif i == step_count - 1:
            step = f"{verb} and verify end-to-end"
        else:
            step = f"{verb} core changes for: {description}"
        steps.append({"index": i + 1, "action": step, "status": "pending"})

    if args.json:
        result = {
            "agent": "botz-architect",
            "plan": description,
            "steps": steps,
            "step_count": step_count,
        }
        print(json.dumps(result, indent=2))
    else:
        print()
        for s in steps:
            print(f"  [ ] {s['index']}. {s['action']}")
        print()
    return 0


# ---------------------------------------------------------------------------
# Audit command (botz-auditor persona)
# ---------------------------------------------------------------------------
_SECURITY_PATTERNS = [
    (r"\beval\s*\(", "eval() call — potential code injection"),
    (r"\bexec\s*\(", "exec() call — potential code injection"),
    (r"shell\s*=\s*True", "shell=True in subprocess — command injection risk"),
    (r"password\s*=\s*[\"'][^\"']+[\"']", "hardcoded password"),
    (r"secret\s*=\s*[\"'][^\"']+[\"']", "hardcoded secret"),
    (r"api_key\s*=\s*[\"']sk-", "hardcoded API key"),
]


def cmd_audit(args: argparse.Namespace) -> int:
    """Run an audit check using the botz-auditor persona."""
    target = Path(args.target)
    _render_agent_header("botz-auditor", "Audit", str(target))

    findings: List[Dict[str, Any]] = []
    passed = True

    # Check 1: File existence
    if not target.exists():
        findings.append({"check": "existence", "status": "FAIL", "detail": f"{target} not found"})
        passed = False
    else:
        findings.append({"check": "existence", "status": "PASS", "detail": str(target)})

        content = target.read_text(encoding="utf-8", errors="replace")

        # Check 2: Syntax validation
        suffix = target.suffix.lower()
        if suffix == ".py":
            try:
                ast.parse(content)
                findings.append({"check": "syntax", "status": "PASS", "detail": "valid Python"})
            except SyntaxError as e:
                findings.append({"check": "syntax", "status": "FAIL", "detail": f"line {e.lineno}: {e.msg}"})
                passed = False
        elif suffix in (".yaml", ".yml"):
            try:
                import yaml
                yaml.safe_load(content)
                findings.append({"check": "syntax", "status": "PASS", "detail": "valid YAML"})
            except Exception as e:
                findings.append({"check": "syntax", "status": "FAIL", "detail": str(e)[:120]})
                passed = False
        elif suffix == ".json":
            try:
                json.loads(content)
                findings.append({"check": "syntax", "status": "PASS", "detail": "valid JSON"})
            except json.JSONDecodeError as e:
                findings.append({"check": "syntax", "status": "FAIL", "detail": str(e)[:120]})
                passed = False
        else:
            findings.append({"check": "syntax", "status": "SKIP", "detail": f"no validator for {suffix}"})

        # Check 3: Security patterns
        sec_hits = []
        for pattern, desc in _SECURITY_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                sec_hits.append({"pattern": desc, "count": len(matches)})
        if sec_hits:
            findings.append({"check": "security", "status": "WARN", "detail": sec_hits})
        else:
            findings.append({"check": "security", "status": "PASS", "detail": "no suspicious patterns"})

    verdict = "PASS" if passed else "FAIL"

    if args.json:
        print(json.dumps({"agent": "botz-auditor", "target": str(target), "verdict": verdict, "findings": findings}, indent=2))
    else:
        print()
        for f in findings:
            icon = {"PASS": "✓", "FAIL": "✗", "WARN": "⚠", "SKIP": "—"}.get(f["status"], "?")
            print(f"  {icon} {f['check']}: {f['detail']}")
        print()
        print(f"  Verdict: {_BOLD}{verdict}{_RST}")
    return 0 if passed else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    """BoTZ CLI entry point."""
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="botz",
        description="BoTZ CLI — Agent Persona Selector + Identity Tool",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    subparsers = parser.add_subparsers(dest="command")

    # Shared parent for --json inheritance
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--json", action="store_true", help="JSON output")

    # whoami
    subparsers.add_parser("whoami", help="Resolve current agent identity", parents=[json_parent])

    # theme
    theme_p = subparsers.add_parser("theme", help="Display agent theme", parents=[json_parent])
    theme_p.add_argument("agent_id", help="Agent ID")

    # persona (with sub-subcommands)
    persona_p = subparsers.add_parser("persona", help="Manage agent personas")
    persona_sub = persona_p.add_subparsers(dest="persona_cmd")
    persona_sub.add_parser("list", help="List all available personas", parents=[json_parent])
    persona_sub.add_parser("current", help="Show current persona", parents=[json_parent])
    sel_p = persona_sub.add_parser("select", help="Select a persona", parents=[json_parent])
    sel_p.add_argument("agent_id", help="Agent ID to select")
    sel_p.add_argument("--export", action="store_true", help="Output shell export commands")

    # plan (botz-architect)
    plan_p = subparsers.add_parser("plan", help="Create a structured plan (botz-architect)", parents=[json_parent])
    plan_p.add_argument("-d", "--description", required=True, help="Plan description")

    # audit (botz-auditor)
    audit_p = subparsers.add_parser("audit", help="Audit a file for quality/security (botz-auditor)", parents=[json_parent])
    audit_p.add_argument("-t", "--target", required=True, help="File to audit")

    args = parser.parse_args()

    if args.command == "whoami":
        return cmd_whoami(args)
    elif args.command == "theme":
        return cmd_theme(args)
    elif args.command == "plan":
        return cmd_plan(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command == "persona":
        if args.persona_cmd == "list":
            return cmd_persona_list(args)
        elif args.persona_cmd == "select":
            return cmd_persona_select(args)
        elif args.persona_cmd == "current":
            return cmd_persona_current(args)
        else:
            persona_p.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())



