#!/usr/bin/env python3
"""Generate a Codex/Claude integration audit matrix for PMOVES submodules."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Iterable


FOCUS_HINTS = (
    "archon",
    "agent",
    "botz",
    "gateway",
    "hirag",
    "flute",
    "evo",
    "chit",
    "cipher",
    "pipecat",
    "creator",
    "hyperdimensions",
    "a2ui",
    "transcribe",
)


def _load_submodule_paths(gitmodules: Path) -> list[str]:
    if not gitmodules.exists():
        return []
    pattern = re.compile(r"^\s*path\s*=\s*(.+?)\s*$")
    paths: list[str] = []
    for line in gitmodules.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            paths.append(match.group(1).strip())
    return paths


def _has_any(path: Path, rels: Iterable[str]) -> bool:
    return any((path / rel).exists() for rel in rels)


def _codex_artifacts(path: Path) -> list[str]:
    found: list[str] = []
    for rel in (".codex", "config/codex", "docs/AGENTS/CODEX_OPERATOR_HOME.md", ".codex/README.md"):
        candidate = path / rel
        if candidate.exists():
            found.append(str(candidate.relative_to(path)))
    return found


def _focus_score(name: str) -> int:
    lowered = name.lower()
    return sum(1 for token in FOCUS_HINTS if token in lowered)


def _priority(focus: int, has_codex: bool) -> str:
    if focus > 0 and not has_codex:
        return "high"
    if focus > 0 and has_codex:
        return "good"
    if has_codex:
        return "medium"
    return "low"


def _recommendation(priority: str) -> str:
    if priority == "high":
        return "Add Codex home/docs and wire to PMOVES integration hooks before audit sign-off."
    if priority == "good":
        return "Keep Codex + Claude docs aligned; no immediate action."
    if priority == "medium":
        return "Validate Codex docs are complete and linked from module README."
    return "No immediate action required unless this module becomes active."


def main() -> int:
    pmoves_root = Path(__file__).resolve().parents[1]
    repo_root = pmoves_root.parent
    gitmodules = repo_root / ".gitmodules"
    output = pmoves_root / "docs" / "AGENTS" / "CODEX_SUBMODULE_INTEGRATION_AUDIT.md"

    rows: list[dict[str, object]] = []
    for rel in _load_submodule_paths(gitmodules):
        module_path = repo_root / rel
        module_name = Path(rel).name
        claude = _has_any(module_path, [".claude", "CLAUDE.md", ".claude/CLAUDE.md"])
        agents = _has_any(module_path, ["AGENTS.md", "docs/AGENTS"])
        codex = _codex_artifacts(module_path)
        focus = _focus_score(module_name)
        priority = _priority(focus, bool(codex))
        rows.append(
            {
                "submodule": rel,
                "claude": "yes" if claude else "no",
                "agents": "yes" if agents else "no",
                "codex": ", ".join(f"`{c}`" for c in codex) if codex else "-",
                "focus": focus,
                "priority": priority,
                "recommendation": _recommendation(priority),
            }
        )

    rows.sort(key=lambda r: (str(r["priority"]), -int(r["focus"]), str(r["submodule"]).lower()))

    total = len(rows)
    claude_count = sum(1 for r in rows if r["claude"] == "yes")
    codex_count = sum(1 for r in rows if r["codex"] != "-")
    focus_count = sum(1 for r in rows if int(r["focus"]) > 0)
    focus_with_codex = sum(1 for r in rows if int(r["focus"]) > 0 and r["codex"] != "-")

    lines = [
        "# Codex Submodule Integration Audit",
        f"_Generated: {dt.date.today().isoformat()}_",
        "",
        "## Summary",
        f"- Total submodules scanned: **{total}**",
        f"- Submodules with Claude context assets: **{claude_count}**",
        f"- Submodules with Codex artifacts or references: **{codex_count}**",
        f"- Focus modules (CHIT/Geometry/Agentic stack): **{focus_count}**",
        f"- Focus modules with Codex coverage: **{focus_with_codex}**",
        "",
        "## Matrix",
        "| Submodule | Claude | AGENTS | Codex Artifacts | Focus Terms | Priority | Recommendation |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        lines.append(
            f"| `{row['submodule']}` | {row['claude']} | {row['agents']} | {row['codex']} | "
            f"{row['focus']} | `{row['priority']}` | {row['recommendation']} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
