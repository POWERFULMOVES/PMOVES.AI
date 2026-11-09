#!/usr/bin/env python3
"""Skills parity across AGInTZ: does every harness see the same skills?

Operator canon (2026-10-11, verbatim): "parrity across AGInTZ skills cant only
work for one". A skill that exists only under `.claude/skills/` is a parity
bug: Codex, OpenCode, Kimi Code, Kilo, Crush and Hermes each read their OWN
directory and never look in Claude's.

This tool answers one question per harness: of the skills Claude Code sees,
which does this harness also see? It is a REPORT first (exit 0, honest gaps
listed) and a gate only on request (`--strict`), so the seam can be wired
before the check turns red in CI.

Where each harness looks is NOT hardcoded here. The source of truth is the
agent table in the PMOVES-skills fork (`skills/PMOVES-skills/src/agents.ts`,
vercel-labs/skills); the table below is the pinned fallback for a checkout
where that submodule is not populated, and the tool warns when the two differ.

Usage:
  python pmoves/tools/skills_parity.py            # report
  python pmoves/tools/skills_parity.py --json     # machine-readable
  python pmoves/tools/skills_parity.py --strict   # exit 1 on any gap
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ".claude/skills"
AGENTS_TS = REPO_ROOT / "skills" / "PMOVES-skills" / "src" / "agents.ts"

#: The harnesses PMOVES overlays (pmoves/docs/TAC/TAC_HARNESS_OVERLAY_MAP.md)
#: -> the project-level skills dir each reads. Pinned from agents.ts on
#: 2026-10-11; `harness_dirs()` prefers the live table when it is present.
PINNED_DIRS: dict[str, str] = {
    "claude-code": ".claude/skills",
    "codex": ".agents/skills",
    "opencode": ".agents/skills",
    "kimi-code-cli": ".agents/skills",
    "kilo": ".kilocode/skills",
    "crush": ".crush/skills",
    "hermes-agent": ".hermes/skills",
}

_ENTRY = re.compile(
    r"name:\s*'(?P<name>[a-z0-9-]+)'.*?skillsDir:\s*'(?P<dir>[^']+)'", re.S
)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def live_dirs(agents_ts: Path | None = None) -> dict[str, str]:
    """Parse `name -> skillsDir` for the pinned harnesses out of agents.ts.

    Returns an empty dict when the submodule is not populated. Only the
    harness names in PINNED_DIRS are returned; the table lists ~75 agents.
    """
    agents_ts = agents_ts or AGENTS_TS  # resolved at call time (tests patch it)
    if not agents_ts.is_file():
        return {}
    text = agents_ts.read_text(encoding="utf-8", errors="replace")
    found: dict[str, str] = {}
    for m in _ENTRY.finditer(text):
        name = m.group("name")
        if name in PINNED_DIRS and name not in found:
            found[name] = m.group("dir")
    return found


def harness_dirs() -> tuple[dict[str, str], list[str]]:
    """Effective harness -> skills dir map, plus warnings about drift."""
    warnings: list[str] = []
    live = live_dirs()
    effective = dict(PINNED_DIRS)
    if not live:
        warnings.append(f"{_rel(AGENTS_TS)} not present; using the pinned table")
        return effective, warnings
    for name, pinned in PINNED_DIRS.items():
        got = live.get(name)
        if got is None:
            warnings.append(f"{name}: not in the live agents.ts table; pinned {pinned}")
        elif got != pinned:
            warnings.append(f"{name}: agents.ts says {got}, pinned table says {pinned}; using agents.ts")
            effective[name] = got
    return effective, warnings


def skills_in(directory: Path) -> set[str]:
    """Skill names = subdirectories that carry a SKILL.md."""
    if not directory.is_dir():
        return set()
    return {p.parent.name for p in directory.glob("*/SKILL.md")}


def build_report(root: Path = REPO_ROOT) -> dict:
    dirs, warnings = harness_dirs()
    canonical = skills_in(root / CANONICAL)
    harnesses: dict[str, dict] = {}
    for name, rel in dirs.items():
        seen = skills_in(root / rel)
        harnesses[name] = {
            "dir": rel,
            "dir_exists": (root / rel).is_dir(),
            "present": sorted(canonical & seen),
            "missing": sorted(canonical - seen),
            "harness_only": sorted(seen - canonical),
        }
    gaps = {k: v["missing"] for k, v in harnesses.items() if v["missing"]}
    return {
        "canonical_dir": CANONICAL,
        "canonical_count": len(canonical),
        "harnesses": harnesses,
        "gaps": gaps,
        "warnings": warnings,
    }


def _print(report: dict) -> None:
    print(f"canonical: {report['canonical_dir']} ({report['canonical_count']} skills)")
    for name, h in report["harnesses"].items():
        state = "" if h["dir_exists"] else " (dir absent)"
        print(
            f"  {name:14s} {h['dir']:18s} present {len(h['present']):3d} "
            f"missing {len(h['missing']):3d} harness-only {len(h['harness_only']):3d}{state}"
        )
    for w in report["warnings"]:
        print(f"warn: {w}")
    if report["gaps"]:
        n = sum(len(v) for v in report["gaps"].values())
        print(f"PARITY GAP: {n} missing placements across {len(report['gaps'])} harnesses")
    else:
        print("PARITY OK: every harness sees every canonical skill")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any parity gap")
    args = ap.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print(report)
    if args.strict and report["gaps"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
